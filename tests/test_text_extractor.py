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

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
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
