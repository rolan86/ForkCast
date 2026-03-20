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
