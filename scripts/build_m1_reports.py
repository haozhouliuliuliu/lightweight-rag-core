#!/usr/bin/env python3
"""Parse and chunk every document under data/docs and write M1 evidence."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.chunker import ChunkerConfig, chunk_document  # noqa: E402
from lightrag.parser import (  # noqa: E402
    DocumentParseError,
    find_supported_documents,
    parse_document,
)

DOCS_DIR = REPO_ROOT / "data" / "docs"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
CONFIG_FILE = REPO_ROOT / "config.example.yaml"


def load_chunker_config() -> ChunkerConfig:
    if not CONFIG_FILE.exists():
        return ChunkerConfig()
    data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    return ChunkerConfig.from_mapping(data.get("chunking"))


def main() -> int:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    config = load_chunker_config()
    paths = find_supported_documents(DOCS_DIR)
    documents: list[dict] = []
    all_chunks = []

    for path in paths:
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            parsed = parse_document(path)
            chunks = chunk_document(parsed, config)
            item = {
                "source_file": parsed.source_file,
                "format": parsed.file_type,
                "blocks": len(parsed.blocks),
                "characters": parsed.char_count,
                "chunks": len(chunks),
                "page_count": parsed.metadata.get("page_count"),
                "error": None,
            }
            all_chunks.extend(chunk.to_dict() for chunk in chunks)
            print(f"[OK] {rel} format={parsed.file_type} blocks={len(parsed.blocks)} chunks={len(chunks)}")
        except DocumentParseError as exc:
            item = {
                "source_file": rel,
                "format": path.suffix.lower().lstrip("."),
                "blocks": 0,
                "characters": 0,
                "chunks": 0,
                "page_count": None,
                "error": exc.to_dict(),
            }
            print(f"[ERROR] {rel}: {exc.error_type}: {exc.reason}")
        except Exception as exc:  # never silently skip
            item = {
                "source_file": rel,
                "format": path.suffix.lower().lstrip("."),
                "blocks": 0,
                "characters": 0,
                "chunks": 0,
                "page_count": None,
                "error": {
                    "type": "unexpected_error",
                    "file": path.name,
                    "source_file": rel,
                    "reason": str(exc),
                    "details": {"exception": type(exc).__name__},
                },
            }
            print(f"[ERROR] {rel}: unexpected_error: {exc}")
        documents.append(item)

    formats = Counter(item["format"] for item in documents)
    errors = [item for item in documents if item["error"]]
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "docs_dir": DOCS_DIR.relative_to(REPO_ROOT).as_posix(),
        "chunking": {"size": config.size, "overlap": config.overlap},
        "summary": {
            "documents": len(documents),
            "parsed": len(documents) - len(errors),
            "errors": len(errors),
            "blocks": sum(item["blocks"] for item in documents),
            "chunks": len(all_chunks),
            "formats": dict(sorted(formats.items())),
        },
        "documents": documents,
    }
    (FIXTURES_DIR / "parse-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (FIXTURES_DIR / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in all_chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {FIXTURES_DIR / 'parse-report.json'}")
    print(f"wrote {FIXTURES_DIR / 'chunks.jsonl'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
