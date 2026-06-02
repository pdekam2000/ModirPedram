"""
Phase 11I-4 — dynamic subtitle highlight term resolution (no fixed niche lists).
"""

from __future__ import annotations

import re
from typing import Any

NEUTRAL_FALLBACK_TERMS = (
    "secret",
    "hidden",
    "important",
    "never",
    "always",
    "stop",
    "watch",
)

_SKINCARE_MARKERS = frozenset(
    {"skin", "glow", "mask", "radiant", "hydrated", "beauty", "skincare", "selfcare", "glassskin"}
)
_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9']{3,}")
_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "you",
        "your",
        "are",
        "was",
        "were",
        "have",
        "has",
        "had",
        "but",
        "not",
        "they",
        "their",
        "about",
        "into",
        "than",
        "then",
        "when",
        "what",
        "why",
        "how",
        "who",
        "will",
        "just",
        "also",
        "very",
        "can",
        "all",
        "one",
        "two",
        "out",
        "our",
    }
)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_term(term: str) -> str:
    cleaned = str(term or "").strip().lower().lstrip("#")
    return cleaned


def _extract_tokens(text: str) -> list[str]:
    return [_normalize_term(match.group(0)) for match in _TOKEN_PATTERN.finditer(str(text or ""))]


def _dedupe_terms(terms: list[str], *, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for term in terms:
        normalized = _normalize_term(term)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
        if len(ordered) >= limit:
            break
    return ordered


def _profile_terms(profile: dict[str, Any] | None) -> list[str]:
    profile = _dict(profile)
    terms: list[str] = []
    terms.extend(str(item) for item in _list(profile.get("highlight_keywords")))
    subtitle_rules = _dict(profile.get("subtitle_rules"))
    terms.extend(str(item) for item in _list(subtitle_rules.get("highlight_keywords")))
    terms.extend(str(item) for item in _list(subtitle_rules.get("fallback_highlight")))
    seo_rules = _dict(profile.get("seo_rules"))
    terms.extend(str(item) for item in _list(seo_rules.get("keywords")))
    terms.extend(str(item) for item in _list(seo_rules.get("hashtags")))
    terms.extend(str(item) for item in _list(profile.get("seo_keywords")))
    return terms


def _channel_terms(channel_identity: dict[str, Any] | None) -> list[str]:
    channel = _dict(channel_identity)
    terms = [str(item) for item in _list(channel.get("highlight_keywords"))]
    terms.extend(str(item) for item in _list(channel.get("seo_keywords")))
    return terms


def _brief_terms(session: dict[str, Any]) -> list[str]:
    brief = _dict(session.get("brief_snapshot"))
    terms: list[str] = []

    topic = str(brief.get("topic") or session.get("topic") or "").strip()
    title = str(brief.get("title") or "").strip()
    if topic:
        terms.extend(_extract_tokens(topic))
    if title:
        terms.extend(_extract_tokens(title))

    run_context = _dict(brief.get("run_context"))
    semantic = _dict(run_context.get("semantic_universe"))
    terms.extend(str(item) for item in _list(semantic.get("topic_seed_pool")))

    keywords = brief.get("keywords")
    if isinstance(keywords, list):
        terms.extend(str(item) for item in keywords)

    return terms


def _narration_derived_terms(narration_texts: list[str], *, limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    for text in narration_texts:
        for token in _extract_tokens(text):
            if token in _STOP_WORDS:
                continue
            if token.isdigit():
                counts[token] = counts.get(token, 0) + 2
                continue
            counts[token] = counts.get(token, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return [token for token, _count in ranked[:limit]]


def resolve_session_highlight_terms(
    session: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    channel_identity: dict[str, Any] | None = None,
    narration_texts: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Return (highlight_terms, sources_used).

    Priority: channel → profile → brief/topic → narration-derived → neutral fallback.
    """
    sources: list[str] = []
    collected: list[str] = []

    channel_terms = _channel_terms(channel_identity)
    if channel_terms:
        sources.append("channel_identity")
        collected.extend(channel_terms)

    profile_terms = _profile_terms(profile)
    if profile_terms:
        sources.append("profile")
        collected.extend(profile_terms)

    brief_terms = _brief_terms(session)
    if brief_terms:
        sources.append("brief_topic")
        collected.extend(brief_terms)

    narration_terms = _narration_derived_terms(narration_texts or [])
    if narration_terms:
        sources.append("narration_derived")
        collected.extend(narration_terms)

    terms = _dedupe_terms(collected)
    if terms:
        return terms, sources

    profile = _dict(profile)
    subtitle_rules = _dict(profile.get("subtitle_rules"))
    if subtitle_rules.get("allow_neutral_fallback") is False:
        return [], sources

    fallback = _list(subtitle_rules.get("fallback_highlight"))
    if fallback:
        sources.append("profile_fallback")
        return _dedupe_terms([str(item) for item in fallback]), sources

    sources.append("neutral_fallback")
    return list(NEUTRAL_FALLBACK_TERMS), sources


def cue_highlight_terms(cue_text: str, session_terms: list[str], *, max_terms: int = 3) -> list[str]:
    lowered = str(cue_text or "").lower()
    matched: list[str] = []
    for term in session_terms:
        if term in lowered and term not in matched:
            matched.append(term)
        if len(matched) >= max_terms:
            break
    return matched


def contains_skincare_marker(terms: list[str]) -> bool:
    return any(any(marker in term for marker in _SKINCARE_MARKERS) for term in terms)


__all__ = [
    "NEUTRAL_FALLBACK_TERMS",
    "resolve_session_highlight_terms",
    "cue_highlight_terms",
    "contains_skincare_marker",
]
