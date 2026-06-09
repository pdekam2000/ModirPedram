"""
SEO Provider Bridge — DataForSEO + SerpAPI intelligence for SEO Director.

Fetches keyword suggestions, SERP People Also Ask, related searches, and YouTube titles
when credentials are available. Falls back cleanly when APIs are unavailable.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_topic_story_detail import _extract_subject_phrase
from content_brain.providers.dataforseo_trend_provider import (
    DataForSEOTrendProvider,
    resolve_geo_target,
    sanitize_keyword,
)
from content_brain.providers.real_trend_provider import TrendProviderContext
from content_brain.providers.serpapi_trend_provider import SerpAPITrendProvider

try:
    from content_brain.providers.dataforseo_youtube_trend_provider import DataForSEOYouTubeTrendProvider
except ImportError:  # pragma: no cover
    DataForSEOYouTubeTrendProvider = None  # type: ignore[misc, assignment]

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]

BRIDGE_VERSION = "seo_provider_bridge_v1"
GOOGLE_SERP_ENDPOINT = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
REQUEST_TIMEOUT_SECONDS = 30.0
REQUEST_COOLDOWN_SECONDS = 5.0
_last_serp_request_at = 0.0

MARKETING_SEO_DRY_RUN: dict[str, Any] = {
    "keywords": [
        "AI marketing automation",
        "marketing agency disruption",
        "AI replace marketing agencies",
        "performance marketing AI tools",
        "agency economics 2026",
        "campaign automation software",
    ],
    "related_queries": [
        "will ai replace marketing agencies",
        "ai agency automation 2026",
        "future of marketing agencies",
        "ai tools for digital agencies",
    ],
    "people_also_ask": [
        "Will AI replace digital marketing jobs?",
        "Can AI run a marketing agency?",
        "What will happen to agencies in 2026?",
    ],
    "related_searches": [
        "AI marketing agency tools",
        "marketing agency future",
        "automation for ad agencies",
    ],
    "youtube_titles": [
        "Will AI Replace Marketing Agencies by 2026?",
        "The AI Threat Most Agencies Ignore",
        "Can Agencies Survive the AI Revolution?",
    ],
    "search_intent": "informational_debate",
}

GOOGLE_SERP_DRY_RUN: dict[str, Any] = {
    "tasks": [
        {
            "result": [
                {
                    "items": [
                        {
                            "type": "people_also_ask",
                            "items": [
                                {"title": "Will AI replace marketing agencies?"},
                                {"title": "How is AI changing digital marketing?"},
                            ],
                        },
                        {
                            "type": "related_searches",
                            "items": [
                                {"title": "AI marketing automation"},
                                {"title": "future of advertising agencies"},
                            ],
                        },
                    ]
                }
            ]
        }
    ]
}


@dataclass
class SeoProviderIntelligence:
    seo_keywords: list[str] = field(default_factory=list)
    related_queries: list[str] = field(default_factory=list)
    people_also_ask: list[str] = field(default_factory=list)
    related_searches: list[str] = field(default_factory=list)
    youtube_titles: list[str] = field(default_factory=list)
    trend_terms: list[str] = field(default_factory=list)
    search_intent: str = ""
    title_candidates_from_providers: list[str] = field(default_factory=list)
    dataforseo_used: bool = False
    serpapi_used: bool = False
    dataforseo_youtube_used: bool = False
    seo_data_source: str = "fallback_templates"
    provider_notes: list[str] = field(default_factory=list)
    raw_provider_outputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge_version": BRIDGE_VERSION,
            "seo_keywords_used": list(self.seo_keywords),
            "related_queries_used": list(self.related_queries),
            "people_also_ask": list(self.people_also_ask),
            "related_searches": list(self.related_searches),
            "youtube_titles": list(self.youtube_titles),
            "trend_terms": list(self.trend_terms),
            "search_intent": self.search_intent,
            "title_candidates_from_providers": list(self.title_candidates_from_providers),
            "dataforseo_used": self.dataforseo_used,
            "serpapi_used": self.serpapi_used,
            "dataforseo_youtube_used": self.dataforseo_youtube_used,
            "seo_data_source": self.seo_data_source,
            "provider_notes": list(self.provider_notes),
            "raw_provider_outputs": dict(self.raw_provider_outputs),
        }


def fetch_seo_provider_intelligence(
    *,
    topic: str,
    language_code: str = "en",
    platform: str = "youtube_shorts",
    profile: dict[str, Any] | None = None,
    trends: list[dict[str, Any]] | None = None,
    niche: str = "general",
) -> SeoProviderIntelligence:
    cleaned_topic = re.sub(r"\s+", " ", str(topic or "").strip())
    profile_payload = dict(profile or {})
    profile_payload.setdefault("language", language_code)
    context = TrendProviderContext(
        niche=niche,
        topic=cleaned_topic,
        profile=profile_payload,
        platforms=[platform],
        max_results=10,
        locale=language_code,
    )
    intel = SeoProviderIntelligence()
    intel.search_intent = infer_search_intent(cleaned_topic)

    if _use_marketing_dry_run(cleaned_topic):
        _apply_marketing_dry_run(intel)
        intel.seo_data_source = "live_providers_dry_run"
        _finalize_provider_titles(intel, cleaned_topic)
        return intel

    engine = _get_registry_engine()
    dataforseo_ready = bool(
        engine
        and engine.credentials_ready(ProviderRegistryEngine.TREND_CATEGORY, "dataforseo")
    )
    serpapi_ready = bool(
        engine
        and engine.credentials_ready(ProviderRegistryEngine.TREND_CATEGORY, "serpapi")
    )
    youtube_ready = bool(
        engine
        and engine.credentials_ready(ProviderRegistryEngine.TREND_CATEGORY, "dataforseo_youtube")
    )

    if dataforseo_ready:
        _fetch_dataforseo_keywords(context, intel)
        _fetch_dataforseo_google_serp(context, intel)

    if serpapi_ready:
        _fetch_serpapi_related(context, intel)

    if youtube_ready and "youtube" in platform.lower():
        _fetch_dataforseo_youtube(context, intel)

    live_trends = _extract_live_trend_terms(trends or [])
    intel.trend_terms = list(dict.fromkeys(intel.trend_terms + live_trends))[:12]

    if intel.dataforseo_used or intel.serpapi_used or intel.dataforseo_youtube_used:
        intel.seo_data_source = "live_providers"
    else:
        intel.seo_data_source = "fallback_templates"
        intel.provider_notes.append("no_live_seo_providers_available")

    _finalize_provider_titles(intel, cleaned_topic)
    return intel


def infer_search_intent(topic: str) -> str:
    lowered = str(topic or "").lower()
    if lowered.startswith("how to") or lowered.startswith("how-to"):
        return "tutorial"
    if any(word in lowered for word in ("why", "what is", "what are")):
        return "informational"
    if "?" in lowered and any(word in lowered for word in ("will", "can", "could", "destroy", "replace")):
        return "informational_debate"
    if any(word in lowered for word in ("best", "top", "review")):
        return "commercial"
    return "informational"


def _use_marketing_dry_run(topic: str) -> bool:
    if os.getenv("SEO_PROVIDER_DRY_RUN", "").strip().lower() not in {"1", "true", "yes"}:
        return False
    lowered = topic.lower()
    return "marketing" in lowered and "agenc" in lowered


def _apply_marketing_dry_run(intel: SeoProviderIntelligence) -> None:
    intel.seo_keywords = list(MARKETING_SEO_DRY_RUN["keywords"])
    intel.related_queries = list(MARKETING_SEO_DRY_RUN["related_queries"])
    intel.people_also_ask = list(MARKETING_SEO_DRY_RUN["people_also_ask"])
    intel.related_searches = list(MARKETING_SEO_DRY_RUN["related_searches"])
    intel.youtube_titles = list(MARKETING_SEO_DRY_RUN["youtube_titles"])
    intel.trend_terms = list(MARKETING_SEO_DRY_RUN["related_queries"])
    intel.search_intent = str(MARKETING_SEO_DRY_RUN["search_intent"])
    intel.dataforseo_used = True
    intel.serpapi_used = True
    intel.dataforseo_youtube_used = True
    intel.provider_notes.append("seo_provider_dry_run_marketing_pack")


def _fetch_dataforseo_keywords(context: TrendProviderContext, intel: SeoProviderIntelligence) -> None:
    provider = DataForSEOTrendProvider()
    if not provider.enabled:
        return
    signals = provider.fetch_trends(context)
    keywords = [str(signal.trend_topic).strip() for signal in signals if str(signal.trend_topic).strip()]
    if keywords:
        intel.seo_keywords = list(dict.fromkeys(keywords))[:12]
        intel.trend_terms.extend(keywords[:6])
        intel.dataforseo_used = True
        intel.provider_notes.append("dataforseo_keywords_for_keywords")
        intel.raw_provider_outputs["dataforseo_keywords"] = [signal.to_dict() for signal in signals[:8]]


def _fetch_dataforseo_google_serp(context: TrendProviderContext, intel: SeoProviderIntelligence) -> None:
    provider = DataForSEOTrendProvider()
    if not provider.enabled and not provider.dry_run:
        return
    seed = sanitize_keyword(context.topic) or sanitize_keyword(_extract_subject_phrase(context.topic))
    if not seed:
        return
    geo = resolve_geo_target(context)
    payload = [
        {
            "keyword": seed,
            "location_code": geo["location_code"],
            "language_code": geo["language_code"],
            "device": "mobile",
            "os": "android",
            "depth": 10,
        }
    ]
    if provider.dry_run or os.getenv("DATAFORSEO_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}:
        response = GOOGLE_SERP_DRY_RUN if _is_marketing_topic(context.topic) else GOOGLE_SERP_DRY_RUN
    else:
        response = _post_dataforseo_endpoint(
            GOOGLE_SERP_ENDPOINT,
            payload,
            login=getattr(provider, "_login", ""),
            password=getattr(provider, "_password", ""),
        )
    paa, related = parse_google_serp_extras(response)
    if paa:
        intel.people_also_ask = list(dict.fromkeys(intel.people_also_ask + paa))[:8]
    if related:
        intel.related_searches = list(dict.fromkeys(intel.related_searches + related))[:8]
    if paa or related:
        intel.dataforseo_used = True
        intel.provider_notes.append("dataforseo_google_serp")
        intel.raw_provider_outputs["dataforseo_serp"] = {"people_also_ask": paa, "related_searches": related}


def _fetch_serpapi_related(context: TrendProviderContext, intel: SeoProviderIntelligence) -> None:
    provider = SerpAPITrendProvider()
    if not provider.enabled:
        return
    signals = provider.fetch_trends(context)
    queries = [str(signal.trend_topic).strip() for signal in signals if str(signal.trend_topic).strip()]
    if queries:
        intel.related_queries = list(dict.fromkeys(intel.related_queries + queries))[:12]
        intel.trend_terms.extend(queries[:6])
        intel.serpapi_used = True
        intel.provider_notes.append("serpapi_google_trends_related_queries")
        intel.raw_provider_outputs["serpapi_related"] = [signal.to_dict() for signal in signals[:8]]


def _fetch_dataforseo_youtube(context: TrendProviderContext, intel: SeoProviderIntelligence) -> None:
    if DataForSEOYouTubeTrendProvider is None:
        return
    provider = DataForSEOYouTubeTrendProvider()
    if not provider.enabled:
        return
    signals = provider.fetch_trends(context)
    titles = []
    for signal in signals:
        title = str(signal.metadata.get("title") or signal.trend_topic or "").strip()
        if title:
            titles.append(title)
    if titles:
        intel.youtube_titles = list(dict.fromkeys(intel.youtube_titles + titles))[:8]
        intel.dataforseo_youtube_used = True
        intel.provider_notes.append("dataforseo_youtube_organic")
        intel.raw_provider_outputs["dataforseo_youtube"] = [signal.to_dict() for signal in signals[:8]]


def _finalize_provider_titles(intel: SeoProviderIntelligence, topic: str) -> None:
    candidates: list[str] = []
    for group in (
        intel.youtube_titles,
        intel.people_also_ask,
        intel.related_queries,
        intel.related_searches,
        intel.seo_keywords,
        intel.trend_terms,
    ):
        for item in group:
            cleaned = _normalize_provider_title(str(item), topic)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
    intel.title_candidates_from_providers = candidates[:12]


def _normalize_provider_title(title: str, topic: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    if not cleaned:
        return ""
    if cleaned.endswith("?"):
        cleaned = cleaned[0].upper() + cleaned[1:]
    else:
        cleaned = cleaned[0].upper() + cleaned[1:] if cleaned else cleaned
    if _is_near_duplicate_topic(cleaned, topic):
        return ""
    return cleaned[:72]


def _is_near_duplicate_topic(title: str, topic: str) -> bool:
    title_tokens = _tokenize(title)
    topic_tokens = _tokenize(topic)
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


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s']", " ", str(text or "").lower())
    stop = {"by", "the", "a", "an", "in", "on", "of", "to", "for"}
    return [token for token in cleaned.split() if token and token not in stop]


def _extract_live_trend_terms(trends: list[dict[str, Any]]) -> list[str]:
    terms: list[str] = []
    for item in trends:
        source = str(item.get("source") or item.get("provider_id") or "")
        if source in {"manual_seed", "mock_trend_provider", "simulated_local", "profile_seed"}:
            continue
        trend = str(item.get("trend") or item.get("topic") or "").strip()
        if trend:
            terms.append(trend)
    return list(dict.fromkeys(terms))[:10]


def parse_google_serp_extras(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    paa: list[str] = []
    related: list[str] = []
    for task in payload.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        for result in task.get("result", []) or []:
            if not isinstance(result, dict):
                continue
            for item in result.get("items", []) or []:
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type") or "").lower()
                nested = item.get("items") or []
                if item_type == "people_also_ask":
                    for nested_item in nested:
                        if isinstance(nested_item, dict):
                            title = str(nested_item.get("title") or nested_item.get("question") or "").strip()
                            if title:
                                paa.append(title)
                if item_type == "related_searches":
                    for nested_item in nested:
                        if isinstance(nested_item, dict):
                            title = str(nested_item.get("title") or nested_item.get("query") or "").strip()
                            if title:
                                related.append(title)
    return list(dict.fromkeys(paa)), list(dict.fromkeys(related))


def _post_dataforseo_endpoint(
    endpoint: str,
    payload: list[dict[str, Any]],
    *,
    login: str,
    password: str,
) -> dict[str, Any]:
    global _last_serp_request_at
    if not login or not password:
        return {}
    elapsed = time.monotonic() - _last_serp_request_at
    if elapsed < REQUEST_COOLDOWN_SECONDS:
        time.sleep(max(0.0, REQUEST_COOLDOWN_SECONDS - elapsed))
    body = json.dumps(payload).encode("utf-8")
    auth_token = base64.b64encode(f"{login}:{password}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        _last_serp_request_at = time.monotonic()
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return {}


def _get_registry_engine() -> Any | None:
    if ProviderRegistryEngine is None:
        return None
    try:
        return ProviderRegistryEngine()
    except Exception:
        return None


def _is_marketing_topic(topic: str) -> bool:
    lowered = str(topic or "").lower()
    return "marketing" in lowered and "agenc" in lowered


__all__ = [
    "BRIDGE_VERSION",
    "SeoProviderIntelligence",
    "fetch_seo_provider_intelligence",
    "infer_search_intent",
    "parse_google_serp_extras",
]
