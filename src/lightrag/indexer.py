"""Build and refresh the Chroma index from the document manifest."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .catalog import DocumentCatalog
from .chunker import chunk_document
from .config import AppConfig
from .embeddings import DashScopeEmbedder
from .parser import DocumentParseError, parse_document
from .vector_store import ChromaStore


class IndexError(RuntimeError):
    """Raised when indexing cannot complete consistently."""


@dataclass
class IndexReport:
    generated_at: str
    model: str
    dimensions: int
    docs: int = 0
    chunks: int = 0
    collection_count: int = 0
    query_backend: str = "hnsw"
    elapsed_seconds: float = 0.0
    documents: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "model": self.model,
            "dimensions": self.dimensions,
            "docs": self.docs,
            "chunks": self.chunks,
            "collection_count": self.collection_count,
            "query_backend": self.query_backend,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "documents": self.documents,
            "errors": self.errors,
        }


def build_index(
    config: AppConfig,
    embedder: DashScopeEmbedder,
    store: ChromaStore,
    *,
    limit: int | None = None,
    recreate: bool = True,
    doc_ids: list[str] | None = None,
) -> IndexReport:
    started = time.perf_counter()
    catalog = DocumentCatalog(config.manifest_path, config.project_root)
    selected = catalog.entries
    if doc_ids:
        wanted = set(doc_ids)
        selected = [entry for entry in selected if entry.get("id") in wanted]
        missing = wanted - {entry.get("id") for entry in selected}
        if missing:
            raise IndexError(f"document id(s) not found: {sorted(missing)}")
    if not selected:
        raise IndexError("no documents selected for indexing")
    if doc_ids and recreate:
        raise IndexError("partial doc_ids cannot be combined with recreate=true")

    if recreate:
        store.reset()
    elif doc_ids:
        for entry in selected:
            store.delete_by_doc(str(entry["id"]))

    report = IndexReport(
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        model=config.embedding.model,
        dimensions=config.embedding.dimensions,
        query_backend=store.backend,
    )
    remaining = limit

    for entry in selected:
        doc_id = str(entry["id"])
        title = str(entry.get("title") or doc_id)
        path = config.project_root / str(entry["path"])
        try:
            parsed = parse_document(path)
            chunks = chunk_document(parsed, config.chunking)
            if not chunks:
                raise IndexError(f"no chunks produced for {doc_id}")
            if remaining is not None:
                chunks = chunks[:remaining]
                remaining -= len(chunks)
            embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
            written = store.upsert_chunks(doc_id, title, chunks, embeddings)
            report.docs += 1
            report.chunks += written
            report.documents.append(
                {
                    "doc_id": doc_id,
                    "title": title,
                    "source_file": parsed.source_file,
                    "chunks": written,
                }
            )
        except (DocumentParseError, Exception) as exc:
            if isinstance(exc, IndexError):
                raise
            report.errors.append(
                {
                    "doc_id": doc_id,
                    "path": str(entry.get("path")),
                    "type": type(exc).__name__,
                    "reason": str(exc),
                }
            )
            raise IndexError(f"indexing failed for {doc_id}: {type(exc).__name__}: {exc}") from exc
        if remaining is not None and remaining <= 0:
            break

    report.collection_count = store.count()
    report.elapsed_seconds = time.perf_counter() - started
    if limit is None and not doc_ids and report.collection_count != report.chunks:
        raise IndexError(
            f"collection count mismatch: expected {report.chunks}, got {report.collection_count}"
        )
    return report
