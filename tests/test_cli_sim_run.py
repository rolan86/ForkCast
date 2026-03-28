"""Tests for CLI sim start command."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from forkcast.cli.main import app
from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.simulation.models import RunResult


runner = CliRunner()


def _setup_prepared_sim(db_path, data_dir, domains_dir):
    """Create a prepared simulation."""
    init_db(db_path)
    project_id = "proj_cli"
    graph_id = "graph_cli"
    sim_id = "sim_cli_run"

    config = {
        "total_hours": 1, "minutes_per_round": 60,
        "peak_hours": [], "off_peak_hours": [],
        "peak_multiplier": 1.0, "off_peak_multiplier": 1.0,
        "seed_posts": [], "hot_topics": [],
        "narrative_direction": "", "agent_configs": [], "platform_config": {},
    }

    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "A researcher.", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"],
         "entity_type": "Person", "entity_source": "Alice"},
    ]

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "agents.json").write_text(json.dumps(profiles), encoding="utf-8")

    # Domain setup
    default_domain = domains_dir / "_default"
    default_domain.mkdir(parents=True, exist_ok=True)
    (default_domain / "manifest.yaml").write_text(
        "name: _default\nversion: '1.0'\ndescription: Default\nlanguage: en\n"
        "sim_engine: claude\nplatforms: [twitter]\n"
    )
    prompts = default_domain / "prompts"
    prompts.mkdir(exist_ok=True)
    for name in ["ontology.md", "persona.md", "report_guidelines.md", "config_gen.md"]:
        (prompts / name).write_text(f"# {name}\nPlaceholder.\n")

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'Test', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, created_at) VALUES (?, ?, 'complete', datetime('now'))",
            (graph_id, project_id),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, config_json, created_at) "
            "VALUES (?, ?, ?, 'prepared', 'claude', '[\"twitter\"]', ?, datetime('now'))",
            (sim_id, project_id, graph_id, json.dumps(config)),
        )

    return sim_id


class TestSimStart:
    @patch("forkcast.cli.sim_cmd.get_settings")
    @patch("forkcast.cli.sim_cmd.create_llm_client")
    def test_start_succeeds(self, mock_client_cls, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id = _setup_prepared_sim(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        settings.anthropic_api_key = "test-key"
        mock_settings.return_value = settings

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="", tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Hi"}}],
            input_tokens=100, output_tokens=50, model="claude-sonnet-4-6", stop_reason="tool_use",
        )
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["sim", "start", sim_id])
        assert result.exit_code == 0
        assert "complete" in result.output.lower() or "actions" in result.output.lower()

    @patch("forkcast.cli.sim_cmd.get_settings")
    def test_start_not_found(self, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)
        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        mock_settings.return_value = settings

        result = runner.invoke(app, ["sim", "start", "nonexistent"])
        assert result.exit_code == 1

    @patch("forkcast.cli.sim_cmd.get_settings")
    def test_start_wrong_status(self, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id = _setup_prepared_sim(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        mock_settings.return_value = settings

        # Change to created status
        with get_db(tmp_db_path) as conn:
            conn.execute("UPDATE simulations SET status = 'created' WHERE id = ?", (sim_id,))

        result = runner.invoke(app, ["sim", "start", sim_id])
        assert result.exit_code == 1

    @patch("forkcast.cli.sim_cmd.get_settings")
    @patch("forkcast.cli.sim_cmd.create_llm_client")
    def test_start_with_max_rounds(self, mock_client_cls, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id = _setup_prepared_sim(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        settings.anthropic_api_key = "test-key"
        mock_settings.return_value = settings

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="", tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=50, output_tokens=30, model="claude-sonnet-4-6", stop_reason="tool_use",
        )
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["sim", "start", sim_id, "--max-rounds", "1"])
        assert result.exit_code == 0
