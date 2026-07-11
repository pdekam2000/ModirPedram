"""
Phase 11H-2a/2c/2d — live voice TTS execution engine.

Mock provider is default; live_elevenlabs uses ElevenLabsRuntimeAdapter when all gates pass.
Never imports legacy ElevenLabsVoiceProvider.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from content_brain.execution.audio_artifact_validator import AudioArtifactValidator
from content_brain.execution.category_runtime_compat import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    ensure_multi_category_shell,
)
from content_brain.execution.elevenlabs_runtime_adapter import (
    CODE_ELEVENLABS_CANCELLED,
    build_live_manifest_extras,
)
from content_brain.execution.mock_voice_tts_provider import (
    PROVIDER_ID as MOCK_PROVIDER_ID,
    PROVIDER_MODE as MOCK_PROVIDER_MODE,
    MockVoiceTtsProvider,
)
from content_brain.execution.operations_cancel import is_cancellation_requested
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_narration_adapter import SessionNarrationAdapter
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_live_tts_action_policy import (
    PROVIDER_MODE_LIVE,
    PROVIDER_MODE_MOCK,
    evaluate_voice_live_tts_run,
    is_live_real_http_permitted,
)
from content_brain.execution.voice_live_tts_smoke_profile import (
    SMOKE_MAX_SEGMENTS,
    evaluate_voice_live_tts_smoke_caps,
)
from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run
from content_brain.execution.voice_provider_factory import build_voice_tts_provider
from providers.elevenlabs_config import ElevenLabsConfigResolver

logger = logging.getLogger(__name__)

ENGINE_VERSION = "11h2d_v1"
MANIFEST_VERSION_MOCK = "11h2a_v1"
MANIFEST_VERSION_LIVE = "11h2d_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

STATUS_CANCELLED = "cancelled"
CANCEL_REJECT_CODES = frozenset({"CANCELLED", CODE_ELEVENLABS_CANCELLED})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


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


def generate_voice_tts_audit_event_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"voice_tts_evt_{stamp}_{uuid.uuid4().hex[:6]}"


def _log_uat_smoke_cap_context(
    session: dict[str, Any],
    *,
    session_id: str,
    voice_slot: dict[str, Any],
    planned_voice_segments: int,
) -> None:
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations"))
    uat_run = _dict(operations.get("uat_run"))
    smoke_guard = _dict(uat_run.get("smoke_duration_guard"))
    brief = _dict(session.get("brief_snapshot"))
    video_plan = _dict(brief.get("video_format_plan"))
    approval = _dict(voice_slot.get("approval"))
    adapter = _dict(voice_slot.get("narration_adapter"))

    logger.warning(
        "[UAT_SMOKE_CAP_CONTEXT] %s",
        json.dumps(
            {
                "session_id": session_id,
                "duration_seconds_uat_target": uat_run.get("target_duration_seconds"),
                "duration_seconds_smoke_guard_original": smoke_guard.get("original_duration_seconds"),
                "duration_seconds_smoke_guard_adjusted": smoke_guard.get("smoke_adjusted_duration_seconds"),
                "duration_seconds_brief_plan": video_plan.get("target_duration_seconds"),
                "clip_duration": video_plan.get("clip_duration_seconds"),
                "planned_clip_count": video_plan.get("clip_count"),
                "planned_voice_segments": planned_voice_segments,
                "planned_voice_segments_slot": voice_slot.get("segment_count"),
                "planned_voice_segments_approval": approval.get("estimated_segment_count"),
                "planned_voice_segments_adapter": adapter.get("segment_count"),
                "smoke_cap": SMOKE_MAX_SEGMENTS,
                "video_provider": uat_run.get("video_provider") or session.get("provider"),
                "voice_provider": uat_run.get("voice_provider") or voice_slot.get("provider"),
            },
            sort_keys=True,
                ensure_ascii=False,
            ),
    )


@dataclass
class LiveVoiceTtsRunResult:
    success: bool
    session_id: str
    status: str
    message: str = ""
    code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    voice_slot: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    manifest_path: str | None = None
    manifest: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    provider_mode: str = PROVIDER_MODE_MOCK
    tts_executed: bool = False
    real_provider_called: bool = False
    video_mutated: bool = False
    panel_excerpt: dict[str, Any] | None = None
    audit_event: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "session_id": self.session_id,
            "status": self.status,
            "message": self.message,
            "provider_mode": self.provider_mode,
            "tts_executed": self.tts_executed,
            "real_provider_called": self.real_provider_called,
            "video_mutated": self.video_mutated,
        }
        if not self.success:
            payload["code"] = self.code
            if self.reject_reasons:
                payload["reject_reasons"] = self.reject_reasons
        if self.voice_slot is not None:
            payload["voice_slot"] = self.voice_slot
        if self.guard_result is not None:
            payload["guard_result"] = self.guard_result
        if self.manifest_path is not None:
            payload["manifest_path"] = self.manifest_path
        if self.manifest is not None:
            payload["manifest"] = self.manifest
        if self.artifacts:
            payload["artifacts"] = list(self.artifacts)
        if self.panel_excerpt is not None:
            payload["panel_excerpt"] = self.panel_excerpt
        if self.audit_event is not None:
            payload["audit_event"] = self.audit_event
        return payload


class LiveVoiceTtsEngine:
    """Execute voice TTS — mock by default; live ElevenLabs when all gates pass."""

    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        project_root: str | Path | None = None,
        provider_factory: Callable[..., Any] | None = None,
        simulate_failure_at: int | None = None,
        http_client: Any | None = None,
    ):
        self.store = store
        self.project_root = Path(project_root or store.project_root).resolve()
        self._provider_factory = provider_factory
        self._simulate_failure_at = simulate_failure_at
        self._http_client = http_client

    def run(
        self,
        session_id: str,
        *,
        triggered_by: str = "local_user",
        reason: str = "",
        force_retry: bool = False,
        provider_mode: str = PROVIDER_MODE_MOCK,
        confirm_live_tts: bool = False,
    ) -> LiveVoiceTtsRunResult:
        effective_mode = str(provider_mode or PROVIDER_MODE_MOCK).lower()
        session = self.store.load_session(session_id)
        runtime, voice_slot, video_before = self._prepare_context(session)

        policy = evaluate_voice_live_tts_run(
            session,
            voice_slot,
            force_retry=force_retry,
            project_root=str(self.project_root),
            provider_mode=effective_mode,
            confirm_live_tts=confirm_live_tts,
        )
        if not policy.allowed:
            audit = self._append_audit(
                session,
                runtime,
                actor=triggered_by,
                reason=reason,
                allowed=False,
                execution_status="rejected",
                blocked_reasons=policy.reject_reasons,
                voice_slot=voice_slot,
                provider_mode=effective_mode,
            )
            self.store.save_session(session, overwrite=True)
            return LiveVoiceTtsRunResult(
                success=False,
                session_id=session_id,
                status="rejected",
                message=policy.message,
                code=policy.code,
                reject_reasons=policy.reject_reasons,
                voice_slot=voice_slot,
                guard_result=policy.guard_result,
                panel_excerpt=self._panel_excerpt(voice_slot, runtime, effective_mode),
                audit_event=audit,
                provider_mode=effective_mode,
                tts_executed=False,
                real_provider_called=False,
                video_mutated=False,
            )

        adapter = SessionNarrationAdapter()
        bundle = adapter.build(session)
        segments = list(bundle.segments)
        total_segments = len(segments)

        if effective_mode == PROVIDER_MODE_LIVE:
            _log_uat_smoke_cap_context(
                session,
                session_id=session_id,
                voice_slot=voice_slot,
                planned_voice_segments=total_segments,
            )
            narration_caps = evaluate_voice_live_tts_smoke_caps(
                voice_slot,
                narration_segment_count=total_segments,
                narration_character_count=bundle.total_text_length,
            )
            if not narration_caps.allowed:
                audit = self._append_audit(
                    session,
                    runtime,
                    actor=triggered_by,
                    reason=reason,
                    allowed=False,
                    execution_status="rejected",
                    blocked_reasons=narration_caps.reject_reasons,
                    voice_slot=voice_slot,
                    provider_mode=effective_mode,
                )
                self.store.save_session(session, overwrite=True)
                return LiveVoiceTtsRunResult(
                    success=False,
                    session_id=session_id,
                    status="rejected",
                    message=narration_caps.message,
                    code=narration_caps.code,
                    reject_reasons=narration_caps.reject_reasons,
                    voice_slot=voice_slot,
                    guard_result=policy.guard_result,
                    panel_excerpt=self._panel_excerpt(voice_slot, runtime, effective_mode),
                    audit_event=audit,
                    provider_mode=effective_mode,
                    tts_executed=False,
                    real_provider_called=False,
                    video_mutated=False,
                )

        artifact_root = self.store.artifact_dir(session_id, CATEGORY_VOICE)
        started_at = _now()

        voice_slot = self._set_running(
            voice_slot,
            artifact_root,
            total_segments,
            started_at,
            provider_mode=effective_mode,
        )
        runtime = self._persist_voice_slot(session, runtime, voice_slot, provider_mode=effective_mode)
        self.store.save_session(session, overwrite=True)

        cancel_check = lambda: is_cancellation_requested(session)
        if self._provider_factory:
            provider = self._provider_factory(cancel_check)
        elif effective_mode == PROVIDER_MODE_LIVE:
            from content_brain.execution.voice_live_tts_smoke_profile import (
                SMOKE_MAX_RETRY_ATTEMPTS,
                SMOKE_TIMEOUT_SECONDS,
            )

            provider = build_voice_tts_provider(
                PROVIDER_MODE_LIVE,
                session,
                project_root=self.project_root,
                cancel_check=cancel_check,
                http_client=self._http_client,
                allow_real_http=is_live_real_http_permitted() and self._http_client is None,
                timeout_seconds=SMOKE_TIMEOUT_SECONDS,
                max_retry_attempts=SMOKE_MAX_RETRY_ATTEMPTS,
            )
        else:
            provider = MockVoiceTtsProvider(
                fail_on_segment=self._simulate_failure_at,
                cancel_check=cancel_check,
            )

        artifact_records: list[dict[str, Any]] = []
        progress = _dict(voice_slot.get("live_tts_progress"))
        last_error: dict[str, Any] | None = None
        execution_status = STATUS_COMPLETED
        result_code: str | None = None
        reject_reasons: list[str] = []
        total_retry_count = 0
        last_request_id: str | None = None
        real_provider_called = False

        for segment in segments:
            if cancel_check():
                execution_status = STATUS_CANCELLED
                result_code = "CANCELLED"
                reject_reasons = ["Cooperative cancellation requested."]
                last_error = {"code": "CANCELLED", "message": reject_reasons[0]}
                break

            index = segment.segment_index
            filename = f"narration_{index:03d}.mp3"
            output_path = artifact_root / filename

            progress["current_segment"] = index
            progress["progress_percent"] = int((index - 1) / total_segments * 100) if total_segments else 0
            voice_slot["live_tts_progress"] = progress
            runtime = self._persist_voice_slot(
                session, runtime, voice_slot, provider_mode=effective_mode
            )
            self.store.save_session(session, overwrite=True)

            seg_result = provider.synthesize_segment(
                segment.text,
                output_path,
                segment_index=index,
                text_hash=segment.text_hash,
            )

            seg_retry = int(getattr(seg_result, "retry_count", 0) or 0)
            total_retry_count += seg_retry
            progress["retry_count"] = total_retry_count
            seg_request_id = getattr(seg_result, "request_id", None)
            if seg_request_id:
                last_request_id = str(seg_request_id)
            if getattr(seg_result, "real_provider_called", False):
                real_provider_called = True

            if not seg_result.success:
                reject_code = getattr(seg_result, "reject_code", None) or "PROVIDER_ERROR"
                execution_status = STATUS_CANCELLED if reject_code in CANCEL_REJECT_CODES else STATUS_FAILED
                result_code = reject_code
                reject_reasons = list(getattr(seg_result, "reject_reasons", None) or [])
                last_error = {
                    "code": result_code,
                    "message": reject_reasons[0] if reject_reasons else "Provider failed.",
                }
                break

            artifact_records.append(
                {
                    "artifact_id": f"voice_seg_{index:03d}",
                    "segment_index": index,
                    "file_path": seg_result.output_path,
                    "file_name": filename,
                    "extension": ".mp3",
                    "size_bytes": getattr(seg_result, "size_bytes", 0),
                    "character_count": getattr(seg_result, "character_count", len(segment.text)),
                    "text_hash": getattr(seg_result, "text_hash", segment.text_hash),
                    "beat_id": segment.beat_id,
                    "request_id": seg_request_id,
                    "retry_count": seg_retry,
                }
            )

        completed_at = _now()
        progress["current_segment"] = progress.get("current_segment", 0)
        progress["total_segments"] = total_segments
        progress["completed_at"] = completed_at
        progress["duration_seconds"] = _duration_seconds(started_at, completed_at)
        progress["partial_artifact_count"] = len(artifact_records)
        progress["last_error"] = last_error

        manifest_path = artifact_root / "voice_manifest.json"
        manifest: dict[str, Any] | None = None
        validation_status = "invalid"
        tts_executed = False

        if execution_status == STATUS_COMPLETED and len(artifact_records) == total_segments:
            validator = AudioArtifactValidator()
            validation = validator.validate(artifact_records, dry_run=False, min_artifact_bytes=1)
            if validation.passed:
                enriched = validation.enriched_artifacts or artifact_records
                for item in enriched:
                    item["validation_status"] = "valid"
                artifact_records = enriched
                validation_status = "valid"
                progress["progress_percent"] = 100
                manifest = self._build_manifest(
                    session_id=session_id,
                    session=session,
                    segments=segments,
                    artifact_records=artifact_records,
                    started_at=started_at,
                    completed_at=completed_at,
                    validation_status=validation_status,
                    execution_status=STATUS_COMPLETED,
                    partial=False,
                    character_count=bundle.total_text_length,
                    provider_mode=effective_mode,
                    total_retry_count=total_retry_count,
                    request_id=last_request_id,
                )
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
                voice_slot = self._set_completed(
                    voice_slot,
                    artifact_records,
                    str(manifest_path.resolve()),
                    manifest,
                    progress,
                    started_at,
                    completed_at,
                )
                tts_executed = True
            else:
                execution_status = STATUS_FAILED
                result_code = validation.reject_code or "ARTIFACT_VALIDATION_FAILED"
                reject_reasons = list(validation.reject_reasons)
                progress["last_error"] = {"code": result_code, "message": reject_reasons[0] if reject_reasons else "Validation failed."}
                voice_slot = self._set_failed(voice_slot, progress, result_code, reject_reasons, partial_artifacts=artifact_records)
        elif execution_status == STATUS_CANCELLED:
            progress["cancelled_at"] = completed_at
            validation_status = "partial" if artifact_records else "invalid"
            manifest = self._build_manifest(
                session_id=session_id,
                session=session,
                segments=segments[: len(artifact_records)],
                artifact_records=artifact_records,
                started_at=started_at,
                completed_at=completed_at,
                validation_status=validation_status,
                execution_status=STATUS_CANCELLED,
                partial=True,
                character_count=sum(a.get("character_count", 0) for a in artifact_records),
                provider_mode=effective_mode,
                total_retry_count=total_retry_count,
                request_id=last_request_id,
            )
            if artifact_records:
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            voice_slot = self._set_cancelled(
                voice_slot,
                progress,
                result_code or "CANCELLED",
                reject_reasons,
                artifact_records,
                str(manifest_path.resolve()) if artifact_records else None,
            )
        else:
            validation_status = "partial" if artifact_records else "invalid"
            voice_slot = self._set_failed(
                voice_slot,
                progress,
                result_code or "PROVIDER_ERROR",
                reject_reasons,
                partial_artifacts=artifact_records,
            )

        voice_slot["live_tts_progress"] = progress
        runtime = self._persist_voice_slot(
            session, runtime, voice_slot, provider_mode=effective_mode
        )
        audit = self._append_audit(
            session,
            runtime,
            actor=triggered_by,
            reason=reason,
            allowed=True,
            execution_status=execution_status,
            blocked_reasons=reject_reasons,
            voice_slot=voice_slot,
            tts_executed=tts_executed,
            provider_mode=effective_mode,
            real_provider_called=real_provider_called,
        )
        session["execution_runtime"] = runtime
        session["updated_at"] = _utc_now()
        self.store.save_session(session, overwrite=True)

        video_after = self._video_slot_snapshot(session)
        video_mutated = not self._video_slot_preserved(video_before, video_after)
        if video_mutated:
            raise RuntimeError("Video generation slot critical fields were mutated — aborting.")

        success = execution_status == STATUS_COMPLETED and tts_executed
        completion_msg = (
            "Live voice TTS completed." if effective_mode == PROVIDER_MODE_LIVE else "Mock live voice TTS completed."
        )
        return LiveVoiceTtsRunResult(
            success=success,
            session_id=session_id,
            status=execution_status,
            message=completion_msg if success else "Voice TTS did not complete.",
            code=result_code,
            reject_reasons=reject_reasons,
            voice_slot=voice_slot,
            guard_result=policy.guard_result,
            manifest_path=str(manifest_path.resolve()) if manifest and manifest_path.is_file() else None,
            manifest=manifest,
            artifacts=artifact_records,
            provider_mode=effective_mode,
            tts_executed=tts_executed,
            real_provider_called=real_provider_called,
            video_mutated=video_mutated,
            panel_excerpt=self._panel_excerpt(voice_slot, runtime, effective_mode),
            audit_event=audit,
        )

    def _prepare_context(
        self,
        session: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        runtime = dict(_dict(session.get("execution_runtime")))
        runtime = ensure_multi_category_shell(runtime)
        runtime = apply_voice_preflight_dry_run(session, runtime, project_root=self.project_root)
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
        video_before = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
        session["execution_runtime"] = runtime
        return runtime, voice_slot, video_before

    def _persist_voice_slot(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        voice_slot: dict[str, Any],
        *,
        provider_mode: str = PROVIDER_MODE_MOCK,
    ) -> dict[str, Any]:
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
        category_runtime[CATEGORY_VOICE] = voice_slot
        category_runtime[CATEGORY_VIDEO] = video_slot
        runtime["category_runtime"] = category_runtime

        operations = dict(_dict(runtime.get("operations")))
        progress = _dict(voice_slot.get("live_tts_progress"))
        operations["voice_tts_execution"] = {
            "engine_version": ENGINE_VERSION,
            "provider_mode": provider_mode,
            "last_status": voice_slot.get("status"),
            "last_run_at": progress.get("started_at"),
            "segment_count": progress.get("total_segments"),
            "tts_executed": bool(voice_slot.get("live_tts_executed")),
            "real_provider_called": bool(progress.get("real_provider_called")),
        }
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return runtime

    def _set_running(
        self,
        voice_slot: dict[str, Any],
        artifact_root: Path,
        total_segments: int,
        started_at: str,
        *,
        provider_mode: str = PROVIDER_MODE_MOCK,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        is_live = provider_mode == PROVIDER_MODE_LIVE
        slot["status"] = STATUS_RUNNING
        slot["state"] = STATUS_RUNNING
        slot["executed"] = False
        slot["dry_run"] = False
        slot["live_tts"] = is_live
        slot["live_tts_executed"] = False
        slot["provider"] = "elevenlabs" if is_live else MOCK_PROVIDER_ID
        slot["artifact_root"] = str(artifact_root.resolve())
        slot["artifacts"] = []
        slot["voice_manifest_path"] = None
        slot["error"] = None
        slot["live_tts_progress"] = {
            "engine_version": ENGINE_VERSION,
            "provider_mode": provider_mode,
            "current_segment": 0,
            "total_segments": total_segments,
            "progress_percent": 0,
            "last_error": None,
            "retry_count": 0,
            "real_provider_called": False,
            "started_at": started_at,
            "completed_at": None,
            "duration_seconds": None,
            "cancelled_at": None,
            "partial_artifact_count": 0,
        }
        return slot

    def _set_completed(
        self,
        voice_slot: dict[str, Any],
        artifacts: list[dict[str, Any]],
        manifest_path: str,
        manifest: dict[str, Any],
        progress: dict[str, Any],
        started_at: str,
        completed_at: str,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        slot["status"] = STATUS_COMPLETED
        slot["state"] = STATUS_COMPLETED
        slot["executed"] = True
        slot["dry_run"] = False
        slot["live_tts"] = True
        slot["live_tts_executed"] = True
        slot["artifacts"] = artifacts
        slot["voice_manifest_path"] = manifest_path
        slot["started_at"] = started_at
        slot["completed_at"] = completed_at
        slot["error"] = None
        progress["progress_percent"] = 100
        progress["completed_at"] = completed_at
        progress["duration_seconds"] = _duration_seconds(started_at, completed_at)
        progress["real_provider_called"] = bool(manifest.get("real_provider_called"))
        slot["live_tts_progress"] = progress
        slot["voice_manifest"] = {"validation_status": manifest.get("validation_status"), "path": manifest_path}
        return slot

    def _set_failed(
        self,
        voice_slot: dict[str, Any],
        progress: dict[str, Any],
        code: str,
        reasons: list[str],
        *,
        partial_artifacts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        slot["status"] = STATUS_FAILED
        slot["state"] = STATUS_FAILED
        slot["executed"] = False
        slot["dry_run"] = False
        slot["live_tts"] = False
        slot["live_tts_executed"] = False
        if partial_artifacts:
            slot["artifacts"] = partial_artifacts
        slot["error"] = {
            "code": code,
            "message": reasons[0] if reasons else "Voice TTS run failed.",
            "category": "RUNTIME_ERROR",
        }
        slot["live_tts_progress"] = progress
        return slot

    def _set_cancelled(
        self,
        voice_slot: dict[str, Any],
        progress: dict[str, Any],
        code: str,
        reasons: list[str],
        partial_artifacts: list[dict[str, Any]],
        manifest_path: str | None,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        slot["status"] = STATUS_CANCELLED
        slot["state"] = STATUS_CANCELLED
        slot["executed"] = False
        slot["dry_run"] = False
        slot["live_tts"] = False
        slot["live_tts_executed"] = False
        slot["artifacts"] = partial_artifacts
        if manifest_path:
            slot["voice_manifest_path"] = manifest_path
        slot["error"] = {
            "code": code,
            "message": reasons[0] if reasons else "Voice TTS run cancelled.",
            "category": "OPERATIONS",
        }
        slot["live_tts_progress"] = progress
        return slot

    def _build_manifest(
        self,
        *,
        session_id: str,
        session: dict[str, Any],
        segments: list[Any],
        artifact_records: list[dict[str, Any]],
        started_at: str,
        completed_at: str,
        validation_status: str,
        execution_status: str,
        partial: bool,
        character_count: int,
        provider_mode: str = PROVIDER_MODE_MOCK,
        total_retry_count: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        files = []
        for record in artifact_records:
            files.append(
                {
                    "segment_index": record.get("segment_index"),
                    "file_name": record.get("file_name"),
                    "file_path": record.get("file_path"),
                    "size_bytes": record.get("size_bytes"),
                    "character_count": record.get("character_count"),
                    "text_hash": record.get("text_hash"),
                    "beat_id": record.get("beat_id"),
                    "validation_status": record.get("validation_status", "valid"),
                    "request_id": record.get("request_id"),
                    "retry_count": record.get("retry_count", 0),
                }
            )

        is_live = provider_mode == PROVIDER_MODE_LIVE
        manifest: dict[str, Any] = {
            "manifest_version": MANIFEST_VERSION_LIVE if is_live else MANIFEST_VERSION_MOCK,
            "session_id": session_id,
            "category": CATEGORY_VOICE,
            "provider": "elevenlabs" if is_live else MOCK_PROVIDER_ID,
            "provider_mode": provider_mode if is_live else MOCK_PROVIDER_MODE,
            "segment_count": len(files),
            "character_count": character_count,
            "total_size_bytes": sum(int(f.get("size_bytes") or 0) for f in files),
            "files": files,
            "created_at": completed_at,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": _duration_seconds(started_at, completed_at),
            "validation_status": validation_status,
            "execution_status": execution_status,
            "partial": partial,
            "tts_executed": execution_status == STATUS_COMPLETED and validation_status == "valid",
            "real_provider_called": is_live,
            "engine_version": ENGINE_VERSION,
        }

        if is_live:
            config = ElevenLabsConfigResolver(self.project_root).resolve(session)
            manifest.update(
                build_live_manifest_extras(
                    config,
                    total_retry_count=total_retry_count,
                    request_id=request_id,
                    use_smoke_profile=True,
                )
            )
        else:
            manifest["real_provider_called"] = False

        return manifest

    def _append_audit(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        *,
        actor: str,
        reason: str,
        allowed: bool,
        execution_status: str,
        blocked_reasons: list[str],
        voice_slot: dict[str, Any],
        tts_executed: bool = False,
        provider_mode: str = PROVIDER_MODE_MOCK,
        real_provider_called: bool = False,
    ) -> dict[str, Any]:
        session_id = ExecutionSessionStore.extract_session_id(session)
        progress = _dict(voice_slot.get("live_tts_progress"))
        event = {
            "event_id": generate_voice_tts_audit_event_id(),
            "event_type": "run_voice_tts",
            "session_id": session_id,
            "category": CATEGORY_VOICE,
            "actor": actor or "local_user",
            "reason": reason,
            "timestamp": _utc_now(),
            "execution_status": execution_status,
            "blocked_reasons": list(blocked_reasons),
            "provider_mode": provider_mode,
            "tts_executed": tts_executed,
            "real_provider_called": real_provider_called,
            "allowed": allowed,
            "metadata": {
                "engine_version": ENGINE_VERSION,
                "progress_percent": progress.get("progress_percent"),
                "segment_count": progress.get("total_segments"),
            },
        }
        operations = dict(_dict(runtime.get("operations")))
        audit_log = list(operations.get("voice_tts_audit") or [])
        audit_log.append(event)
        if len(audit_log) > 50:
            audit_log = audit_log[-50:]
        operations["voice_tts_audit"] = audit_log
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return event

    @staticmethod
    def _video_slot_snapshot(session: dict[str, Any]) -> dict[str, Any]:
        runtime = _dict(session.get("execution_runtime"))
        return dict(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO)))

    @staticmethod
    def _video_slot_preserved(before: dict[str, Any], after: dict[str, Any]) -> bool:
        keys = ("state", "provider", "started_at", "completed_at")
        return all(before.get(key) == after.get(key) for key in keys)

    @staticmethod
    def _panel_excerpt(
        voice_slot: dict[str, Any],
        runtime: dict[str, Any],
        provider_mode: str = PROVIDER_MODE_MOCK,
    ) -> dict[str, Any]:
        progress = _dict(voice_slot.get("live_tts_progress"))
        return {
            "voice_generation_status": voice_slot.get("status"),
            "voice_generation_executed": voice_slot.get("executed"),
            "live_tts_executed": voice_slot.get("live_tts_executed"),
            "provider_mode": provider_mode,
            "progress_percent": progress.get("progress_percent"),
            "voice_tts_execution": _dict(runtime.get("operations")).get("voice_tts_execution"),
        }


__all__ = [
    "ENGINE_VERSION",
    "MANIFEST_VERSION_MOCK",
    "MANIFEST_VERSION_LIVE",
    "LiveVoiceTtsEngine",
    "LiveVoiceTtsRunResult",
    "generate_voice_tts_audit_event_id",
]
