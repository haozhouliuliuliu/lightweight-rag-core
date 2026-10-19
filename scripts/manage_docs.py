#!/usr/bin/env python3
"""Manage local documents and keep the Chroma index in sync."""

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
from lightrag.documents import DocumentManager, DocumentManagerError  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder, EmbeddingError  # noqa: E402
from lightrag.indexer import IndexError, build_index  # noqa: E402
from lightrag.vector_store import ChromaStore, VectorStoreError  # noqa: E402


def _store(config):
    return ChromaStore(
        config.chroma_dir,
        config.collection,
        query_backend=config.retrieval.query_backend,
    )


def _reindex(config, doc_ids=None) -> dict:
    api_key = config.require_api_key()
    embedder = DashScopeEmbedder(config.embedding, api_key)
    store = _store(config)
    report = build_index(
        config,
        embedder,
        store,
        recreate=not doc_ids,
        doc_ids=doc_ids,
    )
    config.results_dir.mkdir(parents=True, exist_ok=True)
    (config.results_dir / "m2-index-report.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("file")
    add.add_argument("--id", default=None)
    add.add_argument("--title", default=None)
    add.add_argument("--category", default="imported")
    add.add_argument("--reindex", action="store_true")

    remove = sub.add_parser("remove")
    remove.add_argument("doc_id")
    remove.add_argument("--yes", action="store_true", help="confirm deletion")
    remove.add_argument("--keep-file", action="store_true")

    sub.add_parser("list")

    reindex = sub.add_parser("reindex")
    reindex.add_argument("--doc-id", action="append", default=None)

    args = parser.parse_args()
    try:
        config = load_config(args.config)
        manager = DocumentManager(config.docs_dir, config.project_root)

        if args.command == "list":
            print(json.dumps(manager.list(), ensure_ascii=False, indent=2))
            return 0

        if args.command == "add":
            entry = manager.add(
                args.file,
                doc_id=args.id,
                title=args.title,
                category=args.category,
            )
            print(f"[ADD] {entry['id']} {entry['path']}")
            if args.reindex:
                report = _reindex(config, [entry["id"]])
                print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        if args.command == "remove":
            if not args.yes:
                print("[FAIL] --yes is required to delete a document", file=sys.stderr)
                return 2
            entry = manager.remove(args.doc_id, delete_file=not args.keep_file)
            try:
                _store(config).delete_by_doc(args.doc_id)
            except VectorStoreError as exc:
                print(f"[WARN] index delete failed: {exc}", file=sys.stderr)
            print(f"[REMOVE] {entry['id']} {entry['path']}")
            return 0

        if args.command == "reindex":
            report = _reindex(config, args.doc_id)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
    except (ConfigError, DocumentManagerError, EmbeddingError, IndexError, VectorStoreError) as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
