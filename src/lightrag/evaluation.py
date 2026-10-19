"""Reuse the project-one 30-question judge rules against this pipeline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .answer import AnswerGenerationError, AnswerResult, QwenAnswerer
from .refusal import is_refusal, normalize
from .retriever import RetrievalError, Retriever

VERDICT_HIT = "命中"
VERDICT_MISS = "未命中"
VERDICT_REFUSAL = "拒答"
VERDICT_FABRICATION = "编造"
VERDICT_ERROR = "错误"


class EvaluationError(RuntimeError):
    """Raised when a question set or evaluation run is invalid."""


@dataclass
class QuestionResult:
    id: str
    question: str
    type: str
    verdict: str
    reason: str
    retrieval_hit: bool | None
    answer: str
    citations: list[dict[str, Any]]
    retrieved: list[dict[str, Any]]
    citation_error: str | None
    model: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "type": self.type,
            "verdict": self.verdict,
            "reason": self.reason,
            "retrieval_hit": self.retrieval_hit,
            "answer": self.answer,
            "citations": self.citations,
            "retrieved": self.retrieved,
            "citation_error": self.citation_error,
            "model": self.model,
            "error": self.error,
        }


def load_questions(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    questions = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(questions, list) or not questions:
        raise EvaluationError("questions file must contain a non-empty array")
    required = {"id", "question", "type", "judge"}
    for index, question in enumerate(questions, start=1):
        missing = required - set(question)
        if missing:
            raise EvaluationError(f"question {index} missing fields: {sorted(missing)}")
        if not isinstance(question["judge"], dict):
            raise EvaluationError(f"question {index} judge must be an object")
    return questions


def _source_titles(items: list[dict[str, Any]]) -> list[str]:
    titles: list[str] = []
    for item in items:
        title = item.get("doc_title")
        if not title and isinstance(item.get("metadata"), dict):
            title = item["metadata"].get("doc_title")
        if title:
            titles.append(str(title))
    return titles


def _has_expected(titles: list[str], expected: list[str]) -> bool:
    blob = normalize(" ".join(titles))
    return any(normalize(value) in blob for value in expected)


def _has_all_expected(titles: list[str], expected: list[str]) -> bool:
    blob = normalize(" ".join(titles))
    return all(normalize(value) in blob for value in expected)


def judge(
    question: dict[str, Any],
    result: AnswerResult,
) -> tuple[str, str, bool | None]:
    rule = question.get("judge") or {}
    answer = result.answer or ""
    normalized_answer = normalize(answer)
    expected = [str(x) for x in (rule.get("expected_sources") or [])]
    expected_all = [str(x) for x in (rule.get("expected_sources_all") or [])]

    retrieval_hit: bool | None = None
    if expected or expected_all:
        # The benchmark metric is explicitly Top-5, even when the answer
        # context is expanded with sibling chunks for generation quality.
        titles = _source_titles([item.to_dict() for item in result.retrieved[:5]])
        retrieval_hit = (
            _has_all_expected(titles, expected_all)
            if expected_all
            else _has_expected(titles, expected)
        )

    if rule.get("must_refuse"):
        if is_refusal(normalized_answer, broad=True):
            return VERDICT_REFUSAL, "无答案题检测到拒答标记", retrieval_hit
        return VERDICT_FABRICATION, "无答案题未表明资料不足", retrieval_hit

    must_all = [str(x) for x in (rule.get("must_include_all") or [])]
    if must_all:
        missing = [x for x in must_all if normalize(x) not in normalized_answer]
        if missing:
            if result.refused or is_refusal(normalized_answer):
                return VERDICT_REFUSAL, "可回答题意外触发拒答", retrieval_hit
            return VERDICT_MISS, "缺少关键词：" + "、".join(missing), retrieval_hit

    must_any = [str(x) for x in (rule.get("must_include_any") or [])]
    if must_any and not any(normalize(x) in normalized_answer for x in must_any):
        if result.refused or is_refusal(normalized_answer):
            return VERDICT_REFUSAL, "可回答题意外触发拒答", retrieval_hit
        return VERDICT_MISS, "未出现任一预期关键词：" + "、".join(must_any), retrieval_hit

    citation_titles = _source_titles([citation.to_dict() for citation in result.citations])
    if result.citation_error:
        return VERDICT_MISS, f"引用编号无效：{result.citation_error}", retrieval_hit
    if expected_all and not _has_all_expected(citation_titles, expected_all):
        return VERDICT_MISS, "引用来源未同时匹配：" + "、".join(expected_all), retrieval_hit
    if expected and not _has_expected(citation_titles, expected):
        return VERDICT_MISS, "引用来源未匹配：" + "、".join(expected), retrieval_hit
    return VERDICT_HIT, "关键词与引用来源匹配", retrieval_hit


def evaluate(
    questions: list[dict[str, Any]],
    retriever: Retriever,
    answerer: QwenAnswerer,
    *,
    top_k: int = 5,
) -> list[QuestionResult]:
    results: list[QuestionResult] = []
    for question in questions:
        try:
            answer = answerer.answer(question["question"], top_k=top_k)
            verdict, reason, retrieval_hit = judge(question, answer)
            results.append(
                QuestionResult(
                    id=str(question["id"]),
                    question=str(question["question"]),
                    type=str(question["type"]),
                    verdict=verdict,
                    reason=reason,
                    retrieval_hit=retrieval_hit,
                    answer=answer.answer,
                    citations=[item.to_dict() for item in answer.citations],
                    retrieved=[item.to_dict() for item in answer.retrieved],
                    citation_error=answer.citation_error,
                    model=answer.model,
                )
            )
        except (RetrievalError, AnswerGenerationError, Exception) as exc:
            results.append(
                QuestionResult(
                    id=str(question["id"]),
                    question=str(question["question"]),
                    type=str(question["type"]),
                    verdict=VERDICT_ERROR,
                    reason=f"{type(exc).__name__}: {exc}",
                    retrieval_hit=None,
                    answer="",
                    citations=[],
                    retrieved=[],
                    citation_error=None,
                    model="",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def summarize(results: list[QuestionResult]) -> dict[str, Any]:
    counts: dict[str, int] = {
        VERDICT_HIT: 0,
        VERDICT_MISS: 0,
        VERDICT_REFUSAL: 0,
        VERDICT_FABRICATION: 0,
        VERDICT_ERROR: 0,
    }
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    answerable = [item for item in results if not item.id.startswith("N")]
    no_answer = [item for item in results if item.id.startswith("N")]
    retrieval_evaluable = [item for item in answerable if item.retrieval_hit is not None]
    retrieval_hits = sum(1 for item in retrieval_evaluable if item.retrieval_hit)
    valid_citations = sum(
        1
        for item in answerable
        if item.citations and item.citation_error is None
    )
    return {
        **counts,
        "total": len(results),
        "answerable": len(answerable),
        "no_answer": len(no_answer),
        "retrieval_evaluable": len(retrieval_evaluable),
        "retrieval_hits": retrieval_hits,
        "retrieval_rate": round(retrieval_hits / len(retrieval_evaluable), 4)
        if retrieval_evaluable
        else 0,
        "citation_valid": valid_citations,
        "citation_rate": round(valid_citations / len(answerable), 4) if answerable else 0,
        "no_answer_refusals": sum(1 for item in no_answer if item.verdict == VERDICT_REFUSAL),
    }


def write_markdown(path: Path, results: list[QuestionResult], summary: dict[str, Any]) -> None:
    lines = [
        "# 30 题评测报告",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 总题数：{summary['total']}；有答案：{summary['answerable']}；无答案：{summary['no_answer']}",
        f"- Top-5 检索命中：{summary['retrieval_hits']}/{summary['retrieval_evaluable']}"
        f"（{summary['retrieval_rate']:.1%}）",
        f"- 有效引用：{summary['citation_valid']}/{summary['answerable']}"
        f"（{summary['citation_rate']:.1%}）",
        f"- 无答案拒答：{summary['no_answer_refusals']}/{summary['no_answer']}",
        "",
        "| 题号 | 类型 | 判定 | Top-5 检索 | 原因 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        retrieval = "—" if result.retrieval_hit is None else ("✅" if result.retrieval_hit else "❌")
        lines.append(
            f"| {result.id} | {result.type} | {result.verdict} | {retrieval} | "
            f"{result.reason.replace('|', '/')} |"
        )
    lines.extend(["", "## 逐题回答", ""])
    for result in results:
        lines.extend(
            [
                f"### {result.id}",
                "",
                f"**问题**：{result.question}",
                "",
                f"**判定**：{result.verdict} — {result.reason}",
                "",
                f"**回答**：{result.answer or '(空)'}",
                "",
                "**引用**：" + (", ".join(
                    f"[{c['marker']}] {c['doc_title']} page={c['page']}" for c in result.citations
                ) or "无"),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
