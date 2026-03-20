"""Tests for OASIS subprocess simulation engine."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import AgentProfile, SimulationConfig
from forkcast.simulation.oasis_engine import (
    OasisEngine,
    _convert_profiles_to_csv,
    _convert_profiles_to_reddit_json,
    _monitor_actions_file,
    _parse_oasis_action,
)


def _make_profiles(n=3):
    return [
        AgentProfile(
            agent_id=i,
            name=f"Agent{i}",
            username=f"agent{i}",
            bio=f"Bio {i}",
            persona=f"Persona {i}",
            age=30 + i,
            gender="female" if i % 2 == 0 else "male",
            profession=f"Profession{i}",
            interests=["AI", "tech"],
            entity_type="Person",
            entity_source=f"Entity{i}",
        )
        for i in range(n)
    ]


def _make_config():
    return SimulationConfig(
        total_hours=2,
        minutes_per_round=30,
        peak_hours=[10, 11],
        off_peak_hours=[0, 1, 2, 3],
        peak_multiplier=1.5,
        off_peak_multiplier=0.3,
        seed_posts=[],
        hot_topics=[],
        narrative_direction="",
        agent_configs=[],
        platform_config={},
    )


class TestConvertProfilesToCSV:
    def test_csv_has_header(self):
        profiles = _make_profiles(2)
        csv_text = _convert_profiles_to_csv(profiles)
        lines = csv_text.strip().split("\n")
        assert lines[0].startswith("agent_id")
        assert len(lines) == 3  # header + 2 profiles

    def test_csv_contains_profile_data(self):
        profiles = _make_profiles(1)
        csv_text = _convert_profiles_to_csv(profiles)
        assert "Agent0" in csv_text
        assert "agent0" in csv_text


class TestConvertProfilesToRedditJSON:
    def test_json_is_list(self):
        profiles = _make_profiles(2)
        data = _convert_profiles_to_reddit_json(profiles)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_json_has_required_fields(self):
        profiles = _make_profiles(1)
        data = _convert_profiles_to_reddit_json(profiles)
        assert "agent_id" in data[0]
        assert "username" in data[0]
        assert "persona" in data[0]


class TestParseOasisAction:
    def test_parse_tweet(self):
        raw = {"action": "tweet", "content": "Hello", "agent_id": 0, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}
        action = _parse_oasis_action(raw, platform="twitter")
        assert action.action_type == ActionType.CREATE_POST
        assert action.action_args["content"] == "Hello"
        assert action.platform == "twitter"

    def test_parse_like(self):
        raw = {"action": "like", "post_id": 5, "agent_id": 1, "round": 2, "timestamp": "2026-03-20T10:01:00Z"}
        action = _parse_oasis_action(raw, platform="twitter")
        assert action.action_type == ActionType.LIKE_POST

    def test_parse_reply(self):
        raw = {"action": "reply", "post_id": 3, "content": "Great!", "agent_id": 2, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}
        action = _parse_oasis_action(raw, platform="reddit")
        assert action.action_type == ActionType.CREATE_COMMENT
        assert action.platform == "reddit"

    def test_parse_unknown_action(self):
        raw = {"action": "unknown_thing", "agent_id": 0, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}
        action = _parse_oasis_action(raw, platform="twitter")
        assert action.action_type == ActionType.DO_NOTHING


class TestMonitorActionsFile:
    def test_monitor_reads_new_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)

        try:
            actions_received = []
            stop_event = threading.Event()

            def on_action(action):
                actions_received.append(action)
                if len(actions_received) >= 2:
                    stop_event.set()

            # Start monitor in background
            t = threading.Thread(
                target=_monitor_actions_file,
                args=(path, "twitter", on_action, stop_event),
            )
            t.start()

            # Write actions after a brief delay
            time.sleep(0.1)
            with open(path, "a") as f:
                f.write(json.dumps({"action": "tweet", "content": "Hello", "agent_id": 0, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}) + "\n")
                f.write(json.dumps({"action": "like", "post_id": 0, "agent_id": 1, "round": 1, "timestamp": "2026-03-20T10:00:01Z"}) + "\n")
                f.flush()

            t.join(timeout=5)
            assert len(actions_received) >= 2
            assert actions_received[0].action_type == ActionType.CREATE_POST
        finally:
            path.unlink(missing_ok=True)


class TestOasisEngine:
    @patch("forkcast.simulation.oasis_engine.subprocess")
    def test_run_writes_profile_files(self, mock_subprocess):
        profiles = _make_profiles(2)
        config = _make_config()

        # Mock subprocess to exit quickly
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.wait.return_value = 0
        mock_proc.pid = 12345
        mock_subprocess.Popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                on_action=lambda a: None,
            )

            # Should have written twitter CSV profile file
            csv_path = sim_dir / "twitter_profiles.csv"
            assert csv_path.exists()

    @patch("forkcast.simulation.oasis_engine.subprocess")
    def test_stop_terminates_process(self, mock_subprocess):
        profiles = _make_profiles(2)
        config = _make_config()

        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, None, 0]  # Running, running, done
        mock_proc.wait.return_value = 0
        mock_proc.pid = 12345
        mock_subprocess.Popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            engine = OasisEngine(sim_dir=Path(tmpdir))
            # Stop immediately
            engine.stop()
            engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                on_action=lambda a: None,
            )
