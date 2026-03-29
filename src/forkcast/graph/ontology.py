"""Generate domain-specific ontology using Claude completions."""

import json
import logging
from pathlib import Path
from typing import Any

from forkcast.db.connection import get_db
from forkcast.llm.client import LLMClient

logger = logging.getLogger(__name__)

_ONTOLOGY_SYSTEM_PROMPT = (
    "You are an expert at designing ontologies for knowledge graph extraction. "
    "Given a prediction question, a document summary, and optional domain hints, "
    "generate a structured ontology with entity types and relationship types. "
    "Return ONLY valid JSON with no markdown formatting."
)

_ONTOLOGY_USER_TEMPLATE = """Generate an ontology for entity extraction.

## Prediction Question
{requirement}

## Document Summary
{document_summary}

{hints_section}

## Required Output Format

Return a JSON object with this structure:
{{
  "entity_types": [
    {{"name": "TypeName", "description": "What this represents", "attributes": ["attr1", "attr2"]}}
  ],
  "relationship_types": [
    {{"name": "RELATION_NAME", "description": "What this relationship means"}}
  ]
}}

Rules:
- Include 4-10 entity types relevant to the scenario
- The last two entity types MUST be "Person" and "Organization" as fallbacks
- Include 6-10 relationship types that capture meaningful connections
- Entity types should represent actors or concepts that could participate in social discourse
"""


def generate_ontology(
    client: LLMClient,
    requirement: str,
    document_summary: str,
    hints_path: Path | None = None,
    system_prompt: str | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Generate an ontology from the prediction question and document summary.

    Args:
        system_prompt: Optional domain-specific system prompt. If None, uses the
            hardcoded default prompt. Domain plugins can customize ontology
            generation by providing their ontology.md content here.

    Returns (ontology_dict, {"input": N, "output": N}).
    """
    hints_section = ""
    if hints_path and hints_path.exists():
        hints_content = hints_path.read_text(encoding="utf-8")
        hints_section = f"## Domain Hints\n{hints_content}"

    user_message = _ONTOLOGY_USER_TEMPLATE.format(
        requirement=requirement,
        document_summary=document_summary,
        hints_section=hints_section,
    )

    response = client.complete(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt or _ONTOLOGY_SYSTEM_PROMPT,
        temperature=0.2,
    )

    # Parse JSON from response, handling markdown fences and extra text
    text = response.text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    # Extract the JSON object even if surrounded by extra text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]

    ontology = json.loads(text)

    # Ensure fallbacks exist
    _ensure_fallbacks(ontology)

    tokens = {"input": response.input_tokens, "output": response.output_tokens}
    return ontology, tokens


def _ensure_fallbacks(ontology: dict[str, Any]) -> None:
    """Ensure Person and Organization entity types are present."""
    existing_names = {et["name"] for et in ontology.get("entity_types", [])}
    if "Person" not in existing_names:
        ontology.setdefault("entity_types", []).append(
            {"name": "Person", "description": "An individual human actor", "attributes": []}
        )
    if "Organization" not in existing_names:
        ontology.setdefault("entity_types", []).append(
            {"name": "Organization", "description": "A company, institution, or group", "attributes": []}
        )


def store_ontology(db_path: Path, project_id: str, ontology: dict[str, Any]) -> None:
    """Store generated ontology in the project record."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE projects SET ontology_json = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(ontology), project_id),
        )
