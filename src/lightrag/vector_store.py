"""Chroma persistence with a cosine fallback for non-AVX2 CPUs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import chromadb
import numpy as np
from chromadb.config import Settings

from .chunker import Chunk


class VectorStoreError(RuntimeError):
    """Raised when Chroma cannot complete an operation."""


@dataclass(frozen=True)
class StoredMatch:
    text: str
    metadata: dict[str, Any]
    distance: float | None
    score: float | None


def _metadata_for(doc_id: str, doc_title: str, chunk: Chunk) -> dict[str, Any]:
    page = chunk.page if chunk.page is not None else -1
    return {
        "doc_id": str(doc_id),
        "doc_title": str(doc_title),
        "source_file": chunk.source_file,
        "chunk_id": int(chunk.chunk_id),
        "page": int(page),
        "char_start": int(chunk.char_start),
        "char_end": int(chunk.char_end),
        "format": str(Path(chunk.source_file).suffix.lower().lstrip(".")),
    }


class ChromaStore:
    def __init__(
        self,
        persist_dir: str | Path | None,
        collection: str,
        *,
        query_backend: str = "hnsw",
        client: Any | None = None,
    ) -> None:
        self.backend = "brute_force" if query_backend == "brute_force" else "hnsw"
        if client is not None:
            self.client = client
        else:
            if persist_dir is None:
                raise VectorStoreError("persist_dir is required when client is not injected")
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
        self.collection_name = collection
        self.collection = self._get_or_create()

    def _get_or_create(self):
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return int(self.collection.count())

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self._get_or_create()

    def upsert_chunks(
        self,
        doc_id: str,
        doc_title: str,
        chunks: Iterable[Chunk],
        embeddings: Iterable[Iterable[float]],
    ) -> int:
        chunk_list = list(chunks)
        vector_list = [list(vector) for vector in embeddings]
        if len(chunk_list) != len(vector_list):
            raise VectorStoreError(
                f"chunk/embedding count mismatch: {len(chunk_list)} vs {len(vector_list)}"
            )
        if not chunk_list:
            return 0
        ids = [f"{doc_id}:{chunk.chunk_id}" for chunk in chunk_list]
        metadatas = [_metadata_for(doc_id, doc_title, chunk) for chunk in chunk_list]
        self.collection.upsert(
            ids=ids,
            embeddings=vector_list,  # type: ignore[arg-type]
            documents=[chunk.text for chunk in chunk_list],
            metadatas=metadatas,
        )
        return len(ids)

    def delete_by_doc(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": str(doc_id)})

    def get_by_doc(self, doc_id: str) -> list[StoredMatch]:
        try:
            data = self.collection.get(
                where={"doc_id": str(doc_id)},
                include=["documents", "metadatas"],
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Chroma get_by_doc failed: {type(exc).__name__}: {exc}"
            ) from exc
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        matches = [
            StoredMatch(str(text), dict(metadata or {}), distance=None, score=None)
            for text, metadata in zip(documents, metadatas)
        ]
        return sorted(matches, key=lambda item: int(item.metadata.get("chunk_id", 0)))

    def query(self, query_embedding: Iterable[float], top_k: int = 5) -> list[StoredMatch]:
        if top_k <= 0:
            return []
        vector = [float(value) for value in query_embedding]
        if self.count() == 0:
            return []
        if self.backend == "brute_force":
            return self._query_bruteforce(vector, top_k)
        try:
            result = self.collection.query(
                query_embeddings=[vector],
                n_results=min(top_k, self.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Chroma HNSW query failed: {type(exc).__name__}: {exc}; "
                "set retrieval.query_backend: brute_force in local config after smoke test"
            ) from exc
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        matches: list[StoredMatch] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            distance_value = float(distance) if distance is not None else None
            score = 1.0 - distance_value if distance_value is not None else None
            matches.append(StoredMatch(str(text), dict(metadata or {}), distance_value, score))
        return matches

    def _query_bruteforce(self, vector: list[float], top_k: int) -> list[StoredMatch]:
        try:
            data = self.collection.get(include=["documents", "metadatas", "embeddings"])
        except Exception as exc:
            raise VectorStoreError(
                f"Chroma brute-force read failed: {type(exc).__name__}: {exc}"
            ) from exc
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        embeddings = data.get("embeddings")
        if embeddings is None:
            raise VectorStoreError("Chroma did not return embeddings for brute-force query")
        matrix = np.asarray(embeddings, dtype=np.float32)
        query = np.asarray(vector, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] != query.shape[0]:
            raise VectorStoreError(
                f"brute-force shape mismatch: embeddings={matrix.shape}, query={query.shape}"
            )
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
        norms[norms == 0] = 1.0
        similarities = (matrix @ query) / norms
        order = np.argsort(-similarities)[:top_k]
        matches: list[StoredMatch] = []
        for index in order:
            metadata = dict(metadatas[int(index)] or {})
            matches.append(
                StoredMatch(
                    str(documents[int(index)]),
                    metadata,
                    distance=float(1.0 - similarities[int(index)]),
                    score=float(similarities[int(index)]),
                )
            )
        return matches
