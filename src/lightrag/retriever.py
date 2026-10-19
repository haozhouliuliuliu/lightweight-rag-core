"""Question embedding and Top-K retrieval from Chroma."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .embeddings import DashScopeEmbedder
from .vector_store import ChromaStore, VectorStoreError


class RetrievalError(RuntimeError):
    """Raised when retrieval cannot be completed."""


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    metadata: dict[str, Any]
    score: float | None
    rank: int

    @property
    def doc_title(self) -> str:
        return str(self.metadata.get("doc_title", ""))

    @property
    def source_file(self) -> str:
        return str(self.metadata.get("source_file", ""))

    @property
    def page(self) -> int | None:
        value = self.metadata.get("page", -1)
        try:
            page = int(value)
        except (TypeError, ValueError):
            return None
        return page if page > 0 else None

    @property
    def chunk_id(self) -> int:
        return int(self.metadata.get("chunk_id", 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "text": self.text,
            "metadata": dict(self.metadata),
        }


class Retriever:
    def __init__(self, embedder: DashScopeEmbedder, store: ChromaStore) -> None:
        self.embedder = embedder
        self.store = store

    def retrieve(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not question.strip():
            raise RetrievalError("question must not be empty")
        try:
            vector = self.embedder.embed_query(question)
            matches = self.store.query(vector, top_k=top_k)
        except VectorStoreError:
            raise
        except Exception as exc:
            raise RetrievalError(f"retrieval failed: {type(exc).__name__}: {exc}") from exc
        return [
            RetrievedChunk(
                text=match.text,
                metadata=dict(match.metadata),
                score=match.score,
                rank=index,
            )
            for index, match in enumerate(matches, start=1)
        ]
