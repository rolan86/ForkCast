"""LLM quality judgment functions (Layer 2)."""

import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Template

logger = logging.getLogger(__name__)

JUDGMENT_NAMES = [
    "ontology_specificity",
    "persona_distinctiveness",
    "persona_authenticity",
    "simulation_in_character",
    "simulation_interaction_quality",
    "report_specialist_quality",
    "report_evidence_grounding",
]

_RUBRICS_DIR = Path(__file__).parent / "rubrics"


def load_rubric(judgment_name: str) -> str:
    """Load a rubric markdown file by judgment name."""
    path = _RUBRICS_DIR / f"{judgment_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Rubric not found: {path}")
    return path.read_text(encoding="utf-8")


def run_judgment(client: Any, judgment_name: str, content: str) -> dict[str, Any]:
    """Run a single LLM quality judgment. Returns {"score": int, "justification": str}."""
    rubric_template = load_rubric(judgment_name)
    template = Template(rubric_template)
    prompt = template.render(content=content)

    try:
        response = client.complete(
            messages=[{"role": "user", "content": prompt}],
            system="You are an evaluation judge. Rate the content according to the rubric. Return ONLY valid JSON.",
        )
        result = json.loads(response.text)
        score = int(result.get("score", 0))
        justification = str(result.get("justification", ""))
        return {"score": score, "justification": justification}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse judgment response for %s: %s", judgment_name, exc)
        return {"score": 0, "justification": f"Parse error: {exc}"}
    except Exception as exc:
        logger.error("Judgment LLM call failed for %s: %s", judgment_name, exc)
        return {"score": 0, "justification": f"LLM error: {exc}"}
