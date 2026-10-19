#!/usr/bin/env python3
"""M2 evidence: real embedding smoke + Chroma query smoke."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import chromadb

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.chunker import Chunk  # noqa: E402
from lightrag.config import load_config  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder  # noqa: E402
from lightrag.vector_store import ChromaStore  # noqa: E402

OUT = REPO_ROOT / "tests" / "results" / "m2-smoke.md"


def main() -> int:
    config = load_config()
    api_key = config.require_api_key()
    embedder = DashScopeEmbedder(config.embedding, api_key)
    vectors = embedder.embed_texts(
        ["X-300 的额定功率是 15 W。", "M4 生命周期测试使用唯一验证码 LIFECYCLE-7788。"]
    )
    assert len(vectors) == 2
    assert all(len(vector) == config.embedding.dimensions for vector in vectors)

    store = ChromaStore(
        persist_dir=None,
        collection=f"smoke-{uuid4().hex}",
        query_backend="hnsw",
        client=chromadb.EphemeralClient(),
    )
    chunks = [
        Chunk("alpha", "data/docs/a.txt", 1, 1, 0, 5),
        Chunk("beta", "data/docs/b.txt", 2, 1, 0, 4),
        Chunk("gamma", "data/docs/c.txt", 3, 1, 0, 5),
    ]
    store.upsert_chunks("SMOKE", "Smoke", chunks, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    matches = store.query([0.9, 0.1, 0.0], top_k=2)
    assert [match.text for match in matches] == ["alpha", "beta"]

    lines = [
        "# M2 真实 Embedding / Chroma 冒烟",
        "",
        "## Embedding",
        "",
        f"- 模型：`{config.embedding.model}`",
        f"- 维度：`{config.embedding.dimensions}`",
        f"- 返回条数：{len(vectors)}",
        f"- 每条维度：{[len(v) for v in vectors]}",
        "- 结论：真实 API 调用成功。",
        "",
        "## Chroma",
        "",
        "- 客户端：`EphemeralClient`（仅冒烟，不写入正式 collection）",
        "- 后端：`hnsw`",
        f"- 写入条数：{store.count()}",
        "- 查询 Top-2：" + ", ".join(f"{m.text} ({m.score:.3f})" for m in matches),
        "- 结论：HNSW query 正常，AVX2 兼容性门禁通过。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
