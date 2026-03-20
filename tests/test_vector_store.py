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
