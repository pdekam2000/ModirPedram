"""
Phase 11D — provider selection engine (metadata ranking only).

Ranks providers using capability registry, cost estimator, and failover planner.
Does not dispatch providers or mutate runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.providers.provider_capability_registry import (
    ProviderCapabilityRecord,
    ProviderCapabilityRegistry,
    normalize_provider_id,
)
from content_brain.providers.provider_cost_catalog import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_UNKNOWN,
    COST_MODEL_FREE,
    COST_MODEL_UNKNOWN,
    ProviderCostEstimator,
)
from content_brain.providers.provider_failover_policy import (
    FailoverConstraints,
    FailoverPlan,
    MODE_PREFERENCE_ANY,
    MODE_PREFERENCE_API,
    MODE_PREFERENCE_BROWSER,
    ProviderFailoverPlanner,
)

ENGINE_VERSION = "11d_v1"
PLACEHOLDER_BENCHMARK_NOTE = (
    "Internal placeholder benchmark score — not an official provider benchmark."
)

OPTIMIZE_COST = "cost"
OPTIMIZE_QUALITY = "quality"
OPTIMIZE_SPEED = "speed"
OPTIMIZE_RELIABILITY = "reliability"
OPTIMIZE_BALANCED = "balanced"

ALL_OPTIMIZE_MODES: tuple[str, ...] = (
    OPTIMIZE_COST,
    OPTIMIZE_QUALITY,
    OPTIMIZE_SPEED,
    OPTIMIZE_RELIABILITY,
    OPTIMIZE_BALANCED,
)

# Placeholder speed/quality/availability profiles (0.0–1.0), not official benchmarks.
_PROVIDER_PLACEHOLDER_PROFILES: dict[str, dict[str, float]] = {
    "runway": {"speed": 0.72, "quality": 0.86, "availability": 0.78},
    "runway_browser": {"speed": 0.42, "quality": 0.82, "availability": 0.62},
    "hailuo_browser": {"speed": 0.48, "quality": 0.78, "availability": 0.65},
    "hailuo_api": {"speed": 0.68, "quality": 0.80, "availability": 0.70},
    "minimax_api": {"speed": 0.60, "quality": 0.70, "availability": 0.55},
    "luma": {"speed": 0.65, "quality": 0.76, "availability": 0.60},
    "kling": {"speed": 0.63, "quality": 0.77, "availability": 0.58},
    "elevenlabs": {"speed": 0.75, "quality": 0.88, "availability": 0.80},
    "openai_tts": {"speed": 0.82, "quality": 0.74, "availability": 0.85},
    "suno": {"speed": 0.55, "quality": 0.72, "availability": 0.50},
    "generic_image": {"speed": 0.70, "quality": 0.75, "availability": 0.72},
}

_DEFAULT_PLACEHOLDER = {"speed": 0.50, "quality": 0.50, "availability": 0.50}

_WEIGHTS_BY_MODE: dict[str, dict[str, float]] = {
    OPTIMIZE_COST: {
        "capability_support": 0.10,
        "cost_score": 0.45,
        "confidence_score": 0.10,
        "speed_score": 0.05,
        "quality_score": 0.05,
        "availability_score": 0.05,
        "mode_match_score": 0.10,
        "failover_position_score": 0.10,
    },
    OPTIMIZE_QUALITY: {
        "capability_support": 0.10,
        "cost_score": 0.05,
        "confidence_score": 0.10,
        "speed_score": 0.10,
        "quality_score": 0.45,
        "availability_score": 0.05,
        "mode_match_score": 0.05,
        "failover_position_score": 0.10,
    },
    OPTIMIZE_SPEED: {
        "capability_support": 0.10,
        "cost_score": 0.05,
        "confidence_score": 0.10,
        "speed_score": 0.45,
        "quality_score": 0.05,
        "availability_score": 0.10,
        "mode_match_score": 0.05,
        "failover_position_score": 0.10,
    },
    OPTIMIZE_RELIABILITY: {
        "capability_support": 0.10,
        "cost_score": 0.05,
        "confidence_score": 0.15,
        "speed_score": 0.05,
        "quality_score": 0.10,
        "availability_score": 0.30,
        "mode_match_score": 0.05,
        "failover_position_score": 0.20,
    },
    OPTIMIZE_BALANCED: {
        "capability_support": 0.125,
        "cost_score": 0.125,
        "confidence_score": 0.125,
        "speed_score": 0.125,
        "quality_score": 0.125,
        "availability_score": 0.125,
        "mode_match_score": 0.125,
        "failover_position_score": 0.125,
    },
}


def _confidence_to_score(confidence: str | None) -> float:
    mapping = {
        CONFIDENCE_HIGH: 1.0,
        CONFIDENCE_MEDIUM: 0.75,
        CONFIDENCE_LOW: 0.5,
        CONFIDENCE_UNKNOWN: 0.25,
    }
    return mapping.get(str(confidence or "").lower(), 0.25)


def _profile(provider_id: str) -> dict[str, float]:
    return dict(_PROVIDER_PLACEHOLDER_PROFILES.get(normalize_provider_id(provider_id), _DEFAULT_PLACEHOLDER))


@dataclass
class SelectionPreferences:
    preferred_provider: str | None = None
    mode_preference: str = MODE_PREFERENCE_ANY
    max_cost: float | None = None
    allow_unknown_cost: bool = True
    excluded_providers: tuple[str, ...] = ()
    require_async_jobs: bool = False
    require_cost_estimation: bool = False
    optimize_for: str = OPTIMIZE_BALANCED
    estimate_quantity: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SelectionPreferences:
        if not data:
            return cls()
        excluded = data.get("excluded_providers") or []
        if isinstance(excluded, str):
            excluded = [excluded]
        optimize = str(data.get("optimize_for") or OPTIMIZE_BALANCED).lower()
        if optimize not in ALL_OPTIMIZE_MODES:
            optimize = OPTIMIZE_BALANCED
        return cls(
            preferred_provider=(
                normalize_provider_id(str(data["preferred_provider"]))
                if data.get("preferred_provider")
                else None
            ),
            mode_preference=str(data.get("mode_preference") or MODE_PREFERENCE_ANY).lower(),
            max_cost=float(data["max_cost"]) if data.get("max_cost") is not None else None,
            allow_unknown_cost=bool(data.get("allow_unknown_cost", True)),
            excluded_providers=tuple(normalize_provider_id(str(item)) for item in excluded if str(item).strip()),
            require_async_jobs=bool(data.get("require_async_jobs", False)),
            require_cost_estimation=bool(data.get("require_cost_estimation", False)),
            optimize_for=optimize,
            estimate_quantity=float(data.get("estimate_quantity") or 1.0),
        )

    def to_failover_constraints(self) -> FailoverConstraints:
        return FailoverConstraints(
            max_cost=self.max_cost,
            mode_preference=self.mode_preference,
            allow_unknown_cost=self.allow_unknown_cost,
            preferred_provider=self.preferred_provider,
            excluded_providers=self.excluded_providers,
            require_async_jobs=self.require_async_jobs,
            require_cost_estimation=self.require_cost_estimation,
            estimate_quantity=self.estimate_quantity,
        )


@dataclass(frozen=True)
class ScoringBreakdown:
    capability_support: float
    cost_score: float
    confidence_score: float
    speed_score: float
    quality_score: float
    availability_score: float
    mode_match_score: float
    failover_position_score: float
    total_score: float
    optimize_for: str
    weights: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_support": self.capability_support,
            "cost_score": self.cost_score,
            "confidence_score": self.confidence_score,
            "speed_score": self.speed_score,
            "quality_score": self.quality_score,
            "availability_score": self.availability_score,
            "mode_match_score": self.mode_match_score,
            "failover_position_score": self.failover_position_score,
            "total_score": self.total_score,
            "optimize_for": self.optimize_for,
            "weights": dict(self.weights),
            "benchmark_note": PLACEHOLDER_BENCHMARK_NOTE,
        }


@dataclass
class RankedCandidate:
    provider_id: str
    rank: int
    total_score: float
    blocked: bool
    block_reason: str | None
    estimated_cost: float | None
    currency: str | None
    cost_model: str | None
    cost_confidence: str | None
    scoring: ScoringBreakdown | None
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "rank": self.rank,
            "total_score": self.total_score,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "estimated_cost": self.estimated_cost,
            "currency": self.currency,
            "cost_model": self.cost_model,
            "cost_confidence": self.cost_confidence,
            "scoring": self.scoring.to_dict() if self.scoring else None,
            "warning": self.warning,
        }


@dataclass
class SelectionResult:
    capability: str
    selected_provider: str | None
    ranked_candidates: list[RankedCandidate] = field(default_factory=list)
    blocked_candidates: list[RankedCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scoring_breakdown: dict[str, Any] | None = None
    estimated_cost: float | None = None
    failover_plan: dict[str, Any] | None = None
    is_executable_later: bool = False
    optimize_for: str = OPTIMIZE_BALANCED

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": ENGINE_VERSION,
            "capability": self.capability,
            "selected_provider": self.selected_provider,
            "ranked_candidates": [item.to_dict() for item in self.ranked_candidates],
            "blocked_candidates": [item.to_dict() for item in self.blocked_candidates],
            "warnings": list(self.warnings),
            "scoring_breakdown": self.scoring_breakdown,
            "estimated_cost": self.estimated_cost,
            "failover_plan": self.failover_plan,
            "is_executable_later": self.is_executable_later,
            "optimize_for": self.optimize_for,
        }


class ProviderSelectionEngine:
    """Rank and select providers using 11A/11B/11C metadata layers."""

    def __init__(
        self,
        capability_registry: ProviderCapabilityRegistry | None = None,
        cost_estimator: ProviderCostEstimator | None = None,
        failover_planner: ProviderFailoverPlanner | None = None,
        *,
        project_root: str | None = None,
    ):
        root = project_root
        self.capabilities = capability_registry or ProviderCapabilityRegistry.load(root)
        self.estimator = cost_estimator or ProviderCostEstimator.load(root)
        self.failover = failover_planner or ProviderFailoverPlanner.load(root)

    @classmethod
    def load(cls, project_root: str | None = None) -> ProviderSelectionEngine:
        return cls(project_root=project_root)

    def rank_providers(
        self,
        capability: str,
        preferences: SelectionPreferences | dict[str, Any] | None = None,
    ) -> SelectionResult:
        cap = str(capability or "").strip().lower()
        prefs = preferences if isinstance(preferences, SelectionPreferences) else SelectionPreferences.from_dict(preferences)
        weights = dict(_WEIGHTS_BY_MODE.get(prefs.optimize_for, _WEIGHTS_BY_MODE[OPTIMIZE_BALANCED]))

        failover_plan = self.failover.plan_failover(
            cap,
            preferred_provider=prefs.preferred_provider,
            constraints=prefs.to_failover_constraints(),
        )

        failover_positions: dict[str, int] = {}
        max_position = max((step.order for step in failover_plan.chain), default=1)
        for step in failover_plan.chain:
            if not step.blocked:
                failover_positions[step.provider_id] = step.order

        candidate_ids = self._candidate_universe(cap, failover_plan, prefs)
        cost_values: list[float] = []

        for provider_id in candidate_ids:
            cost = self.estimator.estimate(provider_id, cap, prefs.estimate_quantity)
            if (
                not cost.blocked
                and cost.estimated_cost is not None
                and cost.cost_model not in {COST_MODEL_UNKNOWN, None}
            ):
                cost_values.append(float(cost.estimated_cost))

        max_observed_cost = max(cost_values) if cost_values else None

        scored: list[tuple[RankedCandidate, bool]] = []
        for provider_id in candidate_ids:
            candidate = self._evaluate_candidate(
                cap,
                provider_id,
                prefs,
                failover_plan,
                failover_positions,
                max_position,
                weights,
                max_observed_cost=max_observed_cost,
            )
            scored.append((candidate, candidate.blocked))

        active = [item for item, blocked in scored if not blocked]
        blocked = [item for item, blocked in scored if blocked]

        active.sort(key=lambda item: (-item.total_score, item.provider_id))
        blocked.sort(key=lambda item: item.provider_id)

        for index, candidate in enumerate(active, start=1):
            candidate.rank = index

        selected = active[0].provider_id if active else None
        result = SelectionResult(
            capability=cap,
            selected_provider=selected,
            ranked_candidates=active,
            blocked_candidates=blocked,
            warnings=list(failover_plan.warnings),
            scoring_breakdown=active[0].scoring.to_dict() if active and active[0].scoring else None,
            estimated_cost=active[0].estimated_cost if active else None,
            failover_plan=failover_plan.to_dict(),
            is_executable_later=failover_plan.is_executable_later,
            optimize_for=prefs.optimize_for,
        )

        if prefs.preferred_provider and selected != prefs.preferred_provider:
            if any(c.provider_id == prefs.preferred_provider for c in blocked):
                result.warnings.append(
                    f"Preferred provider {prefs.preferred_provider} blocked; selected {selected}."
                )

        if not active:
            result.warnings.append("No eligible providers after ranking.")

        return result

    def select_best(
        self,
        capability: str,
        preferences: SelectionPreferences | dict[str, Any] | None = None,
    ) -> SelectionResult:
        return self.rank_providers(capability, preferences)

    def compare_candidates(
        self,
        capability: str,
        candidates: list[str],
        preferences: SelectionPreferences | dict[str, Any] | None = None,
    ) -> SelectionResult:
        prefs = preferences if isinstance(preferences, SelectionPreferences) else SelectionPreferences.from_dict(preferences)
        base = self.rank_providers(capability, prefs)
        allowed = {normalize_provider_id(item) for item in candidates}

        filtered_active = [item for item in base.ranked_candidates if item.provider_id in allowed]
        filtered_blocked = [item for item in base.blocked_candidates if item.provider_id in allowed]

        for index, candidate in enumerate(filtered_active, start=1):
            candidate.rank = index

        return SelectionResult(
            capability=base.capability,
            selected_provider=filtered_active[0].provider_id if filtered_active else None,
            ranked_candidates=filtered_active,
            blocked_candidates=filtered_blocked,
            warnings=base.warnings,
            scoring_breakdown=filtered_active[0].scoring.to_dict() if filtered_active else None,
            estimated_cost=filtered_active[0].estimated_cost if filtered_active else None,
            failover_plan=base.failover_plan,
            is_executable_later=bool(filtered_active),
            optimize_for=base.optimize_for,
        )

    def explain_selection(self, result: SelectionResult) -> list[str]:
        lines = [
            f"Selection for capability={result.capability} optimize_for={result.optimize_for}",
            f"Selected provider: {result.selected_provider or 'none'}",
            f"Executable later (when wired): {result.is_executable_later}",
            PLACEHOLDER_BENCHMARK_NOTE,
        ]
        if result.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {item}" for item in result.warnings)
        lines.append("Ranked candidates:")
        for candidate in result.ranked_candidates:
            lines.append(
                f"  #{candidate.rank} {candidate.provider_id} score={candidate.total_score:.4f} "
                f"cost={candidate.estimated_cost} {candidate.currency or ''}".strip()
            )
        if result.blocked_candidates:
            lines.append("Blocked candidates:")
            for candidate in result.blocked_candidates:
                lines.append(f"  - {candidate.provider_id}: {candidate.block_reason}")
        if result.failover_plan:
            lines.append(f"Failover policy: {result.failover_plan.get('policy_id', 'n/a')}")
        return lines

    def _candidate_universe(
        self,
        capability: str,
        failover_plan: FailoverPlan,
        prefs: SelectionPreferences,
    ) -> list[str]:
        ordered: list[str] = []
        for step in failover_plan.chain:
            if step.provider_id not in ordered:
                ordered.append(step.provider_id)
        for provider_id in self.capabilities.providers_for_capability(capability):
            if provider_id not in ordered:
                ordered.append(provider_id)
        if prefs.preferred_provider:
            preferred = normalize_provider_id(prefs.preferred_provider)
            if preferred in ordered:
                ordered.remove(preferred)
                ordered.insert(0, preferred)
            else:
                ordered.insert(0, preferred)
        return ordered

    def _evaluate_candidate(
        self,
        capability: str,
        provider_id: str,
        prefs: SelectionPreferences,
        failover_plan: FailoverPlan,
        failover_positions: dict[str, int],
        max_position: int,
        weights: dict[str, float],
        *,
        max_observed_cost: float | None = None,
    ) -> RankedCandidate:
        canonical = normalize_provider_id(provider_id)
        record = self.capabilities.get_provider(canonical)

        blocked = False
        block_reason: str | None = None
        warning: str | None = None

        step = next((item for item in failover_plan.chain if item.provider_id == canonical), None)
        if step and step.blocked:
            blocked = True
            block_reason = step.block_reason or "FAILOVER_PLAN_BLOCKED"
        elif not self.capabilities.supports(canonical, capability):
            blocked = True
            block_reason = "CAPABILITY_UNSUPPORTED"
        elif canonical in prefs.excluded_providers:
            blocked = True
            block_reason = "EXCLUDED_BY_PREFERENCE"
        elif record is None:
            blocked = True
            block_reason = "PROVIDER_NOT_IN_REGISTRY"

        cost = self.estimator.estimate(canonical, capability, prefs.estimate_quantity)
        if cost.blocked and not blocked:
            blocked = True
            block_reason = cost.block_reason or "COST_ESTIMATE_BLOCKED"

        if not blocked and prefs.require_async_jobs and record and not record.supports_async_jobs:
            blocked = True
            block_reason = "ASYNC_JOBS_REQUIRED"
        if not blocked and prefs.require_cost_estimation and record and not record.supports_cost_estimation:
            blocked = True
            block_reason = "COST_ESTIMATION_REQUIRED"

        if not blocked and prefs.mode_preference == MODE_PREFERENCE_API and record and not record.supports_api_mode:
            blocked = True
            block_reason = "MODE_PREFERENCE_API"
        if not blocked and prefs.mode_preference == MODE_PREFERENCE_BROWSER and record and not record.supports_browser_mode:
            blocked = True
            block_reason = "MODE_PREFERENCE_BROWSER"

        if not blocked and cost.cost_model == COST_MODEL_UNKNOWN and not prefs.allow_unknown_cost:
            blocked = True
            block_reason = "COST_UNKNOWN_BLOCKED"
        elif cost.cost_model == COST_MODEL_UNKNOWN:
            warning = f"{canonical}: cost unknown"

        if (
            not blocked
            and prefs.max_cost is not None
            and cost.estimated_cost is not None
            and cost.estimated_cost > prefs.max_cost
        ):
            blocked = True
            block_reason = "MAX_COST_EXCEEDED"
        elif (
            not blocked
            and prefs.max_cost is not None
            and cost.estimated_cost is None
            and not prefs.allow_unknown_cost
        ):
            blocked = True
            block_reason = "MAX_COST_UNKNOWN_BLOCKED"

        capability_support = 1.0 if self.capabilities.supports(canonical, capability) else 0.0
        confidence_score = _confidence_to_score(cost.confidence)
        profile = _profile(canonical)
        speed_score = profile["speed"]
        quality_score = profile["quality"]
        availability_score = profile["availability"]

        if record:
            if record.supports_async_jobs:
                availability_score = min(1.0, availability_score + 0.05)
            if record.supports_cost_estimation:
                availability_score = min(1.0, availability_score + 0.03)

        mode_match_score = self._mode_match_score(record, prefs.mode_preference)
        cost_score = self._cost_score(cost.estimated_cost, cost.cost_model, max_observed_cost)

        if cost.cost_model == COST_MODEL_UNKNOWN and prefs.allow_unknown_cost:
            cost_score = 0.35
            confidence_score = min(confidence_score, 0.35)

        position = failover_positions.get(canonical)
        if position is None:
            failover_position_score = 0.25
        else:
            failover_position_score = 1.0 - ((position - 1) / max(max_position, 1))

        if prefs.preferred_provider and canonical == normalize_provider_id(prefs.preferred_provider):
            failover_position_score = min(1.0, failover_position_score + 0.15)

        dimensions = {
            "capability_support": capability_support,
            "cost_score": cost_score,
            "confidence_score": confidence_score,
            "speed_score": speed_score,
            "quality_score": quality_score,
            "availability_score": availability_score,
            "mode_match_score": mode_match_score,
            "failover_position_score": failover_position_score,
        }

        if blocked:
            total = 0.0
            scoring = None
        else:
            total = round(sum(dimensions[key] * weights[key] for key in dimensions), 6)
            scoring = ScoringBreakdown(
                **dimensions,
                total_score=total,
                optimize_for=prefs.optimize_for,
                weights=weights,
            )

        return RankedCandidate(
            provider_id=canonical,
            rank=0,
            total_score=total,
            blocked=blocked,
            block_reason=block_reason,
            estimated_cost=cost.estimated_cost,
            currency=cost.currency,
            cost_model=cost.cost_model,
            cost_confidence=cost.confidence,
            scoring=scoring,
            warning=warning,
        )

    @staticmethod
    def _mode_match_score(record: ProviderCapabilityRecord | None, mode_preference: str) -> float:
        if mode_preference == MODE_PREFERENCE_ANY:
            return 1.0
        if record is None:
            return 0.0
        if mode_preference == MODE_PREFERENCE_API:
            return 1.0 if record.supports_api_mode else 0.0
        if mode_preference == MODE_PREFERENCE_BROWSER:
            return 1.0 if record.supports_browser_mode else 0.0
        return 0.5

    @staticmethod
    def _cost_score(
        estimated_cost: float | None,
        cost_model: str | None,
        max_observed_cost: float | None,
    ) -> float:
        if cost_model == COST_MODEL_FREE:
            return 1.0
        if estimated_cost is None or cost_model == COST_MODEL_UNKNOWN:
            return 0.35
        if max_observed_cost is None or max_observed_cost <= 0:
            return 0.65
        normalized = 1.0 - min(float(estimated_cost) / max_observed_cost, 1.0)
        return round(max(normalized, 0.05), 4)


__all__ = [
    "ENGINE_VERSION",
    "PLACEHOLDER_BENCHMARK_NOTE",
    "OPTIMIZE_COST",
    "OPTIMIZE_QUALITY",
    "OPTIMIZE_SPEED",
    "OPTIMIZE_RELIABILITY",
    "OPTIMIZE_BALANCED",
    "ALL_OPTIMIZE_MODES",
    "SelectionPreferences",
    "ScoringBreakdown",
    "RankedCandidate",
    "SelectionResult",
    "ProviderSelectionEngine",
]
