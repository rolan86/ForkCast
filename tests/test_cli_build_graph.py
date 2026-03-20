import json
from unittest.mock import patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_pipeline_result():
    return {
        "status": "complete",
        "graph_id": "graph_abc123",
        "node_count": 5,
        "edge_count": 4,
        "entities_extracted": 5,
        "chunks_processed": 2,
    }


def test_build_graph_command(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    """forkcast project build-graph should trigger the pipeline."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import get_db, init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    project_id = "proj_cli_test"
    uploads = tmp_data_dir / project_id / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "doc.txt").write_text("Test document content.")

    with get_db(get_settings().db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'CLI Test', 'created', 'Test Q?', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO project_files (project_id, filename, path, size, created_at) "
            "VALUES (?, 'doc.txt', ?, 25, datetime('now'))",
            (project_id, str(uploads / "doc.txt")),
        )

    from forkcast.cli.main import app

    with patch("forkcast.cli.project_cmd.build_graph_pipeline", return_value=_mock_pipeline_result()):
        result = runner.invoke(app, ["project", "build-graph", project_id])

    assert result.exit_code == 0
    assert "graph_abc123" in result.stdout or "complete" in result.stdout


def test_build_graph_command_missing_project(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    """forkcast project build-graph with bad ID should fail."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    from forkcast.cli.main import app

    result = runner.invoke(app, ["project", "build-graph", "proj_nonexistent"])
    assert result.exit_code != 0
