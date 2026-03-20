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
    for word in ["quick", "brown", "fox", "lazy", "dog"]:
        assert any(word in c.text for c in chunks)


def test_chunk_text_overlap():
    """Consecutive chunks should overlap by roughly the specified amount."""
    from forkcast.graph.chunker import chunk_text

    text = "A" * 500
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) >= 2
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
