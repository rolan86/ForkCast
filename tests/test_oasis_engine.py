"""Tests for OASIS in-process simulation engine."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import AgentProfile, SimulationConfig
from forkcast.simulation.oasis_engine import (
    OasisEngine,
    _convert_profiles_to_twitter_csv,
    _convert_profiles_to_reddit_json,
    _trace_row_to_action,
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


class TestConvertProfilesToTwitterCSV:
    def test_csv_header_matches_oasis_format(self):
        profiles = _make_profiles(2)
        csv_text = _convert_profiles_to_twitter_csv(profiles)
        lines = csv_text.strip().splitlines()
        assert lines[0].strip() == "user_id,name,username,user_char,description"
        assert len(lines) == 3  # header + 2 profiles

    def test_csv_maps_fields_correctly(self):
        profiles = _make_profiles(1)
        csv_text = _convert_profiles_to_twitter_csv(profiles)
        import csv as csv_mod
        import io
        reader = csv_mod.DictReader(io.StringIO(csv_text))
        row = next(reader)
        assert row["user_id"] == "0"  # agent_id -> user_id
        assert row["name"] == "Agent0"
        assert row["username"] == "agent0"
        assert row["user_char"] == "Persona 0"  # persona -> user_char
        assert row["description"] == "Bio 0"  # bio -> description

    def test_csv_excludes_dropped_fields(self):
        profiles = _make_profiles(1)
        csv_text = _convert_profiles_to_twitter_csv(profiles)
        import csv as csv_mod
        import io
        reader = csv_mod.DictReader(io.StringIO(csv_text))
        row = next(reader)
        assert "age" not in row
        assert "gender" not in row
        assert "profession" not in row
        assert "interests" not in row


class TestConvertProfilesToRedditJSON:
    def test_json_is_list(self):
        profiles = _make_profiles(2)
        data = _convert_profiles_to_reddit_json(profiles)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_json_has_oasis_fields(self):
        profiles = _make_profiles(1)
        data = _convert_profiles_to_reddit_json(profiles)
        assert "user_id" in data[0]
        assert "username" in data[0]
        assert "persona" in data[0]
        assert "karma" in data[0]
        assert data[0]["karma"] == 0
        assert "mbti" in data[0]
        assert data[0]["mbti"] == ""
        assert "country" in data[0]
        assert data[0]["country"] == ""

    def test_json_drops_old_fields(self):
        profiles = _make_profiles(1)
        data = _convert_profiles_to_reddit_json(profiles)
        assert "agent_id" not in data[0]
        assert "profession" not in data[0]
        assert "interests" not in data[0]


class TestExtractTraceActions:
    def test_create_post(self):
        profiles = _make_profiles(2)
        row = {"user_id": 0, "action": "create_post", "info": json.dumps({"content": "Hello"}), "created_at": "2026-03-20T10:00:00Z"}
        action = _trace_row_to_action(row, round_num=1, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.CREATE_POST
        assert action.action_args["content"] == "Hello"
        assert action.platform == "twitter"
        assert action.agent_name == "Agent0"
        assert action.round == 1

    def test_like_post_with_agent_name_lookup(self):
        profiles = _make_profiles(3)
        row = {"user_id": 1, "action": "like_post", "info": "{}", "created_at": "2026-03-20T10:01:00Z"}
        action = _trace_row_to_action(row, round_num=2, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.LIKE_POST
        assert action.agent_name == "Agent1"

    def test_repost_maps_to_create_post(self):
        profiles = _make_profiles(1)
        row = {"user_id": 0, "action": "repost", "info": "{}", "created_at": ""}
        action = _trace_row_to_action(row, round_num=1, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.CREATE_POST

    def test_unknown_action_maps_to_do_nothing(self):
        profiles = _make_profiles(1)
        row = {"user_id": 0, "action": "unknown_thing", "info": "{}", "created_at": ""}
        action = _trace_row_to_action(row, round_num=1, platform="twitter", profiles=profiles)
        assert action.action_type == ActionType.DO_NOTHING

    def test_do_nothing_action(self):
        profiles = _make_profiles(1)
        row = {"user_id": 0, "action": "do_nothing", "info": "{}", "created_at": ""}
        action = _trace_row_to_action(row, round_num=1, platform="reddit", profiles=profiles)
        assert action.action_type == ActionType.DO_NOTHING
        assert action.platform == "reddit"


class TestOasisEngine:
    def _mock_oasis_module(self):
        mock_oasis = MagicMock()
        mock_oasis.DefaultPlatformType.TWITTER = "twitter"
        mock_oasis.DefaultPlatformType.REDDIT = "reddit"
        mock_env = MagicMock()
        mock_env.reset = AsyncMock()
        mock_env.step = AsyncMock()
        mock_env.close = AsyncMock()
        mock_oasis.make.return_value = mock_env
        mock_oasis.generate_twitter_agent_graph = AsyncMock(return_value=MagicMock())
        mock_oasis.generate_reddit_agent_graph = AsyncMock(return_value=MagicMock())
        return mock_oasis, mock_env

    def _setup_trace_db(self, sim_dir, rows=None):
        """Create a mock OASIS trace DB with optional rows."""
        db_path = sim_dir / "oasis.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE trace (user_id INT, action TEXT, info TEXT, created_at TEXT)")
        for row in (rows or []):
            conn.execute("INSERT INTO trace VALUES (?, ?, ?, ?)", row)
        conn.commit()
        conn.close()
        return db_path

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_calls_on_action(self, mock_import):
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis
        actions_received = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            self._setup_trace_db(sim_dir, [
                (0, "create_post", '{"content": "Hello"}', "2026-03-20T10:00:00Z"),
                (1, "like_post", '{"post_id": 1}', "2026-03-20T10:01:00Z"),
            ])
            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=_make_profiles(2), config=_make_config(),
                platform="twitter", agent_mode="llm",
                on_action=lambda a: actions_received.append(a),
            )
        assert len(actions_received) == 2
        assert actions_received[0].action_type == ActionType.CREATE_POST

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_calls_on_round(self, mock_import):
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis
        rounds_seen = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            self._setup_trace_db(sim_dir)
            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=_make_profiles(2), config=_make_config(),
                platform="twitter", agent_mode="llm",
                on_round=lambda r, t: rounds_seen.append((r, t)),
            )
        assert len(rounds_seen) == 4  # 2 hours / 30 min
        assert rounds_seen[0] == (1, 4)

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_calls_on_round_complete(self, mock_import):
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis
        completes = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            self._setup_trace_db(sim_dir)
            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=_make_profiles(2), config=_make_config(),
                platform="twitter", agent_mode="llm",
                on_round_complete=lambda r, t: completes.append((r, t)),
            )
        assert len(completes) == 4

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_stop_breaks_loop(self, mock_import):
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis
        rounds_seen = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            self._setup_trace_db(sim_dir)
            engine = OasisEngine(sim_dir=sim_dir)

            original_step = mock_env.step
            call_count = [0]
            async def stop_on_second(*a, **kw):
                call_count[0] += 1
                if call_count[0] >= 2:
                    engine.stop()
                return await original_step(*a, **kw)
            mock_env.step = stop_on_second

            engine.run(
                profiles=_make_profiles(2), config=_make_config(),
                platform="twitter", agent_mode="llm",
                on_round=lambda r, t: rounds_seen.append(r),
            )
        assert len(rounds_seen) < 4

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_run_returns_result(self, mock_import):
        mock_oasis, mock_env = self._mock_oasis_module()
        mock_import.return_value = mock_oasis

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            self._setup_trace_db(sim_dir)
            engine = OasisEngine(sim_dir=sim_dir)
            result = engine.run(
                profiles=_make_profiles(2), config=_make_config(),
                platform="twitter", agent_mode="llm",
            )
        assert result["total_rounds"] == 4
        assert "total_actions" in result

    @patch("forkcast.simulation.oasis_engine._import_oasis")
    def test_import_failure_raises(self, mock_import):
        mock_import.side_effect = ImportError("No module named 'oasis'")
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = OasisEngine(sim_dir=Path(tmpdir))
            with pytest.raises(ImportError):
                engine.run(
                    profiles=_make_profiles(2), config=_make_config(),
                    platform="twitter", agent_mode="llm",
                )
