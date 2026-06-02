"""
Queue integrity validation before provider dispatch (Phase 10I).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.execution_readiness_gate import (
    READINESS_READY,
    READINESS_WARNINGS,
)
from content_brain.execution.session_fingerprint import compute_queue_fingerprint

ELIGIBLE_READINESS = {READINESS_READY, READINESS_WARNINGS}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class IntegrityResult:
    passed: bool
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    reject_code: str | None = None


class QueueIntegrityValidator:
    """Validate session is safe to dispatch after dequeue."""

    def validate(
        self,
        session: dict[str, Any],
        *,
        require_queue_fingerprint: bool = True,
        require_readiness: bool = True,
    ) -> IntegrityResult:
        warnings: list[str] = []
        failures: list[str] = []

        state = str(session.get("state", "")).upper()
        if state != "DEQUEUED":
            failures.append(f"Session state is {state or 'UNKNOWN'}, expected DEQUEUED.")
            return IntegrityResult(False, warnings, failures, "NOT_DEQUEUED")

        queue_item = _dict(session.get("queue_item"))
        if queue_item.get("queue_state") != "DEQUEUED":
            failures.append(
                f"Queue item state is {queue_item.get('queue_state') or 'missing'}, expected DEQUEUED."
            )
            return IntegrityResult(False, warnings, failures, "NOT_DEQUEUED")

        if require_readiness:
            readiness = _dict(session.get("execution_readiness"))
            decision = str(readiness.get("decision", ""))
            if decision not in ELIGIBLE_READINESS:
                failures.append(f"Readiness decision is {decision or 'missing'}, not eligible.")
                return IntegrityResult(False, warnings, failures, "READINESS_DRIFT")

        metadata = _dict(queue_item.get("metadata"))
        stored_fp = metadata.get("queue_fingerprint")
        if not stored_fp:
            warnings.append("Queue fingerprint absent on queue item (legacy) — skipping fingerprint check.")
        elif require_queue_fingerprint:
            current_fp = compute_queue_fingerprint(session)
            if current_fp != stored_fp:
                failures.append("Queue fingerprint mismatch — session mutated after enqueue.")
                return IntegrityResult(False, warnings, failures, "STALE_QUEUE_FINGERPRINT")

        if failures:
            return IntegrityResult(False, warnings, failures, "INTEGRITY_FAILED")
        return IntegrityResult(True, warnings, failures, None)


__all__ = ["QueueIntegrityValidator", "IntegrityResult"]
