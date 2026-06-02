"""
Phase 11I-8 — subtitle runtime execution engine.

Orchestrates cue generation + format writing; mutates subtitle_generation slot only.
No FFmpeg, no legacy subtitle_engine, no voice/video slot mutation.
"""

from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.category_runtime_compat import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    SUBTITLE_ARTIFACT_CATEGORY,
    SUBTITLE_PROVIDER,
    ensure_multi_category_shell,
    sync_subtitle_category_aliases,
)
from content_brain.execution.operations_cancel import is_cancellation_requested
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.subtitle_cue_generation_engine import (
    ENGINE_VERSION as CUE_ENGINE_VERSION,
    SubtitleCueGenerationEngine,
    SubtitleCueGenerationRequest,
)
from content_brain.execution.subtitle_format_writer import (
    WRITER_VERSION,
    SubtitleFormatWriter,
    SubtitleWriteRequest,
)
from content_brain.execution.subtitle_preflight_runtime_slot import apply_subtitle_preflight_dry_run
from content_brain.execution.subtitle_run_action_policy import evaluate_subtitle_run_request

ENGINE_VERSION = "11i8_v1"
SLOT_VERSION = "11i7_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
STATUS_CANCELLED = "cancelled"
STATUS_REJECTED = "rejected"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _duration_seconds(started_at: str | None, completed_at: str | None) -> float | None:
    if not started_at or not completed_at:
        return None
    for fmt in (TIMESTAMP_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            start = datetime.strptime(started_at, fmt)
            end = datetime.strptime(completed_at, fmt)
            return max(0.0, (end - start).total_seconds())
        except ValueError:
            continue
    return None


def generate_subtitle_run_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"subtitle_run_{stamp}_{uuid.uuid4().hex[:6]}"


def _build_profile(language: str) -> dict[str, Any] | None:
    lang = str(language or "").strip().lower()
    if not lang or lang == "auto":
        return None
    return {"language_rules": {"caption_language": lang}}


def _resolve_timing_strategy(requested: str) -> str | None:
    value = str(requested or "auto").lower()
    if value == "auto":
        return None
    return value


@dataclass
class SubtitleRuntimeRunResult:
    success: bool
    session_id: str
    status: str
    message: str = ""
    code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    subtitle_slot: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    formats_written: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    manifest_path: str | None = None
    manifest: dict[str, Any] | None = None
    cue_count: int = 0
    validation_status: str = "invalid"
    source_type: str | None = None
    timing_strategy: str | None = None
    subtitles_executed: bool = False
    real_provider_called: bool = False
    video_mutated: bool = False
    voice_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "session_id": self.session_id,
            "status": self.status,
            "message": self.message,
            "formats_written": list(self.formats_written),
            "artifacts": list(self.artifacts),
            "cue_count": self.cue_count,
            "validation_status": self.validation_status,
            "subtitles_executed": self.subtitles_executed,
            "real_provider_called": self.real_provider_called,
            "video_mutated": self.video_mutated,
            "voice_mutated": self.voice_mutated,
        }
        if not self.success:
            payload["code"] = self.code
            if self.reject_reasons:
                payload["reject_reasons"] = self.reject_reasons
        if self.subtitle_slot is not None:
            payload["subtitle_slot"] = self.subtitle_slot
        if self.guard_result is not None:
            payload["guard_result"] = self.guard_result
        if self.manifest_path is not None:
            payload["manifest_path"] = self.manifest_path
        if self.manifest is not None:
            payload["manifest"] = self.manifest
        if self.source_type is not None:
            payload["source_type"] = self.source_type
        if self.timing_strategy is not None:
            payload["timing_strategy"] = self.timing_strategy
        return payload


class SubtitleRuntimeEngine:
    """Execute subtitle generation for a session — local sidecar files only."""

    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        project_root: str | Path | None = None,
    ):
        self.store = store
        self.project_root = Path(project_root or store.project_root).resolve()
        self.cue_engine = SubtitleCueGenerationEngine(self.project_root)
        self.format_writer = SubtitleFormatWriter(store, project_root=self.project_root)
        self._session_locks: dict[str, threading.Lock] = {}
        self._lock_guard = threading.Lock()

    def _session_lock(self, session_id: str) -> threading.Lock:
        with self._lock_guard:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            return self._session_locks[session_id]

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
    ) -> SubtitleRuntimeRunResult:
        with self._session_lock(session_id):
            return self._run_locked(
                session_id,
                formats=formats,
                timing_strategy=timing_strategy,
                overwrite=overwrite,
                language=language,
                triggered_by=triggered_by,
                force_retry=force_retry,
            )

    def _run_locked(
        self,
        session_id: str,
        *,
        formats: list[str] | None,
        timing_strategy: str,
        overwrite: bool,
        language: str,
        triggered_by: str,
        force_retry: bool,
    ) -> SubtitleRuntimeRunResult:
        session = self.store.load_session(session_id)
        voice_before = deepcopy(
            _dict(_dict(session.get("execution_runtime")).get("category_runtime")).get(CATEGORY_VOICE)
        )
        video_before = deepcopy(
            _dict(_dict(session.get("execution_runtime")).get("category_runtime")).get(CATEGORY_VIDEO)
        )

        runtime, subtitle_slot = self._prepare_context(session)

        policy = evaluate_subtitle_run_request(
            session,
            subtitle_slot,
            session_id=session_id,
            formats=formats,
            timing_strategy=timing_strategy,
            overwrite=overwrite,
            force_retry=force_retry,
            project_root=self.project_root,
        )
        if not policy.allowed:
            self._persist_subtitle_slot(session, runtime, subtitle_slot)
            self.store.save_session(session, overwrite=True)
            return SubtitleRuntimeRunResult(
                success=False,
                session_id=session_id,
                status=STATUS_REJECTED,
                message=policy.message,
                code=policy.code,
                reject_reasons=policy.reject_reasons,
                subtitle_slot=subtitle_slot,
                guard_result=policy.guard_result,
                video_mutated=False,
                voice_mutated=False,
            )

        run_id = generate_subtitle_run_id()
        started_at = _now()
        subtitle_slot = self._set_running(
            subtitle_slot,
            run_id=run_id,
            triggered_by=triggered_by,
            formats=formats,
            overwrite=overwrite,
            force_retry=force_retry,
            started_at=started_at,
        )
        runtime = self._persist_subtitle_slot(session, runtime, subtitle_slot)
        self.store.save_session(session, overwrite=True)

        if is_cancellation_requested(session):
            return self._finalize_cancelled(
                session,
                runtime,
                subtitle_slot,
                voice_before,
                video_before,
                started_at=started_at,
            )

        profile = _build_profile(language)
        cue_result = self.cue_engine.generate(
            SubtitleCueGenerationRequest(
                session=session,
                profile=profile,
                timing_strategy=_resolve_timing_strategy(timing_strategy),
            )
        )
        if not cue_result.passed or cue_result.batch is None:
            return self._finalize_failed(
                session,
                runtime,
                subtitle_slot,
                voice_before,
                video_before,
                code=cue_result.reject_code or "CUE_GENERATION_FAILED",
                reasons=cue_result.reject_reasons or ["Subtitle cue generation failed."],
                started_at=started_at,
            )

        if is_cancellation_requested(session):
            return self._finalize_cancelled(
                session,
                runtime,
                subtitle_slot,
                voice_before,
                video_before,
                started_at=started_at,
            )

        batch = cue_result.batch
        write_result = self.format_writer.write(
            SubtitleWriteRequest(
                batch=batch,
                session_id=session_id,
                formats=formats,
                overwrite=overwrite,
                profile=profile,
            )
        )
        if not write_result.passed:
            return self._finalize_failed(
                session,
                runtime,
                subtitle_slot,
                voice_before,
                video_before,
                code=write_result.reject_code or "WRITE_FAILED",
                reasons=write_result.reject_reasons or ["Subtitle format write failed."],
                started_at=started_at,
                partial_artifacts=[record.to_dict() for record in write_result.files],
            )

        completed_at = _now()
        artifact_records = [record.to_dict() for record in write_result.files]
        subtitle_slot = self._set_completed(
            subtitle_slot,
            batch=batch,
            write_result=write_result,
            artifact_records=artifact_records,
            started_at=started_at,
            completed_at=completed_at,
        )
        runtime = self._persist_subtitle_slot(session, runtime, subtitle_slot)
        runtime = self._update_artifacts_by_category(runtime, artifact_records)
        session["execution_runtime"] = runtime
        self.store.save_session(session, overwrite=True)

        voice_after = deepcopy(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VOICE)))
        video_after = deepcopy(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO)))

        return SubtitleRuntimeRunResult(
            success=True,
            session_id=session_id,
            status=STATUS_COMPLETED,
            message="Subtitle generation completed.",
            subtitle_slot=subtitle_slot,
            guard_result=policy.guard_result,
            formats_written=list(write_result.formats_written),
            artifacts=artifact_records,
            manifest_path=write_result.manifest_path,
            manifest=write_result.manifest,
            cue_count=batch.cue_count,
            validation_status=write_result.validation_status,
            source_type=batch.source_type,
            timing_strategy=batch.timing_strategy,
            subtitles_executed=True,
            real_provider_called=False,
            video_mutated=video_after != video_before,
            voice_mutated=voice_after != voice_before,
        )

    def _prepare_context(
        self,
        session: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        runtime = dict(_dict(session.get("execution_runtime")))
        runtime = ensure_multi_category_shell(runtime)
        runtime = apply_subtitle_preflight_dry_run(session, runtime, project_root=self.project_root)
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        sync_subtitle_category_aliases(category_runtime)
        subtitle_slot = dict(
            _dict(
                category_runtime.get(CATEGORY_SUBTITLE_GENERATION)
                or category_runtime.get("subtitles")
            )
        )
        session["execution_runtime"] = runtime
        return runtime, subtitle_slot

    def _persist_subtitle_slot(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        subtitle_slot: dict[str, Any],
    ) -> dict[str, Any]:
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
        video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
        category_runtime[CATEGORY_SUBTITLE_GENERATION] = subtitle_slot
        category_runtime["subtitles"] = subtitle_slot
        category_runtime[CATEGORY_VOICE] = voice_slot
        category_runtime[CATEGORY_VIDEO] = video_slot
        runtime["category_runtime"] = category_runtime

        operations = dict(_dict(runtime.get("operations")))
        operations["subtitle_execution"] = {
            "engine_version": ENGINE_VERSION,
            "last_status": subtitle_slot.get("status"),
            "last_run_id": _dict(subtitle_slot.get("subtitle_run")).get("run_id"),
            "subtitles_executed": bool(subtitle_slot.get("executed")),
            "real_provider_called": False,
        }
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return runtime

    def _update_artifacts_by_category(
        self,
        runtime: dict[str, Any],
        artifact_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        artifacts_by_category = dict(_dict(runtime.get("artifacts_by_category")))
        entries = []
        for record in artifact_records:
            entries.append(
                {
                    "format": record.get("format"),
                    "file_name": record.get("file_name"),
                    "file_path": record.get("file_path"),
                    "category": SUBTITLE_ARTIFACT_CATEGORY,
                    "validation_status": record.get("validation_status"),
                    "cue_count": record.get("cue_count"),
                }
            )
        artifacts_by_category[SUBTITLE_ARTIFACT_CATEGORY] = entries
        artifacts_by_category["subtitles"] = entries
        runtime["artifacts_by_category"] = artifacts_by_category
        return runtime

    def _set_running(
        self,
        subtitle_slot: dict[str, Any],
        *,
        run_id: str,
        triggered_by: str,
        formats: list[str] | None,
        overwrite: bool,
        force_retry: bool,
        started_at: str,
    ) -> dict[str, Any]:
        slot = dict(subtitle_slot)
        slot["status"] = STATUS_RUNNING
        slot["provider"] = SUBTITLE_PROVIDER
        slot["executed"] = False
        slot["dry_run"] = False
        slot["started_at"] = started_at
        slot["completed_at"] = None
        slot["duration_seconds"] = None
        slot["error"] = None
        slot["slot_version"] = SLOT_VERSION
        slot["updated_at"] = started_at
        slot["subtitle_run"] = {
            "run_id": run_id,
            "triggered_by": triggered_by,
            "formats_requested": list(formats or []),
            "overwrite": overwrite,
            "force_retry": force_retry,
            "engine_version": ENGINE_VERSION,
        }
        return slot

    def _set_completed(
        self,
        subtitle_slot: dict[str, Any],
        *,
        batch: Any,
        write_result: Any,
        artifact_records: list[dict[str, Any]],
        started_at: str,
        completed_at: str,
    ) -> dict[str, Any]:
        slot = dict(subtitle_slot)
        slot["status"] = STATUS_COMPLETED
        slot["provider"] = SUBTITLE_PROVIDER
        slot["executed"] = True
        slot["dry_run"] = False
        slot["source_type"] = batch.source_type
        slot["timing_strategy"] = batch.timing_strategy
        slot["language"] = batch.language
        slot["cue_count"] = batch.cue_count
        slot["formats_written"] = list(write_result.formats_written)
        slot["artifacts"] = artifact_records
        slot["manifest_path"] = write_result.manifest_path
        slot["validation_status"] = write_result.validation_status
        slot["started_at"] = started_at
        slot["completed_at"] = completed_at
        slot["duration_seconds"] = _duration_seconds(started_at, completed_at)
        slot["error"] = None
        slot["engine_version"] = CUE_ENGINE_VERSION
        slot["writer_version"] = WRITER_VERSION
        slot["runtime_engine_version"] = ENGINE_VERSION
        slot["slot_version"] = SLOT_VERSION
        slot["updated_at"] = completed_at
        return slot

    def _set_failed(
        self,
        subtitle_slot: dict[str, Any],
        *,
        code: str,
        reasons: list[str],
        started_at: str,
        partial_artifacts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        slot = dict(subtitle_slot)
        completed_at = _now()
        slot["status"] = STATUS_FAILED
        slot["executed"] = False
        slot["dry_run"] = False
        slot["validation_status"] = "invalid"
        slot["completed_at"] = completed_at
        slot["duration_seconds"] = _duration_seconds(started_at, completed_at)
        if partial_artifacts:
            slot["artifacts"] = partial_artifacts
        slot["error"] = {
            "code": code,
            "message": reasons[0] if reasons else "Subtitle run failed.",
            "category": "RUNTIME_ERROR",
        }
        slot["updated_at"] = completed_at
        return slot

    def _set_cancelled(
        self,
        subtitle_slot: dict[str, Any],
        *,
        started_at: str,
        reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        slot = dict(subtitle_slot)
        completed_at = _now()
        slot["status"] = STATUS_CANCELLED
        slot["executed"] = False
        slot["dry_run"] = False
        slot["completed_at"] = completed_at
        slot["duration_seconds"] = _duration_seconds(started_at, completed_at)
        slot["error"] = {
            "code": STATUS_CANCELLED.upper(),
            "message": reasons[0] if reasons else "Subtitle run cancelled.",
            "category": "RUNTIME_CANCEL",
        }
        slot["updated_at"] = completed_at
        return slot

    def _finalize_failed(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        subtitle_slot: dict[str, Any],
        voice_before: dict[str, Any],
        video_before: dict[str, Any],
        *,
        code: str,
        reasons: list[str],
        started_at: str,
        partial_artifacts: list[dict[str, Any]] | None = None,
    ) -> SubtitleRuntimeRunResult:
        session_id = str(session.get("execution_session_id") or "")
        subtitle_slot = self._set_failed(
            subtitle_slot,
            code=code,
            reasons=reasons,
            started_at=started_at,
            partial_artifacts=partial_artifacts,
        )
        runtime = self._persist_subtitle_slot(session, runtime, subtitle_slot)
        self.store.save_session(session, overwrite=True)
        voice_after = deepcopy(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VOICE)))
        video_after = deepcopy(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO)))
        return SubtitleRuntimeRunResult(
            success=False,
            session_id=session_id,
            status=STATUS_FAILED,
            message=reasons[0] if reasons else "Subtitle run failed.",
            code=code,
            reject_reasons=reasons,
            subtitle_slot=subtitle_slot,
            validation_status="invalid",
            video_mutated=video_after != video_before,
            voice_mutated=voice_after != voice_before,
        )

    def _finalize_cancelled(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        subtitle_slot: dict[str, Any],
        voice_before: dict[str, Any],
        video_before: dict[str, Any],
        *,
        started_at: str,
    ) -> SubtitleRuntimeRunResult:
        session_id = str(session.get("execution_session_id") or "")
        subtitle_slot = self._set_cancelled(
            subtitle_slot,
            started_at=started_at,
            reasons=["Operations cancel requested."],
        )
        runtime = self._persist_subtitle_slot(session, runtime, subtitle_slot)
        self.store.save_session(session, overwrite=True)
        voice_after = deepcopy(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VOICE)))
        video_after = deepcopy(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO)))
        return SubtitleRuntimeRunResult(
            success=False,
            session_id=session_id,
            status=STATUS_CANCELLED,
            message="Subtitle run cancelled.",
            code=STATUS_CANCELLED.upper(),
            reject_reasons=["Operations cancel requested."],
            subtitle_slot=subtitle_slot,
            video_mutated=video_after != video_before,
            voice_mutated=voice_after != voice_before,
        )


__all__ = [
    "ENGINE_VERSION",
    "SLOT_VERSION",
    "STATUS_CANCELLED",
    "STATUS_REJECTED",
    "SubtitleRuntimeRunResult",
    "SubtitleRuntimeEngine",
    "generate_subtitle_run_id",
]
