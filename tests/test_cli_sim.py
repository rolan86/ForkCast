"""Tests for CLI simulation commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from forkcast.cli.sim_cmd import sim_app
from forkcast.db.connection import get_db, init_db
from forkcast.simulation.models import PrepareResult


runner = CliRunner()


def _setup_db(db_path, data_dir):
    """Create DB with project and graph."""
    init_db(db_path)
    project_id = "proj_test1"
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'Predict something', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'complete', 5, 3, ?, datetime('now'))",
            (f"graph_{project_id}", project_id, str(data_dir / project_id / "graph.json")),
        )

    # Create graph file
    graph_dir = data_dir / project_id
    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "Entity1", "type": "Person", "description": "desc"}],
        "edges": [],
    }))

    return project_id


class TestSimCreate:
    def test_create_simulation(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id = _setup_db(tmp_db_path, tmp_data_dir)

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            settings.data_dir = tmp_data_dir
            settings.domains_dir = tmp_domains_dir
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["create", project_id])

        assert result.exit_code == 0
        assert "Simulation created" in result.output
        assert "sim_" in result.output

    def test_create_simulation_project_not_found(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["create", "nonexistent"])

        assert result.exit_code == 1


class TestSimPrepare:
    def test_prepare_simulation(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id = _setup_db(tmp_db_path, tmp_data_dir)

        # Create a simulation in DB
        sim_id = "sim_test123"
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
                "VALUES (?, ?, ?, 'created', 'oasis', '[\"twitter\"]', datetime('now'))",
                (sim_id, project_id, f"graph_{project_id}"),
            )

        mock_result = PrepareResult(
            simulation_id=sim_id,
            profiles_count=5,
            profiles_path=str(tmp_data_dir / sim_id / "profiles" / "agents.json"),
            config_generated=True,
            tokens_used={"input": 1000, "output": 500},
        )

        with (
            patch("forkcast.cli.sim_cmd.get_settings") as mock_settings,
            patch("forkcast.cli.sim_cmd.prepare_simulation", return_value=mock_result) as mock_prepare,
            patch("forkcast.cli.sim_cmd.ClaudeClient"),
        ):
            settings = MagicMock()
            settings.db_path = tmp_db_path
            settings.data_dir = tmp_data_dir
            settings.domains_dir = tmp_domains_dir
            settings.anthropic_api_key = "test-key"
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["prepare", sim_id])

        assert result.exit_code == 0
        assert "5" in result.output  # profiles count


class TestSimList:
    def test_list_empty(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["list"])

        assert result.exit_code == 0
        assert "No simulations found" in result.output

    def test_list_with_simulations(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id = _setup_db(tmp_db_path, tmp_data_dir)

        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
                "VALUES (?, ?, ?, 'created', 'oasis', '[\"twitter\"]', datetime('now'))",
                ("sim_abc123", project_id, f"graph_{project_id}"),
            )

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["list"])

        assert result.exit_code == 0
        assert "sim_abc123" in result.output


class TestSimShow:
    def test_show_simulation(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id = _setup_db(tmp_db_path, tmp_data_dir)
        sim_id = "sim_show1"

        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
                "VALUES (?, ?, ?, 'created', 'oasis', '[\"twitter\",\"reddit\"]', datetime('now'))",
                (sim_id, project_id, f"graph_{project_id}"),
            )

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["show", sim_id])

        assert result.exit_code == 0
        assert sim_id in result.output
        assert project_id in result.output
        assert "twitter" in result.output

    def test_show_not_found(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)

        with patch("forkcast.cli.sim_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            mock_settings.return_value = settings

            result = runner.invoke(sim_app, ["show", "nonexistent"])

        assert result.exit_code == 1
