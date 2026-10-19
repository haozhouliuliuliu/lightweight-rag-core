"""lightweight-rag-core: explicit Python RAG pipeline (M1: parse + chunk)."""

from .chunker import Chunk, ChunkerConfig, chunk_document, chunk_documents
from .parser import (
    DocumentParseError,
    ParsedDocument,
    TextBlock,
    find_supported_documents,
    parse_document,
)

__all__ = [
    "Chunk",
    "ChunkerConfig",
    "DocumentParseError",
    "ParsedDocument",
    "TextBlock",
    "chunk_document",
    "chunk_documents",
    "find_supported_documents",
    "parse_document",
]
