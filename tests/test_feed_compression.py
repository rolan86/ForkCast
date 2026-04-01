"""Tests for feed compression in _build_agent_context."""

from forkcast.simulation.claude_engine import _build_agent_context
from forkcast.simulation.models import AgentProfile
from forkcast.simulation.state import SimulationState


def _make_profile():
    return AgentProfile(
        agent_id=0, name="TestAgent", username="test", bio="Test bio",
        persona="A curious observer.", age=30, gender="female",
        profession="Tester", interests=["AI"], entity_type="Person", entity_source="E0",
    )


def _populate_state(state, n_posts):
    for i in range(n_posts):
        state.add_post(
            author_id=i % 5 + 1, author_name=f"user{i % 5}",
            content=f"Post number {i} about topic {i % 3}",
            timestamp=f"2026-04-01T{10 + i // 6:02d}:{(i * 10) % 60:02d}:00Z",
        )
        if i % 3 == 0:
            state.like_post(i, 0)


class TestFeedCompressionInContext:
    def test_no_compression_renders_all_posts_fully(self):
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        _populate_state(state, 8)
        profile = _make_profile()

        context = _build_agent_context(
            profile=profile, state=state, round_num=5,
            hot_topics=[], seed_posts=[],
            agent_system_template="You are {{ agent_name }}.",
            compress_feed=False,
        )
        user_msg = context["messages"][0]["content"]
        # All posts should have full rendering (with like/dislike counts on separate line)
        assert user_msg.count("(") >= 8

    def test_compression_shows_top3_full_rest_summary(self):
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        _populate_state(state, 8)
        profile = _make_profile()

        context = _build_agent_context(
            profile=profile, state=state, round_num=5,
            hot_topics=[], seed_posts=[],
            agent_system_template="You are {{ agent_name }}.",
            compress_feed=True,
        )
        user_msg = context["messages"][0]["content"]
        lines = user_msg.split("\n")
        summary_lines = [l for l in lines if l.strip().startswith("[Post #") and "like" in l and "dislike" in l]
        assert len(summary_lines) >= 4

    def test_compression_with_5_or_fewer_posts_renders_fully(self):
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        _populate_state(state, 4)
        profile = _make_profile()

        context_compressed = _build_agent_context(
            profile=profile, state=state, round_num=3,
            hot_topics=[], seed_posts=[],
            agent_system_template="You are {{ agent_name }}.",
            compress_feed=True,
        )
        context_normal = _build_agent_context(
            profile=profile, state=state, round_num=3,
            hot_topics=[], seed_posts=[],
            agent_system_template="You are {{ agent_name }}.",
            compress_feed=False,
        )
        assert context_compressed["messages"][0]["content"] == context_normal["messages"][0]["content"]
