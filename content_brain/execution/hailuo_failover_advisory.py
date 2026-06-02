"""
Phase 11F-e — Hailuo failover readiness advisory (planning metadata only).

Produces advisory metadata for Hailuo session outcomes. Does not execute failover,
re-dispatch, retry, or requeue.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.hailuo_config import HAILUO_BROWSER_ROUTER_KEY
from content_brain.execution.operations_cancel import CANCEL_REJECT_CODE
from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.providers.provider_capability_registry import (
    CAPABILITY_TEXT_TO_VIDEO,
    ProviderCapabilityRegistry,
    normalize_provider_id,
)
from content_brain.providers.provider_cost_catalog import COST_MODEL_UNKNOWN
from content_brain.providers.provider_failover_policy import (
    FailoverConstraints,
    ProviderFailoverPlanner,
)
from content_brain.providers.provider_selection_engine import (
    ProviderSelectionEngine,
    SelectionPreferences,
)

ADVISORY_VERSION = "11f_e_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

HAILUO_PROVIDER_IDS = frozenset({"hailuo", "hailuo_browser", "hailuo_api"})

OUTCOME_FAILED = "FAILED"
OUTCOME_CANCELLED = "CANCELLED"

REASON_OPERATOR_CANCELLED = "operator_cancelled"
REASON_PROVIDER_FAILURE = "provider_failure"
REASON_ARTIFACT_VALIDATION_REJECT = "artifact_validation_reject"
REASON_CAPABILITY_UNSUPPORTED = "capability_unsupported"
REASON_PROVIDER_DISABLED = "provider_disabled"
REASON_TIMEOUT = "provider_timeout"
REASON_DOWNLOAD_FAILED = "download_failed"
REASON_NO_CANDIDATE = "no_eligible_failover_candidate"

CANCEL_FAILURE_CODES = frozenset(
    {
        CANCEL_REJECT_CODE,
        "OPERATOR_CANCELLED",
        "OPERATIONS_CANCELLED",
    }
)

BLOCK_FAILOVER_CODES = frozenset(
    {
        "CAPABILITY_RUNTIME_UNSUPPORTED",
        "PROVIDER_DISABLED",
        "HAILUO_BROWSER_DISABLED",
        "INVALID_PROVIDER",
        "PROVIDER_UNSUPPORTED",
    }
)

DOWNLOAD_FAILURE_CODES = frozenset(
    {
        "ARTIFACT_TOO_SMALL",
        "ARTIFACT_PATH_MISSING",
        "ARTIFACT_NULL_PATH",
        "ARTIFACT_COPY_FAILED",
        "ARTIFACT_MISSING",
        "DOWNLOAD_FAILED",
    }
)

ARTIFACT_REJECT_CODES = frozenset(
    {
        "ARTIFACT_VALIDATION_FAILED",
        "ARTIFACT_COUNT_MISMATCH",
        "ARTIFACT_INVALID_TYPE",
        *DOWNLOAD_FAILURE_CODES,
    }
)


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_hailuo_provider(provider_id: str) -> str:
    normalized = normalize_provider_id(str(provider_id or ""))
    if normalized == "hailuo":
        return HAILUO_BROWSER_ROUTER_KEY
    return normalized


def is_hailuo_provider(provider_id: str | None) -> bool:
    normalized = _normalize_hailuo_provider(str(provider_id or ""))
    return normalized in HAILUO_PROVIDER_IDS or normalized.startswith("hailuo")


def _resolve_capability(execution_runtime: dict[str, Any]) -> str:
    bundle = _dict(execution_runtime.get("prompt_bundle"))
    raw = str(bundle.get("capability") or bundle.get("requested_capability") or "").strip().lower()
    return raw or CAPABILITY_TEXT_TO_VIDEO


def _extract_partial_artifacts(execution_runtime: dict[str, Any]) -> tuple[list[str], int]:
    paths: list[str] = []
    operations = _dict(execution_runtime.get("operations"))
    cancellation = _dict(operations.get("cancellation"))
    for item in cancellation.get("partial_paths") or []:
        text = str(item).strip()
        if text and text not in paths:
            paths.append(text)

    artifacts = (_dict(execution_runtime.get("artifacts_by_category")).get(CATEGORY_VIDEO)) or []
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            meta = _dict(artifact.get("metadata"))
            clip_result = _dict(meta.get("hailuo_clip_result"))
            if clip_result.get("partial") is True:
                file_path = str(artifact.get("file_path") or clip_result.get("file_path") or "").strip()
                if file_path and file_path not in paths:
                    paths.append(file_path)

    provider_results = execution_runtime.get("provider_clip_results")
    if isinstance(provider_results, list):
        for item in provider_results:
            if isinstance(item, dict) and item.get("partial") is True:
                file_path = str(item.get("file_path") or "").strip()
                if file_path and file_path not in paths:
                    paths.append(file_path)

    clip_results = cancellation.get("clip_results")
    if isinstance(clip_results, list):
        for item in clip_results:
            if isinstance(item, dict) and item.get("partial") is True:
                file_path = str(item.get("file_path") or "").strip()
                if file_path and file_path not in paths:
                    paths.append(file_path)

    return paths, len(paths)


def _next_chain_candidate(plan, current_provider: str) -> tuple[str | None, str | None]:
    current = _normalize_hailuo_provider(current_provider)
    seen_current = False
    for step in plan.chain:
        step_id = _normalize_hailuo_provider(step.provider_id)
        if step_id == current or step.provider_id == current:
            seen_current = True
            continue
        if seen_current and not step.blocked:
            return step.provider_id, None
    for step in plan.chain:
        step_id = _normalize_hailuo_provider(step.provider_id)
        if step_id != current and step.provider_id != current and not step.blocked:
            return step.provider_id, None
    blocked = [
        step
        for step in plan.chain
        if step.blocked and _normalize_hailuo_provider(step.provider_id) != current
    ]
    if blocked:
        return None, blocked[0].block_reason or REASON_NO_CANDIDATE
    return None, REASON_NO_CANDIDATE


def _classify_reason(failure_code: str | None, outcome: str) -> str:
    code = str(failure_code or "").upper()
    if outcome == OUTCOME_CANCELLED or code in CANCEL_FAILURE_CODES:
        return REASON_OPERATOR_CANCELLED
    if code == "CAPABILITY_RUNTIME_UNSUPPORTED":
        return REASON_CAPABILITY_UNSUPPORTED
    if code in {"PROVIDER_DISABLED", "HAILUO_BROWSER_DISABLED"}:
        return REASON_PROVIDER_DISABLED
    if code == "PROVIDER_TIMEOUT":
        return REASON_TIMEOUT
    if code in DOWNLOAD_FAILURE_CODES:
        return REASON_DOWNLOAD_FAILED
    if code in ARTIFACT_REJECT_CODES:
        return REASON_ARTIFACT_VALIDATION_REJECT
    return REASON_PROVIDER_FAILURE


def build_hailuo_failover_advisory(
    *,
    session: dict[str, Any],
    execution_runtime: dict[str, Any],
    outcome: str,
    failure_code: str | None = None,
    failure_message: str | None = None,
    project_root: str | Path | None = None,
    planner: ProviderFailoverPlanner | None = None,
    selection_engine: ProviderSelectionEngine | None = None,
    capability_registry: ProviderCapabilityRegistry | None = None,
) -> dict[str, Any] | None:
    runtime = _dict(execution_runtime)
    provider = _normalize_hailuo_provider(
        str(runtime.get("provider_resolved") or session.get("provider") or "")
    )
    if not is_hailuo_provider(provider):
        return None

    capability = _resolve_capability(runtime)
    partial_paths, partial_count = _extract_partial_artifacts(runtime)
    classified_reason = _classify_reason(failure_code, outcome)
    code = str(failure_code or "").upper()

    base: dict[str, Any] = {
        "advisory_version": ADVISORY_VERSION,
        "advisory_only": True,
        "evaluated_at": _now(),
        "outcome": outcome,
        "failure_code": failure_code,
        "failure_message": failure_message,
        "current_provider": provider,
        "capability": capability,
        "partial_artifacts_present": partial_count > 0,
        "partial_artifacts_safe_to_reuse": False,
        "partial_artifact_count": partial_count,
        "partial_paths": list(partial_paths),
        "reason": classified_reason,
        "blocked_reason": None,
        "failover_recommended": False,
        "failover_allowed": False,
        "candidate_chain": [],
        "preferred_next_provider": None,
        "cost_warning": None,
        "capability_match": False,
    }

    if outcome == OUTCOME_CANCELLED or code in CANCEL_FAILURE_CODES:
        base.update(
            {
                "reason": REASON_OPERATOR_CANCELLED,
                "blocked_reason": REASON_OPERATOR_CANCELLED,
            }
        )
        return base

    root = project_root
    failover_planner = planner or ProviderFailoverPlanner.load(root)
    selector = selection_engine or ProviderSelectionEngine.load(root)
    capabilities = capability_registry or selector.capabilities

    if code in BLOCK_FAILOVER_CODES or classified_reason in {
        REASON_CAPABILITY_UNSUPPORTED,
        REASON_PROVIDER_DISABLED,
    }:
        base["blocked_reason"] = classified_reason
        if code == "CAPABILITY_RUNTIME_UNSUPPORTED":
            base["capability_match"] = False
        return base

    plan = failover_planner.plan_failover(
        capability,
        preferred_provider=provider,
        constraints=FailoverConstraints(excluded_providers=(provider, "hailuo", "hailuo_browser")),
    )
    selection = selector.rank_providers(
        capability,
        SelectionPreferences(
            preferred_provider=provider,
            excluded_providers=(provider, "hailuo", "hailuo_browser"),
        ),
    )

    candidate_chain = [step.provider_id for step in plan.chain if not step.blocked]
    next_provider, blocked_reason = _next_chain_candidate(plan, provider)
    if next_provider is None and selection.ranked_candidates:
        next_provider = selection.ranked_candidates[0].provider_id

    capability_match = bool(next_provider and capabilities.supports(next_provider, capability))

    warnings = list(plan.warnings) + list(selection.warnings)
    cost_warning = None
    for warning in warnings:
        lowered = warning.lower()
        if "cost unknown" in lowered or "low-confidence cost" in lowered:
            cost_warning = warning
            break
    if cost_warning is None and next_provider:
        estimate = selector.estimator.estimate(next_provider, capability, 1.0)
        if estimate.cost_model == COST_MODEL_UNKNOWN or estimate.estimated_cost is None:
            cost_warning = f"{next_provider}: cost unknown for {capability}"

    failover_recommended = bool(next_provider)
    failover_allowed = failover_recommended and capability_match
    if not capability_match and next_provider:
        base["blocked_reason"] = "CAPABILITY_MISMATCH"
        failover_allowed = False
    elif blocked_reason and not next_provider:
        base["blocked_reason"] = blocked_reason
        failover_recommended = False

    base.update(
        {
            "failover_recommended": failover_recommended,
            "failover_allowed": failover_allowed,
            "candidate_chain": candidate_chain,
            "preferred_next_provider": next_provider,
            "cost_warning": cost_warning,
            "capability_match": capability_match,
            "failover_plan": {
                "policy_id": plan.policy_id,
                "chain": [step.provider_id for step in plan.chain],
                "warnings": list(plan.warnings),
            },
            "provider_selection": {
                "engine_version": selection.to_dict().get("engine_version"),
                "selected_provider": selection.selected_provider,
                "ranked_candidates": [
                    item.provider_id for item in selection.ranked_candidates[:5]
                ],
                "warnings": list(selection.warnings),
            },
        }
    )
    return base


def attach_failover_advisory_to_operations(
    execution_runtime: dict[str, Any],
    advisory: dict[str, Any] | None,
) -> dict[str, Any]:
    runtime = dict(_dict(execution_runtime))
    if not advisory:
        return runtime
    operations = dict(_dict(runtime.get("operations")))
    operations["failover_advisory"] = advisory
    runtime["operations"] = operations
    return runtime


__all__ = [
    "ADVISORY_VERSION",
    "HAILUO_PROVIDER_IDS",
    "OUTCOME_FAILED",
    "OUTCOME_CANCELLED",
    "REASON_OPERATOR_CANCELLED",
    "build_hailuo_failover_advisory",
    "attach_failover_advisory_to_operations",
    "is_hailuo_provider",
]
