"""Scorecard assembly, persistence, and comparison."""

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def assemble_scorecard(
    project_id: str,
    simulation_id: str,
    report_id: str,
    gates: dict[str, dict],
    quality: dict[str, dict],
) -> dict[str, Any]:
    """Assemble a scorecard from gate results and quality judgments."""
    gates_passed = sum(1 for g in gates.values() if g.get("passed"))
    gates_total = len(gates)

    scores = [q["score"] for q in quality.values() if "score" in q]
    quality_avg = round(sum(scores) / len(scores), 2) if scores else 0

    weakest = None
    if scores:
        weakest = min(quality, key=lambda k: quality[k].get("score", 0))

    return {
        "eval_id": f"eval_{secrets.token_hex(6)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "simulation_id": simulation_id,
        "report_id": report_id,
        "gates": gates,
        "quality": quality,
        "summary": {
            "gates_passed": gates_passed,
            "gates_total": gates_total,
            "quality_avg": quality_avg,
            "weakest": weakest,
        },
    }


def save_scorecard(scorecard: dict[str, Any], evals_dir: Path) -> Path:
    """Save scorecard as timestamped JSON file."""
    evals_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{scorecard['eval_id']}.json"
    path = evals_dir / filename
    path.write_text(json.dumps(scorecard, indent=2, default=str), encoding="utf-8")
    return path


def load_scorecard(path: Path) -> dict[str, Any]:
    """Load a scorecard from a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def compare_scorecards(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    """Compare two scorecards, returning quality deltas."""
    quality_changes: dict[str, dict] = {}

    all_keys = set(before.get("quality", {}).keys()) | set(after.get("quality", {}).keys())
    for key in sorted(all_keys):
        before_score = before.get("quality", {}).get(key, {}).get("score", 0)
        after_score = after.get("quality", {}).get(key, {}).get("score", 0)
        quality_changes[key] = {
            "before": before_score,
            "after": after_score,
            "delta": after_score - before_score,
        }

    before_gates = before.get("summary", {}).get("gates_passed", 0)
    after_gates = after.get("summary", {}).get("gates_passed", 0)

    return {
        "gates_before": before_gates,
        "gates_after": after_gates,
        "quality_avg_before": before.get("summary", {}).get("quality_avg", 0),
        "quality_avg_after": after.get("summary", {}).get("quality_avg", 0),
        "quality_changes": quality_changes,
    }
