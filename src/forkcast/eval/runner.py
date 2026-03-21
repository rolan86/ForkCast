"""Evaluation runner — orchestrates gates and judgments over pipeline output."""

import json
import logging
from pathlib import Path
from typing import Any

from forkcast.db.connection import get_db
from forkcast.eval.gates import (
    gate_ontology_min_types,
    gate_ontology_valid_json,
    gate_persona_count_matches,
    gate_persona_required_fields,
    gate_persona_unique_names,
    gate_sim_min_actions,
    gate_sim_no_empty_rounds,
    gate_sim_action_diversity,
    gate_sim_all_agents_active,
    gate_sim_has_interactions,
    gate_sim_do_nothing_ratio,
    gate_report_min_length,
    gate_report_has_sections,
    gate_report_references_agents,
    gate_report_no_template_artifacts,
    gate_report_valid_markdown,
)
from forkcast.eval.judgments import JUDGMENT_NAMES, run_judgment
from forkcast.eval.scorecard import assemble_scorecard, save_scorecard

logger = logging.getLogger(__name__)


def _load_ontology(db_path: Path, project_id: str) -> tuple[dict | None, str]:
    """Load ontology from DB. Returns (parsed_dict, raw_json_str)."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT ontology_json FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    if row is None or row["ontology_json"] is None:
        return None, ""
    raw = row["ontology_json"]
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        return None, raw


def _load_personas(data_dir: Path, simulation_id: str) -> list[dict]:
    """Load personas from agents.json."""
    path = data_dir / simulation_id / "profiles" / "agents.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        return []


def _load_sim_stats(db_path: Path, simulation_id: str) -> dict[str, Any]:
    """Load simulation statistics from DB."""
    with get_db(db_path) as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM simulation_actions WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        total_actions = total_row["cnt"] if total_row else 0

        action_rows = conn.execute(
            "SELECT action_type, COUNT(*) as cnt FROM simulation_actions "
            "WHERE simulation_id = ? GROUP BY action_type",
            (simulation_id,),
        ).fetchall()
        action_types = {row["action_type"]: row["cnt"] for row in action_rows}

        round_rows = conn.execute(
            "SELECT round, COUNT(*) as cnt FROM simulation_actions "
            "WHERE simulation_id = ? GROUP BY round",
            (simulation_id,),
        ).fetchall()
        actions_per_round = {row["round"]: row["cnt"] for row in round_rows}

        max_round_row = conn.execute(
            "SELECT MAX(round) as mr FROM simulation_actions WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        total_rounds = max_round_row["mr"] if max_round_row and max_round_row["mr"] else 0

        agent_rows = conn.execute(
            "SELECT agent_id, COUNT(*) as cnt FROM simulation_actions "
            "WHERE simulation_id = ? GROUP BY agent_id",
            (simulation_id,),
        ).fetchall()
        agent_actions = {row["agent_id"]: row["cnt"] for row in agent_rows}

        agent_count_row = conn.execute(
            "SELECT COUNT(DISTINCT agent_id) as cnt FROM simulation_actions WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        agent_count = agent_count_row["cnt"] if agent_count_row else 0

    return {
        "total_actions": total_actions,
        "action_types": action_types,
        "actions_per_round": actions_per_round,
        "total_rounds": total_rounds,
        "agent_actions": agent_actions,
        "agent_count": agent_count,
    }


def _count_graph_entities(data_dir: Path, project_id: str) -> int:
    """Count entity nodes in the project's graph (inputs to profile generation)."""
    graph_path = data_dir / project_id / "graph.json"
    if not graph_path.exists():
        return 0
    try:
        graph_data = json.loads(graph_path.read_text(encoding="utf-8"))
        return len(graph_data.get("nodes", []))
    except (json.JSONDecodeError, TypeError):
        return 0


def _load_report(db_path: Path, simulation_id: str, report_id: str | None = None) -> tuple[str, str]:
    """Load report markdown and report_id. Uses latest report if report_id not specified."""
    with get_db(db_path) as conn:
        if report_id:
            row = conn.execute(
                "SELECT id, content_markdown FROM reports WHERE id = ?", (report_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, content_markdown FROM reports "
                "WHERE simulation_id = ? ORDER BY created_at DESC LIMIT 1",
                (simulation_id,),
            ).fetchone()
    if row is None:
        return "", ""
    return row["id"], row["content_markdown"] or ""


def _build_judgment_content(
    judgment_name: str,
    ontology: dict | None,
    personas: list[dict],
    sim_stats: dict,
    report_md: str,
    db_path: Path,
    simulation_id: str,
) -> str:
    """Build the content string to pass into a judgment rubric."""
    if judgment_name == "ontology_specificity":
        if ontology:
            types = ontology.get("entity_types", [])
            return json.dumps(types, indent=2)
        return "No ontology data available."

    elif judgment_name in ("persona_distinctiveness", "persona_authenticity"):
        if personas:
            summaries = []
            for p in personas:
                summaries.append(
                    f"**{p.get('name', '?')}** (@{p.get('username', '?')})\n"
                    f"Bio: {p.get('bio', '')}\n"
                    f"Persona: {p.get('persona', '')[:500]}"
                )
            return "\n\n---\n\n".join(summaries)
        return "No persona data available."

    elif judgment_name in ("simulation_in_character", "simulation_interaction_quality"):
        with get_db(db_path) as conn:
            rows = conn.execute(
                "SELECT agent_name, action_type, content, round "
                "FROM simulation_actions WHERE simulation_id = ? "
                "ORDER BY round ASC LIMIT 100",
                (simulation_id,),
            ).fetchall()
        if not rows:
            return "No simulation actions available."
        lines = []
        for r in rows:
            lines.append(f"[Round {r['round']}] {r['agent_name']} — {r['action_type']}: {r['content'][:200] if r['content'] else ''}")
        content = "\n".join(lines)
        if judgment_name == "simulation_in_character" and personas:
            persona_summary = "\n".join(
                f"- {p.get('name', '?')}: {p.get('persona', '')[:200]}" for p in personas
            )
            content = f"## Personas\n{persona_summary}\n\n## Actions\n{content}"
        return content

    elif judgment_name in ("report_specialist_quality", "report_evidence_grounding"):
        return report_md[:5000] if report_md else "No report available."

    return "No content available."


def run_evaluation(
    db_path: Path,
    data_dir: Path,
    project_id: str,
    simulation_id: str,
    report_id: str | None = None,
    client: Any = None,
    skip_judgments: bool = False,
) -> dict[str, Any]:
    """Run full evaluation: gates + optional LLM judgments.

    Args:
        db_path: Path to SQLite database.
        data_dir: Path to data directory.
        project_id: Project ID.
        simulation_id: Simulation ID.
        report_id: Optional report ID (uses latest if not specified).
        client: LLM client for quality judgments. Required unless skip_judgments=True.
        skip_judgments: If True, skip Layer 2 LLM judgments (gates only).

    Returns:
        Complete scorecard dict.
    """
    # --- Load data ---
    ontology, ontology_raw = _load_ontology(db_path, project_id)
    personas = _load_personas(data_dir, simulation_id)
    sim_stats = _load_sim_stats(db_path, simulation_id)
    actual_report_id, report_md = _load_report(db_path, simulation_id, report_id)

    # --- Layer 1: Gates ---
    gates: dict[str, dict] = {}

    # Ontology gates
    gates["ontology.min_entity_types"] = gate_ontology_min_types(ontology or {})
    gates["ontology.valid_json"] = gate_ontology_valid_json(ontology_raw)

    # Persona gates — count entity instances from graph, not ontology types
    entity_count = _count_graph_entities(data_dir, project_id)
    gates["persona.count_matches_ontology"] = gate_persona_count_matches(personas, entity_count)
    gates["persona.required_fields_present"] = gate_persona_required_fields(personas)
    gates["persona.unique_names"] = gate_persona_unique_names(personas)

    # Simulation gates
    gates["simulation.min_actions"] = gate_sim_min_actions(
        sim_stats["total_actions"], sim_stats["agent_count"], sim_stats["total_rounds"]
    )
    gates["simulation.no_empty_rounds"] = gate_sim_no_empty_rounds(
        sim_stats["actions_per_round"], sim_stats["total_rounds"]
    )
    gates["simulation.action_type_diversity"] = gate_sim_action_diversity(sim_stats["action_types"])
    gates["simulation.all_agents_active"] = gate_sim_all_agents_active(
        sim_stats["agent_actions"], sim_stats["agent_count"]
    )
    gates["simulation.has_interactions"] = gate_sim_has_interactions(sim_stats["action_types"])
    gates["simulation.do_nothing_ratio"] = gate_sim_do_nothing_ratio(sim_stats["action_types"])

    # Report gates
    agent_names = [p.get("username", p.get("name", "")) for p in personas]
    gates["report.min_length"] = gate_report_min_length(report_md)
    gates["report.has_sections"] = gate_report_has_sections(report_md)
    gates["report.references_agents"] = gate_report_references_agents(report_md, agent_names)
    gates["report.no_template_artifacts"] = gate_report_no_template_artifacts(report_md)
    gates["report.valid_markdown"] = gate_report_valid_markdown(report_md)

    # --- Layer 2: Quality Judgments ---
    quality: dict[str, dict] = {}

    all_gates_passed = all(g.get("passed") for g in gates.values())

    if not skip_judgments and client is not None and all_gates_passed:
        for judgment_name in JUDGMENT_NAMES:
            content = _build_judgment_content(
                judgment_name, ontology, personas, sim_stats, report_md,
                db_path, simulation_id,
            )
            quality[judgment_name] = run_judgment(client, judgment_name, content)
            logger.info("Judgment %s: %d/5", judgment_name, quality[judgment_name]["score"])
    elif not all_gates_passed:
        logger.info("Skipping quality judgments — %d/%d gates failed",
                     sum(1 for g in gates.values() if not g.get("passed")), len(gates))

    # --- Assemble scorecard ---
    scorecard = assemble_scorecard(
        project_id=project_id,
        simulation_id=simulation_id,
        report_id=actual_report_id or report_id or "",
        gates=gates,
        quality=quality,
    )

    # --- Persist ---
    evals_dir = data_dir / project_id / "evals"
    save_scorecard(scorecard, evals_dir)
    logger.info("Scorecard saved: %s", scorecard["eval_id"])

    return scorecard
