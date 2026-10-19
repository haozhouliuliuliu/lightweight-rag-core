from types import SimpleNamespace

from lightrag.retriever import Retriever, RetrievedChunk
from lightrag.vector_store import StoredMatch


class FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeStore:
    def query(self, vector, top_k: int):
        assert vector == [1.0, 0.0]
        return [
            StoredMatch(
                "alpha",
                {
                    "doc_id": "A",
                    "doc_title": "Doc A",
                    "source_file": "data/docs/a.txt",
                    "chunk_id": 1,
                    "page": 1,
                },
                0.1,
                0.9,
            ),
            StoredMatch(
                "beta",
                {
                    "doc_id": "B",
                    "doc_title": "Doc B",
                    "source_file": "data/docs/b.txt",
                    "chunk_id": 2,
                    "page": -1,
                },
                0.3,
                0.7,
            ),
        ][:top_k]


def test_retriever_rank_and_metadata() -> None:
    retriever = Retriever(FakeEmbedder(), FakeStore())
    results = retriever.retrieve("question", top_k=2)
    assert [item.rank for item in results] == [1, 2]
    assert results[0].doc_title == "Doc A"
    assert results[0].page == 1
    assert results[1].page is None
    assert results[0].chunk_id == 1


def test_retriever_rejects_empty_question() -> None:
    retriever = Retriever(FakeEmbedder(), FakeStore())
    try:
        retriever.retrieve("   ")
    except Exception as exc:
        assert type(exc).__name__ == "RetrievalError"
    else:
        raise AssertionError("empty question should fail")
