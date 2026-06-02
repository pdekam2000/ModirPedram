"""
Phase 10J-a — provider cost telemetry helpers (storage only, no pricing math).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.execution.provider_mode_catalog import ModeResolution

TELEMETRY_VERSION = "10j_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_FAILED = "FAILED"
OUTCOME_PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
OUTCOME_CANCELLED = "CANCELLED"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), TIMESTAMP_FORMAT)
    except ValueError:
        return None


def snapshot_estimates(session: dict[str, Any]) -> dict[str, Any]:
    """
    Copy optional estimates from session fields — no calculation.
    Returns estimated_credits, estimated_cost, estimate_source (any may be null).
    """
    simulation = _dict(session.get("simulation_report"))
    approval = _dict(session.get("approval_request"))
    budget = _dict(session.get("budget_decision"))

    estimated_credits = None
    estimate_source = None

    for source_name, container, keys in (
        ("simulation_report", simulation, ("estimated_credits", "estimated_total_credits")),
        ("approval_request", approval, ("estimated_credits",)),
        ("budget_decision", budget, ("estimated_credits",)),
    ):
        for key in keys:
            value = container.get(key)
            if value is not None and value != "":
                try:
                    estimated_credits = float(value)
                    estimate_source = f"{source_name}.{key}"
                    break
                except (TypeError, ValueError):
                    continue
        if estimated_credits is not None:
            break

    estimated_cost = None
    for source_name, container, keys in (
        ("simulation_report", simulation, ("estimated_provider_cost", "estimated_cost")),
        ("budget_decision", budget, ("estimated_cost",)),
    ):
        for key in keys:
            value = container.get(key)
            if value is not None and value != "":
                try:
                    estimated_cost = float(value)
                    if estimate_source is None:
                        estimate_source = f"{source_name}.{key}"
                    break
                except (TypeError, ValueError):
                    continue
        if estimated_cost is not None:
            break

    return {
        "estimated_credits": estimated_credits,
        "estimated_cost": estimated_cost,
        "estimate_source": estimate_source,
    }


def init_cost_telemetry(
    *,
    session: dict[str, Any],
    resolution: ModeResolution,
    dispatch_id: str,
    start_time: str | None = None,
    clip_count: int | None = None,
) -> dict[str, Any]:
    """Initialize cost_telemetry block at dispatch accept / worker start."""
    estimates = snapshot_estimates(session)
    if clip_count is None:
        brief = _dict(session.get("brief_snapshot"))
        format_plan = _dict(brief.get("video_format_plan"))
        simulation = _dict(session.get("simulation_report"))
        try:
            clip_count = int(format_plan.get("clip_count") or simulation.get("estimated_clip_count") or 0) or None
        except (TypeError, ValueError):
            clip_count = None

    return {
        "telemetry_version": TELEMETRY_VERSION,
        "provider_name": resolution.provider_family,
        "provider_execution_mode": resolution.provider_execution_mode,
        "learning_key": resolution.learning_key,
        "router_key": resolution.router_key,
        "provider_category": resolution.provider_category or CATEGORY_VIDEO,
        "dispatch_id": dispatch_id,
        "start_time": start_time or _now(),
        "end_time": None,
        "duration_seconds": None,
        "estimated_cost": estimates.get("estimated_cost"),
        "estimated_credits": estimates.get("estimated_credits"),
        "estimate_source": estimates.get("estimate_source"),
        "cost_basis": resolution.cost_basis,
        "clip_count": clip_count,
        "outcome": None,
        "snapshotted_at": _now(),
    }


def finalize_cost_telemetry(
    telemetry: dict[str, Any],
    *,
    outcome: str,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Set terminal fields on an existing cost_telemetry block."""
    result = dict(telemetry or {})
    terminal_end = end_time or _now()
    result["end_time"] = terminal_end
    result["outcome"] = str(outcome).upper()

    start = _parse_timestamp(str(result.get("start_time") or ""))
    end = _parse_timestamp(terminal_end)
    if start and end:
        result["duration_seconds"] = max(0, int((end - start).total_seconds()))
    else:
        result["duration_seconds"] = None

    return result


__all__ = [
    "TELEMETRY_VERSION",
    "OUTCOME_COMPLETED",
    "OUTCOME_FAILED",
    "OUTCOME_PREFLIGHT_FAILED",
    "OUTCOME_CANCELLED",
    "snapshot_estimates",
    "init_cost_telemetry",
    "finalize_cost_telemetry",
]
