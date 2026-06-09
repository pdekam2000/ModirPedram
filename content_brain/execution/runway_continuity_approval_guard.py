"""
Phase RUNWAY-STARTER-TO-VIDEO-E — operator approval gate for continuity semi-automation.

Generate and Download remain blocked until explicit operator approval is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from content_brain.execution.runway_continuity_dry_run import APPROVAL_GATED_CONTROLS
from content_brain.execution.runway_continuity_models import RunwayContinuityApprovalRecord

GATE_VERSION = "runway_starter_to_video_e_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

STATE_NOT_REQUIRED = "not_required"
STATE_REQUIRED = "required"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"

BLOCK_APPROVAL_REQUIRED = "RUNWAY_CONTINUITY_APPROVAL_REQUIRED"
BLOCK_APPROVAL_REJECTED = "RUNWAY_CONTINUITY_APPROVAL_REJECTED"
BLOCK_DANGEROUS_ACTION_UNAPPROVED = "RUNWAY_DANGEROUS_ACTION_UNAPPROVED"

DANGEROUS_CONTROL_LABELS: dict[str, str] = {
    "image_generate_button": "Image Generate (spends credits)",
    "generate_button": "Video Generate (spends credits)",
    "download_mp4_button": "Download MP4",
}


def _now() -> datetime:
    return datetime.now()


def _format_timestamp(value: datetime) -> str:
    return value.strftime(TIMESTAMP_FORMAT)


def is_approval_gated_control(control_key: str | None) -> bool:
    return bool(control_key and control_key in APPROVAL_GATED_CONTROLS)


def default_continuity_approval_block() -> dict[str, Any]:
    return {
        "gate_version": GATE_VERSION,
        "approval_required": False,
        "approval_state": STATE_NOT_REQUIRED,
        "awaiting_control_key": None,
        "awaiting_step_id": None,
        "approved_by": None,
        "approved_at": None,
        "approval_reason": None,
        "dangerous_controls": sorted(APPROVAL_GATED_CONTROLS),
        "continuity_eligible": False,
        "continuity_blocked_reasons": [],
    }


@dataclass
class RunwayContinuityApprovalGate:
    approval_required: bool = False
    approval_state: str = STATE_NOT_REQUIRED
    awaiting_control_key: str | None = None
    awaiting_step_id: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    approval_reason: str | None = None
    continuity_eligible: bool = False
    continuity_blocked_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = default_continuity_approval_block()
        payload.update(
            {
                "approval_required": self.approval_required,
                "approval_state": self.approval_state,
                "awaiting_control_key": self.awaiting_control_key,
                "awaiting_step_id": self.awaiting_step_id,
                "approved_by": self.approved_by,
                "approved_at": self.approved_at,
                "approval_reason": self.approval_reason,
                "continuity_eligible": self.continuity_eligible,
                "continuity_blocked_reasons": list(self.continuity_blocked_reasons),
            }
        )
        return payload


def evaluate_runway_continuity_approval_gate(
    *,
    control_key: str | None,
    step_id: str | None = None,
    approvals: dict[str, RunwayContinuityApprovalRecord] | None = None,
    rejected: bool = False,
) -> RunwayContinuityApprovalGate:
    """Return gate metadata for a continuity step/control."""
    approvals = approvals or {}
    gate = RunwayContinuityApprovalGate()

    if not is_approval_gated_control(control_key):
        gate.approval_state = STATE_NOT_REQUIRED
        gate.continuity_eligible = True
        return gate

    gate.approval_required = True
    gate.awaiting_control_key = control_key
    gate.awaiting_step_id = step_id

    if rejected:
        gate.approval_state = STATE_REJECTED
        gate.continuity_blocked_reasons = [BLOCK_APPROVAL_REJECTED]
        return gate

    record = approvals.get(str(control_key or ""))
    if record and record.step_id == (step_id or record.step_id):
        gate.approval_state = STATE_APPROVED
        gate.approved_by = record.approved_by
        gate.approved_at = record.approved_at
        gate.approval_reason = record.reason or None
        gate.continuity_eligible = True
        return gate

    gate.approval_state = STATE_REQUIRED
    gate.continuity_blocked_reasons = [BLOCK_APPROVAL_REQUIRED]
    return gate


def can_execute_dangerous_action(
    control_key: str | None,
    *,
    step_id: str | None = None,
    approvals: dict[str, RunwayContinuityApprovalRecord] | None = None,
) -> bool:
    if not is_approval_gated_control(control_key):
        return True
    gate = evaluate_runway_continuity_approval_gate(
        control_key=control_key,
        step_id=step_id,
        approvals=approvals,
    )
    return gate.approval_state == STATE_APPROVED


def grant_continuity_approval(
    *,
    control_key: str,
    step_id: str,
    approved_by: str,
    reason: str = "",
    approvals: dict[str, RunwayContinuityApprovalRecord] | None = None,
) -> dict[str, RunwayContinuityApprovalRecord]:
    if not is_approval_gated_control(control_key):
        raise ValueError(f"control is not approval-gated: {control_key}")
    updated = dict(approvals or {})
    updated[control_key] = RunwayContinuityApprovalRecord(
        control_key=control_key,
        step_id=step_id,
        approved_by=approved_by.strip() or "operator",
        approved_at=_format_timestamp(_now()),
        reason=reason.strip(),
    )
    return updated


def dangerous_action_block_reason(control_key: str | None) -> str:
    label = DANGEROUS_CONTROL_LABELS.get(str(control_key or ""), control_key or "unknown")
    return f"{BLOCK_DANGEROUS_ACTION_UNAPPROVED}: {label}"


__all__ = [
    "APPROVAL_GATED_CONTROLS",
    "BLOCK_APPROVAL_REJECTED",
    "BLOCK_APPROVAL_REQUIRED",
    "BLOCK_DANGEROUS_ACTION_UNAPPROVED",
    "DANGEROUS_CONTROL_LABELS",
    "GATE_VERSION",
    "STATE_APPROVED",
    "STATE_NOT_REQUIRED",
    "STATE_REJECTED",
    "STATE_REQUIRED",
    "RunwayContinuityApprovalGate",
    "can_execute_dangerous_action",
    "dangerous_action_block_reason",
    "default_continuity_approval_block",
    "evaluate_runway_continuity_approval_gate",
    "grant_continuity_approval",
    "is_approval_gated_control",
]
