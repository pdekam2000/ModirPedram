"""
DataForSEO trend provider for the Viral Content Brain.

Uses keywords_for_keywords/live only. Credentials come from ProviderRegistryEngine.
Geo targeting resolves from profile/locale mapping — no hardcoded location_code.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

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


PROVIDER_NAME = "dataforseo"
API_ENDPOINT = (
    "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_keywords/live"
)
API_ENDPOINT_ID = "keywords_data/google_ads/keywords_for_keywords/live"

DEFAULT_LOCALE_KEY = "en"
MAX_KEYWORD_CHARS = 80
MAX_KEYWORD_WORDS = 10
MAX_SEED_KEYWORDS = 5
MAX_SEED_KEYWORDS_HARD = 20
MAX_SUGGESTIONS_PARSED = 50
REQUEST_COOLDOWN_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 30.0
RETRY_DELAY_SECONDS = 5.0

LANGUAGE_NAME_TO_CODE = {
    "english": "en",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "dutch": "nl",
    "polish": "pl",
    "turkish": "tr",
    "arabic": "ar",
    "hindi": "hi",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh",
}

COUNTRY_NAME_TO_LOCATION_CODE = {
    "united states": 2840,
    "usa": 2840,
    "us": 2840,
    "united kingdom": 2826,
    "uk": 2826,
    "great britain": 2826,
    "canada": 2124,
    "australia": 2036,
    "germany": 2276,
    "france": 2250,
    "spain": 2724,
    "italy": 2380,
    "netherlands": 2528,
    "brazil": 2076,
    "mexico": 2484,
    "india": 2356,
    "turkey": 2792,
    "saudi arabia": 2682,
    "uae": 2784,
    "united arab emirates": 2784,
}

LOCALE_GEO_MAP = {
    "default": {
        "location_code": 2840,
        "location_name": "United States",
        "language_code": "en",
    },
    "en": {
        "location_code": 2840,
        "location_name": "United States",
        "language_code": "en",
    },
    "en-us": {
        "location_code": 2840,
        "location_name": "United States",
        "language_code": "en",
    },
    "en-gb": {
        "location_code": 2826,
        "location_name": "United Kingdom",
        "language_code": "en",
    },
    "en-ca": {
        "location_code": 2124,
        "location_name": "Canada",
        "language_code": "en",
    },
    "en-au": {
        "location_code": 2036,
        "location_name": "Australia",
        "language_code": "en",
    },
    "de": {
        "location_code": 2276,
        "location_name": "Germany",
        "language_code": "de",
    },
    "de-de": {
        "location_code": 2276,
        "location_name": "Germany",
        "language_code": "de",
    },
    "fr": {
        "location_code": 2250,
        "location_name": "France",
        "language_code": "fr",
    },
    "es": {
        "location_code": 2724,
        "location_name": "Spain",
        "language_code": "es",
    },
    "es-mx": {
        "location_code": 2484,
        "location_name": "Mexico",
        "language_code": "es",
    },
    "it": {
        "location_code": 2380,
        "location_name": "Italy",
        "language_code": "it",
    },
    "pt": {
        "location_code": 2076,
        "location_name": "Brazil",
        "language_code": "pt",
    },
    "pt-br": {
        "location_code": 2076,
        "location_name": "Brazil",
        "language_code": "pt",
    },
    "nl": {
        "location_code": 2528,
        "location_name": "Netherlands",
        "language_code": "nl",
    },
    "pl": {
        "location_code": 2616,
        "location_name": "Poland",
        "language_code": "pl",
    },
    "tr": {
        "location_code": 2792,
        "location_name": "Turkey",
        "language_code": "tr",
    },
    "ar": {
        "location_code": 2682,
        "location_name": "Saudi Arabia",
        "language_code": "ar",
    },
    "hi": {
        "location_code": 2356,
        "location_name": "India",
        "language_code": "hi",
    },
    "ja": {
        "location_code": 2392,
        "location_name": "Japan",
        "language_code": "ja",
    },
    "ko": {
        "location_code": 2410,
        "location_name": "South Korea",
        "language_code": "ko",
    },
}

DRY_RUN_RESPONSE: dict[str, Any] = {
    "tasks": [
        {
            "result": [
                {
                    "items": [
                        {
                            "keyword": "late var replay angle",
                            "items": [
                                {
                                    "keyword": "var penalty controversy",
                                    "search_volume": 2400,
                                    "competition": "LOW",
                                    "competition_index": 18,
                                    "monthly_searches": [
                                        {"year": 2026, "month": 1, "search_volume": 1800},
                                        {"year": 2026, "month": 2, "search_volume": 2100},
                                        {"year": 2026, "month": 3, "search_volume": 2400},
                                    ],
                                },
                                {
                                    "keyword": "offside line disputes",
                                    "search_volume": 1600,
                                    "competition": "MEDIUM",
                                    "competition_index": 42,
                                    "monthly_searches": [
                                        {"year": 2026, "month": 1, "search_volume": 1500},
                                        {"year": 2026, "month": 2, "search_volume": 1550},
                                        {"year": 2026, "month": 3, "search_volume": 1600},
                                    ],
                                },
                            ],
                        }
                    ]
                }
            ]
        }
    ]
}


class DataForSEOTrendProvider(RealTrendProviderBase):
    """Live trend suggestions via DataForSEO Google Ads keywords_for_keywords."""

    provider_id = PROVIDER_NAME
    source_name = "dataforseo_google_ads"
    supports_live_fetch = True

    _last_request_at: float = 0.0

    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        max_seed_keywords: int = MAX_SEED_KEYWORDS,
        request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        dry_run: bool | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.max_seed_keywords = max(1, min(int(max_seed_keywords), MAX_SEED_KEYWORDS_HARD))
        self.request_timeout_seconds = request_timeout_seconds
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("DATAFORSEO_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        self._login = ""
        self._password = ""
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
        login = credentials.get("DATAFORSEO_LOGIN", "").strip()
        password = credentials.get("DATAFORSEO_PASSWORD", "").strip()

        if not login or not password:
            return False

        self._login = login
        self._password = password
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
        seeds = self._prepare_seed_keywords(context, niche)
        if not seeds:
            return []

        geo = resolve_geo_target(context)
        payload = [
            {
                "location_code": geo["location_code"],
                "language_code": geo["language_code"],
                "keywords": seeds,
            }
        ]

        if self.dry_run:
            response_data = DRY_RUN_RESPONSE
        else:
            if not self._login or not self._password:
                return []
            if not self._cooldown_ready():
                return []
            response_data = self._post_live(payload)

        suggestions = parse_keywords_for_keywords_response(response_data)
        if not suggestions:
            return []

        platforms = _resolve_platforms(context)
        now = datetime.now().strftime(TIMESTAMP_FORMAT)
        signals: list[NormalizedTrendSignal] = []

        for index, item in enumerate(suggestions[:MAX_SUGGESTIONS_PARSED]):
            keyword = str(item.get("keyword", "")).strip()
            if not keyword:
                continue

            niche_match = _score_niche_match(keyword, niche, context.profile)
            freshness, momentum = _score_freshness_and_momentum(
                item.get("monthly_searches", [])
            )
            confidence = _score_confidence(freshness, niche_match, index)

            metadata: dict[str, Any] = {
                "live_fetch": not self.dry_run,
                "api_endpoint": API_ENDPOINT_ID,
                "seed_keyword": str(item.get("seed_keyword", "")),
                "search_volume": _safe_int(item.get("search_volume")),
                "competition": item.get("competition"),
                "competition_index": _safe_int(item.get("competition_index")),
                "monthly_searches": _trim_monthly_searches(
                    item.get("monthly_searches", [])
                ),
                "location_code": geo["location_code"],
                "location_name": geo["location_name"],
                "language_code": geo["language_code"],
                "geo_source": geo.get("source", "locale_map"),
                "data_scope": "google_search",
                "volume_score": _score_live_confidence(
                    search_volume=_safe_int(item.get("search_volume")),
                    competition_index=_safe_int(item.get("competition_index")),
                    niche_match=niche_match,
                ),
            }
            if user_topic and str(item.get("seed_keyword", "")).strip() == sanitize_keyword(
                user_topic
            ):
                metadata["user_topic_authoritative"] = True
                metadata["priority"] = "user_topic"

            slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-") or "keyword"
            signals.append(
                NormalizedTrendSignal(
                    trend_topic=keyword,
                    source=self.source_name,
                    confidence=confidence,
                    freshness_score=freshness,
                    niche_match=niche_match,
                    momentum=momentum,
                    platforms=platforms,
                    provider_id=self.provider_id,
                    source_url="",
                    attribution=f"dataforseo://keywords_for_keywords/{slug}",
                    collected_at=now,
                    metadata=metadata,
                )
            )

        signals.sort(
            key=lambda signal: (
                signal.confidence,
                signal.metadata.get("search_volume", 0),
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

    def _prepare_seed_keywords(
        self,
        context: TrendProviderContext,
        niche: str,
    ) -> list[str]:
        raw_seeds = _collect_seed_topics(context, niche)
        sanitized: list[str] = []
        seen: set[str] = set()

        for seed in raw_seeds:
            cleaned = sanitize_keyword(seed)
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            sanitized.append(cleaned)
            if len(sanitized) >= self.max_seed_keywords:
                break

        return sanitized

    def _cooldown_ready(self) -> bool:
        elapsed = time.monotonic() - DataForSEOTrendProvider._last_request_at
        return elapsed >= REQUEST_COOLDOWN_SECONDS

    def _post_live(self, payload: list[dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        auth_token = base64.b64encode(
            f"{self._login}:{self._password}".encode("utf-8")
        ).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json",
        }

        for attempt in range(2):
            request = urllib.request.Request(
                API_ENDPOINT,
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                DataForSEOTrendProvider._last_request_at = time.monotonic()
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


def resolve_geo_target(context: TrendProviderContext) -> dict[str, Any]:
    """Resolve DataForSEO geo targeting from profile and locale."""
    profile = context.profile if isinstance(context.profile, dict) else {}
    trend_discovery = profile.get("trend_discovery", {})
    if not isinstance(trend_discovery, dict):
        trend_discovery = {}
    metadata = profile.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    explicit_code = _first_int(
        profile.get("location_code"),
        trend_discovery.get("location_code"),
        metadata.get("location_code"),
    )
    if explicit_code is not None:
        return {
            "location_code": explicit_code,
            "location_name": _first_str(
                profile.get("location_name"),
                trend_discovery.get("location_name"),
                metadata.get("location_name"),
            )
            or f"location_{explicit_code}",
            "language_code": _resolve_language_code(context, profile),
            "source": "profile.location_code",
        }

    for key in ("location_name", "country", "region", "market", "target_market"):
        for container in (profile, trend_discovery, metadata):
            if not isinstance(container, dict):
                continue
            location_code = _location_code_from_name(str(container.get(key, "")))
            if location_code is not None:
                return {
                    "location_code": location_code,
                    "location_name": str(container.get(key, "")).strip(),
                    "language_code": _resolve_language_code(context, profile),
                    "source": f"profile.{key}",
                }

    locale_key = _normalize_locale_key(context.locale)
    if locale_key in LOCALE_GEO_MAP:
        target = dict(LOCALE_GEO_MAP[locale_key])
        target["source"] = f"locale:{locale_key}"
        return target

    language_code = _resolve_language_code(context, profile)
    for key, target in LOCALE_GEO_MAP.items():
        if target.get("language_code") == language_code and key != "default":
            resolved = dict(target)
            resolved["source"] = f"language:{language_code}"
            return resolved

    fallback = dict(LOCALE_GEO_MAP[DEFAULT_LOCALE_KEY])
    fallback["source"] = f"locale_default:{DEFAULT_LOCALE_KEY}"
    return fallback


def sanitize_keyword(value: str) -> str:
    cleaned = re.sub(r"[^\w\s\-']", " ", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    if not cleaned:
        return ""

    words = cleaned.split()
    if len(words) > MAX_KEYWORD_WORDS:
        cleaned = " ".join(words[:MAX_KEYWORD_WORDS])

    if len(cleaned) > MAX_KEYWORD_CHARS:
        cleaned = cleaned[:MAX_KEYWORD_CHARS].rsplit(" ", 1)[0].strip()

    return cleaned


def parse_keywords_for_keywords_response(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []

    for task in payload.get("tasks", []):
        if not isinstance(task, dict):
            continue
        for result in task.get("result", []) or []:
            if not isinstance(result, dict):
                continue
            for seed_group in result.get("items", []) or []:
                if not isinstance(seed_group, dict):
                    continue
                seed_keyword = str(seed_group.get("keyword", "")).strip()
                nested_items = seed_group.get("items", []) or []
                if nested_items:
                    for item in nested_items:
                        if isinstance(item, dict):
                            enriched = dict(item)
                            enriched["seed_keyword"] = seed_keyword
                            suggestions.append(enriched)
                    continue
                if seed_group.get("keyword"):
                    suggestions.append(dict(seed_group))

    return suggestions


def _resolve_language_code(
    context: TrendProviderContext,
    profile: dict[str, Any],
) -> str:
    language_rules = profile.get("language_rules", {})
    if not isinstance(language_rules, dict):
        language_rules = {}

    for candidate in (
        profile.get("language"),
        language_rules.get("output_language"),
        context.locale,
    ):
        code = _language_name_to_code(str(candidate or ""))
        if code:
            return code

    locale_key = _normalize_locale_key(context.locale)
    if locale_key in LOCALE_GEO_MAP:
        return str(LOCALE_GEO_MAP[locale_key]["language_code"])

    return str(LOCALE_GEO_MAP[DEFAULT_LOCALE_KEY]["language_code"])


def _language_name_to_code(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if not normalized:
        return ""

    if re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", normalized):
        return normalized.split("-")[0]

    return LANGUAGE_NAME_TO_CODE.get(normalized, "")


def _normalize_locale_key(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if not normalized:
        return DEFAULT_LOCALE_KEY
    return normalized


def _location_code_from_name(value: str) -> int | None:
    normalized = value.strip().lower()
    if not normalized:
        return None

    if normalized.isdigit():
        return int(normalized)

    return COUNTRY_NAME_TO_LOCATION_CODE.get(normalized)


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_str(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _trim_monthly_searches(values: Any, limit: int = 6) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    trimmed = [item for item in values if isinstance(item, dict)]
    return trimmed[-limit:]


def _score_freshness_and_momentum(
    monthly_searches: Any,
) -> tuple[float, str]:
    if not isinstance(monthly_searches, list) or len(monthly_searches) < 2:
        return 0.65, TrendMomentum.STABLE.value

    volumes = [
        _safe_int(item.get("search_volume"))
        for item in monthly_searches
        if isinstance(item, dict)
    ]
    volumes = [volume for volume in volumes if volume >= 0]
    if len(volumes) < 2:
        return 0.65, TrendMomentum.STABLE.value

    recent = volumes[-3:] or volumes[-1:]
    older = volumes[:-3] or volumes[:1]
    recent_avg = sum(recent) / len(recent)
    older_avg = sum(older) / len(older)

    if older_avg <= 0:
        freshness = 0.7
    elif recent_avg >= older_avg * 1.35:
        freshness = 0.92
    elif recent_avg >= older_avg * 1.08:
        freshness = 0.82
    elif recent_avg <= older_avg * 0.85:
        freshness = 0.42
    else:
        freshness = 0.65

    if recent_avg >= older_avg * 1.35 and volumes[-1] >= recent_avg:
        momentum = TrendMomentum.SPIKING.value
    elif recent_avg >= older_avg * 1.08:
        momentum = TrendMomentum.RISING.value
    elif recent_avg <= older_avg * 0.85:
        momentum = TrendMomentum.COOLING.value
    else:
        momentum = TrendMomentum.STABLE.value

    return round(max(0.35, min(1.0, freshness)), 4), momentum


def _score_live_confidence(
    *,
    search_volume: int,
    competition_index: int,
    niche_match: float,
) -> float:
    volume_score = min(1.0, math.log10(max(search_volume, 1) + 1) / 5.0)
    competition_score = 1.0 - (max(0, min(competition_index, 100)) / 100.0)
    score = (0.35 * volume_score) + (0.25 * competition_score) + (0.4 * niche_match)
    return round(max(0.0, min(1.0, score)), 4)


__all__ = [
    "API_ENDPOINT_ID",
    "DataForSEOTrendProvider",
    "LOCALE_GEO_MAP",
    "parse_keywords_for_keywords_response",
    "resolve_geo_target",
    "sanitize_keyword",
]


if __name__ == "__main__":
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    engine = ProviderRegistryEngine() if ProviderRegistryEngine is not None else None
    provider = DataForSEOTrendProvider(registry_engine=engine, dry_run=True)

    print("=" * 72)
    print("DATAFORSEO TREND PROVIDER SMOKE")
    print("=" * 72)
    print("ENABLED:", provider.enabled)
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
    football_geo = resolve_geo_target(football_context)
    print("GEO (en-gb profile):", football_geo)

    user_context = TrendProviderContext(
        niche="football",
        topic="late VAR replay angle",
        profile=football_profile,
        max_results=5,
        locale="en",
    )
    print("SEEDS (user topic):", provider._prepare_seed_keywords(user_context, "football"))

    dry_signals = provider.fetch_trends(user_context)
    print("DRY-RUN SIGNAL COUNT:", len(dry_signals))
    for signal in dry_signals[:3]:
        print(
            f"- {signal.trend_topic} | confidence={signal.confidence} | "
            f"momentum={signal.momentum} | niche_match={signal.niche_match}"
        )

    allow_live = os.getenv("DATAFORSEO_ALLOW_LIVE_SMOKE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if allow_live and provider.enabled:
        live_provider = DataForSEOTrendProvider(registry_engine=engine, dry_run=False)
        live_signals = live_provider.fetch_trends(user_context)
        print("LIVE SIGNAL COUNT:", len(live_signals))
        for signal in live_signals[:3]:
            print(f"- {signal.trend_topic} | volume={signal.metadata.get('search_volume')}")
