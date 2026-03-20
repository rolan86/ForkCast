"""Common action format produced by all simulation engines."""

import json
from dataclasses import dataclass, field
from typing import Any


class ActionType:
    """Simulation action types supported by all engines."""

    CREATE_POST = "CREATE_POST"
    LIKE_POST = "LIKE_POST"
    DISLIKE_POST = "DISLIKE_POST"
    CREATE_COMMENT = "CREATE_COMMENT"
    FOLLOW = "FOLLOW"
    MUTE = "MUTE"
    DO_NOTHING = "DO_NOTHING"


@dataclass
class Action:
    """A single simulation action — common output format for both engines."""

    round: int
    timestamp: str
    agent_id: int
    agent_name: str
    platform: str
    action_type: str
    action_args: dict[str, Any] = field(default_factory=dict)
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "platform": self.platform,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "success": self.success,
        }

    def to_jsonl(self) -> str:
        """Serialize to a single JSON line (no trailing newline)."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Action":
        return cls(
            round=d["round"],
            timestamp=d["timestamp"],
            agent_id=d["agent_id"],
            agent_name=d["agent_name"],
            platform=d["platform"],
            action_type=d["action_type"],
            action_args=d.get("action_args", {}),
            success=d.get("success", True),
        )
