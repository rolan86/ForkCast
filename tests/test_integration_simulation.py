"""Integration tests — domain prompt registration and simulation pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.domains.loader import PROMPT_KEYS, load_domain, read_prompt
from forkcast.llm.client import ClaudeClient, LLMResponse
from forkcast.simulation.runner import run_simulation


class TestAgentSystemPromptRegistration:
    """Verify agent_system is registered in the domain loader."""

    def test_agent_system_in_prompt_keys(self):
        assert "agent_system" in PROMPT_KEYS

    def test_agent_system_loads_from_default_domain(self, tmp_domains_dir):
        domain = load_domain("_default", tmp_domains_dir)
        assert "agent_system" in domain.prompts
        content = read_prompt(domain, "agent_system")
        assert len(content) > 0

    def test_agent_system_loads_from_real_default_domain(self):
        """Load agent_system from the actual domains/_default directory."""
        real_domains = Path(__file__).resolve().parent.parent / "domains"
        if not (real_domains / "_default" / "manifest.yaml").exists():
            pytest.skip("Real domains dir not available")
        domain = load_domain("_default", real_domains)
        assert "agent_system" in domain.prompts
        content = read_prompt(domain, "agent_system")
        assert "{{ agent_name }}" in content
        assert "{{ persona }}" in content


class TestSimulationPipeline:
    """Integration test: create project + simulation, prepare, run."""

    def _setup_db_and_profiles(self, db_path, data_dir, simulation_id, domains_dir):
        """Create DB records and profile files for a ready-to-run simulation."""
        init_db(db_path)
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, name, requirement, domain, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                ("proj-1", "Test", "Predict X", "_default", "ready"),
            )
            config = {
                "total_hours": 0.5,
                "minutes_per_round": 30,
                "hot_topics": ["AI"],
                "seed_posts": ["Hello world"],
                "peak_hours": [],
                "off_peak_hours": [],
                "peak_multiplier": 1.0,
                "off_peak_multiplier": 1.0,
                "narrative_direction": "Discuss AI trends",
                "agent_configs": [],
                "platform_config": {},
            }
            conn.execute(
                "INSERT INTO simulations (id, project_id, engine_type, platforms, config_json, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (simulation_id, "proj-1", "claude", '["twitter"]', json.dumps(config), "prepared"),
            )

        # Write profiles
        profiles_dir = data_dir / simulation_id / "profiles"
        profiles_dir.mkdir(parents=True)
        profiles = [
            {
                "agent_id": 1,
                "name": "Alice",
                "username": "alice",
                "bio": "Test agent",
                "persona": "A curious researcher",
                "age": 30,
                "gender": "female",
                "profession": "Researcher",
                "interests": ["AI", "science"],
                "entity_type": "Person",
                "entity_source": "test",
            }
        ]
        (profiles_dir / "agents.json").write_text(json.dumps(profiles))

    def test_full_create_prepare_run_pipeline(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        """End-to-end: DB setup → run_simulation → completed status + actions persisted."""
        sim_id = "sim-integration-1"
        self._setup_db_and_profiles(tmp_db_path, tmp_data_dir, sim_id, tmp_domains_dir)

        # Mock the Claude client to return a create_post tool call
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.default_model = "claude-sonnet-4-20250514"
        mock_response = LLMResponse(
            text="",
            input_tokens=100,
            output_tokens=50,
            tool_calls=[{"name": "create_post", "input": {"content": "Integration test post!"}}],
        )
        mock_client.tool_use.return_value = mock_response

        progress_events = []

        result = run_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=mock_client,
            domains_dir=tmp_domains_dir,
            on_progress=lambda **kw: progress_events.append(kw),
        )

        # Verify result
        assert result.simulation_id == sim_id
        assert result.actions_count > 0
        assert result.total_rounds > 0

        # Verify DB status is completed
        with get_db(tmp_db_path) as conn:
            row = conn.execute("SELECT status FROM simulations WHERE id = ?", (sim_id,)).fetchone()
            assert row["status"] == "completed"

        # Verify actions persisted to DB
        with get_db(tmp_db_path) as conn:
            actions = conn.execute(
                "SELECT * FROM simulation_actions WHERE simulation_id = ?", (sim_id,)
            ).fetchall()
            assert len(actions) > 0
            assert actions[0]["action_type"] == "CREATE_POST"

        # Verify JSONL file written
        assert Path(result.actions_path).exists()

        # Verify progress events include key stages
        stages = [e["stage"] for e in progress_events]
        assert "loading" in stages
        assert "running" in stages
        assert "complete" in stages
