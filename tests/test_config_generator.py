"""Tests for simulation config generation via Claude extended thinking."""

import json
from unittest.mock import MagicMock

from forkcast.llm.client import LLMResponse
from forkcast.simulation.config_generator import generate_config, _build_config_prompt
from forkcast.simulation.models import AgentProfile, SimulationConfig


def _make_profiles(count=2):
    return [
        AgentProfile(
            agent_id=i, name=f"Agent {i}", username=f"agent{i}", bio=f"Bio {i}",
            persona=f"Persona {i}", age=30 + i, gender="nonbinary",
            profession="Analyst", interests=["data"],
            entity_type="Person", entity_source=f"Entity {i}",
        )
        for i in range(count)
    ]


def _mock_config_response():
    config_json = json.dumps({
        "total_hours": 48,
        "minutes_per_round": 30,
        "peak_hours": [9, 10, 11, 12, 17, 18, 19],
        "off_peak_hours": [0, 1, 2, 3, 4, 5],
        "peak_multiplier": 1.5,
        "off_peak_multiplier": 0.3,
        "seed_posts": ["Breaking news: major policy shift announced"],
        "hot_topics": ["policy", "regulation", "impact"],
        "narrative_direction": "From initial reaction to structured debate",
        "agent_configs": [
            {"agent_id": 0, "activity_level": 0.7, "posts_per_hour": 1.5},
            {"agent_id": 1, "activity_level": 0.5, "posts_per_hour": 1.0},
        ],
        "platform_config": {
            "feed_weights": {"recency": 0.4, "popularity": 0.4, "relevance": 0.2},
            "viral_threshold": 10,
            "echo_chamber_strength": 0.3,
        },
    })
    return LLMResponse(text=config_json, input_tokens=800, output_tokens=600)


class TestBuildConfigPrompt:
    def test_includes_entities_summary(self):
        profiles = _make_profiles(2)
        prompt = _build_config_prompt(
            profiles=profiles,
            requirement="What happens next?",
            config_template="Entities: {{ entities_summary }}\nQuestion: {{ requirement }}",
        )
        assert "Agent 0" in prompt
        assert "Agent 1" in prompt
        assert "What happens next?" in prompt


class TestGenerateConfig:
    def test_generate_config(self):
        client = MagicMock()
        client.think.return_value = _mock_config_response()
        profiles = _make_profiles(2)

        config, tokens = generate_config(
            client=client,
            profiles=profiles,
            requirement="Predict policy impact",
            config_template="Entities: {{ entities_summary }}",
        )

        assert isinstance(config, SimulationConfig)
        assert config.total_hours == 48
        assert config.minutes_per_round == 30
        assert len(config.seed_posts) == 1
        assert len(config.agent_configs) == 2
        assert tokens["input"] == 800
        assert tokens["output"] == 600
        client.think.assert_called_once()

    def test_config_strips_code_fences(self):
        client = MagicMock()
        config_json = json.dumps({
            "total_hours": 24, "minutes_per_round": 15,
            "peak_hours": [10], "off_peak_hours": [2],
            "peak_multiplier": 1.0, "off_peak_multiplier": 0.5,
            "seed_posts": ["post"], "hot_topics": ["topic"],
            "narrative_direction": "dir",
            "agent_configs": [], "platform_config": {},
        })
        client.think.return_value = LLMResponse(
            text=f"```json\n{config_json}\n```",
            input_tokens=100, output_tokens=50,
        )

        config, _ = generate_config(
            client=client,
            profiles=_make_profiles(1),
            requirement="q",
            config_template="t",
        )
        assert config.total_hours == 24

    def test_generate_config_validates_bounds(self):
        client = MagicMock()
        # hours below minimum
        config_json = json.dumps({
            "total_hours": 2, "minutes_per_round": 5,
            "peak_hours": [], "off_peak_hours": [],
            "peak_multiplier": 1.0, "off_peak_multiplier": 0.5,
            "seed_posts": [], "hot_topics": [],
            "narrative_direction": "dir",
            "agent_configs": [], "platform_config": {},
        })
        client.think.return_value = LLMResponse(
            text=config_json, input_tokens=100, output_tokens=50,
        )

        config, _ = generate_config(
            client=client,
            profiles=_make_profiles(1),
            requirement="q",
            config_template="t",
        )
        # Should clamp to spec minimums
        assert config.total_hours >= 12
        assert config.minutes_per_round >= 15
