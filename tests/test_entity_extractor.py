from unittest.mock import MagicMock

from forkcast.graph.chunker import TextChunk


def _mock_claude_for_extraction():
    """Create a mock ClaudeClient that returns tool_use extraction results."""
    from forkcast.llm.client import ClaudeClient, LLMResponse

    client = ClaudeClient.__new__(ClaudeClient)
    client.default_model = "claude-sonnet-4-6"
    client._client = MagicMock()

    client.tool_use = MagicMock(return_value=LLMResponse(
        text="",
        tool_calls=[{
            "id": "call_1",
            "name": "extract_entities",
            "input": {
                "entities": [
                    {"name": "Alice", "type": "Person", "description": "A researcher", "attributes": {}},
                    {"name": "TechCorp", "type": "Company", "description": "A tech company", "attributes": {}},
                ],
                "relationships": [
                    {"source": "Alice", "target": "TechCorp", "type": "WORKS_AT", "fact": "Alice works at TechCorp"},
                ],
            },
        }],
        input_tokens=50,
        output_tokens=100,
        model="claude-sonnet-4-6",
        stop_reason="tool_use",
    ))
    return client


def test_extract_from_chunk_returns_entities_and_rels():
    from forkcast.graph.entity_extractor import extract_from_chunk

    client = _mock_claude_for_extraction()
    chunk = TextChunk(text="Alice works at TechCorp.", index=0, source="doc.txt")
    ontology = {"entity_types": [{"name": "Person"}, {"name": "Company"}], "relationship_types": []}

    result = extract_from_chunk(client, chunk, ontology, requirement="Test question")
    assert len(result.entities) == 2
    assert len(result.relationships) == 1
    assert result.entities[0]["name"] == "Alice"


def test_extract_from_chunk_uses_tool_schema():
    from forkcast.graph.entity_extractor import extract_from_chunk

    client = _mock_claude_for_extraction()
    chunk = TextChunk(text="Some text", index=0, source="doc.txt")
    ontology = {"entity_types": [], "relationship_types": []}

    extract_from_chunk(client, chunk, ontology, requirement="Q?")

    call_args = client.tool_use.call_args
    tools = call_args.kwargs.get("tools") or call_args[1].get("tools", [])
    assert any(t["name"] == "extract_entities" for t in tools)


def test_extract_from_chunks_aggregates():
    from forkcast.graph.entity_extractor import extract_from_chunks

    client = _mock_claude_for_extraction()
    chunks = [
        TextChunk(text="Chunk one", index=0, source="doc.txt"),
        TextChunk(text="Chunk two", index=1, source="doc.txt"),
    ]
    ontology = {"entity_types": [], "relationship_types": []}

    result = extract_from_chunks(client, chunks, ontology, requirement="Q?")
    assert len(result.entities) >= 2
    assert len(result.relationships) >= 1


def test_deduplicate_entities():
    from forkcast.graph.entity_extractor import deduplicate_entities

    entities = [
        {"name": "Alice", "type": "Person", "description": "A researcher", "attributes": {}},
        {"name": "Alice", "type": "Person", "description": "Alice the scientist", "attributes": {"field": "AI"}},
        {"name": "Bob", "type": "Person", "description": "An engineer", "attributes": {}},
    ]

    deduped = deduplicate_entities(entities)
    assert len(deduped) == 2
    names = [e["name"] for e in deduped]
    assert "Alice" in names
    assert "Bob" in names
