"""Deterministic document chunking for M1.

The splitter is intentionally explicit and independent of any downstream
embedding provider. Chunk size and overlap are supplied by the caller/config;
every chunk carries source_file, chunk_id, page (if available), and a
document-level character interval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .parser import ParsedDocument


@dataclass(frozen=True)
class ChunkerConfig:
    size: int = 500
    overlap: int = 50

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("chunk size must be greater than 0")
        if self.overlap < 0:
            raise ValueError("chunk overlap must be >= 0")
        if self.overlap >= self.size:
            raise ValueError("chunk overlap must be smaller than chunk size")

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> "ChunkerConfig":
        values = values or {}
        return cls(size=int(values.get("size", 500)), overlap=int(values.get("overlap", 50)))

    @property
    def step(self) -> int:
        return self.size - self.overlap


@dataclass(frozen=True)
class Chunk:
    text: str
    source_file: str
    chunk_id: int
    page: int | None
    char_start: int
    char_end: int

    @property
    def char_length(self) -> int:
        return self.char_end - self.char_start

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "metadata": {
                "source_file": self.source_file,
                "chunk_id": self.chunk_id,
                "page": self.page,
                "char_start": self.char_start,
                "char_end": self.char_end,
                "char_length": self.char_length,
            },
        }


def _join_blocks(document: ParsedDocument) -> tuple[str, list[int | None]]:
    """Return full document text and a page number for every character."""
    parts: list[str] = []
    pages: list[int | None] = []
    for index, block in enumerate(document.blocks):
        if index:
            parts.append("\n\n")
            pages.extend([block.page, block.page])
        parts.append(block.text)
        pages.extend([block.page] * len(block.text))
    return "".join(parts), pages


def chunk_document(
    document: ParsedDocument,
    config: ChunkerConfig | None = None,
) -> list[Chunk]:
    """Split a parsed document into chunks.

    A document shorter than ``config.size`` yields exactly one chunk. Chunks
    overlap by ``config.overlap`` characters. ``page`` is the page containing
    the chunk start (or ``None`` for formats without pages).
    """
    cfg = config or ChunkerConfig()
    text, pages = _join_blocks(document)
    if not text:
        return []

    if len(text) <= cfg.size:
        return [
            Chunk(
                text=text,
                source_file=document.source_file,
                chunk_id=1,
                page=pages[0] if pages else None,
                char_start=0,
                char_end=len(text),
            )
        ]

    chunks: list[Chunk] = []
    start = 0
    chunk_id = 1
    while start < len(text):
        end = min(start + cfg.size, len(text))
        chunks.append(
            Chunk(
                text=text[start:end],
                source_file=document.source_file,
                chunk_id=chunk_id,
                page=pages[start] if start < len(pages) else None,
                char_start=start,
                char_end=end,
            )
        )
        if end >= len(text):
            break
        next_start = end - cfg.overlap
        if next_start <= start:
            next_start = start + 1
        start = next_start
        chunk_id += 1
    return chunks


def chunk_documents(
    documents: Iterable[ParsedDocument],
    config: ChunkerConfig | None = None,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, config))
    return chunks
