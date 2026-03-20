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
            boundary = text.rfind(". ", start + chunk_size // 2, end)
            if boundary != -1:
                end = boundary + 2

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
