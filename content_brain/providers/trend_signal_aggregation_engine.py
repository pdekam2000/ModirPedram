"""
Multi-provider trend signal aggregation for the Viral Content Brain.

Clusters duplicate topics, applies provider weighting, and ranks merged signals.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
import re

from content_brain.providers.real_trend_provider import (
    NormalizedTrendSignal,
    TrendMomentum,
    TrendProviderContext,
)


ENGINE_VERSION = "trend_signal_aggregation_v1"

LIVE_PROVIDER_IDS = frozenset({"dataforseo", "serpapi"})
MOCK_PROVIDER_ID = "mock_trend_provider"

DEFAULT_LIVE_WEIGHTS = {
    "dataforseo": 0.40,
    "serpapi": 0.35,
    MOCK_PROVIDER_ID: 0.05,
}
MOCK_ONLY_WEIGHT = 1.0

TOKEN_JACCARD_THRESHOLD = 0.75
CORROBORATION_BOOST_STEP = 0.05
CORROBORATION_BOOST_MAX = 0.15
INTERNAL_CANDIDATE_CAP = 20

MOMENTUM_MULTIPLIERS = {
    TrendMomentum.SPIKING.value: 1.15,
    TrendMomentum.RISING.value: 1.08,
    TrendMomentum.STABLE.value: 1.00,
    TrendMomentum.COOLING.value: 0.92,
}


class TrendSignalAggregationEngine:
    """Aggregate and rank NormalizedTrendSignal items from multiple providers."""

    def aggregate(
        self,
        signals: list[NormalizedTrendSignal],
        context: TrendProviderContext,
    ) -> list[NormalizedTrendSignal]:
        if not signals:
            return []

        try:
            return self._aggregate_safe(signals, context)
        except Exception:
            return _fallback_aggregate(signals, context.max_results)

    def _aggregate_safe(
        self,
        signals: list[NormalizedTrendSignal],
        context: TrendProviderContext,
    ) -> list[NormalizedTrendSignal]:
        weights = _resolve_provider_weights(signals, context)
        tagged = [_tag_signal(signal, index, weights) for index, signal in enumerate(signals)]

        authoritative = [
            item for item in tagged if _is_user_topic_authoritative(item["signal"])
        ]
        regular = [
            item for item in tagged if not _is_user_topic_authoritative(item["signal"])
        ]

        clusters = _cluster_signals(regular)
        merged = [_merge_cluster(cluster, weights) for cluster in clusters]

        authoritative_merged = [
            _finalize_authoritative(item, weights) for item in authoritative
        ]

        ranked = authoritative_merged + merged
        ranked.sort(
            key=lambda signal: float(
                signal.metadata.get("final_rank_score", signal.confidence)
            ),
            reverse=True,
        )

        max_results = max(1, int(context.max_results))
        return ranked[:max_results]


def _aggregate_safe_standalone(
    signals: list[NormalizedTrendSignal],
    context: TrendProviderContext,
) -> list[NormalizedTrendSignal]:
    return TrendSignalAggregationEngine().aggregate(signals, context)


def _resolve_provider_weights(
    signals: list[NormalizedTrendSignal],
    context: TrendProviderContext,
) -> dict[str, float]:
    profile = context.profile if isinstance(context.profile, dict) else {}
    trend_discovery = profile.get("trend_discovery", {})
    profile_weights = {}
    if isinstance(trend_discovery, dict):
        raw = trend_discovery.get("provider_weights", {})
        if isinstance(raw, dict):
            profile_weights = {
                str(key): float(value)
                for key, value in raw.items()
                if str(key).strip()
            }

    present = {
        str(signal.provider_id or MOCK_PROVIDER_ID).strip()
        for signal in signals
        if str(signal.provider_id or "").strip()
    }
    if not present:
        present = {MOCK_PROVIDER_ID}

    has_live = bool(present.intersection(LIVE_PROVIDER_IDS))

    if profile_weights:
        active = {key: profile_weights[key] for key in present if key in profile_weights}
        if active:
            return _renormalize_weights(active)

    if not has_live:
        return {MOCK_PROVIDER_ID: MOCK_ONLY_WEIGHT}

    active = {
        key: DEFAULT_LIVE_WEIGHTS[key]
        for key in present
        if key in DEFAULT_LIVE_WEIGHTS
    }
    if MOCK_PROVIDER_ID in present:
        active[MOCK_PROVIDER_ID] = DEFAULT_LIVE_WEIGHTS[MOCK_PROVIDER_ID]
    for provider_id in present:
        if provider_id not in active and provider_id in LIVE_PROVIDER_IDS:
            active[provider_id] = DEFAULT_LIVE_WEIGHTS.get(provider_id, 0.35)

    return _renormalize_weights(active)


def _renormalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in weights.values())
    if total <= 0:
        return {MOCK_PROVIDER_ID: MOCK_ONLY_WEIGHT}
    return {
        key: round(max(0.0, value) / total, 4)
        for key, value in weights.items()
    }


def _tag_signal(
    signal: NormalizedTrendSignal,
    index: int,
    weights: dict[str, float],
) -> dict[str, Any]:
    provider_id = str(signal.provider_id or MOCK_PROVIDER_ID).strip() or MOCK_PROVIDER_ID
    weight = weights.get(provider_id, 0.0)
    provider_base = _provider_base_score(signal, weight)
    return {
        "signal": signal,
        "index": index,
        "provider_id": provider_id,
        "weight": weight,
        "provider_base": provider_base,
        "normalized_topic": _normalize_topic(signal.trend_topic),
        "tokens": _tokenize(signal.trend_topic),
    }


def _provider_base_score(signal: NormalizedTrendSignal, weight: float) -> float:
    momentum = str(signal.momentum or TrendMomentum.STABLE.value)
    multiplier = MOMENTUM_MULTIPLIERS.get(momentum, 1.0)
    return round(max(0.0, float(signal.confidence) * weight * multiplier), 4)


def _cluster_signals(tagged: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    capped = tagged[:INTERNAL_CANDIDATE_CAP]
    clusters: list[list[dict[str, Any]]] = []

    for item in capped:
        matched_cluster: list[dict[str, Any]] | None = None
        for cluster in clusters:
            if _should_merge(item, cluster[0]):
                matched_cluster = cluster
                break
        if matched_cluster is None:
            clusters.append([item])
        else:
            matched_cluster.append(item)

    return clusters


def _should_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["normalized_topic"] == right["normalized_topic"]:
        return True

    jaccard = _token_jaccard(left["tokens"], right["tokens"])
    if jaccard >= TOKEN_JACCARD_THRESHOLD:
        return True

    return _substring_merge(left["tokens"], right["tokens"])


def _merge_cluster(
    cluster: list[dict[str, Any]],
    weights: dict[str, float],
) -> NormalizedTrendSignal:
    canonical_item = max(
        cluster,
        key=lambda item: (
            item["provider_base"],
            item["signal"].niche_match,
            1 if item["provider_id"] in LIVE_PROVIDER_IDS else 0,
        ),
    )
    canonical = canonical_item["signal"]

    provider_bases = [item["provider_base"] for item in cluster]
    niche_matches = [item["signal"].niche_match for item in cluster]
    freshness_scores = [item["signal"].freshness_score for item in cluster]

    provider_ids = sorted({item["provider_id"] for item in cluster})
    corroboration_boost = min(
        CORROBORATION_BOOST_MAX,
        CORROBORATION_BOOST_STEP * max(0, len(provider_ids) - 1),
    )

    aggregation_score = round(
        min(
            1.0,
            max(provider_bases)
            + (sum(provider_bases) / len(provider_bases)) * 0.25
            + corroboration_boost
            + (sum(niche_matches) / len(niche_matches)) * 0.20
            + (sum(freshness_scores) / len(freshness_scores)) * 0.10,
        ),
        4,
    )
    enrichment_delta = float(canonical.metadata.get("enrichment_score_delta", 0.0) or 0.0)
    final_rank_score = round(
        min(1.0, max(0.0, aggregation_score + enrichment_delta)),
        4,
    )

    duplicate_members = []
    for item in cluster:
        if item is canonical_item:
            continue
        duplicate_members.append(
            {
                "provider_id": item["provider_id"],
                "topic": item["signal"].trend_topic,
                "merge_reason": _merge_reason(item, canonical_item),
            }
        )

    providers_meta = []
    for item in cluster:
        providers_meta.append(
            {
                "provider_id": item["provider_id"],
                "source": item["signal"].source,
                "original_topic": item["signal"].trend_topic,
                "confidence": round(float(item["signal"].confidence), 4),
                "niche_match": round(float(item["signal"].niche_match), 4),
                "momentum": item["signal"].momentum,
                "weight": round(float(item["weight"]), 4),
                "provider_base": round(float(item["provider_base"]), 4),
            }
        )

    metadata = dict(canonical.metadata)
    metadata["aggregation"] = {
        "cluster_id": f"cluster_{canonical_item['index']:03d}",
        "canonical_topic": canonical.trend_topic,
        "aggregation_score": aggregation_score,
        "final_rank_score": final_rank_score,
        "corroboration_boost": round(corroboration_boost, 4),
        "provider_count": len(provider_ids),
        "providers": providers_meta,
        "duplicate_members": duplicate_members[:3],
        "engine_version": ENGINE_VERSION,
    }
    metadata["aggregation_score"] = aggregation_score
    metadata["final_rank_score"] = final_rank_score

    momentum = canonical_item["signal"].momentum

    return replace(
        canonical,
        provider_id=canonical_item["provider_id"],
        momentum=momentum,
        metadata=metadata,
    )


def _finalize_authoritative(
    item: dict[str, Any],
    weights: dict[str, float],
) -> NormalizedTrendSignal:
    signal = item["signal"]
    aggregation_score = round(
        min(1.0, max(item["provider_base"], float(signal.confidence))),
        4,
    )
    enrichment_delta = float(signal.metadata.get("enrichment_score_delta", 0.0) or 0.0)
    final_rank_score = round(
        min(1.0, max(aggregation_score, aggregation_score + enrichment_delta)),
        4,
    )

    metadata = dict(signal.metadata)
    metadata["user_topic_authoritative"] = True
    metadata["priority"] = "user_topic"
    metadata["aggregation_score"] = aggregation_score
    metadata["final_rank_score"] = final_rank_score
    metadata["aggregation"] = {
        "cluster_id": f"cluster_auth_{item['index']:03d}",
        "canonical_topic": signal.trend_topic,
        "aggregation_score": aggregation_score,
        "final_rank_score": final_rank_score,
        "corroboration_boost": 0.0,
        "provider_count": 1,
        "providers": [
            {
                "provider_id": item["provider_id"],
                "source": signal.source,
                "original_topic": signal.trend_topic,
                "confidence": round(float(signal.confidence), 4),
                "niche_match": round(float(signal.niche_match), 4),
                "momentum": signal.momentum,
                "weight": round(float(item["weight"]), 4),
                "provider_base": round(float(item["provider_base"]), 4),
            }
        ],
        "duplicate_members": [],
        "engine_version": ENGINE_VERSION,
        "authoritative_tier": 0,
    }

    return replace(signal, metadata=metadata)


def _fallback_aggregate(
    signals: list[NormalizedTrendSignal],
    max_results: int,
) -> list[NormalizedTrendSignal]:
    ranked = sorted(signals, key=lambda item: item.confidence, reverse=True)
    seen: set[str] = set()
    deduped: list[NormalizedTrendSignal] = []
    for signal in ranked:
        key = _normalize_topic(signal.trend_topic)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
        if len(deduped) >= max(1, int(max_results)):
            break
    return deduped


def _is_user_topic_authoritative(signal: NormalizedTrendSignal) -> bool:
    metadata = signal.metadata if isinstance(signal.metadata, dict) else {}
    return bool(
        metadata.get("user_topic_authoritative")
        or metadata.get("priority") == "user_topic"
    )


def _normalize_topic(value: str) -> str:
    cleaned = re.sub(r"[^\w\s\-']", " ", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokenize(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return {token for token in cleaned.split() if token}


def _token_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left.intersection(right))
    union = len(left.union(right))
    if union == 0:
        return 0.0
    return intersection / union


def _substring_merge(left: set[str], right: set[str]) -> bool:
    if len(left) < 2 and len(right) < 2:
        return False
    smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
    if len(smaller) < 2:
        return False
    return smaller.issubset(larger)


def _merge_reason(item: dict[str, Any], canonical_item: dict[str, Any]) -> str:
    if item["normalized_topic"] == canonical_item["normalized_topic"]:
        return "exact_normalized"
    jaccard = _token_jaccard(item["tokens"], canonical_item["tokens"])
    if jaccard >= TOKEN_JACCARD_THRESHOLD:
        return f"token_jaccard_{jaccard:.2f}"
    return "substring_overlap"


__all__ = [
    "DEFAULT_LIVE_WEIGHTS",
    "ENGINE_VERSION",
    "LIVE_PROVIDER_IDS",
    "MOCK_ONLY_WEIGHT",
    "MOCK_PROVIDER_ID",
    "TrendSignalAggregationEngine",
]


if __name__ == "__main__":
    from content_brain.providers.openai_trend_enricher import (
        ENRICHMENT_PROVIDER_NAME,
        OpenAITrendEnricher,
    )

    context = TrendProviderContext(niche="football", topic="", profile={}, max_results=10)
    engine = TrendSignalAggregationEngine()

    print("=" * 72)
    print("TREND SIGNAL AGGREGATION SMOKE")
    print("=" * 72)

    mock_only = [
        NormalizedTrendSignal(
            trend_topic="late match decisions",
            source="mock_local_seed",
            confidence=0.88,
            freshness_score=0.9,
            niche_match=0.85,
            momentum="rising",
            provider_id="mock_trend_provider",
        )
    ]
    mock_weights = _resolve_provider_weights(mock_only, context)
    print("MOCK ONLY WEIGHTS:", mock_weights)
    assert mock_weights.get(MOCK_PROVIDER_ID) == 1.0

    multi_provider = [
        NormalizedTrendSignal(
            trend_topic="VAR penalty controversy",
            source="dataforseo_google_ads",
            confidence=0.81,
            freshness_score=0.82,
            niche_match=0.82,
            momentum="rising",
            provider_id="dataforseo",
        ),
        NormalizedTrendSignal(
            trend_topic="VAR penalty controversy",
            source="serpapi_google_trends",
            confidence=0.75,
            freshness_score=0.86,
            niche_match=0.66,
            momentum="spiking",
            provider_id="serpapi",
        ),
        NormalizedTrendSignal(
            trend_topic="late match decisions",
            source="mock_local_seed",
            confidence=0.88,
            freshness_score=0.9,
            niche_match=0.85,
            momentum="rising",
            provider_id="mock_trend_provider",
        ),
    ]
    live_weights = _resolve_provider_weights(multi_provider, context)
    print("LIVE ACTIVE WEIGHTS:", live_weights)
    assert live_weights.get(MOCK_PROVIDER_ID, 0) < live_weights.get("dataforseo", 1)
    assert live_weights.get("dataforseo", 0) > live_weights.get(MOCK_PROVIDER_ID, 0)

    merged = engine.aggregate(multi_provider, context)
    print("MULTI MERGE COUNT:", len(merged))
    top = merged[0]
    print("TOP TOPIC:", top.trend_topic)
    print("AGGREGATION SCORE:", top.metadata.get("aggregation_score"))
    print("PROVIDER COUNT:", top.metadata.get("aggregation", {}).get("provider_count"))
    assert top.metadata.get("aggregation", {}).get("provider_count") == 2

    duplicate_cluster = [
        NormalizedTrendSignal(
            trend_topic="AI agents",
            source="dataforseo_google_ads",
            confidence=0.7,
            freshness_score=0.7,
            niche_match=0.7,
            momentum="stable",
            provider_id="dataforseo",
        ),
        NormalizedTrendSignal(
            trend_topic="ai agents",
            source="serpapi_google_trends",
            confidence=0.72,
            freshness_score=0.71,
            niche_match=0.69,
            momentum="rising",
            provider_id="serpapi",
        ),
        NormalizedTrendSignal(
            trend_topic="Agentic AI workflows",
            source="dataforseo_google_ads",
            confidence=0.68,
            freshness_score=0.69,
            niche_match=0.67,
            momentum="stable",
            provider_id="dataforseo",
        ),
    ]
    clustered = engine.aggregate(duplicate_cluster, context)
    print("CLUSTER RESULT COUNT:", len(clustered))
    assert len(clustered) == 2

    class FakeEngine:
        TREND_ENRICHMENT_CATEGORY = "trend_enrichment"

        def get_ready_trend_enrichment(self):
            return None

    enricher_disabled = OpenAITrendEnricher(registry_engine=FakeEngine(), dry_run=False)
    print("OPENAI DISABLED ENABLED:", enricher_disabled.enabled)
    unchanged = enricher_disabled.enrich(multi_provider, context)
    print("OPENAI DISABLED PASSTHROUGH:", len(unchanged) == len(multi_provider))

    class ReadyEngine:
        TREND_ENRICHMENT_CATEGORY = "trend_enrichment"

        def get_ready_trend_enrichment(self):
            return ENRICHMENT_PROVIDER_NAME

        def get_provider_credentials(self, category, name):
            return {"OPENAI_API_KEY": "test-key"}

    enricher = OpenAITrendEnricher(registry_engine=ReadyEngine(), dry_run=True)
    aggregated_for_enrich = engine.aggregate(multi_provider, context)
    enriched = enricher.enrich(aggregated_for_enrich[:12], context)
    print("OPENAI DRY-RUN ENRICHED:", len(enriched))
    print("ENRICHMENT APPLIED:", enriched[0].metadata.get("enrichment_applied"))
    print("CONFIDENCE UNCHANGED:", enriched[0].confidence == aggregated_for_enrich[0].confidence)

    print("ALL AGGREGATION TESTS PASSED")
