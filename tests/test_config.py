from pathlib import Path

import pytest

from lightrag.config import ConfigError, load_config

CONFIG = """
paths:
  docs_dir: data/docs
  fixtures_dir: tests/fixtures
  results_dir: tests/results
chunking:
  size: 500
  overlap: 50
embedding:
  base_url: https://example.invalid/v1
  model: text-embedding-v4
  dimensions: 1024
  api_key_env: TEST_DASHSCOPE_KEY
  batch_size: 2
  timeout_seconds: 10
  max_retries: 1
llm:
  base_url: https://example.invalid/v1
  model: qwen-plus
  api_key_env: TEST_DASHSCOPE_KEY
  timeout_seconds: 10
  temperature: 0
  max_tokens: 200
vector_store:
  persist_dir: data/chroma-test
  collection: test-collection
retrieval:
  top_k: 5
  query_backend: hnsw
"""


def test_load_config_paths_and_chunking(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(CONFIG, encoding="utf-8")
    config = load_config(config_file, root=tmp_path, load_env=False)
    assert config.docs_dir == tmp_path / "data/docs"
    assert config.manifest_path == tmp_path / "data/docs/manifest.json"
    assert config.chunking.size == 500
    assert config.chunking.overlap == 50
    assert config.embedding.dimensions == 1024
    assert config.retrieval.top_k == 5


def test_missing_key_is_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(CONFIG, encoding="utf-8")
    monkeypatch.delenv("TEST_DASHSCOPE_KEY", raising=False)
    config = load_config(config_file, root=tmp_path, load_env=False)
    with pytest.raises(ConfigError) as exc_info:
        config.require_api_key()
    assert "TEST_DASHSCOPE_KEY" in str(exc_info.value)


def test_key_from_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("TEST_DASHSCOPE_KEY", "dummy-not-real")
    config = load_config(config_file, root=tmp_path, load_env=False)
    assert config.require_api_key() == "dummy-not-real"
    assert "dummy-not-real" not in repr(config)
