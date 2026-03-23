"""OASIS simulation engine -- subprocess runner with file-based IPC."""

import csv
import io
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
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


def _monitor_actions_file(
    actions_path: Path,
    platform: str,
    on_action: Callable[[Action], None],
    stop_event: threading.Event,
    poll_interval: float = 0.2,
) -> None:
    """Monitor an actions.jsonl file for new lines, parsing each as an Action.

    Runs until stop_event is set. Used as a background thread.
    Legacy helper kept for the subprocess-based run() method; will be removed
    when run() is rewritten to use the in-process OASIS API.
    """
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
                    oasis_action = raw.get("action", "do_nothing")
                    action_type = _OASIS_ACTION_MAP.get(oasis_action, ActionType.DO_NOTHING)
                    action_args: dict[str, Any] = {}
                    if "content" in raw:
                        action_args["content"] = raw["content"]
                    if "post_id" in raw:
                        action_args["post_id"] = raw["post_id"]
                    action = Action(
                        round=raw.get("round", 0),
                        timestamp=raw.get("timestamp", ""),
                        agent_id=raw.get("agent_id", 0),
                        agent_name=raw.get("agent_name", f"agent{raw.get('agent_id', 0)}"),
                        platform=platform,
                        action_type=action_type,
                        action_args=action_args,
                    )
                    on_action(action)
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Failed to parse OASIS action: %s", exc)
            else:
                time.sleep(poll_interval)


class OasisEngine:
    """Run a simulation using OASIS as a subprocess.

    OASIS manages its own agent state internally. We write profile files,
    launch the subprocess, and monitor its actions.jsonl output file.
    """

    def __init__(self, sim_dir: Path) -> None:
        self.sim_dir = sim_dir
        self._process: subprocess.Popen | None = None
        self._stopped = False

    def stop(self) -> None:
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
        if self._stopped:
            return {"total_rounds": 0, "total_actions": 0}
        self.sim_dir.mkdir(parents=True, exist_ok=True)
        self._stopped = False

        # Write profile files — use platform name in filename for consistency
        if platform == "twitter":
            profiles_filename = "twitter_profiles.csv"
            (self.sim_dir / profiles_filename).write_text(
                _convert_profiles_to_twitter_csv(profiles), encoding="utf-8",
            )
        else:
            profiles_filename = f"{platform}_profiles.json"
            (self.sim_dir / profiles_filename).write_text(
                json.dumps(_convert_profiles_to_reddit_json(profiles), indent=2),
                encoding="utf-8",
            )

        # Write config
        config_path = self.sim_dir / "oasis_config.json"
        config_path.write_text(
            json.dumps(config.to_dict(), indent=2), encoding="utf-8",
        )

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

        cmd = [
            sys.executable, "-m", "oasis.run",
            "--platform", platform,
            "--profiles", str(self.sim_dir / profiles_filename),
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
            logger.error(
                "OASIS (camel-oasis) not installed. "
                "Install with: pip install camel-oasis",
            )
        except Exception as exc:
            logger.error("OASIS subprocess failed: %s", exc)
        finally:
            stop_event.set()
            monitor_thread.join(timeout=5)
            self._process = None

        return {
            "total_rounds": 0,  # OASIS reports its own round count
            "total_actions": action_count[0],
        }
