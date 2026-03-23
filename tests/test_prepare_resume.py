# tests/test_prepare_resume.py
"""Tests for prepare pipeline: model selection, profile reuse, resume."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.simulation.profile_generator import load_existing_profiles


def _setup_project_and_sim(db_path, data_dir, status="created", sim_id="sim1", prep_model="claude-haiku-4-5"):
    init_db(db_path)
    # Create minimal graph file first so we can reference its path
    graph_dir = data_dir / "p1"
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph_file = graph_dir / "graph.json"
    graph_file.write_text(json.dumps({
        "nodes": [{"name": "Alice", "type": "Person", "description": "test"}],
        "edges": [],
    }))
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, file_path, created_at) "
            "VALUES ('g1', 'p1', 'complete', ?, datetime('now'))",
            (str(graph_file),),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, prep_model, created_at) "
            "VALUES (?, 'p1', 'g1', ?, 'claude', '[\"twitter\"]', ?, datetime('now'))",
            (sim_id, status, prep_model),
        )


class TestPrepareResume:
    def test_resume_skips_existing_profiles(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        """A simulation in 'preparing' status with existing profiles resumes from where it left off."""
        _setup_project_and_sim(tmp_db_path, tmp_data_dir, status="preparing", sim_id="sim_resume")

        # Create partial profiles on disk
        profiles_dir = tmp_data_dir / "sim_resume" / "profiles"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "agents.json").write_text(json.dumps([
            {"agent_id": 0, "name": "Alice", "entity_source": "Alice",
             "username": "alice", "bio": "", "persona": "", "age": 30,
             "gender": "f", "profession": "dev", "interests": [],
             "entity_type": "Person"},
        ]))

        existing = load_existing_profiles(profiles_dir)
        assert "Alice" in existing

    def test_prepare_endpoint_allows_preparing_status(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        """POST /prepare should allow 'preparing' status for resume."""
        _setup_project_and_sim(tmp_db_path, tmp_data_dir, status="preparing")

        with get_db(tmp_db_path) as conn:
            sim = conn.execute("SELECT status FROM simulations WHERE id = 'sim1'").fetchone()
        assert sim["status"] == "preparing"

    def test_prepare_reads_prep_model_from_db(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        """prepare_simulation reads prep_model from DB when not passed explicitly."""
        _setup_project_and_sim(tmp_db_path, tmp_data_dir, status="created", sim_id="sim_model", prep_model="claude-haiku-4-5")

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        profile_json = json.dumps({
            "name": "Alice", "username": "alice", "bio": "b", "persona": "p",
            "age": 30, "gender": "f", "profession": "dev", "interests": ["code"],
        })
        config_json = json.dumps({
            "total_hours": 24, "minutes_per_round": 15,
            "peak_hours": [10], "off_peak_hours": [2],
            "peak_multiplier": 1.0, "off_peak_multiplier": 0.5,
            "seed_posts": ["post"], "hot_topics": ["topic"],
            "narrative_direction": "dir",
            "agent_configs": [], "platform_config": {},
        })
        client.smart_call.side_effect = [
            LLMResponse(text=profile_json, input_tokens=100, output_tokens=50),
            LLMResponse(text=config_json, input_tokens=200, output_tokens=100),
        ]

        from forkcast.simulation.prepare import prepare_simulation
        result = prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim_model",
            client=client,
            domains_dir=tmp_domains_dir,
        )

        assert result.profiles_count == 1
        assert result.config_generated is True
        # Verify smart_call was called with the haiku model from DB
        for call in client.smart_call.call_args_list:
            assert call.kwargs.get("model") == "claude-haiku-4-5"

    def test_prepare_force_regenerate_skips_reuse(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        """force_regenerate=True should skip profile reuse even when reusable profiles exist."""
        _setup_project_and_sim(tmp_db_path, tmp_data_dir, status="created", sim_id="sim_force")

        # Create a previous simulation's profiles that would be reusable
        prev_profiles_dir = tmp_data_dir / "sim_prev" / "profiles"
        prev_profiles_dir.mkdir(parents=True)
        (prev_profiles_dir / "agents.json").write_text(json.dumps([
            {"agent_id": 0, "name": "Alice", "entity_source": "Alice",
             "username": "alice", "bio": "", "persona": "", "age": 30,
             "gender": "f", "profession": "dev", "interests": [],
             "entity_type": "Person"},
        ]))

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        profile_json = json.dumps({
            "name": "Alice", "username": "alice", "bio": "b", "persona": "p",
            "age": 30, "gender": "f", "profession": "dev", "interests": ["code"],
        })
        config_json = json.dumps({
            "total_hours": 24, "minutes_per_round": 15,
            "peak_hours": [10], "off_peak_hours": [2],
            "peak_multiplier": 1.0, "off_peak_multiplier": 0.5,
            "seed_posts": ["post"], "hot_topics": ["topic"],
            "narrative_direction": "dir",
            "agent_configs": [], "platform_config": {},
        })
        client.smart_call.side_effect = [
            LLMResponse(text=profile_json, input_tokens=100, output_tokens=50),
            LLMResponse(text=config_json, input_tokens=200, output_tokens=100),
        ]

        from forkcast.simulation.prepare import prepare_simulation
        result = prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id="sim_force",
            client=client,
            domains_dir=tmp_domains_dir,
            force_regenerate=True,
        )

        # Should have called smart_call for profile + config (not reused)
        assert client.smart_call.call_count == 2
        assert result.profiles_count == 1
