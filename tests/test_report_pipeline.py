"""Tests for report generation pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.report.pipeline import generate_report


def _setup_simulation(db_path, data_dir, sim_id="sim1", project_id="proj1"):
    """Create a completed simulation with profiles and actions."""
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'ready', 'Predict X', datetime('now'))",
            (project_id,),
        )
        config = {
            "total_hours": 1, "minutes_per_round": 30,
            "hot_topics": [], "seed_posts": [],
            "peak_hours": [], "off_peak_hours": [],
            "peak_multiplier": 1.0, "off_peak_multiplier": 1.0,
            "narrative_direction": "", "agent_configs": [],
            "platform_config": {},
        }
        conn.execute(
            "INSERT INTO simulations (id, project_id, engine_type, platforms, config_json, status) "
            "VALUES (?, ?, 'claude', '[\"twitter\"]', ?, 'completed')",
            (sim_id, project_id, json.dumps(config)),
        )
        conn.execute(
            "INSERT INTO simulation_actions (simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
            "VALUES (?, 1, 0, 'alice', 'CREATE_POST', ?, 'twitter', '2026-01-01T00:00:00')",
            (sim_id, json.dumps({"content": "Hello world"})),
        )

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [{
        "agent_id": 0, "name": "Alice", "username": "alice",
        "bio": "Test", "persona": "A curious tester", "age": 30,
        "gender": "female", "profession": "Tester",
        "interests": ["testing"], "entity_type": "Person",
        "entity_source": "test",
    }]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestGenerateReport:
    def test_generates_report(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_simulation(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.tool_use.return_value = LLMResponse(
            text="# Prediction Report\n\nThis is the report content.",
            input_tokens=500, output_tokens=300, tool_calls=[],
        )

        result = generate_report(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        assert result.simulation_id == "sim1"
        assert "Prediction Report" in result.content_markdown
        assert result.tool_rounds >= 0

    def test_persists_to_db(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_simulation(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.tool_use.return_value = LLMResponse(
            text="# Report", input_tokens=100, output_tokens=50, tool_calls=[],
        )

        result = generate_report(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        with get_db(tmp_db_path) as conn:
            report = conn.execute("SELECT * FROM reports WHERE id = ?", (result.report_id,)).fetchone()
            assert report is not None
            assert report["status"] == "completed"
            assert "Report" in report["content_markdown"]

    def test_tool_use_loop(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_simulation(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.tool_use.side_effect = [
            LLMResponse(
                text="", input_tokens=200, output_tokens=100,
                tool_calls=[{"id": "t1", "name": "simulation_data", "input": {"query_type": "summary"}}],
            ),
            LLMResponse(
                text="# Report with data\n\nBased on 1 action.",
                input_tokens=300, output_tokens=200, tool_calls=[],
            ),
        ]

        result = generate_report(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        assert result.tool_rounds == 1
        assert "Report with data" in result.content_markdown

    def test_emits_progress_events(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_simulation(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.tool_use.return_value = LLMResponse(
            text="# Report", input_tokens=100, output_tokens=50, tool_calls=[],
        )

        events = []
        generate_report(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim1",
            client=mock_client,
            domains_dir=tmp_domains_dir,
            on_progress=lambda **kw: events.append(kw),
        )

        stages = [e["stage"] for e in events]
        assert "loading" in stages
        assert "complete" in stages

    def test_sets_failed_on_error(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        _setup_simulation(tmp_db_path, tmp_data_dir)

        mock_client = MagicMock()
        mock_client.tool_use.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError):
            generate_report(
                db_path=tmp_db_path,
                data_dir=tmp_data_dir,
                simulation_id="sim1",
                client=mock_client,
                domains_dir=tmp_domains_dir,
            )

        with get_db(tmp_db_path) as conn:
            report = conn.execute("SELECT status FROM reports WHERE simulation_id = 'sim1'").fetchone()
            assert report["status"] == "failed"
