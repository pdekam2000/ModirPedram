"""
Phase 11J-12 — read-only assembly approval gate metadata and real-execution guard.

Computes approval block fields on assembly_generation without invoking FFmpeg.
Never imports subprocess, ffmpeg, or full_video_pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_models import (
    AssemblyPlan,
    SUBTITLE_MODE_BURN_IN,
    VALIDATION_READY,
)

GATE_VERSION = "11j12_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

STATE_NOT_REQUIRED = "not_required"
STATE_REQUIRED = "required"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_EXPIRED = "expired"

BLOCK_REAL_ASSEMBLY_NOT_REQUESTED = "REAL_ASSEMBLY_NOT_REQUESTED"
BLOCK_PLAN_NOT_READY = "ASSEMBLY_PLAN_NOT_READY"
BLOCK_APPROVAL_REQUIRED = "ASSEMBLY_APPROVAL_REQUIRED"
BLOCK_APPROVAL_EXPIRED = "ASSEMBLY_APPROVAL_EXPIRED"
BLOCK_APPROVAL_REJECTED = "ASSEMBLY_APPROVAL_REJECTED"
BLOCK_REAL_EXECUTION_DISABLED = "ASSEMBLY_REAL_EXECUTION_DISABLED"
BLOCK_RUNTIME_EXECUTION_DISABLED = "ASSEMBLY_RUNTIME_EXECUTION_DISABLED"
BLOCK_SESSION_CANCELLED = "ASSEMBLY_CANCELLED"
BLOCK_SESSION_ARCHIVED = "ASSEMBLY_SESSION_ARCHIVED"

DEFAULT_SECONDS_PER_CLIP = 30
DEFAULT_APPROVAL_TTL_HOURS = 4


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _now() -> datetime:
    return datetime.now()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in (TIMESTAMP_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _resolve_effective_approval_state(
    existing: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    state = str(existing.get("approval_state") or STATE_NOT_REQUIRED).lower()
    if state != STATE_APPROVED:
        return state
    expires_at = _parse_timestamp(existing.get("approval_expires_at"))
    if expires_at and (now or _now()) >= expires_at:
        return STATE_EXPIRED
    return state


def _plan_validation_status(plan: AssemblyPlan | None, slot: dict[str, Any]) -> str:
    if isinstance(plan, AssemblyPlan):
        return str(plan.validation_status or "").upper()
    return str(slot.get("validation_status") or "").upper()


def _plan_is_ready(plan: AssemblyPlan | None, slot: dict[str, Any]) -> bool:
    return _plan_validation_status(plan, slot) == VALIDATION_READY


def _real_execution_env_enabled() -> bool:
    return os.getenv("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", "false").strip().lower() == "true"


def _runtime_execution_approved_env() -> bool:
    return os.getenv("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", "false").strip().lower() == "true"


def _session_archived(session: dict[str, Any] | None) -> bool:
    if not session:
        return False
    return bool(_dict(session.get("operations_control")).get("archived"))


def _session_cancel_requested(session: dict[str, Any] | None) -> bool:
    if not session:
        return False
    return bool(_dict(session.get("operations_control")).get("cancel_requested"))


def _estimate_metrics(plan: AssemblyPlan | None, slot: dict[str, Any]) -> tuple[float | None, int | None, int | None]:
    input_summary = _dict(slot.get("input_summary"))
    video_count = int(input_summary.get("video_count") or input_summary.get("video") or 0)
    if isinstance(plan, AssemblyPlan):
        video_count = max(video_count, len(plan.video_inputs))
    runtime_seconds = float(video_count * DEFAULT_SECONDS_PER_CLIP)
    if str(slot.get("subtitle_mode") or "").lower() == SUBTITLE_MODE_BURN_IN:
        runtime_seconds += 15.0
    output_size = int(runtime_seconds * 250_000) if runtime_seconds else None
    disk_usage = int(output_size * 2.5) if output_size else None
    return runtime_seconds or None, output_size, disk_usage


def default_assembly_approval_block() -> dict[str, Any]:
    """Default nested approval object for assembly_generation slot."""
    return {
        "gate_version": GATE_VERSION,
        "approval_required": False,
        "approval_state": STATE_NOT_REQUIRED,
        "approved_by": None,
        "approved_at": None,
        "approval_reason": None,
        "approval_expires_at": None,
        "estimated_runtime_seconds": None,
        "estimated_output_size": None,
        "estimated_disk_usage": None,
        "assembly_eligible": False,
        "assembly_blocked_reasons": [BLOCK_REAL_ASSEMBLY_NOT_REQUESTED],
    }


@dataclass
class AssemblyRunRequestContext:
    dry_run: bool = True
    real_assembly_requested: bool = False
    overwrite: bool = False
    timeout_seconds: int = 120
    triggered_by: str = "operator"


@dataclass
class AssemblyRealExecutionGuardResult:
    allowed: bool
    blocked: bool
    block_codes: list[str] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    approval_required: bool = False
    approval_state: str = STATE_NOT_REQUIRED
    approval_expired: bool = False
    assembly_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blocked": self.blocked,
            "block_codes": list(self.block_codes),
            "block_reasons": list(self.block_reasons),
            "blocked_reasons": list(self.block_codes),
            "approval_required": self.approval_required,
            "approval_state": self.approval_state,
            "approval_expired": self.approval_expired,
            "assembly_eligible": self.assembly_eligible,
        }


def can_run_real_assembly(
    slot: dict[str, Any],
    plan: AssemblyPlan | None,
    request: AssemblyRunRequestContext,
    *,
    session: dict[str, Any] | None = None,
    project_root: str | Path | None = None,
) -> AssemblyRealExecutionGuardResult:
    """
    Structured guard for future real FFmpeg assembly (11J-12 read-only).

    Returns allowed=True only when plan READY, approval approved, env flags on,
    and real assembly explicitly requested. Never invokes FFmpeg.
    """
    _ = project_root
    assembly_slot = dict(_dict(slot))
    approval = _dict(assembly_slot.get("approval"))
    block_codes: list[str] = []

    real_requested = bool(request.real_assembly_requested) or bool(
        assembly_slot.get("real_assembly_requested")
    )
    dry_run_only = bool(request.dry_run) and not real_requested

    approval_state = str(approval.get("approval_state") or STATE_NOT_REQUIRED)
    approval_required = False
    approval_expired = False

    if _session_archived(session):
        block_codes.append(BLOCK_SESSION_ARCHIVED)
    if _session_cancel_requested(session):
        block_codes.append(BLOCK_SESSION_CANCELLED)

    if dry_run_only or not real_requested:
        block_codes.append(BLOCK_REAL_ASSEMBLY_NOT_REQUESTED)
        return AssemblyRealExecutionGuardResult(
            allowed=False,
            blocked=True,
            block_codes=block_codes,
            block_reasons=block_codes,
            approval_required=False,
            approval_state=STATE_NOT_REQUIRED,
            approval_expired=False,
            assembly_eligible=False,
        )

    if not _plan_is_ready(plan, assembly_slot):
        block_codes.append(BLOCK_PLAN_NOT_READY)
        return AssemblyRealExecutionGuardResult(
            allowed=False,
            blocked=True,
            block_codes=block_codes,
            block_reasons=block_codes,
            approval_required=False,
            approval_state=STATE_NOT_REQUIRED,
            approval_expired=False,
            assembly_eligible=False,
        )

    approval_required = True
    effective_state = _resolve_effective_approval_state(approval)
    approval_state = effective_state
    approval_expired = effective_state == STATE_EXPIRED

    if effective_state == STATE_REJECTED:
        block_codes.append(BLOCK_APPROVAL_REJECTED)
    elif effective_state == STATE_EXPIRED:
        block_codes.append(BLOCK_APPROVAL_EXPIRED)
    elif effective_state != STATE_APPROVED:
        block_codes.append(BLOCK_APPROVAL_REQUIRED)
    else:
        if not _real_execution_env_enabled():
            block_codes.append(BLOCK_REAL_EXECUTION_DISABLED)
        if not _runtime_execution_approved_env():
            block_codes.append(BLOCK_RUNTIME_EXECUTION_DISABLED)

    allowed = len(block_codes) == 0
    return AssemblyRealExecutionGuardResult(
        allowed=allowed,
        blocked=not allowed,
        block_codes=block_codes,
        block_reasons=block_codes,
        approval_required=approval_required,
        approval_state=approval_state,
        approval_expired=approval_expired,
        assembly_eligible=allowed,
    )


def evaluate_assembly_approval_gate(
    slot: dict[str, Any],
    plan: AssemblyPlan | None,
    request: AssemblyRunRequestContext,
    *,
    session: dict[str, Any] | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Compute read-only approval metadata for assembly_generation slot.

    Preserves existing approval fields (approved_by, approved_at, etc.) when valid.
    """
    assembly_slot = dict(_dict(slot))
    existing = dict(_dict(assembly_slot.get("approval")))
    base = default_assembly_approval_block()
    base.update(existing)
    base["gate_version"] = GATE_VERSION

    runtime_seconds, output_size, disk_usage = _estimate_metrics(plan, assembly_slot)
    base["estimated_runtime_seconds"] = runtime_seconds
    base["estimated_output_size"] = output_size
    base["estimated_disk_usage"] = disk_usage

    guard = can_run_real_assembly(
        assembly_slot,
        plan,
        request,
        session=session,
        project_root=project_root,
    )

    real_requested = bool(request.real_assembly_requested) or bool(
        assembly_slot.get("real_assembly_requested")
    )
    dry_run_only = bool(request.dry_run) and not real_requested

    if dry_run_only or not real_requested:
        base.update(
            {
                "approval_required": False,
                "approval_state": STATE_NOT_REQUIRED,
                "assembly_eligible": False,
                "assembly_blocked_reasons": [BLOCK_REAL_ASSEMBLY_NOT_REQUESTED],
            }
        )
        base["approved_by"] = existing.get("approved_by")
        base["approved_at"] = existing.get("approved_at")
        base["approval_reason"] = existing.get("approval_reason")
        base["approval_expires_at"] = existing.get("approval_expires_at")
        return base

    if not _plan_is_ready(plan, assembly_slot):
        base.update(
            {
                "approval_required": False,
                "approval_state": STATE_NOT_REQUIRED,
                "assembly_eligible": False,
                "assembly_blocked_reasons": [BLOCK_PLAN_NOT_READY],
            }
        )
        return base

    base["approval_required"] = True
    effective_state = _resolve_effective_approval_state(existing)

    if effective_state == STATE_REJECTED:
        base.update(
            {
                "approval_state": STATE_REJECTED,
                "assembly_eligible": False,
                "assembly_blocked_reasons": [BLOCK_APPROVAL_REJECTED],
            }
        )
        return base

    if effective_state == STATE_EXPIRED:
        base.update(
            {
                "approval_state": STATE_EXPIRED,
                "assembly_eligible": False,
                "assembly_blocked_reasons": [BLOCK_APPROVAL_EXPIRED],
            }
        )
        return base

    if effective_state != STATE_APPROVED:
        base.update(
            {
                "approval_state": STATE_REQUIRED,
                "assembly_eligible": False,
                "assembly_blocked_reasons": [BLOCK_APPROVAL_REQUIRED],
            }
        )
        return base

    base["approval_state"] = STATE_APPROVED
    base["approved_by"] = existing.get("approved_by")
    base["approved_at"] = existing.get("approved_at")
    base["approval_reason"] = existing.get("approval_reason")
    base["approval_expires_at"] = existing.get("approval_expires_at")
    base["assembly_eligible"] = guard.assembly_eligible
    base["assembly_blocked_reasons"] = guard.block_codes if guard.blocked else []
    return base


__all__ = [
    "GATE_VERSION",
    "STATE_NOT_REQUIRED",
    "STATE_REQUIRED",
    "STATE_APPROVED",
    "STATE_REJECTED",
    "STATE_EXPIRED",
    "BLOCK_REAL_ASSEMBLY_NOT_REQUESTED",
    "BLOCK_PLAN_NOT_READY",
    "BLOCK_APPROVAL_REQUIRED",
    "BLOCK_APPROVAL_EXPIRED",
    "BLOCK_APPROVAL_REJECTED",
    "BLOCK_REAL_EXECUTION_DISABLED",
    "BLOCK_RUNTIME_EXECUTION_DISABLED",
    "AssemblyRunRequestContext",
    "AssemblyRealExecutionGuardResult",
    "default_assembly_approval_block",
    "evaluate_assembly_approval_gate",
    "can_run_real_assembly",
]
