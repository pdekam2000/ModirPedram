"""
Phase 11I-4 — narration text normalization and cue line splitting.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_MAX_LINE_LENGTH = 42

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+")
_WHITESPACE = re.compile(r"\s+")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def resolve_max_line_length(profile: dict[str, Any] | None = None) -> int:
    profile = _dict(profile)
    subtitle_rules = _dict(profile.get("subtitle_rules"))
    try:
        value = int(subtitle_rules.get("max_line_length", DEFAULT_MAX_LINE_LENGTH))
    except (TypeError, ValueError):
        value = DEFAULT_MAX_LINE_LENGTH
    return max(12, min(value, 120))


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE.sub(" ", str(text or "").strip())


def split_into_cue_lines(
    text: str,
    *,
    max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
) -> list[str]:
    """Split narration into readable subtitle cue lines."""
    normalized = normalize_whitespace(text)
    if not normalized:
        return []

    if len(normalized) <= max_line_length:
        return [normalized]

    lines: list[str] = []
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(normalized) if part.strip()]
    if not sentences:
        sentences = [normalized]

    for sentence in sentences:
        if len(sentence) <= max_line_length:
            lines.append(sentence)
            continue

        clauses = [part.strip() for part in _CLAUSE_SPLIT.split(sentence) if part.strip()]
        if len(clauses) <= 1:
            lines.extend(_word_wrap(sentence, max_line_length))
            continue

        for clause in clauses:
            if len(clause) <= max_line_length:
                lines.append(clause)
            else:
                lines.extend(_word_wrap(clause, max_line_length))

    merged: list[str] = []
    for line in lines:
        if merged and len(line) < 8:
            candidate = f"{merged[-1]} {line}".strip()
            if len(candidate) <= max_line_length:
                merged[-1] = candidate
                continue
        merged.append(line)

    return [line for line in merged if line.strip()]


def _word_wrap(text: str, max_line_length: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        extra = len(word) if not current else len(word) + 1
        if current and current_len + extra > max_line_length:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += extra

    if current:
        chunk = " ".join(current)
        if chunks and len(chunk) <= 8:
            combined = f"{chunks[-1]} {chunk}".strip()
            if len(combined) <= max_line_length:
                chunks[-1] = combined
            else:
                chunks.append(chunk)
        else:
            chunks.append(chunk)

    if len(chunks) == 1 and len(chunks[0]) > max_line_length:
        hard = chunks[0]
        chunks = []
        for index in range(0, len(hard), max_line_length):
            chunks.append(hard[index : index + max_line_length])

    return chunks


__all__ = [
    "DEFAULT_MAX_LINE_LENGTH",
    "normalize_whitespace",
    "split_into_cue_lines",
    "resolve_max_line_length",
]
