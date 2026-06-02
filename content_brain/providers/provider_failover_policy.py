"""
Phase 11C — provider failover policy and pre-dispatch failover planner.

Policy + planning only. Does not dispatch providers or mutate runtime state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from content_brain.providers.provider_capability_registry import (
    CAPABILITY_IMAGE_GENERATION,
    CAPABILITY_IMAGE_TO_VIDEO,
    CAPABILITY_MUSIC_GENERATION,
    CAPABILITY_NARRATION,
    CAPABILITY_TEXT_TO_IMAGE,
    CAPABILITY_TEXT_TO_VIDEO,
    ProviderCapabilityRegistry,
    normalize_provider_id,
)
from content_brain.providers.provider_cost_catalog import (
    CONFIDENCE_LOW,
    CONFIDENCE_UNKNOWN,
    COST_MODEL_UNKNOWN,
    ProviderCostEstimator,
)

POLICY_VERSION = "11c_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

MODE_PREFERENCE_API = "api"
MODE_PREFERENCE_BROWSER = "browser"
MODE_PREFERENCE_ANY = "any"


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _vendor_family(provider_id: str) -> str:
    pid = normalize_provider_id(provider_id)
    if pid.startswith("runway"):
        return "runway"
    if pid.startswith("hailuo"):
        return "hailuo"
    if pid.startswith("minimax"):
        return "minimax"
    if pid in {"elevenlabs", "openai_tts"}:
        return pid.split("_")[0]
    if pid == "generic_image":
        return "generic_image"
    return pid.replace("_api", "").replace("_browser", "")


def _policy(
    policy_id: str,
    capability: str,
    *,
    preferred_provider: str,
    fallback_providers: list[str],
    max_attempts: int = 4,
    allow_browser_fallback: bool = True,
    allow_api_fallback: bool = True,
    allow_cross_vendor_fallback: bool = True,
    preserve_partial_artifacts: bool = True,
    stop_on_cost_unknown: bool = False,
    stop_on_low_confidence_cost: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "capability": capability,
        "preferred_provider": preferred_provider,
        "fallback_providers": fallback_providers,
        "max_attempts": max_attempts,
        "allow_browser_fallback": allow_browser_fallback,
        "allow_api_fallback": allow_api_fallback,
        "allow_cross_vendor_fallback": allow_cross_vendor_fallback,
        "preserve_partial_artifacts": preserve_partial_artifacts,
        "stop_on_cost_unknown": stop_on_cost_unknown,
        "stop_on_low_confidence_cost": stop_on_low_confidence_cost,
        "notes": notes or "Default failover policy — planning only, not executed at runtime.",
    }


_DEFAULT_POLICIES: tuple[dict[str, Any], ...] = (
    _policy(
        "video_text_to_video_default",
        CAPABILITY_TEXT_TO_VIDEO,
        preferred_provider="runway",
        fallback_providers=[
            "runway_browser",
            "hailuo_browser",
            "hailuo_api",
            "minimax_api",
            "luma",
            "kling",
        ],
        max_attempts=4,
        notes="API-first with browser and cross-vendor fallback for text-to-video.",
    ),
    _policy(
        "video_image_to_video_default",
        CAPABILITY_IMAGE_TO_VIDEO,
        preferred_provider="runway",
        fallback_providers=[
            "runway_browser",
            "hailuo_browser",
            "hailuo_api",
            "kling",
        ],
        max_attempts=3,
    ),
    _policy(
        "voice_narration_default",
        CAPABILITY_NARRATION,
        preferred_provider="elevenlabs",
        fallback_providers=["openai_tts"],
        max_attempts=2,
        allow_browser_fallback=False,
        allow_cross_vendor_fallback=True,
    ),
    _policy(
        "music_generation_default",
        CAPABILITY_MUSIC_GENERATION,
        preferred_provider="suno",
        fallback_providers=[],
        max_attempts=1,
        allow_browser_fallback=False,
        stop_on_cost_unknown=False,
    ),
    _policy(
        "image_generation_default",
        CAPABILITY_IMAGE_GENERATION,
        preferred_provider="generic_image",
        fallback_providers=[],
        max_attempts=1,
        allow_browser_fallback=False,
    ),
)


@dataclass(frozen=True)
class FailoverPolicy:
    policy_id: str
    capability: str
    preferred_provider: str
    fallback_providers: tuple[str, ...]
    max_attempts: int
    allow_browser_fallback: bool
    allow_api_fallback: bool
    allow_cross_vendor_fallback: bool
    preserve_partial_artifacts: bool
    stop_on_cost_unknown: bool
    stop_on_low_confidence_cost: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "capability": self.capability,
            "preferred_provider": self.preferred_provider,
            "fallback_providers": list(self.fallback_providers),
            "max_attempts": self.max_attempts,
            "allow_browser_fallback": self.allow_browser_fallback,
            "allow_api_fallback": self.allow_api_fallback,
            "allow_cross_vendor_fallback": self.allow_cross_vendor_fallback,
            "preserve_partial_artifacts": self.preserve_partial_artifacts,
            "stop_on_cost_unknown": self.stop_on_cost_unknown,
            "stop_on_low_confidence_cost": self.stop_on_low_confidence_cost,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailoverPolicy:
        fallbacks = data.get("fallback_providers") or []
        if isinstance(fallbacks, str):
            fallbacks = [fallbacks]
        return cls(
            policy_id=str(data.get("policy_id") or ""),
            capability=str(data.get("capability") or "").strip().lower(),
            preferred_provider=normalize_provider_id(str(data.get("preferred_provider") or "")),
            fallback_providers=tuple(normalize_provider_id(str(item)) for item in fallbacks if str(item).strip()),
            max_attempts=max(1, int(data.get("max_attempts") or 1)),
            allow_browser_fallback=bool(data.get("allow_browser_fallback", True)),
            allow_api_fallback=bool(data.get("allow_api_fallback", True)),
            allow_cross_vendor_fallback=bool(data.get("allow_cross_vendor_fallback", True)),
            preserve_partial_artifacts=bool(data.get("preserve_partial_artifacts", True)),
            stop_on_cost_unknown=bool(data.get("stop_on_cost_unknown", False)),
            stop_on_low_confidence_cost=bool(data.get("stop_on_low_confidence_cost", False)),
            notes=str(data.get("notes") or ""),
        )


@dataclass
class FailoverConstraints:
    max_cost: float | None = None
    mode_preference: str = MODE_PREFERENCE_ANY
    allow_unknown_cost: bool = True
    preferred_provider: str | None = None
    excluded_providers: tuple[str, ...] = ()
    require_async_jobs: bool = False
    require_cost_estimation: bool = False
    estimate_quantity: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FailoverConstraints:
        if not data:
            return cls()
        excluded = data.get("excluded_providers") or []
        if isinstance(excluded, str):
            excluded = [excluded]
        return cls(
            max_cost=float(data["max_cost"]) if data.get("max_cost") is not None else None,
            mode_preference=str(data.get("mode_preference") or MODE_PREFERENCE_ANY).lower(),
            allow_unknown_cost=bool(data.get("allow_unknown_cost", True)),
            preferred_provider=(
                normalize_provider_id(str(data["preferred_provider"]))
                if data.get("preferred_provider")
                else None
            ),
            excluded_providers=tuple(normalize_provider_id(str(item)) for item in excluded if str(item).strip()),
            require_async_jobs=bool(data.get("require_async_jobs", False)),
            require_cost_estimation=bool(data.get("require_cost_estimation", False)),
            estimate_quantity=float(data.get("estimate_quantity") or 1.0),
        )


@dataclass(frozen=True)
class FailoverChainStep:
    provider_id: str
    order: int
    capability_supported: bool
    supports_browser_mode: bool
    supports_api_mode: bool
    estimated_cost: float | None
    currency: str | None
    cost_model: str | None
    cost_confidence: str | None
    blocked: bool
    block_reason: str | None = None
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "order": self.order,
            "capability_supported": self.capability_supported,
            "supports_browser_mode": self.supports_browser_mode,
            "supports_api_mode": self.supports_api_mode,
            "estimated_cost": self.estimated_cost,
            "currency": self.currency,
            "cost_model": self.cost_model,
            "cost_confidence": self.cost_confidence,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "warning": self.warning,
        }


@dataclass
class FailoverPlan:
    capability: str
    preferred_provider: str
    policy_id: str
    chain: list[FailoverChainStep] = field(default_factory=list)
    blocked_providers: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    estimated_costs: list[dict[str, Any]] = field(default_factory=list)
    capability_support: dict[str, bool] = field(default_factory=dict)
    is_executable_later: bool = False
    preserve_partial_artifacts: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "preferred_provider": self.preferred_provider,
            "policy_id": self.policy_id,
            "chain": [step.to_dict() for step in self.chain],
            "blocked_providers": list(self.blocked_providers),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "estimated_costs": list(self.estimated_costs),
            "capability_support": dict(self.capability_support),
            "is_executable_later": self.is_executable_later,
            "preserve_partial_artifacts": self.preserve_partial_artifacts,
        }


class ProviderFailoverPolicyStore:
    """Load and retrieve failover policies by capability."""

    def __init__(self, policies: Iterable[FailoverPolicy]):
        self._by_capability: dict[str, FailoverPolicy] = {}
        self._by_id: dict[str, FailoverPolicy] = {}
        for policy in policies:
            if policy.capability in self._by_capability:
                raise ValueError(f"Duplicate policy for capability: {policy.capability}")
            self._by_capability[policy.capability] = policy
            self._by_id[policy.policy_id] = policy

    @classmethod
    def load(cls, project_root: str | Path | None = None) -> ProviderFailoverPolicyStore:
        policies = [FailoverPolicy.from_dict(item) for item in _DEFAULT_POLICIES]
        if project_root is not None:
            override_path = Path(project_root).resolve() / "config" / "provider_failover_policies.json"
            if override_path.exists():
                payload = json.loads(override_path.read_text(encoding="utf-8"))
                extra = payload.get("policies") or []
                if isinstance(extra, list):
                    by_cap = {p.capability: p for p in policies}
                    for item in extra:
                        if isinstance(item, dict):
                            record = FailoverPolicy.from_dict(item)
                            by_cap[record.capability] = record
                    policies = list(by_cap.values())
        return cls(policies)

    def get_policy(
        self,
        capability: str,
        preferred_provider: str | None = None,
    ) -> FailoverPolicy | None:
        cap = str(capability or "").strip().lower()
        policy = self._by_capability.get(cap)
        if policy is None:
            return None
        if preferred_provider:
            preferred = normalize_provider_id(preferred_provider)
            return FailoverPolicy(
                policy_id=policy.policy_id,
                capability=policy.capability,
                preferred_provider=preferred,
                fallback_providers=policy.fallback_providers,
                max_attempts=policy.max_attempts,
                allow_browser_fallback=policy.allow_browser_fallback,
                allow_api_fallback=policy.allow_api_fallback,
                allow_cross_vendor_fallback=policy.allow_cross_vendor_fallback,
                preserve_partial_artifacts=policy.preserve_partial_artifacts,
                stop_on_cost_unknown=policy.stop_on_cost_unknown,
                stop_on_low_confidence_cost=policy.stop_on_low_confidence_cost,
                notes=policy.notes,
            )
        return policy

    def list_capabilities(self) -> list[str]:
        return sorted(self._by_capability.keys())

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": POLICY_VERSION,
            "policies": [policy.to_dict() for policy in sorted(self._by_id.values(), key=lambda p: p.policy_id)],
        }


class ProviderFailoverPlanner:
    """Plan failover chains using policies, capability registry, and cost estimator."""

    def __init__(
        self,
        policy_store: ProviderFailoverPolicyStore | None = None,
        capability_registry: ProviderCapabilityRegistry | None = None,
        cost_estimator: ProviderCostEstimator | None = None,
        *,
        project_root: str | Path | None = None,
    ):
        root = project_root
        self.policies = policy_store or ProviderFailoverPolicyStore.load(root)
        self.capabilities = capability_registry or ProviderCapabilityRegistry.load(root)
        self.estimator = cost_estimator or ProviderCostEstimator.load(root)

    @classmethod
    def load(cls, project_root: str | Path | None = None) -> ProviderFailoverPlanner:
        return cls(project_root=project_root)

    def get_policy(
        self,
        capability: str,
        preferred_provider: str | None = None,
    ) -> FailoverPolicy | None:
        return self.policies.get_policy(capability, preferred_provider=preferred_provider)

    def providers_for_failover(self, capability: str) -> list[str]:
        return self.capabilities.providers_for_capability(capability)

    def plan_failover(
        self,
        capability: str,
        preferred_provider: str | None = None,
        constraints: FailoverConstraints | dict[str, Any] | None = None,
    ) -> FailoverPlan:
        cap = str(capability or "").strip().lower()
        cons = constraints if isinstance(constraints, FailoverConstraints) else FailoverConstraints.from_dict(constraints)

        policy = self.policies.get_policy(cap, preferred_provider=cons.preferred_provider or preferred_provider)
        if policy is None:
            return FailoverPlan(
                capability=cap,
                preferred_provider=normalize_provider_id(preferred_provider or ""),
                policy_id="",
                reasons=[f"No failover policy registered for capability: {cap}"],
                is_executable_later=False,
            )

        effective_preferred = cons.preferred_provider or preferred_provider or policy.preferred_provider
        effective_preferred = normalize_provider_id(effective_preferred)

        ordered_candidates: list[str] = []
        for candidate in [effective_preferred, *policy.fallback_providers]:
            canonical = normalize_provider_id(candidate)
            if canonical and canonical not in ordered_candidates:
                ordered_candidates.append(canonical)

        preferred_family = _vendor_family(effective_preferred)
        plan = FailoverPlan(
            capability=cap,
            preferred_provider=effective_preferred,
            policy_id=policy.policy_id,
            preserve_partial_artifacts=policy.preserve_partial_artifacts,
        )

        for provider_id in self.capabilities.providers_for_capability(cap):
            plan.capability_support[provider_id] = True

        chain_steps: list[FailoverChainStep] = []
        order = 0

        for candidate in ordered_candidates:
            if len([step for step in chain_steps if not step.blocked]) >= policy.max_attempts:
                plan.reasons.append(f"Max attempts ({policy.max_attempts}) reached; remaining candidates skipped.")
                break

            record = self.capabilities.get_provider(candidate)
            capability_supported = self.capabilities.supports(candidate, cap)
            plan.capability_support[candidate] = capability_supported

            blocked = False
            block_reason: str | None = None
            warning: str | None = None

            if candidate in cons.excluded_providers:
                blocked = True
                block_reason = "EXCLUDED_BY_CONSTRAINT"
            elif not capability_supported:
                blocked = True
                block_reason = "CAPABILITY_UNSUPPORTED"
            elif record is None:
                blocked = True
                block_reason = "PROVIDER_NOT_IN_REGISTRY"
            else:
                if not policy.allow_cross_vendor_fallback and _vendor_family(candidate) != preferred_family:
                    blocked = True
                    block_reason = "CROSS_VENDOR_NOT_ALLOWED"
                elif not policy.allow_browser_fallback and record.supports_browser_mode and not record.supports_api_mode:
                    blocked = True
                    block_reason = "BROWSER_FALLBACK_NOT_ALLOWED"
                elif not policy.allow_api_fallback and record.supports_api_mode and not record.supports_browser_mode:
                    blocked = True
                    block_reason = "API_FALLBACK_NOT_ALLOWED"
                elif cons.mode_preference == MODE_PREFERENCE_BROWSER and not record.supports_browser_mode:
                    blocked = True
                    block_reason = "MODE_PREFERENCE_BROWSER"
                elif cons.mode_preference == MODE_PREFERENCE_API and not record.supports_api_mode:
                    blocked = True
                    block_reason = "MODE_PREFERENCE_API"
                elif cons.require_async_jobs and not record.supports_async_jobs:
                    blocked = True
                    block_reason = "ASYNC_JOBS_REQUIRED"
                elif cons.require_cost_estimation and not record.supports_cost_estimation:
                    blocked = True
                    block_reason = "COST_ESTIMATION_REQUIRED"

            cost_result = self.estimator.estimate(candidate, cap, cons.estimate_quantity)
            estimated_cost = cost_result.estimated_cost
            currency = cost_result.currency
            cost_model = cost_result.cost_model
            cost_confidence = cost_result.confidence

            if cost_result.blocked and not blocked:
                blocked = True
                block_reason = cost_result.block_reason or "COST_ESTIMATE_BLOCKED"

            if not blocked:
                if cost_model == COST_MODEL_UNKNOWN or estimated_cost is None:
                    msg = f"{candidate}: cost unknown for {cap}"
                    if policy.stop_on_cost_unknown and not cons.allow_unknown_cost:
                        blocked = True
                        block_reason = "COST_UNKNOWN_BLOCKED"
                    else:
                        plan.warnings.append(msg)
                        warning = msg
                elif cons.max_cost is not None and estimated_cost is not None and estimated_cost > cons.max_cost:
                    blocked = True
                    block_reason = "MAX_COST_EXCEEDED"
                elif policy.stop_on_low_confidence_cost and cost_confidence in {CONFIDENCE_LOW, CONFIDENCE_UNKNOWN}:
                    if not cons.allow_unknown_cost:
                        blocked = True
                        block_reason = "LOW_CONFIDENCE_COST_BLOCKED"
                    else:
                        plan.warnings.append(f"{candidate}: low-confidence cost estimate ({cost_confidence})")

            order += 1
            step = FailoverChainStep(
                provider_id=candidate,
                order=order,
                capability_supported=capability_supported,
                supports_browser_mode=bool(record.supports_browser_mode) if record else False,
                supports_api_mode=bool(record.supports_api_mode) if record else False,
                estimated_cost=estimated_cost,
                currency=currency,
                cost_model=cost_model,
                cost_confidence=cost_confidence,
                blocked=blocked,
                block_reason=block_reason,
                warning=warning,
            )
            chain_steps.append(step)

            if blocked:
                plan.blocked_providers.append(candidate)
                if block_reason:
                    plan.reasons.append(f"{candidate}: {block_reason}")
            else:
                plan.estimated_costs.append(
                    {
                        "provider_id": candidate,
                        "estimated_cost": estimated_cost,
                        "currency": currency,
                        "cost_model": cost_model,
                        "confidence": cost_confidence,
                    }
                )

        plan.chain = chain_steps
        plan.is_executable_later = any(not step.blocked for step in chain_steps)
        return plan

    def explain_plan(self, plan: FailoverPlan) -> list[str]:
        lines = [
            f"Failover plan for capability={plan.capability} policy={plan.policy_id or 'none'}",
            f"Preferred provider: {plan.preferred_provider}",
            f"Preserve partial artifacts: {plan.preserve_partial_artifacts}",
            f"Executable later (when wired): {plan.is_executable_later}",
        ]
        if plan.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {item}" for item in plan.warnings)
        if plan.reasons:
            lines.append("Blocked reasons:")
            lines.extend(f"  - {item}" for item in plan.reasons)
        lines.append("Chain:")
        for step in plan.chain:
            status = "BLOCKED" if step.blocked else "OK"
            cost = (
                f"{step.estimated_cost} {step.currency}"
                if step.estimated_cost is not None
                else "unknown"
            )
            lines.append(
                f"  {step.order}. {step.provider_id} [{status}] "
                f"browser={step.supports_browser_mode} api={step.supports_api_mode} cost={cost}"
            )
        return lines


# Convenience alias matching design doc naming
ProviderFailoverPolicy = ProviderFailoverPolicyStore


__all__ = [
    "POLICY_VERSION",
    "MODE_PREFERENCE_API",
    "MODE_PREFERENCE_BROWSER",
    "MODE_PREFERENCE_ANY",
    "FailoverPolicy",
    "FailoverConstraints",
    "FailoverChainStep",
    "FailoverPlan",
    "ProviderFailoverPolicyStore",
    "ProviderFailoverPolicy",
    "ProviderFailoverPlanner",
]
