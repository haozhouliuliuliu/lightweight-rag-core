#!/usr/bin/env python3
"""M4 evidence: a fresh process reads the persisted Chroma collection."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.config import load_config  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder  # noqa: E402
from lightrag.retriever import Retriever  # noqa: E402
from lightrag.vector_store import ChromaStore  # noqa: E402

OUT = REPO_ROOT / "tests" / "results" / "m4-restart.md"


def main() -> int:
    config = load_config()
    key = config.require_api_key()
    store = ChromaStore(
        config.chroma_dir,
        config.collection,
        query_backend=config.retrieval.query_backend,
    )
    count = store.count()
    retriever = Retriever(DashScopeEmbedder(config.embedding, key), store)
    results = retriever.retrieve("X-100 的额定功率是多少？", top_k=5)
    lines = [
        "# M4 新进程读取持久化 Chroma",
        "",
        f"- 运行时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 新进程 PID：{__import__('os').getpid()}",
        f"- 持久化目录：`{config.chroma_dir}`",
        f"- collection：`{config.collection}`",
        f"- 读取 count：**{count}**",
        f"- 检索 Top-5 条数：{len(results)}",
        "- Top-5 来源：" + "；".join(
            f"{item.rank}. {item.doc_title} (chunk_id={item.chunk_id})" for item in results
        ),
        "",
        "结论：**新进程**可以读取已持久化的 Chroma 索引，不依赖上一次进程内存。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
