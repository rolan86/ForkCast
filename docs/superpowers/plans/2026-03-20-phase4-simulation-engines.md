# Phase 4: Simulation Engines — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two simulation engines (Claude in-process engine and OASIS subprocess engine) that run multi-agent social media simulations, producing a common JSONL action log, with SSE streaming, API endpoints, and CLI commands.

**Architecture:** Both engines implement a common `SimulationEngine` protocol — `run(simulation_id, profiles, config, on_action)` that yields `Action` objects. The Claude engine maintains in-memory social platform state (posts, comments, social graph, feeds) and calls `client.complete()` with tool_use per agent per round. The OASIS engine launches a subprocess and monitors `actions.jsonl` via a background thread. A `run_simulation()` orchestrator loads config, selects the engine, runs it, persists actions to SQLite + JSONL, and emits SSE events. The API uses the same non-blocking POST + SSE stream pattern established in Phase 3.

**Tech Stack:** Python 3.11, FastAPI, SQLite, Anthropic SDK (tool_use for agent decisions), Typer CLI, sse-starlette, subprocess (OASIS)

**Spec Reference:** `docs/specs/2026-03-20-forkcast-design.md` — Sections 7, 8, 10, 11

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/forkcast/simulation/action.py` | `Action` dataclass — common output format for both engines |
| **Create:** `src/forkcast/simulation/state.py` | `SimulationState` — in-memory social platform (posts, comments, social graph, feeds, feed ranking) |
| **Create:** `src/forkcast/simulation/claude_engine.py` | Claude engine — runs agents in-process via tool_use, manages state per round |
| **Create:** `src/forkcast/simulation/oasis_engine.py` | OASIS engine — subprocess launcher with file-based IPC, action monitoring |
| **Create:** `src/forkcast/simulation/runner.py` | `run_simulation()` orchestrator — loads config, selects engine, writes JSONL + SQLite, emits progress |
| **Modify:** `src/forkcast/simulation/models.py:39-68` | Add `RunResult` dataclass |
| **Modify:** `src/forkcast/api/simulation_routes.py:1-204` | Add `POST /{id}/start`, `POST /{id}/stop`, `GET /{id}/run/stream` endpoints |
| **Modify:** `src/forkcast/cli/sim_cmd.py:1-157` | Add `sim start` and `sim stop` commands |
| **Create:** `domains/_default/prompts/agent_system.md` | System prompt template for Claude engine agents |
| **Create:** `tests/test_action.py` | Tests for Action dataclass |
| **Create:** `tests/test_simulation_state.py` | Tests for SimulationState |
| **Create:** `tests/test_claude_engine.py` | Tests for Claude engine |
| **Create:** `tests/test_oasis_engine.py` | Tests for OASIS engine |
| **Create:** `tests/test_simulation_runner.py` | Tests for run_simulation orchestrator |
| **Create:** `tests/test_api_simulation_run.py` | Tests for start/stop/stream API endpoints |
| **Create:** `tests/test_cli_sim_run.py` | Tests for CLI start/stop commands |

---

## Task 1: Action Dataclass — Common Output Format

**Files:**
- Create: `src/forkcast/simulation/action.py`
- Create: `tests/test_action.py`

Both engines produce the same action format. This dataclass is the shared contract.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_action.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_action.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.simulation.action'`

- [ ] **Step 3: Implement Action and ActionType**

```python
# src/forkcast/simulation/action.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_action.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/simulation/action.py tests/test_action.py
git commit -m "feat: add Action dataclass — common output format for simulation engines"
```

---

## Task 2: SimulationState — In-Memory Social Platform

**Files:**
- Create: `src/forkcast/simulation/state.py`
- Create: `tests/test_simulation_state.py`

The Claude engine needs an in-memory representation of the simulated social platform. This manages posts, comments, social graph, and feed ranking. The OASIS engine does not use this — it manages its own state internally.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_simulation_state.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.simulation.state'`

- [ ] **Step 3: Implement SimulationState**

```python
# src/forkcast/simulation/state.py
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


@dataclass
class Comment:
    """A comment on a post."""

    id: int
    post_id: int
    author_id: int
    author_name: str
    content: str
    timestamp: str


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
        self.followers: dict[int, set[int]] = defaultdict(set)  # agent_id -> set of followee_ids
        self.mutes: dict[int, set[int]] = defaultdict(set)  # agent_id -> set of muted_ids
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

        def score(post: Post, idx: int) -> float:
            recency_score = idx / max(len(candidates), 1)  # Higher index = more recent
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_state.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/simulation/state.py tests/test_simulation_state.py
git commit -m "feat: SimulationState — in-memory social platform for Claude engine"
```

---

## Task 3: Claude Engine — In-Process Simulation via Tool Use

**Files:**
- Create: `src/forkcast/simulation/claude_engine.py`
- Create: `domains/_default/prompts/agent_system.md`
- Create: `tests/test_claude_engine.py`

The Claude engine is the core of ForkCast. For each round, for each active agent, it sends the agent's persona + feed context to Claude, receives a tool_use action, and applies it to the in-memory state. Agent activity varies by peak/off-peak hours per the simulation config.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_claude_engine.py
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
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Hello from sim"}}],
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-6",
            stop_reason="tool_use",
        )

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
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Test post"}}],
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-6",
            stop_reason="tool_use",
        )

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
            model="claude-sonnet-4-6",
            stop_reason="tool_use",
        )

        engine = ClaudeEngine(client=mock_client, agent_system_template="You are {{ agent_name }}. {{ persona }}")
        result = engine.run(profiles=profiles, config=config, platform="twitter", on_action=lambda a: None)

        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0
        assert result["total_rounds"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_claude_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.simulation.claude_engine'`

- [ ] **Step 3: Create agent system prompt template**

```markdown
# domains/_default/prompts/agent_system.md
You are {{ agent_name }} (@{{ username }}) participating in a social media simulation on {{ platform }}.

## Your Persona
{{ persona }}

## Your Profile
- Age: {{ age }}
- Profession: {{ profession }}
- Interests: {{ interests }}

## Instructions
You are browsing your {{ platform }} feed. Based on what you see, decide what to do. You can:
- **create_post**: Write a new post sharing your perspective
- **like_post**: Like a post you agree with or find interesting
- **dislike_post**: Dislike a post you disagree with
- **create_comment**: Reply to a specific post
- **follow_user**: Follow someone whose content interests you
- **mute_user**: Mute someone whose content you find irrelevant or annoying
- **do_nothing**: Skip this round if nothing catches your attention

Act naturally. Stay in character. Your posts should reflect your persona's knowledge, opinions, and communication style. Do not break character or mention that you are in a simulation.
```

- [ ] **Step 4: Implement ClaudeEngine**

```python
# src/forkcast/simulation/claude_engine.py
"""Claude simulation engine — runs agents in-process via tool_use."""

import logging
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from jinja2 import Template

from forkcast.llm.client import ClaudeClient
from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import AgentProfile, SimulationConfig
from forkcast.simulation.state import SimulationState

logger = logging.getLogger(__name__)

AGENT_TOOLS = [
    {
        "name": "create_post",
        "description": "Write a new post on the platform",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The post content (max 280 chars for twitter)"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "like_post",
        "description": "Like a post in your feed",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The ID of the post to like"},
            },
            "required": ["post_id"],
        },
    },
    {
        "name": "dislike_post",
        "description": "Dislike a post in your feed",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The ID of the post to dislike"},
            },
            "required": ["post_id"],
        },
    },
    {
        "name": "create_comment",
        "description": "Reply to a specific post",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The ID of the post to comment on"},
                "content": {"type": "string", "description": "Your comment"},
            },
            "required": ["post_id", "content"],
        },
    },
    {
        "name": "follow_user",
        "description": "Follow another user",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The agent ID of the user to follow"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "mute_user",
        "description": "Mute another user so their posts don't appear in your feed",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The agent ID of the user to mute"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "do_nothing",
        "description": "Skip this round without taking action",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Brief reason for skipping"},
            },
            "required": ["reason"],
        },
    },
]

# Map tool names to ActionType values
_TOOL_TO_ACTION = {
    "create_post": ActionType.CREATE_POST,
    "like_post": ActionType.LIKE_POST,
    "dislike_post": ActionType.DISLIKE_POST,
    "create_comment": ActionType.CREATE_COMMENT,
    "follow_user": ActionType.FOLLOW,
    "mute_user": ActionType.MUTE,
    "do_nothing": ActionType.DO_NOTHING,
}


def _parse_tool_action(tool_calls: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Parse Claude's tool_use response into (action_type, action_args)."""
    if not tool_calls:
        return ActionType.DO_NOTHING, {}
    call = tool_calls[0]  # Take first tool call
    action_type = _TOOL_TO_ACTION.get(call["name"], ActionType.DO_NOTHING)
    return action_type, call.get("input", {})


def _determine_active_agents(
    profiles: list[AgentProfile],
    config: SimulationConfig,
    current_hour: int,
) -> list[AgentProfile]:
    """Determine which agents are active this round based on time of day."""
    if current_hour in config.peak_hours:
        multiplier = config.peak_multiplier
    elif current_hour in config.off_peak_hours:
        multiplier = config.off_peak_multiplier
    else:
        multiplier = 1.0

    # Base probability: each agent has ~60% chance of being active in a normal round
    base_prob = 0.6
    prob = min(1.0, base_prob * multiplier)

    active = [p for p in profiles if random.random() < prob]
    # Always at least one agent
    if not active:
        active = [random.choice(profiles)]
    return active


def _build_agent_context(
    profile: AgentProfile,
    state: SimulationState,
    round_num: int,
    hot_topics: list[str],
    seed_posts: list[str],
    agent_system_template: str,
) -> dict[str, Any]:
    """Build the system prompt and messages for one agent's turn."""
    template = Template(agent_system_template)
    system = template.render(
        agent_name=profile.name,
        username=profile.username,
        platform=state.platform,
        persona=profile.persona,
        age=profile.age,
        profession=profile.profession,
        interests=", ".join(profile.interests),
    )

    # Build user message with feed context
    parts = [f"Round {round_num}. Here is your current feed:\n"]

    feed = state.get_feed(agent_id=profile.agent_id, limit=10)
    if feed:
        for post in feed:
            comments = state.get_post_comments(post.id)
            parts.append(post.to_feed_text(comments))
            parts.append("")
    else:
        parts.append("Your feed is empty — no posts yet.\n")

    if hot_topics:
        parts.append(f"Trending topics: {', '.join(hot_topics)}\n")

    if round_num == 1 and seed_posts:
        parts.append("Discussion starters:")
        for sp in seed_posts:
            parts.append(f"  - {sp}")
        parts.append("")

    parts.append("What would you like to do? Use one of the available tools.")

    user_content = "\n".join(parts)
    return {
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }


class ClaudeEngine:
    """Run a simulation using Claude as the agent brain.

    For each round, active agents receive their feed and persona context,
    Claude decides an action via tool_use, and the action is applied to
    the in-memory simulation state.
    """

    def __init__(self, client: ClaudeClient, agent_system_template: str):
        self.client = client
        self.agent_system_template = agent_system_template
        self.state: SimulationState | None = None
        self._stopped = False

    def stop(self):
        """Signal the engine to stop after the current round."""
        self._stopped = True

    def run(
        self,
        profiles: list[AgentProfile],
        config: SimulationConfig,
        platform: str,
        on_action: Callable[[Action], None],
        on_round: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Run the full simulation. Returns token usage stats."""
        feed_weights = config.platform_config.get(
            "feed_weights", {"recency": 0.5, "popularity": 0.3, "relevance": 0.2}
        )
        self.state = SimulationState(platform=platform, feed_weights=feed_weights)
        self._stopped = False

        total_rounds = math.ceil((config.total_hours * 60) / config.minutes_per_round)
        total_input = 0
        total_output = 0
        start_time = datetime.now(timezone.utc)
        round_num = 0

        for round_num in range(1, total_rounds + 1):
            if self._stopped:
                break

            sim_time = start_time + timedelta(minutes=(round_num - 1) * config.minutes_per_round)
            current_hour = sim_time.hour
            timestamp = sim_time.isoformat()

            if on_round:
                on_round(round_num, total_rounds)

            active = _determine_active_agents(profiles, config, current_hour)

            for profile in active:
                if self._stopped:
                    break

                context = _build_agent_context(
                    profile=profile,
                    state=self.state,
                    round_num=round_num,
                    hot_topics=config.hot_topics,
                    seed_posts=config.seed_posts if round_num == 1 else [],
                    agent_system_template=self.agent_system_template,
                )

                try:
                    response = self.client.tool_use(
                        messages=context["messages"],
                        tools=AGENT_TOOLS,
                        system=context["system"],
                        max_tokens=1024,
                        temperature=1.0,
                    )
                    total_input += response.input_tokens
                    total_output += response.output_tokens

                    action_type, action_args = _parse_tool_action(response.tool_calls)
                except Exception as e:
                    logger.warning(f"Agent {profile.name} failed: {e}")
                    action_type = ActionType.DO_NOTHING
                    action_args = {"error": str(e)}

                # Apply action to state
                self._apply_action(profile, action_type, action_args, timestamp)

                action = Action(
                    round=round_num,
                    timestamp=timestamp,
                    agent_id=profile.agent_id,
                    agent_name=profile.username,
                    platform=platform,
                    action_type=action_type,
                    action_args=action_args,
                    success=True,
                )
                on_action(action)

        return {
            "total_rounds": round_num if not self._stopped else round_num - 1,
            "total_actions": len(self.state.posts) + len(self.state.comments),
            "input_tokens": total_input,
            "output_tokens": total_output,
        }

    def _apply_action(
        self,
        profile: AgentProfile,
        action_type: str,
        action_args: dict[str, Any],
        timestamp: str,
    ) -> None:
        """Apply an action to the in-memory simulation state."""
        if action_type == ActionType.CREATE_POST:
            self.state.add_post(
                author_id=profile.agent_id,
                author_name=profile.username,
                content=action_args.get("content", ""),
                timestamp=timestamp,
            )
        elif action_type == ActionType.LIKE_POST:
            self.state.like_post(
                post_id=action_args.get("post_id", -1),
                agent_id=profile.agent_id,
            )
        elif action_type == ActionType.DISLIKE_POST:
            self.state.dislike_post(
                post_id=action_args.get("post_id", -1),
                agent_id=profile.agent_id,
            )
        elif action_type == ActionType.CREATE_COMMENT:
            self.state.add_comment(
                post_id=action_args.get("post_id", -1),
                author_id=profile.agent_id,
                author_name=profile.username,
                content=action_args.get("content", ""),
                timestamp=timestamp,
            )
        elif action_type == ActionType.FOLLOW:
            self.state.follow(
                follower_id=profile.agent_id,
                followee_id=action_args.get("user_id", -1),
            )
        elif action_type == ActionType.MUTE:
            self.state.mute(
                agent_id=profile.agent_id,
                muted_id=action_args.get("user_id", -1),
            )
        # DO_NOTHING: no state change
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_claude_engine.py -v`
Expected: 16 passed

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/simulation/claude_engine.py domains/_default/prompts/agent_system.md tests/test_claude_engine.py
git commit -m "feat: Claude simulation engine — in-process multi-agent via tool_use"
```

---

## Task 4: OASIS Engine — Subprocess Runner with File-Based IPC

**Files:**
- Create: `src/forkcast/simulation/oasis_engine.py`
- Create: `tests/test_oasis_engine.py`

The OASIS engine runs as a subprocess. It writes actions to an `actions.jsonl` file which we monitor via a background thread. We convert OASIS output to our common `Action` format. The engine manages process group isolation for clean termination.

**Important:** This task creates the adapter/runner infrastructure. Actual OASIS subprocess execution depends on having camel-oasis installed, which is an optional dependency. Tests use subprocess mocks.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_oasis_engine.py
"""Tests for OASIS subprocess simulation engine."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import AgentProfile, SimulationConfig
from forkcast.simulation.oasis_engine import (
    OasisEngine,
    _convert_profiles_to_csv,
    _convert_profiles_to_reddit_json,
    _monitor_actions_file,
    _parse_oasis_action,
)


def _make_profiles(n=3):
    return [
        AgentProfile(
            agent_id=i,
            name=f"Agent{i}",
            username=f"agent{i}",
            bio=f"Bio {i}",
            persona=f"Persona {i}",
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
        seed_posts=[],
        hot_topics=[],
        narrative_direction="",
        agent_configs=[],
        platform_config={},
    )


class TestConvertProfilesToCSV:
    def test_csv_has_header(self):
        profiles = _make_profiles(2)
        csv_text = _convert_profiles_to_csv(profiles)
        lines = csv_text.strip().split("\n")
        assert lines[0].startswith("agent_id")
        assert len(lines) == 3  # header + 2 profiles

    def test_csv_contains_profile_data(self):
        profiles = _make_profiles(1)
        csv_text = _convert_profiles_to_csv(profiles)
        assert "Agent0" in csv_text
        assert "agent0" in csv_text


class TestConvertProfilesToRedditJSON:
    def test_json_is_list(self):
        profiles = _make_profiles(2)
        data = _convert_profiles_to_reddit_json(profiles)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_json_has_required_fields(self):
        profiles = _make_profiles(1)
        data = _convert_profiles_to_reddit_json(profiles)
        assert "agent_id" in data[0]
        assert "username" in data[0]
        assert "persona" in data[0]


class TestParseOasisAction:
    def test_parse_tweet(self):
        raw = {"action": "tweet", "content": "Hello", "agent_id": 0, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}
        action = _parse_oasis_action(raw, platform="twitter")
        assert action.action_type == ActionType.CREATE_POST
        assert action.action_args["content"] == "Hello"
        assert action.platform == "twitter"

    def test_parse_like(self):
        raw = {"action": "like", "post_id": 5, "agent_id": 1, "round": 2, "timestamp": "2026-03-20T10:01:00Z"}
        action = _parse_oasis_action(raw, platform="twitter")
        assert action.action_type == ActionType.LIKE_POST

    def test_parse_reply(self):
        raw = {"action": "reply", "post_id": 3, "content": "Great!", "agent_id": 2, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}
        action = _parse_oasis_action(raw, platform="reddit")
        assert action.action_type == ActionType.CREATE_COMMENT
        assert action.platform == "reddit"

    def test_parse_unknown_action(self):
        raw = {"action": "unknown_thing", "agent_id": 0, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}
        action = _parse_oasis_action(raw, platform="twitter")
        assert action.action_type == ActionType.DO_NOTHING


class TestMonitorActionsFile:
    def test_monitor_reads_new_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)

        try:
            actions_received = []
            stop_event = threading.Event()

            def on_action(action):
                actions_received.append(action)
                if len(actions_received) >= 2:
                    stop_event.set()

            # Start monitor in background
            t = threading.Thread(
                target=_monitor_actions_file,
                args=(path, "twitter", on_action, stop_event),
            )
            t.start()

            # Write actions after a brief delay
            time.sleep(0.1)
            with open(path, "a") as f:
                f.write(json.dumps({"action": "tweet", "content": "Hello", "agent_id": 0, "round": 1, "timestamp": "2026-03-20T10:00:00Z"}) + "\n")
                f.write(json.dumps({"action": "like", "post_id": 0, "agent_id": 1, "round": 1, "timestamp": "2026-03-20T10:00:01Z"}) + "\n")
                f.flush()

            t.join(timeout=5)
            assert len(actions_received) >= 2
            assert actions_received[0].action_type == ActionType.CREATE_POST
        finally:
            path.unlink(missing_ok=True)


class TestOasisEngine:
    @patch("forkcast.simulation.oasis_engine.subprocess")
    def test_run_writes_profile_files(self, mock_subprocess):
        profiles = _make_profiles(2)
        config = _make_config()

        # Mock subprocess to exit quickly
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.wait.return_value = 0
        mock_proc.pid = 12345
        mock_subprocess.Popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir)
            engine = OasisEngine(sim_dir=sim_dir)
            engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                on_action=lambda a: None,
            )

            # Should have written twitter CSV profile file
            csv_path = sim_dir / "twitter_profiles.csv"
            assert csv_path.exists()

    @patch("forkcast.simulation.oasis_engine.subprocess")
    def test_stop_terminates_process(self, mock_subprocess):
        profiles = _make_profiles(2)
        config = _make_config()

        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, None, 0]  # Running, running, done
        mock_proc.wait.return_value = 0
        mock_proc.pid = 12345
        mock_subprocess.Popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            engine = OasisEngine(sim_dir=Path(tmpdir))
            # Stop immediately
            engine.stop()
            engine.run(
                profiles=profiles,
                config=config,
                platform="twitter",
                on_action=lambda a: None,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forkcast.simulation.oasis_engine'`

- [ ] **Step 3: Implement OasisEngine**

```python
# src/forkcast/simulation/oasis_engine.py
"""OASIS simulation engine — subprocess runner with file-based IPC."""

import csv
import io
import json
import logging
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import AgentProfile, SimulationConfig

logger = logging.getLogger(__name__)

# Map OASIS action names to our ActionType
_OASIS_ACTION_MAP = {
    "tweet": ActionType.CREATE_POST,
    "post": ActionType.CREATE_POST,
    "like": ActionType.LIKE_POST,
    "dislike": ActionType.DISLIKE_POST,
    "reply": ActionType.CREATE_COMMENT,
    "comment": ActionType.CREATE_COMMENT,
    "follow": ActionType.FOLLOW,
    "mute": ActionType.MUTE,
    "retweet": ActionType.CREATE_POST,  # Treat retweet as a post
}


def _convert_profiles_to_csv(profiles: list[AgentProfile]) -> str:
    """Convert profiles to CSV format for OASIS Twitter simulation."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["agent_id", "name", "username", "bio", "persona", "age", "gender", "profession", "interests"])
    for p in profiles:
        writer.writerow([
            p.agent_id, p.name, p.username, p.bio, p.persona,
            p.age, p.gender, p.profession, ";".join(p.interests),
        ])
    return output.getvalue()


def _convert_profiles_to_reddit_json(profiles: list[AgentProfile]) -> list[dict[str, Any]]:
    """Convert profiles to JSON format for OASIS Reddit simulation."""
    return [
        {
            "agent_id": p.agent_id,
            "username": p.username,
            "name": p.name,
            "bio": p.bio,
            "persona": p.persona,
            "age": p.age,
            "gender": p.gender,
            "profession": p.profession,
            "interests": p.interests,
        }
        for p in profiles
    ]


def _parse_oasis_action(raw: dict[str, Any], platform: str) -> Action:
    """Parse a raw OASIS action dict into our common Action format."""
    oasis_action = raw.get("action", "unknown")
    action_type = _OASIS_ACTION_MAP.get(oasis_action, ActionType.DO_NOTHING)

    action_args = {}
    if "content" in raw:
        action_args["content"] = raw["content"]
    if "post_id" in raw:
        action_args["post_id"] = raw["post_id"]
    if "user_id" in raw:
        action_args["user_id"] = raw["user_id"]

    return Action(
        round=raw.get("round", 0),
        timestamp=raw.get("timestamp", ""),
        agent_id=raw.get("agent_id", 0),
        agent_name=raw.get("agent_name", f"agent{raw.get('agent_id', 0)}"),
        platform=platform,
        action_type=action_type,
        action_args=action_args,
        success=raw.get("success", True),
    )


def _monitor_actions_file(
    actions_path: Path,
    platform: str,
    on_action: Callable[[Action], None],
    stop_event: threading.Event,
    poll_interval: float = 0.2,
) -> None:
    """Monitor an actions.jsonl file for new lines, parsing each as an Action.

    Runs until stop_event is set. Used as a background thread.
    """
    # Wait for file to appear
    while not actions_path.exists() and not stop_event.is_set():
        time.sleep(poll_interval)

    if stop_event.is_set():
        return

    with open(actions_path) as f:
        while not stop_event.is_set():
            line = f.readline()
            if line.strip():
                try:
                    raw = json.loads(line)
                    action = _parse_oasis_action(raw, platform)
                    on_action(action)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse OASIS action: {e}")
            else:
                time.sleep(poll_interval)


class OasisEngine:
    """Run a simulation using OASIS as a subprocess.

    OASIS manages its own agent state internally. We write profile files,
    launch the subprocess, and monitor its actions.jsonl output file.
    """

    def __init__(self, sim_dir: Path):
        self.sim_dir = sim_dir
        self._process: subprocess.Popen | None = None
        self._stopped = False

    def stop(self):
        """Signal the engine to stop."""
        self._stopped = True
        if self._process and self._process.poll() is None:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass

    def run(
        self,
        profiles: list[AgentProfile],
        config: SimulationConfig,
        platform: str,
        on_action: Callable[[Action], None],
        on_round: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Run OASIS simulation as a subprocess."""
        self.sim_dir.mkdir(parents=True, exist_ok=True)
        self._stopped = False

        # Write profile files
        if platform == "twitter":
            csv_path = self.sim_dir / "twitter_profiles.csv"
            csv_path.write_text(_convert_profiles_to_csv(profiles), encoding="utf-8")
        else:
            json_path = self.sim_dir / "reddit_profiles.json"
            json_path.write_text(
                json.dumps(_convert_profiles_to_reddit_json(profiles), indent=2),
                encoding="utf-8",
            )

        # Write config
        config_path = self.sim_dir / "oasis_config.json"
        config_path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")

        if self._stopped:
            return {"total_rounds": 0, "total_actions": 0}

        actions_path = self.sim_dir / "actions.jsonl"
        stop_event = threading.Event()
        action_count = [0]

        def _tracked_on_action(action: Action) -> None:
            action_count[0] += 1
            on_action(action)

        # Start action monitor thread
        monitor_thread = threading.Thread(
            target=_monitor_actions_file,
            args=(actions_path, platform, _tracked_on_action, stop_event),
            daemon=True,
        )
        monitor_thread.start()

        # Launch OASIS subprocess
        cmd = [
            "python", "-m", "oasis.run",
            "--platform", platform,
            "--profiles", str(self.sim_dir / (f"{platform}_profiles.csv" if platform == "twitter" else f"{platform}_profiles.json")),
            "--config", str(config_path),
            "--output", str(actions_path),
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,  # Process group for clean kill
            )
            self._process.wait()
        except FileNotFoundError:
            logger.error("OASIS (camel-oasis) not installed. Install with: pip install camel-oasis")
        except Exception as e:
            logger.error(f"OASIS subprocess failed: {e}")
        finally:
            stop_event.set()
            monitor_thread.join(timeout=5)
            self._process = None

        return {
            "total_rounds": 0,  # OASIS reports its own round count
            "total_actions": action_count[0],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_oasis_engine.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/simulation/oasis_engine.py tests/test_oasis_engine.py
git commit -m "feat: OASIS simulation engine — subprocess runner with file-based IPC"
```

---

## Task 5: Simulation Runner Orchestrator

**Files:**
- Create: `src/forkcast/simulation/runner.py`
- Modify: `src/forkcast/simulation/models.py` — add `RunResult`
- Create: `tests/test_simulation_runner.py`

The runner orchestrates the full simulation lifecycle: load config/profiles from DB and disk, select the engine (claude or oasis), run it, write actions to JSONL + SQLite, log token usage, update simulation status.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_simulation_runner.py
"""Tests for simulation runner orchestrator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import (
    AgentProfile,
    RunResult,
    SimulationConfig,
)
from forkcast.simulation.runner import run_simulation


def _setup_db(db_path, data_dir, domains_dir):
    """Set up a test database with project, graph, and prepared simulation."""
    init_db(db_path)

    project_id = "proj_test"
    graph_id = "graph_test"
    sim_id = "sim_test"

    profiles = [
        AgentProfile(
            agent_id=0, name="Alice", username="alice", bio="AI researcher",
            persona="A thoughtful researcher focused on AI safety.",
            age=32, gender="female", profession="Researcher",
            interests=["AI", "ethics"], entity_type="Person", entity_source="Alice Smith",
        ),
        AgentProfile(
            agent_id=1, name="Bob", username="bob", bio="Tech CEO",
            persona="A bold tech leader pushing for rapid AI adoption.",
            age=45, gender="male", profession="CEO",
            interests=["startups", "AI"], entity_type="Person", entity_source="Bob Jones",
        ),
    ]

    config = SimulationConfig(
        total_hours=1, minutes_per_round=60,
        peak_hours=[10], off_peak_hours=[0, 1, 2],
        peak_multiplier=1.5, off_peak_multiplier=0.3,
        seed_posts=["What does AI mean?"], hot_topics=["AI safety"],
        narrative_direction="Explore", agent_configs=[], platform_config={},
    )

    # Write profiles
    sim_dir = data_dir / sim_id / "profiles"
    sim_dir.mkdir(parents=True)
    (sim_dir / "agents.json").write_text(
        json.dumps([p.to_dict() for p in profiles]), encoding="utf-8"
    )

    # Set up domain prompts
    default_domain = domains_dir / "_default"
    default_domain.mkdir(parents=True, exist_ok=True)
    (default_domain / "manifest.yaml").write_text(
        "name: _default\nversion: '1.0'\ndescription: Default\nlanguage: en\n"
        "sim_engine: claude\nplatforms: [twitter, reddit]\n"
    )
    prompts_dir = default_domain / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "agent_system.md").write_text(
        "You are {{ agent_name }}. {{ persona }}"
    )
    for name in ["ontology.md", "persona.md", "report_guidelines.md", "config_gen.md"]:
        (prompts_dir / name).write_text(f"# {name}\nPlaceholder.\n")

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'Predict AI trends', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, created_at) "
            "VALUES (?, ?, 'complete', datetime('now'))",
            (graph_id, project_id),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, config_json, created_at) "
            "VALUES (?, ?, ?, 'prepared', 'claude', '[\"twitter\"]', ?, datetime('now'))",
            (sim_id, project_id, graph_id, json.dumps(config.to_dict())),
        )

    return sim_id, project_id


class TestRunSimulation:
    def test_run_produces_result(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, project_id = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Hello"}}],
            input_tokens=100, output_tokens=50,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        progress = []
        result = run_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=mock_client,
            domains_dir=tmp_domains_dir,
            on_progress=lambda **kw: progress.append(kw),
        )

        assert isinstance(result, RunResult)
        assert result.simulation_id == sim_id
        assert result.actions_count > 0

    def test_run_writes_actions_jsonl(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Test"}}],
            input_tokens=100, output_tokens=50,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
        )

        jsonl_path = tmp_data_dir / sim_id / "actions.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) > 0
        action = json.loads(lines[0])
        assert "action_type" in action
        assert "agent_id" in action

    def test_run_updates_db_status(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=50, output_tokens=30,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
        )

        with get_db(tmp_db_path) as conn:
            sim = conn.execute("SELECT status FROM simulations WHERE id = ?", (sim_id,)).fetchone()
            assert sim["status"] == "completed"

    def test_run_inserts_actions_to_db(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "DB test"}}],
            input_tokens=100, output_tokens=50,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
        )

        with get_db(tmp_db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM simulation_actions WHERE simulation_id = ?", (sim_id,)
            ).fetchone()[0]
            assert count > 0

    def test_run_emits_progress_events(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=50, output_tokens=30,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        events = []
        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
            on_progress=lambda **kw: events.append(kw),
        )

        stages = [e.get("stage") for e in events]
        assert "loading" in stages
        assert "running" in stages or "round" in stages
        assert "complete" in stages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_runner.py -v`
Expected: FAIL — `ImportError: cannot import name 'RunResult'`

- [ ] **Step 3: Add RunResult to models.py**

Add after the `PrepareResult` class in `src/forkcast/simulation/models.py`:

```python
@dataclass
class RunResult:
    """Result of running a simulation."""

    simulation_id: str
    actions_count: int
    total_rounds: int
    actions_path: str
    tokens_used: dict[str, int] = field(default_factory=dict)
```

- [ ] **Step 4: Implement run_simulation orchestrator**

```python
# src/forkcast/simulation/runner.py
"""Orchestrate simulation execution: load config, select engine, run, persist."""

import json
import logging
import math
import threading
from pathlib import Path
from typing import Any, Callable

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.action import Action
from forkcast.simulation.claude_engine import ClaudeEngine
from forkcast.simulation.models import AgentProfile, RunResult, SimulationConfig

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None] | None

# Domain prompt key for agent system prompt
AGENT_SYSTEM_PROMPT_KEY = "agent_system"


def run_simulation(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    client: ClaudeClient,
    domains_dir: Path,
    on_progress: ProgressCallback = None,
    max_rounds: int | None = None,
    stop_event: threading.Event | None = None,
) -> RunResult:
    """Run a simulation end-to-end.

    1. Load simulation, config, profiles from DB/disk
    2. Select engine based on engine_type
    3. Run simulation, writing each action to JSONL + SQLite
    4. Update simulation status to 'completed'
    5. Log token usage

    Args:
        max_rounds: If set, overrides total_hours to limit rounds (non-destructive).
        stop_event: If set, the engine checks this event to stop gracefully.
    """

    def _progress(stage: str, **kwargs: Any) -> None:
        if on_progress:
            on_progress(stage=stage, **kwargs)

    # 1. Load simulation record
    _progress(stage="loading")
    with get_db(db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        raise ValueError(f"Simulation not found: {simulation_id}")
    if sim["status"] != "prepared":
        raise ValueError(f"Simulation not in 'prepared' status: {sim['status']}")

    project_id = sim["project_id"]
    engine_type = sim["engine_type"]
    platforms = json.loads(sim["platforms"]) if sim["platforms"] else ["twitter"]

    # Load config — filter to known fields to handle extra keys gracefully
    config_data = json.loads(sim["config_json"])
    known_fields = {f.name for f in SimulationConfig.__dataclass_fields__.values()}
    config = SimulationConfig(**{k: v for k, v in config_data.items() if k in known_fields})

    # Non-destructive max_rounds override: adjust total_hours in memory only
    if max_rounds is not None:
        config.total_hours = max(1, (max_rounds * config.minutes_per_round) / 60)

    # Load profiles
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    if not profiles_path.exists():
        raise FileNotFoundError(f"Profiles not found: {profiles_path}")
    profiles = [AgentProfile(**p) for p in json.loads(profiles_path.read_text(encoding="utf-8"))]

    # Load domain for agent system prompt
    with get_db(db_path) as conn:
        project = conn.execute("SELECT domain FROM projects WHERE id = ?", (project_id,)).fetchone()
    domain = load_domain(project["domain"], domains_dir)

    # Update status to running
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE simulations SET status = 'running', updated_at = datetime('now') WHERE id = ?",
            (simulation_id,),
        )

    # 2. Set up JSONL output
    sim_dir = data_dir / simulation_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    actions_path = sim_dir / "actions.jsonl"
    actions_file = open(actions_path, "w", encoding="utf-8")
    all_actions: list[Action] = []

    def on_action(action: Action) -> None:
        all_actions.append(action)
        actions_file.write(action.to_jsonl() + "\n")
        actions_file.flush()
        _progress(stage="action", **action.to_dict())

    def on_round(round_num: int, total: int) -> None:
        _progress(stage="round", current=round_num, total=total)

    # 3. Select and run engine
    engine_result: dict[str, Any] = {}
    total_tokens: dict[str, int] = {"input": 0, "output": 0}
    try:
        if engine_type == "claude":
            # Try to load agent_system prompt; fall back to a minimal default
            try:
                agent_system_template = read_prompt(domain, AGENT_SYSTEM_PROMPT_KEY)
            except FileNotFoundError:
                agent_system_template = "You are {{ agent_name }}. {{ persona }}"

            _progress(stage="running", engine="claude", total_rounds=0)

            # Run once per platform
            for platform in platforms:
                engine = ClaudeEngine(client=client, agent_system_template=agent_system_template)
                # Wire stop_event to engine
                if stop_event is not None:
                    def _check_stop():
                        if stop_event.is_set():
                            engine.stop()
                    # Check periodically via on_round callback
                    original_on_round = on_round
                    def on_round_with_stop(r, t):
                        _check_stop()
                        original_on_round(r, t)
                    engine_result = engine.run(
                        profiles=profiles,
                        config=config,
                        platform=platform,
                        on_action=on_action,
                        on_round=on_round_with_stop,
                    )
                else:
                    engine_result = engine.run(
                        profiles=profiles,
                        config=config,
                        platform=platform,
                        on_action=on_action,
                        on_round=on_round,
                    )
                total_tokens["input"] += engine_result.get("input_tokens", 0)
                total_tokens["output"] += engine_result.get("output_tokens", 0)

        elif engine_type == "oasis":
            # Deferred import — OASIS is an optional dependency
            from forkcast.simulation.oasis_engine import OasisEngine

            _progress(stage="running", engine="oasis")
            for platform in platforms:
                oasis_engine = OasisEngine(sim_dir=sim_dir)
                # Wire stop_event: OASIS doesn't use on_round from our code,
                # so we spawn a monitor thread that checks the event and kills the subprocess
                if stop_event is not None:
                    def _oasis_stop_monitor():
                        stop_event.wait()
                        oasis_engine.stop()
                    stop_thread = threading.Thread(target=_oasis_stop_monitor, daemon=True)
                    stop_thread.start()
                engine_result = oasis_engine.run(
                    profiles=profiles,
                    config=config,
                    platform=platform,
                    on_action=on_action,
                    on_round=on_round,
                )
        else:
            raise ValueError(f"Unknown engine type: {engine_type}")
    finally:
        actions_file.close()

    # 4. Persist actions to SQLite
    with get_db(db_path) as conn:
        for action in all_actions:
            conn.execute(
                "INSERT INTO simulation_actions "
                "(simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    simulation_id,
                    action.round,
                    action.agent_id,
                    action.agent_name,
                    action.action_type,
                    json.dumps(action.action_args),
                    action.platform,
                    action.timestamp,
                ),
            )

    # 5. Update status
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE simulations SET status = 'completed', updated_at = datetime('now') WHERE id = ?",
            (simulation_id,),
        )

    # 6. Log token usage
    if engine_type == "claude" and (total_tokens["input"] > 0 or total_tokens["output"] > 0):
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO token_usage (project_id, stage, model, input_tokens, output_tokens, created_at) "
                "VALUES (?, 'simulation_run', ?, ?, ?, datetime('now'))",
                (project_id, client.default_model, total_tokens["input"], total_tokens["output"]),
            )

    _progress(stage="complete", actions_count=len(all_actions))

    return RunResult(
        simulation_id=simulation_id,
        actions_count=len(all_actions),
        total_rounds=engine_result.get("total_rounds", 0),
        actions_path=str(actions_path),
        tokens_used=total_tokens if engine_type == "claude" else {},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_simulation_runner.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/simulation/models.py src/forkcast/simulation/runner.py tests/test_simulation_runner.py
git commit -m "feat: simulation runner orchestrator — engine selection, JSONL + SQLite persistence"
```

---

## Task 6: API Endpoints — Start, Stop, Run Stream

**Files:**
- Modify: `src/forkcast/api/simulation_routes.py` — add start/stop/stream endpoints
- Create: `tests/test_api_simulation_run.py`

Follows the same non-blocking POST + SSE stream pattern from Phase 3. `POST /start` fires a background task, `GET /run/stream` provides real-time action events, `POST /stop` signals graceful termination.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_simulation_run.py
"""Tests for simulation run API endpoints (start, stop, stream)."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from forkcast.api.app import create_app
from forkcast.db.connection import get_db, init_db


@pytest.fixture
def app(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    with patch("forkcast.api.simulation_routes.get_settings") as mock_settings, \
         patch("forkcast.api.project_routes.get_settings") as mock_ps, \
         patch("forkcast.api.graph_routes.get_settings") as mock_gs, \
         patch("forkcast.api.domain_routes.get_settings") as mock_ds:
        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        settings.anthropic_api_key = "test-key"
        mock_settings.return_value = settings
        mock_ps.return_value = settings
        mock_gs.return_value = settings
        mock_ds.return_value = settings

        init_db(tmp_db_path)
        application = create_app()
        yield application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def prepared_sim(tmp_db_path, tmp_data_dir):
    """Create a prepared simulation in the test DB."""
    project_id = "proj_test"
    graph_id = "graph_test"
    sim_id = "sim_run_test"
    now = datetime.now(timezone.utc).isoformat()

    config = {
        "total_hours": 1, "minutes_per_round": 60,
        "peak_hours": [10], "off_peak_hours": [0],
        "peak_multiplier": 1.5, "off_peak_multiplier": 0.3,
        "seed_posts": [], "hot_topics": ["AI"],
        "narrative_direction": "", "agent_configs": [], "platform_config": {},
    }

    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "A researcher.", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"],
         "entity_type": "Person", "entity_source": "Alice"},
    ]

    # Write profiles
    profiles_dir = tmp_data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "agents.json").write_text(json.dumps(profiles), encoding="utf-8")

    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'Test question', ?)",
            (project_id, now),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, created_at) VALUES (?, ?, 'complete', ?)",
            (graph_id, project_id, now),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, config_json, created_at) "
            "VALUES (?, ?, ?, 'prepared', 'claude', '[\"twitter\"]', ?, ?)",
            (sim_id, project_id, graph_id, json.dumps(config), now),
        )

    return sim_id


class TestStartSimulation:
    def test_start_returns_immediately(self, client, prepared_sim):
        with patch("forkcast.api.simulation_routes.ClaudeClient"):
            resp = client.post(f"/api/simulations/{prepared_sim}/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "running"

    def test_start_not_found(self, client):
        resp = client.post("/api/simulations/nonexistent/start")
        assert resp.status_code == 404

    def test_start_wrong_status(self, client, tmp_db_path, prepared_sim):
        # Change status to 'created' (not prepared)
        with get_db(tmp_db_path) as conn:
            conn.execute("UPDATE simulations SET status = 'created' WHERE id = ?", (prepared_sim,))
        with patch("forkcast.api.simulation_routes.ClaudeClient"):
            resp = client.post(f"/api/simulations/{prepared_sim}/start")
        assert resp.status_code == 400


class TestStopSimulation:
    def test_stop_not_found(self, client):
        resp = client.post("/api/simulations/nonexistent/stop")
        assert resp.status_code == 404

    def test_stop_not_running(self, client, prepared_sim):
        resp = client.post(f"/api/simulations/{prepared_sim}/stop")
        assert resp.status_code == 400


class TestRunStream:
    def test_stream_not_found(self, client):
        resp = client.get("/api/simulations/nonexistent/run/stream")
        assert resp.status_code == 404


class TestGetSimulationActions:
    def test_get_actions_empty(self, client, prepared_sim):
        resp = client.get(f"/api/simulations/{prepared_sim}/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []

    def test_get_actions_with_data(self, client, prepared_sim, tmp_db_path):
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO simulation_actions (simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
                "VALUES (?, 1, 0, 'alice', 'CREATE_POST', '{\"content\": \"Hello\"}', 'twitter', '2026-03-20T10:00:00Z')",
                (prepared_sim,),
            )
        resp = client.get(f"/api/simulations/{prepared_sim}/actions")
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["action_type"] == "CREATE_POST"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_api_simulation_run.py -v`
Expected: FAIL — routes don't exist yet

- [ ] **Step 3: Add start/stop/stream/actions endpoints to simulation_routes.py**

Add the following to the end of `src/forkcast/api/simulation_routes.py` (after the existing `stream_prepare` function at line ~204):

```python
# --- Run simulation endpoints ---

import threading

# Per-simulation run queues and stop events
_run_queues: dict[str, asyncio.Queue] = {}
_stop_events: dict[str, threading.Event] = {}


@router.post("/{simulation_id}/start")
async def start_simulation(simulation_id: str):
    """Start running a prepared simulation as a background task.

    Returns immediately with status 'running'. Monitor via
    GET /api/simulations/{id}/run/stream (SSE).
    """
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)
    if sim["status"] != "prepared":
        return error(f"Simulation must be in 'prepared' status to start (current: {sim['status']})", status_code=400)

    queue: asyncio.Queue = asyncio.Queue()
    _run_queues[simulation_id] = queue
    stop_event = threading.Event()
    _stop_events[simulation_id] = stop_event
    loop = asyncio.get_event_loop()

    client = ClaudeClient(api_key=settings.anthropic_api_key)

    def on_progress(stage: str, **kwargs):
        event = {"stage": stage, **kwargs}
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _run():
        from forkcast.simulation.runner import run_simulation
        return run_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
            stop_event=stop_event,
        )

    async def _background_run():
        try:
            result = await asyncio.to_thread(_run)
            queue.put_nowait({
                "stage": "result",
                "simulation_id": result.simulation_id,
                "actions_count": result.actions_count,
                "total_rounds": result.total_rounds,
                "tokens_used": result.tokens_used,
            })
        except Exception as e:
            logger.exception(f"Simulation run failed for {simulation_id}")
            queue.put_nowait({"stage": "error", "message": str(e)})
        finally:
            queue.put_nowait(None)
            _stop_events.pop(simulation_id, None)

    asyncio.create_task(_background_run())

    return success({"status": "running", "simulation_id": simulation_id})


@router.post("/{simulation_id}/stop")
async def stop_simulation(simulation_id: str):
    """Stop a running simulation gracefully via stop_event."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)

    stop_event = _stop_events.get(simulation_id)
    if stop_event is None:
        return error("No running simulation to stop", status_code=400)

    stop_event.set()
    return success({"status": "stopping", "simulation_id": simulation_id})


@router.get("/{simulation_id}/run/stream")
async def stream_run(simulation_id: str, request: Request):
    """SSE stream for simulation run progress and actions."""
    queue = _run_queues.get(simulation_id)
    if queue is None:
        return error("No run job active for this simulation", status_code=404)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue

            if event is None:
                yield {"event": "complete", "data": "{}"}
                _run_queues.pop(simulation_id, None)
                break

            yield {"event": event.get("stage", "progress"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@router.get("/{simulation_id}/actions")
async def get_simulation_actions(simulation_id: str):
    """Get all recorded actions for a simulation."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()
        if sim is None:
            return error(f"Simulation not found: {simulation_id}", status_code=404)

        rows = conn.execute(
            "SELECT round, agent_id, agent_name, action_type, content, platform, timestamp "
            "FROM simulation_actions WHERE simulation_id = ? ORDER BY id",
            (simulation_id,),
        ).fetchall()

    actions = []
    for row in rows:
        d = dict(row)
        if d["content"]:
            try:
                d["action_args"] = json.loads(d["content"])
            except json.JSONDecodeError:
                d["action_args"] = {"content": d["content"]}
        else:
            d["action_args"] = {}
        d.pop("content", None)
        actions.append(d)

    return success(actions)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_api_simulation_run.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/api/simulation_routes.py tests/test_api_simulation_run.py
git commit -m "feat: simulation run API — start (non-blocking), stop, SSE stream, actions query"
```

---

## Task 7: CLI Commands — sim start and sim stop

**Files:**
- Modify: `src/forkcast/cli/sim_cmd.py` — add `start` and `stop` commands
- Create: `tests/test_cli_sim_run.py`

The CLI `sim start` command calls `run_simulation()` directly (synchronous, with progress output). `sim stop` is deferred — it requires the API server to be running (the CLI doesn't manage background processes). Users stop simulations via `POST /api/simulations/{id}/stop`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_sim_run.py
"""Tests for CLI sim start command."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from forkcast.cli.main import app
from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.simulation.models import RunResult


runner = CliRunner()


def _setup_prepared_sim(db_path, data_dir, domains_dir):
    """Create a prepared simulation."""
    init_db(db_path)
    project_id = "proj_cli"
    graph_id = "graph_cli"
    sim_id = "sim_cli_run"

    config = {
        "total_hours": 1, "minutes_per_round": 60,
        "peak_hours": [], "off_peak_hours": [],
        "peak_multiplier": 1.0, "off_peak_multiplier": 1.0,
        "seed_posts": [], "hot_topics": [],
        "narrative_direction": "", "agent_configs": [], "platform_config": {},
    }

    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "A researcher.", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"],
         "entity_type": "Person", "entity_source": "Alice"},
    ]

    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "agents.json").write_text(json.dumps(profiles), encoding="utf-8")

    # Domain setup
    default_domain = domains_dir / "_default"
    default_domain.mkdir(parents=True, exist_ok=True)
    (default_domain / "manifest.yaml").write_text(
        "name: _default\nversion: '1.0'\ndescription: Default\nlanguage: en\n"
        "sim_engine: claude\nplatforms: [twitter]\n"
    )
    prompts = default_domain / "prompts"
    prompts.mkdir(exist_ok=True)
    for name in ["ontology.md", "persona.md", "report_guidelines.md", "config_gen.md"]:
        (prompts / name).write_text(f"# {name}\nPlaceholder.\n")

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'Test', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, created_at) VALUES (?, ?, 'complete', datetime('now'))",
            (graph_id, project_id),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, config_json, created_at) "
            "VALUES (?, ?, ?, 'prepared', 'claude', '[\"twitter\"]', ?, datetime('now'))",
            (sim_id, project_id, graph_id, json.dumps(config)),
        )

    return sim_id


class TestSimStart:
    @patch("forkcast.cli.sim_cmd.get_settings")
    @patch("forkcast.cli.sim_cmd.ClaudeClient")
    def test_start_succeeds(self, mock_client_cls, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id = _setup_prepared_sim(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        settings.anthropic_api_key = "test-key"
        mock_settings.return_value = settings

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="", tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Hi"}}],
            input_tokens=100, output_tokens=50, model="claude-sonnet-4-6", stop_reason="tool_use",
        )
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["sim", "start", sim_id])
        assert result.exit_code == 0
        assert "complete" in result.output.lower() or "actions" in result.output.lower()

    @patch("forkcast.cli.sim_cmd.get_settings")
    def test_start_not_found(self, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)
        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        mock_settings.return_value = settings

        result = runner.invoke(app, ["sim", "start", "nonexistent"])
        assert result.exit_code == 1

    @patch("forkcast.cli.sim_cmd.get_settings")
    def test_start_wrong_status(self, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id = _setup_prepared_sim(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        mock_settings.return_value = settings

        # Change to created status
        with get_db(tmp_db_path) as conn:
            conn.execute("UPDATE simulations SET status = 'created' WHERE id = ?", (sim_id,))

        result = runner.invoke(app, ["sim", "start", sim_id])
        assert result.exit_code == 1

    @patch("forkcast.cli.sim_cmd.get_settings")
    @patch("forkcast.cli.sim_cmd.ClaudeClient")
    def test_start_with_max_rounds(self, mock_client_cls, mock_settings, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id = _setup_prepared_sim(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        settings = MagicMock()
        settings.db_path = tmp_db_path
        settings.data_dir = tmp_data_dir
        settings.domains_dir = tmp_domains_dir
        settings.anthropic_api_key = "test-key"
        mock_settings.return_value = settings

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="", tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=50, output_tokens=30, model="claude-sonnet-4-6", stop_reason="tool_use",
        )
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["sim", "start", sim_id, "--max-rounds", "1"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_cli_sim_run.py -v`
Expected: FAIL — no `start` command

- [ ] **Step 3: Add start command to sim_cmd.py**

Add to the end of `src/forkcast/cli/sim_cmd.py`:

```python
@sim_app.command("start")
def sim_start(
    simulation_id: str,
    max_rounds: Annotated[int | None, typer.Option(help="Maximum rounds to run")] = None,
):
    """Start running a prepared simulation."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status, engine_type, config_json FROM simulations WHERE id = ?",
            (simulation_id,),
        ).fetchone()

    if sim is None:
        typer.echo(f"Error: Simulation not found: {simulation_id}", err=True)
        raise typer.Exit(code=1)

    if sim["status"] != "prepared":
        typer.echo(f"Error: Simulation must be 'prepared' to start (current: {sim['status']})", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Starting simulation {simulation_id} (engine: {sim['engine_type']})...")
    client = ClaudeClient(api_key=settings.anthropic_api_key)

    def on_progress(stage: str, **kwargs):
        if stage == "round":
            typer.echo(f"  [round] {kwargs.get('current', '?')}/{kwargs.get('total', '?')}")
        elif stage == "action":
            agent = kwargs.get("agent_name", "?")
            atype = kwargs.get("action_type", "?")
            typer.echo(f"  [action] {agent}: {atype}")
        elif stage not in ("loading", "running"):
            typer.echo(f"  [{stage}]")

    try:
        from forkcast.simulation.runner import run_simulation
        result = run_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
            max_rounds=max_rounds,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\nSimulation complete!")
    typer.echo(f"  Actions: {result.actions_count}")
    typer.echo(f"  Rounds:  {result.total_rounds}")
    typer.echo(f"  Output:  {result.actions_path}")
    if result.tokens_used:
        typer.echo(f"  Tokens:  {result.tokens_used.get('input', 0)} in / {result.tokens_used.get('output', 0)} out")
```

Note: `run_simulation` is imported inside the function body to avoid circular imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_cli_sim_run.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/forkcast/cli/sim_cmd.py tests/test_cli_sim_run.py
git commit -m "feat: CLI sim start command with --max-rounds option"
```

---

## Task 8: Domain Prompt Registration and Integration Test

**Files:**
- Modify: `domains/_default/manifest.yaml` — add `agent_system` prompt key
- Modify: `src/forkcast/domains/loader.py:14` — add `agent_system` to PROMPT_KEYS
- Create: `tests/test_integration_simulation.py`

Wire up the `agent_system` prompt in the domain loader so that `read_prompt(domain, "agent_system")` resolves to `prompts/agent_system.md`. Then write an integration test that exercises the full create → prepare → run pipeline with mocks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration_simulation.py
"""Integration test: create simulation → prepare → run (with mocked LLM)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from forkcast.db.connection import get_db, init_db
from forkcast.domains.loader import load_domain, read_prompt, PROMPT_KEYS
from forkcast.llm.client import LLMResponse
from forkcast.simulation.runner import run_simulation


class TestAgentSystemPromptRegistered:
    def test_agent_system_in_prompt_keys(self):
        assert "agent_system" in PROMPT_KEYS

    def test_agent_system_loads_from_default_domain(self, tmp_domains_dir):
        # Write agent_system.md to the tmp domain
        prompts_dir = tmp_domains_dir / "_default" / "prompts"
        (prompts_dir / "agent_system.md").write_text(
            "You are {{ agent_name }}. {{ persona }}"
        )
        domain = load_domain("_default", tmp_domains_dir)
        text = read_prompt(domain, "agent_system")
        assert "agent_name" in text


class TestFullSimulationPipeline:
    def test_create_prepare_run(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        """Full pipeline: DB setup → run_simulation with mocked Claude client."""
        init_db(tmp_db_path)

        project_id = "proj_integ"
        graph_id = "graph_integ"
        sim_id = "sim_integ"

        # Write graph data
        graph_dir = tmp_data_dir / project_id
        graph_dir.mkdir(parents=True)
        graph_data = {
            "nodes": [
                {"id": "Alice", "type": "Person"},
                {"id": "Bob", "type": "Person"},
            ],
            "edges": [{"source": "Alice", "target": "Bob", "type": "knows"}],
        }
        (graph_dir / "graph.json").write_text(json.dumps(graph_data))

        # Profiles (pre-generated for this test)
        profiles = [
            {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Researcher",
             "persona": "AI safety researcher.", "age": 30, "gender": "female",
             "profession": "Researcher", "interests": ["AI"],
             "entity_type": "Person", "entity_source": "Alice"},
            {"agent_id": 1, "name": "Bob", "username": "bob", "bio": "Engineer",
             "persona": "Software engineer.", "age": 35, "gender": "male",
             "profession": "Engineer", "interests": ["code"],
             "entity_type": "Person", "entity_source": "Bob"},
        ]
        profiles_dir = tmp_data_dir / sim_id / "profiles"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "agents.json").write_text(json.dumps(profiles))

        config = {
            "total_hours": 1, "minutes_per_round": 60,
            "peak_hours": [], "off_peak_hours": [],
            "peak_multiplier": 1.0, "off_peak_multiplier": 1.0,
            "seed_posts": ["Discuss AI"], "hot_topics": ["AI safety"],
            "narrative_direction": "Open discussion",
            "agent_configs": [], "platform_config": {},
        }

        # Write agent_system.md
        prompts_dir = tmp_domains_dir / "_default" / "prompts"
        (prompts_dir / "agent_system.md").write_text(
            "You are {{ agent_name }}. {{ persona }}"
        )

        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES (?, '_default', 'Integration', 'created', 'Predict AI', datetime('now'))",
                (project_id,),
            )
            conn.execute(
                "INSERT INTO graphs (id, project_id, status, file_path, created_at) "
                "VALUES (?, ?, 'complete', ?, datetime('now'))",
                (graph_id, project_id, str(graph_dir / "graph.json")),
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, config_json, created_at) "
                "VALUES (?, ?, ?, 'prepared', 'claude', '[\"twitter\"]', ?, datetime('now'))",
                (sim_id, project_id, graph_id, json.dumps(config)),
            )

        # Mock Claude client
        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "AI is transforming everything"}}],
            input_tokens=150, output_tokens=60,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        events = []
        result = run_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=mock_client,
            domains_dir=tmp_domains_dir,
            on_progress=lambda **kw: events.append(kw),
        )

        # Verify result
        assert result.simulation_id == sim_id
        assert result.actions_count > 0

        # Verify JSONL written
        jsonl = (tmp_data_dir / sim_id / "actions.jsonl").read_text()
        lines = [l for l in jsonl.strip().split("\n") if l]
        assert len(lines) == result.actions_count

        # Verify DB updated
        with get_db(tmp_db_path) as conn:
            sim = conn.execute("SELECT status FROM simulations WHERE id = ?", (sim_id,)).fetchone()
            assert sim["status"] == "completed"

            action_count = conn.execute(
                "SELECT COUNT(*) FROM simulation_actions WHERE simulation_id = ?", (sim_id,)
            ).fetchone()[0]
            assert action_count == result.actions_count

        # Verify progress events
        stages = [e["stage"] for e in events]
        assert "loading" in stages
        assert "complete" in stages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_integration_simulation.py -v`
Expected: FAIL — `agent_system` not in PROMPT_KEYS

- [ ] **Step 3: Register agent_system prompt**

In `src/forkcast/domains/loader.py`, update line 14:

```python
PROMPT_KEYS = ["ontology", "persona", "report_guidelines", "config_generation", "agent_system"]
```

In `src/forkcast/domains/loader.py`, update `DEFAULT_PROMPT_FILES` (around line 15-20):

```python
DEFAULT_PROMPT_FILES = {
    "ontology": "prompts/ontology.md",
    "persona": "prompts/persona.md",
    "report_guidelines": "prompts/report_guidelines.md",
    "config_generation": "prompts/config_gen.md",
    "agent_system": "prompts/agent_system.md",
}
```

In `domains/_default/manifest.yaml`, add the agent_system prompt:

```yaml
name: _default
version: "1.0"
description: "Default domain — general-purpose collective intelligence simulation"
language: en
sim_engine: claude
platforms:
  - twitter
  - reddit
prompts:
  ontology: prompts/ontology.md
  persona: prompts/persona.md
  report_guidelines: prompts/report_guidelines.md
  config_generation: prompts/config_gen.md
  agent_system: prompts/agent_system.md
ontology:
  hints: ontology/hints.yaml
  max_entity_types: 10
  required_fallbacks:
    - Person
    - Organization
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_integration_simulation.py -v`
Expected: 3 passed

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v`
Expected: All tests pass (existing + new)

- [ ] **Step 6: Commit**

```bash
git add src/forkcast/domains/loader.py domains/_default/manifest.yaml domains/_default/prompts/agent_system.md tests/test_integration_simulation.py
git commit -m "feat: register agent_system prompt, integration test for full simulation pipeline"
```

---

## Summary

| Task | Component | New Tests | New/Modified Files |
|------|-----------|-----------|-------------------|
| 1 | Action dataclass | 6 | 2 new |
| 2 | SimulationState | 17 | 2 new |
| 3 | Claude Engine | 16 | 3 new |
| 4 | OASIS Engine | 8 | 2 new |
| 5 | Runner orchestrator | 5 | 2 new, 1 modified |
| 6 | API endpoints | 8 | 1 modified, 1 new |
| 7 | CLI commands | 4 | 1 modified, 1 new |
| 8 | Domain integration | 3 | 2 modified, 1 new |
| **Total** | | **67** | **14 new, 4 modified** |
