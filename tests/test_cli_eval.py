"""Tests for eval CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from forkcast.cli.eval_cmd import eval_app
from forkcast.db.connection import get_db, init_db

runner = CliRunner()


def _setup_project_with_sim(db_path: Path, data_dir: Path) -> tuple[str, str, str]:
    """Create a project, simulation, and report for eval testing."""
    init_db(db_path)
    project_id = "proj_eval1"
    sim_id = "sim_eval1"
    report_id = "rpt_eval1"

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, ontology_json, created_at) "
            "VALUES (?, 'social-media', 'Test', 'graph_built', 'Predict reaction', ?, datetime('now'))",
            (project_id, json.dumps({"entity_types": [{"name": "Influencer"}, {"name": "Brand"}, {"name": "Analyst"}]})),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, created_at) "
            "VALUES (?, ?, 'completed', datetime('now'))",
            (sim_id, project_id),
        )
        conn.execute(
            "INSERT INTO reports (id, simulation_id, status, content_markdown, created_at) "
            "VALUES (?, ?, 'completed', ?, datetime('now'))",
            (report_id, sim_id, "## Section 1\nText about @agent_0 engagement.\n\n## Section 2\nMore about @agent_1 replies.\n\n## Section 3\nConclusion with agent_2 analysis." + ("x" * 500)),
        )
        # Add some simulation actions
        for i in range(10):
            conn.execute(
                "INSERT INTO simulation_actions (simulation_id, agent_id, agent_name, action_type, content, round, platform, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, 'twitter', datetime('now'))",
                (sim_id, i % 3, f"agent_{i%3}", ["CREATE_POST", "LIKE_POST", "CREATE_COMMENT"][i % 3],
                 json.dumps({"content": f"Post {i}"}), (i // 3) + 1),
            )

    # Create agents.json
    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profiles = [
        {"agent_id": j, "name": f"Agent{j}", "username": f"agent_{j}",
         "bio": "A bio", "persona": "A persona", "age": 30,
         "gender": "female", "profession": "Engineer", "interests": ["tech"]}
        for j in range(3)
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))

    # Create graph.json for entity count gate
    project_dir = data_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "graph.json").write_text(json.dumps({
        "nodes": [
            {"name": "Agent0", "type": "Influencer"},
            {"name": "Agent1", "type": "Brand"},
            {"name": "Agent2", "type": "Analyst"},
        ],
        "edges": [],
    }))

    return project_id, sim_id, report_id


class TestEvalRun:
    def test_eval_run_gates_only(self, tmp_data_dir, tmp_db_path):
        project_id, sim_id, _ = _setup_project_with_sim(tmp_db_path, tmp_data_dir)

        with patch("forkcast.cli.eval_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            settings.data_dir = tmp_data_dir
            mock_settings.return_value = settings

            result = runner.invoke(eval_app, ["run", project_id, "--simulation-id", sim_id, "--gates-only"])

        assert result.exit_code == 0
        assert "GATES" in result.output

    def test_eval_run_saves_scorecard(self, tmp_data_dir, tmp_db_path):
        project_id, sim_id, _ = _setup_project_with_sim(tmp_db_path, tmp_data_dir)

        with patch("forkcast.cli.eval_cmd.get_settings") as mock_settings:
            settings = MagicMock()
            settings.db_path = tmp_db_path
            settings.data_dir = tmp_data_dir
            mock_settings.return_value = settings

            runner.invoke(eval_app, ["run", project_id, "--simulation-id", sim_id, "--gates-only"])

        evals_dir = tmp_data_dir / project_id / "evals"
        assert evals_dir.exists()
        files = list(evals_dir.glob("*.json"))
        assert len(files) == 1
