"""Tests for Claude simulation engine."""

import json
from unittest.mock import MagicMock, patch

from forkcast.llm.client import LLMResponse
from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.claude_engine import (
    ClaudeEngine,
    AGENT_TOOLS,
    _build_agent_context,
    _parse_tool_action,
    _determine_active_agents,
)
from forkcast.simulation.models import AgentProfile, SimulationConfig
from forkcast.simulation.state import SimulationState


def _make_profiles(n=3):
    return [
        AgentProfile(
            agent_id=i,
            name=f"Agent{i}",
            username=f"agent{i}",
            bio=f"Bio {i}",
            persona=f"A thoughtful person who cares about topic {i}.",
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
        seed_posts=["What does the future hold for AI?"],
        hot_topics=["AI regulation", "open source models"],
        narrative_direction="Explore diverse perspectives on AI governance",
        agent_configs=[],
        platform_config={"feed_weights": {"recency": 0.5, "popularity": 0.3, "relevance": 0.2}},
    )


class TestAgentTools:
    def test_tools_list_has_required_tools(self):
        tool_names = {t["name"] for t in AGENT_TOOLS}
        assert "create_post" in tool_names
        assert "like_post" in tool_names
        assert "dislike_post" in tool_names
        assert "create_comment" in tool_names
        assert "follow_user" in tool_names
        assert "mute_user" in tool_names
        assert "do_nothing" in tool_names


class TestParseToolAction:
    def test_parse_create_post(self):
        tool_calls = [{"id": "1", "name": "create_post", "input": {"content": "Hello world"}}]
        action_type, action_args = _parse_tool_action(tool_calls)
        assert action_type == ActionType.CREATE_POST
        assert action_args["content"] == "Hello world"

    def test_parse_like_post(self):
        tool_calls = [{"id": "1", "name": "like_post", "input": {"post_id": 5}}]
        action_type, action_args = _parse_tool_action(tool_calls)
        assert action_type == ActionType.LIKE_POST
        assert action_args["post_id"] == 5

    def test_parse_do_nothing(self):
        tool_calls = [{"id": "1", "name": "do_nothing", "input": {"reason": "nothing interesting"}}]
        action_type, action_args = _parse_tool_action(tool_calls)
        assert action_type == ActionType.DO_NOTHING

    def test_parse_empty_tool_calls_returns_do_nothing(self):
        action_type, action_args = _parse_tool_action([])
        assert action_type == ActionType.DO_NOTHING

    def test_parse_create_comment(self):
        tool_calls = [{"id": "1", "name": "create_comment", "input": {"post_id": 2, "content": "Great point!"}}]
        action_type, action_args = _parse_tool_action(tool_calls)
        assert action_type == ActionType.CREATE_COMMENT
        assert action_args["post_id"] == 2
        assert action_args["content"] == "Great point!"

    def test_parse_follow_user(self):
        tool_calls = [{"id": "1", "name": "follow_user", "input": {"user_id": 3}}]
        action_type, action_args = _parse_tool_action(tool_calls)
        assert action_type == ActionType.FOLLOW
        assert action_args["user_id"] == 3


class TestDetermineActiveAgents:
    def setup_method(self):
        import random
        random.seed(42)  # Deterministic tests

    def test_peak_hour_more_agents(self):
        profiles = _make_profiles(10)
        config = _make_config()
        active_peak = _determine_active_agents(profiles, config, current_hour=10)
        active_offpeak = _determine_active_agents(profiles, config, current_hour=2)
        # Peak should have more or equal agents
        assert len(active_peak) >= len(active_offpeak)

    def test_always_at_least_one_agent(self):
        profiles = _make_profiles(3)
        config = _make_config()
        active = _determine_active_agents(profiles, config, current_hour=2)
        assert len(active) >= 1

    def test_normal_hour_returns_subset(self):
        profiles = _make_profiles(10)
        config = _make_config()
        active = _determine_active_agents(profiles, config, current_hour=14)
        assert 1 <= len(active) <= 10


class TestBuildAgentContext:
    def test_context_includes_persona(self):
        profiles = _make_profiles(2)
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        context = _build_agent_context(
            profile=profiles[0],
            state=state,
            round_num=1,
            hot_topics=["AI"],
            seed_posts=[],
            agent_system_template="You are {{ agent_name }}. {{ persona }}",
        )
        assert "Agent0" in context["system"]
        assert "thoughtful" in context["system"]

    def test_context_includes_feed(self):
        profiles = _make_profiles(2)
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        state.add_post(1, "agent1", "Interesting take", "2026-03-20T10:00:00Z")
        context = _build_agent_context(
            profile=profiles[0],
            state=state,
            round_num=2,
            hot_topics=["AI"],
            seed_posts=[],
            agent_system_template="You are {{ agent_name }}. {{ persona }}",
        )
        user_msg = context["messages"][0]["content"]
        assert "Interesting take" in user_msg

    def test_context_includes_hot_topics(self):
        profiles = _make_profiles(1)
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        context = _build_agent_context(
            profile=profiles[0],
            state=state,
            round_num=1,
            hot_topics=["AI regulation", "open source"],
            seed_posts=[],
            agent_system_template="You are {{ agent_name }}. {{ persona }}",
        )
        user_msg = context["messages"][0]["content"]
        assert "AI regulation" in user_msg

    def test_round_1_includes_seed_posts(self):
        profiles = _make_profiles(1)
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        context = _build_agent_context(
            profile=profiles[0],
            state=state,
            round_num=1,
            hot_topics=[],
            seed_posts=["What does AI mean for humanity?"],
            agent_system_template="You are {{ agent_name }}. {{ persona }}",
        )
        user_msg = context["messages"][0]["content"]
        assert "What does AI mean for humanity?" in user_msg


class TestClaudeEngineRun:
    def test_run_produces_actions(self):
        profiles = _make_profiles(2)
        config = _make_config()
        config.total_hours = 1
        config.minutes_per_round = 60  # 1 round only

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"

        def mock_tool_use(**kwargs):
            # Phase 1 (decision model) — decide to create_post
            if kwargs.get("model") == "claude-haiku-4-5":
                return LLMResponse(
                    text="",
                    tool_calls=[{"id": "1", "name": "create_post", "input": {}}],
                    input_tokens=100, output_tokens=50,
                    model="claude-haiku-4-5", stop_reason="tool_use",
                )
            # Phase 2 (creative model) — write content
            return LLMResponse(
                text="",
                tool_calls=[{"id": "1", "name": "write_content", "input": {"content": "Hello from sim"}}],
                input_tokens=50, output_tokens=30,
                model="claude-sonnet-4-6", stop_reason="tool_use",
            )

        mock_client.tool_use.side_effect = mock_tool_use

        engine = ClaudeEngine(client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}")
        actions = []
        engine.run(
            profiles=profiles,
            config=config,
            platform="twitter",
            on_action=lambda a: actions.append(a),
        )

        assert len(actions) > 0
        assert all(isinstance(a, Action) for a in actions)
        assert all(a.platform == "twitter" for a in actions)
        # At least one CREATE_POST since that's what our mock returns
        assert any(a.action_type == ActionType.CREATE_POST for a in actions)

    def test_run_calls_on_action_per_agent(self):
        profiles = _make_profiles(3)
        config = _make_config()
        config.total_hours = 1
        config.minutes_per_round = 60

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "observing"}}],
            input_tokens=50,
            output_tokens=30,
            model="claude-sonnet-4-6",
            stop_reason="tool_use",
        )

        engine = ClaudeEngine(client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}")
        actions = []
        engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: actions.append(a))

        # Should have at least 1 action (at least 1 agent active in 1 round)
        assert len(actions) >= 1

    def test_run_applies_create_post_to_state(self):
        profiles = _make_profiles(1)
        config = _make_config()
        config.total_hours = 1
        config.minutes_per_round = 60

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"

        def mock_tool_use(**kwargs):
            if kwargs.get("model") == "claude-haiku-4-5":
                return LLMResponse(
                    text="",
                    tool_calls=[{"id": "1", "name": "create_post", "input": {}}],
                    input_tokens=100, output_tokens=50,
                    model="claude-haiku-4-5", stop_reason="tool_use",
                )
            return LLMResponse(
                text="",
                tool_calls=[{"id": "1", "name": "write_content", "input": {"content": "Test post"}}],
                input_tokens=50, output_tokens=30,
                model="claude-sonnet-4-6", stop_reason="tool_use",
            )

        mock_client.tool_use.side_effect = mock_tool_use

        engine = ClaudeEngine(client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}")
        engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: None)

        # Engine should have internal state with the post
        assert len(engine.state.posts) >= 1

    def test_run_returns_token_usage(self):
        profiles = _make_profiles(1)
        config = _make_config()
        config.total_hours = 1
        config.minutes_per_round = 60

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=100,
            output_tokens=50,
            model="claude-haiku-4-5",
            stop_reason="tool_use",
        )

        engine = ClaudeEngine(client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}")
        result = engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: None)

        assert result["decision_tokens"]["input"] > 0
        assert result["decision_tokens"]["output"] > 0
        assert result["total_rounds"] >= 1
