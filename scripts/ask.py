#!/usr/bin/env python3
"""Ask one question through the explicit retrieval -> LLM -> citation chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.answer import AnswerGenerationError, QwenAnswerer  # noqa: E402
from lightrag.config import ConfigError, load_config  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder, EmbeddingError  # noqa: E402
from lightrag.retriever import RetrievalError, Retriever  # noqa: E402
from lightrag.vector_store import ChromaStore, VectorStoreError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?")
    parser.add_argument("--question", dest="question_opt")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    question = (args.question or args.question_opt or "").strip()
    if not question:
        print("[FAIL] question is required", file=sys.stderr)
        return 2

    try:
        config = load_config(args.config)
        api_key = config.require_api_key()
        embedder = DashScopeEmbedder(config.embedding, api_key)
        store = ChromaStore(
            config.chroma_dir,
            config.collection,
            query_backend=config.retrieval.query_backend,
        )
        retriever = Retriever(embedder, store)
        answerer = QwenAnswerer(config.llm, api_key, retriever)
        result = answerer.answer(question, top_k=args.top_k or config.retrieval.answer_top_k)
    except (
        ConfigError,
        EmbeddingError,
        RetrievalError,
        AnswerGenerationError,
        VectorStoreError,
    ) as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(result.answer)
    print("\n引用来源：")
    if not result.citations:
        print("  (无有效引用)")
    for citation in result.citations:
        page = citation.page if citation.page is not None else "-"
        print(f"  [{citation.marker}] {citation.doc_title} | {citation.source_file} | page={page}")
    if result.citation_error:
        print(f"\n[WARN] {result.citation_error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
