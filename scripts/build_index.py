#!/usr/bin/env python3
"""Build or refresh the Chroma index from data/docs/manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.config import ConfigError, load_config  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder, EmbeddingError  # noqa: E402
from lightrag.indexer import IndexError, build_index  # noqa: E402
from lightrag.vector_store import ChromaStore, VectorStoreError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--limit", type=int, default=None, help="only index N chunks (smoke)")
    parser.add_argument("--no-recreate", action="store_true", help="append/update instead of reset")
    parser.add_argument("--doc-id", action="append", default=None, help="only refresh given doc id")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        api_key = config.require_api_key()
        embedder = DashScopeEmbedder(config.embedding, api_key)
        store = ChromaStore(
            config.chroma_dir,
            config.collection,
            query_backend=config.retrieval.query_backend,
        )
        if args.doc_id and not args.no_recreate:
            raise IndexError("--doc-id requires --no-recreate to avoid deleting other docs")
        report = build_index(
            config,
            embedder,
            store,
            limit=args.limit,
            recreate=not args.no_recreate,
            doc_ids=args.doc_id,
        )
    except (ConfigError, EmbeddingError, IndexError, VectorStoreError, FileNotFoundError) as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    config.results_dir.mkdir(parents=True, exist_ok=True)
    out = config.results_dir / "m2-index-report.json"
    out.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
