"""
Phase 10K-b — operator session control (retry, cancel, archive, requeue).

Does not call provider runtime dispatch or any provider/browser execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

from content_brain.execution.execution_queue_engine import (
    ELIGIBLE_READINESS,
    ExecutionQueueEngine,
    QueuePolicy,
    QUEUE_QUEUED,
)
from content_brain.execution.execution_readiness_gate import READINESS_READY, READINESS_WARNINGS
from content_brain.execution.operations_action_policy import (
    RUNTIME_ACTIVE_STATES,
    evaluate_eligibility,
)
from content_brain.execution.operations_cancel import (
    PHASE_CANCELLATION_REQUESTED,
    STATE_CANCELLED,
)
from content_brain.execution.runtime_job_registry import RuntimeJobRegistry
from content_brain.execution.session_store import ExecutionSessionStore

ENGINE_VERSION = "10k_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
STATE_DEQUEUED = "DEQUEUED"
MIN_REASON_LENGTH = 3


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _first(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def generate_operations_audit_event_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ops_evt_{stamp}_{uuid.uuid4().hex[:6]}"


@dataclass
class OperationsActionResult:
    ok: bool
    session_id: str
    action: str
    previous_state: str | None = None
    next_state: str | None = None
    audit_event_id: str | None = None
    message: str = ""
    code: str | None = None
    current_state: str | None = None
    reason: str | None = None
    reject_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "session_id": self.session_id,
            "action": self.action,
            "previous_state": self.previous_state,
            "next_state": self.next_state,
            "audit_event_id": self.audit_event_id,
            "message": self.message,
        }
        if not self.ok:
            payload["code"] = self.code
            payload["current_state"] = self.current_state
            payload["reason"] = self.reason or (self.reject_reasons[0] if self.reject_reasons else None)
            if self.reject_reasons:
                payload["reject_reasons"] = self.reject_reasons
        return payload


class OperationsControlEngine:
    """Safe operator actions on execution sessions — state preparation only."""

    def __init__(self, store: ExecutionSessionStore):
        self.store = store
        self.registry = RuntimeJobRegistry(store)
        self.queue = ExecutionQueueEngine(store)

    def eligibility(self, session_id: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        active_job = self.registry.get_active_for_session(session_id)
        current_state = ExecutionSessionStore.extract_status(session)
        actions = evaluate_eligibility(session, active_job=active_job)
        return {
            "session_id": session_id,
            "current_state": current_state,
            "actions": {name: item.to_dict() for name, item in actions.items()},
        }

    def retry(
        self,
        session_id: str,
        *,
        reason: str = "",
        actor: str = "operator",
    ) -> OperationsActionResult:
        return self._run_action(session_id, "retry", reason=reason, actor=actor, require_reason=False)

    def cancel(
        self,
        session_id: str,
        *,
        reason: str = "",
        actor: str = "operator",
    ) -> OperationsActionResult:
        return self._run_action(session_id, "cancel", reason=reason, actor=actor, require_reason=True)

    def archive(
        self,
        session_id: str,
        *,
        reason: str = "",
        actor: str = "operator",
    ) -> OperationsActionResult:
        return self._run_action(session_id, "archive", reason=reason, actor=actor, require_reason=True)

    def requeue(
        self,
        session_id: str,
        *,
        reason: str = "",
        actor: str = "operator",
    ) -> OperationsActionResult:
        return self._run_action(session_id, "requeue", reason=reason, actor=actor, require_reason=True)

    def _run_action(
        self,
        session_id: str,
        action: str,
        *,
        reason: str,
        actor: str,
        require_reason: bool,
    ) -> OperationsActionResult:
        if require_reason and len(str(reason or "").strip()) < MIN_REASON_LENGTH:
            return OperationsActionResult(
                ok=False,
                session_id=session_id,
                action=action,
                code="REASON_REQUIRED",
                current_state=None,
                reason="Reason is required (minimum 3 characters).",
                message="Action blocked.",
            )

        with self.store.file_mutex(f"session_{session_id}"):
            session = self.store.load_session(session_id)
            previous_state = ExecutionSessionStore.extract_status(session)
            active_job = self.registry.get_active_for_session(session_id)
            eligibility = evaluate_eligibility(session, active_job=active_job)
            gate = eligibility.get(action)
            if gate is None or not gate.allowed:
                event_id = self._write_audit(
                    session,
                    action=action,
                    actor=actor,
                    previous_state=previous_state,
                    next_state=previous_state,
                    reason=reason,
                    allowed=False,
                    blocked_reason=gate.reason if gate else "Action not allowed.",
                )
                self.store.save_session(session, overwrite=True)
                return OperationsActionResult(
                    ok=False,
                    session_id=session_id,
                    action=action,
                    code="ACTION_NOT_ALLOWED",
                    current_state=previous_state,
                    reason=gate.reason if gate else "Action not allowed.",
                    reject_reasons=[gate.reason] if gate else ["Action not allowed."],
                    audit_event_id=event_id,
                    message="Action blocked.",
                )

            if action == "requeue":
                return self._apply_requeue(session, reason=reason, actor=actor)

            if action == "retry":
                result = self._apply_retry(session, reason=reason, actor=actor)
            elif action == "cancel":
                result = self._apply_cancel(session, active_job=active_job, reason=reason, actor=actor)
            elif action == "archive":
                result = self._apply_archive(session, reason=reason, actor=actor)
            else:
                return OperationsActionResult(
                    ok=False,
                    session_id=session_id,
                    action=action,
                    code="UNKNOWN_ACTION",
                    current_state=previous_state,
                    reason="Unknown action.",
                    message="Action blocked.",
                )

            self.store.save_session(session, overwrite=True)
            return result

    def _apply_retry(
        self,
        session: dict[str, Any],
        *,
        reason: str,
        actor: str,
    ) -> OperationsActionResult:
        session_id = ExecutionSessionStore.extract_session_id(session)
        previous_state = ExecutionSessionStore.extract_status(session)
        runtime = _dict(session.get("execution_runtime"))
        control = self._ensure_operations_control(session)

        attempt_snapshot = {
            "failed_at": runtime.get("completed_at") or runtime.get("running_at") or _now(),
            "failure": runtime.get("failure"),
            "runtime_state": runtime.get("state"),
            "dispatch_id": runtime.get("dispatch_id"),
            "operations": runtime.get("operations"),
        }
        history = list(control.get("attempt_history") or [])
        history.append(attempt_snapshot)
        control["attempt_history"] = history
        control["retry_count"] = int(control.get("retry_count") or 0) + 1
        control["last_retry_at"] = _now()
        control["last_retry_reason"] = reason or None
        session["operations_control"] = control

        runtime.pop("failure", None)
        runtime["state"] = STATE_DEQUEUED
        runtime["retry_prepared_at"] = _now()
        session["execution_runtime"] = runtime
        session["state"] = STATE_DEQUEUED
        session["updated_at"] = _now()
        self._append_state_history(session, STATE_DEQUEUED, f"operator retry: {reason or 'prepare for re-dispatch'}")

        event_id = self._write_audit(
            session,
            action="retry",
            actor=actor,
            previous_state=previous_state,
            next_state=STATE_DEQUEUED,
            reason=reason,
            allowed=True,
            blocked_reason=None,
            metadata={"retry_count": control["retry_count"]},
        )
        return OperationsActionResult(
            ok=True,
            session_id=session_id,
            action="retry",
            previous_state=previous_state,
            next_state=STATE_DEQUEUED,
            audit_event_id=event_id,
            message="Session prepared for re-dispatch (DEQUEUED). Provider dispatch not started.",
        )

    def _apply_cancel(
        self,
        session: dict[str, Any],
        *,
        active_job: Any,
        reason: str,
        actor: str,
    ) -> OperationsActionResult:
        session_id = ExecutionSessionStore.extract_session_id(session)
        previous_state = ExecutionSessionStore.extract_status(session)
        control = self._ensure_operations_control(session)
        control["cancel_requested"] = True
        control["cancel_requested_at"] = _now()
        control["cancel_reason"] = reason
        control["cancelled_by"] = actor
        session["operations_control"] = control

        runtime = _dict(session.get("execution_runtime"))
        operations = _dict(runtime.get("operations"))
        worker = _dict(operations.get("worker"))
        worker["phase"] = PHASE_CANCELLATION_REQUESTED
        worker["cancel_requested_at"] = _now()
        operations["worker"] = worker
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        session["updated_at"] = _now()

        if active_job is not None:
            self._append_state_history(
                session,
                previous_state,
                f"operator cancel requested: {reason}",
            )
            event_id = self._write_audit(
                session,
                action="cancel",
                actor=actor,
                previous_state=previous_state,
                next_state=previous_state,
                reason=reason,
                allowed=True,
                blocked_reason=None,
                metadata={
                    "dispatch_id": runtime.get("dispatch_id") or active_job.job_id,
                    "cancel_mode": "cooperative_requested",
                    "event_type": "CANCELLATION_REQUESTED",
                },
            )
            self.store.save_session(session, overwrite=True)
            return OperationsActionResult(
                ok=True,
                session_id=session_id,
                action="cancel",
                previous_state=previous_state,
                next_state=previous_state,
                audit_event_id=event_id,
                message="Cancel requested. Worker will acknowledge at next checkpoint.",
            )

        control["cancelled_at"] = _now()
        session["operations_control"] = control
        runtime["state"] = STATE_CANCELLED
        runtime["cancelled_at"] = _now()
        runtime["failure"] = {
            "code": "OPERATOR_CANCELLED",
            "message": reason,
            "category": "OPERATIONS",
        }
        worker["phase"] = STATE_CANCELLED
        operations["worker"] = worker
        telemetry = _dict(operations.get("cost_telemetry"))
        if telemetry:
            telemetry["outcome"] = STATE_CANCELLED
            operations["cost_telemetry"] = telemetry
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        session["state"] = STATE_CANCELLED
        self._append_state_history(session, STATE_CANCELLED, f"operator cancel: {reason}")

        event_id = self._write_audit(
            session,
            action="cancel",
            actor=actor,
            previous_state=previous_state,
            next_state=STATE_CANCELLED,
            reason=reason,
            allowed=True,
            blocked_reason=None,
            metadata={"dispatch_id": runtime.get("dispatch_id"), "cancel_mode": "immediate_no_active_job"},
        )
        return OperationsActionResult(
            ok=True,
            session_id=session_id,
            action="cancel",
            previous_state=previous_state,
            next_state=STATE_CANCELLED,
            audit_event_id=event_id,
            message="Session marked CANCELLED (no active worker job).",
        )

    def _apply_archive(
        self,
        session: dict[str, Any],
        *,
        reason: str,
        actor: str,
    ) -> OperationsActionResult:
        session_id = ExecutionSessionStore.extract_session_id(session)
        previous_state = ExecutionSessionStore.extract_status(session)
        control = self._ensure_operations_control(session)
        control["archived"] = True
        control["archived_at"] = _now()
        control["archived_by"] = actor
        control["archive_reason"] = reason
        session["operations_control"] = control
        session["updated_at"] = _now()
        self._append_state_history(session, previous_state, f"operator archive: {reason}")

        event_id = self._write_audit(
            session,
            action="archive",
            actor=actor,
            previous_state=previous_state,
            next_state=previous_state,
            reason=reason,
            allowed=True,
            blocked_reason=None,
            metadata={"archived": True},
        )
        return OperationsActionResult(
            ok=True,
            session_id=session_id,
            action="archive",
            previous_state=previous_state,
            next_state=previous_state,
            audit_event_id=event_id,
            message="Session archived (soft flag). Data preserved.",
        )

    def _apply_requeue(
        self,
        session: dict[str, Any],
        *,
        reason: str,
        actor: str,
    ) -> OperationsActionResult:
        session_id = ExecutionSessionStore.extract_session_id(session)
        previous_state = ExecutionSessionStore.extract_status(session)
        control = self._ensure_operations_control(session)
        control["requeue_count"] = int(control.get("requeue_count") or 0) + 1
        control["last_requeue_at"] = _now()
        control["last_requeue_reason"] = reason
        session["operations_control"] = control

        self._prepare_session_for_requeue(session)
        self.store.save_session(session, overwrite=True)

        policy = QueuePolicy(require_fingerprint_match=False)
        enqueue_result = self.queue.enqueue_by_id(session_id, actor=actor, policy=policy)
        if not enqueue_result.success:
            code = enqueue_result.reject_code or "REQUEUE_FAILED"
            refreshed = self.store.load_session(session_id)
            event_id = self._write_audit(
                refreshed,
                action="requeue",
                actor=actor,
                previous_state=previous_state,
                next_state=ExecutionSessionStore.extract_status(refreshed),
                reason=reason,
                allowed=False,
                blocked_reason=code,
                metadata={"reject_reasons": enqueue_result.reject_reasons},
            )
            self.store.save_session(refreshed, overwrite=True)
            return OperationsActionResult(
                ok=False,
                session_id=session_id,
                action="requeue",
                code=code,
                current_state=ExecutionSessionStore.extract_status(refreshed),
                reason=enqueue_result.reject_reasons[0] if enqueue_result.reject_reasons else code,
                reject_reasons=enqueue_result.reject_reasons,
                audit_event_id=event_id,
                message="Requeue blocked by queue engine.",
            )

        refreshed = enqueue_result.session or self.store.load_session(session_id)
        next_state = ExecutionSessionStore.extract_status(refreshed)
        event_id = self._write_audit(
            refreshed,
            action="requeue",
            actor=actor,
            previous_state=previous_state,
            next_state=next_state,
            reason=reason,
            allowed=True,
            blocked_reason=None,
            metadata={"requeue_count": control["requeue_count"]},
        )
        self.store.save_session(refreshed, overwrite=True)
        return OperationsActionResult(
            ok=True,
            session_id=session_id,
            action="requeue",
            previous_state=previous_state,
            next_state=next_state,
            audit_event_id=event_id,
            message="Session requeued. Provider dispatch not started.",
        )

    @staticmethod
    def _prepare_session_for_requeue(session: dict[str, Any]) -> None:
        readiness = _dict(session.get("execution_readiness"))
        decision = _first(readiness.get("decision"))
        if decision in ELIGIBLE_READINESS:
            session["state"] = decision
        elif decision:
            session["state"] = READINESS_WARNINGS
        else:
            session["state"] = READINESS_READY
            readiness.setdefault("decision", READINESS_READY)
            session["execution_readiness"] = readiness

        queue_item = _dict(session.get("queue_item"))
        if queue_item and _first(queue_item.get("queue_state")).upper() != QUEUE_QUEUED:
            retry_meta = _dict(queue_item.get("retry"))
            retry_meta["last_terminal_state"] = _first(session.get("state"))
            queue_item["retry"] = retry_meta

    @staticmethod
    def _ensure_operations_control(session: dict[str, Any]) -> dict[str, Any]:
        control = _dict(session.get("operations_control"))
        control.setdefault("schema_version", ENGINE_VERSION)
        control.setdefault("archived", False)
        control.setdefault("retry_count", 0)
        control.setdefault("requeue_count", 0)
        session["operations_control"] = control
        return control

    @staticmethod
    def _append_state_history(session: dict[str, Any], state: str, reason: str) -> None:
        history = list(session.get("state_history") or [])
        history.append({"at": _now(), "state": state, "reason": reason})
        session["state_history"] = history

    def _write_audit(
        self,
        session: dict[str, Any],
        *,
        action: str,
        actor: str,
        previous_state: str,
        next_state: str,
        reason: str,
        allowed: bool,
        blocked_reason: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        event_id = generate_operations_audit_event_id()
        timestamp = _now()
        session_id = ExecutionSessionStore.extract_session_id(session)
        event = {
            "event_id": event_id,
            "timestamp": timestamp,
            "session_id": session_id,
            "action": action,
            "actor": actor,
            "previous_state": previous_state,
            "next_state": next_state,
            "reason": reason or None,
            "allowed": allowed,
            "blocked_reason": blocked_reason,
            "metadata": metadata or {},
        }
        audit_log = list(session.get("operations_audit_log") or [])
        audit_log.append(event)
        session["operations_audit_log"] = audit_log
        self.store.append_global_operations_audit(event)
        return event_id


__all__ = [
    "OperationsControlEngine",
    "OperationsActionResult",
    "generate_operations_audit_event_id",
]
