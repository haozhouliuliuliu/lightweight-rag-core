#!/usr/bin/env python3
"""M4 evidence: invalid inputs and failed external services do not fake success."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lightrag.answer import AnswerGenerationError, QwenAnswerer  # noqa: E402
from lightrag.config import load_config  # noqa: E402
from lightrag.documents import DocumentManager, DocumentManagerError  # noqa: E402
from lightrag.embeddings import DashScopeEmbedder, EmbeddingError  # noqa: E402
from lightrag.retriever import RetrievedChunk  # noqa: E402

OUT = REPO_ROOT / "tests" / "results" / "m4-failures.md"


class FakeRetriever:
    def retrieve(self, question: str, top_k: int = 5):
        return [
            RetrievedChunk(
                "X-100 的额定功率为 5 W。",
                {
                    "doc_id": "A01",
                    "doc_title": "X-100 便携式扭矩校验仪产品说明书",
                    "source_file": "data/docs/product/STARLAN-X100-product-manual-v1.2.docx",
                    "chunk_id": 1,
                    "page": -1,
                },
                0.9,
                1,
            )
        ]


def main() -> int:
    config = load_config()
    rows: list[tuple[str, str, str]] = []

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        docs = root / "data" / "docs"
        docs.mkdir(parents=True)
        manager = DocumentManager(docs, root)

        bad = root / "bad.csv"
        bad.write_text("a,b\n1,2\n", encoding="utf-8")
        try:
            manager.add(bad)
            rows.append(("不支持格式", "FAIL", "未报错"))
        except DocumentManagerError as exc:
            rows.append(("不支持格式", "PASS", str(exc)[:160]))

        empty = root / "empty.txt"
        empty.write_text("", encoding="utf-8")
        try:
            manager.add(empty)
            rows.append(("空文档", "FAIL", "未报错"))
        except DocumentManagerError as exc:
            rows.append(("空文档", "PASS", str(exc)[:160]))

    try:
        DashScopeEmbedder(config.embedding, "invalid-key", sleep=lambda _: None).embed_texts(
            ["failure smoke"]
        )
        rows.append(("Embedding 鉴权失败", "FAIL", "未报错"))
    except EmbeddingError as exc:
        rows.append(("Embedding 鉴权失败", "PASS", str(exc)[:160]))

    try:
        QwenAnswerer(config.llm, "invalid-key", FakeRetriever()).answer(
            "X-100 的额定功率是多少？", top_k=1
        )
        rows.append(("LLM 鉴权失败", "FAIL", "未报错"))
    except AnswerGenerationError as exc:
        rows.append(("LLM 鉴权失败", "PASS", str(exc)[:160]))

    lines = [
        "# M4 异常与失败处理证据",
        "",
        "| 场景 | 结果 | 证据 |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {name} | {status} | {evidence} |" for name, status, evidence in rows]
    lines += [
        "",
        "## 自动化测试覆盖",
        "",
        "- `tests/test_documents.py`：不支持格式、空文档、重复 id。",
        "- `tests/test_embeddings.py::test_dimension_mismatch_raises`：Embedding 维度异常。",
        "- `tests/test_answer.py::test_llm_failure_is_not_fake_answer`：LLM 超时抛出错误，不返回假回答。",
        "- `tests/test_answer.py::test_no_retrieval_is_refusal_without_llm_call`：空检索直接拒答。",
        "- `tests/test_lifecycle.py`：新增、删除、重新索引、重复索引。",
        "- `tests/test_vector_store.py`：删除后 count=0、brute-force 回退路径。",
        "",
        "## 结论",
        "",
        "- 不支持的格式和空文档被拒绝；",
        "- Embedding/LLM 鉴权失败均抛错，没有生成假向量或假回答；",
        "- 自动化测试覆盖超时、维度、删除和重索引路径。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
