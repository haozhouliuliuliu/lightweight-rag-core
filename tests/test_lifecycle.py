from pathlib import Path
from uuid import uuid4

import chromadb

from lightrag.config import load_config
from lightrag.documents import DocumentManager
from lightrag.indexer import build_index
from lightrag.vector_store import ChromaStore

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
  dimensions: 4
  api_key_env: TEST_KEY
  batch_size: 10
  timeout_seconds: 5
  max_retries: 1
llm:
  base_url: https://example.invalid/v1
  model: qwen-plus
  api_key_env: TEST_KEY
vector_store:
  persist_dir: data/chroma-test
  collection: test
retrieval:
  top_k: 5
  query_backend: hnsw
"""


class FakeEmbedder:
    def embed_texts(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _setup(tmp_path: Path):
    docs = tmp_path / "data" / "docs"
    docs.mkdir(parents=True)
    (docs / "a.txt").write_text("A 文档内容", encoding="utf-8")
    (docs / "b.txt").write_text("B 文档内容", encoding="utf-8")
    manifest = [
        {"id": "A", "path": "data/docs/a.txt", "title": "Doc A", "format": "txt"},
        {"id": "B", "path": "data/docs/b.txt", "title": "Doc B", "format": "txt"},
    ]
    import json

    (docs / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(CONFIG, encoding="utf-8")
    config = load_config(cfg_file, root=tmp_path, load_env=False)
    store = ChromaStore(
        persist_dir=None,
        collection=f"test-{uuid4().hex}",
        query_backend="hnsw",
        client=chromadb.EphemeralClient(),
    )
    return config, store, docs, manifest


def test_add_index_remove_and_reindex(tmp_path: Path) -> None:
    config, store, docs, _ = _setup(tmp_path)
    manager = DocumentManager(config.docs_dir, config.project_root)
    report = build_index(config, FakeEmbedder(), store)
    assert report.chunks == 2
    assert store.count() == 2

    source = tmp_path / "new.txt"
    source.write_text("新增文档内容", encoding="utf-8")
    entry = manager.add(source, doc_id="NEW", title="New Doc")
    partial = build_index(config, FakeEmbedder(), store, recreate=False, doc_ids=["NEW"])
    assert partial.chunks == 1
    assert store.count() == 3

    manager.remove("NEW")
    store.delete_by_doc("NEW")
    assert store.count() == 2

    # Rebuilding must not duplicate chunks.
    build_index(config, FakeEmbedder(), store)
    build_index(config, FakeEmbedder(), store)
    assert store.count() == 2
