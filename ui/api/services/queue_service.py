"""Queue operations for Execution Center API."""

from __future__ import annotations

from typing import Any

from content_brain.execution.execution_queue_engine import ExecutionQueueEngine, QueuePolicy
from content_brain.execution.session_store import ExecutionSessionStore


class QueueService:
    def __init__(self, store: ExecutionSessionStore):
        self._store = store
        self._engine = ExecutionQueueEngine(store)

    def enqueue(self, session_id: str, *, actor: str = "api") -> dict[str, Any]:
        result = self._engine.enqueue_by_id(session_id, actor=actor)
        return {
            "success": result.success,
            "session_id": session_id,
            "state": (result.session or {}).get("state"),
            "queue_item": result.queue_item,
            "reject_code": result.reject_code,
            "reject_reasons": result.reject_reasons,
        }

    def cancel(self, session_id: str, *, reason: str = "cancelled", actor: str = "api") -> dict[str, Any]:
        session = self._engine.cancel_by_id(session_id, reason=reason, actor=actor)
        return {
            "success": True,
            "session_id": session_id,
            "state": session.get("state"),
            "queue_item": session.get("queue_item"),
        }

    def dequeue_next(self, *, actor: str = "api") -> dict[str, Any]:
        result = self._engine.dequeue_next(actor=actor)
        session = result.session or {}
        return {
            "success": result.success,
            "session_id": ExecutionSessionStore.extract_session_id(session) if session else None,
            "state": session.get("state"),
            "queue_item": result.queue_item,
            "reject_code": result.reject_code,
            "reject_reasons": result.reject_reasons,
        }

    def peek(self) -> dict[str, Any]:
        item = self._engine.peek_next()
        return {"item": item}

    def status(self) -> dict[str, Any]:
        return self._engine.queue_status(QueuePolicy())
