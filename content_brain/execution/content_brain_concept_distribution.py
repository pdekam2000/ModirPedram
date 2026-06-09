"""
Content Brain V8.1 — Concept Distribution Engine.

Distributes domain concepts across clip roles (hook / mechanism / payoff)
so prompts do not repeat the same concept set in every clip.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.domain_knowledge_layer import filter_expert_domain_concepts

DISTRIBUTION_LAYER_VERSION = "concept_distribution_v1"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_DOMAIN_WEIGHT = 0.70
PROMPT_DIVERSITY_MIN = 0.70
PROMPT_DIVERSITY_TARGET = 0.80
MAX_ADJACENT_OVERLAP = 0.60

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CACHE_DIR = os.path.join(ROOT, "project_brain", "content_brain_concept_distribution_cache")

CLIP_ROLE_BY_INDEX: dict[int, str] = {1: "hook", 2: "mechanism", 3: "payoff"}
ROLE_BY_CLIP_INDEX = CLIP_ROLE_BY_INDEX

DOMAIN_CLIP_ROLE: dict[str, str] = {
    "business": "payoff",
    "future": "payoff",
    "economics": "payoff",
    "marketing": "payoff",
    "ethics": "payoff",
    "business_history": "hook",
    "science": "hook",
    "perfume": "mechanism",
    "medicine": "mechanism",
    "ai": "mechanism",
    "technology": "mechanism",
    "creative": "mechanism",
}

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hook": (
        "raw material",
        "visual",
        "strip",
        "bottle",
        "surprising",
        "opening",
        "claim",
        "setup",
        "question",
        "molecular",
        "analysis",
        "formulation",
    ),
    "mechanism": (
        "prediction",
        "formulation",
        "accord",
        "mechanism",
        "process",
        "testing",
        "model",
        "algorithm",
        "chemistry",
        "longevity",
        "precision",
        "evidence",
        "comparison",
    ),
    "payoff": (
        "market",
        "brand",
        "consumer",
        "adoption",
        "share",
        "outcome",
        "verdict",
        "impact",
        "positioning",
        "bestseller",
        "success",
        "forecast",
        "2030",
        "survival",
    ),
}


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _concept_key(concept: str) -> str:
    return re.sub(r"\s+", " ", str(concept or "").strip().lower())


def _clip_index_for_role(role: str, clip_count: int) -> int:
    if clip_count <= 1:
        return 1
    if clip_count == 2:
        return 1 if role == "hook" else 2
    if role == "hook":
        return 1
    if role == "payoff":
        return clip_count
    return min(2, clip_count)


def _role_for_clip_index(clip_index: int, clip_count: int) -> str:
    if clip_count <= 2:
        return "hook" if clip_index == 1 else "payoff"
    if clip_index == 1:
        return "hook"
    if clip_index >= clip_count:
        return "payoff"
    return "mechanism"


def _score_concept_for_role(concept: str, role: str) -> float:
    lowered = _concept_key(concept)
    keywords = ROLE_KEYWORDS.get(role, ())
    hits = sum(1 for token in keywords if token in lowered)
    return float(hits)


@dataclass
class ConceptDistributionResult:
    topic: str
    clip_count: int = 3
    clip_assignments: dict[int, dict[str, list[str]]] = field(default_factory=dict)
    concept_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    clip_roles: dict[int, str] = field(default_factory=dict)
    distribution_score: float = 0.0
    openai_applied: bool = False
    openai_distribution_used: bool = False
    cache_hit: bool = False
    estimated_cost_usd: float = 0.0
    source: str = "local_rules"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "clip_count": self.clip_count,
            "clip_assignments": {
                str(index): {
                    "primary": list(values.get("primary") or []),
                    "secondary": list(values.get("secondary") or []),
                    "role": self.clip_roles.get(index, _role_for_clip_index(index, self.clip_count)),
                }
                for index, values in sorted(self.clip_assignments.items())
            },
            "concept_states": dict(self.concept_states),
            "clip_roles": {str(k): v for k, v in self.clip_roles.items()},
            "distribution_score": round(self.distribution_score, 4),
            "openai_applied": self.openai_applied,
            "openai_distribution_used": self.openai_distribution_used,
            "cache_hit": self.cache_hit,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "source": self.source,
            "warnings": list(self.warnings),
        }

    def concepts_for_clip(self, clip_index: int) -> list[str]:
        bucket = self.clip_assignments.get(clip_index) or {}
        merged = list(bucket.get("primary") or []) + list(bucket.get("secondary") or [])
        return list(dict.fromkeys(item for item in merged if item))


def build_local_concept_distribution(
    topic: str,
    *,
    clip_count: int = 3,
    domain_concepts_by_domain: dict[str, list[str]] | None = None,
    flat_concepts: list[str] | None = None,
    clip_beats: list[str] | None = None,
    content_strategy: str = "",
    strategic_angle: str = "",
) -> ConceptDistributionResult:
    del content_strategy, strategic_angle, clip_beats
    by_domain = {
        str(domain): filter_expert_domain_concepts([str(item) for item in concepts or [] if str(item).strip()])
        for domain, concepts in (domain_concepts_by_domain or {}).items()
        if concepts
    }
    if not by_domain and flat_concepts:
        by_domain = {"general": filter_expert_domain_concepts(list(flat_concepts))}

    clip_assignments: dict[int, dict[str, list[str]]] = {
        index: {"primary": [], "secondary": []} for index in range(1, clip_count + 1)
    }
    clip_roles = {index: _role_for_clip_index(index, clip_count) for index in range(1, clip_count + 1)}

    if not by_domain:
        return ConceptDistributionResult(topic=topic, clip_count=clip_count, clip_assignments=clip_assignments, clip_roles=clip_roles)

    domain_order = sorted(
        by_domain.keys(),
        key=lambda domain: (
            {"hook": 0, "mechanism": 1, "payoff": 2}.get(DOMAIN_CLIP_ROLE.get(domain, "mechanism"), 1),
            domain,
        ),
    )

    for domain in domain_order:
        role = DOMAIN_CLIP_ROLE.get(domain, "mechanism")
        target_clip = _clip_index_for_role(role, clip_count)
        concepts = list(by_domain.get(domain) or [])
        if not concepts:
            continue
        ranked = sorted(
            concepts,
            key=lambda concept: _score_concept_for_role(concept, clip_roles[target_clip]),
            reverse=True,
        )
        primary_count = 3 if clip_count >= 3 else 2
        primaries = ranked[:primary_count]
        clip_assignments[target_clip]["primary"].extend(
            item for item in primaries if item not in clip_assignments[target_clip]["primary"]
        )
        remainder = [item for item in ranked if item not in primaries]
        if remainder and target_clip > 1:
            clip_assignments[target_clip - 1]["secondary"].append(remainder[0])
        if len(remainder) > 1 and target_clip < clip_count:
            clip_assignments[target_clip + 1]["secondary"].append(remainder[1])

    for index in range(1, clip_count + 1):
        clip_assignments[index]["primary"] = list(dict.fromkeys(clip_assignments[index]["primary"]))[:3]
        clip_assignments[index]["secondary"] = [
            item
            for item in dict.fromkeys(clip_assignments[index]["secondary"])
            if item not in clip_assignments[index]["primary"]
        ][:2]

    concept_states: dict[str, dict[str, Any]] = {}
    all_concepts = [
        concept
        for domain_concepts in by_domain.values()
        for concept in domain_concepts
    ]
    for concept in all_concepts:
        key = _concept_key(concept)
        primary_clip: int | None = None
        secondary_clips: list[int] = []
        for clip_index, bucket in clip_assignments.items():
            if concept in bucket.get("primary") or []:
                primary_clip = clip_index
            elif concept in bucket.get("secondary") or []:
                secondary_clips.append(clip_index)
        concept_states[key] = {
            "label": concept,
            "primary": primary_clip,
            "secondary": secondary_clips,
            "unused": primary_clip is None and not secondary_clips,
        }

    score = _score_distribution(clip_assignments, concept_states, clip_count)
    return ConceptDistributionResult(
        topic=topic,
        clip_count=clip_count,
        clip_assignments=clip_assignments,
        concept_states=concept_states,
        clip_roles=clip_roles,
        distribution_score=score,
        source="local_rules",
    )


def _score_distribution(
    clip_assignments: dict[int, dict[str, list[str]]],
    concept_states: dict[str, dict[str, Any]],
    clip_count: int,
) -> float:
    if clip_count <= 0:
        return 0.0
    primaries_per_clip = [set(_concept_key(c) for c in (clip_assignments[i].get("primary") or [])) for i in range(1, clip_count + 1)]
    if not any(primaries_per_clip):
        return 0.0
    universal = set.intersection(*primaries_per_clip) if len(primaries_per_clip) > 1 else set()
    overlap_penalty = 0.0
    for left, right in zip(primaries_per_clip, primaries_per_clip[1:]):
        if not left and not right:
            continue
        union = left | right
        if not union:
            continue
        overlap = len(left & right) / len(union)
        if overlap > MAX_ADJACENT_OVERLAP:
            overlap_penalty += (overlap - MAX_ADJACENT_OVERLAP) * 0.5
    unused_ratio = sum(1 for state in concept_states.values() if state.get("unused")) / max(1, len(concept_states))
    coverage = sum(1 for bucket in clip_assignments.values() if bucket.get("primary")) / clip_count
    score = 0.55 + coverage * 0.25 + (0.20 if not universal else 0.0) - overlap_penalty - unused_ratio * 0.15
    return round(min(1.0, max(0.0, score)), 4)


PROMPT_DIVERSITY_STOPWORDS: frozenset[str] = frozenset(
    {
        "about",
        "across",
        "action",
        "additional",
        "assigned",
        "because",
        "beat",
        "business",
        "character",
        "clip",
        "compare",
        "concepts",
        "continuity",
        "continues",
        "deliver",
        "detail",
        "domain",
        "drive",
        "driven",
        "evidence",
        "explain",
        "first",
        "focus",
        "frame",
        "from",
        "grounded",
        "handoff",
        "historical",
        "identity",
        "impact",
        "introduce",
        "location",
        "maintain",
        "mechanism",
        "motivated",
        "narrative",
        "opens",
        "outcome",
        "pose",
        "power",
        "prediction",
        "previous",
        "primary",
        "process",
        "progression",
        "question",
        "reference",
        "same",
        "scientific",
        "sequence",
        "stable",
        "story",
        "subject",
        "surprising",
        "takeaway",
        "through",
        "topic",
        "using",
        "verdict",
        "video",
        "visible",
        "visual",
        "camera",
        "captions",
        "cards",
        "cinematic",
        "color",
        "continuous",
        "contrast",
        "entering",
        "forbidden",
        "frame",
        "framing",
        "handoff",
        "jump",
        "lighting",
        "logos",
        "materials",
        "micro",
        "motion",
        "negatives",
        "overlays",
        "photoreal",
        "pose",
        "priority",
        "projection",
        "readable",
        "readonly",
        "realistic",
        "response",
        "scene",
        "seed",
        "shorts",
        "silhouette",
        "stable",
        "starter",
        "strict",
        "subtitles",
        "textures",
        "title",
        "unrelated",
        "vertical",
        "watermarks",
    }
)


def _strip_continuity_boilerplate(text: str) -> str:
    core = str(text or "")
    for marker in (
        "Strict negatives:",
        "Opens from approved starter",
        "Continues from previous clip",
        "Maintain same character",
        "Single continuous 10-second",
        "Additional continuity detail:",
    ):
        idx = core.find(marker)
        if idx >= 0:
            core = core[:idx]
    return core


def _diversity_nouns(text: str) -> set[str]:
    core = _strip_continuity_boilerplate(text)
    tokens = set(re.findall(r"\b[a-z]{4,}\b", core.lower()))
    return {token for token in tokens if token not in PROMPT_DIVERSITY_STOPWORDS}


def _concept_in_prompt(concept: str, text: str) -> bool:
    key = _concept_key(concept)
    if not key:
        return False
    lowered = str(text or "").lower()
    if key in lowered:
        return True
    parts = [part for part in key.split() if len(part) > 3]
    return bool(parts) and all(part in lowered for part in parts)


def score_prompt_diversity(
    prompt_texts: list[str],
    *,
    clip_assignments: dict[int, dict[str, list[str]]] | None = None,
    concept_states: dict[str, dict[str, Any]] | None = None,
) -> tuple[float, list[str]]:
    warnings: list[str] = []
    texts = [str(text or "").lower() for text in prompt_texts if str(text or "").strip()]
    if len(texts) < 2:
        return 0.75, warnings

    assigned_sets: list[set[str]] = []
    prompt_concept_sets: list[set[str]] = []
    if clip_assignments:
        for index in range(1, len(texts) + 1):
            bucket = clip_assignments.get(index) or {}
            concepts = list(bucket.get("primary") or []) + list(bucket.get("secondary") or [])
            tokens = {_concept_key(item) for item in concepts if _concept_key(item)}
            assigned_sets.append(tokens)
            prompt_concept_sets.append(
                {token for token in tokens if _concept_in_prompt(token, texts[index - 1])}
            )
    else:
        assigned_sets = [_diversity_nouns(text) for text in texts]
        prompt_concept_sets = assigned_sets

    overlap_scores: list[float] = []
    for left, right in zip(assigned_sets, assigned_sets[1:]):
        if not left or not right:
            overlap_scores.append(0.35)
            continue
        overlap = len(left & right) / len(left | right)
        overlap_scores.append(1.0 - overlap)

    prompt_overlap_scores: list[float] = []
    for left, right in zip(prompt_concept_sets, prompt_concept_sets[1:]):
        if not left or not right:
            prompt_overlap_scores.append(0.45)
            continue
        overlap = len(left & right) / len(left | right)
        prompt_overlap_scores.append(1.0 - overlap)

    if concept_states:
        primary_counts: dict[int, int] = {}
        for state in concept_states.values():
            primary = state.get("primary")
            if isinstance(primary, int):
                primary_counts[primary] = primary_counts.get(primary, 0) + 1
        for clip_index, count in primary_counts.items():
            if count >= len(texts):
                warnings.append(f"concept_primary_in_all_clips:{clip_index}")

    noun_sets = [_diversity_nouns(text) for text in texts]
    entity_overlap: list[float] = []
    for left, right in zip(noun_sets, noun_sets[1:]):
        if not left or not right:
            entity_overlap.append(0.4)
            continue
        entity_overlap.append(1.0 - (len(left & right) / len(left | right)))

    concept_score = sum(overlap_scores) / len(overlap_scores) if overlap_scores else 0.5
    prompt_concept_score = (
        sum(prompt_overlap_scores) / len(prompt_overlap_scores) if prompt_overlap_scores else concept_score
    )
    entity_score = sum(entity_overlap) / len(entity_overlap) if entity_overlap else 0.5

    if clip_assignments:
        score = concept_score * 0.50 + prompt_concept_score * 0.40 + entity_score * 0.10
    else:
        score = concept_score * 0.65 + entity_score * 0.35

    if any(item > MAX_ADJACENT_OVERLAP for item in (1.0 - value for value in overlap_scores)):
        warnings.append("adjacent_clip_concept_overlap_high")
    if score < PROMPT_DIVERSITY_MIN:
        warnings.append(f"prompt_diversity_score<{PROMPT_DIVERSITY_MIN}")

    return round(min(1.0, max(0.0, score)), 4), warnings


def validate_concept_distribution_gates(
    *,
    distribution: ConceptDistributionResult | dict[str, Any],
    prompt_texts: list[str],
    prompt_diversity_score: float,
) -> tuple[bool, list[str]]:
    payload = distribution.to_dict() if hasattr(distribution, "to_dict") else dict(distribution or {})
    failures: list[str] = []
    assignments_raw = dict(payload.get("clip_assignments") or {})
    assignments: dict[int, dict[str, list[str]]] = {}
    for key, value in assignments_raw.items():
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        assignments[index] = {
            "primary": list((value or {}).get("primary") or []),
            "secondary": list((value or {}).get("secondary") or []),
        }
    concept_states = dict(payload.get("concept_states") or {})
    clip_count = max(len(prompt_texts), len(assignments), 1)

    primary_sets = [
        {_concept_key(item) for item in (assignments.get(index, {}).get("primary") or [])}
        for index in range(1, clip_count + 1)
    ]
    if len(primary_sets) >= 2 and primary_sets[0]:
        universal = set.intersection(*primary_sets)
        if universal:
            failures.append("same_primary_concept_in_all_clips")

    for left, right in zip(primary_sets, primary_sets[1:]):
        if not left or not right:
            continue
        overlap = len(left & right) / len(left | right)
        if overlap > MAX_ADJACENT_OVERLAP:
            failures.append(f"adjacent_clip_overlap>{MAX_ADJACENT_OVERLAP}:{overlap:.2f}")

    if float(prompt_diversity_score) < PROMPT_DIVERSITY_MIN:
        failures.append(f"prompt_diversity_score<{PROMPT_DIVERSITY_MIN}:{prompt_diversity_score:.4f}")

    return not failures, failures


def should_use_openai_distribution(
    *,
    concept_count: int,
    domain_count: int,
    multi_domain: bool,
    fusion_score: float = 0.0,
) -> bool:
    if concept_count <= 8 and domain_count <= 2 and not multi_domain:
        return False
    if multi_domain and fusion_score >= 0.75:
        return True
    return concept_count > 8 or domain_count > 2


def resolve_concept_distribution(
    topic: str,
    *,
    clip_count: int = 3,
    domain_concepts_by_domain: dict[str, list[str]] | None = None,
    flat_concepts: list[str] | None = None,
    clip_beats: list[str] | None = None,
    content_strategy: str = "",
    strategic_angle: str = "",
    cross_domain_fusion: dict[str, Any] | None = None,
    fusion_score: float = 0.0,
    language_code: str = "en",
) -> ConceptDistributionResult:
    fusion = dict(cross_domain_fusion or {})
    by_domain = dict(domain_concepts_by_domain or fusion.get("domain_concepts_by_domain") or {})
    if not by_domain and flat_concepts:
        by_domain = {"general": list(flat_concepts)}

    local = build_local_concept_distribution(
        topic,
        clip_count=clip_count,
        domain_concepts_by_domain=by_domain,
        flat_concepts=flat_concepts,
        clip_beats=clip_beats,
        content_strategy=content_strategy,
        strategic_angle=strategic_angle or str(fusion.get("strategic_angle") or ""),
    )
    concept_count = sum(len(items) for items in by_domain.values())
    domain_count = len(by_domain)
    multi_domain = bool(fusion.get("multi_domain")) or domain_count >= 2

    if not should_use_openai_distribution(
        concept_count=concept_count,
        domain_count=domain_count,
        multi_domain=multi_domain,
        fusion_score=float(fusion_score or fusion.get("cross_domain_fusion_score") or 0.0),
    ):
        return local

    enricher = OpenAIConceptDistributionEnricher(
        dry_run=(
            os.getenv("OPENAI_CONCEPT_DISTRIBUTION_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
            or os.getenv("OPENAI_CROSS_DOMAIN_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
    )
    enriched = enricher.maybe_enrich(
        topic=topic,
        local_distribution=local,
        domain_concepts_by_domain=by_domain,
        clip_count=clip_count,
        clip_beats=list(clip_beats or []),
        content_strategy=content_strategy,
        strategic_angle=strategic_angle or str(fusion.get("strategic_angle") or ""),
        language_code=language_code,
    )
    if enriched:
        return enriched
    return local


@dataclass
class OpenAIConceptDistributionEnricher:
    model: str = DEFAULT_MODEL
    dry_run: bool = False
    cache_dir: str = DEFAULT_CACHE_DIR

    def maybe_enrich(
        self,
        *,
        topic: str,
        local_distribution: ConceptDistributionResult,
        domain_concepts_by_domain: dict[str, list[str]],
        clip_count: int,
        clip_beats: list[str] | None = None,
        content_strategy: str = "",
        strategic_angle: str = "",
        language_code: str = "en",
    ) -> ConceptDistributionResult | None:
        if self.dry_run:
            payload = _build_dry_run_distribution(
                topic,
                local_distribution,
                domain_concepts_by_domain=domain_concepts_by_domain,
                clip_count=clip_count,
            )
            return _parse_distribution_payload(payload, topic, base=local_distribution, clip_count=clip_count)

        cache_key = self._cache_key(topic, clip_count, domain_concepts_by_domain, content_strategy)
        cached = self._read_cache(cache_key)
        if cached is not None:
            parsed = _parse_distribution_payload(cached, topic, base=local_distribution, clip_count=clip_count)
            parsed.cache_hit = True
            parsed.openai_applied = True
            parsed.openai_distribution_used = True
            parsed.source = "openai_concept_distribution_cache"
            return parsed
        return None

    def _cache_key(self, topic: str, clip_count: int, by_domain: dict[str, list[str]], strategy: str) -> str:
        normalized = re.sub(r"\s+", " ", topic.strip().lower())
        digest = hashlib.sha256(
            f"{DISTRIBUTION_LAYER_VERSION}|{strategy}|{clip_count}|{normalized}|{sorted(by_domain.items())}".encode("utf-8")
        ).hexdigest()
        return digest[:24]

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            return dict(payload.get("payload") or payload)
        except (OSError, json.JSONDecodeError):
            return None


def _build_dry_run_distribution(
    topic: str,
    local: ConceptDistributionResult,
    *,
    domain_concepts_by_domain: dict[str, list[str]],
    clip_count: int,
) -> dict[str, Any]:
    lowered = topic.lower()
    if "chemistry" in lowered and "perfume" in lowered and "bestseller" in lowered:
        return {
            "clip_assignments": {
                "1": {"primary": ["raw materials", "molecular analysis", "formulation science"], "secondary": ["accord design"]},
                "2": {"primary": ["chemical prediction", "accord design", "consumer testing"], "secondary": ["longevity"]},
                "3": {"primary": ["market share", "consumer adoption", "brand positioning"], "secondary": ["chemical prediction"]},
            }
        }
    if "ai" in lowered and "perfume" in lowered and ("billion" in lowered or "brand" in lowered):
        return {
            "clip_assignments": {
                "1": {"primary": ["luxury market", "brand positioning", "luxury fragrance brand"], "secondary": ["accord design"]},
                "2": {"primary": ["algorithmic formulation", "accord design", "consumer preference modeling"], "secondary": ["raw materials"]},
                "3": {"primary": ["consumer adoption", "market positioning", "prediction models"], "secondary": ["brand strategy board"]},
            }
        }
    return {
        "clip_assignments": {
            str(index): {
                "primary": list((local.clip_assignments.get(index) or {}).get("primary") or []),
                "secondary": list((local.clip_assignments.get(index) or {}).get("secondary") or []),
            }
            for index in range(1, clip_count + 1)
        }
    }


def _parse_distribution_payload(
    raw: dict[str, Any],
    topic: str,
    *,
    base: ConceptDistributionResult,
    clip_count: int,
) -> ConceptDistributionResult:
    assignments: dict[int, dict[str, list[str]]] = {
        index: {"primary": [], "secondary": []} for index in range(1, clip_count + 1)
    }
    raw_assignments = dict(raw.get("clip_assignments") or {})
    for key, value in raw_assignments.items():
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        if index < 1 or index > clip_count:
            continue
        assignments[index] = {
            "primary": filter_expert_domain_concepts(list((value or {}).get("primary") or []))[:3],
            "secondary": filter_expert_domain_concepts(list((value or {}).get("secondary") or []))[:2],
        }

    concept_states: dict[str, dict[str, Any]] = {}
    for index, bucket in assignments.items():
        for concept in bucket.get("primary") or []:
            key = _concept_key(concept)
            concept_states[key] = {"label": concept, "primary": index, "secondary": [], "unused": False}
        for concept in bucket.get("secondary") or []:
            key = _concept_key(concept)
            existing = concept_states.get(key) or {"label": concept, "primary": None, "secondary": [], "unused": True}
            secondary = list(existing.get("secondary") or [])
            if index not in secondary:
                secondary.append(index)
            existing["secondary"] = secondary
            existing["unused"] = existing.get("primary") is None and not secondary
            concept_states[key] = existing

    clip_roles = {index: _role_for_clip_index(index, clip_count) for index in range(1, clip_count + 1)}
    score = _score_distribution(assignments, concept_states, clip_count)
    return ConceptDistributionResult(
        topic=topic,
        clip_count=clip_count,
        clip_assignments=assignments,
        concept_states=concept_states,
        clip_roles=clip_roles,
        distribution_score=score,
        openai_applied=True,
        openai_distribution_used=True,
        source="openai_concept_distribution_dry_run",
    )


__all__ = [
    "ConceptDistributionResult",
    "OpenAIConceptDistributionEnricher",
    "build_local_concept_distribution",
    "resolve_concept_distribution",
    "score_prompt_diversity",
    "validate_concept_distribution_gates",
    "should_use_openai_distribution",
    "PROMPT_DIVERSITY_MIN",
    "PROMPT_DIVERSITY_TARGET",
]
