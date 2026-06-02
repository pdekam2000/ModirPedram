"""
Phase 10K-d — cooperative cancellation helpers (shared by worker + runtime engine).
"""

from __future__ import annotations

from typing import Any

PHASE_CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
PHASE_CANCELLATION_ACKNOWLEDGED = "CANCELLATION_ACKNOWLEDGED"
STATE_CANCELLED = "CANCELLED"
CANCEL_REJECT_CODE = "OPERATOR_CANCELLED"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_cancellation_requested(session: dict[str, Any]) -> bool:
    control = _dict(session.get("operations_control"))
    return bool(control.get("cancel_requested"))


def get_cancel_metadata(session: dict[str, Any]) -> dict[str, Any]:
    control = _dict(session.get("operations_control"))
    return {
        "cancel_reason": control.get("cancel_reason"),
        "cancel_requested_at": control.get("cancel_requested_at"),
        "cancelled_by": control.get("cancelled_by"),
        "cancelled_at": control.get("cancelled_at"),
    }


def clip_counts_from_runtime(execution_runtime: dict[str, Any], clip_target: int | None = None) -> tuple[int, int | None]:
    runtime = _dict(execution_runtime)
    artifacts = (runtime.get("artifacts_by_category") or {}).get("video_generation") or []
    completed = len(artifacts) if isinstance(artifacts, list) else 0
    if clip_target is None:
        bundle = _dict(runtime.get("prompt_bundle"))
        try:
            clip_target = int(bundle.get("clip_count") or 0) or None
        except (TypeError, ValueError):
            clip_target = None
    skipped = None
    if clip_target is not None:
        skipped = max(0, clip_target - completed)
    return completed, skipped
