"""Tests for simulation action dataclass."""

import json
from datetime import datetime, timezone

from forkcast.simulation.action import Action, ActionType


class TestActionType:
    def test_action_types_exist(self):
        assert ActionType.CREATE_POST == "CREATE_POST"
        assert ActionType.LIKE_POST == "LIKE_POST"
        assert ActionType.DISLIKE_POST == "DISLIKE_POST"
        assert ActionType.CREATE_COMMENT == "CREATE_COMMENT"
        assert ActionType.FOLLOW == "FOLLOW"
        assert ActionType.MUTE == "MUTE"
        assert ActionType.DO_NOTHING == "DO_NOTHING"


class TestAction:
    def test_create_action(self):
        action = Action(
            round=1,
            timestamp="2026-03-20T10:30:00Z",
            agent_id=3,
            agent_name="user3",
            platform="twitter",
            action_type=ActionType.CREATE_POST,
            action_args={"content": "Hello world"},
            success=True,
        )
        assert action.round == 1
        assert action.agent_id == 3
        assert action.action_type == "CREATE_POST"
        assert action.success is True

    def test_action_to_dict(self):
        action = Action(
            round=1,
            timestamp="2026-03-20T10:30:00Z",
            agent_id=3,
            agent_name="user3",
            platform="reddit",
            action_type=ActionType.CREATE_POST,
            action_args={"content": "Test post"},
            success=True,
        )
        d = action.to_dict()
        assert d["round"] == 1
        assert d["agent_id"] == 3
        assert d["platform"] == "reddit"
        assert d["action_type"] == "CREATE_POST"
        assert d["action_args"]["content"] == "Test post"

    def test_action_to_jsonl(self):
        action = Action(
            round=2,
            timestamp="2026-03-20T11:00:00Z",
            agent_id=0,
            agent_name="alice",
            platform="twitter",
            action_type=ActionType.LIKE_POST,
            action_args={"post_id": 5},
            success=True,
        )
        line = action.to_jsonl()
        parsed = json.loads(line)
        assert parsed["round"] == 2
        assert parsed["action_type"] == "LIKE_POST"
        assert not line.endswith("\n")  # No trailing newline

    def test_action_from_dict(self):
        d = {
            "round": 1,
            "timestamp": "2026-03-20T10:30:00Z",
            "agent_id": 3,
            "agent_name": "user3",
            "platform": "twitter",
            "action_type": "CREATE_POST",
            "action_args": {"content": "Hello"},
            "success": True,
        }
        action = Action.from_dict(d)
        assert action.round == 1
        assert action.agent_name == "user3"
        assert action.action_type == "CREATE_POST"

    def test_do_nothing_action(self):
        action = Action(
            round=1,
            timestamp="2026-03-20T10:30:00Z",
            agent_id=0,
            agent_name="bob",
            platform="twitter",
            action_type=ActionType.DO_NOTHING,
            action_args={},
            success=True,
        )
        assert action.action_type == "DO_NOTHING"
        assert action.action_args == {}
