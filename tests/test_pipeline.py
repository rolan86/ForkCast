import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def _setup_project(tmp_data_dir, tmp_db_path):
    """Create a project with uploaded files for pipeline testing."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)

    project_id = "proj_test"
    uploads = tmp_data_dir / project_id / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "doc.txt").write_text("Alice is a researcher at TechCorp. She studies AI.")
    (uploads / "notes.md").write_text("# Notes\nBob manages the ML team at TechCorp.")

    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'What will TechCorp do?', datetime('now'))",
            (project_id,),
        )
        for fname, size in [("doc.txt", 50), ("notes.md", 50)]:
            conn.execute(
                "INSERT INTO project_files (project_id, filename, path, size, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (project_id, fname, str(uploads / fname), size),
            )

    return project_id


def _mock_claude():
    """Mock ClaudeClient for pipeline tests."""
    from forkcast.llm.client import ClaudeClient, LLMResponse

    client = ClaudeClient.__new__(ClaudeClient)
    client.default_model = "claude-sonnet-4-6"
    client._client = MagicMock()

    ontology = {
        "entity_types": [
            {"name": "Person", "description": "Individual", "attributes": []},
            {"name": "Organization", "description": "Company", "attributes": []},
        ],
        "relationship_types": [
            {"name": "WORKS_AT", "description": "Employment"},
        ],
    }
    client.complete = MagicMock(return_value=LLMResponse(
        text=json.dumps(ontology),
        input_tokens=50,
        output_tokens=100,
        model="claude-sonnet-4-6",
    ))

    client.tool_use = MagicMock(return_value=LLMResponse(
        text="",
        tool_calls=[{
            "id": "call_1",
            "name": "extract_entities",
            "input": {
                "entities": [
                    {"name": "Alice", "type": "Person", "description": "Researcher", "attributes": {}},
                    {"name": "TechCorp", "type": "Organization", "description": "Tech company", "attributes": {}},
                ],
                "relationships": [
                    {"source": "Alice", "target": "TechCorp", "type": "WORKS_AT", "fact": "Alice works at TechCorp"},
                ],
            },
        }],
        input_tokens=50,
        output_tokens=100,
        model="claude-sonnet-4-6",
        stop_reason="tool_use",
    ))

    return client


def test_build_graph_pipeline_end_to_end(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    result = build_graph_pipeline(
        db_path=tmp_db_path,
        data_dir=tmp_data_dir,
        project_id=project_id,
        client=client,
        domains_dir=tmp_domains_dir,
    )

    assert result["status"] == "complete"
    assert result["node_count"] >= 2
    assert result["edge_count"] >= 1
    assert result["graph_id"].startswith("graph_")
    project_dir = tmp_data_dir / project_id
    assert (project_dir / "graph.json").exists()


def test_pipeline_updates_project_status(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    from forkcast.db.connection import get_db
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    build_graph_pipeline(
        db_path=tmp_db_path, data_dir=tmp_data_dir, project_id=project_id,
        client=client, domains_dir=tmp_domains_dir,
    )

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT status FROM projects WHERE id = ?", (project_id,)).fetchone()
    assert row["status"] == "graph_built"


def test_pipeline_records_graph_in_db(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    from forkcast.db.connection import get_db
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    result = build_graph_pipeline(
        db_path=tmp_db_path, data_dir=tmp_data_dir, project_id=project_id,
        client=client, domains_dir=tmp_domains_dir,
    )

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT * FROM graphs WHERE id = ?", (result["graph_id"],)).fetchone()
    assert row is not None
    assert row["project_id"] == project_id
    assert row["node_count"] >= 2


def test_pipeline_logs_token_usage(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    from forkcast.db.connection import get_db
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    build_graph_pipeline(
        db_path=tmp_db_path, data_dir=tmp_data_dir, project_id=project_id,
        client=client, domains_dir=tmp_domains_dir,
    )

    with get_db(tmp_db_path) as conn:
        row = conn.execute(
            "SELECT * FROM token_usage WHERE project_id = ?", (project_id,)
        ).fetchone()
    assert row is not None
    assert row["stage"] == "graph_pipeline"
    assert row["input_tokens"] > 0
    assert row["output_tokens"] > 0


def test_pipeline_progress_callback(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()
    progress_events = []

    build_graph_pipeline(
        db_path=tmp_db_path, data_dir=tmp_data_dir, project_id=project_id,
        client=client, domains_dir=tmp_domains_dir,
        on_progress=lambda **kwargs: progress_events.append(kwargs),
    )

    stages = [e["stage"] for e in progress_events]
    assert "extracting_text" in stages
    assert "generating_ontology" in stages
    assert "extracting_entities" in stages
    assert "building_graph" in stages
