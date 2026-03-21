"""Programmatic evaluation gates (Layer 1).

Each gate function returns a dict with:
- "passed": bool
- "value": the measured value
- "threshold": the threshold used
"""

import json
import re
from typing import Any


def gate_ontology_min_types(ontology: dict[str, Any], threshold: int = 3) -> dict:
    """Check that ontology has at least `threshold` entity types."""
    types = ontology.get("entity_types", [])
    count = len(types)
    return {"passed": count >= threshold, "value": count, "threshold": threshold}


def gate_ontology_valid_json(ontology_json_str: str) -> dict:
    """Check that ontology JSON string parses without error."""
    try:
        json.loads(ontology_json_str)
        return {"passed": True, "value": "valid"}
    except (json.JSONDecodeError, TypeError) as exc:
        return {"passed": False, "value": str(exc)}


def gate_persona_count_matches(personas: list[dict], entity_count: int) -> dict:
    """Check that persona count >= entity count (no dropped entities)."""
    count = len(personas)
    return {"passed": count >= entity_count, "value": count, "threshold": entity_count}


_REQUIRED_FIELDS = {"name", "username", "bio", "persona", "age", "gender", "profession"}


def gate_persona_required_fields(personas: list[dict]) -> dict:
    """Check all personas have required fields."""
    for i, p in enumerate(personas):
        missing = _REQUIRED_FIELDS - set(p.keys())
        if missing:
            return {"passed": False, "value": f"persona {i} missing: {missing}"}
    return {"passed": True, "value": "all fields present"}


def gate_persona_unique_names(personas: list[dict]) -> dict:
    """Check no duplicate names or usernames."""
    names = [p.get("name", "") for p in personas]
    usernames = [p.get("username", "") for p in personas]
    dup_names = len(names) != len(set(names))
    dup_usernames = len(usernames) != len(set(usernames))
    if dup_names or dup_usernames:
        return {"passed": False, "value": f"duplicate names={dup_names}, usernames={dup_usernames}"}
    return {"passed": True, "value": "all unique"}


def gate_sim_min_actions(total_actions: int, agent_count: int, round_count: int, factor: float = 0.5) -> dict:
    """Check total actions >= agents * rounds * factor."""
    threshold = agent_count * round_count * factor
    return {"passed": total_actions >= threshold, "value": total_actions, "threshold": threshold}


def gate_sim_no_empty_rounds(actions_per_round: dict[int, int], total_rounds: int) -> dict:
    """Check every round has at least 1 action."""
    empty = [r for r in range(1, total_rounds + 1) if actions_per_round.get(r, 0) == 0]
    return {"passed": len(empty) == 0, "value": f"empty_rounds={empty}" if empty else "all rounds active"}


def gate_sim_action_diversity(action_types: dict[str, int], threshold: int = 3) -> dict:
    """Check at least `threshold` distinct action types."""
    count = len(action_types)
    return {"passed": count >= threshold, "value": count, "threshold": threshold}


def gate_sim_all_agents_active(agent_actions: dict[int, int], expected_agents: int) -> dict:
    """Check every agent took at least 1 action."""
    active = len(agent_actions)
    return {"passed": active >= expected_agents, "value": active, "threshold": expected_agents}


def gate_sim_has_interactions(action_types: dict[str, int]) -> dict:
    """Check at least 1 comment or like action exists."""
    interaction_types = {"LIKE_POST", "DISLIKE_POST", "CREATE_COMMENT"}
    interaction_count = sum(action_types.get(t, 0) for t in interaction_types)
    return {"passed": interaction_count > 0, "value": interaction_count}


def gate_sim_do_nothing_ratio(action_types: dict[str, int], threshold: float = 0.7) -> dict:
    """Check DO_NOTHING ratio is below threshold."""
    total = sum(action_types.values())
    if total == 0:
        return {"passed": False, "value": "no actions"}
    do_nothing = action_types.get("DO_NOTHING", 0)
    ratio = do_nothing / total
    return {"passed": ratio < threshold, "value": round(ratio, 3), "threshold": threshold}


def gate_report_min_length(report_md: str, threshold: int = 500) -> dict:
    """Check report is at least `threshold` characters."""
    length = len(report_md)
    return {"passed": length >= threshold, "value": length, "threshold": threshold}


def gate_report_has_sections(report_md: str, threshold: int = 3) -> dict:
    """Check report has at least `threshold` ## headings."""
    headings = re.findall(r"^## ", report_md, re.MULTILINE)
    count = len(headings)
    return {"passed": count >= threshold, "value": count, "threshold": threshold}


def gate_report_references_agents(report_md: str, agents: list[str]) -> dict:
    """Check report mentions at least 2 agent names or @handles."""
    text_lower = report_md.lower()
    mentioned = [a for a in agents if a.lower() in text_lower or f"@{a.lower()}" in text_lower]
    return {"passed": len(mentioned) >= 2, "value": len(mentioned), "threshold": 2}


def gate_report_no_template_artifacts(report_md: str) -> dict:
    """Check no Jinja2 {{ }} artifacts or [PLACEHOLDER] text."""
    has_jinja = "{{" in report_md and "}}" in report_md
    has_placeholder = "[PLACEHOLDER]" in report_md.upper()
    if has_jinja or has_placeholder:
        return {"passed": False, "value": f"jinja={has_jinja}, placeholder={has_placeholder}"}
    return {"passed": True, "value": "clean"}


def gate_report_valid_markdown(report_md: str) -> dict:
    """Check no unclosed code fences."""
    fence_count = report_md.count("```")
    if fence_count % 2 != 0:
        return {"passed": False, "value": f"odd fence count: {fence_count}"}
    return {"passed": True, "value": "valid"}
