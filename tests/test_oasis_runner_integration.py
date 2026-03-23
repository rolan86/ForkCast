"""Integration tests: runner -> OasisEngine -> DB flow with mocked OASIS."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from forkcast.db.connection import init_db, get_db
from forkcast.simulation.runner import run_simulation
from forkcast.llm.client import ClaudeClient


def _seed_db(db_path, project_id="proj_1", sim_id="sim_1", agent_mode="llm"):
    """Create a minimal DB with a prepared simulation."""
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, requirement, domain, status, created_at) "
            "VALUES (?, 'Test', 'test req', 'social_media', 'ready', datetime('now'))",
            (project_id,),
        )
        config = {
            "total_hours": 1,
            "minutes_per_round": 30,
            "peak_hours": [10],
            "off_peak_hours": [0],
            "peak_multiplier": 1.5,
            "off_peak_multiplier": 0.3,
            "seed_posts": [],
            "hot_topics": [],
            "narrative_direction": "",
            "agent_configs": [],
            "platform_config": {},
        }
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, engine_type, platforms, agent_mode, config_json, created_at) "
            "VALUES (?, ?, 'prepared', 'oasis', '[\"twitter\"]', ?, ?, datetime('now'))",
            (sim_id, project_id, agent_mode, json.dumps(config)),
        )


def _seed_profiles(data_dir, sim_id="sim_1"):
    """Write a minimal agents.json."""
    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {
            "agent_id": 0, "name": "Alice", "username": "alice",
            "bio": "Test", "persona": "Curious", "age": 30,
            "gender": "female", "profession": "Engineer",
            "interests": ["AI"], "entity_type": "Person", "entity_source": "test",
        },
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


def _setup_oasis_trace_db(data_dir, sim_id="sim_1"):
    """Create OASIS trace DB with sample data."""
    oasis_db_path = data_dir / sim_id / "oasis.db"
    oasis_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(oasis_db_path))
    conn.execute("CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)")
    conn.execute("INSERT INTO trace VALUES (0, 'create_post', '{\"content\": \"Hello\"}', '2026-03-20T10:00:00Z')")
    conn.commit()
    conn.close()


def _setup_domain(domains_dir):
    """Create minimal social_media domain."""
    (domains_dir / "social_media").mkdir(parents=True)
    (domains_dir / "social_media" / "manifest.yaml").write_text(
        "name: social_media\nplatforms: [twitter]\nsim_engine: oasis\n"
    )


class TestRunnerOasisIntegration:
    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_runner_completes_with_oasis(self, mock_import, tmp_path):
        mock_oasis = MagicMock()
        mock_env = MagicMock()
        mock_env.reset = AsyncMock()
        mock_env.step = AsyncMock()
        mock_env.close = AsyncMock()
        mock_oasis.make.return_value = mock_env
        mock_oasis.generate_twitter_agent_graph = AsyncMock(return_value=MagicMock())
        mock_import.return_value = mock_oasis

        db_path = tmp_path / "test.db"
        data_dir = tmp_path / "data"
        domains_dir = tmp_path / "domains"

        _seed_db(db_path, agent_mode="native")
        _seed_profiles(data_dir)
        _setup_oasis_trace_db(data_dir)
        _setup_domain(domains_dir)

        client = MagicMock(spec=ClaudeClient)
        result = run_simulation(
            db_path=db_path, data_dir=data_dir, simulation_id="sim_1",
            client=client, domains_dir=domains_dir,
        )
        assert result.actions_count >= 0

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_actions_persisted_to_db(self, mock_import, tmp_path):
        mock_oasis = MagicMock()
        mock_env = MagicMock()
        mock_env.reset = AsyncMock()
        mock_env.step = AsyncMock()
        mock_env.close = AsyncMock()
        mock_oasis.make.return_value = mock_env
        mock_oasis.generate_twitter_agent_graph = AsyncMock(return_value=MagicMock())
        mock_import.return_value = mock_oasis

        db_path = tmp_path / "test.db"
        data_dir = tmp_path / "data"
        domains_dir = tmp_path / "domains"

        _seed_db(db_path)
        _seed_profiles(data_dir)
        _setup_oasis_trace_db(data_dir)
        _setup_domain(domains_dir)

        client = MagicMock(spec=ClaudeClient)
        run_simulation(
            db_path=db_path, data_dir=data_dir, simulation_id="sim_1",
            client=client, domains_dir=domains_dir,
        )

        with get_db(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM simulation_actions WHERE simulation_id = 'sim_1'"
            ).fetchone()[0]
            status = conn.execute(
                "SELECT status FROM simulations WHERE id = 'sim_1'"
            ).fetchone()["status"]

        assert count >= 1
        assert status == "completed"
