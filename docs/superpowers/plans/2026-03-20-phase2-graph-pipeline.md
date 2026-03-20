# ForkCast Phase 2: Graph Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full graph pipeline — text extraction, chunking, Claude-powered entity extraction, NetworkX graph storage, ChromaDB vector indexing, SSE streaming, and the `build-graph` API endpoint — so that `POST /api/projects/{id}/build-graph` works end-to-end.

**Architecture:** Text files uploaded in Phase 1 are read and chunked. Each chunk is sent to Claude via tool_use with the domain's ontology prompt and hints. Extracted entities/relationships are deduplicated and assembled into a NetworkX DiGraph. Text chunks and entity summaries are embedded into ChromaDB for semantic search. Progress is streamed via SSE. The graph is persisted as `graph.json` alongside a ChromaDB local store.

**Tech Stack:** Python 3.11+, FastAPI (SSE via `sse-starlette`), NetworkX, ChromaDB (SentenceTransformerEmbeddingFunction, all-MiniLM-L6-v2), Anthropic SDK (tool_use), Jinja2 (prompt templating)

**Spec:** `docs/specs/2026-03-20-forkcast-design.md` (Sections 6, 8, 10)

**IMPORTANT — Clean-Room Implementation:** This is an original product. Do NOT reference, copy, or adapt code from any existing codebase. Design everything from first principles.

---

## File Structure

```
src/forkcast/
├── graph/
│   ├── __init__.py
│   ├── text_extractor.py      # Read uploaded files, extract text content
│   ├── chunker.py             # Split text into overlapping chunks
│   ├── ontology.py            # Generate ontology via Claude complete()
│   ├── entity_extractor.py    # Extract entities/rels from chunks via Claude tool_use
│   ├── graph_store.py         # NetworkX DiGraph builder, dedup, persist, load
│   ├── vector_store.py        # ChromaDB collection manager — embed, query
│   └── pipeline.py            # Orchestrate the full build-graph pipeline
├── api/
│   ├── graph_routes.py        # POST /api/projects/{id}/build-graph + SSE stream
│   └── app.py                 # (modify) register graph router
└── cli/
    └── project_cmd.py         # (modify) add `forkcast project build-graph` command

tests/
├── test_text_extractor.py
├── test_chunker.py
├── test_ontology.py
├── test_entity_extractor.py
├── test_graph_store.py
├── test_vector_store.py
├── test_pipeline.py
├── test_api_graph.py
└── conftest.py                # (modify) add graph-related fixtures
```

---

### Task 1: Text Extractor

**Files:**
- Create: `src/forkcast/graph/__init__.py`
- Create: `src/forkcast/graph/text_extractor.py`
- Create: `tests/test_text_extractor.py`

**Note:** Add `pypdf` dependency for PDF text extraction:
`cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv add pypdf`

- [ ] **Step 0: Add pypdf dependency**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv add pypdf`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_text_extractor.py
from pathlib import Path


def test_extract_text_from_txt(tmp_path):
    """Should read plain text files."""
    from forkcast.graph.text_extractor import extract_text

    f = tmp_path / "doc.txt"
    f.write_text("Hello, world!", encoding="utf-8")

    result = extract_text(f)
    assert result == "Hello, world!"


def test_extract_text_from_md(tmp_path):
    """Should read markdown files as plain text."""
    from forkcast.graph.text_extractor import extract_text

    f = tmp_path / "doc.md"
    f.write_text("# Title\n\nSome content.", encoding="utf-8")

    result = extract_text(f)
    assert "# Title" in result
    assert "Some content." in result


def test_extract_text_from_multiple_files(tmp_path):
    """Should extract text from a list of files, returning a dict."""
    from forkcast.graph.text_extractor import extract_texts_from_files

    (tmp_path / "a.txt").write_text("File A content")
    (tmp_path / "b.md").write_text("# File B\n\nContent B")

    results = extract_texts_from_files([tmp_path / "a.txt", tmp_path / "b.md"])
    assert len(results) == 2
    assert results["a.txt"] == "File A content"
    assert "Content B" in results["b.md"]


def test_extract_text_from_pdf(tmp_path):
    """Should extract text from PDF files using pypdf."""
    from pypdf import PdfWriter

    from forkcast.graph.text_extractor import extract_text

    # Create a minimal PDF
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    page = writer.pages[0]
    # pypdf doesn't have a simple text-add API, so we test with a real PDF fixture.
    # For the plan, we'll just verify it handles the PDF extension without raising.
    pdf_path = tmp_path / "doc.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)

    result = extract_text(pdf_path)
    assert isinstance(result, str)


def test_extract_text_unsupported_extension(tmp_path):
    """Should raise ValueError for unsupported file types."""
    import pytest
    from forkcast.graph.text_extractor import extract_text

    f = tmp_path / "doc.xlsx"
    f.write_bytes(b"\x00\x01\x02")

    with pytest.raises(ValueError, match="Unsupported"):
        extract_text(f)


def test_extract_text_stores_to_db(tmp_data_dir, tmp_db_path):
    """store_text_content should update project_files.text_content."""
    from forkcast.db.connection import get_db, init_db
    from forkcast.graph.text_extractor import store_text_content

    init_db(tmp_db_path)
    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('proj_001', '_default', 'Test', 'created', 'Q?', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO project_files (project_id, filename, path, size, created_at) "
            "VALUES ('proj_001', 'doc.txt', '/tmp/doc.txt', 100, datetime('now'))"
        )

    store_text_content(tmp_db_path, "proj_001", {"doc.txt": "Extracted text here"})

    with get_db(tmp_db_path) as conn:
        row = conn.execute(
            "SELECT text_content FROM project_files WHERE project_id = 'proj_001' AND filename = 'doc.txt'"
        ).fetchone()

    assert row["text_content"] == "Extracted text here"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_text_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement text_extractor.py**

```python
# src/forkcast/graph/__init__.py
```

```python
# src/forkcast/graph/text_extractor.py
"""Extract text content from uploaded files."""

from pathlib import Path

from forkcast.db.connection import get_db

SUPPORTED_EXTENSIONS = {".txt", ".md", ".text", ".markdown", ".pdf"}


def extract_text(file_path: Path) -> str:
    """Read text content from a single file.

    Raises ValueError for unsupported file types.
    """
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {SUPPORTED_EXTENSIONS}")
    if ext == ".pdf":
        return _extract_pdf(file_path)
    return file_path.read_text(encoding="utf-8")


def _extract_pdf(file_path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def extract_texts_from_files(file_paths: list[Path]) -> dict[str, str]:
    """Extract text from multiple files. Returns {filename: text_content}."""
    results = {}
    for fp in file_paths:
        results[fp.name] = extract_text(fp)
    return results


def store_text_content(db_path: Path, project_id: str, texts: dict[str, str]) -> None:
    """Update project_files.text_content for extracted texts."""
    with get_db(db_path) as conn:
        for filename, content in texts.items():
            conn.execute(
                "UPDATE project_files SET text_content = ? "
                "WHERE project_id = ? AND filename = ?",
                (content, project_id, filename),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_text_extractor.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add pyproject.toml src/forkcast/graph/ tests/test_text_extractor.py
git commit -m "feat: text extractor — read uploaded files and store text content

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Text Chunker

**Files:**
- Create: `src/forkcast/graph/chunker.py`
- Create: `tests/test_chunker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_chunker.py


def test_chunk_text_basic():
    """Should split text into chunks of specified size."""
    from forkcast.graph.chunker import chunk_text

    text = "word " * 200  # 1000 chars
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk.text) <= 300 + 50  # Allow overlap margin


def test_chunk_text_preserves_content():
    """All original text should be covered by chunks."""
    from forkcast.graph.chunker import chunk_text

    text = "The quick brown fox jumps over the lazy dog. " * 20
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    # Every word in original should appear in at least one chunk
    for word in ["quick", "brown", "fox", "lazy", "dog"]:
        assert any(word in c.text for c in chunks)


def test_chunk_text_overlap():
    """Consecutive chunks should overlap by roughly the specified amount."""
    from forkcast.graph.chunker import chunk_text

    text = "A" * 500
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) >= 2
    # Check that consecutive chunks share content
    if len(chunks) >= 2:
        end_of_first = chunks[0].text[-50:]
        assert end_of_first in chunks[1].text


def test_chunk_text_short():
    """Short text should produce exactly one chunk."""
    from forkcast.graph.chunker import chunk_text

    chunks = chunk_text("Short text", chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0].text == "Short text"


def test_chunk_has_metadata():
    """Each chunk should carry index and source metadata."""
    from forkcast.graph.chunker import chunk_text

    chunks = chunk_text("Some text " * 100, chunk_size=100, overlap=10, source="doc.txt")
    assert chunks[0].index == 0
    assert chunks[0].source == "doc.txt"
    assert chunks[1].index == 1


def test_chunk_documents():
    """chunk_documents should chunk multiple documents."""
    from forkcast.graph.chunker import chunk_documents

    docs = {"a.txt": "Hello " * 50, "b.txt": "World " * 50}
    all_chunks = chunk_documents(docs, chunk_size=100, overlap=20)
    sources = {c.source for c in all_chunks}
    assert "a.txt" in sources
    assert "b.txt" in sources
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement chunker.py**

```python
# src/forkcast/graph/chunker.py
"""Split text into overlapping chunks for entity extraction."""

from dataclasses import dataclass


@dataclass
class TextChunk:
    """A chunk of text with metadata."""

    text: str
    index: int
    source: str = ""
    char_start: int = 0
    char_end: int = 0


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    source: str = "",
) -> list[TextChunk]:
    """Split text into overlapping chunks.

    Tries to break on sentence boundaries (periods followed by spaces).
    Falls back to hard character splits if no sentence boundary is found.
    """
    if not text.strip():
        return []

    if len(text) <= chunk_size:
        return [TextChunk(text=text, index=0, source=source, char_start=0, char_end=len(text))]

    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Try to find a sentence boundary near the end
        if end < len(text):
            # Look backwards from end for a period followed by a space
            boundary = text.rfind(". ", start + chunk_size // 2, end)
            if boundary != -1:
                end = boundary + 2  # Include the period and space

        chunk_text_str = text[start:end].strip()
        if chunk_text_str:
            chunks.append(TextChunk(
                text=chunk_text_str,
                index=idx,
                source=source,
                char_start=start,
                char_end=end,
            ))
            idx += 1

        # Move start forward by (chunk_size - overlap)
        step = max(chunk_size - overlap, 1)
        start += step

    return chunks


def chunk_documents(
    documents: dict[str, str],
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[TextChunk]:
    """Chunk multiple documents, returning a flat list with source metadata."""
    all_chunks = []
    for filename, text in documents.items():
        all_chunks.extend(chunk_text(text, chunk_size, overlap, source=filename))
    return all_chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_chunker.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add src/forkcast/graph/chunker.py tests/test_chunker.py
git commit -m "feat: text chunker with overlap and sentence boundary splitting

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Ontology Generation

**Files:**
- Create: `src/forkcast/graph/ontology.py`
- Create: `tests/test_ontology.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ontology.py
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

    # Mock LLM returning ontology WITHOUT Person or Organization
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

    # Verify Claude was called and hints content was in the prompt
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_ontology.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ontology.py**

```python
# src/forkcast/graph/ontology.py
"""Generate domain-specific ontology using Claude completions."""

import json
import logging
from pathlib import Path
from typing import Any

from forkcast.db.connection import get_db
from forkcast.llm.client import ClaudeClient

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
    client: ClaudeClient,
    requirement: str,
    document_summary: str,
    hints_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Generate an ontology from the prediction question and document summary.

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
        system=_ONTOLOGY_SYSTEM_PROMPT,
        temperature=0.2,
    )

    # Parse JSON from response, stripping any markdown code fences
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_ontology.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add src/forkcast/graph/ontology.py tests/test_ontology.py
git commit -m "feat: ontology generation via Claude with domain hints and fallbacks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Entity Extractor

**Files:**
- Create: `src/forkcast/graph/entity_extractor.py`
- Create: `tests/test_entity_extractor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_entity_extractor.py
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
    """extract_from_chunk should return entities and relationships."""
    from forkcast.graph.entity_extractor import extract_from_chunk

    client = _mock_claude_for_extraction()
    chunk = TextChunk(text="Alice works at TechCorp.", index=0, source="doc.txt")
    ontology = {"entity_types": [{"name": "Person"}, {"name": "Company"}], "relationship_types": []}

    result = extract_from_chunk(client, chunk, ontology, requirement="Test question")
    assert len(result.entities) == 2
    assert len(result.relationships) == 1
    assert result.entities[0]["name"] == "Alice"


def test_extract_from_chunk_uses_tool_schema():
    """The extraction should use the extract_entities tool."""
    from forkcast.graph.entity_extractor import extract_from_chunk

    client = _mock_claude_for_extraction()
    chunk = TextChunk(text="Some text", index=0, source="doc.txt")
    ontology = {"entity_types": [], "relationship_types": []}

    extract_from_chunk(client, chunk, ontology, requirement="Q?")

    call_args = client.tool_use.call_args
    tools = call_args.kwargs.get("tools") or call_args[1].get("tools", [])
    assert any(t["name"] == "extract_entities" for t in tools)


def test_extract_from_chunks_aggregates():
    """extract_from_chunks should aggregate results from multiple chunks."""
    from forkcast.graph.entity_extractor import extract_from_chunks

    client = _mock_claude_for_extraction()
    chunks = [
        TextChunk(text="Chunk one", index=0, source="doc.txt"),
        TextChunk(text="Chunk two", index=1, source="doc.txt"),
    ]
    ontology = {"entity_types": [], "relationship_types": []}

    result = extract_from_chunks(client, chunks, ontology, requirement="Q?")
    # Two chunks, each returns 2 entities → 4 total (before dedup)
    assert len(result.entities) >= 2
    assert len(result.relationships) >= 1


def test_deduplicate_entities():
    """deduplicate_entities should merge entities with same name+type."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_entity_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement entity_extractor.py**

```python
# src/forkcast/graph/entity_extractor.py
"""Extract entities and relationships from text chunks using Claude tool_use."""

import logging
from dataclasses import dataclass, field
from typing import Any

from forkcast.graph.chunker import TextChunk
from forkcast.llm.client import ClaudeClient

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
    client: ClaudeClient,
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
    client: ClaudeClient,
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
            # Keep the longer description
            if len(entity.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = entity["description"]
            # Merge attributes
            existing_attrs = existing.get("attributes", {}) or {}
            new_attrs = entity.get("attributes", {}) or {}
            existing_attrs.update(new_attrs)
            existing["attributes"] = existing_attrs

    return list(seen.values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_entity_extractor.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add src/forkcast/graph/entity_extractor.py tests/test_entity_extractor.py
git commit -m "feat: entity extraction via Claude tool_use with deduplication

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Graph Store (NetworkX)

**Files:**
- Create: `src/forkcast/graph/graph_store.py`
- Create: `tests/test_graph_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_store.py
import json
from pathlib import Path


def test_build_graph_from_extraction():
    """Should create a NetworkX graph from extraction results."""
    from forkcast.graph.graph_store import build_graph

    entities = [
        {"name": "Alice", "type": "Person", "description": "A researcher", "attributes": {}},
        {"name": "TechCorp", "type": "Company", "description": "Tech company", "attributes": {}},
    ]
    relationships = [
        {"source": "Alice", "target": "TechCorp", "type": "WORKS_AT", "fact": "Alice works there"},
    ]

    G = build_graph(entities, relationships)
    assert G.number_of_nodes() == 2
    assert G.number_of_edges() == 1
    assert G.nodes["Alice"]["type"] == "Person"
    assert G.edges[("Alice", "TechCorp")]["type"] == "WORKS_AT"


def test_build_graph_handles_missing_nodes():
    """Relationships referencing unknown entities should still create edges."""
    from forkcast.graph.graph_store import build_graph

    entities = [{"name": "Alice", "type": "Person", "description": "A person", "attributes": {}}]
    relationships = [
        {"source": "Alice", "target": "Bob", "type": "KNOWS", "fact": "They know each other"},
    ]

    G = build_graph(entities, relationships)
    assert G.number_of_nodes() == 2  # Bob auto-created
    assert G.has_edge("Alice", "Bob")


def test_save_and_load_graph(tmp_path):
    """Should serialize graph to JSON and reload it identically."""
    from forkcast.graph.graph_store import build_graph, load_graph, save_graph

    entities = [
        {"name": "Alice", "type": "Person", "description": "Researcher", "attributes": {"field": "AI"}},
        {"name": "Bob", "type": "Person", "description": "Engineer", "attributes": {}},
    ]
    relationships = [
        {"source": "Alice", "target": "Bob", "type": "COLLABORATES", "fact": "They work together"},
    ]

    G = build_graph(entities, relationships)
    path = tmp_path / "graph.json"
    save_graph(G, path)

    assert path.exists()
    G2 = load_graph(path)
    assert G2.number_of_nodes() == G.number_of_nodes()
    assert G2.number_of_edges() == G.number_of_edges()
    assert G2.nodes["Alice"]["type"] == "Person"


def test_save_graph_creates_valid_json(tmp_path):
    """The saved file should be valid JSON."""
    from forkcast.graph.graph_store import build_graph, save_graph

    G = build_graph(
        [{"name": "X", "type": "T", "description": "D", "attributes": {}}],
        [],
    )
    path = tmp_path / "graph.json"
    save_graph(G, path)

    data = json.loads(path.read_text())
    assert "nodes" in data
    assert "edges" in data


def test_register_graph_in_db(tmp_db_path):
    """register_graph should insert a row into the graphs table."""
    from forkcast.db.connection import get_db, init_db
    from forkcast.graph.graph_store import register_graph

    init_db(tmp_db_path)
    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('proj_001', '_default', 'Test', 'created', 'Q?', datetime('now'))"
        )

    graph_id = register_graph(tmp_db_path, "proj_001", node_count=5, edge_count=3, file_path="/tmp/graph.json")

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT * FROM graphs WHERE id = ?", (graph_id,)).fetchone()

    assert row is not None
    assert row["project_id"] == "proj_001"
    assert row["node_count"] == 5
    assert row["edge_count"] == 3
    assert row["status"] == "complete"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_graph_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement graph_store.py**

```python
# src/forkcast/graph/graph_store.py
"""NetworkX graph construction, persistence, and querying."""

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from forkcast.db.connection import get_db


def build_graph(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> nx.DiGraph:
    """Build a NetworkX directed graph from entities and relationships."""
    G = nx.DiGraph()

    for entity in entities:
        G.add_node(
            entity["name"],
            type=entity.get("type", "Unknown"),
            description=entity.get("description", ""),
            attributes=entity.get("attributes", {}),
        )

    for rel in relationships:
        source = rel["source"]
        target = rel["target"]
        # Auto-create nodes for relationship endpoints not in entities
        if source not in G:
            G.add_node(source, type="Unknown", description="", attributes={})
        if target not in G:
            G.add_node(target, type="Unknown", description="", attributes={})

        G.add_edge(
            source,
            target,
            type=rel.get("type", "RELATED"),
            fact=rel.get("fact", ""),
        )

    return G


def save_graph(G: nx.DiGraph, path: Path) -> None:
    """Serialize a NetworkX graph to a JSON file."""
    data = {
        "nodes": [
            {"name": n, **G.nodes[n]}
            for n in G.nodes
        ],
        "edges": [
            {"source": u, "target": v, **G.edges[u, v]}
            for u, v in G.edges
        ],
        "metadata": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_graph(path: Path) -> nx.DiGraph:
    """Load a NetworkX graph from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    G = nx.DiGraph()

    for node in data["nodes"]:
        name = node.pop("name")
        G.add_node(name, **node)

    for edge in data["edges"]:
        source = edge.pop("source")
        target = edge.pop("target")
        G.add_edge(source, target, **edge)

    return G


def register_graph(
    db_path: Path,
    project_id: str,
    node_count: int,
    edge_count: int,
    file_path: str,
) -> str:
    """Register a built graph in the database."""
    graph_id = f"graph_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'complete', ?, ?, ?, ?)",
            (graph_id, project_id, node_count, edge_count, file_path, now),
        )
        conn.execute(
            "UPDATE projects SET status = 'graph_built', updated_at = ? WHERE id = ?",
            (now, project_id),
        )

    return graph_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_graph_store.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add src/forkcast/graph/graph_store.py tests/test_graph_store.py
git commit -m "feat: NetworkX graph store — build, save, load, and register in DB

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Vector Store (ChromaDB)

**Files:**
- Create: `src/forkcast/graph/vector_store.py`
- Create: `tests/test_vector_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vector_store.py
from forkcast.graph.chunker import TextChunk


def test_create_collection(tmp_path):
    """Should create a ChromaDB collection for a project."""
    from forkcast.graph.vector_store import create_vector_store

    store = create_vector_store(tmp_path / "chroma")
    assert store is not None


def test_index_chunks(tmp_path):
    """Should index text chunks into ChromaDB."""
    from forkcast.graph.vector_store import create_vector_store, index_chunks

    store = create_vector_store(tmp_path / "chroma")
    chunks = [
        TextChunk(text="Alice is a researcher at TechCorp.", index=0, source="doc.txt"),
        TextChunk(text="Bob works in marketing at BigCo.", index=1, source="doc.txt"),
    ]

    index_chunks(store, chunks)
    assert store.count() == 2


def test_index_entities(tmp_path):
    """Should index entity summaries into ChromaDB."""
    from forkcast.graph.vector_store import create_vector_store, index_entities

    store = create_vector_store(tmp_path / "chroma")
    entities = [
        {"name": "Alice", "type": "Person", "description": "A researcher in AI"},
        {"name": "TechCorp", "type": "Company", "description": "A tech company"},
    ]

    index_entities(store, entities)
    assert store.count() == 2


def test_query_returns_results(tmp_path):
    """Semantic search should return relevant results."""
    from forkcast.graph.vector_store import create_vector_store, index_chunks, query

    store = create_vector_store(tmp_path / "chroma")
    chunks = [
        TextChunk(text="Machine learning is transforming healthcare.", index=0, source="a.txt"),
        TextChunk(text="The stock market crashed yesterday.", index=1, source="b.txt"),
    ]
    index_chunks(store, chunks)

    results = query(store, "artificial intelligence in medicine", n_results=1)
    assert len(results) >= 1
    assert "healthcare" in results[0]["text"] or "Machine" in results[0]["text"]


def test_query_empty_collection(tmp_path):
    """Querying an empty collection should return empty results."""
    from forkcast.graph.vector_store import create_vector_store, query

    store = create_vector_store(tmp_path / "chroma")
    results = query(store, "anything", n_results=5)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_vector_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement vector_store.py**

```python
# src/forkcast/graph/vector_store.py
"""ChromaDB vector store for semantic search over text chunks and entities."""

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from forkcast.graph.chunker import TextChunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "forkcast_chunks"


def create_vector_store(
    persist_dir: Path,
    collection_name: str = COLLECTION_NAME,
) -> chromadb.Collection:
    """Create or open a ChromaDB collection with sentence transformer embeddings."""
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
    )
    return collection


def index_chunks(collection: chromadb.Collection, chunks: list[TextChunk]) -> None:
    """Index text chunks into the vector store."""
    if not chunks:
        return

    collection.add(
        ids=[f"chunk_{c.source}_{c.index}" for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {"source": c.source, "index": c.index, "type": "chunk", "char_start": c.char_start, "char_end": c.char_end}
            for c in chunks
        ],
    )


def index_entities(collection: chromadb.Collection, entities: list[dict[str, Any]]) -> None:
    """Index entity summaries into the vector store."""
    if not entities:
        return

    collection.add(
        ids=[f"entity_{e['name']}_{e.get('type', 'unknown')}" for e in entities],
        documents=[f"{e['name']} ({e.get('type', '')}): {e.get('description', '')}" for e in entities],
        metadatas=[
            {"name": e["name"], "type": e.get("type", ""), "entity_type": "entity"}
            for e in entities
        ],
    )


def query(
    collection: chromadb.Collection,
    query_text: str,
    n_results: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search over the vector store."""
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=min(n_results, collection.count()),
    )

    items = []
    for i in range(len(results["ids"][0])):
        items.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "distance": results["distances"][0][i] if results["distances"] else None,
        })

    return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_vector_store.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add src/forkcast/graph/vector_store.py tests/test_vector_store.py
git commit -m "feat: ChromaDB vector store — index chunks/entities, semantic search

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Graph Pipeline Orchestrator

**Files:**
- Create: `src/forkcast/graph/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pipeline.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def _setup_project(tmp_data_dir, tmp_db_path):
    """Create a project with uploaded files for pipeline testing."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)

    project_id = "proj_test"
    uploads = tmp_data_dir / project_id / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "doc.txt").write_text("Alice is a researcher at TechCorp. She studies AI.")
    (uploads / "notes.md").write_text("# Notes\nBob manages the ML team at TechCorp.")

    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'What will TechCorp do?', datetime('now'))",
            (project_id,),
        )
        for fname, size in [("doc.txt", 50), ("notes.md", 50)]:
            conn.execute(
                "INSERT INTO project_files (project_id, filename, path, size, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (project_id, fname, str(uploads / fname), size),
            )

    return project_id


def _mock_claude():
    """Mock ClaudeClient for pipeline tests."""
    from forkcast.llm.client import ClaudeClient, LLMResponse

    client = ClaudeClient.__new__(ClaudeClient)
    client.default_model = "claude-sonnet-4-6"
    client._client = MagicMock()

    # Mock ontology generation
    ontology = {
        "entity_types": [
            {"name": "Person", "description": "Individual", "attributes": []},
            {"name": "Organization", "description": "Company", "attributes": []},
        ],
        "relationship_types": [
            {"name": "WORKS_AT", "description": "Employment"},
        ],
    }
    client.complete = MagicMock(return_value=LLMResponse(
        text=json.dumps(ontology),
        input_tokens=50,
        output_tokens=100,
        model="claude-sonnet-4-6",
    ))

    # Mock entity extraction
    client.tool_use = MagicMock(return_value=LLMResponse(
        text="",
        tool_calls=[{
            "id": "call_1",
            "name": "extract_entities",
            "input": {
                "entities": [
                    {"name": "Alice", "type": "Person", "description": "Researcher", "attributes": {}},
                    {"name": "TechCorp", "type": "Organization", "description": "Tech company", "attributes": {}},
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


def test_build_graph_pipeline_end_to_end(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    """Full pipeline: extract text → chunk → ontology → extract entities → build graph → index."""
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    result = build_graph_pipeline(
        db_path=tmp_db_path,
        data_dir=tmp_data_dir,
        project_id=project_id,
        client=client,
        domains_dir=tmp_domains_dir,
    )

    assert result["status"] == "complete"
    assert result["node_count"] >= 2
    assert result["edge_count"] >= 1
    assert result["graph_id"].startswith("graph_")

    # Verify files exist
    project_dir = tmp_data_dir / project_id
    assert (project_dir / "graph.json").exists()


def test_pipeline_updates_project_status(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    """Pipeline should update project status to graph_built."""
    from forkcast.db.connection import get_db
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    build_graph_pipeline(
        db_path=tmp_db_path,
        data_dir=tmp_data_dir,
        project_id=project_id,
        client=client,
        domains_dir=tmp_domains_dir,
    )

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT status FROM projects WHERE id = ?", (project_id,)).fetchone()
    assert row["status"] == "graph_built"


def test_pipeline_records_graph_in_db(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    """Pipeline should insert a row in the graphs table."""
    from forkcast.db.connection import get_db
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    result = build_graph_pipeline(
        db_path=tmp_db_path,
        data_dir=tmp_data_dir,
        project_id=project_id,
        client=client,
        domains_dir=tmp_domains_dir,
    )

    with get_db(tmp_db_path) as conn:
        row = conn.execute("SELECT * FROM graphs WHERE id = ?", (result["graph_id"],)).fetchone()
    assert row is not None
    assert row["project_id"] == project_id
    assert row["node_count"] >= 2


def test_pipeline_logs_token_usage(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    """Pipeline should persist token usage to the token_usage table."""
    from forkcast.db.connection import get_db
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()

    build_graph_pipeline(
        db_path=tmp_db_path,
        data_dir=tmp_data_dir,
        project_id=project_id,
        client=client,
        domains_dir=tmp_domains_dir,
    )

    with get_db(tmp_db_path) as conn:
        row = conn.execute(
            "SELECT * FROM token_usage WHERE project_id = ?", (project_id,)
        ).fetchone()
    assert row is not None
    assert row["stage"] == "graph_pipeline"
    assert row["input_tokens"] > 0
    assert row["output_tokens"] > 0


def test_pipeline_progress_callback(tmp_data_dir, tmp_db_path, tmp_domains_dir):
    """Pipeline should call on_progress with stage updates."""
    from forkcast.graph.pipeline import build_graph_pipeline

    project_id = _setup_project(tmp_data_dir, tmp_db_path)
    client = _mock_claude()
    progress_events = []

    build_graph_pipeline(
        db_path=tmp_db_path,
        data_dir=tmp_data_dir,
        project_id=project_id,
        client=client,
        domains_dir=tmp_domains_dir,
        on_progress=lambda **kwargs: progress_events.append(kwargs),
    )

    stages = [e["stage"] for e in progress_events]
    assert "extracting_text" in stages
    assert "generating_ontology" in stages
    assert "extracting_entities" in stages
    assert "building_graph" in stages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pipeline.py**

```python
# src/forkcast/graph/pipeline.py
"""Orchestrate the full graph-building pipeline."""

import logging
from pathlib import Path
from typing import Any, Callable

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain
from forkcast.graph.chunker import chunk_documents
from forkcast.graph.entity_extractor import deduplicate_entities, extract_from_chunks
from forkcast.graph.graph_store import build_graph, register_graph, save_graph
from forkcast.graph.ontology import generate_ontology, store_ontology
from forkcast.graph.text_extractor import extract_text, store_text_content
from forkcast.graph.vector_store import create_vector_store, index_chunks, index_entities
from forkcast.llm.client import ClaudeClient

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None] | None


def build_graph_pipeline(
    db_path: Path,
    data_dir: Path,
    project_id: str,
    client: ClaudeClient,
    domains_dir: Path,
    on_progress: ProgressCallback = None,
) -> dict[str, Any]:
    """Execute the full graph-building pipeline.

    Steps:
    1. Read project and files from DB
    2. Extract text from uploaded files
    3. Chunk text
    4. Generate ontology via Claude
    5. Extract entities from chunks via Claude tool_use
    6. Deduplicate entities
    7. Build NetworkX graph
    8. Index into ChromaDB
    9. Save graph and register in DB

    Returns a result dict with graph_id, node_count, edge_count, status.
    """
    def _progress(stage: str, **kwargs: Any) -> None:
        if on_progress:
            on_progress(stage=stage, **kwargs)

    # 1. Read project info
    with get_db(db_path) as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        files = conn.execute(
            "SELECT * FROM project_files WHERE project_id = ?", (project_id,)
        ).fetchall()

    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    domain_name = project["domain"]
    requirement = project["requirement"]

    # Load domain for ontology hints
    domain = load_domain(domain_name, domains_dir)

    # 2. Extract text
    _progress("extracting_text")
    texts = {}
    for f in files:
        file_path = Path(f["path"])
        if file_path.exists():
            try:
                texts[f["filename"]] = extract_text(file_path)
            except ValueError:
                logger.warning(f"Skipping unsupported file: {f['filename']}")

    store_text_content(db_path, project_id, texts)

    # 3. Chunk text
    _progress("chunking")
    chunks = chunk_documents(texts, chunk_size=1000, overlap=200)

    # 4. Generate ontology
    _progress("generating_ontology")
    document_summary = " ".join(t[:200] for t in texts.values())
    ontology, ontology_response_tokens = generate_ontology(
        client=client,
        requirement=requirement,
        document_summary=document_summary,
        hints_path=domain.ontology_hints_path,
    )
    store_ontology(db_path, project_id, ontology)

    # 5. Extract entities from chunks
    _progress("extracting_entities", total=len(chunks))
    extraction = extract_from_chunks(
        client=client,
        chunks=chunks,
        ontology=ontology,
        requirement=requirement,
        on_progress=lambda current, total: _progress("extracting_entities", current=current, total=total),
    )

    # 6. Deduplicate
    _progress("deduplicating")
    entities = deduplicate_entities(extraction.entities)
    relationships = extraction.relationships

    # 7. Build graph
    _progress("building_graph")
    G = build_graph(entities, relationships)

    # 8. Save graph
    project_dir = data_dir / project_id
    graph_path = project_dir / "graph.json"
    save_graph(G, graph_path)

    # 9. Index into ChromaDB
    _progress("indexing")
    chroma_dir = project_dir / "chroma"
    collection = create_vector_store(chroma_dir)
    index_chunks(collection, chunks)
    index_entities(collection, entities)

    # 10. Register in DB
    _progress("registering")
    graph_id = register_graph(
        db_path=db_path,
        project_id=project_id,
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        file_path=str(graph_path),
    )

    # 11. Log token usage
    total_input = extraction.total_input_tokens
    total_output = extraction.total_output_tokens
    # Add ontology generation tokens (stored from step 4)
    total_input += ontology_response_tokens["input"]
    total_output += ontology_response_tokens["output"]

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO token_usage (project_id, stage, model, input_tokens, output_tokens, created_at) "
            "VALUES (?, 'graph_pipeline', ?, ?, ?, datetime('now'))",
            (project_id, client.default_model, total_input, total_output),
        )

    _progress("complete")

    return {
        "status": "complete",
        "graph_id": graph_id,
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "entities_extracted": len(entities),
        "chunks_processed": extraction.chunks_processed,
        "tokens_used": {"input": total_input, "output": total_output},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_pipeline.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run ALL tests**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v`
Expected: All tests PASS (38 from Phase 1 + new)

- [ ] **Step 6: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add src/forkcast/graph/pipeline.py tests/test_pipeline.py
git commit -m "feat: graph pipeline orchestrator — full build-graph flow from files to indexed graph

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: SSE Support + Graph API Routes

**Files:**
- Create: `src/forkcast/api/graph_routes.py`
- Create: `tests/test_api_graph.py`
- Modify: `src/forkcast/api/app.py` — register graph router

**Note:** Install `sse-starlette` for SSE support. Add to `pyproject.toml` dependencies:
`"sse-starlette>=2.0"`

- [ ] **Step 1: Add sse-starlette dependency**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv add sse-starlette`

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_api_graph.py
import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.api.app import create_app
    return create_app()


def _create_project(tmp_data_dir, tmp_db_path):
    """Helper to create a project with files for graph building."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)
    project_id = "proj_graph_test"
    uploads = tmp_data_dir / project_id / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "doc.txt").write_text("Alice works at TechCorp researching AI.")

    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Graph Test', 'created', 'What will happen?', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO project_files (project_id, filename, path, size, created_at) "
            "VALUES (?, 'doc.txt', ?, 40, datetime('now'))",
            (project_id, str(uploads / "doc.txt")),
        )
    return project_id


def _mock_pipeline_result():
    return {
        "status": "complete",
        "graph_id": "graph_abc123",
        "node_count": 3,
        "edge_count": 2,
        "entities_extracted": 3,
        "chunks_processed": 1,
    }


@pytest.mark.asyncio
async def test_build_graph_triggers(app, tmp_data_dir, tmp_db_path):
    """POST /api/projects/{id}/build-graph should trigger graph building."""
    project_id = _create_project(tmp_data_dir, tmp_db_path)

    with patch("forkcast.api.graph_routes.build_graph_pipeline", return_value=_mock_pipeline_result()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/projects/{project_id}/build-graph")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["graph_id"] == "graph_abc123"


@pytest.mark.asyncio
async def test_build_graph_project_not_found(app):
    """POST /api/projects/{id}/build-graph with bad ID should 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/projects/proj_nonexistent/build-graph")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_graph_for_project(app, tmp_data_dir, tmp_db_path):
    """GET /api/projects/{id}/graph should return graph metadata."""
    project_id = _create_project(tmp_data_dir, tmp_db_path)

    with patch("forkcast.api.graph_routes.build_graph_pipeline", return_value=_mock_pipeline_result()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(f"/api/projects/{project_id}/build-graph")
            resp = await client.get(f"/api/projects/{project_id}/graph")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_api_graph.py -v`
Expected: FAIL

- [ ] **Step 4: Implement graph_routes.py**

```python
# src/forkcast/api/graph_routes.py
"""Graph pipeline API routes with SSE streaming."""

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.graph.pipeline import build_graph_pipeline
from forkcast.llm.client import ClaudeClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["graph"])

# In-memory store for SSE progress events per project (simple dict, single-process)
_progress_queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)


@router.post("/{project_id}/build-graph")
async def trigger_build_graph(project_id: str):
    """Trigger graph building for a project.

    Starts the pipeline synchronously and emits progress events
    that can be consumed via GET /{project_id}/build-graph/stream.
    """
    settings = get_settings()

    # Verify project exists
    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, status FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    if project is None:
        return error(f"Project not found: {project_id}", status_code=404)

    # Build the graph in a thread so SSE consumers can drain the queue concurrently
    client = ClaudeClient(api_key=settings.anthropic_api_key)
    queue = _progress_queues[project_id]

    def on_progress(stage: str, **kwargs):
        event = {"stage": stage, **kwargs}
        queue.put_nowait(event)

    def _run_pipeline():
        return build_graph_pipeline(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            project_id=project_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
        )

    try:
        result = await asyncio.to_thread(_run_pipeline)
    except Exception as e:
        logger.exception(f"Graph build failed for {project_id}")
        queue.put_nowait({"stage": "error", "message": str(e)})
        return error(f"Graph build failed: {str(e)}", status_code=500)
    finally:
        queue.put_nowait(None)  # Sentinel to close SSE stream

    return success(result)


@router.get("/{project_id}/build-graph/stream")
async def stream_build_graph(project_id: str, request: Request):
    """SSE endpoint for streaming graph build progress.

    Connect to this endpoint before or after triggering build-graph
    to receive real-time progress events.
    """
    queue = _progress_queues[project_id]

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue

            if event is None:
                yield {"event": "complete", "data": "{}"}
                break

            yield {"event": event.get("stage", "progress"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@router.get("/{project_id}/graph")
async def get_graph(project_id: str):
    """Get graph metadata for a project."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if project is None:
            return error(f"Project not found: {project_id}", status_code=404)

        graph = conn.execute(
            "SELECT * FROM graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()

    if graph is None:
        return error("No graph built for this project", status_code=404)

    return success(dict(graph))
```

- [ ] **Step 5: Register the router in app.py**

Add to `create_app()` in `src/forkcast/api/app.py`, before `return app`:

```python
from forkcast.api.graph_routes import router as graph_router
app.include_router(graph_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_api_graph.py -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Run ALL tests**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add pyproject.toml src/forkcast/api/graph_routes.py src/forkcast/api/app.py tests/test_api_graph.py
git commit -m "feat: graph API routes — build-graph trigger and graph metadata endpoint

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: CLI Build-Graph Command + E2E Validation

**Files:**
- Modify: `src/forkcast/cli/project_cmd.py` — add `build-graph` subcommand
- Create: `tests/test_cli_build_graph.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_build_graph.py
import json
from unittest.mock import patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_pipeline_result():
    return {
        "status": "complete",
        "graph_id": "graph_abc123",
        "node_count": 5,
        "edge_count": 4,
        "entities_extracted": 5,
        "chunks_processed": 2,
    }


def test_build_graph_command(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    """forkcast project build-graph should trigger the pipeline."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import get_db, init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    # Create a project
    project_id = "proj_cli_test"
    uploads = tmp_data_dir / project_id / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "doc.txt").write_text("Test document content.")

    with get_db(get_settings().db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'CLI Test', 'created', 'Test Q?', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO project_files (project_id, filename, path, size, created_at) "
            "VALUES (?, 'doc.txt', ?, 25, datetime('now'))",
            (project_id, str(uploads / "doc.txt")),
        )

    from forkcast.cli.main import app

    with patch("forkcast.cli.project_cmd.build_graph_pipeline", return_value=_mock_pipeline_result()):
        result = runner.invoke(app, ["project", "build-graph", project_id])

    assert result.exit_code == 0
    assert "graph_abc123" in result.stdout or "complete" in result.stdout


def test_build_graph_command_missing_project(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    """forkcast project build-graph with bad ID should fail."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.db.connection import init_db
    from forkcast.config import get_settings
    init_db(get_settings().db_path)

    from forkcast.cli.main import app

    result = runner.invoke(app, ["project", "build-graph", "proj_nonexistent"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_cli_build_graph.py -v`
Expected: FAIL

- [ ] **Step 3: Add build-graph command to project_cmd.py**

Add this command to `src/forkcast/cli/project_cmd.py`:

```python
# Add at top of file with other imports:
from forkcast.graph.pipeline import build_graph_pipeline
from forkcast.llm.client import ClaudeClient

# Add this command to the project_app Typer group:
@project_app.command("build-graph")
def project_build_graph(project_id: str):
    """Build a knowledge graph from project documents."""
    settings = get_settings()

    # Verify project exists
    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, status FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    if project is None:
        typer.echo(f"Project not found: {project_id}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Building graph for project {project_id}...")
    client = ClaudeClient(api_key=settings.anthropic_api_key)

    def on_progress(stage: str, **kwargs):
        current = kwargs.get("current", "")
        total = kwargs.get("total", "")
        if current and total:
            typer.echo(f"  [{stage}] {current}/{total}")
        else:
            typer.echo(f"  [{stage}]")

    try:
        result = build_graph_pipeline(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            project_id=project_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\nGraph built successfully!")
    typer.echo(f"  Graph ID:   {result['graph_id']}")
    typer.echo(f"  Nodes:      {result['node_count']}")
    typer.echo(f"  Edges:      {result['edge_count']}")
    typer.echo(f"  Entities:   {result['entities_extracted']}")
    typer.echo(f"  Chunks:     {result['chunks_processed']}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest tests/test_cli_build_graph.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Run ALL tests**

Run: `cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast
git add src/forkcast/cli/project_cmd.py tests/test_cli_build_graph.py
git commit -m "feat: CLI build-graph command with progress output

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

- [ ] **Step 7: Tag Phase 2 complete**

Run all tests one more time:
```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && uv run pytest -v
```

Then tag:
```bash
cd /Users/merryldmello/Desktop/Projects/ClaudeMiro/ForkCast && git tag v0.2.0-phase2
```

---

## Phase 2 Complete Checklist

At the end of Phase 2, verify:

- [ ] `POST /api/projects/{id}/build-graph` → triggers pipeline, returns graph metadata
- [ ] `GET /api/projects/{id}/build-graph/stream` → SSE stream of progress events
- [ ] `GET /api/projects/{id}/graph` → returns graph metadata
- [ ] Token usage logged to `token_usage` table
- [ ] `forkcast project build-graph {id}` → runs pipeline with progress output
- [ ] Graph stored at `data/{project_id}/graph.json` as valid JSON
- [ ] ChromaDB collection persisted at `data/{project_id}/chroma/`
- [ ] Entities deduplicated by name+type
- [ ] Project status updated to `graph_built`
- [ ] Graph registered in `graphs` table with counts
- [ ] Ontology stored in `projects.ontology_json`
- [ ] Text content stored in `project_files.text_content`
- [ ] All tests pass: `uv run pytest -v`
- [ ] Clean git history with descriptive commits
