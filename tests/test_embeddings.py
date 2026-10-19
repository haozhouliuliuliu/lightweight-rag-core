from types import SimpleNamespace

import pytest

from lightrag.config import EmbeddingSettings
from lightrag.embeddings import DashScopeEmbedder, EmbeddingError

SETTINGS = EmbeddingSettings(
    base_url="https://example.invalid/v1",
    model="text-embedding-v4",
    dimensions=4,
    api_key_env="TEST_KEY",
    batch_size=2,
    timeout_seconds=5,
    max_retries=1,
)


class FakeEmbeddings:
    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        batch = kwargs["input"]
        start = sum(len(call["input"]) for call in self.calls[:-1])
        data = [
            SimpleNamespace(embedding=self.vectors[start + index])
            for index in range(len(batch))
        ]
        return SimpleNamespace(data=data)


class FakeClient:
    def __init__(self, vectors):
        self.embeddings = FakeEmbeddings(vectors)


def test_batches_keep_order_and_dimensions() -> None:
    vectors = [[float(i)] * 4 for i in range(5)]
    embedder = DashScopeEmbedder(SETTINGS, "dummy", client=FakeClient(vectors))
    result = embedder.embed_texts(["a", "b", "c", "d", "e"])
    assert result == vectors
    assert [len(call["input"]) for call in embedder.client.embeddings.calls] == [2, 2, 1]
    assert all(call["dimensions"] == 4 for call in embedder.client.embeddings.calls)


def test_dimension_mismatch_raises() -> None:
    client = FakeClient([[0.1, 0.2]])
    embedder = DashScopeEmbedder(SETTINGS, "dummy", client=client)
    with pytest.raises(EmbeddingError, match="dimension mismatch"):
        embedder.embed_texts(["a"])


def test_retries_rate_limit() -> None:
    calls = {"n": 0}

    class RetryClient:
        def __init__(self):
            self.embeddings = self

        def create(self, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                exc = RuntimeError("rate limited")
                exc.status_code = 429
                raise exc
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * 4)])

    embedder = DashScopeEmbedder(
        SETTINGS,
        "dummy",
        client=RetryClient(),
        sleep=lambda _: None,
    )
    assert embedder.embed_texts(["a"]) == [[0.0] * 4]
    assert calls["n"] == 2


def test_empty_input() -> None:
    embedder = DashScopeEmbedder(SETTINGS, "dummy", client=FakeClient([]))
    assert embedder.embed_texts([]) == []
