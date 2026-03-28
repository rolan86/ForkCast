"""Extract entities and relationships from text chunks using Claude tool_use."""

import logging
from dataclasses import dataclass, field
from typing import Any

from forkcast.graph.chunker import TextChunk
from forkcast.llm.client import LLMClient

logger = logging.getLogger(__name__)

EXTRACT_ENTITIES_TOOL = {
    "name": "extract_entities",
    "description": "Extract entities and relationships from text based on the provided ontology",
    "input_schema": {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "attributes": {"type": "object"},
                    },
                    "required": ["name", "type", "description"],
                },
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "type": {"type": "string"},
                        "fact": {"type": "string"},
                    },
                    "required": ["source", "target", "type"],
                },
            },
        },
        "required": ["entities", "relationships"],
    },
}

_EXTRACTION_SYSTEM_PROMPT = (
    "You are an expert at extracting structured entities and relationships from text. "
    "Use the extract_entities tool to return your findings. "
    "Only extract entities and relationships that are explicitly mentioned or strongly implied in the text."
)


@dataclass
class ExtractionResult:
    """Aggregated extraction results from one or more chunks."""

    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    chunks_processed: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


def extract_from_chunk(
    client: LLMClient,
    chunk: TextChunk,
    ontology: dict[str, Any],
    requirement: str,
) -> ExtractionResult:
    """Extract entities and relationships from a single text chunk."""
    entity_types_desc = "\n".join(
        f"- {et['name']}: {et.get('description', '')}"
        for et in ontology.get("entity_types", [])
    )
    rel_types_desc = "\n".join(
        f"- {rt['name']}: {rt.get('description', '')}"
        for rt in ontology.get("relationship_types", [])
    )

    user_message = (
        f"Extract entities and relationships from this text.\n\n"
        f"## Prediction Question\n{requirement}\n\n"
        f"## Entity Types to Look For\n{entity_types_desc}\n\n"
        f"## Relationship Types to Look For\n{rel_types_desc}\n\n"
        f"## Text (from {chunk.source}, chunk {chunk.index})\n{chunk.text}"
    )

    response = client.tool_use(
        messages=[{"role": "user", "content": user_message}],
        system=_EXTRACTION_SYSTEM_PROMPT,
        tools=[EXTRACT_ENTITIES_TOOL],
    )

    entities = []
    relationships = []
    for tc in response.tool_calls:
        if tc["name"] == "extract_entities":
            entities.extend(tc["input"].get("entities", []))
            relationships.extend(tc["input"].get("relationships", []))

    return ExtractionResult(
        entities=entities,
        relationships=relationships,
        chunks_processed=1,
        total_input_tokens=response.input_tokens,
        total_output_tokens=response.output_tokens,
    )


def extract_from_chunks(
    client: LLMClient,
    chunks: list[TextChunk],
    ontology: dict[str, Any],
    requirement: str,
    on_progress: Any = None,
) -> ExtractionResult:
    """Extract entities and relationships from all chunks, aggregating results."""
    aggregated = ExtractionResult()

    for i, chunk in enumerate(chunks):
        result = extract_from_chunk(client, chunk, ontology, requirement)
        aggregated.entities.extend(result.entities)
        aggregated.relationships.extend(result.relationships)
        aggregated.chunks_processed += 1
        aggregated.total_input_tokens += result.total_input_tokens
        aggregated.total_output_tokens += result.total_output_tokens

        if on_progress:
            on_progress(current=i + 1, total=len(chunks))

    return aggregated


def deduplicate_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge entities with the same name and type, keeping the richest description."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for entity in entities:
        key = (entity["name"].strip().lower(), entity.get("type", "").strip().lower())
        if key not in seen:
            seen[key] = entity.copy()
        else:
            existing = seen[key]
            if len(entity.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = entity["description"]
            existing_attrs = existing.get("attributes", {}) or {}
            new_attrs = entity.get("attributes", {}) or {}
            existing_attrs.update(new_attrs)
            existing["attributes"] = existing_attrs

    return list(seen.values())
