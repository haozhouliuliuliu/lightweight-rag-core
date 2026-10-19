#!/usr/bin/env python3
"""Run the project-one 30-question benchmark against this pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.answer import QwenAnswerer  # noqa: E402
from lightrag.config import ConfigError, load_config  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder, EmbeddingError  # noqa: E402
from lightrag.evaluation import (  # noqa: E402
    EvaluationError,
    evaluate,
    load_questions,
    summarize,
    write_markdown,
)
from lightrag.retriever import Retriever  # noqa: E402
from lightrag.vector_store import ChromaStore, VectorStoreError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="tests/questions.full.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        api_key = config.require_api_key()
        questions = load_questions(args.questions)
        if args.limit:
            questions = questions[: args.limit]
        embedder = DashScopeEmbedder(config.embedding, api_key)
        store = ChromaStore(
            config.chroma_dir,
            config.collection,
            query_backend=config.retrieval.query_backend,
        )
        if store.count() == 0:
            raise EvaluationError("Chroma collection is empty; run scripts/build_index.py first")
        retriever = Retriever(embedder, store)
        answerer = QwenAnswerer(config.llm, api_key, retriever)
        results = evaluate(
            questions,
            retriever,
            answerer,
            top_k=args.top_k or config.retrieval.answer_top_k,
        )
        summary = summarize(results)
    except (
        ConfigError,
        EmbeddingError,
        EvaluationError,
        VectorStoreError,
        FileNotFoundError,
    ) as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir) if args.output_dir else config.results_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"eval-{stamp}.json"
    md_path = output_dir / f"eval-{stamp}.md"
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "questions": str(args.questions),
        "top_k": args.top_k or config.retrieval.top_k,
        "summary": summary,
        "results": [result.to_dict() for result in results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, results, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
