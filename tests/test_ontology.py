import json
from unittest.mock import MagicMock


def _mock_claude_for_ontology():
    """Create a mock ClaudeClient that returns a valid ontology JSON."""
    from forkcast.llm.client import ClaudeClient, LLMResponse

    client = ClaudeClient.__new__(ClaudeClient)
    client.default_model = "claude-sonnet-4-6"
    client._client = MagicMock()

    ontology = {
        "entity_types": [
            {"name": "Analyst", "description": "Financial analyst", "attributes": ["firm", "specialty"]},
            {"name": "Company", "description": "Public company", "attributes": ["sector", "market_cap"]},
            {"name": "Person", "description": "Individual", "attributes": []},
            {"name": "Organization", "description": "Institution", "attributes": []},
        ],
        "relationship_types": [
            {"name": "COVERS", "description": "Analyst covers a company"},
            {"name": "WORKS_AT", "description": "Person works at organization"},
        ],
    }

    client.complete = MagicMock(return_value=LLMResponse(
        text=json.dumps(ontology),
        input_tokens=100,
        output_tokens=200,
        model="claude-sonnet-4-6",
    ))
    return client, ontology


def test_generate_ontology_returns_parsed_dict():
    """generate_ontology should return parsed ontology dict and token counts."""
    from forkcast.graph.ontology import generate_ontology

    client, expected = _mock_claude_for_ontology()
    result, tokens = generate_ontology(
        client=client,
        requirement="What will happen to tech stocks?",
        document_summary="Report about tech industry trends.",
        hints_path=None,
    )
    assert "entity_types" in result
    assert "relationship_types" in result
    assert len(result["entity_types"]) >= 2
    assert tokens["input"] > 0
    assert tokens["output"] > 0


def test_generate_ontology_includes_fallbacks():
    """Ontology should always include Person and Organization fallbacks."""
    from forkcast.graph.ontology import generate_ontology

    client, _ = _mock_claude_for_ontology()
    result, _ = generate_ontology(
        client=client,
        requirement="Test question",
        document_summary="Test summary",
        hints_path=None,
    )
    names = [et["name"] for et in result["entity_types"]]
    assert "Person" in names
    assert "Organization" in names


def test_generate_ontology_adds_missing_fallbacks():
    """_ensure_fallbacks should add Person/Organization when LLM omits them."""
    from forkcast.graph.ontology import generate_ontology
    from forkcast.llm.client import ClaudeClient, LLMResponse

    client = ClaudeClient.__new__(ClaudeClient)
    client._client = MagicMock()
    ontology_without_fallbacks = {
        "entity_types": [
            {"name": "Technology", "description": "A technology or tool", "attributes": []},
        ],
        "relationship_types": [
            {"name": "USES", "description": "Uses a technology"},
        ],
    }
    client.complete = MagicMock(return_value=LLMResponse(
        text=json.dumps(ontology_without_fallbacks),
        input_tokens=50,
        output_tokens=100,
        model="claude-sonnet-4-6",
    ))

    result, _ = generate_ontology(
        client=client,
        requirement="Test",
        document_summary="Summary",
        hints_path=None,
    )
    names = [et["name"] for et in result["entity_types"]]
    assert "Technology" in names
    assert "Person" in names
    assert "Organization" in names


def test_generate_ontology_uses_hints(tmp_path):
    """When hints_path is provided, hints should be included in the prompt."""
    from forkcast.graph.ontology import generate_ontology

    hints = tmp_path / "hints.yaml"
    hints.write_text("max_entity_types: 5\nrequired_fallbacks:\n  - Person\n  - Organization\n")

    client, _ = _mock_claude_for_ontology()
    generate_ontology(
        client=client,
        requirement="Test",
        document_summary="Summary",
        hints_path=hints,
    )

    call_args = client.complete.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
    user_msg = messages[0]["content"] if messages else ""
    assert "max_entity_types" in user_msg or "5" in user_msg


def test_generate_ontology_uses_custom_system_prompt():
    """generate_ontology should use provided system_prompt instead of hardcoded one."""
    from forkcast.graph.ontology import generate_ontology

    client, _ = _mock_claude_for_ontology()
    custom_prompt = "You are a social media ontology expert. Focus on influencers and brands."

    generate_ontology(
        client=client,
        requirement="How will influencers react?",
        document_summary="Social media trends.",
        hints_path=None,
        system_prompt=custom_prompt,
    )

    call_args = client.complete.call_args
    system = call_args.kwargs.get("system") or call_args[1].get("system", "")
    assert system == custom_prompt


def test_generate_ontology_falls_back_to_default_prompt():
    """generate_ontology should use hardcoded prompt when no system_prompt provided."""
    from forkcast.graph.ontology import generate_ontology, _ONTOLOGY_SYSTEM_PROMPT

    client, _ = _mock_claude_for_ontology()

    generate_ontology(
        client=client,
        requirement="Test",
        document_summary="Summary",
        hints_path=None,
    )

    call_args = client.complete.call_args
    system = call_args.kwargs.get("system") or call_args[1].get("system", "")
    assert system == _ONTOLOGY_SYSTEM_PROMPT


def test_pipeline_passes_domain_ontology_prompt(tmp_path, tmp_domains_dir):
    """build_graph_pipeline should read the domain's ontology.md and pass it to generate_ontology()."""
    from unittest.mock import MagicMock, patch

    from forkcast.graph.pipeline import build_graph_pipeline

    # Write a custom ontology prompt to the _default domain
    ontology_prompt = tmp_domains_dir / "_default" / "prompts" / "ontology.md"
    ontology_prompt.write_text("Custom domain ontology prompt for testing.")

    # Set up minimal DB and project
    db_path = tmp_path / "test.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    from forkcast.db.connection import init_db

    init_db(db_path)

    # Create a project with a file
    from forkcast.db.connection import get_db

    seed_file = tmp_path / "seed.txt"
    seed_file.write_text("Test document content for pipeline integration test.")

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, domain, requirement, status, created_at) "
            "VALUES ('p1', 'Test', '_default', 'Test question', 'created', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO project_files (project_id, filename, path, size, created_at) "
            "VALUES ('p1', 'seed.txt', ?, 50, datetime('now'))",
            (str(seed_file),),
        )

    mock_client = MagicMock()
    mock_client.default_model = "claude-sonnet-4-6"
    # Mock generate_ontology to return valid result
    mock_ontology = (
        {"entity_types": [], "relationship_types": []},
        {"input": 100, "output": 50},
    )

    with patch("forkcast.graph.pipeline.generate_ontology", return_value=mock_ontology) as mock_gen, \
         patch("forkcast.graph.pipeline.extract_from_chunks") as mock_extract, \
         patch("forkcast.graph.pipeline.create_vector_store"), \
         patch("forkcast.graph.pipeline.index_chunks"), \
         patch("forkcast.graph.pipeline.index_entities"):
        # Mock extraction result
        mock_extract.return_value = MagicMock(
            entities=[], relationships=[],
            chunks_processed=0, total_input_tokens=0, total_output_tokens=0,
        )

        build_graph_pipeline(
            db_path=db_path,
            data_dir=data_dir,
            project_id="p1",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        # Verify generate_ontology was called with the domain's ontology prompt
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs.get("system_prompt") == "Custom domain ontology prompt for testing."


def test_generate_ontology_stores_to_project(tmp_db_path):
    """store_ontology should update projects.ontology_json."""
    from forkcast.db.connection import get_db, init_db
    from forkcast.graph.ontology import store_ontology

    init_db(tmp_db_path)
    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('proj_001', '_default', 'Test', 'created', 'Q?', datetime('now'))"
        )

    ontology = {"entity_types": [{"name": "Person"}], "relationship_types": []}
    store_ontology(tmp_db_path, "proj_001", ontology)

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT ontology_json FROM projects WHERE id = 'proj_001'").fetchone()

    stored = json.loads(row["ontology_json"])
    assert stored["entity_types"][0]["name"] == "Person"
