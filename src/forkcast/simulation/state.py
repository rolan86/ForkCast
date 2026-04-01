"""In-memory social platform state for the Claude simulation engine."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Post:
    """A post in the simulated social platform."""

    id: int
    author_id: int
    author_name: str
    content: str
    timestamp: str
    likes: int = 0
    dislikes: int = 0
    _liked_by: set[int] = field(default_factory=set, repr=False)
    _disliked_by: set[int] = field(default_factory=set, repr=False)

    def to_feed_text(self, comments: list["Comment"] | None = None) -> str:
        """Render this post as text for an agent's feed context."""
        parts = [f"[Post #{self.id}] @{self.author_name}: {self.content}"]
        parts.append(f"  ({self.likes} like{'s' if self.likes != 1 else ''}, {self.dislikes} dislike{'s' if self.dislikes != 1 else ''})")
        if comments:
            for c in comments[:3]:  # Show top 3 comments
                parts.append(f"  └ @{c.author_name}: {c.content}")
            if len(comments) > 3:
                parts.append(f"  └ ... and {len(comments) - 3} more comments")
        return "\n".join(parts)

    def to_summary_text(self) -> str:
        """Render this post as a one-line summary for compressed feeds."""
        truncated = self.content[:80] + "..." if len(self.content) > 80 else self.content
        likes = f"{self.likes} like{'s' if self.likes != 1 else ''}"
        dislikes = f"{self.dislikes} dislike{'s' if self.dislikes != 1 else ''}"
        return f"[Post #{self.id}] @{self.author_name}: {truncated} ({likes}, {dislikes})"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "author_id": self.author_id, "author_name": self.author_name,
            "content": self.content, "timestamp": self.timestamp,
            "likes": self.likes, "dislikes": self.dislikes,
            "liked_by": sorted(self._liked_by), "disliked_by": sorted(self._disliked_by),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Post":
        post = cls(id=d["id"], author_id=d["author_id"], author_name=d["author_name"],
                   content=d["content"], timestamp=d["timestamp"],
                   likes=d.get("likes", 0), dislikes=d.get("dislikes", 0))
        post._liked_by = set(d.get("liked_by", []))
        post._disliked_by = set(d.get("disliked_by", []))
        return post


@dataclass
class Comment:
    """A comment on a post."""

    id: int
    post_id: int
    author_id: int
    author_name: str
    content: str
    timestamp: str

    def to_dict(self) -> dict:
        return {"id": self.id, "post_id": self.post_id, "author_id": self.author_id,
                "author_name": self.author_name, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, d: dict) -> "Comment":
        return cls(**d)


class SimulationState:
    """In-memory state for a simulated social platform.

    Manages posts, comments, follower/mute relationships, and feed generation.
    This state is ephemeral — it exists only during simulation and can be
    reconstructed from the actions.jsonl log if needed.
    """

    def __init__(self, platform: str, feed_weights: dict[str, float]):
        self.platform = platform
        self.feed_weights = feed_weights
        self.posts: list[Post] = []
        self.comments: list[Comment] = []
        self.followers: dict[int, set[int]] = defaultdict(set)
        self.mutes: dict[int, set[int]] = defaultdict(set)
        self._next_post_id = 0
        self._next_comment_id = 0

    def add_post(self, author_id: int, author_name: str, content: str, timestamp: str) -> int:
        """Add a post. Returns the post ID."""
        post_id = self._next_post_id
        self._next_post_id += 1
        self.posts.append(Post(
            id=post_id,
            author_id=author_id,
            author_name=author_name,
            content=content,
            timestamp=timestamp,
        ))
        return post_id

    def like_post(self, post_id: int, agent_id: int) -> None:
        """Like a post. Idempotent — same agent liking twice has no additional effect."""
        if post_id >= len(self.posts) or post_id < 0:
            return
        post = self.posts[post_id]
        if agent_id not in post._liked_by:
            post._liked_by.add(agent_id)
            post.likes += 1

    def dislike_post(self, post_id: int, agent_id: int) -> None:
        """Dislike a post. Idempotent."""
        if post_id >= len(self.posts) or post_id < 0:
            return
        post = self.posts[post_id]
        if agent_id not in post._disliked_by:
            post._disliked_by.add(agent_id)
            post.dislikes += 1

    def add_comment(self, post_id: int, author_id: int, author_name: str, content: str, timestamp: str) -> int:
        """Add a comment to a post. Returns the comment ID."""
        comment_id = self._next_comment_id
        self._next_comment_id += 1
        self.comments.append(Comment(
            id=comment_id,
            post_id=post_id,
            author_id=author_id,
            author_name=author_name,
            content=content,
            timestamp=timestamp,
        ))
        return comment_id

    def follow(self, follower_id: int, followee_id: int) -> None:
        """Add a follow relationship. Idempotent."""
        self.followers[follower_id].add(followee_id)

    def mute(self, agent_id: int, muted_id: int) -> None:
        """Mute an agent. Idempotent."""
        self.mutes[agent_id].add(muted_id)

    def snapshot(self) -> "SimulationState":
        """Return a deep copy of this state for round-level isolation."""
        return SimulationState.from_dict(self.to_dict())

    def get_post_comments(self, post_id: int) -> list[Comment]:
        """Get all comments for a post, ordered by timestamp."""
        return [c for c in self.comments if c.post_id == post_id]

    def get_feed(self, agent_id: int, limit: int = 20) -> list[Post]:
        """Build a ranked feed for an agent.

        Excludes posts from muted agents. Ranks by weighted combination of:
        - recency: newer posts score higher
        - popularity: more likes score higher
        - relevance: posts from followed agents score higher
        """
        muted = self.mutes.get(agent_id, set())
        following = self.followers.get(agent_id, set())

        # Filter out muted
        candidates = [p for p in self.posts if p.author_id not in muted]
        if not candidates:
            return []

        w_recency = self.feed_weights.get("recency", 0.5)
        w_popularity = self.feed_weights.get("popularity", 0.3)
        w_relevance = self.feed_weights.get("relevance", 0.2)

        # Score each post
        max_likes = max((p.likes for p in candidates), default=1) or 1

        # Compute recency using exponential decay relative to the newest post.
        # Half-life of 1 hour means posts within the same minute score nearly
        # identically on recency, allowing follow/relevance to dominate.
        from datetime import datetime
        import math

        HALF_LIFE_SECONDS = 3600.0  # 1 hour

        def _parse_ts(ts: str) -> float:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.timestamp()
            except ValueError:
                return 0.0

        epoch_times = [_parse_ts(p.timestamp) for p in candidates]
        newest_epoch = max(epoch_times)

        def recency_decay(epoch: float) -> float:
            age_seconds = newest_epoch - epoch
            return math.exp(-age_seconds * math.log(2) / HALF_LIFE_SECONDS)

        def score(post: Post, idx: int) -> float:
            recency_score = recency_decay(epoch_times[idx])
            popularity_score = post.likes / max_likes
            relevance_score = 1.0 if post.author_id in following else 0.0
            return (
                w_recency * recency_score
                + w_popularity * popularity_score
                + w_relevance * relevance_score
            )

        scored = [(score(p, i), p) for i, p in enumerate(candidates)]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:limit]]

    def to_dict(self) -> dict:
        return {
            "platform": self.platform, "feed_weights": self.feed_weights,
            "posts": [p.to_dict() for p in self.posts],
            "comments": [c.to_dict() for c in self.comments],
            "followers": {str(k): sorted(v) for k, v in self.followers.items()},
            "mutes": {str(k): sorted(v) for k, v in self.mutes.items()},
            "_next_post_id": self._next_post_id, "_next_comment_id": self._next_comment_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SimulationState":
        state = cls(platform=d["platform"], feed_weights=d["feed_weights"])
        state.posts = [Post.from_dict(p) for p in d.get("posts", [])]
        state.comments = [Comment.from_dict(c) for c in d.get("comments", [])]
        state.followers = defaultdict(set)
        for k, v in d.get("followers", {}).items():
            state.followers[int(k)] = set(v)
        state.mutes = defaultdict(set)
        for k, v in d.get("mutes", {}).items():
            state.mutes[int(k)] = set(v)
        state._next_post_id = d.get("_next_post_id", len(state.posts))
        state._next_comment_id = d.get("_next_comment_id", len(state.comments))
        return state
