"""Voice live TTS run API service (Phase 11H-2a/2c/2d)."""

from __future__ import annotations

from typing import Any

from content_brain.execution.live_voice_tts_engine import LiveVoiceTtsEngine
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_live_tts_action_policy import (
    PROVIDER_MODE_MOCK,
    evaluate_voice_run_mode_request,
)

API_VERSION = "0.7.2"


class VoiceRunService:
    """Service wrapper for POST /sessions/{id}/voice/run."""

    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        engine: LiveVoiceTtsEngine | None = None,
    ):
        self._store = store
        self._engine = engine or LiveVoiceTtsEngine(store, project_root=store.project_root)

    def run(
        self,
        session_id: str,
        *,
        triggered_by: str = "local_user",
        reason: str = "",
        force_retry: bool = False,
        provider_mode: str = PROVIDER_MODE_MOCK,
        confirm_live_tts: bool = False,
    ) -> dict[str, Any]:
        effective_mode = str(provider_mode or PROVIDER_MODE_MOCK).strip().lower()
        mode_policy = evaluate_voice_run_mode_request(effective_mode, confirm_live_tts)
        if not mode_policy.allowed:
            return {
                "success": False,
                "session_id": session_id,
                "status": "rejected",
                "message": mode_policy.message,
                "code": mode_policy.code,
                "reject_reasons": mode_policy.reject_reasons,
                "provider_mode": effective_mode,
                "tts_executed": False,
                "real_provider_called": False,
                "video_mutated": False,
                "api_version": API_VERSION,
            }

        result = self._engine.run(
            session_id,
            triggered_by=triggered_by,
            reason=reason,
            force_retry=force_retry,
            provider_mode=effective_mode,
            confirm_live_tts=confirm_live_tts,
        )
        return self._wrap(result)

    @staticmethod
    def _wrap(result: Any) -> dict[str, Any]:
        payload = result.to_dict()
        payload["api_version"] = API_VERSION
        return payload
