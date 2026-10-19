from types import SimpleNamespace

import pytest

from lightrag.answer import (
    AnswerGenerationError,
    QwenAnswerer,
    build_context,
    parse_citations,
)
from lightrag.config import LLMSettings
from lightrag.retriever import RetrievedChunk

SETTINGS = LLMSettings(
    base_url="https://example.invalid/v1",
    model="qwen-plus",
    api_key_env="TEST_KEY",
    timeout_seconds=5,
    temperature=0,
    max_tokens=200,
)


def chunks():
    return [
        RetrievedChunk(
            "X-100 额定功率 5 W",
            {
                "doc_title": "X-100 说明书",
                "source_file": "data/docs/x100.docx",
                "chunk_id": 2,
                "page": -1,
            },
            0.9,
            1,
        ),
        RetrievedChunk(
            "X-100 防护等级 IP54",
            {
                "doc_title": "X-100 说明书",
                "source_file": "data/docs/x100.docx",
                "chunk_id": 3,
                "page": -1,
            },
            0.8,
            2,
        ),
    ]


class FakeRetriever:
    def __init__(self, items):
        self.items = items

    def retrieve(self, question: str, top_k: int = 5):
        return self.items[:top_k]


class FakeClient:
    def __init__(self, content: str):
        self.content = content
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_context_and_citation_parsing() -> None:
    context = build_context(chunks())
    assert "[1]" in context and "[2]" in context
    citations, error = parse_citations("功率 5 W [1]，防护 IP54 [2]。", chunks())
    assert [c.marker for c in citations] == [1, 2]
    assert error is None
    assert citations[0].source_file == "data/docs/x100.docx"


def test_invalid_marker_is_reported() -> None:
    citations, error = parse_citations("答案 [9]", chunks())
    assert citations == []
    assert "9" in error


def test_answer_uses_context_and_citations() -> None:
    client = FakeClient("X-100 额定功率为 5 W [1]。")
    answerer = QwenAnswerer(SETTINGS, "dummy", FakeRetriever(chunks()), client=client)
    result = answerer.answer("额定功率？")
    assert result.answer == "X-100 额定功率为 5 W [1]。"
    assert [c.marker for c in result.citations] == [1]
    assert result.refused is False
    assert result.citation_error is None
    assert "X-100 额定功率 5 W" in client.calls[0]["messages"][1]["content"]


def test_no_retrieval_is_refusal_without_llm_call() -> None:
    client = FakeClient("should not be called")
    answerer = QwenAnswerer(SETTINGS, "dummy", FakeRetriever([]), client=client)
    result = answerer.answer("任何问题")
    assert result.refused is True
    assert "资料不足" in result.answer
    assert client.calls == []


def test_llm_failure_is_not_fake_answer() -> None:
    class FailingClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            raise TimeoutError("timeout")

    answerer = QwenAnswerer(SETTINGS, "dummy", FakeRetriever(chunks()), client=FailingClient())
    with pytest.raises(AnswerGenerationError):
        answerer.answer("额定功率？")
