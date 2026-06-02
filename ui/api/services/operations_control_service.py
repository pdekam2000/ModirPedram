"""Operator session control for Execution Center API (Phase 10K-b)."""

from __future__ import annotations

from typing import Any

from content_brain.execution.operations_control_engine import OperationsControlEngine
from content_brain.execution.session_store import ExecutionSessionStore

API_VERSION = "0.6.0"


class OperationsControlService:
    def __init__(self, store: ExecutionSessionStore):
        self._engine = OperationsControlEngine(store)

    def eligibility(self, session_id: str) -> dict[str, Any]:
        payload = self._engine.eligibility(session_id)
        payload["api_version"] = API_VERSION
        return payload

    def retry(self, session_id: str, *, reason: str = "", actor: str = "operator") -> dict[str, Any]:
        return self._wrap(self._engine.retry(session_id, reason=reason, actor=actor))

    def cancel(self, session_id: str, *, reason: str = "", actor: str = "operator") -> dict[str, Any]:
        return self._wrap(self._engine.cancel(session_id, reason=reason, actor=actor))

    def archive(self, session_id: str, *, reason: str = "", actor: str = "operator") -> dict[str, Any]:
        return self._wrap(self._engine.archive(session_id, reason=reason, actor=actor))

    def requeue(self, session_id: str, *, reason: str = "", actor: str = "operator") -> dict[str, Any]:
        return self._wrap(self._engine.requeue(session_id, reason=reason, actor=actor))

    @staticmethod
    def _wrap(result: Any) -> dict[str, Any]:
        payload = result.to_dict()
        payload["api_version"] = API_VERSION
        return payload
