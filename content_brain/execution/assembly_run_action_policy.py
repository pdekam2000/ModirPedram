"""
Phase 11J-19 — eligibility policy for POST /sessions/{id}/assembly/run.

Pure policy — never builds plans, runs FFmpeg, writes files, or mutates sessions.
Dry-run remains the default path. Real execution requires explicit confirm, approval,
env flags, completed dry-run, and smoke caps when applicable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_approval_guard import (
    AssemblyRunRequestContext,
    can_run_real_assembly,
)
from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability
from content_brain.execution.assembly_models import AssemblyPlan, EXPECTED_OUTPUT, VALIDATION_READY
from content_brain.execution.assembly_smoke_profile import evaluate_assembly_smoke_caps
from content_brain.execution.operations_cancel import is_cancellation_requested

ACTION_RUN_DRY = "run_assembly_dry_run"
ACTION_RUN_REAL = "run_assembly_real"

CODE_SESSION_ARCHIVED = "ASSEMBLY_SESSION_ARCHIVED"
CODE_SESSION_CANCELLED = "ASSEMBLY_CANCELLED"
CODE_ASSEMBLY_SLOT_MISSING = "ASSEMBLY_SLOT_MISSING"
CODE_ASSEMBLY_RUN_ACTIVE = "ASSEMBLY_RUN_ACTIVE"
CODE_PLAN_INVALID = "ASSEMBLY_PLAN_INVALID"
CODE_REAL_EXECUTION_DISABLED = "ASSEMBLY_REAL_EXECUTION_DISABLED"
CODE_REAL_EXECUTION_NOT_CONFIRMED = "ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED"
CODE_DRY_RUN_NOT_COMPLETED = "ASSEMBLY_DRY_RUN_NOT_COMPLETED"
CODE_OUTPUT_EXISTS = "ASSEMBLY_OUTPUT_EXISTS"
CODE_ALREADY_EXECUTED = "ASSEMBLY_ALREADY_EXECUTED"
CODE_FFMPEG_UNAVAILABLE = "ASSEMBLY_FFMPEG_FAILED"

ACTIVE_STATUSES = frozenset({"running", "in_progress", "started"})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _session_archived(session: dict[str, Any]) -> bool:
    return bool(_dict(session.get("operations_control")).get("archived"))


def _dry_run_completed(assembly_slot: dict[str, Any]) -> bool:
    if bool(assembly_slot.get("dry_run_completed")):
        return True
    status = str(assembly_slot.get("status") or "").lower()
    if status != "completed":
        return False
    if assembly_slot.get("real_assembly_executed"):
        return bool(assembly_slot.get("dry_run_completed"))
    return (
        assembly_slot.get("dry_run") is True
        and len(assembly_slot.get("planned_steps") or []) >= 1
        and not assembly_slot.get("real_assembly_executed")
    )


@dataclass
class AssemblyRunPolicyResult:
    allowed: bool
    action: str = ACTION_RUN_DRY
    code: str | None = None
    message: str = ""
    reject_reasons: list[str] = field(default_factory=list)
    guard_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "action": self.action,
            "reject_reasons": list(self.reject_reasons),
            "message": self.message,
        }
        if self.code:
            payload["code"] = self.code
        if self.guard_result is not None:
            payload["guard_result"] = dict(self.guard_result)
        return payload


def evaluate_assembly_run_request(
    session: dict[str, Any],
    assembly_slot: dict[str, Any],
    plan: AssemblyPlan | None,
    *,
    session_id: str,
    dry_run: bool = True,
    confirm_real_assembly: bool = False,
    overwrite: bool = False,
    timeout_seconds: int = 120,
    triggered_by: str = "operator",
    project_root: str | None = None,
) -> AssemblyRunPolicyResult:
    """Decide whether an assembly dry-run or gated real run may proceed."""
    _ = project_root
    checks: list[dict[str, Any]] = []

    def _block(code: str, message: str, *, action: str = ACTION_RUN_DRY) -> AssemblyRunPolicyResult:
        return AssemblyRunPolicyResult(
            allowed=False,
            action=action,
            code=code,
            message=message,
            reject_reasons=[message],
            guard_result={"checks": checks},
        )

    # 1. Session must exist.
    if not session or not session.get("execution_session_id"):
        checks.append({"check": "session_exists", "passed": False})
        return _block(CODE_ASSEMBLY_SLOT_MISSING, "Session not found or missing identifier.")
    checks.append({"check": "session_exists", "passed": True})

    # 2. Session must not be archived.
    if _session_archived(session):
        checks.append({"check": "session_not_archived", "passed": False})
        return _block(CODE_SESSION_ARCHIVED, "Session is archived.")
    checks.append({"check": "session_not_archived", "passed": True})

    # 3. Session must not be cancelled.
    if is_cancellation_requested(session):
        checks.append({"check": "session_not_cancelled", "passed": False})
        return _block(CODE_SESSION_CANCELLED, "Session has a pending cancellation request.")
    checks.append({"check": "session_not_cancelled", "passed": True})

    # 4. Assembly slot must exist.
    if not assembly_slot:
        checks.append({"check": "assembly_slot_exists", "passed": False})
        return _block(CODE_ASSEMBLY_SLOT_MISSING, "Assembly generation slot is missing.")
    checks.append({"check": "assembly_slot_exists", "passed": True})

    # 5. No active assembly run already in flight.
    status = str(assembly_slot.get("status") or "").lower()
    if status in ACTIVE_STATUSES:
        checks.append({"check": "no_active_run", "passed": False, "status": status})
        return _block(CODE_ASSEMBLY_RUN_ACTIVE, "An assembly run is already in progress.")
    checks.append({"check": "no_active_run", "passed": True, "status": status})

    # 6. AssemblyPlan must be READY.
    plan_status = getattr(plan, "validation_status", None) if plan is not None else None
    if not isinstance(plan, AssemblyPlan) or plan_status != VALIDATION_READY:
        checks.append({"check": "plan_ready", "passed": False, "validation_status": plan_status})
        return _block(
            CODE_PLAN_INVALID,
            f"AssemblyPlan is not READY (validation_status={plan_status}).",
        )
    checks.append({"check": "plan_ready", "passed": True, "validation_status": plan_status})

    # ---- Dry-run path -------------------------------------------------------
    if dry_run is not False:
        checks.append({"check": "dry_run_path", "passed": True})
        return AssemblyRunPolicyResult(
            allowed=True,
            action=ACTION_RUN_DRY,
            guard_result={"checks": checks},
            message="Assembly dry-run permitted.",
        )

    # ---- Real execution path (gated) ----------------------------------------
    checks.append({"check": "real_execution_requested", "passed": True})

    if not confirm_real_assembly:
        checks.append({"check": "confirm_real_assembly", "passed": False})
        return _block(
            CODE_REAL_EXECUTION_NOT_CONFIRMED,
            "Real assembly requires confirm_real_assembly=true.",
            action=ACTION_RUN_REAL,
        )
    checks.append({"check": "confirm_real_assembly", "passed": True})

    if bool(assembly_slot.get("real_assembly_executed")) and not overwrite:
        checks.append({"check": "not_already_executed", "passed": False})
        return _block(
            CODE_ALREADY_EXECUTED,
            "Real assembly already executed for this session.",
            action=ACTION_RUN_REAL,
        )
    checks.append({"check": "not_already_executed", "passed": True})

    if not _dry_run_completed(assembly_slot):
        checks.append({"check": "dry_run_completed", "passed": False})
        return _block(
            CODE_DRY_RUN_NOT_COMPLETED,
            "Assembly dry-run must complete before real execution.",
            action=ACTION_RUN_REAL,
        )
    checks.append({"check": "dry_run_completed", "passed": True})

    smoke = evaluate_assembly_smoke_caps(
        plan,
        triggered_by=triggered_by,
        session_id=session_id,
        timeout_seconds=timeout_seconds,
    )
    if not smoke.allowed:
        checks.append({"check": "smoke_caps", "passed": False})
        return _block(
            smoke.code or "ASSEMBLY_SMOKE_CAP_EXCEEDED",
            smoke.message,
            action=ACTION_RUN_REAL,
        )
    checks.append({"check": "smoke_caps", "passed": True})

    request_ctx = AssemblyRunRequestContext(
        dry_run=False,
        real_assembly_requested=True,
        overwrite=overwrite,
        timeout_seconds=timeout_seconds,
        triggered_by=triggered_by,
    )
    guard = can_run_real_assembly(
        assembly_slot,
        plan,
        request_ctx,
        session=session,
    )
    checks.append({"check": "real_assembly_guard", "passed": guard.allowed, "block_codes": guard.block_codes})
    if not guard.allowed:
        code = guard.block_codes[0] if guard.block_codes else CODE_REAL_EXECUTION_DISABLED
        return AssemblyRunPolicyResult(
            allowed=False,
            action=ACTION_RUN_REAL,
            code=code,
            message=f"Real assembly blocked: {code}.",
            reject_reasons=list(guard.block_reasons or guard.block_codes),
            guard_result={"checks": checks, "guard": guard.to_dict()},
        )

    output_dir = Path(getattr(plan, "output_dir", "") or "")
    output_path = output_dir / EXPECTED_OUTPUT
    if output_path.is_file() and not overwrite:
        checks.append({"check": "output_collision", "passed": False})
        return _block(
            CODE_OUTPUT_EXISTS,
            f"Output already exists: {output_path.name}.",
            action=ACTION_RUN_REAL,
        )
    checks.append({"check": "output_collision", "passed": True})

    ffmpeg = check_ffmpeg_availability()
    checks.append({"check": "ffmpeg_available", "passed": ffmpeg.available})
    if not ffmpeg.available:
        return _block(
            CODE_FFMPEG_UNAVAILABLE,
            ffmpeg.error or "FFmpeg is not available.",
            action=ACTION_RUN_REAL,
        )

    return AssemblyRunPolicyResult(
        allowed=True,
        action=ACTION_RUN_REAL,
        guard_result={"checks": checks, "guard": guard.to_dict(), "ffmpeg": ffmpeg.to_dict()},
        message="Real assembly permitted.",
    )


__all__ = [
    "ACTION_RUN_DRY",
    "ACTION_RUN_REAL",
    "CODE_SESSION_ARCHIVED",
    "CODE_SESSION_CANCELLED",
    "CODE_ASSEMBLY_SLOT_MISSING",
    "CODE_ASSEMBLY_RUN_ACTIVE",
    "CODE_PLAN_INVALID",
    "CODE_REAL_EXECUTION_DISABLED",
    "CODE_REAL_EXECUTION_NOT_CONFIRMED",
    "CODE_DRY_RUN_NOT_COMPLETED",
    "CODE_OUTPUT_EXISTS",
    "CODE_ALREADY_EXECUTED",
    "AssemblyRunPolicyResult",
    "evaluate_assembly_run_request",
]
