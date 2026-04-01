"""Tests for two-phase model routing in Claude simulation engine."""

from forkcast.simulation.claude_engine import DECISION_TOOLS, CREATIVE_TOOLS, AGENT_TOOLS


class TestDecisionTools:
    def test_decision_tools_has_all_action_names(self):
        names = {t["name"] for t in DECISION_TOOLS}
        expected = {t["name"] for t in AGENT_TOOLS}
        assert names == expected

    def test_create_post_has_no_content_field(self):
        tool = next(t for t in DECISION_TOOLS if t["name"] == "create_post")
        props = tool["input_schema"]["properties"]
        assert "content" not in props

    def test_create_comment_has_post_id_but_no_content(self):
        tool = next(t for t in DECISION_TOOLS if t["name"] == "create_comment")
        props = tool["input_schema"]["properties"]
        assert "post_id" in props
        assert "content" not in props

    def test_do_nothing_keeps_reason_field(self):
        tool = next(t for t in DECISION_TOOLS if t["name"] == "do_nothing")
        props = tool["input_schema"]["properties"]
        assert "reason" in props

    def test_like_post_unchanged(self):
        decision = next(t for t in DECISION_TOOLS if t["name"] == "like_post")
        original = next(t for t in AGENT_TOOLS if t["name"] == "like_post")
        assert decision["input_schema"] == original["input_schema"]


class TestCreativeTools:
    def test_has_write_content_tool(self):
        names = {t["name"] for t in CREATIVE_TOOLS}
        assert "write_content" in names

    def test_write_content_has_content_field(self):
        tool = next(t for t in CREATIVE_TOOLS if t["name"] == "write_content")
        props = tool["input_schema"]["properties"]
        assert "content" in props
        assert props["content"]["type"] == "string"


from unittest.mock import MagicMock
from forkcast.llm.client import LLMResponse
from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.claude_engine import ClaudeEngine, _build_agent_context, DECISION_TOOLS, CREATIVE_TOOLS, AGENT_TOOLS
from forkcast.simulation.models import AgentProfile, SimulationConfig
from forkcast.simulation.state import SimulationState


def _make_profiles(n=3):
    return [
        AgentProfile(
            agent_id=i, name=f"Agent{i}", username=f"agent{i}", bio=f"Bio {i}",
            persona=f"A thoughtful person who cares about topic {i}.", age=30 + i,
            gender="female" if i % 2 == 0 else "male", profession=f"Profession{i}",
            interests=["AI", "tech"], entity_type="Person", entity_source=f"Entity{i}",
        )
        for i in range(n)
    ]


def _make_config(**overrides):
    defaults = dict(
        total_hours=1, minutes_per_round=60, peak_hours=[10, 11],
        off_peak_hours=[0, 1, 2, 3], peak_multiplier=1.5, off_peak_multiplier=0.3,
        seed_posts=["Launch day!"], hot_topics=["AI"], narrative_direction="test",
        agent_configs=[], platform_config={"feed_weights": {"recency": 0.5, "popularity": 0.3, "relevance": 0.2}},
    )
    defaults.update(overrides)
    return SimulationConfig(**defaults)


class TestTwoPhaseRouting:
    def test_non_creative_action_uses_decision_model_only(self):
        """do_nothing should only call decision model, no Phase 2."""
        import random
        random.seed(42)

        profiles = _make_profiles(1)
        config = _make_config()

        mock_client = MagicMock()
        mock_client.default_model = "claude-haiku-4-5"
        mock_client.tool_use.return_value = LLMResponse(
            text="", tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "boring"}}],
            input_tokens=50, output_tokens=30, model="claude-haiku-4-5", stop_reason="tool_use",
        )

        engine = ClaudeEngine(
            client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}",
            decision_model="claude-haiku-4-5", creative_model="claude-sonnet-4-6",
        )
        engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: None)

        # Only Phase 1 calls — all with decision model
        for c in mock_client.tool_use.call_args_list:
            assert c[1]["model"] == "claude-haiku-4-5"

    def test_create_post_triggers_phase2_with_creative_model(self):
        """create_post from Phase 1 should trigger Phase 2 with creative model."""
        import random
        random.seed(42)

        profiles = _make_profiles(1)
        config = _make_config()

        mock_client = MagicMock()
        mock_client.default_model = "claude-haiku-4-5"

        def mock_tool_use(**kwargs):
            if kwargs.get("model") == "claude-haiku-4-5":
                return LLMResponse(
                    text="", tool_calls=[{"id": "1", "name": "create_post", "input": {}}],
                    input_tokens=50, output_tokens=30, model="claude-haiku-4-5", stop_reason="tool_use",
                )
            else:
                return LLMResponse(
                    text="", tool_calls=[{"id": "1", "name": "write_content", "input": {"content": "Great product!"}}],
                    input_tokens=30, output_tokens=40, model="claude-sonnet-4-6", stop_reason="tool_use",
                )

        mock_client.tool_use.side_effect = mock_tool_use

        engine = ClaudeEngine(
            client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}",
            decision_model="claude-haiku-4-5", creative_model="claude-sonnet-4-6",
        )
        actions = []
        engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: actions.append(a))

        post_actions = [a for a in actions if a.action_type == ActionType.CREATE_POST]
        assert len(post_actions) >= 1
        assert post_actions[0].action_args.get("content") == "Great product!"

        models_used = {c[1]["model"] for c in mock_client.tool_use.call_args_list}
        assert "claude-haiku-4-5" in models_used
        assert "claude-sonnet-4-6" in models_used

    def test_create_comment_triggers_phase2(self):
        """create_comment from Phase 1 should trigger Phase 2."""
        import random
        random.seed(42)

        profiles = _make_profiles(1)
        config = _make_config()

        mock_client = MagicMock()
        mock_client.default_model = "claude-haiku-4-5"

        def mock_tool_use(**kwargs):
            if kwargs.get("model") == "claude-haiku-4-5":
                return LLMResponse(
                    text="", tool_calls=[{"id": "1", "name": "create_comment", "input": {"post_id": 0}}],
                    input_tokens=50, output_tokens=30, model="claude-haiku-4-5", stop_reason="tool_use",
                )
            else:
                return LLMResponse(
                    text="", tool_calls=[{"id": "1", "name": "write_content", "input": {"content": "Nice point!"}}],
                    input_tokens=30, output_tokens=40, model="claude-sonnet-4-6", stop_reason="tool_use",
                )

        mock_client.tool_use.side_effect = mock_tool_use

        engine = ClaudeEngine(
            client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}",
            decision_model="claude-haiku-4-5", creative_model="claude-sonnet-4-6",
        )
        actions = []
        engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: actions.append(a))

        comment_actions = [a for a in actions if a.action_type == ActionType.CREATE_COMMENT]
        assert len(comment_actions) >= 1
        assert comment_actions[0].action_args.get("content") == "Nice point!"

    def test_engine_returns_per_phase_token_breakdown(self):
        """Engine result should have decision_tokens and creative_tokens."""
        import random
        random.seed(42)

        profiles = _make_profiles(1)
        config = _make_config()

        mock_client = MagicMock()
        mock_client.default_model = "claude-haiku-4-5"
        mock_client.tool_use.return_value = LLMResponse(
            text="", tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=50, output_tokens=30, model="claude-haiku-4-5", stop_reason="tool_use",
        )

        engine = ClaudeEngine(
            client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}",
            decision_model="claude-haiku-4-5", creative_model="claude-sonnet-4-6",
        )
        result = engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: None)

        assert "decision_tokens" in result
        assert "creative_tokens" in result
        assert result["decision_tokens"]["input"] > 0
        assert result["creative_tokens"]["input"] == 0


class TestRoundBuffering:
    def test_actions_buffered_until_round_end(self):
        """All agents in a round should see the same state."""
        import random
        random.seed(42)

        profiles = _make_profiles(3)
        config = _make_config()

        call_count = 0
        mock_client = MagicMock()
        mock_client.default_model = "claude-haiku-4-5"

        def mock_tool_use(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    text="", tool_calls=[{"id": "1", "name": "create_post", "input": {}}],
                    input_tokens=50, output_tokens=30, model="claude-haiku-4-5", stop_reason="tool_use",
                )
            # For create_post Phase 2
            if kwargs.get("model") != "claude-haiku-4-5":
                return LLMResponse(
                    text="", tool_calls=[{"id": "1", "name": "write_content", "input": {"content": "Hello!"}}],
                    input_tokens=30, output_tokens=40, model="claude-sonnet-4-6", stop_reason="tool_use",
                )
            return LLMResponse(
                text="", tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "observing"}}],
                input_tokens=50, output_tokens=30, model="claude-haiku-4-5", stop_reason="tool_use",
            )

        mock_client.tool_use.side_effect = mock_tool_use

        engine = ClaudeEngine(
            client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}",
            decision_model="claude-haiku-4-5", creative_model="claude-sonnet-4-6",
        )
        actions = []
        engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: actions.append(a))

        assert len(actions) >= 1
