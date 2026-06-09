"""
SEO Director V2 — strategy-aware natural titles without malformed template chaining.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_seo_title_builder import (
    DEFAULT_MAX_CHARS,
    SeoTitlePackage,
    _build_keywords,
    _pick_trend_angle,
    _topic_overlap,
    _trim_title,
    locale_or_detect,
)
from content_brain.execution.content_brain_topic_locale import pick_title_anchor
from content_brain.execution.content_brain_topic_story_detail import _extract_subject_phrase
from content_brain.execution.content_brain_openai_seo_polisher import polish_provider_seo_titles
from content_brain.execution.content_brain_seo_provider_bridge import (
    SeoProviderIntelligence,
    fetch_seo_provider_intelligence,
)

try:
    from content_brain.execution.content_brain_topic_strategy import (
        STRATEGY_DOCUMENTARY,
        STRATEGY_NARRATIVE_MYSTERY,
        STRATEGY_RECIPE_TUTORIAL,
        STRATEGY_INSTRUCTIONAL_FISHING,
        STRATEGY_INSTRUCTIONAL_GENERAL,
        STRATEGY_EDUCATIONAL_TECH,
        STRATEGY_EDUCATIONAL_LIFESTYLE,
        STRATEGY_HISTORICAL_INVESTIGATION,
        STRATEGY_FUTURE_ANALYSIS,
        STRATEGY_BUSINESS_DEBATE,
        STRATEGY_TECHNOLOGY_FORECAST,
        STRATEGY_SCIENTIFIC_EXPLANATION,
        ContentStrategyPlan,
    )
except ImportError:  # pragma: no cover
    ContentStrategyPlan = Any  # type: ignore[misc, assignment]
    STRATEGY_DOCUMENTARY = "documentary"
    STRATEGY_NARRATIVE_MYSTERY = "narrative_mystery"
    STRATEGY_RECIPE_TUTORIAL = "recipe_tutorial"
    STRATEGY_INSTRUCTIONAL_FISHING = "instructional_fishing"
    STRATEGY_INSTRUCTIONAL_GENERAL = "instructional_general"
    STRATEGY_EDUCATIONAL_LIFESTYLE = "educational_lifestyle"
    STRATEGY_HISTORICAL_INVESTIGATION = "historical_investigation"
    STRATEGY_FUTURE_ANALYSIS = "future_analysis"
    STRATEGY_BUSINESS_DEBATE = "business_debate"
    STRATEGY_TECHNOLOGY_FORECAST = "technology_forecast"
    STRATEGY_SCIENTIFIC_EXPLANATION = "scientific_explanation"

SEO_DIRECTOR_VERSION = "seo_director_v4"

MYSTERY_MALFORMED_SEO_PATTERNS: tuple[str, ...] = (
    r"why the mystery\b",
    r"why the mystery of\b",
    r"why your mystery\b",
    r"\bmystery\b.+\bnever works\b",
    r"\bhow to mystery\b",
    r"\bhow to the mystery\b",
    r"stop making this .+ mystery mistake",
    r"stop making this mystery mistake",
    r"mystery of .+ mystery",
)

INSTRUCTIONAL_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "{action_topic} Step by Step",
        "The Easiest {core_topic} for Beginners",
        "Why Your {core_topic} Never Works",
        "The Simple {core_topic} Trick Most Beginners Miss",
        "{core_topic}: {angle} That Actually Works",
        "Stop Making This {core_topic} Mistake",
    ],
    "fa": [
        "آموزش {core_topic} قدم‌به‌قدم",
        "ساده‌ترین روش {core_topic} برای مبتدی‌ها",
        "چرا {core_topic} شما نتیجه نمی‌دهد",
    ],
    "de": [
        "{action_topic} Schritt für Schritt",
        "Der einfachste {core_topic} für Anfänger",
    ],
    "es": [
        "{action_topic} paso a paso",
        "El truco simple de {core_topic} que casi nadie usa",
    ],
}

MYSTERY_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "What Really Happened at {subject}?",
        "The Untold Story of {subject}",
        "{subject}: The Evidence Still Doesn't Add Up",
        "Why {subject} Remains Unsolved",
        "Why {subject} Still Has No Simple Answer",
        "The Most Disturbing Clue From {subject}",
        "Inside the {subject} Case",
    ],
    "fa": [
        "چه اتفاقی در {subject} افتاد؟",
        "راز {subject} هنوز حل نشده",
    ],
}

DOCUMENTARY_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "The Truth About {subject}",
        "What Really Happened: {subject}",
        "{subject}: What the Records Show",
    ],
    "fa": [
        "حقیقت درباره {subject}",
        "آنچه واقعاً در {subject} رخ داد",
    ],
}

FUTURE_ANALYSIS_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "Will {subject} by 2026?",
        "The Future of {subject} Explained",
        "Why {subject} Could Change Everything",
        "What {subject} Means by 2026",
    ],
    "fa": [
        "آیا {subject} تا ۲۰۲۶ تغییر می‌کند؟",
    ],
}

BUSINESS_DEBATE_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "Will AI Replace {subject}?",
        "Can {subject} Survive the AI Revolution?",
        "The AI Threat Most {subject} Ignore",
        "Why AI Could Disrupt {subject}",
    ],
    "fa": [
        "آیا هوش مصنوعی جای {subject} را می‌گیرد؟",
    ],
}

TECHNOLOGY_FORECAST_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "Will AI Replace {subject}?",
        "The Future of {subject} in an AI World",
        "What AI Still Cannot Do for {subject}",
        "Which {subject} Jobs AI Will Change First",
    ],
    "fa": [
        "آینده {subject} با هوش مصنوعی",
    ],
}

SCIENTIFIC_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "Why {subject}",
        "The Science Behind {subject}",
        "What Makes {subject} Work",
    ],
    "fa": [
        "چرا {subject}",
        "علم پشت {subject}",
    ],
}

INSTRUCTIONAL_STRATEGIES = {
    STRATEGY_INSTRUCTIONAL_FISHING,
    STRATEGY_RECIPE_TUTORIAL,
    STRATEGY_INSTRUCTIONAL_GENERAL,
    STRATEGY_EDUCATIONAL_TECH,
    STRATEGY_EDUCATIONAL_LIFESTYLE,
}

SEO_DIRECTOR_TEMPLATES = INSTRUCTIONAL_TEMPLATES


@dataclass
class SeoTitleCandidate:
    title: str
    reason: str
    seo_score: float
    ctr_score: float
    audience_fit: float
    keywords: list[str] = field(default_factory=list)
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "reason": self.reason,
            "seo_score": round(self.seo_score, 4),
            "ctr_score": round(self.ctr_score, 4),
            "audience_fit": round(self.audience_fit, 4),
            "keywords": list(self.keywords),
            "selected": self.selected,
        }


@dataclass
class SeoDirectorPackage(SeoTitlePackage):
    candidates_ranked: list[dict[str, Any]] = field(default_factory=list)
    selection_reason: str = ""
    seo_data_source: str = "fallback_templates"
    dataforseo_used: bool = False
    serpapi_used: bool = False
    dataforseo_youtube_used: bool = False
    seo_keywords_used: list[str] = field(default_factory=list)
    related_queries_used: list[str] = field(default_factory=list)
    people_also_ask: list[str] = field(default_factory=list)
    search_intent: str = ""
    provider_intelligence: dict[str, Any] = field(default_factory=dict)
    openai_seo_polish: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["candidates_ranked"] = list(self.candidates_ranked)
        payload["selection_reason"] = self.selection_reason
        payload["seo_data_source"] = self.seo_data_source
        payload["dataforseo_used"] = self.dataforseo_used
        payload["serpapi_used"] = self.serpapi_used
        payload["dataforseo_youtube_used"] = self.dataforseo_youtube_used
        payload["seo_keywords_used"] = list(self.seo_keywords_used)
        payload["related_queries_used"] = list(self.related_queries_used)
        payload["people_also_ask"] = list(self.people_also_ask)
        payload["search_intent"] = self.search_intent
        payload["provider_intelligence"] = dict(self.provider_intelligence)
        payload["openai_seo_polish"] = dict(self.openai_seo_polish)
        payload["seo_director_version"] = SEO_DIRECTOR_VERSION
        return payload


def build_seo_director_package(
    *,
    topic: str,
    trends: list[dict[str, Any]] | None = None,
    platform: str = "youtube_shorts",
    language_code: str | None = None,
    mood: str = "emotional",
    max_chars: int = DEFAULT_MAX_CHARS,
    strategy_plan: ContentStrategyPlan | None = None,
    audience_level: str = "general",
    profile: dict[str, Any] | None = None,
    niche: str = "general",
    seo_intelligence: SeoProviderIntelligence | None = None,
    use_provider_bridge: bool = True,
) -> SeoDirectorPackage:
    cleaned_topic = re.sub(r"\s+", " ", str(topic or "").strip())
    lang = locale_or_detect(language_code, cleaned_topic)
    anchor = pick_title_anchor(cleaned_topic)
    subject = _extract_subject_phrase(cleaned_topic)
    angle = _pick_trend_angle(cleaned_topic, trends or [], lang)
    core_topic, action_topic = _normalize_topic_phrases(cleaned_topic)
    strategy_id = getattr(strategy_plan, "strategy_id", "") if strategy_plan else ""

    intel = seo_intelligence
    if intel is None and use_provider_bridge:
        intel = fetch_seo_provider_intelligence(
            topic=cleaned_topic,
            language_code=lang,
            platform=platform,
            profile=profile,
            trends=trends,
            niche=niche,
        )
    intel = intel or SeoProviderIntelligence()

    polish = polish_provider_seo_titles(
        topic=cleaned_topic,
        language_code=lang,
        provider_titles=intel.title_candidates_from_providers,
        seo_keywords=intel.seo_keywords,
        related_queries=intel.related_queries,
        people_also_ask=intel.people_also_ask,
        search_intent=intel.search_intent,
        strategy_id=strategy_id,
    )
    provider_titles = list(polish.titles or intel.title_candidates_from_providers)

    templates = _select_templates(strategy_id, lang, cleaned_topic)
    if strategy_plan is not None and strategy_plan.seo_title_candidates:
        strategy_templates = [
            _clean_strategy_template(item, cleaned_topic, subject=subject)
            for item in strategy_plan.seo_title_candidates
        ]
        templates = strategy_templates + templates

    candidates: list[SeoTitleCandidate] = []
    context = {
        "topic": cleaned_topic,
        "anchor": anchor,
        "subject": subject,
        "angle": angle,
        "core_topic": core_topic,
        "action_topic": action_topic,
        "mood": mood,
        "platform": platform,
    }

    def _append_candidate(title: str, reason: str, *, boost: float = 0.0) -> None:
        cleaned = _sanitize_seo_title(title, cleaned_topic, subject=subject)
        trimmed = _trim_title(cleaned, max_chars)
        if not trimmed or _is_bad_seo_title(trimmed, cleaned_topic, subject=subject):
            return
        if trimmed.lower() in {item.title.lower() for item in candidates}:
            return
        seo_score, ctr_score, audience_fit, scored_reason = _score_candidate(
            trimmed,
            cleaned_topic,
            anchor,
            angle,
            audience_level=audience_level,
        )
        if boost:
            seo_score = min(1.0, seo_score + boost)
            ctr_score = min(1.0, ctr_score + boost * 0.5)
        candidates.append(
            SeoTitleCandidate(
                title=trimmed,
                reason=reason or scored_reason,
                seo_score=seo_score,
                ctr_score=ctr_score,
                audience_fit=audience_fit,
                keywords=_build_keywords(
                    cleaned_topic,
                    trends or [],
                    anchor,
                    angle,
                    extra=intel.seo_keywords,
                )[:6],
            )
        )

    for title in provider_titles:
        _append_candidate(title, "provider_derived_title", boost=0.12)

    use_templates = not candidates or intel.seo_data_source == "fallback_templates"
    if use_templates:
        for template in templates:
            rendered = _render_template(template, context)
            _append_candidate(rendered, "strategy_template")

    if not candidates:
        fallback = _sanitize_seo_title(
            _title_case(subject or action_topic or core_topic or cleaned_topic),
            cleaned_topic,
            subject=subject,
        )
        candidates.append(
            SeoTitleCandidate(
                title=_trim_title(fallback, max_chars),
                reason="fallback_topic_title",
                seo_score=0.55,
                ctr_score=0.45,
                audience_fit=0.5,
            )
        )

    ranked = sorted(
        candidates,
        key=lambda item: (item.seo_score * 0.35 + item.ctr_score * 0.35 + item.audience_fit * 0.3),
        reverse=True,
    )
    selected = ranked[0]
    selected.selected = True
    keywords = _build_keywords(
        cleaned_topic,
        trends or [],
        anchor,
        angle,
        extra=intel.seo_keywords + intel.related_queries,
    )
    return SeoDirectorPackage(
        seo_title=selected.title,
        title_candidates=[item.title for item in ranked[:6]],
        keywords=keywords,
        trend_angle=angle,
        language_code=lang,
        seo_score=selected.seo_score,
        candidates_ranked=[item.to_dict() for item in ranked[:8]],
        selection_reason=selected.reason,
        seo_data_source=intel.seo_data_source,
        dataforseo_used=intel.dataforseo_used,
        serpapi_used=intel.serpapi_used,
        dataforseo_youtube_used=intel.dataforseo_youtube_used,
        seo_keywords_used=list(intel.seo_keywords),
        related_queries_used=list(intel.related_queries),
        people_also_ask=list(intel.people_also_ask),
        search_intent=intel.search_intent,
        provider_intelligence=intel.to_dict(),
        openai_seo_polish=polish.to_dict(),
    )


def _normalize_topic_phrases(topic: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", str(topic or "").strip())
    lowered = cleaned.lower()
    core = re.sub(r"^(how to|how-to|best|the)\s+", "", lowered, flags=re.I).strip()
    if "best" in lowered:
        core = re.sub(r"^best\s+", "", core, flags=re.I).strip()
    core = re.sub(r"^(make|master|learn)\s+", "", core, flags=re.I).strip()
    core = re.sub(r"\s+", " ", core)
    action = core
    if not lowered.startswith("how to") and not lowered.startswith("how-to"):
        action = f"how to {core}"
    return _title_case(core), _title_case(action)


def _select_templates(strategy_id: str, lang: str, topic: str) -> list[str]:
    lowered = topic.lower()
    if strategy_id == STRATEGY_FUTURE_ANALYSIS:
        return list(FUTURE_ANALYSIS_TEMPLATES.get(lang) or FUTURE_ANALYSIS_TEMPLATES["en"])
    if strategy_id == STRATEGY_BUSINESS_DEBATE:
        return list(BUSINESS_DEBATE_TEMPLATES.get(lang) or BUSINESS_DEBATE_TEMPLATES["en"])
    if strategy_id == STRATEGY_TECHNOLOGY_FORECAST:
        return list(TECHNOLOGY_FORECAST_TEMPLATES.get(lang) or TECHNOLOGY_FORECAST_TEMPLATES["en"])
    if strategy_id == STRATEGY_SCIENTIFIC_EXPLANATION:
        return list(SCIENTIFIC_TEMPLATES.get(lang) or SCIENTIFIC_TEMPLATES["en"])
    if strategy_id == STRATEGY_HISTORICAL_INVESTIGATION or any(
        word in lowered for word in ("roanoke", "colony", "croatoan", "what really happened", "what happened to")
    ):
        return list(DOCUMENTARY_TEMPLATES.get(lang) or DOCUMENTARY_TEMPLATES["en"]) + list(
            MYSTERY_TEMPLATES.get(lang) or MYSTERY_TEMPLATES["en"]
        )
    if strategy_id == STRATEGY_NARRATIVE_MYSTERY or (
        not strategy_id and any(word in lowered for word in ("mystery", "unsolved", "dyatlov", "case"))
    ):
        return list(MYSTERY_TEMPLATES.get(lang) or MYSTERY_TEMPLATES["en"])
    if strategy_id == STRATEGY_DOCUMENTARY or any(word in lowered for word in ("history", "documentary", "archival")):
        return list(DOCUMENTARY_TEMPLATES.get(lang) or DOCUMENTARY_TEMPLATES["en"])
    if strategy_id in INSTRUCTIONAL_STRATEGIES or lowered.startswith("how to"):
        return list(INSTRUCTIONAL_TEMPLATES.get(lang) or INSTRUCTIONAL_TEMPLATES["en"])
    if any(word in lowered for word in ("mystery", "unsolved", "pass", "disappearance")):
        return list(MYSTERY_TEMPLATES.get(lang) or MYSTERY_TEMPLATES["en"])
    return list(INSTRUCTIONAL_TEMPLATES.get(lang) or INSTRUCTIONAL_TEMPLATES["en"])


def _clean_strategy_template(template: str, topic: str, *, subject: str = "") -> str:
    core, action = _normalize_topic_phrases(topic)
    anchor = pick_title_anchor(topic)
    subject_phrase = subject or _extract_subject_phrase(topic)
    rendered = template.format(
        topic=subject_phrase,
        anchor=anchor,
        subject=subject_phrase,
        core_topic=core,
        action_topic=action,
    )
    return _sanitize_seo_title(rendered, topic, subject=subject_phrase)


def _sanitize_seo_title(title: str, topic: str, *, subject: str = "") -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    cleaned = re.sub(r"(?i)\bhow to\s+how to\b", "How to", cleaned)
    cleaned = re.sub(r"(?i)\bbest how to\b", "How to", cleaned)
    cleaned = re.sub(r"(?i)\bwhy best\b", "Why", cleaned)
    cleaned = re.sub(r"(?i)\bthe\s+the\b", "The", cleaned)
    cleaned = re.sub(r"(?i)\bmystery\s+mystery\b", "Mystery", cleaned)
    cleaned = re.sub(r"\s+That$", "", cleaned, flags=re.I)
    cleaned = re.sub(r":\s*Why\s+The\b", ": Why", cleaned, flags=re.I)
    if cleaned.lower() == topic.lower() and topic.lower().startswith("how to"):
        _, action = _normalize_topic_phrases(topic)
        cleaned = f"{action} Step by Step"
    subject_phrase = subject or _extract_subject_phrase(topic)
    if subject_phrase and subject_phrase.lower() in cleaned.lower():
        duplicate = re.search(
            rf"(?i)({re.escape(subject_phrase)}).*?\1",
            cleaned,
        )
        if duplicate:
            cleaned = subject_phrase
    return cleaned


def is_malformed_seo_title(title: str, topic: str = "", *, subject: str = "") -> bool:
    """Return True when a title is malformed or unnatural for the topic."""
    return _is_bad_seo_title(title, topic, subject=subject)


def _is_mystery_topic(topic: str) -> bool:
    lowered = str(topic or "").lower()
    return any(
        marker in lowered
        for marker in (
            "mystery",
            "unsolved",
            "dyatlov",
            "roanoke",
            "disappearance",
            "what really happened",
            "what happened to",
            "cold case",
        )
    )


def _is_bad_seo_title(title: str, topic: str, *, subject: str = "") -> bool:
    lowered = title.lower()
    topic_lower = topic.lower()
    subject_lower = (subject or _extract_subject_phrase(topic)).lower()
    if _is_raw_topic_duplicate(title, topic):
        return True
    if "how to how to" in lowered:
        return True
    if lowered == topic_lower and len(topic.split()) <= 4:
        return True
    if len(title.split()) < 3:
        return True
    if lowered.endswith(" that"):
        return True
    for pattern in MYSTERY_MALFORMED_SEO_PATTERNS:
        if re.search(pattern, lowered):
            return True
    if re.search(r"(?i)\bwhy\s+the\s+mystery\b", title):
        return True
    if _is_mystery_topic(topic):
        if re.search(r"(?i)\bwhy .+ matters\b", title):
            return True
        if re.search(r"(?i)\bnever works\b", title):
            return True
        if re.search(r"(?i)\bstop making this .+ mistake\b", title):
            return True
        if re.search(r"(?i)\bhow to .+ mystery\b", title) or re.search(r"(?i)\bhow to the mystery\b", title):
            return True
        if re.search(r"(?i)\bthe truth about the mystery of\b", title):
            return True
        if re.search(r"(?i)\bwhat everyone gets wrong about the mystery of\b", title):
            return True
        if re.search(r"(?i)\bthe real story behind the mystery of\b", title):
            return True
        if subject_lower and topic_lower in lowered and subject_lower in lowered:
            topic_words = [word for word in topic_lower.split() if len(word) > 3]
            overlap = sum(1 for word in topic_words if word in lowered)
            if overlap >= max(3, len(topic_words) - 1) and "?" not in title:
                return True
        words = lowered.split()
        if len(words) != len(set(words)) and any(
            word in {"mystery", "the", "of", "pass", "dyatlov"} for word in words
        ):
            return True
        if re.search(r"(?i)mystery of .+ mystery behind", title):
            return True
    return False


def _is_raw_topic_duplicate(title: str, topic: str) -> bool:
    title_tokens = _title_tokens(title)
    topic_tokens = _title_tokens(topic)
    if len(topic_tokens) < 4:
        return title_tokens == topic_tokens
    if title_tokens == topic_tokens:
        return True
    if len(title_tokens) >= len(topic_tokens) - 1:
        matches = sum(
            1
            for index, token in enumerate(topic_tokens)
            if index < len(title_tokens) and title_tokens[index] == token
        )
        if matches >= max(len(topic_tokens) - 2, int(len(topic_tokens) * 0.85)):
            return True
    return False


def _title_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s']", " ", str(text or "").lower())
    stop = {"by", "the", "a", "an", "in", "on", "of", "to", "for"}
    return [token for token in cleaned.split() if token and token not in stop]


def _score_candidate(
    title: str,
    topic: str,
    anchor: str,
    angle: str,
    *,
    audience_level: str,
) -> tuple[float, float, float, str]:
    seo = min(1.0, _topic_overlap(title, topic) * 1.2 + (0.2 if anchor.lower() in title.lower() else 0.0))
    ctr = 0.45
    if any(word in title.lower() for word in ("why", "mistake", "secret", "simple", "best", "stop")):
        ctr += 0.25
    if 28 <= len(title) <= 68:
        ctr += 0.1
    ctr = min(1.0, ctr)
    audience = 0.55
    if audience_level == "beginner" and "beginner" in title.lower():
        audience += 0.25
    if "step" in title.lower() or "guide" in title.lower() or "method" in title.lower():
        audience += 0.15
    audience = min(1.0, audience)
    reason = "balanced SEO/CTR/topic authority"
    if ctr >= 0.7:
        reason = "high CTR hook with topic authority"
    elif seo >= 0.75:
        reason = "strong SEO relevance"
    return seo, ctr, audience, reason


def _render_template(template: str, context: dict[str, str]) -> str:
    try:
        return re.sub(r"\s+", " ", template.format(**context)).strip()
    except KeyError:
        return re.sub(r"\s+", " ", template).strip()


def _title_case(text: str) -> str:
    parts = str(text or "").split()
    if not parts:
        return ""
    small = {"to", "for", "and", "in", "on", "of", "a", "an", "the"}
    result = []
    for index, part in enumerate(parts):
        if index > 0 and part.lower() in small:
            result.append(part.lower())
        else:
            result.append(part[:1].upper() + part[1:])
    return " ".join(result)


__all__ = [
    "SEO_DIRECTOR_VERSION",
    "MYSTERY_MALFORMED_SEO_PATTERNS",
    "SeoDirectorPackage",
    "SeoTitleCandidate",
    "build_seo_director_package",
    "is_malformed_seo_title",
]
