"""
Real Trend Provider V1 for the Viral Content Brain.

Provider layer for future live internet trend signals.
Local/mock structure only in V1 — no real APIs or browser automation yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Any, Optional

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

FUTURE_PROVIDER_IDS = (
    "youtube_trends",
    "reddit",
    "google_trends",
    "tiktok_discovery",
    "shorts_reels_trends",
    "news_trends",
)


FORBIDDEN_SEED_PATTERNS = (
    r"\bbreakout topic\b",
    r"\baudience debate\b",
    r"\bcreator angle\b",
    r"^[\w_]+ breakout topic$",
    r"^[\w_]+ audience debate$",
    r"^[\w_]+ creator angle$",
)

SAFE_GENERIC_FALLBACK_SEEDS = (
    "the detail viewers are debating this week",
    "the moment creators keep remaking with a new angle",
    "the overlooked story beat gaining traction",
    "the angle splitting comment sections right now",
)


class TrendMomentum(str, Enum):
    RISING = "rising"
    STABLE = "stable"
    SPIKING = "spiking"
    COOLING = "cooling"


@dataclass
class TrendProviderContext:
    niche: str = "general"
    topic: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    platforms: list[str] = field(default_factory=list)
    max_results: int = 10
    locale: str = "en"

    def to_dict(self) -> dict[str, Any]:
        return {
            "niche": self.niche,
            "topic": self.topic,
            "platforms": list(self.platforms),
            "max_results": self.max_results,
            "locale": self.locale,
            "profile_niche": self.profile.get("niche", self.niche),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrendProviderContext:
        return cls(
            niche=str(data.get("niche", "general")),
            topic=str(data.get("topic", "")),
            profile=dict(data.get("profile", {})),
            platforms=list(data.get("platforms", [])),
            max_results=int(data.get("max_results", 10)),
            locale=str(data.get("locale", "en")),
        )


@dataclass
class NormalizedTrendSignal:
    trend_topic: str
    source: str
    confidence: float
    freshness_score: float
    niche_match: float
    momentum: str
    platforms: list[str] = field(default_factory=list)
    provider_id: str = ""
    source_url: str = ""
    attribution: str = ""
    collected_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend_topic": self.trend_topic,
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "freshness_score": round(self.freshness_score, 4),
            "niche_match": round(self.niche_match, 4),
            "momentum": self.momentum,
            "platforms": list(self.platforms),
            "provider_id": self.provider_id,
            "source_url": self.source_url,
            "attribution": self.attribution,
            "collected_at": self.collected_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedTrendSignal:
        if not isinstance(data, dict):
            raise ValueError("NormalizedTrendSignal.from_dict() expects a dict.")

        return cls(
            trend_topic=str(data.get("trend_topic", "")),
            source=str(data.get("source", "")),
            confidence=float(data.get("confidence", 0.0)),
            freshness_score=float(data.get("freshness_score", 0.0)),
            niche_match=float(data.get("niche_match", 0.0)),
            momentum=str(data.get("momentum", TrendMomentum.STABLE.value)),
            platforms=list(data.get("platforms", [])),
            provider_id=str(data.get("provider_id", "")),
            source_url=str(data.get("source_url", "")),
            attribution=str(data.get("attribution", "")),
            collected_at=str(data.get("collected_at", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_discovery_bridge(self) -> dict[str, Any]:
        """Future bridge payload for TrendDiscoveryEngine adapters."""
        return {
            "topic": self.trend_topic,
            "source": self.source,
            "provider_id": self.provider_id,
            "velocity_hint": round(self.confidence * 100.0, 2),
            "saturation_hint": round(max(0.0, 100.0 - (self.freshness_score * 100.0)), 2),
            "freshness_hours": round(max(1.0, (1.0 - self.freshness_score) * 72.0), 2),
            "niche_match": self.niche_match,
            "platforms": list(self.platforms),
            "momentum": self.momentum,
            "metadata": dict(self.metadata),
        }


@dataclass
class TrendProviderFetchResult:
    provider_id: str
    source: str
    signals: list[NormalizedTrendSignal]
    enabled: bool
    live_data: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "source": self.source,
            "enabled": self.enabled,
            "live_data": self.live_data,
            "notes": self.notes,
            "signals": [signal.to_dict() for signal in self.signals],
        }


class RealTrendProviderBase(ABC):
    """Base interface for Content Brain real trend providers."""

    provider_id: str = "base"
    source_name: str = "unknown"
    enabled: bool = True
    supports_live_fetch: bool = False

    @abstractmethod
    def fetch_trends(self, context: TrendProviderContext) -> list[NormalizedTrendSignal]:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "source_name": self.source_name,
            "enabled": self.enabled,
            "supports_live_fetch": self.supports_live_fetch,
        }


class FutureTrendProviderStub(RealTrendProviderBase):
    """Placeholder for future API/browser-backed providers."""

    def __init__(self, provider_id: str, source_name: str):
        self.provider_id = provider_id
        self.source_name = source_name
        self.enabled = False
        self.supports_live_fetch = True

    def fetch_trends(self, context: TrendProviderContext) -> list[NormalizedTrendSignal]:
        del context
        return []


class MockTrendProvider(RealTrendProviderBase):
    """Local mock provider using profile seeds and niche-aware templates."""

    provider_id = "mock_trend_provider"
    source_name = "mock_local_seed"
    enabled = True
    supports_live_fetch = False

    TOPIC_TEMPLATES = [
        "{topic}",
        "Why {topic} is gaining traction via {angle}",
        "{topic}: the {angle} angle gaining comments this week",
    ]

    USER_TOPIC_ANGLE_TEMPLATES = [
        "Why {topic} is gaining traction via {angle}",
        "{topic}: the {angle} angle creators are testing now",
        "What changed around {topic} when viewed through {angle}",
    ]

    def fetch_trends(self, context: TrendProviderContext) -> list[NormalizedTrendSignal]:
        niche = context.niche.strip() or str(context.profile.get("niche", "general"))
        platforms = _resolve_platforms(context)
        seeds = _collect_seed_topics(context, niche)
        render_angles = _collect_render_angles(context.profile)
        now = datetime.now().strftime(TIMESTAMP_FORMAT)

        signals: list[NormalizedTrendSignal] = []
        user_topic = context.topic.strip()
        for index, seed in enumerate(seeds[: context.max_results]):
            rendered_topic, trend_angle = self._render_topic(
                seed,
                user_topic,
                index,
                profile=context.profile,
                render_angles=render_angles,
            )
            freshness = _score_freshness(index, has_user_topic=bool(user_topic))
            niche_match = _score_niche_match(rendered_topic, niche, context.profile)
            confidence = _score_confidence(freshness, niche_match, index)
            momentum = _resolve_momentum(index, confidence)

            metadata: dict[str, Any] = {
                "mock": True,
                "seed_index": index,
                "seed_source": seed,
                "niche": niche,
                "bridge": {
                    "future_sources": list(FUTURE_PROVIDER_IDS),
                },
            }
            if trend_angle and trend_angle != rendered_topic:
                metadata["trend_angle"] = trend_angle
            if user_topic and rendered_topic == user_topic:
                metadata["user_topic_authoritative"] = True
                metadata["priority"] = "user_topic"

            signals.append(
                NormalizedTrendSignal(
                    trend_topic=rendered_topic,
                    source=self.source_name,
                    confidence=confidence,
                    freshness_score=freshness,
                    niche_match=niche_match,
                    momentum=momentum,
                    platforms=platforms,
                    provider_id=self.provider_id,
                    source_url="",
                    attribution=f"mock://content_brain/{self.provider_id}/{niche}",
                    collected_at=now,
                    metadata=metadata,
                )
            )

        signals.sort(key=lambda item: item.confidence, reverse=True)
        return signals

    def _render_topic(
        self,
        seed: str,
        user_topic: str,
        index: int,
        profile: dict[str, Any] | None = None,
        render_angles: list[str] | None = None,
    ) -> tuple[str, str]:
        base = seed.strip() or user_topic.strip()
        user_explicit = user_topic.strip()
        angles = render_angles or _collect_render_angles(profile or {})
        angle = _normalize_render_angle(
            angles[index % len(angles)] if angles else "timely"
        )

        if not base:
            base = "a timely short-form story beat"

        if user_explicit and base == user_explicit:
            preserved = re.sub(r"\s+", " ", user_explicit).strip()
            template = self.USER_TOPIC_ANGLE_TEMPLATES[
                index % len(self.USER_TOPIC_ANGLE_TEMPLATES)
            ]
            trend_angle = re.sub(
                r"\s+",
                " ",
                template.format(topic=preserved, angle=angle),
            ).strip()
            return preserved, trend_angle

        template = self.TOPIC_TEMPLATES[index % len(self.TOPIC_TEMPLATES)]
        rendered = re.sub(
            r"\s+",
            " ",
            template.format(topic=base, angle=angle),
        ).strip()
        if rendered == base:
            trend_angle = f"{angle} framing around {base}"
        else:
            trend_angle = rendered
        return rendered, trend_angle


class RealTrendProviderRegistry:
    """Registry for modular trend provider lookup and aggregation."""

    def __init__(self):
        self._providers: dict[str, RealTrendProviderBase] = {}

    def register(self, provider: RealTrendProviderBase) -> None:
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> Optional[RealTrendProviderBase]:
        return self._providers.get(provider_id)

    def list_providers(self) -> list[dict[str, Any]]:
        return [provider.describe() for provider in self._providers.values()]

    def list_enabled(self) -> list[RealTrendProviderBase]:
        return [provider for provider in self._providers.values() if provider.enabled]

    def fetch_from_provider(
        self,
        provider_id: str,
        context: TrendProviderContext,
    ) -> TrendProviderFetchResult:
        provider = self.get(provider_id)
        if provider is None:
            return TrendProviderFetchResult(
                provider_id=provider_id,
                source="unknown",
                signals=[],
                enabled=False,
                live_data=False,
                notes=f"Provider {provider_id!r} is not registered.",
            )

        signals = provider.fetch_trends(context) if provider.enabled else []
        return TrendProviderFetchResult(
            provider_id=provider.provider_id,
            source=provider.source_name,
            signals=signals,
            enabled=provider.enabled,
            live_data=provider.supports_live_fetch and provider.enabled,
            notes="live fetch disabled in V1" if not provider.supports_live_fetch else "",
        )

    def fetch_all(self, context: TrendProviderContext) -> list[TrendProviderFetchResult]:
        results: list[TrendProviderFetchResult] = []
        for provider in self._providers.values():
            results.append(
                TrendProviderFetchResult(
                    provider_id=provider.provider_id,
                    source=provider.source_name,
                    signals=provider.fetch_trends(context) if provider.enabled else [],
                    enabled=provider.enabled,
                    live_data=provider.supports_live_fetch and provider.enabled,
                    notes="" if provider.enabled else "provider disabled",
                )
            )
        return results


class RealTrendProvider:
    """
    Facade for real trend provider access.

    Registry is built from config via TrendProviderConfigLoader,
    with MockTrendProvider as the safe fallback.
    """

    def __init__(self, registry: RealTrendProviderRegistry | None = None):
        self.registry = registry or build_default_registry()

    def fetch(
        self,
        niche: str = "general",
        topic: str = "",
        profile: dict[str, Any] | None = None,
        platforms: list[str] | None = None,
        max_results: int = 10,
        provider_id: str = "mock_trend_provider",
    ) -> TrendProviderFetchResult:
        context = TrendProviderContext(
            niche=niche,
            topic=topic,
            profile=dict(profile or {}),
            platforms=list(platforms or []),
            max_results=max_results,
        )
        return self.registry.fetch_from_provider(provider_id, context)

    def fetch_best_signals(
        self,
        niche: str = "general",
        topic: str = "",
        profile: dict[str, Any] | None = None,
        platforms: list[str] | None = None,
        max_results: int = 10,
        locale: str = "",
    ) -> list[NormalizedTrendSignal]:
        profile_payload = dict(profile or {})
        resolved_locale = str(
            locale
            or profile_payload.get("language")
            or (profile_payload.get("language_rules") or {}).get("output_language")
            or "en"
        ).strip()
        context = TrendProviderContext(
            niche=niche,
            topic=topic,
            profile=profile_payload,
            platforms=list(platforms or []),
            max_results=max_results,
            locale=resolved_locale,
        )

        combined: list[NormalizedTrendSignal] = []
        for result in self.registry.fetch_all(context):
            if result.enabled and result.signals:
                combined.extend(result.signals)

        from content_brain.providers.trend_signal_aggregation_engine import (
            TrendSignalAggregationEngine,
        )

        aggregated = TrendSignalAggregationEngine().aggregate(combined, context)

        from content_brain.engines.niche_relevance_filter_engine import (
            NicheRelevanceFilterEngine,
        )

        filtered = NicheRelevanceFilterEngine().filter(aggregated, context)
        return _maybe_enrich_signals(filtered, context)

    def list_providers(self) -> list[dict[str, Any]]:
        return self.registry.list_providers()


def build_default_registry() -> RealTrendProviderRegistry:
    """Build trend registry from config; fallback to MockTrendProvider only."""
    try:
        from content_brain.providers.trend_provider_loader import (
            TrendProviderConfigLoader,
        )

        return TrendProviderConfigLoader().build_registry()
    except Exception:
        registry = RealTrendProviderRegistry()
        registry.register(MockTrendProvider())
        return registry


def _maybe_enrich_signals(
    signals: list[NormalizedTrendSignal],
    context: TrendProviderContext,
) -> list[NormalizedTrendSignal]:
    if len(signals) <= 1:
        return signals

    try:
        from core.provider_registry_engine import ProviderRegistryEngine
        from content_brain.providers.openai_trend_enricher import (
            MAX_ENRICHMENT_SIGNALS,
            OpenAITrendEnricher,
        )

        engine = ProviderRegistryEngine()
        if engine.get_ready_trend_enrichment() != OpenAITrendEnricher.enricher_id:
            return signals

        enricher = OpenAITrendEnricher(registry_engine=engine)
        if not enricher.enabled:
            return signals

        head = signals[:MAX_ENRICHMENT_SIGNALS]
        tail = signals[MAX_ENRICHMENT_SIGNALS:]
        enriched_head = enricher.enrich(head, context)
        if enriched_head is head or not enriched_head:
            return signals
        return enriched_head + tail
    except Exception:
        return signals


def _resolve_platforms(context: TrendProviderContext) -> list[str]:
    if context.platforms:
        return [str(item) for item in context.platforms]

    profile_platforms = context.profile.get("target_platforms", [])
    if profile_platforms:
        return [str(item) for item in profile_platforms]

    return ["tiktok", "youtube_shorts", "instagram_reels"]


def _collect_seed_topics(context: TrendProviderContext, niche: str) -> list[str]:
    user_topic = context.topic.strip()
    if user_topic:
        return _expand_related_topic_seeds(user_topic, context)

    seeds: list[str] = []
    profile = context.profile

    semantic_universe = profile.get("semantic_universe", {})
    if isinstance(semantic_universe, dict):
        seeds.extend(_clean_seed_list(semantic_universe.get("topic_seed_pool", [])))

    trend_discovery = profile.get("trend_discovery", {})
    if isinstance(trend_discovery, dict):
        seeds.extend(_clean_seed_list(trend_discovery.get("manual_seed_topics", [])))

    seeds.extend(_clean_seed_list(profile.get("example_seed_topics", [])))
    seeds.extend(_clean_seed_list(profile.get("competitor_keywords", [])))

    seeds = _dedupe_preserve_order(seeds)
    seeds = [
        seed
        for seed in seeds
        if not _is_forbidden_slug_seed(seed, niche, profile)
    ]

    if not seeds:
        seeds = list(SAFE_GENERIC_FALLBACK_SEEDS)

    return seeds


def _expand_related_topic_seeds(topic: str, context: TrendProviderContext) -> list[str]:
    """Build related search-style seeds from the operator topic (offline fallback)."""
    cleaned = re.sub(r"\s+", " ", topic.strip())
    if not cleaned:
        return []

    locale = str(context.locale or "en").strip().lower().split("-")[0] or "en"
    templates = RELATED_TOPIC_TEMPLATES.get(locale) or RELATED_TOPIC_TEMPLATES["en"]
    seeds = [cleaned]
    for template in templates:
        rendered = re.sub(r"\s+", " ", template.format(topic=cleaned)).strip()
        if rendered and rendered.lower() not in {item.lower() for item in seeds}:
            seeds.append(rendered)
        if len(seeds) >= max(3, min(context.max_results, 8)):
            break
    return seeds


RELATED_TOPIC_TEMPLATES: dict[str, list[str]] = {
    "en": [
        "{topic}",
        "best {topic} tips",
        "how to {topic}",
        "{topic} for beginners",
        "why {topic} is trending",
    ],
    "fa": [
        "{topic}",
        "بهترین نکات {topic}",
        "آموزش {topic}",
        "{topic} برای مبتدیان",
        "چرا {topic} ترند شده",
    ],
    "de": [
        "{topic}",
        "beste {topic} tipps",
        "wie {topic} funktioniert",
        "{topic} für anfänger",
    ],
    "fr": [
        "{topic}",
        "meilleurs conseils {topic}",
        "comment {topic}",
    ],
    "es": [
        "{topic}",
        "mejores consejos de {topic}",
        "cómo {topic}",
    ],
    "ar": [
        "{topic}",
        "أفضل نصائح {topic}",
        "كيف {topic}",
    ],
    "tr": [
        "{topic}",
        "en iyi {topic} ipuçları",
        "nasıl {topic}",
    ],
}


def _clean_seed_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", item.strip())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _is_forbidden_slug_seed(seed: str, niche: str, profile: dict[str, Any]) -> bool:
    lowered = seed.lower()
    for pattern in FORBIDDEN_SEED_PATTERNS:
        if re.search(pattern, lowered):
            return True

    slug = str(profile.get("niche", niche)).strip().lower()
    label = str(profile.get("niche_label", "")).strip().lower()
    if slug and slug in lowered and any(
        token in lowered for token in ("breakout", "creator angle", "audience debate")
    ):
        return True
    if label and lowered == label:
        return True
    return False


def _normalize_render_angle(angle: str) -> str:
    cleaned = re.sub(r"\s+", " ", angle.strip())
    return re.sub(r"^the\s+", "", cleaned, flags=re.IGNORECASE) or "timely"


def _collect_render_angles(profile: dict[str, Any]) -> list[str]:
    semantic_universe = profile.get("semantic_universe", {})
    if not isinstance(semantic_universe, dict):
        return ["timely", "debate-driven", "emotion-led"]

    angles: list[str] = []
    for key in (
        "trend_angles",
        "conflict_angles",
        "audience_angles",
        "emotional_angles",
    ):
        angles.extend(_clean_seed_list(semantic_universe.get(key, [])))

    angles = _dedupe_preserve_order(angles)
    return angles or ["timely", "debate-driven", "emotion-led"]


def _collect_semantic_universe_tokens(profile: dict[str, Any]) -> set[str]:
    semantic_universe = profile.get("semantic_universe", {})
    if not isinstance(semantic_universe, dict):
        return set()

    token_sources: list[str] = []
    token_sources.extend(_clean_seed_list(semantic_universe.get("topic_seed_pool", [])))
    token_sources.extend(_clean_seed_list(semantic_universe.get("emotional_angles", [])))
    token_sources.extend(_clean_seed_list(semantic_universe.get("audience_angles", [])))
    token_sources.extend(_clean_seed_list(semantic_universe.get("conflict_angles", [])))
    token_sources.extend(_clean_seed_list(semantic_universe.get("trend_angles", [])))

    for cluster in semantic_universe.get("semantic_clusters", []):
        if not isinstance(cluster, dict):
            continue
        token_sources.extend(_clean_seed_list(cluster.get("concepts", [])))
        label = str(cluster.get("label", "")).strip()
        if label:
            token_sources.append(label)

    tokens: set[str] = set()
    for source in token_sources:
        tokens.update(_tokenize(source))
    return {token for token in tokens if len(token) >= 3}


def _tokenize(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return {token for token in cleaned.split() if token}


def _score_niche_match(topic: str, niche: str, profile: dict[str, Any]) -> float:
    topic_tokens = _tokenize(topic)
    if not topic_tokens:
        return 0.62

    universe_tokens = _collect_semantic_universe_tokens(profile)
    if universe_tokens:
        overlap = len(topic_tokens.intersection(universe_tokens))
        if overlap:
            return round(min(1.0, 0.58 + overlap * 0.08), 4)

        partial_hits = sum(
            1
            for token in topic_tokens
            if any(token in universe_token or universe_token in token for universe_token in universe_tokens)
        )
        if partial_hits:
            return round(min(1.0, 0.54 + partial_hits * 0.06), 4)

        return 0.52

    niche_tokens = _tokenize(niche.replace("_", " "))
    label_tokens = _tokenize(str(profile.get("niche_label", "")))
    overlap = len(topic_tokens.intersection(niche_tokens.union(label_tokens)))
    if overlap:
        return round(min(1.0, 0.55 + overlap * 0.12), 4)

    keywords = profile.get("niche_keywords", []) or profile.get("competitor_keywords", [])
    keyword_tokens = _tokenize(" ".join(str(item) for item in keywords))
    keyword_overlap = len(topic_tokens.intersection(keyword_tokens))
    if keyword_overlap:
        return round(min(1.0, 0.5 + keyword_overlap * 0.1), 4)

    return 0.62


def _score_freshness(index: int, has_user_topic: bool) -> float:
    base = 0.92 if has_user_topic and index == 0 else 0.84 - (index * 0.05)
    return round(max(0.35, min(1.0, base)), 4)


def _score_confidence(freshness: float, niche_match: float, index: int) -> float:
    penalty = index * 0.03
    score = (freshness * 0.45) + (niche_match * 0.55) - penalty
    return round(max(0.0, min(1.0, score)), 4)


def _resolve_momentum(index: int, confidence: float) -> str:
    if confidence >= 0.85 and index == 0:
        return TrendMomentum.SPIKING.value
    if confidence >= 0.75:
        return TrendMomentum.RISING.value
    if confidence <= 0.55:
        return TrendMomentum.COOLING.value
    return TrendMomentum.STABLE.value


__all__ = [
    "FUTURE_PROVIDER_IDS",
    "MockTrendProvider",
    "NormalizedTrendSignal",
    "RealTrendProvider",
    "RealTrendProviderBase",
    "RealTrendProviderRegistry",
    "TrendMomentum",
    "TrendProviderContext",
    "TrendProviderFetchResult",
    "build_default_registry",
]


if __name__ == "__main__":
    import json
    import tempfile

    from content_brain.profiles.channel_identity_store import ChannelIdentity
    from content_brain.profiles.profile_loader import ProfileLoader

    provider = RealTrendProvider()
    loader = ProfileLoader()

    cases = [
        ("football", "late VAR replay angle"),
        ("perfume", "airport scent everyone asked about"),
        ("dark_mystery", "room missing from the blueprint"),
    ]

    print("REGISTERED PROVIDERS")
    for item in provider.list_providers():
        print(
            f"- {item['provider_id']} | enabled={item['enabled']} | "
            f"live={item['supports_live_fetch']}"
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        del tmp_dir

        for niche, topic in cases:
            profile = loader.resolve(niche=niche)
            result = provider.fetch(
                niche=niche,
                topic=topic,
                profile=profile,
                max_results=5,
            )
            best = provider.fetch_best_signals(
                niche=niche,
                topic=topic,
                profile=profile,
                max_results=3,
            )

            print("\n" + "=" * 72)
            print(f"{niche.upper()} | provider={result.provider_id} | signals={len(result.signals)}")
            if result.signals:
                sample = result.signals[0].to_dict()
                roundtrip = NormalizedTrendSignal.from_dict(sample)
                print("SAMPLE:", json.dumps(sample, ensure_ascii=False))
                print("ROUNDTRIP TOPIC:", roundtrip.trend_topic)
                print("BRIDGE:", json.dumps(roundtrip.to_discovery_bridge(), ensure_ascii=False))
            print("BEST SIGNALS:", len(best))

        print("\n" + "=" * 72)
        print("SEMANTIC UNIVERSE AUTO-TOPIC CHECK")
        football_channel = ChannelIdentity(
            channel_name="VAR Decisions Daily",
            main_niche="football VAR controversy",
            sub_niche="Premier League replay decisions",
            audience="Football fans who debate referee calls",
            tone_story_style="documentary_style",
            visual_style="broadcast replay frames, stadium close-ups",
        )
        football_profile = loader.resolve_from_channel_identity(football_channel)
        auto_result = provider.fetch_best_signals(
            niche=football_profile.get("niche", "football_var_controversy"),
            topic="",
            profile=football_profile,
            max_results=5,
        )
        print("PROFILE SEED SOURCE:", football_profile.get("trend_discovery", {}).get("seed_source"))
        print("AUTO SIGNAL COUNT:", len(auto_result))
        for signal in auto_result[:5]:
            print(" -", signal.trend_topic)
            forbidden = _is_forbidden_slug_seed(
                signal.trend_topic,
                str(football_profile.get("niche", "")),
                football_profile,
            )
            print("   forbidden_slug_seed=", forbidden)

        print("\n" + "=" * 72)
        print("CONFIG-DRIVEN REGISTRY CHECK")
        ready_sources: list[str] = []
        try:
            from core.provider_registry_engine import ProviderRegistryEngine

            engine = ProviderRegistryEngine()
            ready_sources = engine.get_ready_trend_sources()
            print("READY TREND SOURCES:", ready_sources)
        except Exception as exc:
            print("CONFIG READ ERROR:", type(exc).__name__)

        registered_ids = [
            item["provider_id"]
            for item in provider.list_providers()
        ]
        print("REGISTERED PROVIDERS:", registered_ids)
        print(
            "MOCK PRESENT:",
            "mock_trend_provider" in registered_ids,
        )
        for future_id in ("dataforseo", "serpapi"):
            if future_id in ready_sources and future_id not in registered_ids:
                print(f"SKIPPED (plugin not implemented): {future_id}")
