"""Shared refusal detection and text normalization."""

from __future__ import annotations

import re

REFUSAL_MARKERS = (
    "资料中未找到",
    "资料未找到",
    "未找到相关资料",
    "没有找到相关",
    "资料不足",
    "无法从资料",
    "无法回答",
    "没有相关信息",
    "没有相关记录",
    "无任何记录",
    "从未出现",
    "未出现",
    "没有提供",
    "未提供相关",
    "不存在相关",
    "不包含该信息",
    "not found",
    "insufficient information",
    "no relevant information",
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


BROAD_REFUSAL_MARKERS = REFUSAL_MARKERS + ("未提及", "未说明", "无对应", "无任何")


def is_refusal(text: str, *, broad: bool = False) -> bool:
    normalized = normalize(text)
    markers = BROAD_REFUSAL_MARKERS if broad else REFUSAL_MARKERS
    return any(marker.lower() in normalized for marker in markers)
