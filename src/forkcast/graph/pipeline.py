"""Orchestrate the full graph-building pipeline."""

import logging
from pathlib import Path
from typing import Any, Callable

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
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

    # Read domain-specific ontology prompt if available
    ontology_system_prompt = (
        read_prompt(domain, "ontology") if "ontology" in domain.prompts else None
    )

    ontology, ontology_response_tokens = generate_ontology(
        client=client,
        requirement=requirement,
        document_summary=document_summary,
        hints_path=domain.ontology_hints_path,
        system_prompt=ontology_system_prompt,
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
