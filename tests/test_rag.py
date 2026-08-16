import pytest

from app.domains.rag.service import chunk_text, validate_collection_name


def test_chunking_returns_complete_small_document() -> None:
    assert chunk_text("hello world", size=500, overlap=50) == ["hello world"]


def test_chunking_splits_large_document() -> None:
    text = "A" * 1000
    chunks = chunk_text(text, size=400, overlap=50)
    assert len(chunks) >= 3
    assert all(chunks)


def test_collection_name_is_restricted() -> None:
    assert validate_collection_name("docs_local-1") == "docs_local-1"
    with pytest.raises(ValueError):
        validate_collection_name("../../etc")
