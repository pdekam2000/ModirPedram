"""
DataForSEO YouTube SERP trend provider for the Viral Content Brain.

Uses serp/youtube/organic/live/advanced only. Credentials come from
ProviderRegistryEngine (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD).
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from content_brain.providers.dataforseo_trend_provider import sanitize_keyword
from content_brain.providers.real_trend_provider import (
    NormalizedTrendSignal,
    RealTrendProviderBase,
    TIMESTAMP_FORMAT,
    TrendMomentum,
    TrendProviderContext,
    _collect_seed_topics,
    _score_confidence,
    _score_niche_match,
)

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover - defensive import
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]


PROVIDER_NAME = "dataforseo_youtube"
API_ENDPOINT = "https://api.dataforseo.com/v3/serp/youtube/organic/live/advanced"
API_ENDPOINT_ID = "serp/youtube/organic/live/advanced"

SEARCH_ENGINE = "youtube"
SE_TYPE = "organic"
DEFAULT_LOCATION_NAME = "United States"
DEFAULT_LANGUAGE_NAME = "English"
DEFAULT_DEVICE = "mobile"
DEFAULT_OS = "android"
DEFAULT_DEPTH = 20

MAX_YOUTUBE_SEEDS = 1
MAX_RESULTS_PARSED = 20
REQUEST_COOLDOWN_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 30.0
RETRY_DELAY_SECONDS = 5.0

DRY_RUN_RESPONSE: dict[str, Any] = {
    "tasks": [
        {
            "result": [
                {
                    "keyword": "late var replay angle",
                    "items": [
                        {
                            "type": "youtube_video",
                            "rank_group": 1,
                            "rank_absolute": 1,
                            "title": "Why this VAR replay changed the entire match",
                            "url": "https://www.youtube.com/watch?v=dryrun001",
                            "channel_name": "Match Review Daily",
                        },
                        {
                            "type": "youtube_video",
                            "rank_group": 2,
                            "rank_absolute": 2,
                            "title": "Offside line disputes explained in 60 seconds",
                            "url": "https://www.youtube.com/watch?v=dryrun002",
                            "channel_name": "Tactics Breakdown",
                        },
                        {
                            "type": "youtube_channel",
                            "rank_group": 1,
                            "rank_absolute": 3,
                            "title": "VAR Decisions Hub",
                        },
                    ],
                }
            ]
        }
    ]
}


class DataForSEOYouTubeTrendProvider(RealTrendProviderBase):
    """Live YouTube SERP organic trend suggestions via DataForSEO."""

    provider_id = PROVIDER_NAME
    source_name = "dataforseo_youtube"
    supports_live_fetch = True

    _last_request_at: float = 0.0

    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        max_youtube_seeds: int = MAX_YOUTUBE_SEEDS,
        request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        dry_run: bool | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.max_youtube_seeds = max(1, min(int(max_youtube_seeds), MAX_YOUTUBE_SEEDS))
        self.request_timeout_seconds = request_timeout_seconds
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("DATAFORSEO_YOUTUBE_DRY_RUN", "").strip().lower()
            in {"1", "true", "yes"}
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
        query = self._select_query(context, niche)
        if not query:
            return []

        payload = [
            {
                "keyword": query,
                "location_name": DEFAULT_LOCATION_NAME,
                "language_name": DEFAULT_LANGUAGE_NAME,
                "device": DEFAULT_DEVICE,
                "os": DEFAULT_OS,
                "block_depth": DEFAULT_DEPTH,
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
            if not response_data:
                return []

        items = parse_youtube_organic_response(response_data)
        if not items:
            return []

        now = datetime.now().strftime(TIMESTAMP_FORMAT)
        max_results = max(1, min(int(context.max_results), MAX_RESULTS_PARSED))
        signals: list[NormalizedTrendSignal] = []

        for index, item in enumerate(items[:MAX_RESULTS_PARSED]):
            title = _clean_video_title(str(item.get("title", "")))
            if not title:
                continue

            rank_absolute = _safe_int(item.get("rank_absolute"), default=index + 1)
            niche_match = _score_niche_match(title, niche, context.profile)
            freshness = _score_rank_freshness(rank_absolute)
            confidence = _score_youtube_confidence(freshness, niche_match, rank_absolute, index)
            channel_name = str(item.get("channel_name", "")).strip()
            video_url = str(item.get("url", "")).strip()

            metadata: dict[str, Any] = {
                "provider": PROVIDER_NAME,
                "live_fetch": not self.dry_run,
                "search_engine": SEARCH_ENGINE,
                "se_type": SE_TYPE,
                "api_endpoint": API_ENDPOINT_ID,
                "query_used": query,
                "location_name": DEFAULT_LOCATION_NAME,
                "language_name": DEFAULT_LANGUAGE_NAME,
                "device": DEFAULT_DEVICE,
                "os": DEFAULT_OS,
                "depth": DEFAULT_DEPTH,
                "rank_group": _safe_int(item.get("rank_group"), default=0),
                "rank_absolute": rank_absolute,
                "url": video_url,
                "channel_name": channel_name,
            }
            if user_topic and sanitize_keyword(user_topic) == sanitize_keyword(query):
                metadata["user_topic_authoritative"] = True
                metadata["priority"] = "user_topic"

            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "video"
            signals.append(
                NormalizedTrendSignal(
                    trend_topic=title,
                    source=self.source_name,
                    confidence=confidence,
                    freshness_score=freshness,
                    niche_match=niche_match,
                    momentum=TrendMomentum.STABLE.value,
                    platforms=["youtube"],
                    provider_id=self.provider_id,
                    source_url=video_url,
                    attribution=f"dataforseo://youtube/organic/{slug}",
                    collected_at=now,
                    metadata=metadata,
                )
            )
            if len(signals) >= max_results:
                break

        return signals

    def _select_query(self, context: TrendProviderContext, niche: str) -> str:
        user_topic = context.topic.strip()
        if user_topic:
            return sanitize_keyword(user_topic) or user_topic.strip().lower()

        seeds = _collect_seed_topics(context, niche)
        for seed in seeds:
            cleaned = sanitize_keyword(seed)
            if cleaned:
                return cleaned
        return ""

    def _cooldown_ready(self) -> bool:
        elapsed = time.monotonic() - DataForSEOYouTubeTrendProvider._last_request_at
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
                DataForSEOYouTubeTrendProvider._last_request_at = time.monotonic()
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


def parse_youtube_organic_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []

    for task in payload.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        for result in task.get("result", []) or []:
            if not isinstance(result, dict):
                continue
            for item in result.get("items", []) or []:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type", "")).strip() != "youtube_video":
                    continue
                title = str(item.get("title", "")).strip()
                if not title:
                    continue
                videos.append(dict(item))

    return videos


def _clean_video_title(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip())
    return cleaned[:120].strip()


def _score_rank_freshness(rank_absolute: int) -> float:
    rank = max(1, rank_absolute)
    return round(max(0.55, 0.92 - (rank - 1) * 0.018), 4)


def _score_youtube_confidence(
    freshness: float,
    niche_match: float,
    rank_absolute: int,
    index: int,
) -> float:
    base = _score_confidence(freshness, niche_match, index)
    rank_bonus = max(0.0, 0.12 - (max(1, rank_absolute) - 1) * 0.006)
    return round(min(1.0, base + rank_bonus), 4)


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "API_ENDPOINT_ID",
    "DataForSEOYouTubeTrendProvider",
    "MAX_YOUTUBE_SEEDS",
    "PROVIDER_NAME",
    "parse_youtube_organic_response",
]


if __name__ == "__main__":
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    engine = ProviderRegistryEngine() if ProviderRegistryEngine is not None else None
    provider = DataForSEOYouTubeTrendProvider(registry_engine=engine, dry_run=True)

    print("=" * 72)
    print("DATAFORSEO YOUTUBE TREND PROVIDER SMOKE")
    print("=" * 72)
    print("ENABLED:", provider.enabled)
    print("DRY_RUN:", provider.dry_run)
    print("MAX_YOUTUBE_SEEDS:", provider.max_youtube_seeds)
    if engine is not None:
        print(
            "CREDENTIALS READY:",
            engine.credentials_ready(ProviderRegistryEngine.TREND_CATEGORY, PROVIDER_NAME),
        )

    football_profile = loader.resolve(niche="football")
    auto_context = TrendProviderContext(
        niche="football",
        topic="",
        profile=football_profile,
        max_results=5,
        locale="en",
    )
    user_context = TrendProviderContext(
        niche="football",
        topic="late VAR replay angle",
        profile=football_profile,
        max_results=5,
        locale="en",
    )
    print("AUTO QUERY:", provider._select_query(auto_context, "football"))
    print("USER QUERY:", provider._select_query(user_context, "football"))

    dry_signals = provider.fetch_trends(user_context)
    print("DRY-RUN SIGNAL COUNT:", len(dry_signals))
    for signal in dry_signals[:3]:
        print(
            f"- {signal.trend_topic} | confidence={signal.confidence} | "
            f"rank={signal.metadata.get('rank_absolute')} | "
            f"channel={signal.metadata.get('channel_name')}"
        )
        assert signal.platforms == ["youtube"]
        assert signal.metadata.get("provider") == PROVIDER_NAME
        assert signal.metadata.get("search_engine") == SEARCH_ENGINE

    allow_live = os.getenv("DATAFORSEO_YOUTUBE_ALLOW_LIVE_SMOKE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if allow_live and provider.enabled:
        live_provider = DataForSEOYouTubeTrendProvider(registry_engine=engine, dry_run=False)
        live_signals = live_provider.fetch_trends(user_context)
        print("LIVE SIGNAL COUNT:", len(live_signals))
        for signal in live_signals[:3]:
            print(
                f"- {signal.trend_topic} | rank={signal.metadata.get('rank_absolute')} | "
                f"live={signal.metadata.get('live_fetch')}"
            )

    print("ALL DATAFORSEO YOUTUBE SMOKE CHECKS PASSED")
