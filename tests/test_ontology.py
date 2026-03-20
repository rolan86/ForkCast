import json
from unittest.mock import MagicMock


def _mock_claude_for_ontology():
    """Create a mock ClaudeClient that returns a valid ontology JSON."""
    from forkcast.llm.client import ClaudeClient, LLMResponse

    client = ClaudeClient.__new__(ClaudeClient)
    client.default_model = "claude-sonnet-4-6"
    client._client = MagicMock()

    ontology = {
        "entity_types": [
            {"name": "Analyst", "description": "Financial analyst", "attributes": ["firm", "specialty"]},
            {"name": "Company", "description": "Public company", "attributes": ["sector", "market_cap"]},
            {"name": "Person", "description": "Individual", "attributes": []},
            {"name": "Organization", "description": "Institution", "attributes": []},
        ],
        "relationship_types": [
            {"name": "COVERS", "description": "Analyst covers a company"},
            {"name": "WORKS_AT", "description": "Person works at organization"},
        ],
    }

    client.complete = MagicMock(return_value=LLMResponse(
        text=json.dumps(ontology),
        input_tokens=100,
        output_tokens=200,
        model="claude-sonnet-4-6",
    ))
    return client, ontology


def test_generate_ontology_returns_parsed_dict():
    """generate_ontology should return parsed ontology dict and token counts."""
    from forkcast.graph.ontology import generate_ontology

    client, expected = _mock_claude_for_ontology()
    result, tokens = generate_ontology(
        client=client,
        requirement="What will happen to tech stocks?",
        document_summary="Report about tech industry trends.",
        hints_path=None,
    )
    assert "entity_types" in result
    assert "relationship_types" in result
    assert len(result["entity_types"]) >= 2
    assert tokens["input"] > 0
    assert tokens["output"] > 0


def test_generate_ontology_includes_fallbacks():
    """Ontology should always include Person and Organization fallbacks."""
    from forkcast.graph.ontology import generate_ontology

    client, _ = _mock_claude_for_ontology()
    result, _ = generate_ontology(
        client=client,
        requirement="Test question",
        document_summary="Test summary",
        hints_path=None,
    )
    names = [et["name"] for et in result["entity_types"]]
    assert "Person" in names
    assert "Organization" in names


def test_generate_ontology_adds_missing_fallbacks():
    """_ensure_fallbacks should add Person/Organization when LLM omits them."""
    from forkcast.graph.ontology import generate_ontology
    from forkcast.llm.client import ClaudeClient, LLMResponse

    client = ClaudeClient.__new__(ClaudeClient)
    client._client = MagicMock()
    ontology_without_fallbacks = {
        "entity_types": [
            {"name": "Technology", "description": "A technology or tool", "attributes": []},
        ],
        "relationship_types": [
            {"name": "USES", "description": "Uses a technology"},
        ],
    }
    client.complete = MagicMock(return_value=LLMResponse(
        text=json.dumps(ontology_without_fallbacks),
        input_tokens=50,
        output_tokens=100,
        model="claude-sonnet-4-6",
    ))

    result, _ = generate_ontology(
        client=client,
        requirement="Test",
        document_summary="Summary",
        hints_path=None,
    )
    names = [et["name"] for et in result["entity_types"]]
    assert "Technology" in names
    assert "Person" in names
    assert "Organization" in names


def test_generate_ontology_uses_hints(tmp_path):
    """When hints_path is provided, hints should be included in the prompt."""
    from forkcast.graph.ontology import generate_ontology

    hints = tmp_path / "hints.yaml"
    hints.write_text("max_entity_types: 5\nrequired_fallbacks:\n  - Person\n  - Organization\n")

    client, _ = _mock_claude_for_ontology()
    generate_ontology(
        client=client,
        requirement="Test",
        document_summary="Summary",
        hints_path=hints,
    )

    call_args = client.complete.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
    user_msg = messages[0]["content"] if messages else ""
    assert "max_entity_types" in user_msg or "5" in user_msg


def test_generate_ontology_stores_to_project(tmp_db_path):
    """store_ontology should update projects.ontology_json."""
    from forkcast.db.connection import get_db, init_db
    from forkcast.graph.ontology import store_ontology

    init_db(tmp_db_path)
    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('proj_001', '_default', 'Test', 'created', 'Q?', datetime('now'))"
        )

    ontology = {"entity_types": [{"name": "Person"}], "relationship_types": []}
    store_ontology(tmp_db_path, "proj_001", ontology)

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT ontology_json FROM projects WHERE id = 'proj_001'").fetchone()

    stored = json.loads(row["ontology_json"])
    assert stored["entity_types"][0]["name"] == "Person"
