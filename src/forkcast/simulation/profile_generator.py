"""Generate agent profiles from knowledge graph entities using Claude extended thinking."""

import json
import logging
from pathlib import Path
from typing import Any, Callable

from jinja2 import Template

from forkcast.llm.client import LLMClient
from forkcast.llm.utils import strip_code_fences
from forkcast.simulation.models import AgentProfile

logger = logging.getLogger(__name__)


def _build_persona_prompt(
    entity: dict[str, Any],
    related_entities: list[str],
    requirement: str,
    persona_template: str,
) -> str:
    """Build the persona generation prompt using the domain template."""
    template = Template(persona_template)
    return template.render(
        entity_name=entity["name"],
        entity_type=entity["type"],
        entity_description=entity.get("description", ""),
        related_entities=", ".join(related_entities) if related_entities else "None",
        requirement=requirement,
    )


def _get_related_entities(entity_name: str, graph_data: dict[str, Any]) -> list[str]:
    """Find entities connected to the given entity in the graph."""
    related = set()
    for edge in graph_data.get("edges", []):
        if edge["source"] == entity_name:
            related.add(edge["target"])
        elif edge["target"] == entity_name:
            related.add(edge["source"])
    return sorted(related)


def load_existing_profiles(profiles_dir: Path) -> set[str]:
    """Load entity_source names from existing agents.json for incremental recovery."""
    agents_path = profiles_dir / "agents.json"
    if not agents_path.exists():
        return set()
    try:
        data = json.loads(agents_path.read_text(encoding="utf-8"))
        return {p["entity_source"] for p in data if "entity_source" in p}
    except (json.JSONDecodeError, KeyError):
        return set()


def generate_profile(
    client: LLMClient,
    entity: dict[str, Any],
    agent_id: int,
    related_entities: list[str],
    requirement: str,
    persona_template: str,
    model: str | None = None,
) -> tuple[AgentProfile, dict[str, int]]:
    """Generate a single agent profile using extended thinking.

    Returns (AgentProfile, {"input": N, "output": N}).
    """
    prompt = _build_persona_prompt(
        entity=entity,
        related_entities=related_entities,
        requirement=requirement,
        persona_template=persona_template,
    )

    system = (
        "You are generating a simulation agent profile. "
        "Think deeply about this entity's background, motivations, and communication style. "
        "Return ONLY valid JSON with keys: name, username, bio, persona, age, gender, "
        "profession, interests (array of strings). "
        "No markdown formatting. No code fences."
    )

    response = client.smart_call(
        model=model or client.default_model,
        messages=[{"role": "user", "content": prompt}],
        system=system,
        thinking_budget=8000,
    )

    data = json.loads(strip_code_fences(response.text))

    profile = AgentProfile(
        agent_id=agent_id,
        name=data.get("name", entity["name"]),
        username=data.get("username", entity["name"].lower().replace(" ", "_")),
        bio=data.get("bio", ""),
        persona=data.get("persona", ""),
        age=data.get("age", 30),
        gender=data.get("gender", "unspecified"),
        profession=data.get("profession", ""),
        interests=data.get("interests", []),
        entity_type=entity["type"],
        entity_source=entity["name"],
    )

    tokens = {"input": response.input_tokens, "output": response.output_tokens}
    return profile, tokens


def generate_profiles(
    client: LLMClient,
    entities: list[dict[str, Any]],
    graph_data: dict[str, Any],
    requirement: str,
    persona_template: str,
    profiles_dir: Path,
    on_progress: Callable[[int, int], None] | None = None,
    model: str | None = None,
) -> tuple[list[AgentProfile], dict[str, int]]:
    """Generate profiles for all entities with incremental saving.

    Supports recovery: loads existing profiles from profiles_dir and skips
    entities that already have profiles (matched by entity_source name).

    Returns (all_profiles, {"input": total_in, "output": total_out}).
    """
    existing_sources = load_existing_profiles(profiles_dir)
    profiles: list[AgentProfile] = []
    total_input = 0
    total_output = 0

    # Reload existing profiles as AgentProfile objects
    agents_path = profiles_dir / "agents.json"
    if agents_path.exists():
        try:
            existing_data = json.loads(agents_path.read_text(encoding="utf-8"))
            for pd in existing_data:
                profiles.append(AgentProfile(**pd))
        except (json.JSONDecodeError, TypeError):
            pass

    for i, entity in enumerate(entities):
        if entity["name"] in existing_sources:
            if on_progress:
                on_progress(i + 1, len(entities))
            continue

        related = _get_related_entities(entity["name"], graph_data)
        agent_id = len(profiles)  # Assign next available ID
        profile, tokens = generate_profile(
            client=client,
            entity=entity,
            agent_id=agent_id,
            related_entities=related,
            requirement=requirement,
            persona_template=persona_template,
            model=model,
        )
        profiles.append(profile)
        total_input += tokens["input"]
        total_output += tokens["output"]

        # Incremental save after each profile
        save_profiles(profiles, profiles_dir)

        if on_progress:
            on_progress(i + 1, len(entities))

    return profiles, {"input": total_input, "output": total_output}


def save_profiles(profiles: list[AgentProfile], profiles_dir: Path) -> Path:
    """Save profiles to agents.json. Creates directory if needed."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / "agents.json"
    data = [p.to_dict() for p in profiles]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
