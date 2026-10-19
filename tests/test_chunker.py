from pathlib import Path

import pytest

from lightrag.chunker import Chunk, ChunkerConfig, chunk_document
from lightrag.parser import ParsedDocument, TextBlock, parse_document

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCX = REPO_ROOT / "data" / "docs" / "product" / "STARLAN-X100-product-manual-v1.2.docx"


def make_document() -> ParsedDocument:
    return ParsedDocument(
        source_file="data/docs/example.txt",
        file_type="txt",
        blocks=[
            TextBlock("a" * 30, "data/docs/example.txt", 0, page=1),
            TextBlock("b" * 30, "data/docs/example.txt", 1, page=2),
        ],
    )


def test_chunk_metadata_and_overlap() -> None:
    document = make_document()
    config = ChunkerConfig(size=20, overlap=5)
    chunks = chunk_document(document, config)
    assert len(chunks) >= 3
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    assert [chunk.chunk_id for chunk in chunks] == list(range(1, len(chunks) + 1))
    assert all(chunk.source_file == document.source_file for chunk in chunks)
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(document.text)
    for chunk in chunks:
        assert chunk.char_end > chunk.char_start
        assert chunk.char_end - chunk.char_start <= config.size
        assert chunk.text == document.text[chunk.char_start : chunk.char_end]
    for previous, current in zip(chunks, chunks[1:]):
        assert current.char_start == previous.char_end - config.overlap


def test_short_document_is_one_chunk() -> None:
    document = ParsedDocument(
        source_file="short.txt",
        file_type="txt",
        blocks=[TextBlock("短文档", "short.txt", 0)],
    )
    chunks = chunk_document(document, ChunkerConfig(size=500, overlap=50))
    assert len(chunks) == 1
    assert chunks[0].chunk_id == 1
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(document.text)


def test_page_is_taken_from_chunk_start() -> None:
    document = make_document()
    chunks = chunk_document(document, ChunkerConfig(size=20, overlap=0))
    # First block starts at 0; the second starts after "a"*30 + "\n\n".
    assert chunks[0].page == 1
    assert any(chunk.page == 2 for chunk in chunks)


def test_invalid_config() -> None:
    with pytest.raises(ValueError):
        ChunkerConfig(size=0, overlap=0)
    with pytest.raises(ValueError):
        ChunkerConfig(size=10, overlap=10)
    with pytest.raises(ValueError):
        ChunkerConfig(size=10, overlap=-1)


def test_real_document_chunks_have_complete_metadata() -> None:
    document = parse_document(DOCX)
    chunks = chunk_document(document, ChunkerConfig(size=500, overlap=50))
    assert len(chunks) >= 2
    for chunk in chunks:
        payload = chunk.to_dict()
        metadata = payload["metadata"]
        assert metadata["source_file"] == document.source_file
        assert metadata["chunk_id"] >= 1
        assert metadata["char_end"] > metadata["char_start"]
        assert metadata["char_length"] == len(payload["text"])
        assert "page" in metadata
