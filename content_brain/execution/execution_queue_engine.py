"""
Phase 10H — execution queue runtime between readiness and future provider runtime.

No provider execution, no browser automation, no queue fingerprint validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
import uuid

from content_brain.execution.execution_readiness_gate import (
    READINESS_READY,
    READINESS_WARNINGS,
)
from content_brain.execution.session_fingerprint import (
    QUEUE_FINGERPRINT_SOURCES,
    QUEUE_FINGERPRINT_VERSION,
    compute_queue_fingerprint,
    compute_simulation_fingerprint,
)
from content_brain.execution.session_store import ExecutionSessionStore

ENGINE_NAME = "ExecutionQueueEngine"
ENGINE_VERSION = "10h_v1"
POLICY_VERSION = "10h_v1"
INDEX_VERSION = "10h_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

QUEUE_QUEUED = "QUEUED"
QUEUE_DEQUEUED = "DEQUEUED"
QUEUE_CANCELLED = "CANCELLED"
QUEUE_EXPIRED = "EXPIRED"

ELIGIBLE_READINESS = {READINESS_READY, READINESS_WARNINGS}
ELIGIBLE_SESSION_STATES = {READINESS_READY, READINESS_WARNINGS}

BAND_WEIGHTS = {
    "critical": 400,
    "high": 300,
    "medium": 200,
    "low": 100,
}
READINESS_BONUS = {
    READINESS_READY: 5.0,
    READINESS_WARNINGS: 0.0,
}


@dataclass
class QueuePolicy:
    policy_id: str = "default_local"
    policy_version: str = POLICY_VERSION
    eligible_readiness_decisions: tuple[str, ...] = (READINESS_READY, READINESS_WARNINGS)
    default_ttl_seconds: int = 86400
    max_active_queue_depth: int = 100
    max_enqueue_attempts: int = 3
    require_fingerprint_match: bool = True

    def snapshot(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "eligible_readiness_decisions": list(self.eligible_readiness_decisions),
            "default_ttl_seconds": self.default_ttl_seconds,
            "max_active_queue_depth": self.max_active_queue_depth,
            "max_enqueue_attempts": self.max_enqueue_attempts,
            "require_fingerprint_match": self.require_fingerprint_match,
            "priority_band_weights": dict(BAND_WEIGHTS),
        }


@dataclass
class EnqueueResult:
    success: bool
    session: dict[str, Any] | None = None
    queue_item: dict[str, Any] | None = None
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)


@dataclass
class DequeueResult:
    success: bool
    session: dict[str, Any] | None = None
    queue_item: dict[str, Any] | None = None
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        return None


def generate_queue_item_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"queue_{stamp}_{uuid.uuid4().hex[:6]}"


def generate_audit_event_id() -> str:
    return f"qevt_{uuid.uuid4().hex[:12]}"


def _first(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


class ExecutionQueueEngine:
    """File-backed queue between readiness gate and future provider runtime."""

    def __init__(self, store: ExecutionSessionStore):
        self.store = store

    def validate_eligibility(
        self,
        session: dict[str, Any],
        policy: QueuePolicy | None = None,
    ) -> tuple[bool, list[str], str | None]:
        policy = policy or QueuePolicy()

        readiness = _dict(session.get("execution_readiness"))
        readiness_decision = _first(readiness.get("decision"))
        session_state = _first(session.get("state")).upper()
        approval = _dict(session.get("approval_decision"))
        budget = _dict(session.get("budget_decision"))

        if not readiness:
            return False, ["Execution readiness has not been evaluated."], "READINESS_MISSING"

        if readiness_decision not in policy.eligible_readiness_decisions:
            return False, [
                f"Readiness decision is {readiness_decision or 'unknown'}, not eligible for queue."
            ], "READINESS_NOT_READY"

        if session_state not in ELIGIBLE_SESSION_STATES:
            if session_state in {"NOT_READY", "REJECTED"}:
                return False, [f"Session state {session_state} is not eligible."], "READINESS_NOT_READY"
            if session_state == "BUDGET_BLOCKED":
                return False, [f"Session state {session_state} is not eligible."], "BUDGET_BLOCKED"
            if session_state == "AWAITING_APPROVAL":
                return False, ["Session is awaiting approval."], "AWAITING_APPROVAL"
            if session_state == QUEUE_QUEUED:
                return False, ["Session already has an active queued item."], "ALREADY_QUEUED"
            return False, [f"Session state {session_state} is not eligible for enqueue."], "READINESS_NOT_READY"

        approval_status = _first(approval.get("status"))
        if approval_status == "REJECTED" or session_state == "REJECTED":
            return False, ["Approval status is REJECTED."], "GOVERNANCE_REJECTED"
        if approval_status != "APPROVED_FOR_EXECUTION":
            reason = f"Approval status is {approval_status or 'unknown'}."
            if approval_status == "AWAITING_APPROVAL":
                return False, [reason], "AWAITING_APPROVAL"
            return False, [reason], "GOVERNANCE_REJECTED"

        if budget.get("budget_allowed") is not True:
            return False, ["Budget is not allowed for execution."], "BUDGET_BLOCKED"
        budget_status = _first(budget.get("budget_status"), budget.get("budget_state"))
        if budget_status == "BUDGET_BLOCKED":
            return False, ["Budget status is BUDGET_BLOCKED."], "BUDGET_BLOCKED"

        existing = _dict(session.get("queue_item"))
        if existing.get("queue_state") == QUEUE_QUEUED:
            return False, ["Session already has an active QUEUED item."], "ALREADY_QUEUED"

        prior_attempts = int(_dict(existing.get("retry")).get("enqueue_attempts_used") or 0)
        if prior_attempts >= policy.max_enqueue_attempts:
            return False, ["Max enqueue attempts exceeded."], "MAX_ENQUEUE_ATTEMPTS_EXCEEDED"

        if policy.require_fingerprint_match:
            simulation = _dict(session.get("simulation_report"))
            stored_fp = _dict(simulation.get("metadata")).get("simulation_fingerprint")
            if stored_fp and compute_simulation_fingerprint(session) != stored_fp:
                return False, ["Simulation fingerprint mismatch — session changed since simulation."], "STALE_READINESS"

        active_count = len(self._active_index_items())
        if active_count >= policy.max_active_queue_depth:
            return False, [f"Queue depth {active_count} exceeds max {policy.max_active_queue_depth}."], "QUEUE_FULL"

        return True, [], None

    def enqueue(
        self,
        session: dict[str, Any],
        *,
        actor: str = "system",
        policy: QueuePolicy | None = None,
    ) -> EnqueueResult:
        policy = policy or QueuePolicy()
        ok, reasons, code = self.validate_eligibility(session, policy)
        if not ok:
            self._audit_session_event(
                session,
                event_type="ENQUEUE_REJECTED",
                actor=actor,
                details={"reject_code": code, "reject_reasons": reasons},
            )
            self.store.save_session(session, overwrite=True)
            return EnqueueResult(False, session=session, reject_code=code, reject_reasons=reasons)

        timestamp = _now()
        queue_item = self._build_queue_item(session, policy, timestamp)
        session = dict(session)
        session["queue_item"] = queue_item
        session["state"] = QUEUE_QUEUED
        session["updated_at"] = timestamp
        session["session_schema_version"] = "10h_v1"

        priority = _dict(queue_item.get("priority"))
        priority_decision = dict(session.get("priority_decision") or {})
        priority_decision.update(
            {
                "priority_band": priority.get("priority_band"),
                "priority_score": priority.get("priority_score"),
                "queue_position": priority.get("queue_position"),
                "decision_source": "execution_queue_engine",
            }
        )
        session["priority_decision"] = priority_decision
        session["priority_band"] = priority.get("priority_band")

        metadata = _dict(session.get("metadata"))
        metadata["queue_version"] = ENGINE_VERSION
        metadata["queue_enqueued_at"] = timestamp
        session["metadata"] = metadata

        self._append_state_history(session, QUEUE_QUEUED, timestamp, queue_item)
        self._audit_session_event(
            session,
            event_type="ENQUEUED",
            actor=actor,
            queue_item=queue_item,
            details={
                "queue_position": priority.get("queue_position"),
                "effective_priority": priority.get("effective_priority"),
                "readiness_decision": _dict(session.get("execution_readiness")).get("decision"),
            },
        )

        self.store.save_session(session, overwrite=True)
        self.rebuild_index()

        refreshed = self.store.load_session(
            ExecutionSessionStore.extract_session_id(session)
        )
        return EnqueueResult(True, session=refreshed, queue_item=refreshed.get("queue_item"))

    def enqueue_by_id(
        self,
        session_id: str,
        *,
        actor: str = "system",
        policy: QueuePolicy | None = None,
    ) -> EnqueueResult:
        session = self.store.load_session(session_id)
        return self.enqueue(session, actor=actor, policy=policy)

    def cancel(
        self,
        session: dict[str, Any],
        *,
        reason: str = "cancelled",
        actor: str = "system",
    ) -> dict[str, Any]:
        session = dict(session)
        queue_item = _dict(session.get("queue_item"))
        if queue_item.get("queue_state") != QUEUE_QUEUED:
            raise ValueError("No active QUEUED item to cancel.")

        timestamp = _now()
        queue_item["queue_state"] = QUEUE_CANCELLED
        lifecycle = _dict(queue_item.get("lifecycle"))
        lifecycle["cancelled_at"] = timestamp
        lifecycle["cancelled_by"] = actor
        lifecycle["cancel_reason"] = reason
        queue_item["lifecycle"] = lifecycle

        retry = _dict(queue_item.get("retry"))
        retry["last_terminal_state"] = QUEUE_CANCELLED
        queue_item["retry"] = retry
        session["queue_item"] = queue_item

        readiness_decision = _dict(session.get("execution_readiness")).get("decision")
        revert_state = readiness_decision if readiness_decision in ELIGIBLE_SESSION_STATES else QUEUE_CANCELLED
        session["state"] = revert_state
        session["updated_at"] = timestamp

        priority_decision = dict(session.get("priority_decision") or {})
        priority_decision["queue_position"] = None
        session["priority_decision"] = priority_decision

        queue_priority = dict(queue_item.get("priority") or {})
        queue_priority["queue_position"] = None
        queue_item["priority"] = queue_priority
        session["queue_item"] = queue_item

        self._append_state_history(
            session,
            revert_state,
            timestamp,
            queue_item,
            reason=f"queue cancelled: {reason}",
        )
        self._audit_session_event(
            session,
            event_type="CANCELLED",
            actor=actor,
            queue_item=queue_item,
            details={"cancel_reason": reason},
        )

        self.store.save_session(session, overwrite=True)
        self.rebuild_index()
        return self.store.load_session(ExecutionSessionStore.extract_session_id(session))

    def cancel_by_id(
        self,
        session_id: str,
        *,
        reason: str = "cancelled",
        actor: str = "system",
    ) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        return self.cancel(session, reason=reason, actor=actor)

    def expire_stale(self, policy: QueuePolicy | None = None) -> list[str]:
        policy = policy or QueuePolicy()
        expired_ids: list[str] = []
        timestamp = _now()

        for path in self.store.list_session_paths():
            try:
                session = self.store.load_session_from_path(path)
            except Exception:
                continue

            queue_item = _dict(session.get("queue_item"))
            if queue_item.get("queue_state") != QUEUE_QUEUED:
                continue

            lifecycle = _dict(queue_item.get("lifecycle"))
            expires_at = _first(lifecycle.get("expires_at"))
            expire_dt = _parse_ts(expires_at)
            if expire_dt is None:
                enqueued_at = _first(_dict(queue_item.get("enqueue_context")).get("enqueued_at"))
                enqueued_dt = _parse_ts(enqueued_at)
                if enqueued_dt is None:
                    continue
                expire_dt = enqueued_dt + timedelta(seconds=policy.default_ttl_seconds)

            if datetime.now() < expire_dt:
                continue

            session = dict(session)
            queue_item["queue_state"] = QUEUE_EXPIRED
            lifecycle["expired_at"] = timestamp
            lifecycle["expire_reason"] = "ttl_exceeded"
            queue_item["lifecycle"] = lifecycle
            retry = _dict(queue_item.get("retry"))
            retry["last_terminal_state"] = QUEUE_EXPIRED
            queue_item["retry"] = retry
            session["queue_item"] = queue_item
            session["state"] = QUEUE_EXPIRED
            session["updated_at"] = timestamp

            priority_decision = dict(session.get("priority_decision") or {})
            priority_decision["queue_position"] = None
            session["priority_decision"] = priority_decision

            self._append_state_history(session, QUEUE_EXPIRED, timestamp, queue_item, reason="queue expired: ttl")
            self._audit_session_event(
                session,
                event_type="EXPIRED",
                actor="system",
                queue_item=queue_item,
                details={"expire_reason": "ttl_exceeded"},
            )
            self.store.save_session(session, overwrite=True)
            expired_ids.append(_first(queue_item.get("queue_item_id")))

        if expired_ids:
            self.rebuild_index()
        return expired_ids

    def peek_next(self, policy: QueuePolicy | None = None) -> dict[str, Any] | None:
        policy = policy or QueuePolicy()
        self.expire_stale(policy)
        items = self._sorted_active_items()
        return items[0] if items else None

    def dequeue_next(
        self,
        *,
        actor: str = "system",
        policy: QueuePolicy | None = None,
    ) -> DequeueResult:
        policy = policy or QueuePolicy()
        self.expire_stale(policy)
        items = self._sorted_active_items()
        if not items:
            return DequeueResult(False, reject_code="QUEUE_EMPTY", reject_reasons=["No queued items available."])

        head = items[0]
        session_id = head["execution_session_id"]
        session = self.store.load_session(session_id)
        queue_item = _dict(session.get("queue_item"))

        if queue_item.get("queue_state") != QUEUE_QUEUED:
            self.rebuild_index()
            return DequeueResult(
                False,
                reject_code="STALE_INDEX",
                reject_reasons=[f"Index head {session_id} is no longer QUEUED."],
            )

        timestamp = _now()
        queue_item["queue_state"] = QUEUE_DEQUEUED
        lifecycle = _dict(queue_item.get("lifecycle"))
        lifecycle["dequeued_at"] = timestamp
        lifecycle["dequeued_by"] = actor
        queue_item["lifecycle"] = lifecycle
        retry = _dict(queue_item.get("retry"))
        retry["last_terminal_state"] = QUEUE_DEQUEUED
        queue_item["retry"] = retry

        session = dict(session)
        session["queue_item"] = queue_item
        session["state"] = QUEUE_DEQUEUED
        session["updated_at"] = timestamp

        priority_decision = dict(session.get("priority_decision") or {})
        priority_decision["queue_position"] = None
        session["priority_decision"] = priority_decision

        queue_priority = dict(queue_item.get("priority") or {})
        queue_priority["queue_position"] = None
        queue_item["priority"] = queue_priority
        session["queue_item"] = queue_item

        self._append_state_history(session, QUEUE_DEQUEUED, timestamp, queue_item, reason="queue dequeued")
        self._audit_session_event(
            session,
            event_type="DEQUEUED",
            actor=actor,
            queue_item=queue_item,
            details={"queue_item_id": queue_item.get("queue_item_id")},
        )

        self.store.save_session(session, overwrite=True)
        self.rebuild_index()

        refreshed = self.store.load_session(session_id)
        return DequeueResult(True, session=refreshed, queue_item=refreshed.get("queue_item"))

    def dequeue_by_id(
        self,
        session_id: str,
        *,
        actor: str = "system",
        policy: QueuePolicy | None = None,
    ) -> DequeueResult:
        policy = policy or QueuePolicy()
        self.expire_stale(policy)
        session = self.store.load_session(session_id)
        queue_item = _dict(session.get("queue_item"))

        if queue_item.get("queue_state") != QUEUE_QUEUED:
            return DequeueResult(
                False,
                session=session,
                reject_code="NOT_QUEUED",
                reject_reasons=[f"Session {session_id} has no active QUEUED item."],
            )

        timestamp = _now()
        queue_item["queue_state"] = QUEUE_DEQUEUED
        lifecycle = _dict(queue_item.get("lifecycle"))
        lifecycle["dequeued_at"] = timestamp
        lifecycle["dequeued_by"] = actor
        queue_item["lifecycle"] = lifecycle
        retry = _dict(queue_item.get("retry"))
        retry["last_terminal_state"] = QUEUE_DEQUEUED
        queue_item["retry"] = retry

        session = dict(session)
        session["queue_item"] = queue_item
        session["state"] = QUEUE_DEQUEUED
        session["updated_at"] = timestamp

        priority_decision = dict(session.get("priority_decision") or {})
        priority_decision["queue_position"] = None
        session["priority_decision"] = priority_decision

        queue_priority = dict(queue_item.get("priority") or {})
        queue_priority["queue_position"] = None
        queue_item["priority"] = queue_priority
        session["queue_item"] = queue_item

        self._append_state_history(session, QUEUE_DEQUEUED, timestamp, queue_item, reason="queue dequeued")
        self._audit_session_event(
            session,
            event_type="DEQUEUED",
            actor=actor,
            queue_item=queue_item,
            details={"queue_item_id": queue_item.get("queue_item_id"), "targeted": True},
        )

        self.store.save_session(session, overwrite=True)
        self.rebuild_index()
        refreshed = self.store.load_session(session_id)
        return DequeueResult(True, session=refreshed, queue_item=refreshed.get("queue_item"))

    def queue_status(self, policy: QueuePolicy | None = None) -> dict[str, Any]:
        policy = policy or QueuePolicy()
        self.expire_stale(policy)
        items = self._sorted_active_items()
        oldest = items[-1]["enqueued_at"] if items else None
        bands: dict[str, int] = {}
        for item in items:
            band = item.get("priority_band") or "unknown"
            bands[band] = bands.get(band, 0) + 1
        return {
            "depth": len(items),
            "max_depth": policy.max_active_queue_depth,
            "oldest_enqueued_at": oldest,
            "bands": bands,
            "items": items,
        }

    def rebuild_index(self) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []

        for path in self.store.list_session_paths():
            try:
                session = self.store.load_session_from_path(path)
            except Exception:
                continue
            queue_item = _dict(session.get("queue_item"))
            if queue_item.get("queue_state") != QUEUE_QUEUED:
                continue

            priority = _dict(queue_item.get("priority"))
            enqueue_ctx = _dict(queue_item.get("enqueue_context"))
            entries.append(
                {
                    "queue_item_id": queue_item.get("queue_item_id"),
                    "queue_item_uuid": queue_item.get("queue_item_uuid"),
                    "execution_session_id": ExecutionSessionStore.extract_session_id(session),
                    "session_uuid": session.get("session_uuid"),
                    "queue_state": QUEUE_QUEUED,
                    "effective_priority": priority.get("effective_priority", 0.0),
                    "priority_band": priority.get("priority_band"),
                    "enqueued_at": enqueue_ctx.get("enqueued_at"),
                }
            )

        entries.sort(
            key=lambda item: (
                -float(item.get("effective_priority") or 0),
                item.get("enqueued_at") or "",
                item.get("execution_session_id") or "",
            )
        )

        for position, entry in enumerate(entries, start=1):
            entry["queue_position"] = position
            session_id = entry["execution_session_id"]
            try:
                session = self.store.load_session(session_id)
            except FileNotFoundError:
                continue
            session = dict(session)
            queue_item = dict(session.get("queue_item") or {})
            queue_priority = dict(queue_item.get("priority") or {})
            queue_priority["queue_position"] = position
            queue_item["priority"] = queue_priority
            session["queue_item"] = queue_item
            priority_decision = dict(session.get("priority_decision") or {})
            priority_decision["queue_position"] = position
            session["priority_decision"] = priority_decision
            self.store.save_session(session, overwrite=True)

        index = {
            "index_version": INDEX_VERSION,
            "updated_at": _now(),
            "items": entries,
        }
        self.store.save_queue_index(index)
        return index

    def _build_queue_item(
        self,
        session: dict[str, Any],
        policy: QueuePolicy,
        timestamp: str,
    ) -> dict[str, Any]:
        readiness = _dict(session.get("execution_readiness"))
        approval = _dict(session.get("approval_decision"))
        budget = _dict(session.get("budget_decision"))
        simulation = _dict(session.get("simulation_report"))
        simulation_meta = _dict(simulation.get("metadata"))
        provider_selection = _dict(session.get("provider_selection"))
        priority_decision = _dict(session.get("priority_decision"))

        band = _first(session.get("priority_band"), priority_decision.get("priority_band"), default="medium").lower()
        band_weight = BAND_WEIGHTS.get(band, BAND_WEIGHTS["medium"])
        priority_score = float(priority_decision.get("priority_score") or session.get("story_quality_score") or 0)
        readiness_decision = _first(readiness.get("decision"))
        readiness_bonus = READINESS_BONUS.get(readiness_decision, 0.0)
        effective_priority = round(band_weight * 1000 + priority_score + readiness_bonus, 1)

        existing = _dict(session.get("queue_item"))
        prior_attempts = int(_dict(existing.get("retry")).get("enqueue_attempts_used") or 0)
        enqueue_attempt = prior_attempts + 1

        expires_dt = datetime.now() + timedelta(seconds=policy.default_ttl_seconds)
        expires_at = expires_dt.strftime(TIMESTAMP_FORMAT)

        queue_fingerprint = compute_queue_fingerprint(session)
        simulation_fp = simulation_meta.get("simulation_fingerprint")

        return {
            "queue_item_uuid": str(uuid.uuid4()),
            "queue_item_id": generate_queue_item_id(),
            "queue_state": QUEUE_QUEUED,
            "queue_version": ENGINE_VERSION,
            "session_uuid": session.get("session_uuid"),
            "execution_session_id": ExecutionSessionStore.extract_session_id(session),
            "brief_id": session.get("brief_id"),
            "priority": {
                "priority_band": band,
                "priority_score": priority_score,
                "queue_position": None,
                "effective_priority": effective_priority,
            },
            "eligibility_snapshot": {
                "readiness_decision": readiness_decision,
                "readiness_score": readiness.get("readiness_score"),
                "approval_status": approval.get("status"),
                "budget_status": budget.get("budget_status"),
                "simulation_fingerprint": simulation_fp,
                "provider": _first(provider_selection.get("primary_provider"), session.get("provider")),
            },
            "enqueue_context": {
                "enqueued_at": timestamp,
                "enqueued_by": "system",
                "enqueue_attempt": enqueue_attempt,
                "enqueue_reason": "readiness_passed",
            },
            "lifecycle": {
                "dequeued_at": None,
                "dequeued_by": None,
                "cancelled_at": None,
                "cancelled_by": None,
                "cancel_reason": None,
                "expired_at": None,
                "expire_reason": None,
                "ttl_seconds": policy.default_ttl_seconds,
                "expires_at": expires_at,
            },
            "retry": {
                "max_enqueue_attempts": policy.max_enqueue_attempts,
                "enqueue_attempts_used": enqueue_attempt,
                "requeue_allowed": True,
                "last_terminal_state": None,
            },
            "metadata": {
                "queue_provenance": {
                    "engine": ENGINE_NAME,
                    "engine_version": ENGINE_VERSION,
                    "policy_version": policy.policy_version,
                    "evaluated_at": timestamp,
                    "policy_snapshot": policy.snapshot(),
                },
                "queue_fingerprint": queue_fingerprint,
                "queue_fingerprint_version": QUEUE_FINGERPRINT_VERSION,
                "queue_fingerprint_sources": list(QUEUE_FINGERPRINT_SOURCES),
                "readiness_provenance": _dict(_dict(readiness.get("metadata")).get("readiness_provenance")),
                "governance_decision_ids": _dict(_dict(readiness.get("metadata")).get("governance_decision_ids")),
            },
        }

    def _active_index_items(self) -> list[dict[str, Any]]:
        index = self.store.load_queue_index()
        return [
            item
            for item in index.get("items") or []
            if isinstance(item, dict) and item.get("queue_state") == QUEUE_QUEUED
        ]

    def _sorted_active_items(self) -> list[dict[str, Any]]:
        items = self._active_index_items()
        items.sort(
            key=lambda item: (
                -float(item.get("effective_priority") or 0),
                item.get("enqueued_at") or "",
                item.get("execution_session_id") or "",
            )
        )
        return items

    def _append_state_history(
        self,
        session: dict[str, Any],
        state: str,
        timestamp: str,
        queue_item: dict[str, Any],
        *,
        reason: str | None = None,
    ) -> None:
        priority = _dict(queue_item.get("priority"))
        default_reason = (
            f"queue engine: {state} "
            f"(item={queue_item.get('queue_item_id')}, position={priority.get('queue_position')})"
        )
        history = list(session.get("state_history") or [])
        history.append({"at": timestamp, "state": state, "reason": reason or default_reason})
        session["state_history"] = history

    def _audit_session_event(
        self,
        session: dict[str, Any],
        *,
        event_type: str,
        actor: str,
        queue_item: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        timestamp = _now()
        event = {
            "event_id": generate_audit_event_id(),
            "event_type": event_type,
            "at": timestamp,
            "queue_item_id": _first((queue_item or {}).get("queue_item_id")),
            "queue_item_uuid": (queue_item or {}).get("queue_item_uuid"),
            "actor": actor,
            "details": details or {},
        }
        audit_log = list(session.get("queue_audit_log") or [])
        audit_log.append(event)
        session["queue_audit_log"] = audit_log
        self.store.append_global_queue_audit(
            {
                **event,
                "execution_session_id": ExecutionSessionStore.extract_session_id(session),
                "session_uuid": session.get("session_uuid"),
            }
        )


__all__ = [
    "ExecutionQueueEngine",
    "QueuePolicy",
    "EnqueueResult",
    "DequeueResult",
    "QUEUE_QUEUED",
    "QUEUE_DEQUEUED",
    "QUEUE_CANCELLED",
    "QUEUE_EXPIRED",
]
