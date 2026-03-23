"""OASIS simulation engine -- in-process API runner."""

import asyncio
import csv
import io
import json
import logging
import math
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable

from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import AgentProfile, SimulationConfig

logger = logging.getLogger(__name__)

# Map OASIS ActionType.value strings to our ActionType
_OASIS_ACTION_MAP: dict[str, str] = {
    "create_post": ActionType.CREATE_POST,
    "like_post": ActionType.LIKE_POST,
    "dislike_post": ActionType.DISLIKE_POST,
    "create_comment": ActionType.CREATE_COMMENT,
    "follow": ActionType.FOLLOW,
    "mute": ActionType.MUTE,
    "do_nothing": ActionType.DO_NOTHING,
    "repost": ActionType.CREATE_POST,
}


def _convert_profiles_to_twitter_csv(profiles: list[AgentProfile]) -> str:
    """Convert profiles to OASIS Twitter CSV format.

    OASIS Twitter requires exactly 5 columns: user_id, name, username, user_char, description.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "name", "username", "user_char", "description"])
    for p in profiles:
        writer.writerow([p.agent_id, p.name, p.username, p.persona, p.bio])
    return output.getvalue()


def _convert_profiles_to_reddit_json(profiles: list[AgentProfile]) -> list[dict[str, Any]]:
    """Convert profiles to OASIS Reddit JSON format."""
    return [
        {
            "user_id": p.agent_id,
            "username": p.username,
            "name": p.name,
            "bio": p.bio,
            "persona": p.persona,
            "age": p.age,
            "gender": p.gender,
            "karma": 0,
            "mbti": "",
            "country": "",
        }
        for p in profiles
    ]


def _trace_row_to_action(
    row: dict[str, Any],
    round_num: int,
    platform: str,
    profiles: list[AgentProfile],
) -> Action:
    """Convert an OASIS trace table row to a ForkCast Action."""
    user_id = row.get("user_id", 0)
    oasis_action = row.get("action", "do_nothing")
    action_type = _OASIS_ACTION_MAP.get(oasis_action, ActionType.DO_NOTHING)

    action_args: dict[str, Any] = {}
    info_str = row.get("info", "{}")
    try:
        info = json.loads(info_str) if isinstance(info_str, str) else info_str
        if isinstance(info, dict):
            if "content" in info:
                action_args["content"] = info["content"]
            if "post_id" in info:
                action_args["post_id"] = info["post_id"]
            if "user_id" in info:
                action_args["user_id"] = info["user_id"]
    except (json.JSONDecodeError, TypeError):
        pass

    agent_name = f"agent{user_id}"
    for p in profiles:
        if p.agent_id == user_id:
            agent_name = p.name
            break

    return Action(
        round=round_num,
        timestamp=row.get("created_at", ""),
        agent_id=user_id,
        agent_name=agent_name,
        platform=platform,
        action_type=action_type,
        action_args=action_args,
    )


def _import_oasis():
    """Import the oasis module. Raises ImportError if not installed."""
    import oasis
    return oasis


class OasisEngine:
    """Run a simulation using OASIS's in-process Python API.

    Supports two agent modes:
    - 'llm': Each agent gets LLMAction() -- OASIS uses camel-ai's LLM integration
    - 'native': Each agent gets ManualAction() -- rule-based action selection
    """

    def __init__(self, sim_dir: Path) -> None:
        self.sim_dir = sim_dir
        self._stopped = False

    def stop(self) -> None:
        """Signal the engine to stop after the current round."""
        self._stopped = True

    def run(
        self,
        profiles: list[AgentProfile],
        config: SimulationConfig,
        platform: str,
        agent_mode: str = "llm",
        on_action: Callable[[Action], None] = lambda a: None,
        on_round: Callable[[int, int], None] | None = None,
        on_round_complete: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Run OASIS simulation using the in-process API."""
        if self._stopped:
            return {"total_rounds": 0, "total_actions": 0}
        self._stopped = False
        return asyncio.run(self._run_async(
            profiles, config, platform, agent_mode,
            on_action, on_round, on_round_complete,
        ))

    async def _run_async(
        self,
        profiles: list[AgentProfile],
        config: SimulationConfig,
        platform: str,
        agent_mode: str,
        on_action: Callable[[Action], None],
        on_round: Callable[[int, int], None] | None,
        on_round_complete: Callable[[int, int], None] | None,
    ) -> dict[str, Any]:
        oasis = _import_oasis()
        self.sim_dir.mkdir(parents=True, exist_ok=True)

        # Write profile files
        if platform == "twitter":
            profile_path = self.sim_dir / "twitter_profiles.csv"
            profile_path.write_text(
                _convert_profiles_to_twitter_csv(profiles), encoding="utf-8"
            )
        else:
            profile_path = self.sim_dir / f"{platform}_profiles.json"
            profile_path.write_text(
                json.dumps(_convert_profiles_to_reddit_json(profiles), indent=2),
                encoding="utf-8",
            )

        # Bridge ForkCast LLM config to camel-ai env vars
        self._bridge_llm_config()

        # Build model for LLM mode
        model = None
        if agent_mode == "llm":
            model = self._create_camel_model()

        # Create agent graph
        if platform == "twitter":
            agent_graph = await oasis.generate_twitter_agent_graph(
                profile_path=str(profile_path),
                model=model,
            )
            oasis_platform = oasis.DefaultPlatformType.TWITTER
        else:
            agent_graph = await oasis.generate_reddit_agent_graph(
                profile_path=str(profile_path),
                model=model,
            )
            oasis_platform = oasis.DefaultPlatformType.REDDIT

        # Create OASIS environment
        oasis_db_path = self.sim_dir / "oasis.db"
        env = oasis.make(
            agent_graph=agent_graph,
            platform=oasis_platform,
            database_path=str(oasis_db_path),
            semaphore=30,
        )
        await env.reset()

        total_rounds = math.ceil(config.total_hours * 60 / config.minutes_per_round)
        total_actions = 0
        last_trace_rowid = 0
        round_num = 0

        try:
            for round_num in range(1, total_rounds + 1):
                if self._stopped:
                    break

                if on_round:
                    on_round(round_num, total_rounds)

                # Build actions for this round
                try:
                    if agent_mode == "llm":
                        await env.step({})
                    else:
                        actions = self._build_native_actions(
                            agent_graph, round_num, config, platform, oasis,
                        )
                        await env.step(actions)
                except Exception as step_exc:
                    logger.error("env.step() failed on round %d: %s", round_num, step_exc)

                # Extract new actions from OASIS trace table
                new_actions, last_trace_rowid = self._extract_actions_from_trace(
                    oasis_db_path, round_num, platform, profiles, last_trace_rowid,
                )
                for action in new_actions:
                    on_action(action)
                    total_actions += 1

                if on_round_complete:
                    on_round_complete(round_num, total_rounds)
        finally:
            await env.close()

        return {
            "total_rounds": round_num if round_num > 0 else 0,
            "total_actions": total_actions,
        }

    def _bridge_llm_config(self) -> None:
        """Bridge ForkCast LLM settings to camel-ai expected env vars."""
        llm_key = os.environ.get("LLM_API_KEY", "")
        llm_base = os.environ.get("LLM_BASE_URL", "")
        if llm_key:
            os.environ["OPENAI_API_KEY"] = llm_key
        if llm_base:
            os.environ["OPENAI_API_BASE_URL"] = llm_base

    def _create_camel_model(self):
        """Create a camel-ai ModelFactory model from ForkCast config."""
        try:
            from camel.models import ModelFactory
            model_name = os.environ.get("LLM_MODEL_NAME", "")
            if model_name:
                return ModelFactory.create(model_name=model_name)
        except Exception as exc:
            logger.warning("Could not create camel-ai model: %s — using default", exc)
        return None

    def _build_native_actions(self, agent_graph, round_num, config, platform, oasis_module):
        """Build rule-based ManualAction for each agent in native mode."""
        import random
        try:
            from oasis.social_platform.typing import ActionType as OasisActionType
        except ImportError:
            return {}

        actions = {}
        agents = list(agent_graph.get_agents()) if hasattr(agent_graph, 'get_agents') else []

        hour_in_sim = (round_num * config.minutes_per_round / 60) % 24
        if int(hour_in_sim) in config.peak_hours:
            activity_mult = config.peak_multiplier
        elif int(hour_in_sim) in config.off_peak_hours:
            activity_mult = config.off_peak_multiplier
        else:
            activity_mult = 1.0

        for agent in agents:
            agent_id = getattr(agent, 'agent_id', None) or getattr(agent, 'user_id', 0)
            agent_cfg = None
            for ac in config.agent_configs:
                if ac.get("agent_id") == agent_id:
                    agent_cfg = ac
                    break

            activity_level = (agent_cfg or {}).get("activity_level", 0.5)
            if random.random() > activity_level * activity_mult:
                try:
                    actions[agent] = oasis_module.ManualAction(action_type=OasisActionType.DO_NOTHING)
                except Exception:
                    pass
                continue

            post_freq = (agent_cfg or {}).get("post_frequency", 0.4)
            like_freq = (agent_cfg or {}).get("like_frequency", 0.4)

            roll = random.random()
            if roll < post_freq:
                content = random.choice(config.hot_topics or config.seed_posts or [""])
                try:
                    actions[agent] = oasis_module.ManualAction(
                        action_type=OasisActionType.CREATE_POST, action_args={"content": content},
                    )
                except Exception:
                    pass
            elif roll < post_freq + like_freq:
                try:
                    actions[agent] = oasis_module.ManualAction(action_type=OasisActionType.LIKE_POST)
                except Exception:
                    pass
            else:
                content = random.choice(config.hot_topics or ["Interesting!"])
                try:
                    actions[agent] = oasis_module.ManualAction(
                        action_type=OasisActionType.CREATE_COMMENT, action_args={"content": content},
                    )
                except Exception:
                    pass

        return actions

    def _extract_actions_from_trace(self, oasis_db_path, round_num, platform, profiles, last_rowid):
        """Query OASIS SQLite trace table for new actions since last_rowid."""
        actions = []
        new_last_rowid = last_rowid
        try:
            conn = sqlite3.connect(str(oasis_db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT rowid, user_id, action, info, created_at FROM trace WHERE rowid > ? ORDER BY rowid",
                (last_rowid,),
            ).fetchall()
            conn.close()
            for row in rows:
                row_dict = dict(row)
                new_last_rowid = max(new_last_rowid, row_dict["rowid"])
                action = _trace_row_to_action(row_dict, round_num, platform, profiles)
                if action.action_type != ActionType.DO_NOTHING:
                    actions.append(action)
        except Exception as exc:
            logger.warning("Failed to extract actions from OASIS trace: %s", exc)
        return actions, new_last_rowid
