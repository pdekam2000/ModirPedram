"""
Trend Intelligence V2 — classify trends and compute opportunity scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_studio_preflight import MOCK_ONLY_SOURCES


@dataclass
class TrendIntelligenceItem:
    trend: str
    source: str
    classification: str
    competition_level: str
    ctr_potential: str
    educational_value: str
    viral_potential: str
    trend_opportunity_score: float = 0.0
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend": self.trend,
            "source": self.source,
            "classification": self.classification,
            "competition_level": self.competition_level,
            "ctr_potential": self.ctr_potential,
            "educational_value": self.educational_value,
            "viral_potential": self.viral_potential,
            "trend_opportunity_score": round(self.trend_opportunity_score, 4),
            "score": round(self.score, 4),
            "metadata": dict(self.metadata),
        }


def classify_trend_mode_v2(sources_used: list[str], *, use_live_trends: bool = True) -> str:
    cleaned = [str(item).strip() for item in sources_used if str(item).strip()]
    live = [source for source in cleaned if source not in MOCK_ONLY_SOURCES]
    if live and any(source in MOCK_ONLY_SOURCES for source in cleaned):
        return "hybrid"
    if live:
        return "live_api"
    if use_live_trends:
        return "fallback_seed_expansion"
    return "fallback_seed_expansion"


def analyze_trend_opportunities(
    trends: list[dict[str, Any]],
    *,
    topic: str,
    trend_mode: str = "fallback_seed_expansion",
) -> dict[str, Any]:
    items: list[TrendIntelligenceItem] = []
    for raw in trends:
        trend_text = str(raw.get("trend") or raw.get("topic") or "").strip()
        if not trend_text:
            continue
        score = float(raw.get("score") or raw.get("overall_trend_score") or 0.5)
        source = str(raw.get("source") or raw.get("provider_id") or "seed")
        classification = _classify_trend(trend_text, score)
        competition = "high competition" if score < 0.45 else "low competition"
        ctr = "high CTR potential" if any(word in trend_text.lower() for word in ("how", "why", "best", "mistake", "secret")) else "medium CTR potential"
        edu = "high educational value" if any(word in trend_text.lower() for word in ("how", "guide", "method", "tutorial", "step")) else "medium educational value"
        viral = "high viral potential" if any(word in trend_text.lower() for word in ("challenge", "mistake", "never", "ignore", "fast")) else "medium viral potential"
        opportunity = min(
            1.0,
            score * 0.45
            + (0.2 if classification in {"rising", "evergreen"} else 0.1)
            + (0.15 if ctr.startswith("high") else 0.08)
            + (0.1 if edu.startswith("high") else 0.05)
            + (0.1 if viral.startswith("high") else 0.05),
        )
        items.append(
            TrendIntelligenceItem(
                trend=trend_text,
                source=source,
                classification=classification,
                competition_level=competition,
                ctr_potential=ctr,
                educational_value=edu,
                viral_potential=viral,
                trend_opportunity_score=opportunity,
                score=score,
                metadata=dict(raw.get("metadata") or {}),
            )
        )
    items.sort(key=lambda item: item.trend_opportunity_score, reverse=True)
    best = items[0].trend_opportunity_score if items else 0.0
    return {
        "trend_mode": trend_mode,
        "topic": topic,
        "items": [item.to_dict() for item in items[:15]],
        "best_trend_opportunity_score": round(best, 4),
        "summary": {
            "count": len(items),
            "rising": sum(1 for item in items if item.classification == "rising"),
            "evergreen": sum(1 for item in items if item.classification == "evergreen"),
            "seasonal": sum(1 for item in items if item.classification == "seasonal"),
        },
    }


def _classify_trend(text: str, score: float) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("winter", "summer", "spring", "holiday", "season")):
        return "seasonal"
    if any(word in lowered for word in ("how", "guide", "tutorial", "method", "best")):
        return "evergreen"
    if score >= 0.72:
        return "rising"
    if score < 0.35:
        return "declining"
    return "evergreen"


__all__ = [
    "analyze_trend_opportunities",
    "classify_trend_mode_v2",
]
