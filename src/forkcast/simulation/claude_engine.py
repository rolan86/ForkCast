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
    if len(tool_calls) > 1:
        logger.debug(f"Multiple tool calls received ({len(tool_calls)}), using first only")
    call = tool_calls[0]
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
        action_count = 0
        start_time = datetime.now(timezone.utc)
        round_num = 0
        completed_rounds = 0

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

                call_succeeded = True
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
                    call_succeeded = False

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
                    success=call_succeeded,
                )
                on_action(action)
                action_count += 1

            if not self._stopped:
                completed_rounds = round_num

        return {
            "total_rounds": completed_rounds,
            "total_actions": action_count,
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
