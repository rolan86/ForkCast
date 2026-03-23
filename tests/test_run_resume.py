"""Tests for run resume: checkpoint system, state restore, multi-platform."""

import json
from pathlib import Path

import pytest

from forkcast.simulation.state import SimulationState


class TestCheckpointWriteRead:
    def test_write_and_read_checkpoint(self, tmp_path):
        from forkcast.simulation.runner import write_checkpoint, read_checkpoint

        sim_dir = tmp_path / "sim1"
        sim_dir.mkdir()

        state = SimulationState(platform="twitter", feed_weights={"recency": 0.5})
        state.add_post(0, "alice", "hello", "2026-01-01T00:00:00Z")

        write_checkpoint(sim_dir, round_num=5, total_rounds=20, platform="twitter",
                         platform_index=0, completed_platforms=[], state=state)

        cp = read_checkpoint(sim_dir)
        assert cp is not None
        assert cp["last_completed_round"] == 5
        assert cp["total_rounds"] == 20
        assert cp["platform"] == "twitter"

        # Verify state snapshot exists
        state_path = sim_dir / "sim_state_r5.json"
        assert state_path.exists()
        restored = SimulationState.from_dict(json.loads(state_path.read_text()))
        assert len(restored.posts) == 1

    def test_read_checkpoint_returns_none_when_missing(self, tmp_path):
        from forkcast.simulation.runner import read_checkpoint
        assert read_checkpoint(tmp_path / "nonexistent") is None

    def test_cleanup_checkpoint(self, tmp_path):
        from forkcast.simulation.runner import write_checkpoint, cleanup_checkpoint

        sim_dir = tmp_path / "sim2"
        sim_dir.mkdir()

        state = SimulationState(platform="twitter", feed_weights={})
        write_checkpoint(sim_dir, 3, 10, "twitter", 0, [], state)
        assert (sim_dir / "checkpoint.json").exists()

        cleanup_checkpoint(sim_dir)
        assert not (sim_dir / "checkpoint.json").exists()
        assert not list(sim_dir.glob("sim_state_r*.json"))


class TestCheckpointWiring:
    """Verify that run_simulation actually calls write_checkpoint during execution."""

    def test_checkpoint_written_during_run(self, tmp_path, tmp_db_path, tmp_domains_dir):
        """run_simulation should write checkpoints via on_round_complete callback."""
        from unittest.mock import MagicMock, patch
        from forkcast.simulation.runner import run_simulation

        db_path = tmp_db_path
        data_dir = tmp_path / "data"
        domains_dir = tmp_domains_dir

        from forkcast.db.connection import init_db, get_db
        init_db(db_path)

        # Create project, graph, and simulation
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('p1', '_default', 'Test', 'created', 'test req', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO graphs (id, project_id, file_path, status, created_at) "
                "VALUES ('g1', 'p1', '/fake/graph.json', 'completed', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, "
                "config_json, created_at) VALUES ('sim1', 'p1', 'g1', 'prepared', 'claude', "
                "'[\"twitter\"]', ?, datetime('now'))",
                (json.dumps({
                    "total_hours": 1,
                    "minutes_per_round": 60,
                    "peak_hours": [],
                    "off_peak_hours": [],
                    "peak_multiplier": 1.0,
                    "off_peak_multiplier": 1.0,
                    "seed_posts": [],
                    "hot_topics": [],
                    "narrative_direction": "",
                    "agent_configs": [],
                    "platform_config": {},
                }),),
            )

        # Write profiles
        profiles_dir = data_dir / "sim1" / "profiles"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "agents.json").write_text(json.dumps([{
            "agent_id": 0, "name": "Alice", "username": "alice",
            "bio": "Test", "persona": "Curious", "age": 30,
            "gender": "female", "profession": "Engineer",
            "interests": ["tech"], "entity_type": "Person", "entity_source": "Alice",
        }]))

        # Mock Claude client to return a do_nothing tool call
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = [{"name": "do_nothing", "input": {"reason": "test"}}]
        mock_response.input_tokens = 10
        mock_response.output_tokens = 5
        mock_client.tool_use.return_value = mock_response
        mock_client.default_model = "claude-haiku-4-5-20251001"

        checkpoints_written = []
        original_write = __import__('forkcast.simulation.runner', fromlist=['write_checkpoint']).write_checkpoint

        def tracking_write(*args, **kwargs):
            checkpoints_written.append(kwargs.get('round_num', args[1] if len(args) > 1 else None))
            return original_write(*args, **kwargs)

        with patch('forkcast.simulation.runner.write_checkpoint', side_effect=tracking_write):
            result = run_simulation(
                db_path=db_path,
                data_dir=data_dir,
                simulation_id="sim1",
                client=mock_client,
                domains_dir=domains_dir,
            )

        # Checkpoint should have been written at least once (1 round)
        assert len(checkpoints_written) >= 1
        assert result.actions_count >= 1


from httpx import ASGITransport, AsyncClient
from forkcast.api.app import create_app
from forkcast.db.connection import get_db, init_db


@pytest.fixture
def app(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    from forkcast.config import reset_settings
    reset_settings()
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestResumeRunEndpoint:
    @pytest.mark.anyio
    async def test_start_rejects_completed_simulation(self, client, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, status, engine_type, platforms, created_at) "
                "VALUES ('sim_done', 'p1', 'completed', 'claude', '[\"twitter\"]', datetime('now'))"
            )
        resp = await client.post("/api/simulations/sim_done/start")
        assert resp.status_code == 400
