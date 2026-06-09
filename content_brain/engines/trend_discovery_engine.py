"""
Trend Discovery Engine V1 for the Viral Content Brain.

Discovers and ranks trend opportunities for any resolved profile/niche.
Provider-ready architecture without paid APIs or web scraping in V1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import md5
import json
import re
from pathlib import Path
from typing import Any, Optional

from content_brain.schemas.content_brief import Platform, TrendSignal

try:
    from content_brain.providers.real_trend_provider import RealTrendProvider

    REAL_TREND_PROVIDER_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive fallback
    RealTrendProvider = None  # type: ignore[assignment,misc]
    REAL_TREND_PROVIDER_AVAILABLE = False


@dataclass
class TrendDiscoveryContext:
    niche: str
    niche_label: str
    user_topic: str
    profile: dict[str, Any]
    manual_seed_topics: list[str] = field(default_factory=list)
    competitor_keywords: list[str] = field(default_factory=list)
    target_platforms: list[Platform] = field(default_factory=list)

    @classmethod
    def from_inputs(
        cls,
        profile: dict[str, Any],
        niche: str = "",
        topic: str = "",
        manual_seed_topics: Optional[list[str]] = None,
        competitor_keywords: Optional[list[str]] = None,
        platforms: Optional[list[Platform | str]] = None,
    ) -> TrendDiscoveryContext:
        resolved_niche = niche.strip() or str(profile.get("niche", "general"))
        niche_label = str(
            profile.get("niche_label", resolved_niche.replace("_", " ").title())
        )
        target_platforms = _resolve_platforms(profile, platforms)

        return cls(
            niche=resolved_niche,
            niche_label=niche_label,
            user_topic=topic.strip(),
            profile=profile,
            manual_seed_topics=list(manual_seed_topics or []),
            competitor_keywords=list(competitor_keywords or []),
            target_platforms=target_platforms,
        )


@dataclass
class TrendCandidate:
    topic: str
    source: str
    platform_hint: Optional[str] = None
    freshness_hours: Optional[float] = None
    velocity_hint: Optional[float] = None
    saturation_hint: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def candidate_id(self) -> str:
        digest = md5(f"{self.source}:{self.topic}".encode("utf-8")).hexdigest()[:10]
        return f"trend_{digest}"


@dataclass
class TrendScoreBreakdown:
    freshness_score: float = 0.0
    velocity_score: float = 0.0
    niche_fit_score: float = 0.0
    emotional_potential_score: float = 0.0
    competition_score: float = 0.0
    platform_fit_score: float = 0.0
    overall_trend_score: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "freshness_score": round(self.freshness_score, 2),
            "velocity_score": round(self.velocity_score, 2),
            "niche_fit_score": round(self.niche_fit_score, 2),
            "emotional_potential_score": round(self.emotional_potential_score, 2),
            "competition_score": round(self.competition_score, 2),
            "platform_fit_score": round(self.platform_fit_score, 2),
            "overall_trend_score": round(self.overall_trend_score, 2),
        }


@dataclass
class TrendOpportunity:
    opportunity_id: str
    topic: str
    source: str
    scores: TrendScoreBreakdown
    reasoning: str
    platform_fit: dict[str, float] = field(default_factory=dict)
    emotional_vector: dict[str, float] = field(default_factory=dict)
    recommended_platform: Platform = Platform.TIKTOK
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "topic": self.topic,
            "source": self.source,
            "scores": self.scores.to_dict(),
            "reasoning": self.reasoning,
            "platform_fit": self.platform_fit,
            "emotional_vector": self.emotional_vector,
            "recommended_platform": self.recommended_platform.value,
            "metadata": self.metadata,
        }

    def to_trend_signal(self) -> TrendSignal:
        return TrendSignal(
            topic=self.topic,
            velocity=self.scores.velocity_score,
            saturation=self.scores.competition_score,
            virality_score=self.scores.overall_trend_score,
            platform=self.recommended_platform,
            source=self.source,
            emotional_vector=self.emotional_vector,
            platform_fit=self.platform_fit,
            expiry_window_hours=int(self.metadata.get("expiry_window_hours", 72)),
        )


@dataclass
class TrendDiscoveryResult:
    opportunities: list[TrendOpportunity]
    best_signal: Optional[TrendSignal]
    niche: str
    sources_used: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "niche": self.niche,
            "sources_used": self.sources_used,
            "best_signal": self.best_signal.to_dict() if self.best_signal else None,
            "opportunities": [item.to_dict() for item in self.opportunities],
        }


class TrendSourceAdapter(ABC):
    source_id: str = "base"
    enabled: bool = True

    @abstractmethod
    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        raise NotImplementedError


class ManualSeedAdapter(TrendSourceAdapter):
    source_id = "manual_seed"

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        candidates: list[TrendCandidate] = []

        if context.user_topic:
            candidates.append(
                TrendCandidate(
                    topic=context.user_topic,
                    source=self.source_id,
                    freshness_hours=0.0,
                    velocity_hint=88.0,
                    metadata={"priority": "user_topic"},
                )
            )

        for topic in context.manual_seed_topics:
            cleaned = topic.strip()
            if cleaned:
                candidates.append(
                    TrendCandidate(
                        topic=cleaned,
                        source=self.source_id,
                        freshness_hours=6.0,
                        velocity_hint=80.0,
                        metadata={"priority": "manual_seed"},
                    )
                )

        return candidates


class SemanticUniverseSeedAdapter(TrendSourceAdapter):
    """Primary auto-topic source from profile semantic universe (any niche)."""

    source_id = "semantic_universe"

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        if context.user_topic:
            return []

        semantic_universe = context.profile.get("semantic_universe", {})
        if not isinstance(semantic_universe, dict):
            return []

        seeds = _clean_seed_list(semantic_universe.get("topic_seed_pool", []))
        if not seeds:
            return []

        universe_id = str(semantic_universe.get("universe_id", "")).strip()
        candidates: list[TrendCandidate] = []

        for index, seed in enumerate(seeds[:12]):
            if _is_forbidden_slug_seed(seed, context):
                continue
            candidates.append(
                TrendCandidate(
                    topic=seed,
                    source=self.source_id,
                    freshness_hours=4.0 + index * 2.0,
                    velocity_hint=76.0 + index * 2.0,
                    saturation_hint=30.0 + index * 3.0,
                    metadata={
                        "priority": "semantic_universe_seed",
                        "semantic_universe_id": universe_id,
                        "seed_index": index,
                        "seed_source": str(
                            context.profile.get("trend_discovery", {}).get(
                                "seed_source",
                                "semantic_universe_engine_v1",
                            )
                        ),
                    },
                )
            )

        return candidates


class ProfileSeedAdapter(TrendSourceAdapter):
    source_id = "profile_seed"

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        if context.user_topic:
            return []

        seeds = context.profile.get("example_seed_topics", [])
        candidates: list[TrendCandidate] = []

        for topic in seeds:
            cleaned = str(topic).strip()
            if cleaned:
                candidates.append(
                    TrendCandidate(
                        topic=cleaned,
                        source=self.source_id,
                        freshness_hours=12.0,
                        velocity_hint=74.0,
                        metadata={"priority": "profile_seed"},
                    )
                )

        return candidates


class CompetitorKeywordAdapter(TrendSourceAdapter):
    source_id = "competitor_keyword"

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        if context.user_topic:
            return []

        if not context.competitor_keywords:
            return []

        templates = [
            "What {keyword} channels are posting about in {niche_label} right now",
            "The {keyword} angle gaining traction in {niche_label}",
            "Why {keyword} content is outperforming usual {niche_label} formats",
        ]

        candidates: list[TrendCandidate] = []
        for keyword in context.competitor_keywords:
            cleaned = keyword.strip()
            if not cleaned:
                continue
            for template in templates:
                candidates.append(
                    TrendCandidate(
                        topic=template.format(
                            keyword=cleaned,
                            niche_label=context.niche_label,
                        ),
                        source=self.source_id,
                        freshness_hours=18.0,
                        velocity_hint=70.0,
                        metadata={"keyword": cleaned},
                    )
                )

        return candidates


class SimulatedTrendAdapter(TrendSourceAdapter):
    source_id = "simulated_local"

    NICHE_ANGLES: dict[str, list[str]] = {
        "football": [
            "VAR controversy breakdowns",
            "last-minute goal psychology",
            "underdog transfer rumors",
            "tactical switch in the second half",
        ],
        "perfume": [
            "skin chemistry testing",
            "budget niche dupes",
            "office-safe scent layering",
            "longevity tests on fabric vs skin",
        ],
        "music": [
            "bridge-to-drop transitions",
            "viral snippet song structures",
            "bedroom producer workflow",
            "before-and-after mix comparisons",
        ],
        "education": [
            "exam cram frameworks",
            "common mistake corrections",
            "visual memory tricks",
            "study routine comparisons",
        ],
        "horror": [
            "found-footage pacing tricks",
            "one-room psychological dread",
            "open-loop cliffhanger endings",
            "ambient sound design hooks",
        ],
        "dark_mystery": [
            "found-footage pacing tricks",
            "one-room psychological dread",
            "open-loop cliffhanger endings",
            "ambient sound design hooks",
        ],
        "selfcare": [
            "night routine simplification",
            "ingredient order mistakes",
            "before-sleep skin recovery",
            "minimal 3-step routines",
        ],
        "comedy": [
            "deadpan one-beat delays",
            "misdirect punchline timing",
            "comment-section bit callbacks",
            "relatable micro-observations",
        ],
        "news": [
            "timeline correction threads",
            "context missing from headlines",
            "local impact explainers",
            "what changed since yesterday",
        ],
    }

    GENERIC_ANGLES = [
        "audience debate threads",
        "before-and-after proof",
        "common mistake breakdowns",
        "quick comparison formats",
        "comment-driven follow-ups",
    ]

    TOPIC_TEMPLATES = [
        "Why {angle} is gaining traction this week",
        "The {angle} format getting saves right now",
        "{angle}: the short-form angle audiences are rewinding",
    ]

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        if context.user_topic:
            return []

        angles = _collect_simulated_angles(context, self.NICHE_ANGLES, self.GENERIC_ANGLES)
        candidates: list[TrendCandidate] = []

        for index, angle in enumerate(angles[:5]):
            for template in self.TOPIC_TEMPLATES[:2]:
                topic = template.format(angle=angle)
                if _topic_repeats_full_niche_label(topic, context):
                    continue
                candidates.append(
                    TrendCandidate(
                        topic=topic,
                        source=self.source_id,
                        freshness_hours=8.0 + index * 3.0,
                        velocity_hint=62.0 + index * 4.0,
                        saturation_hint=35.0 + index * 5.0,
                        metadata={"angle": angle, "simulated": True},
                    )
                )

        return candidates


class InternalPerformanceMemoryAdapter(TrendSourceAdapter):
    source_id = "internal_performance_memory"

    def __init__(self, project_root: str | Path = "."):
        self.memory_dir = (
            Path(project_root).resolve()
            / "storage"
            / "content_brain"
            / "memory"
            / "performance"
        )

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        if not self.memory_dir.exists():
            return []

        candidates: list[TrendCandidate] = []
        for path in sorted(self.memory_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            records = payload if isinstance(payload, list) else payload.get("records", [])
            for record in records:
                topic = str(record.get("topic", "")).strip()
                if not topic:
                    continue
                if not _topic_matches_niche(topic, context):
                    continue

                candidates.append(
                    TrendCandidate(
                        topic=topic,
                        source=self.source_id,
                        velocity_hint=float(record.get("velocity_hint", 75.0)),
                        saturation_hint=float(record.get("saturation_hint", 40.0)),
                        freshness_hours=float(record.get("freshness_hours", 24.0)),
                        metadata={"record_path": str(path.name)},
                    )
                )

        return candidates


class ProviderStubAdapter(TrendSourceAdapter):
    """Future provider placeholder. Returns no live data in V1."""

    def __init__(self, source_id: str):
        self.source_id = source_id

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        del context
        return []


class RealTrendProviderAdapter(TrendSourceAdapter):
    """
    Bridge adapter for Content Brain RealTrendProvider.

    V1 uses MockTrendProvider only. Falls back safely if provider layer is unavailable.
    """

    source_id = "mock_trend_provider"

    def __init__(
        self,
        provider: Any | None = None,
        enabled: bool = True,
    ):
        self._provider = provider
        self.enabled = bool(enabled and REAL_TREND_PROVIDER_AVAILABLE)

    def collect(self, context: TrendDiscoveryContext) -> list[TrendCandidate]:
        if not self.enabled:
            return []

        try:
            provider = self._resolve_provider()
            if provider is None:
                return []

            platforms = [platform.value for platform in context.target_platforms]
            locale = str(
                context.profile.get("language")
                or (context.profile.get("language_rules") or {}).get("output_language")
                or "en"
            ).strip()
            signals = provider.fetch_best_signals(
                niche=context.niche,
                topic=context.user_topic,
                profile=context.profile,
                platforms=platforms,
                max_results=10,
                locale=locale,
            )
            return [
                _candidate_from_normalized_signal(signal)
                for signal in signals
                if signal.trend_topic.strip()
            ]
        except Exception:
            return []

    def _resolve_provider(self) -> Any | None:
        if self._provider is not None:
            return self._provider
        if not REAL_TREND_PROVIDER_AVAILABLE or RealTrendProvider is None:
            return None
        self._provider = RealTrendProvider()
        return self._provider


def _candidate_from_normalized_signal(signal: Any) -> TrendCandidate:
    bridge = signal.to_discovery_bridge()
    platform_hint = signal.platforms[0] if signal.platforms else None

    return TrendCandidate(
        topic=str(bridge.get("topic", signal.trend_topic)),
        source=str(signal.provider_id or signal.source),
        platform_hint=platform_hint,
        freshness_hours=float(bridge.get("freshness_hours", 12.0)),
        velocity_hint=float(bridge.get("velocity_hint", 70.0)),
        saturation_hint=float(bridge.get("saturation_hint", 40.0)),
        metadata={
            "provider_backed": True,
            "provider_name": str(signal.provider_id or signal.source),
            "source": str(signal.source),
            "provider_confidence": float(signal.confidence),
            "freshness_score": float(signal.freshness_score),
            "niche_match": float(signal.niche_match),
            "momentum": str(signal.momentum),
            "attribution": str(signal.attribution),
            "collected_at": str(signal.collected_at),
            "platforms": list(signal.platforms),
            **dict(signal.metadata),
        },
    )


PROVIDER_STUBS = [
    "google_trends",
    "youtube_search",
    "tiktok_trend_signals",
    "reddit",
    "news_headlines",
]


class TrendDiscoveryEngine:
    """
    Discover and rank trend opportunities for any niche/profile.

    Usage:
        engine = TrendDiscoveryEngine()
        result = engine.discover(profile, niche="football", topic="VAR decisions")
    """

    OVERALL_WEIGHTS = {
        "freshness_score": 0.15,
        "velocity_score": 0.20,
        "niche_fit_score": 0.20,
        "emotional_potential_score": 0.15,
        "competition_score": 0.15,
        "platform_fit_score": 0.15,
    }

    EMOTIONAL_KEYWORDS = {
        "curiosity": ("why", "what", "secret", "hidden", "truth", "question"),
        "surprise": ("shock", "unexpected", "twist", "sudden", "plot"),
        "desire": ("better", "upgrade", "want", "need", "must"),
        "urgency": ("now", "today", "before", "last", "final"),
        "dread": ("wrong", "missing", "warning", "dark", "fear"),
        "belonging": ("community", "fans", "everyone", "people", "audience"),
    }

    def __init__(
        self,
        project_root: str | Path = ".",
        use_provider_layer: bool = True,
    ):
        self.project_root = Path(project_root).resolve()
        self.use_provider_layer = bool(use_provider_layer and REAL_TREND_PROVIDER_AVAILABLE)
        self.adapters: list[TrendSourceAdapter] = self._default_adapters()

    def discover(
        self,
        profile: dict[str, Any],
        niche: str = "",
        topic: str = "",
        manual_seed_topics: Optional[list[str]] = None,
        competitor_keywords: Optional[list[str]] = None,
        platforms: Optional[list[Platform | str]] = None,
        adapters: Optional[list[TrendSourceAdapter]] = None,
        max_results: int = 10,
        use_provider_layer: Optional[bool] = None,
    ) -> TrendDiscoveryResult:
        context = TrendDiscoveryContext.from_inputs(
            profile=profile,
            niche=niche,
            topic=topic,
            manual_seed_topics=manual_seed_topics,
            competitor_keywords=competitor_keywords,
            platforms=platforms,
        )

        active_adapters = adapters if adapters is not None else self._resolve_adapters(
            use_provider_layer=use_provider_layer,
        )
        candidates: list[TrendCandidate] = []
        sources_used: list[str] = []

        for adapter in active_adapters:
            if not adapter.enabled:
                continue
            batch = adapter.collect(context)
            if batch:
                sources_used.append(adapter.source_id)
            candidates.extend(batch)

        deduped = self._dedupe_candidates(candidates)
        opportunities = [
            self._score_candidate(candidate, context)
            for candidate in deduped
        ]
        opportunities.sort(
            key=lambda item: item.scores.overall_trend_score,
            reverse=True,
        )
        opportunities = opportunities[:max_results]

        best_signal = (
            self._build_authoritative_signal(context, opportunities)
            if context.user_topic
            else (opportunities[0].to_trend_signal() if opportunities else None)
        )

        return TrendDiscoveryResult(
            opportunities=opportunities,
            best_signal=best_signal,
            niche=context.niche,
            sources_used=sources_used,
        )

    def discover_best_signal(
        self,
        profile: dict[str, Any],
        niche: str = "",
        topic: str = "",
        **kwargs: Any,
    ) -> Optional[TrendSignal]:
        return self.discover(
            profile=profile,
            niche=niche,
            topic=topic,
            **kwargs,
        ).best_signal

    def register_adapter(self, adapter: TrendSourceAdapter) -> None:
        self.adapters.append(adapter)

    def _resolve_adapters(
        self,
        use_provider_layer: Optional[bool] = None,
    ) -> list[TrendSourceAdapter]:
        if use_provider_layer is False:
            return [
                adapter
                for adapter in self.adapters
                if adapter.source_id != RealTrendProviderAdapter.source_id
            ]
        return self.adapters

    def _default_adapters(self) -> list[TrendSourceAdapter]:
        adapters: list[TrendSourceAdapter] = [
            ManualSeedAdapter(),
            SemanticUniverseSeedAdapter(),
            ProfileSeedAdapter(),
            SimulatedTrendAdapter(),
            InternalPerformanceMemoryAdapter(self.project_root),
        ]
        if self.use_provider_layer:
            adapters.insert(2, RealTrendProviderAdapter())
        adapters.extend(ProviderStubAdapter(source_id=item) for item in PROVIDER_STUBS)
        return adapters

    def _dedupe_candidates(self, candidates: list[TrendCandidate]) -> list[TrendCandidate]:
        seen: set[str] = set()
        deduped: list[TrendCandidate] = []

        for candidate in candidates:
            key = _normalize_topic(candidate.topic)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)

        return deduped

    def _score_candidate(
        self,
        candidate: TrendCandidate,
        context: TrendDiscoveryContext,
    ) -> TrendOpportunity:
        scores = TrendScoreBreakdown(
            freshness_score=self._score_freshness(candidate),
            velocity_score=self._score_velocity(candidate, context),
            niche_fit_score=self._score_niche_fit(candidate.topic, context),
            emotional_potential_score=self._score_emotional_potential(
                candidate.topic,
                context,
            ),
            competition_score=self._score_competition(candidate),
            platform_fit_score=0.0,
        )

        platform_fit = self._score_platform_fit_map(candidate.topic, context)
        scores.platform_fit_score = (
            round(sum(platform_fit.values()) / len(platform_fit), 2)
            if platform_fit
            else 60.0
        )
        scores.overall_trend_score = self._overall_score(scores)
        self._apply_provider_metadata_scores(candidate, scores)

        recommended_platform = _best_platform(platform_fit, context.target_platforms)
        emotional_vector = self._build_emotional_vector(candidate.topic, context)

        reasoning = (
            f"{candidate.source} candidate ranked for {context.niche_label}. "
            f"Freshness {scores.freshness_score}, velocity {scores.velocity_score}, "
            f"niche fit {scores.niche_fit_score}, competition {scores.competition_score}. "
            f"Best platform: {recommended_platform.value}."
        )

        return TrendOpportunity(
            opportunity_id=candidate.candidate_id(),
            topic=candidate.topic,
            source=candidate.source,
            scores=scores,
            reasoning=reasoning,
            platform_fit=platform_fit,
            emotional_vector=emotional_vector,
            recommended_platform=recommended_platform,
            metadata={
                **candidate.metadata,
                "expiry_window_hours": 72,
                "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    def _overall_score(self, scores: TrendScoreBreakdown) -> float:
        competition_opportunity = max(0.0, 100.0 - scores.competition_score)
        components = {
            "freshness_score": scores.freshness_score,
            "velocity_score": scores.velocity_score,
            "niche_fit_score": scores.niche_fit_score,
            "emotional_potential_score": scores.emotional_potential_score,
            "competition_score": competition_opportunity,
            "platform_fit_score": scores.platform_fit_score,
        }
        total = sum(components[key] * weight for key, weight in self.OVERALL_WEIGHTS.items())
        return round(min(100.0, max(0.0, total)), 2)

    def _apply_provider_metadata_scores(
        self,
        candidate: TrendCandidate,
        scores: TrendScoreBreakdown,
    ) -> None:
        if not candidate.metadata.get("provider_backed"):
            return

        provider_freshness = candidate.metadata.get("freshness_score")
        if provider_freshness is not None:
            scores.freshness_score = round(
                max(scores.freshness_score, float(provider_freshness) * 100.0),
                2,
            )

        provider_niche_match = candidate.metadata.get("niche_match")
        if provider_niche_match is not None:
            scores.niche_fit_score = round(
                max(scores.niche_fit_score, float(provider_niche_match) * 100.0),
                2,
            )

        provider_confidence = candidate.metadata.get("provider_confidence")
        if provider_confidence is not None:
            scores.velocity_score = round(
                max(scores.velocity_score, float(provider_confidence) * 100.0),
                2,
            )

        scores.overall_trend_score = self._overall_score(scores)

    def _build_authoritative_signal(
        self,
        context: TrendDiscoveryContext,
        opportunities: list[TrendOpportunity],
    ) -> TrendSignal:
        user_topic = context.user_topic
        enrichment = self._select_enrichment_opportunity(opportunities, context)

        if enrichment is None:
            return TrendSignal(
                topic=user_topic,
                velocity=82.0,
                saturation=35.0,
                virality_score=78.0,
                platform=context.target_platforms[0] if context.target_platforms else Platform.TIKTOK,
                source="user_topic",
                emotional_vector=self._build_emotional_vector(user_topic, context),
                platform_fit=self._score_platform_fit_map(user_topic, context),
                expiry_window_hours=72,
            )

        signal = enrichment.to_trend_signal()
        metadata = dict(enrichment.metadata)
        metadata["user_topic_authoritative"] = True
        metadata["trend_angle"] = metadata.get("trend_angle") or enrichment.topic

        return TrendSignal(
            topic=user_topic,
            velocity=signal.velocity,
            saturation=signal.saturation,
            virality_score=signal.virality_score,
            platform=signal.platform,
            source="user_topic",
            emotional_vector=signal.emotional_vector,
            platform_fit=signal.platform_fit,
            expiry_window_hours=signal.expiry_window_hours,
        )

    def _select_enrichment_opportunity(
        self,
        opportunities: list[TrendOpportunity],
        context: TrendDiscoveryContext,
    ) -> Optional[TrendOpportunity]:
        if not opportunities:
            return None

        user_topic = context.user_topic
        normalized_user_topic = _normalize_topic(user_topic)

        for opportunity in opportunities:
            if opportunity.metadata.get("priority") == "user_topic":
                return opportunity

        for opportunity in opportunities:
            if opportunity.metadata.get("user_topic_authoritative"):
                return opportunity

        for opportunity in opportunities:
            if _normalize_topic(opportunity.topic) == normalized_user_topic:
                return opportunity

        for opportunity in opportunities:
            if _token_overlap(opportunity.topic, user_topic) >= 0.75:
                return opportunity

        return opportunities[0]

    def _score_freshness(self, candidate: TrendCandidate) -> float:
        if candidate.freshness_hours is None:
            return 65.0

        hours = max(0.0, candidate.freshness_hours)
        if hours <= 6:
            return 95.0
        if hours <= 24:
            return 85.0
        if hours <= 72:
            return 70.0
        if hours <= 168:
            return 55.0
        return 40.0

    def _score_velocity(self, candidate: TrendCandidate, context: TrendDiscoveryContext) -> float:
        base = float(candidate.velocity_hint or 60.0)
        if candidate.metadata.get("priority") == "user_topic":
            base += 8.0
        if context.user_topic and _token_overlap(candidate.topic, context.user_topic) >= 0.4:
            base += 6.0
        return round(min(100.0, base), 2)

    def _score_niche_fit(self, topic: str, context: TrendDiscoveryContext) -> float:
        score = 50.0
        lower = topic.lower()
        topic_tokens = _tokenize_topic_set(topic)
        universe_tokens = _collect_semantic_universe_tokens(context.profile)

        if universe_tokens:
            overlap = len(topic_tokens.intersection(universe_tokens))
            if overlap:
                score += min(24.0, overlap * 6.0)

            partial_hits = sum(
                1
                for token in topic_tokens
                if any(
                    token in universe_token or universe_token in token
                    for universe_token in universe_tokens
                )
            )
            if partial_hits:
                score += min(12.0, partial_hits * 3.0)
        else:
            overlap = _token_overlap(topic, context.niche_label)
            score += min(12.0, overlap * 15.0)
            if context.niche != "general" and context.niche.replace("_", " ") in lower:
                score += 6.0

        niche_label = context.niche_label.strip().lower()
        if niche_label and niche_label in lower:
            score -= 12.0
        if niche_label and _normalize_topic(topic) == _normalize_topic(niche_label):
            score -= 20.0

        if context.user_topic:
            user_overlap = _token_overlap(topic, context.user_topic)
            score += min(15.0, user_overlap * 20.0)

        for keyword in context.competitor_keywords:
            if keyword.lower() in lower:
                score += 5.0

        return round(min(100.0, max(0.0, score)), 2)

    def _score_emotional_potential(self, topic: str, context: TrendDiscoveryContext) -> float:
        score = 52.0
        lower = topic.lower()
        tone_targets = context.profile.get("tone_rules", {}).get("emotional_targets", [])

        for target in tone_targets:
            target_key = str(target).lower()
            keywords = self.EMOTIONAL_KEYWORDS.get(target_key, (target_key,))
            if any(keyword in lower for keyword in keywords):
                score += 8.0

        if "?" in topic or "why" in lower or "what" in lower:
            score += 6.0

        return round(min(100.0, score), 2)

    def _score_competition(self, candidate: TrendCandidate) -> float:
        if candidate.saturation_hint is not None:
            return round(min(100.0, max(0.0, candidate.saturation_hint)), 2)

        digest = int(md5(candidate.topic.encode("utf-8")).hexdigest()[:6], 16)
        simulated = 30.0 + (digest % 45)
        if candidate.source == "simulated_local":
            simulated += 5.0
        return round(min(100.0, simulated), 2)

    def _score_platform_fit_map(
        self,
        topic: str,
        context: TrendDiscoveryContext,
    ) -> dict[str, float]:
        platform_rules = context.profile.get("platform_rules", {})
        lower = topic.lower()
        word_count = len(topic.split())
        fit: dict[str, float] = {}

        for platform in context.target_platforms:
            rules = platform_rules.get(platform.value, {})
            score = 68.0

            if platform == Platform.TIKTOK and word_count <= 14:
                score += 8.0
            if platform == Platform.YOUTUBE_SHORTS and any(
                token in lower for token in ("why", "how", "explained", "breakdown")
            ):
                score += 10.0
            if platform == Platform.INSTAGRAM_REELS and word_count <= 12:
                score += 8.0

            pacing_note = str(rules.get("pacing_note", "")).lower()
            if "visual" in pacing_note and any(
                token in lower for token in ("look", "see", "watch", "visual")
            ):
                score += 4.0

            fit[platform.value] = round(min(100.0, score), 2)

        return fit

    def _build_emotional_vector(
        self,
        topic: str,
        context: TrendDiscoveryContext,
    ) -> dict[str, float]:
        lower = topic.lower()
        vector: dict[str, float] = {}
        tone_targets = context.profile.get("tone_rules", {}).get("emotional_targets", [])

        for target in tone_targets[:5]:
            key = str(target).lower()
            keywords = self.EMOTIONAL_KEYWORDS.get(key, (key,))
            hits = sum(1 for keyword in keywords if keyword in lower)
            vector[key] = round(min(1.0, 0.25 + hits * 0.25), 2)

        if not vector:
            vector["curiosity"] = 0.6 if "why" in lower or "what" in lower else 0.4

        return vector


def _clean_seed_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


FORBIDDEN_SEED_PATTERNS = (
    r"\bbreakout topic\b",
    r"\baudience debate\b",
    r"\bcreator angle\b",
)


def _is_forbidden_slug_seed(seed: str, context: TrendDiscoveryContext) -> bool:
    lowered = seed.lower()
    for pattern in FORBIDDEN_SEED_PATTERNS:
        if re.search(pattern, lowered):
            return True

    slug = str(context.profile.get("niche", context.niche)).strip().lower()
    if slug and slug in lowered and any(
        token in lowered for token in ("breakout", "creator angle", "audience debate")
    ):
        return True
    return False


def _topic_repeats_full_niche_label(topic: str, context: TrendDiscoveryContext) -> bool:
    niche_label = context.niche_label.strip().lower()
    if not niche_label:
        return False
    return niche_label in topic.lower()


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
        tokens.update(_tokenize_topic_set(source))
    return {token for token in tokens if len(token) >= 3}


def _collect_simulated_angles(
    context: TrendDiscoveryContext,
    niche_angles: dict[str, list[str]],
    generic_angles: list[str],
) -> list[str]:
    semantic_universe = context.profile.get("semantic_universe", {})
    if isinstance(semantic_universe, dict):
        angles: list[str] = []
        for cluster in semantic_universe.get("semantic_clusters", []):
            if not isinstance(cluster, dict):
                continue
            angles.extend(_clean_seed_list(cluster.get("concepts", []))[:2])
        angles.extend(_clean_seed_list(semantic_universe.get("trend_angles", []))[:3])
        angles.extend(_clean_seed_list(semantic_universe.get("conflict_angles", []))[:2])
        deduped = _dedupe_preserve_order(angles)
        if deduped:
            return deduped[:5]

    pack_angles = niche_angles.get(context.niche, [])
    if pack_angles:
        return pack_angles[:5]
    return generic_angles[:5]


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


def _tokenize_topic_set(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return {token for token in cleaned.split() if len(token) >= 3}


def _resolve_platforms(
    profile: dict[str, Any],
    platforms: Optional[list[Platform | str]],
) -> list[Platform]:
    if platforms:
        resolved: list[Platform] = []
        for item in platforms:
            resolved.append(item if isinstance(item, Platform) else Platform(str(item)))
        return resolved

    resolved: list[Platform] = []
    for value in profile.get("target_platforms", []):
        try:
            resolved.append(Platform(value))
        except ValueError:
            continue
    return resolved or [Platform.TIKTOK]


def _normalize_topic(topic: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", topic.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _token_overlap(text_a: str, text_b: str) -> float:
    tokens_a = set(_normalize_topic(text_a).split())
    tokens_b = set(_normalize_topic(text_b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a.intersection(tokens_b)) / len(tokens_a.union(tokens_b))


def _topic_matches_niche(topic: str, context: TrendDiscoveryContext) -> bool:
    if context.niche == "general":
        return True

    universe_tokens = _collect_semantic_universe_tokens(context.profile)
    if universe_tokens:
        topic_tokens = _tokenize_topic_set(topic)
        if topic_tokens.intersection(universe_tokens):
            return True
        partial_hits = sum(
            1
            for token in topic_tokens
            if any(
                token in universe_token or universe_token in token
                for universe_token in universe_tokens
            )
        )
        return partial_hits >= 1

    lower = topic.lower()
    return context.niche in lower or _token_overlap(topic, context.niche_label) >= 0.2


def _best_platform(
    platform_fit: dict[str, float],
    fallback_platforms: list[Platform],
) -> Platform:
    if platform_fit:
        best_key = max(platform_fit, key=platform_fit.get)
        return Platform(best_key)

    return fallback_platforms[0] if fallback_platforms else Platform.TIKTOK


__all__ = [
    "PROVIDER_STUBS",
    "ProviderStubAdapter",
    "REAL_TREND_PROVIDER_AVAILABLE",
    "RealTrendProviderAdapter",
    "SemanticUniverseSeedAdapter",
    "TrendCandidate",
    "TrendDiscoveryContext",
    "TrendDiscoveryEngine",
    "TrendDiscoveryResult",
    "TrendOpportunity",
    "TrendScoreBreakdown",
    "TrendSourceAdapter",
]


if __name__ == "__main__":
    from content_brain.profiles.channel_identity_store import ChannelIdentity
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    engine = TrendDiscoveryEngine()

    print("PROVIDER LAYER AVAILABLE:", REAL_TREND_PROVIDER_AVAILABLE)
    print("ENGINE USES PROVIDER LAYER:", engine.use_provider_layer)

    test_cases = [
        {
            "label": "football explicit topic",
            "niche": "football",
            "topic": "VAR decisions in the 89th minute",
            "keywords": ["tactics", "referee"],
        },
        {
            "label": "perfume explicit topic",
            "niche": "perfume",
            "topic": "Vanilla skin chemistry after twenty minutes",
            "keywords": ["fragrance", "dupes"],
        },
        {
            "label": "horror auto topic",
            "niche": "horror",
            "topic": "",
            "keywords": ["found footage"],
        },
        {
            "label": "custom finance auto topic",
            "niche": "personal finance for beginners",
            "topic": "",
            "keywords": [],
        },
    ]

    for case in test_cases:
        profile = loader.resolve(niche=case["niche"])
        result = engine.discover(
            profile=profile,
            niche=case["niche"],
            topic=case["topic"],
            competitor_keywords=case["keywords"],
            max_results=5,
        )

        print("\n" + "=" * 72)
        print(f"CASE: {case['label']}")
        print(f"NICHE: {case['niche']}")
        print(f"SOURCES: {', '.join(result.sources_used)}")
        print(f"OPPORTUNITIES: {len(result.opportunities)}")
        print(
            "SEMANTIC UNIVERSE USED:",
            SemanticUniverseSeedAdapter.source_id in result.sources_used,
        )
        print(
            "PROVIDER BACKED:",
            RealTrendProviderAdapter.source_id in result.sources_used,
        )

        if result.opportunities:
            top = result.opportunities[0]
            top_meta = top.metadata
            print(f"TOP TOPIC: {top.topic}")
            print(f"TOP SOURCE: {top.source}")
            print(f"NICHE FIT: {top.scores.niche_fit_score}")
            if top_meta.get("provider_backed"):
                print(f"PROVIDER NAME: {top_meta.get('provider_name')}")
                print(f"PROVIDER CONFIDENCE: {top_meta.get('provider_confidence')}")

        if result.best_signal:
            print(f"BEST TOPIC: {result.best_signal.topic}")
            print(f"BEST SCORE: {result.best_signal.virality_score}")
            print(f"BEST SOURCE: {result.best_signal.source}")
            print("SIGNAL VALID:", result.best_signal.validate().is_valid)

        print("JSON SAFE:", isinstance(result.to_dict(), dict))

    print("\n" + "=" * 72)
    print("CHANNEL IDENTITY AUTO-TOPIC CHECK")
    channel = ChannelIdentity(
        channel_name="Scent Signal",
        main_niche="perfume niche reviews",
        sub_niche="airport duty-free scent testing",
        audience="Fragrance enthusiasts comparing dupes",
        tone_story_style="luxury_brand",
        platform="Instagram Reels",
    )
    channel_profile = loader.resolve_from_channel_identity(channel)
    channel_result = engine.discover(
        profile=channel_profile,
        niche=str(channel_profile.get("niche", "")),
        topic="",
        max_results=5,
    )
    print("CHANNEL:", channel.channel_name)
    print("SOURCES:", ", ".join(channel_result.sources_used))
    if channel_result.best_signal:
        print("BEST TOPIC:", channel_result.best_signal.topic)
        print("BEST SOURCE:", channel_result.best_signal.source)
    niche_label = str(channel_profile.get("niche_label", "")).lower()
    if channel_result.best_signal and niche_label:
        repeats_label = niche_label in channel_result.best_signal.topic.lower()
        print("REPEATS FULL NICHE LABEL:", repeats_label)

    fallback = TrendDiscoveryEngine(use_provider_layer=False)
    fallback_profile = loader.resolve(niche="comedy")
    fallback_result = fallback.discover(
        profile=fallback_profile,
        niche="comedy",
        topic="",
        max_results=3,
    )
    print("\n" + "=" * 72)
    print("LOCAL FALLBACK (provider layer disabled)")
    print(f"SOURCES: {', '.join(fallback_result.sources_used)}")
    print(
        "PROVIDER BACKED:",
        RealTrendProviderAdapter.source_id in fallback_result.sources_used,
    )
    if fallback_result.best_signal:
        print("BEST TOPIC:", fallback_result.best_signal.topic)
