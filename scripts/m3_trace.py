#!/usr/bin/env python3
"""M3 evidence: one question's retrieval -> context -> answer -> citations trace."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.answer import SYSTEM_PROMPT, QwenAnswerer  # noqa: E402
from lightrag.config import load_config  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder  # noqa: E402
from lightrag.retriever import Retriever  # noqa: E402
from lightrag.vector_store import ChromaStore  # noqa: E402

QUESTION = "X-100S 便携式扭矩校验仪产品说明书中，防护等级和通信方式是什么？"


def main() -> int:
    config = load_config()
    key = config.require_api_key()
    embedder = DashScopeEmbedder(config.embedding, key)
    store = ChromaStore(
        config.chroma_dir,
        config.collection,
        query_backend=config.retrieval.query_backend,
    )
    answerer = QwenAnswerer(config.llm, key, Retriever(embedder, store))
    result = answerer.answer(QUESTION, top_k=config.retrieval.answer_top_k)

    results_dir = config.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "m3-answer-trace.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# M3 检索 → 上下文 → 回答 → 引用 trace",
        "",
        f"**问题**：{QUESTION}",
        "",
        "## 检索结果（Top-5 指标口径）",
        "",
        "| rank | doc_title | chunk_id | page | score |",
        "| ---: | --- | ---: | --- | ---: |",
    ]
    for item in result.retrieved[:5]:
        page = item.page if item.page is not None else "—"
        score = f"{item.score:.4f}" if item.score is not None else "—"
        lines.append(
            f"| {item.rank} | {item.doc_title} | {item.chunk_id} | {page} | {score} |"
        )
    lines += [
        "",
        "## 模型输入（system prompt）",
        "",
        "```text",
        SYSTEM_PROMPT,
        "```",
        "",
        "## 模型输入（检索上下文摘要）",
        "",
        "```text",
        result.context[:2000],
        "```",
        "",
        "## 模型输出",
        "",
        "```text",
        result.answer,
        "```",
        "",
        "## 引用映射",
        "",
        "| marker | doc_title | source_file | chunk_id | page |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    for citation in result.citations:
        page = citation.page if citation.page is not None else "—"
        lines.append(
            f"| {citation.marker} | {citation.doc_title} | `{citation.source_file}` | "
            f"{citation.chunk_id} | {page} |"
        )
    lines += [
        "",
        "## 结论",
        "",
        "- 回答中的 `[n]` 均可映射到本次上下文中的真实 chunk；",
        "- 引用来源可通过 `source_file + chunk_id + page` 回溯；",
        f"- citation_error：`{result.citation_error}`；refused：`{result.refused}`。",
        "",
    ]
    (results_dir / "m3-answer-trace.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
