"""qwen-plus answer generation with explicit, verifiable chunk citations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from .config import LLMSettings
from .refusal import is_refusal
from .retriever import RetrievalError, RetrievedChunk, Retriever

CITATION_RE = re.compile(r"\[(\d+)\]")

SYSTEM_PROMPT = """你是企业内部知识库助手。必须遵守：
1. 仅根据提供的资料回答，不得使用资料之外的知识。
2. 资料中没有答案时，明确说明“资料不足”并指出缺什么，禁止编造。
3. 每个结论后用 [n] 标注来源，n 必须是上下文中真实存在的编号。
4. 不得引用未提供的编号；不得编造文件名、页码或版本。
5. 回答涉及型号、版本、日期时必须逐项对应，不得混用。"""


class AnswerGenerationError(RuntimeError):
    """Raised when the LLM call fails or returns unusable output."""


@dataclass(frozen=True)
class Citation:
    marker: int
    doc_title: str
    source_file: str
    chunk_id: int
    page: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "doc_title": self.doc_title,
            "source_file": self.source_file,
            "chunk_id": self.chunk_id,
            "page": self.page,
        }


@dataclass
class AnswerResult:
    question: str
    answer: str
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    context_chunks: list[RetrievedChunk] = field(default_factory=list)
    context: str = ""
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False
    citation_error: str | None = None
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "refused": self.refused,
            "citation_error": self.citation_error,
            "citations": [citation.to_dict() for citation in self.citations],
            "retrieved": [item.to_dict() for item in self.retrieved],
            "context_chunks": [item.to_dict() for item in self.context_chunks],
            "context": self.context,
            "model": self.model,
        }


def build_context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        page = chunk.page if chunk.page is not None else "-"
        blocks.append(
            f"[{index}] {chunk.doc_title} | {chunk.source_file} | page={page} | "
            f"chunk_id={chunk.chunk_id}\n{chunk.text}"
        )
    return "\n\n".join(blocks)


def parse_citations(answer: str, chunks: list[RetrievedChunk]) -> tuple[list[Citation], str | None]:
    citations: list[Citation] = []
    seen: set[int] = set()
    invalid: list[int] = []
    for raw in CITATION_RE.findall(answer):
        marker = int(raw)
        if marker < 1 or marker > len(chunks):
            invalid.append(marker)
            continue
        if marker in seen:
            continue
        seen.add(marker)
        chunk = chunks[marker - 1]
        citations.append(
            Citation(
                marker=marker,
                doc_title=chunk.doc_title,
                source_file=chunk.source_file,
                chunk_id=chunk.chunk_id,
                page=chunk.page,
            )
        )
    error = f"invalid citation markers: {sorted(set(invalid))}" if invalid else None
    return citations, error


class QwenAnswerer:
    def __init__(
        self,
        settings: LLMSettings,
        api_key: str,
        retriever: Retriever,
        *,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise AnswerGenerationError("missing LLM API key")
        self.settings = settings
        self.retriever = retriever
        self.client = client or OpenAI(
            api_key=api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
        )

    def _expand_context(self, retrieved: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Add sibling chunks from the same documents to recover split tables."""
        store = getattr(self.retriever, "store", None)
        if store is None or not hasattr(store, "get_by_doc"):
            return list(retrieved)
        expanded = list(retrieved)
        seen = {
            (item.metadata.get("doc_id"), item.metadata.get("chunk_id")) for item in retrieved
        }
        doc_ids: list[str] = []
        for item in retrieved:
            doc_id = str(item.metadata.get("doc_id", ""))
            if doc_id and doc_id not in doc_ids:
                doc_ids.append(doc_id)
        for doc_id in doc_ids:
            for sibling in store.get_by_doc(doc_id):
                key = (sibling.metadata.get("doc_id"), sibling.metadata.get("chunk_id"))
                if key in seen:
                    continue
                seen.add(key)
                expanded.append(
                    RetrievedChunk(
                        text=sibling.text,
                        metadata=dict(sibling.metadata),
                        score=sibling.score,
                        rank=len(expanded) + 1,
                    )
                )
        return expanded

    def answer(self, question: str, top_k: int = 5) -> AnswerResult:
        try:
            retrieved = self.retriever.retrieve(question, top_k=top_k)
        except RetrievalError:
            raise
        context_chunks = self._expand_context(retrieved)
        context = build_context(context_chunks)
        if not retrieved:
            return AnswerResult(
                question=question,
                answer="资料不足：当前索引没有可供检索的片段。",
                retrieved=[],
                context_chunks=[],
                context="",
                refused=True,
                model=self.settings.model,
            )

        user_prompt = f"问题：{question}\n\n检索资料：\n{context}\n\n请按要求回答并标注 [n] 引用。"
        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_tokens,
            )
            content = response.choices[0].message.content
        except Exception as exc:
            raise AnswerGenerationError(
                f"LLM request failed ({type(exc).__name__}): {exc}"
            ) from exc
        if not content or not str(content).strip():
            raise AnswerGenerationError("LLM returned an empty answer")

        answer = str(content).strip()
        citations, citation_error = parse_citations(answer, context_chunks)
        return AnswerResult(
            question=question,
            answer=answer,
            retrieved=retrieved,
            context_chunks=context_chunks,
            context=context,
            citations=citations,
            refused=is_refusal(answer),
            citation_error=citation_error,
            model=self.settings.model,
        )
