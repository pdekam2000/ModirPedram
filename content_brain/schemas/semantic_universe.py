"""
Semantic universe schema contracts for the Viral Content Brain.

Defines the niche → semantic universe layer used by topic generation systems.
JSON-safe serialization compatible with profile enrichment and runtime persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid

ENGINE_VERSION = "semantic_universe_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def generate_universe_id(source_niche: str) -> str:
    slug = _normalize_slug(source_niche)
    suffix = uuid.uuid5(uuid.NAMESPACE_DNS, source_niche.strip().lower()).hex[:8]
    return f"universe_{slug}_{suffix}"


def _normalize_slug(value: str) -> str:
    import re

    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s\-_]", "", cleaned)
    cleaned = re.sub(r"[\s\-]+", "_", cleaned)
    return cleaned[:48].strip("_") or "general"


@dataclass
class SemanticUniverseRequest:
    """Input contract for semantic universe expansion."""

    main_niche: str
    sub_niche: str = ""
    audience: str = ""
    tone: str = ""
    visual_style: str = ""

    def validate(self) -> None:
        if not self.main_niche.strip():
            raise ValueError("SemanticUniverseRequest.main_niche is required.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "main_niche": self.main_niche.strip(),
            "sub_niche": self.sub_niche.strip(),
            "audience": self.audience.strip(),
            "tone": self.tone.strip(),
            "visual_style": self.visual_style.strip(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticUniverseRequest:
        if not isinstance(data, dict):
            raise ValueError("SemanticUniverseRequest.from_dict() expects a dict.")

        return cls(
            main_niche=str(data.get("main_niche", "")),
            sub_niche=str(data.get("sub_niche", "")),
            audience=str(data.get("audience", "")),
            tone=str(data.get("tone", "")),
            visual_style=str(data.get("visual_style", "")),
        )


@dataclass
class SemanticCluster:
    """Grouped concept domain inside a semantic universe."""

    cluster_id: str
    label: str
    concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "label": self.label,
            "concepts": list(self.concepts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticCluster:
        if not isinstance(data, dict):
            raise ValueError("SemanticCluster.from_dict() expects a dict.")

        return cls(
            cluster_id=str(data.get("cluster_id", "")),
            label=str(data.get("label", "")),
            concepts=[str(item) for item in data.get("concepts", []) if str(item).strip()],
        )


@dataclass
class SemanticUniverse:
    """Expanded semantic universe for a niche or channel identity."""

    universe_id: str
    source_niche: str
    niche_slug: str
    domain: str
    semantic_clusters: list[SemanticCluster] = field(default_factory=list)
    topic_seed_pool: list[str] = field(default_factory=list)
    emotional_angles: list[str] = field(default_factory=list)
    audience_angles: list[str] = field(default_factory=list)
    conflict_angles: list[str] = field(default_factory=list)
    trend_angles: list[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    generated_at: str = field(default_factory=_now_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe_id": self.universe_id,
            "source_niche": self.source_niche,
            "niche_slug": self.niche_slug,
            "domain": self.domain,
            "semantic_clusters": [cluster.to_dict() for cluster in self.semantic_clusters],
            "topic_seed_pool": list(self.topic_seed_pool),
            "emotional_angles": list(self.emotional_angles),
            "audience_angles": list(self.audience_angles),
            "conflict_angles": list(self.conflict_angles),
            "trend_angles": list(self.trend_angles),
            "engine_version": self.engine_version,
            "generated_at": self.generated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticUniverse:
        if not isinstance(data, dict):
            raise ValueError("SemanticUniverse.from_dict() expects a dict.")

        clusters = [
            SemanticCluster.from_dict(item)
            for item in data.get("semantic_clusters", [])
            if isinstance(item, dict)
        ]

        return cls(
            universe_id=str(data.get("universe_id", "")),
            source_niche=str(data.get("source_niche", "")),
            niche_slug=str(data.get("niche_slug", "")),
            domain=str(data.get("domain", "custom")),
            semantic_clusters=clusters,
            topic_seed_pool=[str(item) for item in data.get("topic_seed_pool", [])],
            emotional_angles=[str(item) for item in data.get("emotional_angles", [])],
            audience_angles=[str(item) for item in data.get("audience_angles", [])],
            conflict_angles=[str(item) for item in data.get("conflict_angles", [])],
            trend_angles=[str(item) for item in data.get("trend_angles", [])],
            engine_version=str(data.get("engine_version", ENGINE_VERSION)),
            generated_at=str(data.get("generated_at", "")),
            metadata=dict(data.get("metadata", {})),
        )


__all__ = [
    "ENGINE_VERSION",
    "SemanticCluster",
    "SemanticUniverse",
    "SemanticUniverseRequest",
    "generate_universe_id",
]
