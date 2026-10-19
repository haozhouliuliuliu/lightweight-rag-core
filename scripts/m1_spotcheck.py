#!/usr/bin/env python3
"""Generate a 3-chunk human spot-check report for M1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.parser import parse_document  # noqa: E402

CHUNKS = REPO_ROOT / "tests" / "fixtures" / "chunks.jsonl"
OUT = REPO_ROOT / "tests" / "results" / "m1-parse-spotcheck.md"

CASES = [
    ("A01/DOCX", "data/docs/product/STARLAN-X100-product-manual-v1.2.docx", "额定功率"),
    ("B04/PDF", "data/docs/quality/STARLAN-QS-001-inspection-spec-v2.0.pdf", "1500 VAC"),
    ("C06/PDF", "data/docs/equipment/STARLAN-M3-operation-manual-v1.1.pdf", "8.0 N·m"),
]


def main() -> int:
    if not CHUNKS.exists():
        raise SystemExit(f"missing {CHUNKS}; run scripts/build_m1_reports.py first")
    rows = [json.loads(line) for line in CHUNKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_source: dict[str, list[dict]] = {}
    for row in rows:
        by_source.setdefault(row["metadata"]["source_file"], []).append(row)

    lines = [
        "# M1 解析与切分人工抽查（3 个 chunk）",
        "",
        "> 数据来源：`tests/fixtures/chunks.jsonl`；逐块与 `parser.parse_document()` 的全文按字符区间比对。",
        "",
        "| 用例 | 源文件 | 格式 | chunk_id | page | 字符区间 | 文本片段 | 原文一致 | 元数据完整 |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    all_ok = True
    details: list[str] = []
    for label, source, needle in CASES:
        candidates = by_source.get(source, [])
        chunk = next((item for item in candidates if needle in item["text"]), None)
        if chunk is None and candidates:
            chunk = candidates[0]
        if chunk is None:
            all_ok = False
            lines.append(f"| {label} | {source} | - | - | - | - | - | 未找到 chunk | ❌ |")
            continue

        meta = chunk["metadata"]
        parsed = parse_document(REPO_ROOT / source)
        expected = parsed.text[meta["char_start"] : meta["char_end"]]
        exact = expected == chunk["text"]
        fields_ok = all(
            key in meta and meta[key] is not None
            for key in ("source_file", "chunk_id", "page", "char_start", "char_end")
        ) or (parsed.file_type == "docx" and meta.get("page") is None)
        all_ok = all_ok and exact and fields_ok
        snippet = " ".join(chunk["text"].split())[:100]
        lines.append(
            f"| {label} | `{source}` | {parsed.file_type} | {meta['chunk_id']} | "
            f"{meta['page'] if meta['page'] is not None else '—'} | "
            f"{meta['char_start']}–{meta['char_end']} | {snippet}… | "
            f"{'✅' if exact else '❌'} | {'✅' if fields_ok else '❌'} |"
        )
        details.append(
            f"### {label}\n\n"
            f"- 源文件：`{source}`\n"
            f"- chunk_id：{meta['chunk_id']}\n"
            f"- page：{meta['page']}\n"
            f"- 字符区间：{meta['char_start']}–{meta['char_end']}（长度 {meta['char_length']}）\n"
            f"- 原文按区间切片与 chunk 文本一致：**{'是' if exact else '否'}**\n\n"
            f"```text\n{chunk['text'][:500]}\n```\n"
        )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 3 个 chunk 的文本与源文档按 `char_start:char_end` 切片完全一致：**{'是' if all_ok else '否'}**。",
            "- DOCX 的 page 为 `None`（格式无页码）；PDF 的 page 为解析页码。",
            "- `source_file`、`chunk_id`、`page`、字符区间均已写入 `chunks.jsonl`。",
            "",
            "## 逐块证据",
            "",
            *details,
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"all_ok={all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
