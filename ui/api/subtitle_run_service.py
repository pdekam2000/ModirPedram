"""Subtitle runtime run API service (Phase 11I-8)."""

from __future__ import annotations

from typing import Any

from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.subtitle_runtime_engine import SubtitleRuntimeEngine

API_VERSION = "0.7.3"


class SubtitleRunService:
    """Service wrapper for POST /sessions/{id}/subtitle/run."""

    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        engine: SubtitleRuntimeEngine | None = None,
    ):
        self._store = store
        self._engine = engine or SubtitleRuntimeEngine(store, project_root=store.project_root)

    def run(
        self,
        session_id: str,
        *,
        formats: list[str] | None = None,
        timing_strategy: str = "auto",
        overwrite: bool = False,
        language: str = "auto",
        triggered_by: str = "operator",
        force_retry: bool = False,
    ) -> dict[str, Any]:
        result = self._engine.run(
            session_id,
            formats=formats,
            timing_strategy=timing_strategy,
            overwrite=overwrite,
            language=language,
            triggered_by=triggered_by,
            force_retry=force_retry,
        )
        payload = result.to_dict()
        payload["api_version"] = API_VERSION
        return payload
