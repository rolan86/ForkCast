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
