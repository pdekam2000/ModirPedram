"""
SEO title builder for Content Brain Test Studio.

Builds CTR-focused titles from the user topic + live/mock trend angles,
in the same language the operator typed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_topic_locale import (
    detect_language_code,
    pick_title_anchor,
)

try:
    from content_brain.execution.content_brain_topic_strategy import ContentStrategyPlan
except ImportError:  # pragma: no cover
    ContentStrategyPlan = Any  # type: ignore[misc, assignment]

DEFAULT_MAX_CHARS = 72

TITLE_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "{topic}: the {angle} that actually works",
        "Why {anchor} changes everything about {topic}",
        "The {anchor} secret behind {topic}",
        "{topic} — {angle} (watch this first)",
        "Nobody explains {topic} like this {anchor} method",
    ],
    "fa": [
        "{topic}: {angle} که واقعاً جواب می‌دهد",
        "چرا {anchor} در {topic} همه‌چیز را عوض می‌کند",
        "راز {anchor} در {topic}",
        "{topic} — {angle} (اول این را ببین)",
        "این روش {anchor} برای {topic} را از دست نده",
    ],
    "de": [
        "{topic}: der {angle}, der wirklich funktioniert",
        "Warum {anchor} bei {topic} alles verändert",
        "Das {anchor}-Geheimnis hinter {topic}",
        "{topic} — {angle} (zuerst ansehen)",
    ],
    "fr": [
        "{topic} : la {angle} qui fonctionne vraiment",
        "Pourquoi {anchor} change tout sur {topic}",
        "Le secret {anchor} derrière {topic}",
    ],
    "es": [
        "{topic}: el {angle} que realmente funciona",
        "Por qué {anchor} lo cambia todo en {topic}",
        "El secreto de {anchor} en {topic}",
    ],
    "ar": [
        "{topic}: {angle} التي تعمل فعلاً",
        "لماذا {anchor} يغيّر كل شيء في {topic}",
        "سر {anchor} في {topic}",
    ],
    "tr": [
        "{topic}: gerçekten işe yarayan {angle}",
        "{anchor} neden {topic} konusunda her şeyi değiştiriyor",
        "{topic} — {angle} (önce bunu izle)",
    ],
}

DEFAULT_ANGLE: dict[str, str] = {
    "en": "trending angle",
    "fa": "زاویه دید ترند",
    "de": "Trend-Winkel",
    "fr": "angle tendance",
    "es": "ángulo en tendencia",
    "ar": "زاوية رائجة",
    "tr": "trend açısı",
}


@dataclass
class SeoTitlePackage:
    seo_title: str
    title_candidates: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    trend_angle: str = ""
    language_code: str = "en"
    seo_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "seo_title": self.seo_title,
            "title_candidates": list(self.title_candidates),
            "keywords": list(self.keywords),
            "trend_angle": self.trend_angle,
            "language_code": self.language_code,
            "seo_score": round(self.seo_score, 4),
        }


def build_seo_title_package(
    *,
    topic: str,
    trends: list[dict[str, Any]] | None = None,
    platform: str = "youtube_shorts",
    language_code: str | None = None,
    mood: str = "emotional",
    max_chars: int = DEFAULT_MAX_CHARS,
    strategy_plan: ContentStrategyPlan | None = None,
) -> SeoTitlePackage:
    cleaned_topic = re.sub(r"\s+", " ", str(topic or "").strip())
    lang = locale_or_detect(language_code, cleaned_topic)
    anchor = pick_title_anchor(cleaned_topic)
    angle = _pick_trend_angle(cleaned_topic, trends or [], lang)
    templates = list(TITLE_TEMPLATES.get(lang) or TITLE_TEMPLATES["en"])
    if strategy_plan is not None and strategy_plan.seo_title_candidates:
        templates = list(strategy_plan.seo_title_candidates) + templates

    candidates: list[str] = []
    context = {
        "topic": cleaned_topic,
        "anchor": anchor,
        "angle": angle,
        "mood": mood,
        "platform": platform,
    }
    for template in templates:
        rendered = _render_template(template, context)
        trimmed = _trim_title(rendered, max_chars)
        if trimmed and trimmed.lower() not in {c.lower() for c in candidates}:
            candidates.append(trimmed)

    if cleaned_topic and cleaned_topic.lower() not in {c.lower() for c in candidates}:
        candidates.insert(0, _trim_title(cleaned_topic, max_chars))

    scored = sorted(candidates, key=lambda title: _score_title(title, cleaned_topic, anchor, angle), reverse=True)
    seo_title = scored[0] if scored else _trim_title(cleaned_topic or anchor, max_chars)
    keywords = _build_keywords(cleaned_topic, trends or [], anchor, angle)
    seo_score = min(
        1.0,
        sum(
            [
                0.35 if seo_title else 0.0,
                0.25 if anchor.lower() in seo_title.lower() or anchor in seo_title else 0.0,
                0.2 if _topic_overlap(seo_title, cleaned_topic) >= 0.25 else 0.0,
                0.2 if keywords else 0.0,
            ]
        ),
    )
    return SeoTitlePackage(
        seo_title=seo_title,
        title_candidates=scored[:6],
        keywords=keywords,
        trend_angle=angle,
        language_code=lang,
        seo_score=seo_score,
    )


def locale_or_detect(language_code: str | None, topic: str) -> str:
    if language_code and str(language_code).strip():
        return str(language_code).strip().lower().split("-")[0]
    return detect_language_code(topic)


def _pick_trend_angle(topic: str, trends: list[dict[str, Any]], lang: str) -> str:
    for item in trends:
        trend_text = str(item.get("trend") or "").strip()
        if not trend_text or trend_text.lower() == topic.lower():
            continue
        meta = dict(item.get("metadata") or {})
        angle = str(meta.get("trend_angle") or "").strip()
        if angle and angle.lower() != topic.lower():
            return _shorten_angle(angle, lang)
        if _topic_overlap(trend_text, topic) >= 0.15:
            return _shorten_angle(trend_text, lang)
    return DEFAULT_ANGLE.get(lang) or DEFAULT_ANGLE["en"]


def _shorten_angle(text: str, lang: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) <= 48:
        return cleaned
    tokens = cleaned.split()
    if lang == "fa":
        return " ".join(tokens[:6])
    return " ".join(tokens[:7])


def _render_template(template: str, context: dict[str, str]) -> str:
    try:
        return re.sub(r"\s+", " ", template.format(**context)).strip()
    except KeyError:
        return re.sub(r"\s+", " ", template).strip()


def _trim_title(title: str, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    trimmed = cleaned[: max_chars - 1].rsplit(" ", 1)[0]
    return trimmed.strip() or cleaned[:max_chars]


def _score_title(title: str, topic: str, anchor: str, angle: str) -> float:
    score = 0.0
    lower = title.lower()
    if anchor.lower() in lower or anchor in title:
        score += 2.5
    score += _topic_overlap(title, topic) * 4.0
    if angle and (angle.lower() in lower or angle in title):
        score += 1.5
    if 28 <= len(title) <= 68:
        score += 1.0
    return score


def _topic_overlap(text_a: str, text_b: str) -> float:
    tokens_a = set(re.findall(r"[\w\u0600-\u06FF]+", text_a.lower(), flags=re.UNICODE))
    tokens_b = set(re.findall(r"[\w\u0600-\u06FF]+", text_b.lower(), flags=re.UNICODE))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a.intersection(tokens_b)) / len(tokens_a.union(tokens_b))


def _build_keywords(
    topic: str,
    trends: list[dict[str, Any]],
    anchor: str,
    angle: str,
    extra: list[str] | None = None,
) -> list[str]:
    items: list[str] = [topic, anchor]
    for trend in trends[:5]:
        text = str(trend.get("trend") or "").strip()
        if text:
            items.append(text)
    for item in list(extra or []):
        cleaned = str(item or "").strip()
        if cleaned:
            items.append(cleaned)
    if angle:
        items.append(angle)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:12]


__all__ = [
    "SeoTitlePackage",
    "build_seo_title_package",
]
