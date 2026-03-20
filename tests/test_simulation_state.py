"""Tests for in-memory simulation state."""

from forkcast.simulation.state import SimulationState, Post, Comment


class TestSimulationState:
    def setup_method(self):
        self.state = SimulationState(
            platform="twitter",
            feed_weights={"recency": 0.5, "popularity": 0.3, "relevance": 0.2},
        )

    def test_initial_state_empty(self):
        assert len(self.state.posts) == 0
        assert len(self.state.comments) == 0
        assert len(self.state.followers) == 0

    def test_add_post(self):
        post_id = self.state.add_post(
            author_id=0, author_name="alice", content="Hello world", timestamp="2026-03-20T10:00:00Z"
        )
        assert post_id == 0
        assert len(self.state.posts) == 1
        assert self.state.posts[0].content == "Hello world"
        assert self.state.posts[0].likes == 0

    def test_add_multiple_posts_increments_id(self):
        id1 = self.state.add_post(0, "alice", "First", "2026-03-20T10:00:00Z")
        id2 = self.state.add_post(1, "bob", "Second", "2026-03-20T10:01:00Z")
        assert id1 == 0
        assert id2 == 1

    def test_like_post(self):
        self.state.add_post(0, "alice", "Like me", "2026-03-20T10:00:00Z")
        self.state.like_post(post_id=0, agent_id=1)
        assert self.state.posts[0].likes == 1

    def test_like_post_idempotent(self):
        self.state.add_post(0, "alice", "Like me", "2026-03-20T10:00:00Z")
        self.state.like_post(0, 1)
        self.state.like_post(0, 1)  # Same agent likes again
        assert self.state.posts[0].likes == 1  # Still 1

    def test_dislike_post(self):
        self.state.add_post(0, "alice", "Dislike me", "2026-03-20T10:00:00Z")
        self.state.dislike_post(post_id=0, agent_id=1)
        assert self.state.posts[0].dislikes == 1

    def test_add_comment(self):
        self.state.add_post(0, "alice", "Post", "2026-03-20T10:00:00Z")
        comment_id = self.state.add_comment(
            post_id=0, author_id=1, author_name="bob", content="Nice!", timestamp="2026-03-20T10:01:00Z"
        )
        assert comment_id == 0
        assert len(self.state.comments) == 1
        assert self.state.comments[0].content == "Nice!"

    def test_follow(self):
        self.state.follow(follower_id=0, followee_id=1)
        assert 1 in self.state.followers[0]

    def test_follow_idempotent(self):
        self.state.follow(0, 1)
        self.state.follow(0, 1)
        assert len(self.state.followers[0]) == 1

    def test_mute(self):
        self.state.mute(agent_id=0, muted_id=1)
        assert 1 in self.state.mutes[0]

    def test_get_feed_returns_recent_posts(self):
        self.state.add_post(0, "alice", "Old post", "2026-03-20T09:00:00Z")
        self.state.add_post(1, "bob", "New post", "2026-03-20T10:00:00Z")
        feed = self.state.get_feed(agent_id=2, limit=10)
        assert len(feed) == 2
        # Most recent first (recency weight is highest)
        assert feed[0].content == "New post"

    def test_get_feed_excludes_muted(self):
        self.state.add_post(0, "alice", "Hello", "2026-03-20T10:00:00Z")
        self.state.add_post(1, "bob", "World", "2026-03-20T10:01:00Z")
        self.state.mute(agent_id=2, muted_id=0)
        feed = self.state.get_feed(agent_id=2, limit=10)
        assert len(feed) == 1
        assert feed[0].author_name == "bob"

    def test_get_feed_prioritizes_followed(self):
        self.state.add_post(0, "alice", "Followed post", "2026-03-20T10:00:00Z")
        self.state.add_post(1, "bob", "Not followed", "2026-03-20T10:00:01Z")
        self.state.follow(follower_id=2, followee_id=0)
        feed = self.state.get_feed(agent_id=2, limit=10)
        # Both appear, but followed should rank higher (relevance boost)
        assert len(feed) == 2
        assert feed[0].author_name == "alice"

    def test_get_feed_respects_limit(self):
        for i in range(20):
            self.state.add_post(0, "alice", f"Post {i}", f"2026-03-20T10:{i:02d}:00Z")
        feed = self.state.get_feed(agent_id=1, limit=5)
        assert len(feed) == 5

    def test_get_post_comments(self):
        self.state.add_post(0, "alice", "Post", "2026-03-20T10:00:00Z")
        self.state.add_comment(0, 1, "bob", "Comment 1", "2026-03-20T10:01:00Z")
        self.state.add_comment(0, 2, "carol", "Comment 2", "2026-03-20T10:02:00Z")
        comments = self.state.get_post_comments(post_id=0)
        assert len(comments) == 2

    def test_invalid_post_id_ignored(self):
        self.state.like_post(post_id=999, agent_id=0)  # No crash
        self.state.dislike_post(post_id=999, agent_id=0)  # No crash


class TestPost:
    def test_post_to_feed_text(self):
        state = SimulationState("twitter", {"recency": 1.0, "popularity": 0.0, "relevance": 0.0})
        state.add_post(0, "alice", "Great insight on AI", "2026-03-20T10:00:00Z")
        state.like_post(0, 1)
        state.add_comment(0, 1, "bob", "Agreed!", "2026-03-20T10:01:00Z")
        text = state.posts[0].to_feed_text(state.get_post_comments(0))
        assert "alice" in text
        assert "Great insight on AI" in text
        assert "1 like" in text
