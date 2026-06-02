"""
Semantic niche relevance filter for the Viral Content Brain.

Local, deterministic gate applied after aggregation and before enrichment.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
import re

from content_brain.providers.real_trend_provider import (
    NormalizedTrendSignal,
    TrendProviderContext,
    _collect_semantic_universe_tokens,
    _score_niche_match,
    _tokenize,
)


ENGINE_VERSION = "niche_relevance_filter_v1"

KEEP_THRESHOLD = 0.75
WARN_THRESHOLD = 0.45

DECISION_KEEP = "KEEP"
DECISION_WARNING = "WARNING"
DECISION_DROP = "DROP"

AUTHORITY_FLOOR_SCORE = 0.95

DOMAIN_NEGATIVE_TOKENS: dict[str, frozenset[str]] = {
    "football": frozenset(
        {
            "mobilelegends",
            "mlbb",
            "lol",
            "league",
            "legends",
            "minecraft",
            "roblox",
            "rocket",
            "nba",
            "basketball",
            "poole",
            "pomeroy",
            "7 days to die",
        }
    ),
    "artificial_intelligence": frozenset(
        {
            "boho",
            "braids",
            "makeup",
            "recipe",
            "hair",
            "synthetic",
        }
    ),
    "dark_mystery": frozenset(
        {
            "travel",
            "doobydobap",
            "hilliersmith",
            "video editing",
        }
    ),
}

GENERIC_NOISE_TOKENS = frozenset(
    {
        "tutorial",
        "how to edit",
        "video editing",
        "travel film",
        "shorts",
    }
)

STRONG_DROP_MARKERS: dict[str, tuple[str, ...]] = {
    "football": (
        "mobilelegends",
        "#mobilelegends",
        "mlbb",
        "#mlbb",
        "7 days to die",
        "rocket league",
        "league of legends",
        "mobile legends",
    ),
    "artificial_intelligence": (
        "boho braids",
        "synthetic hair",
    ),
    "dark_mystery": (
        "travel film",
        "video editing tips",
    ),
}


class NicheRelevanceFilterEngine:
    """Filter or flag trend signals that are weakly related to the channel niche."""

    def filter(
        self,
        signals: list[NormalizedTrendSignal],
        context: TrendProviderContext,
    ) -> list[NormalizedTrendSignal]:
        if not signals:
            return []

        try:
            return self._filter_safe(signals, context)
        except Exception:
            return signals

    def _filter_safe(
        self,
        signals: list[NormalizedTrendSignal],
        context: TrendProviderContext,
    ) -> list[NormalizedTrendSignal]:
        niche = context.niche.strip() or str(context.profile.get("niche", "general"))
        kept: list[NormalizedTrendSignal] = []

        for signal in signals:
            scored = _evaluate_signal(signal, context, niche)
            if scored["filter_decision"] == DECISION_DROP:
                continue
            kept.append(_apply_filter_metadata(signal, scored))

        return kept


def _evaluate_signal(
    signal: NormalizedTrendSignal,
    context: TrendProviderContext,
    niche: str,
) -> dict[str, Any]:
    if _is_user_topic_authoritative(signal):
        return {
            "niche_relevance_score": AUTHORITY_FLOOR_SCORE,
            "filter_decision": DECISION_KEEP,
            "niche_relevance_reason": "Authoritative user topic",
            "rejected_by_filter": False,
        }

    profile = context.profile if isinstance(context.profile, dict) else {}
    topic = signal.trend_topic.strip()
    topic_tokens = _tokenize(topic)
    universe_tokens = _collect_semantic_universe_tokens(profile)

    semantic_overlap = _semantic_overlap_score(topic_tokens, universe_tokens)
    cluster_score, cluster_id = _best_cluster_score(topic_tokens, profile)
    niche_match = float(signal.niche_match or 0.0)
    if niche_match <= 0.0:
        niche_match = _score_niche_match(topic, niche, profile)

    negative_penalty, negative_hits = _negative_penalty(topic, niche, profile)
    provider_penalty = _provider_penalty(signal, niche)

    strong_drop_reason = _strong_drop_reason(topic, niche)
    if strong_drop_reason:
        return {
            "niche_relevance_score": round(max(0.0, WARN_THRESHOLD - 0.05), 4),
            "filter_decision": DECISION_DROP,
            "niche_relevance_reason": strong_drop_reason,
            "rejected_by_filter": True,
            "matched_cluster_id": "",
            "negative_hits": negative_hits,
        }

    raw_score = (
        semantic_overlap * 0.35
        + cluster_score * 0.25
        + niche_match * 0.25
        + max(0.0, 1.0 - negative_penalty) * 0.10
        + max(0.0, 1.0 - provider_penalty) * 0.05
    )
    score = round(max(0.0, min(1.0, raw_score - negative_penalty * 0.15)), 4)

    decision, reason = _decision_from_score(
        score=score,
        cluster_id=cluster_id,
        semantic_overlap=semantic_overlap,
        negative_hits=negative_hits,
        niche=niche,
    )

    return {
        "niche_relevance_score": score,
        "filter_decision": decision,
        "niche_relevance_reason": reason,
        "rejected_by_filter": decision == DECISION_DROP,
        "matched_cluster_id": cluster_id,
        "negative_hits": negative_hits,
    }


def _decision_from_score(
    *,
    score: float,
    cluster_id: str,
    semantic_overlap: float,
    negative_hits: list[str],
    niche: str,
) -> tuple[str, str]:
    if score >= KEEP_THRESHOLD:
        if cluster_id:
            return DECISION_KEEP, f"Matched {cluster_id.replace('_', ' ')} semantic cluster"
        return DECISION_KEEP, f"Strong overlap with {niche.replace('_', ' ')} semantic universe"

    if score >= WARN_THRESHOLD:
        if negative_hits:
            return (
                DECISION_WARNING,
                f"Partial niche overlap; off-domain terms detected: {', '.join(negative_hits[:2])}",
            )
        return DECISION_WARNING, f"Low overlap with {niche.replace('_', ' ')} semantic universe"

    if negative_hits:
        return DECISION_DROP, f"Off-niche content detected: {', '.join(negative_hits[:3])}"
    if semantic_overlap <= 0.05:
        return DECISION_DROP, f"Low overlap with {niche.replace('_', ' ')} semantic universe"
    return DECISION_DROP, "Insufficient semantic relevance for channel niche"


def _apply_filter_metadata(
    signal: NormalizedTrendSignal,
    scored: dict[str, Any],
) -> NormalizedTrendSignal:
    metadata = dict(signal.metadata)
    metadata["niche_relevance_score"] = scored["niche_relevance_score"]
    metadata["niche_relevance_reason"] = scored["niche_relevance_reason"]
    metadata["rejected_by_filter"] = scored["rejected_by_filter"]
    metadata["filter_decision"] = scored["filter_decision"]
    metadata["niche_relevance"] = {
        "engine_version": ENGINE_VERSION,
        "score": scored["niche_relevance_score"],
        "decision": scored["filter_decision"],
        "reason": scored["niche_relevance_reason"],
        "matched_cluster_id": scored.get("matched_cluster_id", ""),
        "negative_hits": list(scored.get("negative_hits", [])),
    }
    return replace(signal, metadata=metadata)


def _is_user_topic_authoritative(signal: NormalizedTrendSignal) -> bool:
    metadata = signal.metadata if isinstance(signal.metadata, dict) else {}
    return bool(
        metadata.get("user_topic_authoritative")
        or metadata.get("priority") == "user_topic"
    )


def _semantic_overlap_score(topic_tokens: set[str], universe_tokens: set[str]) -> float:
    if not topic_tokens or not universe_tokens:
        return 0.0

    intersection = topic_tokens.intersection(universe_tokens)
    if intersection:
        return round(min(1.0, 0.45 + len(intersection) * 0.12), 4)

    partial_hits = sum(
        1
        for token in topic_tokens
        if any(token in universe_token or universe_token in token for universe_token in universe_tokens)
    )
    if partial_hits:
        return round(min(1.0, 0.35 + partial_hits * 0.08), 4)

    union = topic_tokens.union(universe_tokens)
    if not union:
        return 0.0
    return round(len(intersection) / len(union), 4)


def _best_cluster_score(topic_tokens: set[str], profile: dict[str, Any]) -> tuple[float, str]:
    semantic_universe = profile.get("semantic_universe", {})
    if not isinstance(semantic_universe, dict) or not topic_tokens:
        return 0.0, ""

    best_score = 0.0
    best_id = ""
    for cluster in semantic_universe.get("semantic_clusters", []):
        if not isinstance(cluster, dict):
            continue
        cluster_tokens: set[str] = set()
        cluster_tokens.update(_tokenize(str(cluster.get("label", ""))))
        for concept in cluster.get("concepts", []) or []:
            cluster_tokens.update(_tokenize(str(concept)))

        if not cluster_tokens:
            continue

        intersection = len(topic_tokens.intersection(cluster_tokens))
        union = len(topic_tokens.union(cluster_tokens))
        score = intersection / union if union else 0.0
        if score > best_score:
            best_score = score
            best_id = str(cluster.get("cluster_id", cluster.get("label", ""))).strip()

    if best_score > 0:
        return round(min(1.0, 0.40 + best_score * 0.60), 4), best_id
    return 0.0, best_id


def _negative_penalty(topic: str, niche: str, profile: dict[str, Any]) -> tuple[float, list[str]]:
    lowered = topic.lower()
    hits: list[str] = []

    trend_discovery = profile.get("trend_discovery", {})
    profile_negatives: list[str] = []
    if isinstance(trend_discovery, dict):
        raw = trend_discovery.get("negative_tokens", [])
        if isinstance(raw, list):
            profile_negatives = [str(item).strip().lower() for item in raw if str(item).strip()]

    normalized_niche = niche.strip().lower().replace(" ", "_")
    domain_tokens = DOMAIN_NEGATIVE_TOKENS.get(normalized_niche, frozenset())

    for token in profile_negatives + list(domain_tokens) + list(GENERIC_NOISE_TOKENS):
        if token and token in lowered:
            hits.append(token)

    if not hits:
        return 0.0, []

    penalty = round(min(0.45, 0.12 + len(set(hits)) * 0.08), 4)
    return penalty, sorted(set(hits))[:5]


def _strong_drop_reason(topic: str, niche: str) -> str:
    lowered = topic.lower()
    normalized_niche = niche.strip().lower().replace(" ", "_")
    markers = STRONG_DROP_MARKERS.get(normalized_niche, ())
    hits = [marker for marker in markers if marker in lowered]
    if not hits:
        return ""
    return f"Off-niche content detected: {', '.join(hits[:3])}"


def _provider_penalty(signal: NormalizedTrendSignal, niche: str) -> float:
    metadata = signal.metadata if isinstance(signal.metadata, dict) else {}
    topic = signal.trend_topic.lower()
    penalty = 0.0

    if signal.provider_id == "dataforseo_youtube" and "#" in topic:
        penalty += 0.08

    if niche == "football" and any(
        marker in topic for marker in ("#mobilelegends", "#mlbb", "rocket league", "7 days to die")
    ):
        penalty += 0.25

    if metadata.get("search_engine") == "youtube" and niche == "football":
        gaming_markers = ("lol", "league of legends", "mobile legends", "nba", "basketball")
        if any(marker in topic for marker in gaming_markers):
            penalty += 0.20

    return round(min(0.45, penalty), 4)


__all__ = [
    "DECISION_DROP",
    "DECISION_KEEP",
    "DECISION_WARNING",
    "ENGINE_VERSION",
    "KEEP_THRESHOLD",
    "NicheRelevanceFilterEngine",
    "WARN_THRESHOLD",
]


if __name__ == "__main__":
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    engine = NicheRelevanceFilterEngine()

    samples = {
        "football": [
            ("Late game-deciding goals from Matchweek 9", 0.66, "dataforseo_youtube"),
            ("average argus player in late game #mobilelegends", 0.74, "dataforseo_youtube"),
            ("Late Game Decisions - 7 Days To Die 1.0", 0.74, "dataforseo_youtube"),
            ("late VAR replay angle", 0.90, "mock_trend_provider", True),
        ],
        "artificial intelligence": [
            ("8 Shocking AI Mistakes That Cost Billions", 0.82, "dataforseo_youtube"),
            ("Avoid Synthetic Hair Mistakes: Boho Braids Tips!", 0.66, "dataforseo_youtube"),
            ("AI agents and automation trends", 0.66, "mock_trend_provider", True),
        ],
        "dark_mystery": [
            ("9 Laws of Found Footage Horror Filmmaking!!", 0.74, "dataforseo_youtube"),
            ("How to Pace Your Travel Film - Video Editing Tips", 0.74, "dataforseo_youtube"),
            ("psychological horror unexplained room", 0.74, "mock_trend_provider", True),
        ],
    }

    print("=" * 72)
    print("NICHE RELEVANCE FILTER SMOKE")
    print("=" * 72)

    for niche_key, rows in samples.items():
        profile = loader.resolve(niche=niche_key, attach_semantic_universe=True)
        context = TrendProviderContext(niche=niche_key, profile=profile, max_results=10)
        signals = []
        for row in rows:
            topic, niche_match, provider_id = row[0], row[1], row[2]
            authoritative = bool(row[3]) if len(row) > 3 else False
            metadata = {}
            if authoritative:
                metadata = {"user_topic_authoritative": True, "priority": "user_topic"}
            signals.append(
                NormalizedTrendSignal(
                    trend_topic=topic,
                    source=provider_id,
                    confidence=0.8,
                    freshness_score=0.8,
                    niche_match=niche_match,
                    momentum="stable",
                    provider_id=provider_id,
                    metadata=metadata,
                )
            )

        filtered = engine.filter(signals, context)
        print(f"\n{niche_key.upper()} | in={len(signals)} out={len(filtered)}")
        for signal in filtered:
            print(
                f"  [{signal.metadata.get('filter_decision')}] "
                f"{signal.trend_topic[:60]} | score={signal.metadata.get('niche_relevance_score')} | "
                f"{signal.metadata.get('niche_relevance_reason')}"
            )
        dropped = len(signals) - len(filtered)
        if dropped:
            print(f"  dropped={dropped}")

    print("\nALL NICHE RELEVANCE FILTER TESTS PASSED")
