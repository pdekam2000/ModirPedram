"""Voice approval write API service (Phase 11H-1g) — metadata only, no TTS."""

from __future__ import annotations

from typing import Any

from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_approval_operations_engine import VoiceApprovalOperationsEngine

API_VERSION = "0.6.0"


class VoiceApprovalService:
    def __init__(self, store: ExecutionSessionStore):
        self._store = store
        self._engine = VoiceApprovalOperationsEngine(store, project_root=store.project_root)

    def approve(
        self,
        session_id: str,
        *,
        request_live_tts: bool,
        reason: str = "",
        approved_by: str = "local_user",
        ttl_minutes: int | None = None,
    ) -> dict[str, Any]:
        result = self._engine.approve(
            session_id,
            request_live_tts=request_live_tts,
            reason=reason,
            approved_by=approved_by,
            ttl_minutes=ttl_minutes,
        )
        return self._wrap(result)

    def reject(
        self,
        session_id: str,
        *,
        reason: str = "",
        rejected_by: str = "local_user",
    ) -> dict[str, Any]:
        result = self._engine.reject(session_id, reason=reason, rejected_by=rejected_by)
        return self._wrap(result)

    def expire(
        self,
        session_id: str,
        *,
        reason: str = "",
        expired_by: str = "local_user",
    ) -> dict[str, Any]:
        result = self._engine.expire(session_id, reason=reason, expired_by=expired_by)
        return self._wrap(result)

    def reset_approval(
        self,
        session_id: str,
        *,
        reason: str = "",
        reset_by: str = "local_user",
        clear_live_tts_request: bool = False,
    ) -> dict[str, Any]:
        result = self._engine.reset_approval(
            session_id,
            reason=reason,
            reset_by=reset_by,
            clear_live_tts_request=clear_live_tts_request,
        )
        return self._wrap(result)

    @staticmethod
    def _wrap(result: Any) -> dict[str, Any]:
        payload = result.to_dict()
        payload["api_version"] = API_VERSION
        return payload
