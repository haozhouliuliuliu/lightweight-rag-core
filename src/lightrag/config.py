"""Configuration loading for the lightweight RAG core.

Rules:
- ``config.yaml`` (local, gitignored) wins over ``config.example.yaml``.
- Secrets are read from environment variables, optionally from a local ``.env``.
- Config objects and error messages never contain the API key value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .chunker import ChunkerConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_FILE = PROJECT_ROOT / "config.example.yaml"
LOCAL_CONFIG_FILE = PROJECT_ROOT / "config.yaml"


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class EmbeddingSettings:
    base_url: str
    model: str
    dimensions: int
    api_key_env: str
    batch_size: int
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    model: str
    api_key_env: str
    timeout_seconds: float
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class RetrievalSettings:
    top_k: int
    answer_top_k: int
    query_backend: str


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    config_path: Path
    docs_dir: Path
    manifest_path: Path
    fixtures_dir: Path
    results_dir: Path
    chroma_dir: Path
    collection: str
    chunking: ChunkerConfig
    embedding: EmbeddingSettings
    llm: LLMSettings
    retrieval: RetrievalSettings

    def require_api_key(self, env_name: str | None = None) -> str:
        name = env_name or self.embedding.api_key_env
        value = os.environ.get(name, "").strip()
        if not value:
            raise ConfigError(
                f"missing API key: set environment variable {name} "
                "(or place it in the gitignored .env file)"
            )
        return value


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"config section {key!r} must be a mapping")
    return value


def load_config(
    path: str | Path | None = None,
    *,
    load_env: bool = True,
    root: Path | None = None,
) -> AppConfig:
    """Load config and optional local .env; never expose secret values."""
    project_root = (root or PROJECT_ROOT).resolve()
    chosen = Path(path) if path else (
        LOCAL_CONFIG_FILE if LOCAL_CONFIG_FILE.exists() else DEFAULT_CONFIG_FILE
    )
    if not chosen.is_absolute():
        chosen = project_root / chosen
    if not chosen.exists():
        raise ConfigError(f"config file not found: {chosen}")

    if load_env:
        load_dotenv(project_root / ".env", override=False)

    try:
        raw = yaml.safe_load(chosen.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML config: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    paths = _section(raw, "paths")
    chunk_data = _section(raw, "chunking")
    embedding = _section(raw, "embedding")
    llm = _section(raw, "llm")
    vector = _section(raw, "vector_store")
    retrieval = _section(raw, "retrieval")

    try:
        chunking = ChunkerConfig.from_mapping(chunk_data)
        embed_settings = EmbeddingSettings(
            base_url=str(embedding.get("base_url", "")).rstrip("/"),
            model=str(embedding.get("model", "text-embedding-v4")),
            dimensions=int(embedding.get("dimensions", 1024)),
            api_key_env=str(embedding.get("api_key_env", "DASHSCOPE_API_KEY")),
            batch_size=int(embedding.get("batch_size", 10)),
            timeout_seconds=float(embedding.get("timeout_seconds", 60)),
            max_retries=int(embedding.get("max_retries", 3)),
        )
        llm_settings = LLMSettings(
            base_url=str(llm.get("base_url", "")).rstrip("/"),
            model=str(llm.get("model", "qwen-plus")),
            api_key_env=str(llm.get("api_key_env", "DASHSCOPE_API_KEY")),
            timeout_seconds=float(llm.get("timeout_seconds", 90)),
            temperature=float(llm.get("temperature", 0)),
            max_tokens=int(llm.get("max_tokens", 1200)),
        )
        retrieval_settings = RetrievalSettings(
            top_k=int(retrieval.get("top_k", 5)),
            answer_top_k=int(retrieval.get("answer_top_k", 10)),
            query_backend=str(retrieval.get("query_backend", "hnsw")).lower(),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid numeric config: {exc}") from exc

    if not embed_settings.base_url:
        raise ConfigError("embedding.base_url is required")
    if not llm_settings.base_url:
        raise ConfigError("llm.base_url is required")
    if embed_settings.dimensions <= 0:
        raise ConfigError("embedding.dimensions must be positive")
    if embed_settings.batch_size <= 0:
        raise ConfigError("embedding.batch_size must be positive")
    if retrieval_settings.top_k <= 0:
        raise ConfigError("retrieval.top_k must be positive")
    if retrieval_settings.answer_top_k < retrieval_settings.top_k:
        raise ConfigError("retrieval.answer_top_k must be >= retrieval.top_k")
    if retrieval_settings.query_backend not in {"auto", "hnsw", "brute_force"}:
        raise ConfigError("retrieval.query_backend must be auto, hnsw, or brute_force")

    docs_dir = _resolve(project_root, paths.get("docs_dir", "data/docs"))
    return AppConfig(
        project_root=project_root,
        config_path=chosen,
        docs_dir=docs_dir,
        manifest_path=docs_dir / "manifest.json",
        fixtures_dir=_resolve(project_root, paths.get("fixtures_dir", "tests/fixtures")),
        results_dir=_resolve(project_root, paths.get("results_dir", "tests/results")),
        chroma_dir=_resolve(project_root, vector.get("persist_dir", "data/chroma")),
        collection=str(vector.get("collection", "lightweight-rag-core")),
        chunking=chunking,
        embedding=embed_settings,
        llm=llm_settings,
        retrieval=retrieval_settings,
    )
