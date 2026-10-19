from uuid import uuid4

import chromadb

from lightrag.chunker import Chunk
from lightrag.vector_store import ChromaStore


def make_store(backend: str = "hnsw") -> ChromaStore:
    return ChromaStore(
        persist_dir=None,
        collection=f"test-{uuid4().hex}",
        query_backend=backend,
        client=chromadb.EphemeralClient(),
    )


def test_upsert_query_and_delete() -> None:
    store = make_store()
    chunks = [
        Chunk("alpha", "data/docs/a.txt", 1, 1, 0, 5),
        Chunk("beta", "data/docs/b.txt", 2, 2, 0, 4),
        Chunk("gamma", "data/docs/c.txt", 3, 1, 0, 5),
    ]
    store.upsert_chunks("DOC1", "Doc One", chunks, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert store.count() == 3
    matches = store.query([0.9, 0.1, 0.0], top_k=2)
    assert [match.text for match in matches] == ["alpha", "beta"]
    assert matches[0].metadata["doc_id"] == "DOC1"
    assert matches[0].metadata["page"] == 1
    store.delete_by_doc("DOC1")
    assert store.count() == 0


def test_bruteforce_backend() -> None:
    store = make_store("brute_force")
    chunks = [
        Chunk("alpha", "data/docs/a.txt", 1, 1, 0, 5),
        Chunk("beta", "data/docs/b.txt", 2, None, 0, 4),
    ]
    store.upsert_chunks("DOC1", "Doc One", chunks, [[1, 0, 0], [0, 1, 0]])
    matches = store.query([0.0, 1.0, 0.0], top_k=1)
    assert matches[0].text == "beta"
    assert matches[0].metadata["page"] == -1


def test_reset_is_idempotent() -> None:
    store = make_store()
    store.upsert_chunks(
        "DOC1",
        "Doc One",
        [Chunk("alpha", "data/docs/a.txt", 1, 1, 0, 5)],
        [[1, 0, 0]],
    )
    assert store.count() == 1
    store.reset()
    assert store.count() == 0
    store.reset()
    assert store.count() == 0
