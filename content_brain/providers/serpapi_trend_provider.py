"""
SerpAPI trend provider for the Viral Content Brain.

Uses google_trends / RELATED_QUERIES only. Credentials come from ProviderRegistryEngine.
Geo targeting resolves from profile/locale via shared seed/geo helpers.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from content_brain.providers.dataforseo_trend_provider import (
    sanitize_keyword,
    resolve_geo_target,
)
from content_brain.providers.real_trend_provider import (
    NormalizedTrendSignal,
    RealTrendProviderBase,
    TIMESTAMP_FORMAT,
    TrendMomentum,
    TrendProviderContext,
    _collect_seed_topics,
    _resolve_platforms,
    _score_confidence,
    _score_niche_match,
)

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover - defensive import
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]


PROVIDER_NAME = "serpapi"
API_BASE_URL = "https://serpapi.com/search.json"
API_ENGINE = "google_trends"
API_DATA_TYPE = "RELATED_QUERIES"
API_DATE_RANGE = "today 3-m"

DEFAULT_SEED_LIMIT = 1
MAX_SEED_LIMIT = 1
MAX_RESULTS_PARSED = 25
REQUEST_COOLDOWN_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 30.0
RETRY_DELAY_SECONDS = 5.0

LOCATION_CODE_TO_GEO = {
    2840: "US",
    2826: "GB",
    2124: "CA",
    2036: "AU",
    2276: "DE",
    2250: "FR",
    2724: "ES",
    2380: "IT",
    2528: "NL",
    2076: "BR",
    2484: "MX",
    2356: "IN",
    2792: "TR",
    2682: "SA",
    2784: "AE",
    2616: "PL",
    2392: "JP",
    2410: "KR",
}

LOCALE_TO_GEO = {
    "en": "US",
    "en-us": "US",
    "en-gb": "GB",
    "en-ca": "CA",
    "en-au": "AU",
    "de": "DE",
    "de-de": "DE",
    "fr": "FR",
    "es": "ES",
    "es-mx": "MX",
    "it": "IT",
    "pt": "BR",
    "pt-br": "BR",
    "nl": "NL",
    "pl": "PL",
    "tr": "TR",
    "ar": "SA",
    "hi": "IN",
    "ja": "JP",
    "ko": "KR",
}

DRY_RUN_RESPONSE: dict[str, Any] = {
    "related_queries": {
        "rising": [
            {
                "query": "var penalty controversy",
                "value": "+180%",
                "extracted_value": 180,
                "link": "https://trends.google.com/trends/explore?q=var+penalty+controversy",
            },
            {
                "query": "offside line disputes",
                "value": "+120%",
                "extracted_value": 120,
                "link": "https://trends.google.com/trends/explore?q=offside+line+disputes",
            },
        ],
        "top": [
            {
                "query": "football referee decisions",
                "value": "100",
                "extracted_value": 100,
                "link": "https://trends.google.com/trends/explore?q=football+referee+decisions",
            },
        ],
    }
}


class SerpAPITrendProvider(RealTrendProviderBase):
    """Live trend suggestions via SerpAPI Google Trends related queries."""

    provider_id = PROVIDER_NAME
    source_name = "serpapi_google_trends"
    supports_live_fetch = True

    _last_request_at: float = 0.0

    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        seed_limit: int = DEFAULT_SEED_LIMIT,
        max_results_parsed: int = MAX_RESULTS_PARSED,
        request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        dry_run: bool | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.seed_limit = max(1, min(int(seed_limit), MAX_SEED_LIMIT))
        self.max_results_parsed = max(1, int(max_results_parsed))
        self.request_timeout_seconds = request_timeout_seconds
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("SERPAPI_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        self._api_key = ""
        credential_enabled = self._resolve_enabled_state()
        self.enabled = credential_enabled or self.dry_run

    def _get_registry_engine(self) -> Any:
        if self.registry_engine is not None:
            return self.registry_engine
        if ProviderRegistryEngine is None:
            raise RuntimeError("ProviderRegistryEngine is unavailable.")
        return ProviderRegistryEngine()

    def _resolve_enabled_state(self) -> bool:
        try:
            engine = self._get_registry_engine()
        except Exception:
            return False

        if not engine.credentials_ready(
            ProviderRegistryEngine.TREND_CATEGORY,
            PROVIDER_NAME,
        ):
            return False

        credentials = engine.get_provider_credentials(
            ProviderRegistryEngine.TREND_CATEGORY,
            PROVIDER_NAME,
        )
        api_key = credentials.get("SERPAPI_API_KEY", "").strip()
        if not api_key:
            return False

        self._api_key = api_key
        return True

    def fetch_trends(self, context: TrendProviderContext) -> list[NormalizedTrendSignal]:
        if not self.enabled:
            return []

        try:
            return self._fetch_trends_safe(context)
        except Exception:
            return []

    def _fetch_trends_safe(
        self,
        context: TrendProviderContext,
    ) -> list[NormalizedTrendSignal]:
        niche = context.niche.strip() or str(context.profile.get("niche", "general"))
        user_topic = context.topic.strip()
        seed_query = self._select_seed_query(context, niche)
        if not seed_query:
            return []

        geo = resolve_serpapi_geo(context)

        if self.dry_run:
            response_data = DRY_RUN_RESPONSE
        else:
            if not self._api_key:
                return []
            if not self._cooldown_ready():
                return []
            response_data = self._get_live(seed_query, geo)

        parsed_items = parse_related_queries_response(response_data)
        if not parsed_items:
            return []

        platforms = _resolve_platforms(context)
        now = datetime.now().strftime(TIMESTAMP_FORMAT)
        signals: list[NormalizedTrendSignal] = []

        for index, item in enumerate(parsed_items[: self.max_results_parsed]):
            query = str(item.get("query", "")).strip()
            if not query:
                continue

            niche_match = _score_niche_match(query, niche, context.profile)
            freshness, momentum = _score_trend_freshness_and_momentum(item)
            confidence = _score_confidence(freshness, niche_match, index)
            extracted_value = _safe_int(item.get("extracted_value"))

            metadata: dict[str, Any] = {
                "live_fetch": not self.dry_run,
                "api_engine": API_ENGINE,
                "data_type": API_DATA_TYPE,
                "seed_query": seed_query,
                "trend_bucket": str(item.get("trend_bucket", "")),
                "growth_value": item.get("value"),
                "extracted_value": extracted_value,
                "geo": geo.get("geo"),
                "hl": geo.get("hl"),
                "location_name": geo.get("location_name"),
                "geo_source": geo.get("source", "locale_map"),
                "growth_score": _score_growth(extracted_value),
            }
            if user_topic and seed_query == sanitize_keyword(user_topic):
                metadata["user_topic_authoritative"] = True
                metadata["priority"] = "user_topic"

            slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-") or "query"
            signals.append(
                NormalizedTrendSignal(
                    trend_topic=query,
                    source=self.source_name,
                    confidence=confidence,
                    freshness_score=freshness,
                    niche_match=niche_match,
                    momentum=momentum,
                    platforms=platforms,
                    provider_id=self.provider_id,
                    source_url=str(item.get("link", "")),
                    attribution=f"serpapi://google_trends/related_queries/{slug}",
                    collected_at=now,
                    metadata=metadata,
                )
            )

        signals.sort(
            key=lambda signal: (
                1 if signal.metadata.get("trend_bucket") == "rising" else 0,
                signal.metadata.get("extracted_value", 0),
                signal.confidence,
            ),
            reverse=True,
        )

        deduped: list[NormalizedTrendSignal] = []
        seen: set[str] = set()
        for signal in signals:
            key = signal.trend_topic.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(signal)
            if len(deduped) >= max(1, int(context.max_results)):
                break

        return deduped

    def _select_seed_query(
        self,
        context: TrendProviderContext,
        niche: str,
    ) -> str:
        raw_seeds = _collect_seed_topics(context, niche)
        for seed in raw_seeds[: self.seed_limit]:
            cleaned = sanitize_keyword(seed)
            if cleaned:
                return cleaned
        return ""

    def _cooldown_ready(self) -> bool:
        elapsed = time.monotonic() - SerpAPITrendProvider._last_request_at
        return elapsed >= REQUEST_COOLDOWN_SECONDS

    def _get_live(
        self,
        seed_query: str,
        geo: dict[str, Any],
    ) -> dict[str, Any]:
        params = {
            "engine": API_ENGINE,
            "data_type": API_DATA_TYPE,
            "q": seed_query,
            "date": API_DATE_RANGE,
            "geo": str(geo.get("geo", "")),
            "hl": str(geo.get("hl", "en")),
            "api_key": self._api_key,
        }
        query_string = urllib.parse.urlencode(params)
        url = f"{API_BASE_URL}?{query_string}"

        for attempt in range(2):
            request = urllib.request.Request(url, method="GET")
            try:
                SerpAPITrendProvider._last_request_at = time.monotonic()
                with urllib.request.urlopen(
                    request,
                    timeout=self.request_timeout_seconds,
                ) as response:
                    raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
                return {}
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt == 0:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                return {}
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                return {}

        return {}


def resolve_serpapi_geo(context: TrendProviderContext) -> dict[str, Any]:
    """Resolve SerpAPI geo/hl targeting from profile and locale."""
    profile = context.profile if isinstance(context.profile, dict) else {}
    dfs_target = resolve_geo_target(context)

    location_code = dfs_target.get("location_code")
    geo_code = LOCATION_CODE_TO_GEO.get(location_code) if location_code is not None else None

    if not geo_code:
        locale_key = _normalize_locale_key(context.locale)
        geo_code = LOCALE_TO_GEO.get(locale_key)

    if not geo_code:
        geo_code = LOCALE_TO_GEO.get("en", "US")

    language_code = str(dfs_target.get("language_code", "en")).strip() or "en"

    return {
        "geo": geo_code,
        "hl": language_code,
        "location_name": dfs_target.get("location_name", geo_code),
        "source": dfs_target.get("source", "locale_map"),
    }


def parse_related_queries_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    related = payload.get("related_queries", {})
    if not isinstance(related, dict):
        return []

    parsed: list[dict[str, Any]] = []

    rising = related.get("rising", [])
    if isinstance(rising, list):
        for item in rising:
            if isinstance(item, dict) and str(item.get("query", "")).strip():
                enriched = dict(item)
                enriched["trend_bucket"] = "rising"
                parsed.append(enriched)

    top = related.get("top", [])
    if isinstance(top, list):
        for item in top:
            if isinstance(item, dict) and str(item.get("query", "")).strip():
                enriched = dict(item)
                enriched["trend_bucket"] = "top"
                parsed.append(enriched)

    return parsed


def _normalize_locale_key(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    return normalized or "en"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _score_growth(extracted_value: int) -> float:
    if extracted_value <= 0:
        return 0.35
    return round(min(1.0, math.log10(extracted_value + 1) / 3.5), 4)


def _score_trend_freshness_and_momentum(item: dict[str, Any]) -> tuple[float, str]:
    bucket = str(item.get("trend_bucket", "")).strip().lower()
    extracted_value = _safe_int(item.get("extracted_value"))

    if bucket == "rising":
        if extracted_value >= 300:
            return 0.93, TrendMomentum.SPIKING.value
        if extracted_value >= 100:
            return 0.86, TrendMomentum.RISING.value
        return 0.78, TrendMomentum.RISING.value

    if extracted_value >= 80:
        return 0.68, TrendMomentum.STABLE.value
    return 0.58, TrendMomentum.STABLE.value


__all__ = [
    "API_DATA_TYPE",
    "API_ENGINE",
    "SerpAPITrendProvider",
    "parse_related_queries_response",
    "resolve_serpapi_geo",
]


if __name__ == "__main__":
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    engine = ProviderRegistryEngine() if ProviderRegistryEngine is not None else None
    provider = SerpAPITrendProvider(registry_engine=engine, dry_run=True)

    print("=" * 72)
    print("SERPAPI TREND PROVIDER SMOKE")
    print("=" * 72)
    print("ENABLED:", provider.enabled)
    print("SEED LIMIT:", provider.seed_limit)
    if engine is not None:
        print(
            "CREDENTIALS READY:",
            engine.credentials_ready(ProviderRegistryEngine.TREND_CATEGORY, PROVIDER_NAME),
        )

    football_profile = loader.resolve(niche="football")
    football_context = TrendProviderContext(
        niche="football",
        topic="",
        profile=football_profile,
        max_results=5,
        locale="en-gb",
    )
    print("GEO (en-gb profile):", resolve_serpapi_geo(football_context))

    user_context = TrendProviderContext(
        niche="football",
        topic="late VAR replay angle",
        profile=football_profile,
        max_results=5,
        locale="en",
    )
    print("SEED QUERY (user topic):", provider._select_seed_query(user_context, "football"))

    dry_signals = provider.fetch_trends(user_context)
    print("DRY-RUN SIGNAL COUNT:", len(dry_signals))
    for signal in dry_signals[:3]:
        print(
            f"- {signal.trend_topic} | confidence={signal.confidence} | "
            f"momentum={signal.momentum} | bucket={signal.metadata.get('trend_bucket')}"
        )

    allow_live = os.getenv("SERPAPI_ALLOW_LIVE_SMOKE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if allow_live and provider.enabled and provider._api_key:
        live_provider = SerpAPITrendProvider(registry_engine=engine, dry_run=False)
        live_signals = live_provider.fetch_trends(user_context)
        print("LIVE SIGNAL COUNT:", len(live_signals))
        for signal in live_signals[:3]:
            print(
                f"- {signal.trend_topic} | growth={signal.metadata.get('extracted_value')}"
            )
