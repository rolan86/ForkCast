"""Tests for SimulationState, Post, Comment serialization."""
from forkcast.simulation.state import Comment, Post, SimulationState


class TestPostSerialization:
    def test_roundtrip(self):
        post = Post(id=1, author_id=2, author_name="alice", content="hello", timestamp="2026-01-01T00:00:00Z")
        post._liked_by = {3, 4}
        post._disliked_by = {5}
        post.likes = 2
        post.dislikes = 1
        d = post.to_dict()
        assert d["id"] == 1
        assert set(d["liked_by"]) == {3, 4}
        restored = Post.from_dict(d)
        assert restored._liked_by == {3, 4}
        assert restored.likes == 2


class TestCommentSerialization:
    def test_roundtrip(self):
        comment = Comment(id=0, post_id=1, author_id=2, author_name="bob", content="nice", timestamp="2026-01-01T00:00:00Z")
        d = comment.to_dict()
        restored = Comment.from_dict(d)
        assert restored.id == 0
        assert restored.content == "nice"


class TestSimulationStateSerialization:
    def test_roundtrip_with_posts_and_follows(self):
        state = SimulationState(platform="twitter", feed_weights={"recency": 0.5, "popularity": 0.3, "relevance": 0.2})
        state.add_post(0, "alice", "hello world", "2026-01-01T00:00:00Z")
        state.add_post(1, "bob", "hi there", "2026-01-01T00:01:00Z")
        state.add_comment(0, 1, "bob", "nice!", "2026-01-01T00:02:00Z")
        state.follow(0, 1)
        state.mute(1, 0)
        state.like_post(0, 1)

        d = state.to_dict()
        assert d["platform"] == "twitter"
        assert len(d["posts"]) == 2
        assert "0" in d["followers"]

        restored = SimulationState.from_dict(d)
        assert restored.platform == "twitter"
        assert len(restored.posts) == 2
        assert 1 in restored.followers[0]
        assert 0 in restored.mutes[1]
        assert restored.posts[0].likes == 1
        assert 1 in restored.posts[0]._liked_by

    def test_empty_state_roundtrip(self):
        state = SimulationState(platform="reddit", feed_weights={"recency": 0.5})
        d = state.to_dict()
        restored = SimulationState.from_dict(d)
        assert restored.platform == "reddit"
        assert len(restored.posts) == 0
