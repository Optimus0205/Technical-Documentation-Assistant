import pytest

from app.ingest_service import IngestError, _check_public_host, safe_filename, validate_extension
from app.ingestion import chunk_text, clean_markdown, split_by_headers


def test_hash_inside_code_fence_is_not_a_heading():
    text = "# Title\n\nintro\n\n```python\n# not a heading\nx = 1\n```\n\n## Sub\n\nbody"
    sections = split_by_headers(text)
    assert len(sections) == 2
    assert sections[0].metadata == {"h1": "Title"}
    assert "# not a heading" in sections[0].page_content
    assert sections[1].metadata == {"h1": "Title", "h2": "Sub"}


def test_code_indentation_survives_chunking():
    text = (
        "# Models\n\nThis intro is long enough to pass the minimum chunk size filter easily.\n\n"
        "```python\nclass Item(BaseModel):\n    name: str\n    price: float\n```\n"
    )
    chunks = chunk_text(text, source="t.md")
    assert any("    name: str" in c.page_content for c in chunks)


def test_chunk_metadata_and_stable_ids():
    text = "# A\n\n" + "A sentence that makes this chunk long enough to keep. " * 3
    first, second = chunk_text(text, "t.md"), chunk_text(text, "t.md")
    assert first[0].metadata["source"] == "t.md"
    assert first[0].metadata["section"] == "A"
    assert first[0].metadata["chunk_id"] == second[0].metadata["chunk_id"]


def test_clean_markdown_removes_anchors_and_admonitions():
    cleaned = clean_markdown("# Title { #title }\n\n/// note | Hint\nBody text\n///\n")
    assert "{ #" not in cleaned
    assert "///" not in cleaned
    assert "Note: Hint" in cleaned


def test_filenames_cannot_escape_the_data_directory():
    assert safe_filename("../../evil.md") == "evil.md"
    assert safe_filename("..\\..\\evil.md") == "evil.md"


def test_unsupported_extension_is_rejected():
    with pytest.raises(IngestError):
        validate_extension("report.pdf")


def test_private_and_non_http_urls_are_blocked():
    with pytest.raises(IngestError):
        _check_public_host("http://127.0.0.1/admin")
    with pytest.raises(IngestError):
        _check_public_host("file:///etc/passwd")

def test_clean_markdown_strips_terminal_colour_tags():
    cleaned = clean_markdown('$ <font color="#4E9A06">uv run fastapi</font> dev')
    assert "<font" not in cleaned
    assert "uv run fastapi dev" in cleaned