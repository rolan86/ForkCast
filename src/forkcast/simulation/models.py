"""Data models for simulation preparation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentProfile:
    """A simulation agent's profile, generated from a knowledge graph entity."""

    agent_id: int
    name: str
    username: str
    bio: str
    persona: str
    age: int
    gender: str
    profession: str
    interests: list[str]
    entity_type: str
    entity_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "username": self.username,
            "bio": self.bio,
            "persona": self.persona,
            "age": self.age,
            "gender": self.gender,
            "profession": self.profession,
            "interests": self.interests,
            "entity_type": self.entity_type,
            "entity_source": self.entity_source,
        }


@dataclass
class SimulationConfig:
    """Generated simulation parameters."""

    total_hours: int
    minutes_per_round: int
    peak_hours: list[int]
    off_peak_hours: list[int]
    peak_multiplier: float
    off_peak_multiplier: float
    seed_posts: list[str]
    hot_topics: list[str]
    narrative_direction: str
    agent_configs: list[dict[str, Any]]
    platform_config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_hours": self.total_hours,
            "minutes_per_round": self.minutes_per_round,
            "peak_hours": self.peak_hours,
            "off_peak_hours": self.off_peak_hours,
            "peak_multiplier": self.peak_multiplier,
            "off_peak_multiplier": self.off_peak_multiplier,
            "seed_posts": self.seed_posts,
            "hot_topics": self.hot_topics,
            "narrative_direction": self.narrative_direction,
            "agent_configs": self.agent_configs,
            "platform_config": self.platform_config,
        }


@dataclass
class PrepareResult:
    """Result of the simulation prepare pipeline."""

    simulation_id: str
    profiles_count: int
    profiles_path: str
    config_generated: bool
    tokens_used: dict[str, int] = field(default_factory=dict)


@dataclass
class RunResult:
    """Result of running a simulation."""

    simulation_id: str
    actions_count: int
    total_rounds: int
    actions_path: str
    tokens_used: dict[str, int] = field(default_factory=dict)
