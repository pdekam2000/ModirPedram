"""
Content Brain — language authority audit.

Ensures all downstream outputs match the user's input language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_topic_locale import (
    LANG_HINT_WORDS,
    detect_language_code,
    filter_auxiliary_topic_tokens,
    locale_for_language,
)

LANGUAGE_MARKERS: dict[str, tuple[str, ...]] = {
    "en": ("the", "and", "for", "with", "how", "why", "your", "this", "that", "what", "when"),
    "es": ("el", "la", "los", "las", "para", "con", "como", "porque", "qué", "método", "una", "del"),
    "de": ("und", "der", "die", "das", "mit", "für", "wie", "warum", "nicht", "eine"),
    "fr": ("et", "les", "des", "pour", "avec", "comment", "pourquoi", "dans", "une"),
    "fa": ("و", "در", "با", "از", "که", "این", "آن", "برای", "چگونه"),
    "ar": ("في", "من", "على", "هذا", "التي", "كيف", "لماذا"),
    "tr": ("ve", "bir", "için", "nasıl", "neden", "ile", "bu"),
}

QUESTION_AUX_WORDS = frozenset(
    {
        "can",
        "you",
        "how",
        "to",
        "make",
        "master",
        "the",
        "best",
        "what",
        "why",
        "when",
        "where",
        "who",
        "one",
        "day",
        "try",
        "learn",
        "get",
        "do",
        "does",
        "is",
        "are",
        "a",
        "an",
    }
)


@dataclass
class LanguageAuthorityResult:
    expected_language_code: str
    language_authority_score: float = 1.0
    drift_detected: list[str] = field(default_factory=list)
    field_scores: dict[str, float] = field(default_factory=dict)
    passed: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_language_code": self.expected_language_code,
            "language_authority_score": round(self.language_authority_score, 4),
            "drift_detected": list(self.drift_detected),
            "field_scores": {key: round(value, 4) for key, value in self.field_scores.items()},
            "passed": self.passed,
            "notes": list(self.notes),
        }


def audit_language_authority(
    *,
    topic: str,
    expected_language_code: str | None = None,
    seo_title: str = "",
    story_payload: dict[str, Any] | None = None,
    clip_beats: list[str] | None = None,
    prompt_texts: list[str] | None = None,
    hashtags: list[str] | None = None,
    trends: list[str] | None = None,
) -> LanguageAuthorityResult:
    expected = locale_for_language(expected_language_code or detect_language_code(topic))
    story = dict(story_payload or {})
    fields = {
        "seo_title": seo_title,
        "story_logline": str(story.get("logline") or ""),
        "story_character": str(story.get("main_character") or ""),
        "story_setting": str(story.get("setting") or ""),
        "story_beats": " ".join(str(b) for b in story.get("clip_beats") or clip_beats or []),
        "prompts": " ".join(prompt_texts or []),
        "hashtags": " ".join(hashtags or []),
        "trends": " ".join(trends or []),
    }

    field_scores: dict[str, float] = {}
    drift: list[str] = []
    for key, text in fields.items():
        if not str(text).strip():
            continue
        score = _score_text_language(text, expected)
        field_scores[key] = score
        foreign = _detect_foreign_languages(text, expected)
        if foreign:
            drift.append(f"{key}:{','.join(foreign)}")

    if not field_scores:
        return LanguageAuthorityResult(expected_language_code=expected, language_authority_score=1.0, passed=True)

    authority = sum(field_scores.values()) / len(field_scores)
    passed = authority >= 0.75 and not drift
    notes: list[str] = []
    if drift:
        notes.append("language_drift_detected")
    if not passed:
        notes.append("language_authority_failed")

    return LanguageAuthorityResult(
        expected_language_code=expected,
        language_authority_score=round(min(1.0, max(0.0, authority)), 4),
        drift_detected=drift,
        field_scores=field_scores,
        passed=passed,
        notes=notes,
    )


def _score_text_language(text: str, expected: str) -> float:
    tokens = re.findall(r"[\w\u0600-\u06FF\u0750-\u077F\u4e00-\u9fff]+", str(text or "").lower(), flags=re.UNICODE)
    if not tokens:
        return 1.0
    expected_hits = sum(1 for token in tokens if token in LANGUAGE_MARKERS.get(expected, ()))
    foreign_hits = 0
    for lang, markers in LANGUAGE_MARKERS.items():
        if lang == expected:
            continue
        foreign_hits += sum(1 for token in tokens if token in markers)
    if foreign_hits == 0:
        base = 0.88 if expected == "en" else 0.65
        return min(1.0, base + (expected_hits / max(len(tokens), 1)) * 0.12)
    penalty = foreign_hits / max(len(tokens), 1)
    return max(0.0, 1.0 - penalty * 2.5)


def _detect_foreign_languages(text: str, expected: str) -> list[str]:
    tokens = set(re.findall(r"[\w\u0600-\u06FF\u0750-\u077F]+", str(text or "").lower(), flags=re.UNICODE))
    foreign: list[str] = []
    for lang, markers in LANGUAGE_MARKERS.items():
        if lang == expected:
            continue
        hits = sum(1 for marker in markers if marker in tokens)
        if hits >= 2:
            foreign.append(lang)
    return foreign


__all__ = [
    "LanguageAuthorityResult",
    "audit_language_authority",
]
