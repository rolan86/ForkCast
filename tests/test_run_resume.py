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
