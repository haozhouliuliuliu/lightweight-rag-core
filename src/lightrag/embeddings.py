"""DashScope OpenAI-compatible embedding client with batching and retries."""

from __future__ import annotations

import math
import time
from typing import Any

from openai import OpenAI

from .config import EmbeddingSettings


class EmbeddingError(RuntimeError):
    """Raised for a missing key, failed request, or bad embedding response."""


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 429} or (isinstance(status, int) and status >= 500):
        return True
    return isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
    }


class DashScopeEmbedder:
    def __init__(
        self,
        settings: EmbeddingSettings,
        api_key: str,
        *,
        client: Any | None = None,
        sleep=time.sleep,
    ) -> None:
        if not api_key:
            raise EmbeddingError("missing embedding API key")
        self.settings = settings
        self._sleep = sleep
        self.client = client or OpenAI(
            api_key=api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.settings.batch_size):
            batch = texts[start : start + self.settings.batch_size]
            vectors.extend(self._request(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        return vectors[0]

    def _request(self, batch: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self.client.embeddings.create(
                    model=self.settings.model,
                    input=batch,
                    dimensions=self.settings.dimensions,
                    encoding_format="float",
                )
                vectors = [list(item.embedding) for item in response.data]
                if len(vectors) != len(batch):
                    raise EmbeddingError(
                        f"embedding count mismatch: sent {len(batch)}, got {len(vectors)}"
                    )
                for vector in vectors:
                    if len(vector) != self.settings.dimensions:
                        raise EmbeddingError(
                            f"embedding dimension mismatch: expected {self.settings.dimensions}, "
                            f"got {len(vector)}"
                        )
                    if any(not math.isfinite(float(value)) for value in vector):
                        raise EmbeddingError("embedding contains non-finite values")
                return vectors
            except EmbeddingError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.max_retries and _retryable(exc):
                    self._sleep(min(2**attempt, 8))
                    continue
                raise EmbeddingError(
                    f"embedding request failed ({type(exc).__name__}): {exc}"
                ) from exc
        raise EmbeddingError(f"embedding request failed: {last_error}")
