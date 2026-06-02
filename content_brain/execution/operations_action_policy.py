"""
Phase 10K — pure eligibility rules for operator session actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from content_brain.execution.runtime_job_registry import JobRecord, TERMINAL_PHASES
from content_brain.execution.session_store import ExecutionSessionStore

RUNTIME_ACTIVE_STATES = frozenset({"DISPATCHED", "RUNNING", "EXECUTING"})
TERMINAL_ARCHIVE_STATES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "EXPIRED"})
REQUEUE_SOURCE_STATES = frozenset({"FAILED", "CANCELLED"})
RETRY_SOURCE_STATES = frozenset({"FAILED"})
QUEUE_STATE = "QUEUED"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


@dataclass(frozen=True)
class ActionEligibility:
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason}


def _is_archived(session: dict[str, Any]) -> bool:
    control = _dict(session.get("operations_control"))
    return bool(control.get("archived"))


def _has_active_job(active_job: JobRecord | None) -> bool:
    if active_job is None:
        return False
    return active_job.phase not in TERMINAL_PHASES


def evaluate_eligibility(
    session: dict[str, Any],
    *,
    active_job: JobRecord | None = None,
) -> dict[str, ActionEligibility]:
    state = ExecutionSessionStore.extract_status(session)
    archived = _is_archived(session)
    job_active = _has_active_job(active_job)
    queue_item = _dict(session.get("queue_item"))
    queue_state = _upper(queue_item.get("queue_state"))

    if archived:
        blocked = "Session is archived."
        return {
            "retry": ActionEligibility(False, blocked),
            "cancel": ActionEligibility(False, blocked),
            "archive": ActionEligibility(False, "Session is already archived."),
            "requeue": ActionEligibility(False, blocked),
        }

    if job_active:
        cancel_allowed = state in RUNTIME_ACTIVE_STATES
        return {
            "retry": ActionEligibility(False, "Active runtime job blocks retry."),
            "cancel": ActionEligibility(
                cancel_allowed,
                "Cancel in-flight runtime job."
                if cancel_allowed
                else f"Cancel requires DISPATCHED/RUNNING with active job (current: {state}).",
            ),
            "archive": ActionEligibility(False, "Active runtime job blocks archive."),
            "requeue": ActionEligibility(False, "Active runtime job blocks requeue."),
        }

    retry_allowed = state in RETRY_SOURCE_STATES
    cancel_allowed = False
    archive_allowed = state in TERMINAL_ARCHIVE_STATES
    requeue_allowed = state in REQUEUE_SOURCE_STATES and queue_state != QUEUE_STATE

    return {
        "retry": ActionEligibility(
            retry_allowed,
            "Retry prepares FAILED session for re-dispatch." if retry_allowed else f"Retry allowed only from FAILED (current: {state}).",
        ),
        "cancel": ActionEligibility(
            cancel_allowed,
            "Cancel in-flight runtime job." if cancel_allowed else (
                "Use POST /queue/cancel for QUEUED sessions."
                if queue_state == QUEUE_STATE
                else f"Cancel allowed only for DISPATCHED/RUNNING (current: {state})."
            ),
        ),
        "archive": ActionEligibility(
            archive_allowed,
            "Soft-archive terminal session." if archive_allowed else f"Archive allowed only for COMPLETED/FAILED/CANCELLED (current: {state}).",
        ),
        "requeue": ActionEligibility(
            requeue_allowed,
            "Requeue returns session to execution queue." if requeue_allowed else (
                "Session is already queued."
                if queue_state == QUEUE_STATE
                else f"Requeue allowed only from FAILED/CANCELLED (current: {state})."
            ),
        ),
    }


def eligibility_dict(session: dict[str, Any], *, active_job: JobRecord | None = None) -> dict[str, dict[str, Any]]:
    evaluated = evaluate_eligibility(session, active_job=active_job)
    return {name: item.to_dict() for name, item in evaluated.items()}
