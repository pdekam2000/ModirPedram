"""UAT runtime API service (Phase 12D)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.uat_runtime_engine import (
    UATRuntimeEngine,
    UatReviewAlreadySubmittedError,
    UatReviewSubmission,
    UatRunAlreadyActiveError,
    validate_uat_config,
)
from content_brain.execution.uat_runtime_profile import UatRuntimeConfig
from ui.api.schemas.uat_runtime import UatReviewRequest, UatRunRequest

API_VERSION = "12d_v1"


class UatRuntimeService:
    """Thin wrapper for POST /uat/run, GET /uat/status, POST /uat/review."""

    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        engine: UATRuntimeEngine | None = None,
    ):
        self._store = store
        self._engine = engine or UATRuntimeEngine(store.project_root, store=store)

    def start_run(self, request: UatRunRequest) -> dict[str, Any]:
        config = validate_uat_config(
            UatRuntimeConfig(
                topic=request.topic,
                platform=request.platform,
                duration_seconds=request.duration_seconds,
                video_provider=request.video_provider,
                voice_provider=request.voice_provider,
                confirm_real_voice=request.confirm_real_voice,
                confirm_real_video=request.confirm_real_video,
                confirm_real_assembly=request.confirm_real_assembly,
                open_folder=request.open_folder,
                niche=request.niche,
            )
        )
        payload = self._engine.start(config)
        payload["api_version"] = API_VERSION
        return payload

    def get_status(self, session_id: str) -> dict[str, Any]:
        payload = self._engine.get_status(session_id)
        payload["api_version"] = API_VERSION
        return payload

    def submit_review(self, session_id: str, request: UatReviewRequest) -> dict[str, Any]:
        submission = UatReviewSubmission(
            story_quality_score=request.story_quality_score,
            visual_quality_score=request.visual_quality_score,
            voice_quality_score=request.voice_quality_score,
            subtitle_quality_score=request.subtitle_quality_score,
            continuity_score=request.continuity_score,
            overall_quality_score=request.overall_quality_score,
            comments=request.comments,
            publishable=request.publishable,
            submitted_by=request.submitted_by,
        )
        payload = self._engine.submit_review(session_id, submission)
        payload["api_version"] = API_VERSION
        return payload


def map_uat_error(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, UatRunAlreadyActiveError):
        return 409, "UAT_RUN_ALREADY_ACTIVE", str(exc)
    if isinstance(exc, UatReviewAlreadySubmittedError):
        return 409, "UAT_REVIEW_ALREADY_SUBMITTED", str(exc)
    if isinstance(exc, ValueError):
        return 400, "UAT_INVALID_REQUEST", str(exc)
    if isinstance(exc, FileNotFoundError):
        return 404, "UAT_SESSION_NOT_FOUND", str(exc)
    if isinstance(exc, KeyError):
        return 404, "UAT_SESSION_NOT_FOUND", str(exc)
    return 500, "UAT_INTERNAL_ERROR", str(exc)
