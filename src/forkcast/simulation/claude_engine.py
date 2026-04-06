"""Claude simulation engine — runs agents in-process via tool_use."""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Callable

from jinja2 import Template

from forkcast.llm.client import LLMClient
from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import AgentProfile, SimulationConfig
from forkcast.simulation.state import SimulationState

if TYPE_CHECKING:
    from forkcast.simulation.dynamics import DynamicsState

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

# Stripped-down tools for Phase 1 (decision only — no content fields)
DECISION_TOOLS = [
    {
        "name": "create_post",
        "description": "Decide to write a new post on the platform",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
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
        "description": "Decide to reply to a specific post",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "The ID of the post to comment on"},
            },
            "required": ["post_id"],
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

# Phase 2 tool — content generation only
CREATIVE_TOOLS = [
    {
        "name": "write_content",
        "description": "Write the content for your post or comment",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The text content to publish"},
            },
            "required": ["content"],
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
    if len(tool_calls) > 1:
        logger.debug(f"Multiple tool calls received ({len(tool_calls)}), using first only")
    call = tool_calls[0]
    action_type = _TOOL_TO_ACTION.get(call["name"], ActionType.DO_NOTHING)
    return action_type, call.get("input", {})


def _determine_active_agents(
    profiles: list[AgentProfile],
    config: SimulationConfig,
    current_hour: int,
    dynamics: DynamicsState | None = None,
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

    active = []
    for p in profiles:
        if dynamics is not None and p.agent_id in dynamics.circadian_models:
            prob = dynamics.circadian_models[p.agent_id].get_activation_probability()
        else:
            prob = min(1.0, base_prob * multiplier)
        if random.random() < prob:
            active.append(p)
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
    compress_feed: bool = False,
    dynamics: DynamicsState | None = None,
) -> dict[str, Any]:
    """Build the system prompt and messages for one agent's decision turn."""
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

    parts = [f"Round {round_num}. Here is your current feed:\n"]

    feed = state.get_feed(agent_id=profile.agent_id, limit=10)
    if feed:
        for i, post in enumerate(feed):
            if compress_feed and len(feed) > 5 and i >= 3:
                parts.append(post.to_summary_text())
            else:
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

    # Inject engagement dynamics signals
    if dynamics and dynamics.engagement_models:
        trending = [
            m.get_engagement_context()
            for m in dynamics.engagement_models.values()
            if m.get_engagement_context()["trend_status"] in ("trending", "viral")
        ]
        if trending:
            signals = ", ".join(
                f"Post #{s['post_id']} is {s['trend_status']} ({s['saturation_pct']}% saturation)"
                for s in trending
            )
            parts.append(f"\n[Platform signals: {signals}]")

    parts.append("What would you like to do? Use one of the available tools.")

    user_content = "\n".join(parts)
    return {
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }


class ClaudeEngine:
    """Run a simulation using Claude as the agent brain with two-phase routing."""

    def __init__(
        self,
        client: LLMClient,
        agent_system_template: str,
        decision_model: str = "claude-haiku-4-5",
        creative_model: str = "claude-sonnet-4-6",
    ):
        self.client = client
        self.agent_system_template = agent_system_template
        self.decision_model = decision_model
        self.creative_model = creative_model
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
        on_round_complete: Callable[[int, int], None] | None = None,
        dynamics: DynamicsState | None = None,
    ) -> dict[str, Any]:
        """Run the full simulation. Returns per-phase token usage stats."""
        feed_weights = config.platform_config.get(
            "feed_weights", {"recency": 0.5, "popularity": 0.3, "relevance": 0.2}
        )
        self.state = SimulationState(platform=platform, feed_weights=feed_weights)
        self._stopped = False

        total_rounds = math.ceil((config.total_hours * 60) / config.minutes_per_round)
        decision_input = 0
        decision_output = 0
        creative_input = 0
        creative_output = 0
        action_count = 0
        start_time = datetime.now(timezone.utc)
        completed_rounds = 0

        for round_num in range(1, total_rounds + 1):
            if self._stopped:
                break

            sim_time = start_time + timedelta(minutes=(round_num - 1) * config.minutes_per_round)
            current_hour = sim_time.hour
            timestamp = sim_time.isoformat()

            if on_round:
                on_round(round_num, total_rounds)

            # Pre-round: evolve circadian clocks
            if dynamics is not None and config.circadian_enabled:
                dynamics.evolve_circadian()

            active = _determine_active_agents(profiles, config, current_hour, dynamics=dynamics)

            # Snapshot state at round start — all agents see the same feed
            round_snapshot = self.state.snapshot()
            buffered_actions: list[tuple[AgentProfile, str, dict[str, Any], bool]] = []

            for profile in active:
                if self._stopped:
                    break

                context = _build_agent_context(
                    profile=profile,
                    state=round_snapshot,
                    round_num=round_num,
                    hot_topics=config.hot_topics,
                    seed_posts=config.seed_posts if round_num == 1 else [],
                    agent_system_template=self.agent_system_template,
                    compress_feed=config.compress_feed,
                    dynamics=dynamics,
                )

                call_succeeded = True
                try:
                    # Phase 1: Decision
                    response = self.client.tool_use(
                        messages=context["messages"],
                        tools=DECISION_TOOLS,
                        system=context["system"],
                        model=self.decision_model,
                        max_tokens=256,
                        temperature=1.0,
                        use_cache=True,
                    )
                    decision_input += response.input_tokens
                    decision_output += response.output_tokens

                    action_type, action_args = _parse_tool_action(response.tool_calls)

                    # Phase 2: Content creation (only for creative actions)
                    if action_type in (ActionType.CREATE_POST, ActionType.CREATE_COMMENT):
                        creative_context = self._build_creative_context(
                            profile=profile,
                            action_type=action_type,
                            action_args=action_args,
                            state=round_snapshot,
                            config=config,
                        )
                        creative_response = self.client.tool_use(
                            messages=creative_context["messages"],
                            tools=CREATIVE_TOOLS,
                            system=creative_context["system"],
                            model=self.creative_model,
                            max_tokens=1024,
                            temperature=1.0,
                            use_cache=True,
                        )
                        creative_input += creative_response.input_tokens
                        creative_output += creative_response.output_tokens

                        content = ""
                        if creative_response.tool_calls:
                            content = creative_response.tool_calls[0].get("input", {}).get("content", "")
                        action_args["content"] = content

                except Exception as e:
                    logger.warning(f"Agent {profile.name} failed: {e}")
                    action_type = ActionType.DO_NOTHING
                    action_args = {"error": str(e)}
                    call_succeeded = False

                buffered_actions.append((profile, action_type, action_args, call_succeeded))

            # Apply all buffered actions at end of round
            for profile, action_type, action_args, call_succeeded in buffered_actions:
                self._apply_action(profile, action_type, action_args, timestamp)
                action = Action(
                    round=round_num,
                    timestamp=timestamp,
                    agent_id=profile.agent_id,
                    agent_name=profile.username,
                    platform=platform,
                    action_type=action_type,
                    action_args=action_args,
                    success=call_succeeded,
                )
                on_action(action)
                action_count += 1

            # Post-round: register new posts and evolve engagement
            if dynamics is not None and config.engagement_enabled:
                from forkcast.simulation.dynamics import compute_carrying_capacity
                posts_before_round = len(round_snapshot.posts)
                new_post_idx = 0
                for profile, action_type, action_args, _ in buffered_actions:
                    if action_type == ActionType.CREATE_POST:
                        post_id = posts_before_round + new_post_idx
                        new_post_idx += 1
                        follower_count = len(self.state.followers.get(profile.agent_id, set()))
                        k = compute_carrying_capacity(
                            num_agents=len(profiles),
                            follower_count=follower_count,
                            hot_topics=config.hot_topics,
                            post_content=action_args.get("content", ""),
                            total_agents=len(profiles),
                        )
                        dynamics.register_post(post_id=post_id, carrying_capacity=k)
                    elif action_type in (ActionType.LIKE_POST, ActionType.DISLIKE_POST):
                        pid = action_args.get("post_id", -1)
                        if pid in dynamics.engagement_models:
                            dynamics.engagement_models[pid].inject_discrete_engagement(1)

                dt = config.minutes_per_round / 60.0
                dynamics.evolve_engagement(dt)

            if not self._stopped:
                completed_rounds = round_num
                if on_round_complete:
                    on_round_complete(round_num, total_rounds)

        return {
            "total_rounds": completed_rounds,
            "total_actions": action_count,
            "decision_tokens": {"input": decision_input, "output": decision_output, "model": self.decision_model},
            "creative_tokens": {"input": creative_input, "output": creative_output, "model": self.creative_model},
        }

    def _build_creative_context(
        self,
        profile: AgentProfile,
        action_type: str,
        action_args: dict[str, Any],
        state: SimulationState,
        config: SimulationConfig,
    ) -> dict[str, Any]:
        """Build the system prompt and messages for Phase 2 content generation."""
        template = Template(self.agent_system_template)
        system = template.render(
            agent_name=profile.name,
            username=profile.username,
            platform=state.platform,
            persona=profile.persona,
            age=profile.age,
            profession=profile.profession,
            interests=", ".join(profile.interests),
        )

        parts = []
        if action_type == ActionType.CREATE_COMMENT:
            post_id = action_args.get("post_id", -1)
            if 0 <= post_id < len(state.posts):
                post = state.posts[post_id]
                comments = state.get_post_comments(post_id)
                parts.append(f"You decided to reply to this post:\n{post.to_feed_text(comments)}\n")
            parts.append("Write your reply. Be specific — reference what they said.")
        else:  # CREATE_POST
            if config.hot_topics:
                parts.append(f"Trending topics: {', '.join(config.hot_topics)}")
            if config.narrative_direction:
                parts.append(f"Context: {config.narrative_direction}")
            if state.posts:
                total = len(state.posts)
                recent = state.posts[-3:] if len(state.posts) > 3 else state.posts
                summaries = [f"@{p.author_name}: {p.content[:60]}" for p in recent]
                parts.append(f"The conversation so far ({total} posts). Recent:")
                parts.extend(f"  - {s}" for s in summaries)
            parts.append("\nWrite your post. Keep it concise (1-3 sentences).")

        return {
            "system": system,
            "messages": [{"role": "user", "content": "\n".join(parts)}],
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
