from lightrag.answer import AnswerResult, Citation
from lightrag.evaluation import (
    VERDICT_HIT,
    VERDICT_REFUSAL,
    QuestionResult,
    judge,
    summarize,
)
from lightrag.retriever import RetrievedChunk


def make_result(answer: str, titles=("X-100 说明书",)) -> AnswerResult:
    retrieved = [
        RetrievedChunk(
            "X-100 额定功率 5 W",
            {
                "doc_title": title,
                "source_file": "data/docs/x100.docx",
                "chunk_id": index + 1,
                "page": -1,
            },
            0.9,
            index + 1,
        )
        for index, title in enumerate(titles)
    ]
    citations = [
        Citation(index + 1, title, "data/docs/x100.docx", index + 1, None)
        for index, title in enumerate(titles)
    ]
    return AnswerResult(
        question="额定功率？",
        answer=answer,
        retrieved=retrieved,
        citations=citations,
        refused="资料不足" in answer,
        model="qwen-plus",
    )


def test_judge_hit_and_refusal() -> None:
    question = {
        "id": "F01",
        "question": "额定功率？",
        "type": "直接",
        "judge": {
            "must_include_all": ["5 W"],
            "expected_sources": ["X-100 说明书"],
        },
    }
    verdict, reason, retrieval_hit = judge(question, make_result("额定功率 5 W [1]"))
    assert verdict == VERDICT_HIT
    assert retrieval_hit is True

    no_answer = {
        "id": "N01",
        "question": "不存在？",
        "type": "无答案",
        "judge": {"must_refuse": True},
    }
    verdict, reason, _ = judge(no_answer, make_result("资料不足，资料中未找到。"))
    assert verdict == VERDICT_REFUSAL


def test_summary_counts() -> None:
    results = [
        QuestionResult("F01", "q", "直接", VERDICT_HIT, "ok", True, "a [1]", [{"doc_title": "x"}], [], None, "qwen"),
        QuestionResult("M01", "q", "综合", VERDICT_HIT, "ok", False, "a [1]", [{"doc_title": "x"}], [], None, "qwen"),
        QuestionResult("N01", "q", "无答案", VERDICT_REFUSAL, "ok", None, "资料不足", [], [], None, "qwen"),
    ]
    summary = summarize(results)
    assert summary["total"] == 3
    assert summary["retrieval_hits"] == 1
    assert summary["retrieval_evaluable"] == 2
    assert summary["no_answer_refusals"] == 1
