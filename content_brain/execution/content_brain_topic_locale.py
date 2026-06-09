"""
Detect user input language/locale for Content Brain pipelines.

Rule-based only — no external API. Used to keep SEO, story, and trend search
aligned with the language the operator typed.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_LANGUAGE = "en"

LANGUAGE_NAME_TO_CODE: dict[str, str] = {
    "english": "en",
    "persian": "fa",
    "farsi": "fa",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "arabic": "ar",
    "turkish": "tr",
    "italian": "it",
    "portuguese": "pt",
    "dutch": "nl",
    "polish": "pl",
    "russian": "ru",
    "japanese": "ja",
    "korean": "ko",
    "hindi": "hi",
}

LANG_HINT_WORDS: dict[str, tuple[str, ...]] = {
    "fa": (
        "و",
        "در",
        "با",
        "از",
        "که",
        "این",
        "آن",
        "برای",
        "روش",
        "چگونه",
        "ماهی",
        "صید",
    ),
    "ar": ("في", "من", "على", "هذا", "التي", "كيف", "لماذا"),
    "de": ("und", "der", "die", "das", "mit", "für", "wie", "warum", "nicht"),
    "fr": ("et", "les", "des", "pour", "avec", "comment", "pourquoi", "dans"),
    "es": ("y", "los", "las", "para", "con", "como", "porque", "método"),
    "tr": ("ve", "bir", "için", "nasıl", "neden", "ile", "bu"),
    "en": ("the", "and", "for", "with", "how", "why", "method", "best"),
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

TITLE_STOPWORDS = frozenset(
    {
        "concrete",
        "specific",
        "story",
        "detail",
        "sensory",
        "anchor",
        "topic",
        "about",
        "this",
        "that",
        "with",
        "from",
        "your",
        "what",
        "when",
        "where",
        "everyone",
        "nobody",
        "actually",
        "really",
        "method",
    }
)


def filter_auxiliary_topic_tokens(tokens: list[str]) -> list[str]:
    cleaned: list[str] = []
    for token in tokens:
        lowered = str(token or "").strip().lower()
        if not lowered or lowered in QUESTION_AUX_WORDS:
            continue
        if len(lowered) < 2:
            continue
        cleaned.append(str(token).strip())
    return cleaned


def detect_language_code(text: str) -> str:
    """Return ISO 639-1 language code inferred from user text."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return DEFAULT_LANGUAGE

    if _contains_persian(cleaned):
        return "fa"
    if _contains_arabic(cleaned) and not _contains_persian(cleaned):
        return "ar"
    if _contains_cyrillic(cleaned):
        return "ru"
    if _contains_cjk(cleaned):
        if _contains_hangul(cleaned):
            return "ko"
        if _contains_hiragana_katakana(cleaned):
            return "ja"
        return "zh"

    lowered = cleaned.lower()
    scores: dict[str, int] = {}
    tokens = re.findall(r"[\w\u0600-\u06FF\u0750-\u077F]+", lowered, flags=re.UNICODE)
    token_set = set(tokens)
    for lang, hints in LANG_HINT_WORDS.items():
        scores[lang] = sum(1 for word in hints if word in token_set)

    best_lang = max(scores, key=lambda key: scores[key])
    if scores.get(best_lang, 0) >= 1 and best_lang != "en":
        return best_lang
    if scores.get("en", 0) >= 1:
        return "en"
    return DEFAULT_LANGUAGE


def locale_for_language(language_code: str) -> str:
    code = str(language_code or DEFAULT_LANGUAGE).strip().lower().split("-")[0]
    return code or DEFAULT_LANGUAGE


def profile_with_output_language(
    profile: dict[str, Any],
    language_code: str,
) -> dict[str, Any]:
    """Clone profile and inject output language for trend providers."""
    merged = dict(profile or {})
    language_rules = dict(merged.get("language_rules") or {})
    language_rules["output_language"] = locale_for_language(language_code)
    merged["language_rules"] = language_rules
    merged["language"] = locale_for_language(language_code)
    return merged


def extract_topic_anchor_tokens(topic: str, *, limit: int = 4) -> list[str]:
    """Meaningful tokens from topic for titles and preservation checks."""
    stop = TITLE_STOPWORDS | {
        "the",
        "and",
        "for",
        "with",
        "from",
        "how",
        "why",
        "best",
        "top",
        "guide",
        "tips",
    }
    tokens = re.findall(r"[\w\u0600-\u06FF\u0750-\u077F\u4e00-\u9fff]+", str(topic or ""), flags=re.UNICODE)
    result: list[str] = []
    for token in tokens:
        cleaned = token.strip()
        if len(cleaned) < 2:
            continue
        if cleaned.lower() in stop:
            continue
        if cleaned not in result:
            result.append(cleaned)
        if len(result) >= limit:
            break
    filtered = filter_auxiliary_topic_tokens(result)
    return filtered or result or [str(topic or "topic").strip()[:40] or "topic"]


def pick_title_anchor(topic: str, *, fallback: str = "topic") -> str:
    """Primary anchor word/phrase for SEO titles — never generic filler like 'concrete'."""
    tokens = extract_topic_anchor_tokens(topic, limit=3)
    if not tokens:
        return fallback
    if len(tokens) >= 2 and len(" ".join(tokens[:2])) <= 32:
        return " ".join(tokens[:2])
    return tokens[0]


def _contains_persian(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]", text))


def _contains_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF\u0750-\u077F]", text))


def _contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", text))


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[\uAC00-\uD7AF]", text))


def _contains_hiragana_katakana(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30FF]", text))


__all__ = [
    "DEFAULT_LANGUAGE",
    "TITLE_STOPWORDS",
    "QUESTION_AUX_WORDS",
    "detect_language_code",
    "extract_topic_anchor_tokens",
    "filter_auxiliary_topic_tokens",
    "locale_for_language",
    "pick_title_anchor",
    "profile_with_output_language",
]
