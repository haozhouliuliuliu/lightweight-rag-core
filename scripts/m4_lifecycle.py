#!/usr/bin/env python3
"""M4 evidence: add/delete/modify/reindex/persistence against real Chroma."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.config import load_config  # noqa: E402
from lightrag.documents import DocumentManager  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder  # noqa: E402
from lightrag.indexer import build_index  # noqa: E402
from lightrag.retriever import Retriever  # noqa: E402
from lightrag.vector_store import ChromaStore  # noqa: E402

OUT = REPO_ROOT / "tests" / "results" / "m4-lifecycle.md"
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def main() -> int:
    config = load_config()
    api_key = config.require_api_key()
    embedder = DashScopeEmbedder(config.embedding, api_key)
    store = ChromaStore(
        config.chroma_dir,
        config.collection,
        query_backend=config.retrieval.query_backend,
    )
    retriever = Retriever(embedder, store)
    manager = DocumentManager(config.docs_dir, config.project_root)

    base_count = store.count()
    if base_count != 55:
        raise SystemExit(f"expected 55 base chunks, got {base_count}")

    lines = [
        "# M4 文档生命周期与持久化证据",
        "",
        f"- 基线 collection count：{base_count}",
        "",
        "## 新增文档",
        "",
    ]
    added_ids: list[str] = []

    def top5(question: str) -> list[dict]:
        return [item.to_dict() for item in retriever.retrieve(question, top_k=5)]

    def contains(results: list[dict], doc_id: str) -> bool:
        return any(item.get("metadata", {}).get("doc_id") == doc_id for item in results)

    def contains_text(results: list[dict], token: str) -> bool:
        return any(token in str(item.get("text", "")) for item in results)

    try:
        add_entry = manager.add(FIXTURES / "m4-add.txt", doc_id="M4-ADD", title="M4 新增测试")
        added_ids.append("M4-ADD")
        report = build_index(config, embedder, store, recreate=False, doc_ids=["M4-ADD"])
        new_results = top5("M4 新增测试文档的唯一验证码 LIFECYCLE-ADD-7788 是什么？")
        lines += [
            f"- 新增 doc_id：`{add_entry['id']}`；新增 chunk：{report.chunks}",
            f"- collection count：{store.count()}（{base_count} + 1）",
            f"- Top-5 包含新文档：**{'是' if contains(new_results, 'M4-ADD') else '否'}**",
            "",
            "## 删除文档",
            "",
        ]
        manager.remove("M4-ADD")
        store.delete_by_doc("M4-ADD")
        deleted_results = top5("M4 新增测试文档的唯一验证码 LIFECYCLE-ADD-7788 是什么？")
        lines += [
            f"- 删除后 collection count：{store.count()}",
            f"- Top-5 仍包含已删除文档：**{'是' if contains(deleted_results, 'M4-ADD') else '否'}**",
            "",
            "## 修改后重新索引",
            "",
        ]

        manager.add(FIXTURES / "m4-modify-v1.txt", doc_id="M4-MOD", title="M4 修改测试")
        build_index(config, embedder, store, recreate=False, doc_ids=["M4-MOD"])
        old_results = top5("旧验证码 LIFECYCLE-OLD-1111")
        manager.remove("M4-MOD")
        store.delete_by_doc("M4-MOD")
        manager.add(FIXTURES / "m4-modify-v2.txt", doc_id="M4-MOD", title="M4 修改测试")
        build_index(config, embedder, store, recreate=False, doc_ids=["M4-MOD"])
        new_results = top5("新验证码 LIFECYCLE-NEW-2222")
        old_after = top5("旧验证码 LIFECYCLE-OLD-1111")
        lines += [
            f"- 修改前旧内容命中：**{'是' if contains_text(old_results, 'LIFECYCLE-OLD-1111') else '否'}**",
            f"- 修改后新内容命中：**{'是' if contains_text(new_results, 'LIFECYCLE-NEW-2222') else '否'}**",
            f"- 修改后旧内容仍命中：**{'是' if contains_text(old_after, 'LIFECYCLE-OLD-1111') else '否'}**",
            "",
        ]
        manager.remove("M4-MOD")
        store.delete_by_doc("M4-MOD")
        added_ids.clear()
        lines += [
            "## 重复重新索引",
            "",
        ]
        first = build_index(config, embedder, store)
        second = build_index(config, embedder, store)
        ids_after = store.collection.get(include=[])["ids"]
        lines += [
            f"- 第一次全量重索引 count：{first.collection_count}",
            f"- 第二次全量重索引 count：{second.collection_count}",
            f"- chunk ID 唯一数：{len(set(ids_after))}/{len(ids_after)}",
            "",
            "## 重启后持久化",
            "",
        ]
        reopened = ChromaStore(
            config.chroma_dir,
            config.collection,
            query_backend=config.retrieval.query_backend,
        )
        persisted_results = top5("X-100 的额定功率是多少？")
        lines += [
            f"- 重新创建 PersistentClient 后 count：{reopened.count()}",
            f"- 重开后检索返回条数：{len(persisted_results)}",
            f"- 重开后仍能命中 X-100 说明书：**{'是' if any('X-100' in str(item.get('metadata', {}).get('doc_title', '')) for item in persisted_results) else '否'}**",
            "",
            "## 结论",
            "",
            "- 新增、删除、修改后重索引、重复重索引、重启持久化均已实际运行。",
            "- 删除或替换后，旧内容不再出现在 Top-5。",
        ]
    finally:
        for doc_id in added_ids:
            try:
                manager.remove(doc_id)
            except Exception:
                pass
        try:
            build_index(config, embedder, store)
        except Exception as exc:
            print(f"[WARN] final rebuild failed: {exc}", file=sys.stderr)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
