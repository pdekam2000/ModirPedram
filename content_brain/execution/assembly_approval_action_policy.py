"""
Phase 11J-14 — eligibility and precondition checks for assembly approval write actions.

Pure policy — never executes FFmpeg or mutates sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from content_brain.execution.assembly_approval_guard import (
    BLOCK_PLAN_NOT_READY,
    BLOCK_REAL_ASSEMBLY_NOT_REQUESTED,
    BLOCK_SESSION_ARCHIVED,
    BLOCK_SESSION_CANCELLED,
    STATE_APPROVED,
    STATE_EXPIRED,
    STATE_NOT_REQUIRED,
    STATE_REJECTED,
    STATE_REQUIRED,
    TIMESTAMP_FORMAT,
)
from content_brain.execution.assembly_models import (
    EXPECTED_OUTPUT,
    AssemblyPlan,
    VALIDATION_READY,
)

ACTION_APPROVE = "approve_assembly"
ACTION_REJECT = "reject_assembly"
ACTION_EXPIRE = "expire_assembly"
ACTION_RESET = "reset_assembly_approval"

CODE_PRECONDITION_FAILED = "ASSEMBLY_APPROVAL_PRECONDITION_FAILED"
CODE_ALREADY_APPROVED = "ALREADY_APPROVED"
CODE_SESSION_ARCHIVED = "ASSEMBLY_SESSION_ARCHIVED"
CODE_ASSEMBLY_SLOT_MISSING = "ASSEMBLY_SLOT_MISSING"
CODE_INVALID_STATE = "ASSEMBLY_APPROVAL_INVALID_STATE"
CODE_DRY_RUN_NOT_COMPLETED = "ASSEMBLY_DRY_RUN_NOT_COMPLETED"
CODE_OUTPUT_MISSING = "ASSEMBLY_OUTPUT_MISSING"
CODE_RUN_ACTIVE = "ASSEMBLY_RUN_ACTIVE"
CODE_VIDEO_MISSING = "ASSEMBLY_VIDEO_MISSING"
CODE_AUDIO_MISSING = "ASSEMBLY_AUDIO_MISSING"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(" UTC", "")
    for fmt in (TIMESTAMP_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _session_archived(session: dict[str, Any]) -> bool:
    return bool(_dict(session.get("operations_control")).get("archived"))


def _session_cancel_requested(session: dict[str, Any]) -> bool:
    runtime = _dict(session.get("execution_runtime"))
    if _dict(runtime.get("operations_control")).get("cancel_requested"):
        return True
    return bool(_dict(session.get("operations_control")).get("cancel_requested"))


def _plan_validation_status(plan: AssemblyPlan | None, slot: dict[str, Any]) -> str:
    if isinstance(plan, AssemblyPlan):
        return str(plan.validation_status or "").upper()
    return str(slot.get("validation_status") or "").upper()


def _plan_is_ready(plan: AssemblyPlan | None, slot: dict[str, Any]) -> bool:
    return _plan_validation_status(plan, slot) == VALIDATION_READY


def _dry_run_completed(assembly_slot: dict[str, Any], runtime: dict[str, Any]) -> bool:
    if (
        str(assembly_slot.get("status") or "").lower() == "completed"
        and bool(assembly_slot.get("dry_run"))
        and len(_list(assembly_slot.get("planned_steps"))) >= 1
    ):
        return True
    operations = _dict(runtime.get("operations"))
    exec_meta = _dict(operations.get("assembly_execution"))
    if (
        str(exec_meta.get("last_status") or "").lower() == "completed"
        and exec_meta.get("real_assembly_executed") is False
    ):
        return True
    return False


def _expected_output_resolvable(plan: AssemblyPlan | None, slot: dict[str, Any]) -> bool:
    if isinstance(plan, AssemblyPlan) and str(plan.expected_output or "").strip():
        return True
    return bool(str(slot.get("expected_output") or EXPECTED_OUTPUT).strip())


def _upstream_artifacts_ready(plan: AssemblyPlan | None, slot: dict[str, Any]) -> tuple[bool, list[str]]:
    if _plan_is_ready(plan, slot):
        return True, []
    reasons: list[str] = []
    input_summary = _dict(slot.get("input_summary"))
    video_count = int(input_summary.get("video_count") or input_summary.get("video") or 0)
    voice_count = int(input_summary.get("voice_count") or input_summary.get("voice") or 0)
    if video_count <= 0:
        reasons.append(CODE_VIDEO_MISSING)
    if voice_count <= 0:
        reasons.append(CODE_AUDIO_MISSING)
    return False, reasons


def _effective_approval_state(assembly_slot: dict[str, Any]) -> str:
    approval = _dict(assembly_slot.get("approval"))
    state = str(approval.get("approval_state") or STATE_NOT_REQUIRED).lower()
    if state != STATE_APPROVED:
        return state
    expires_at = _parse_timestamp(approval.get("approval_expires_at"))
    if expires_at and datetime.utcnow() >= expires_at:
        return STATE_EXPIRED
    return state


@dataclass
class AssemblyApprovalPolicyResult:
    allowed: bool
    action: str
    reject_reasons: list[str] = field(default_factory=list)
    code: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "action": self.action,
            "reject_reasons": list(self.reject_reasons),
            "message": self.message,
        }
        if self.code:
            payload["code"] = self.code
        return payload


def _blocked(
    action: str,
    reasons: list[str],
    *,
    code: str = CODE_PRECONDITION_FAILED,
    message: str = "",
) -> AssemblyApprovalPolicyResult:
    return AssemblyApprovalPolicyResult(
        allowed=False,
        action=action,
        reject_reasons=reasons,
        code=code,
        message=message or (reasons[0] if reasons else "Assembly approval action blocked."),
    )


def _allowed(action: str, message: str = "") -> AssemblyApprovalPolicyResult:
    return AssemblyApprovalPolicyResult(allowed=True, action=action, message=message or "Allowed.")


def evaluate_assembly_approval_action(
    session: dict[str, Any],
    assembly_slot: dict[str, Any] | None,
    plan: AssemblyPlan | None,
    action: str,
    *,
    request_real_assembly: bool = False,
    runtime: dict[str, Any] | None = None,
) -> AssemblyApprovalPolicyResult:
    """Return whether an assembly approval write action is permitted."""
    runtime_dict = _dict(runtime or session.get("execution_runtime"))

    if _session_archived(session):
        return _blocked(
            action,
            [CODE_SESSION_ARCHIVED],
            code=CODE_SESSION_ARCHIVED,
            message="Session is archived.",
        )

    if assembly_slot is None:
        return _blocked(
            action,
            [CODE_ASSEMBLY_SLOT_MISSING],
            code=CODE_ASSEMBLY_SLOT_MISSING,
            message="Assembly generation slot is missing.",
        )

    slot = dict(_dict(assembly_slot))

    if str(slot.get("status") or "").lower() == "running":
        return _blocked(
            action,
            [CODE_RUN_ACTIVE],
            code=CODE_RUN_ACTIVE,
            message="Assembly run is active.",
        )

    if action == ACTION_RESET:
        return _allowed(action, "Reset assembly approval metadata.")

    if _session_cancel_requested(session) and action == ACTION_APPROVE:
        return _blocked(
            action,
            [BLOCK_SESSION_CANCELLED],
            message="Session cancellation requested.",
        )

    if action == ACTION_APPROVE:
        if not _plan_is_ready(plan, slot):
            return _blocked(
                action,
                [BLOCK_PLAN_NOT_READY],
                code=BLOCK_PLAN_NOT_READY,
                message="Assembly plan is not READY.",
            )
        if not _dry_run_completed(slot, runtime_dict):
            return _blocked(
                action,
                [CODE_DRY_RUN_NOT_COMPLETED],
                code=CODE_DRY_RUN_NOT_COMPLETED,
                message="Assembly dry-run has not completed successfully.",
            )
        if not _expected_output_resolvable(plan, slot):
            return _blocked(
                action,
                [CODE_OUTPUT_MISSING],
                code=CODE_OUTPUT_MISSING,
                message="Expected assembly output is missing.",
            )
        real_requested = request_real_assembly or bool(slot.get("real_assembly_requested"))
        if not real_requested:
            return _blocked(
                action,
                [BLOCK_REAL_ASSEMBLY_NOT_REQUESTED],
                code=BLOCK_REAL_ASSEMBLY_NOT_REQUESTED,
                message="request_real_assembly must be true to approve real assembly.",
            )
        artifacts_ok, artifact_reasons = _upstream_artifacts_ready(plan, slot)
        if not artifacts_ok:
            return _blocked(
                action,
                artifact_reasons,
                code=artifact_reasons[0] if artifact_reasons else CODE_PRECONDITION_FAILED,
                message="Upstream assembly artifacts are missing.",
            )

        effective = _effective_approval_state(slot)
        if effective == STATE_APPROVED:
            return _blocked(
                action,
                [CODE_ALREADY_APPROVED],
                code=CODE_ALREADY_APPROVED,
                message="Assembly approval is already active and not expired.",
            )
        if effective not in (STATE_REQUIRED, STATE_EXPIRED, STATE_REJECTED, STATE_NOT_REQUIRED):
            return _blocked(
                action,
                [CODE_INVALID_STATE],
                code=CODE_INVALID_STATE,
                message=f"Cannot approve from approval_state={effective}.",
            )
        return _allowed(action, "Approve assembly for future real FFmpeg execution.")

    if action == ACTION_REJECT:
        effective = _effective_approval_state(slot)
        if effective == STATE_NOT_REQUIRED:
            return _blocked(
                action,
                [CODE_INVALID_STATE],
                code=CODE_INVALID_STATE,
                message=f"Cannot reject from approval_state={effective}.",
            )
        return _allowed(action)

    if action == ACTION_EXPIRE:
        effective = _effective_approval_state(slot)
        if effective not in (STATE_APPROVED, STATE_EXPIRED):
            return _blocked(
                action,
                [CODE_INVALID_STATE],
                code=CODE_INVALID_STATE,
                message=f"Cannot expire from approval_state={effective}.",
            )
        return _allowed(action)

    return _blocked(action, ["UNKNOWN_ACTION"], message=f"Unknown action: {action}")


__all__ = [
    "ACTION_APPROVE",
    "ACTION_REJECT",
    "ACTION_EXPIRE",
    "ACTION_RESET",
    "CODE_PRECONDITION_FAILED",
    "CODE_ALREADY_APPROVED",
    "CODE_SESSION_ARCHIVED",
    "CODE_ASSEMBLY_SLOT_MISSING",
    "CODE_DRY_RUN_NOT_COMPLETED",
    "AssemblyApprovalPolicyResult",
    "evaluate_assembly_approval_action",
]
