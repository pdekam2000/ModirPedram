"""Phase 12D — UAT runtime engine (shared CLI + API pipeline)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from content_brain.execution.approval_budget_governance_engine import (
    ApprovalBudgetGovernanceEngine,
    GovernancePolicy,
)
from content_brain.execution.assembly_approval_operations_engine import AssemblyApprovalOperationsEngine
from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability
from content_brain.execution.assembly_models import EXPECTED_OUTPUT
from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.execution_readiness_gate import ExecutionReadinessGate
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine, RuntimePolicy
from content_brain.execution.session_population_builder import SessionPopulationBuilder
from content_brain.execution.session_prompt_adapter import SessionPromptAdapter
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.simulation_report_builder import SimulationReportBuilder
from content_brain.execution.uat_runtime_profile import (
    UAT_ASSEMBLY_TIMEOUT_SECONDS,
    UAT_MAX_ASSEMBLY_OUTPUT_BYTES,
    UAT_MAX_VIDEO_CLIPS,
    UAT_MAX_VOICE_SEGMENTS,
    UAT_SESSION_PREFIX,
    UAT_TRIGGER,
    UatRuntimeConfig,
    apply_live_voice_smoke_duration_guard,
    build_uat_operations_block,
    generate_uat_session_id,
    uat_routing_snapshot,
)
from content_brain.execution.uat_real_video_bridge import (
    uat_log,
    uat_runway_queue_and_dispatch_prepare,
    uat_supervised_real_runway_requested,
    validate_runway_browser_operator_ready,
)
from content_brain.execution.uat_smoke_narration_adapter import apply_uat_smoke_narration_session
from content_brain.execution.voice_approval_operations_engine import VoiceApprovalOperationsEngine
from content_brain.execution.voice_live_tts_action_policy import PROVIDER_MODE_LIVE, PROVIDER_MODE_MOCK
from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run
from content_brain.orchestrators.content_brief_orchestrator import (
    ContentBriefOrchestrator,
    ContentBriefRunRequest,
)
from content_brain.schemas.content_brief import Platform
from ui.api.assembly_run_service import AssemblyRunService
from ui.api.subtitle_run_service import SubtitleRunService
from ui.api.voice_run_service import VoiceRunService

REASON = "12B supervised UAT pipeline"
REVIEW_VERSION = "12d_v1"
UAT_STAGES = ("content_brain", "video", "voice", "subtitle", "assembly", "final_mp4")

_PLATFORM_ENUM: dict[str, Platform] = {
    "tiktok": Platform.TIKTOK,
    "youtube_shorts": Platform.YOUTUBE_SHORTS,
    "instagram_reels": Platform.INSTAGRAM_REELS,
}


def _reviews_dir(project_root: Path) -> Path:
    return project_root / "project_brain" / "user_acceptance_reviews"


def _uat_runs_dir(project_root: Path) -> Path:
    return project_root / "project_brain" / "uat_runs"


class UatRunAlreadyActiveError(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"UAT run already active: {session_id}")


class UatReviewAlreadySubmittedError(Exception):
    pass


@dataclass
class UatReviewSubmission:
    story_quality_score: int
    visual_quality_score: int
    voice_quality_score: int
    subtitle_quality_score: int
    continuity_score: int
    overall_quality_score: int
    comments: str = ""
    publishable: bool = False
    submitted_by: str = UAT_TRIGGER


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _pipeline_session(session: dict[str, Any]) -> dict[str, Any]:
    session = SimulationReportBuilder().enrich_session(session)
    session = ApprovalBudgetGovernanceEngine().enrich_session(session, policy=GovernancePolicy())
    return ExecutionReadinessGate().enrich_session(session)


def _clarify_voice_smoke_error(message: str | None) -> str:
    msg = str(message or "").strip()
    if "Smoke segment count exceeds cap" in msg:
        return (
            f"{msg} This is an 11H-2d live-voice smoke safety limit (max 1 segment), "
            "not a Content Brain failure. For live voice UAT, duration is auto-reduced "
            "before planning; if this persists, use mock voice or lower duration."
        )
    return msg or "Voice stage failed."


def _resolve_platform(platform: str) -> Platform:
    return _PLATFORM_ENUM.get(platform, Platform.YOUTUBE_SHORTS)


def _attach_uat_metadata(session: dict[str, Any], config: UatRuntimeConfig, session_id: str) -> dict[str, Any]:
    runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
    operations = dict(_dict(runtime.get("operations")))
    operations.update(build_uat_operations_block(config, session_id))
    uat_block = dict(_dict(operations.get("uat_run")))
    uat_block.setdefault("progress_log", [])
    uat_block.setdefault("stages", {})
    uat_block["current_stage"] = "content_brain"
    uat_block["started_at"] = _now()
    operations["uat_run"] = uat_block
    runtime["operations"] = operations
    session["execution_session_id"] = session_id
    session["execution_runtime"] = runtime
    session["updated_at"] = _now()
    return session


def _update_uat_progress(
    store: ExecutionSessionStore,
    session_id: str,
    *,
    stage: str,
    message: str,
    level: str = "info",
    stage_result: dict[str, Any] | None = None,
    status: str | None = None,
) -> None:
    session = store.load_session(session_id)
    runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
    operations = dict(_dict(runtime.get("operations")))
    uat_block = dict(_dict(operations.get("uat_run")))
    uat_block["current_stage"] = stage
    log = list(uat_block.get("progress_log") or [])
    log.append({"timestamp": _now(), "stage": stage, "level": level, "message": message})
    uat_block["progress_log"] = log
    if stage_result is not None:
        stages = dict(_dict(uat_block.get("stages")))
        stages[stage] = stage_result
        uat_block["stages"] = stages
    if status is not None:
        uat_block["status"] = status
    operations["uat_run"] = uat_block
    runtime["operations"] = operations
    session["execution_runtime"] = runtime
    session["updated_at"] = _now()
    store.save_session(session, overwrite=True)


def _mark_uat_failed(store: ExecutionSessionStore, session_id: str, error: str) -> None:
    session = store.load_session(session_id)
    runtime = dict(_dict(session.get("execution_runtime")))
    operations = dict(_dict(runtime.get("operations")))
    uat_block = dict(_dict(operations.get("uat_run")))
    failed_stage = uat_block.get("current_stage")

    _update_uat_progress(
        store,
        session_id,
        stage="failed",
        message=error,
        level="error",
        status="failed",
    )
    session = store.load_session(session_id)
    runtime = dict(_dict(session.get("execution_runtime")))
    operations = dict(_dict(runtime.get("operations")))
    uat_block = dict(_dict(operations.get("uat_run")))
    if failed_stage and failed_stage != "failed":
        uat_block["failed_stage"] = failed_stage
    runtime = dict(_dict(session.get("execution_runtime")))
    operations = dict(_dict(runtime.get("operations")))
    uat_block = dict(_dict(operations.get("uat_run")))
    errors = list(uat_block.get("errors") or [])
    errors.append(error)
    uat_block["errors"] = errors
    uat_block["completed_at"] = _now()
    operations["uat_run"] = uat_block
    runtime["operations"] = operations
    session["execution_runtime"] = runtime
    store.save_session(session, overwrite=True)


def _ffmpeg_generate_clip(path: Path, *, duration: int, color: str, ffmpeg_bin: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=640x360:d={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-t",
            str(duration),
            str(path),
        ],
        check=True,
        timeout=120,
    )


def _resolve_ffmpeg_bin() -> str | None:
    probe = check_ffmpeg_availability()
    return probe.ffmpeg_path if probe.available else None


def _apply_mock_video_artifacts(
    store: ExecutionSessionStore,
    session_id: str,
    *,
    clip_count: int,
    provider: str,
    clip_seconds: int = 4,
) -> dict[str, Any]:
    ffmpeg_bin = _resolve_ffmpeg_bin()
    if not ffmpeg_bin:
        raise RuntimeError("Mock video generation requires FFmpeg on PATH.")

    video_dir = store.artifact_dir(session_id, CATEGORY_VIDEO)
    clip_paths: list[str] = []
    colors = ("0x224488", "0x442288", "0x228844", "0x884422", "0x448822", "0x662244")
    for index in range(1, min(clip_count, UAT_MAX_VIDEO_CLIPS) + 1):
        path = video_dir / f"clip_{index:03d}.mp4"
        _ffmpeg_generate_clip(path, duration=clip_seconds, color=colors[(index - 1) % len(colors)], ffmpeg_bin=ffmpeg_bin)
        clip_paths.append(str(path.resolve()))

    manifest = {"clips": [{"file_path": p, "clip_number": i + 1} for i, p in enumerate(clip_paths)]}
    manifest_path = video_dir / "video_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    session = store.load_session(session_id)
    runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
    artifacts = [
        {
            "artifact_id": f"art_{uuid.uuid4().hex[:12]}",
            "provider_category": CATEGORY_VIDEO,
            "artifact_type": "video_clip",
            "provider": provider,
            "file_path": path,
            "clip_number": idx,
            "metadata": {"uat_mock": True},
        }
        for idx, path in enumerate(clip_paths, start=1)
    ]
    runtime["artifacts_by_category"] = dict(_dict(runtime.get("artifacts_by_category")))
    runtime["artifacts_by_category"][CATEGORY_VIDEO] = artifacts
    cr = dict(_dict(runtime.get("category_runtime")))
    ts = _now()
    video_slot = dict(_dict(cr.get(CATEGORY_VIDEO)))
    video_slot.update(
        {
            "state": "COMPLETED",
            "status": "completed",
            "provider": provider,
            "executed": True,
            "started_at": ts,
            "completed_at": ts,
            "artifact_count": len(artifacts),
            "video_manifest_path": str(manifest_path.resolve()),
        }
    )
    cr[CATEGORY_VIDEO] = video_slot
    runtime["category_runtime"] = cr
    session["execution_runtime"] = runtime
    session["updated_at"] = ts
    store.save_session(session, overwrite=True)
    return {"clip_count": len(clip_paths), "clip_paths": clip_paths, "manifest_path": str(manifest_path.resolve())}


def _run_video_stage(
    store: ExecutionSessionStore,
    session_id: str,
    config: UatRuntimeConfig,
    *,
    mock_paid_providers: bool,
) -> dict[str, Any]:
    session = store.load_session(session_id)
    clip_count = int(
        _dict(_dict(session.get("brief_snapshot")).get("video_format_plan")).get("clip_count") or 1
    )
    clip_count = max(1, min(clip_count, UAT_MAX_VIDEO_CLIPS))

    supervised_runway = uat_supervised_real_runway_requested(config, mock_paid_providers=mock_paid_providers)

    if mock_paid_providers or config.video_provider == "mock":
        info = _apply_mock_video_artifacts(
            store, session_id, clip_count=clip_count, provider=config.video_provider
        )
        return {
            "success": True,
            "video_provider_mode": "mock",
            "message": "Mock video clips generated via FFmpeg lavfi.",
            **info,
        }

    if supervised_runway:
        validate_runway_browser_operator_ready(store.project_root)
        uat_log(
            "UAT_REAL_VIDEO",
            session_id=session_id,
            provider=config.video_provider,
            confirm_real_video=True,
        )
        uat_runway_queue_and_dispatch_prepare(store, session_id)

    if config.video_provider not in {"runway_browser", "hailuo_browser", "runway", "hailuo"}:
        if supervised_runway:
            uat_log(
                "UAT_PLACEHOLDER_BLOCKED",
                session_id=session_id,
                reason=f"unsupported_provider_{config.video_provider}",
            )
            raise RuntimeError(f"Unsupported video provider for supervised real UAT: {config.video_provider!r}")
        info = _apply_mock_video_artifacts(
            store, session_id, clip_count=clip_count, provider=config.video_provider
        )
        return {
            "success": True,
            "video_provider_mode": "mock",
            "message": f"Unsupported video provider {config.video_provider!r}; mock fallback.",
            **info,
        }

    engine = ProviderRuntimeEngine(store)
    policy = RuntimePolicy(skip_provider_execution=False, max_clips_cap=UAT_MAX_VIDEO_CLIPS)
    uat_log("UAT_RUNWAY_EXECUTION", session_id=session_id, dispatch_started=True, router_selected="VideoProviderRouter")
    dispatch = engine.dispatch_by_id(session_id, actor=UAT_TRIGGER, policy=policy)
    if dispatch.success:
        uat_log(
            "UAT_RUNWAY_EXECUTION",
            session_id=session_id,
            provider_selected=config.video_provider,
            dispatch_success=True,
        )
        return {
            "success": True,
            "video_provider_mode": "real",
            "message": "Video provider dispatch completed.",
            "dispatch_reject_code": None,
            "queue_bridge": supervised_runway,
        }

    reject_code = dispatch.reject_code or "DISPATCH_FAILED"
    reject_reasons = "; ".join(dispatch.reject_reasons or [])
    if supervised_runway:
        uat_log(
            "UAT_PLACEHOLDER_BLOCKED",
            session_id=session_id,
            reason=reject_code,
            detail=reject_reasons or "dispatch_failed",
        )
        raise RuntimeError(
            f"Real Runway video dispatch failed ({reject_code}): "
            f"{reject_reasons or 'no additional detail'}"
        )

    info = _apply_mock_video_artifacts(
        store, session_id, clip_count=clip_count, provider=config.video_provider
    )
    return {
        "success": True,
        "video_provider_mode": "mock",
        "message": f"Real video dispatch failed ({reject_code}); mock fallback used.",
        "dispatch_reject_code": reject_code,
        **info,
    }


def _run_voice_stage(
    store: ExecutionSessionStore,
    session_id: str,
    config: UatRuntimeConfig,
    *,
    mock_paid_providers: bool,
) -> dict[str, Any]:
    voice_mock = mock_paid_providers or config.voice_provider == "mock"
    use_live = (
        not voice_mock
        and config.confirm_real_voice
        and config.voice_provider == "elevenlabs"
    )

    if use_live:
        smoke_narration_meta = apply_uat_smoke_narration_session(store, session_id, config)
        if smoke_narration_meta and smoke_narration_meta.get("applied"):
            _update_uat_progress(
                store,
                session_id,
                stage="voice",
                level="warning",
                message=(
                    "Live voice smoke narration merged: "
                    f"{smoke_narration_meta.get('original_narration_segment_count')} → "
                    f"{smoke_narration_meta.get('smoke_narration_segment_count')} segment(s)."
                ),
            )

    session = store.load_session(session_id)
    runtime = apply_voice_preflight_dry_run(
        session,
        ensure_multi_category_shell(session.get("execution_runtime") or {}),
        project_root=store.project_root,
    )
    session["execution_runtime"] = runtime
    store.save_session(session, overwrite=True)

    voice_slot = dict(
        _dict(_dict(_dict(session.get("execution_runtime")).get("category_runtime")).get(CATEGORY_VOICE))
    )
    voice_status = str(voice_slot.get("status") or voice_slot.get("state") or "").lower()
    if voice_status == "completed" and voice_slot.get("executed") and not use_live:
        return {
            "success": True,
            "voice_provider_mode": "mock",
            "real_provider_called": False,
            "tts_executed": True,
            "code": None,
            "message": "Voice already completed; mock path retained (no live re-run).",
        }

    if use_live and not config.confirm_real_voice:
        return {
            "success": False,
            "voice_provider_mode": "blocked",
            "code": "VOICE_REAL_EXECUTION_NOT_CONFIRMED",
            "message": "Live voice requires --confirm-real-voice.",
        }

    service = VoiceRunService(store)
    if use_live:
        approval_engine = VoiceApprovalOperationsEngine(store, project_root=store.project_root)
        approval = approval_engine.approve(
            session_id,
            request_live_tts=True,
            approved_by=UAT_TRIGGER,
            reason=REASON,
            ttl_minutes=60,
        )
        if not approval.success:
            return {
                "success": False,
                "voice_provider_mode": "blocked",
                "code": approval.code,
                "message": f"Voice approval failed: {approval.reject_reasons}",
            }

        import content_brain.execution.voice_live_tts_action_policy as policy_module

        try:
            os.environ["MODIR_VOICE_LIVE_TTS_ENABLED"] = "true"
            with patch.object(policy_module, "LIVE_RUNTIME_EXECUTION_APPROVED", True):
                result = service.run(
                    session_id,
                    triggered_by=UAT_TRIGGER,
                    reason=REASON,
                    provider_mode=PROVIDER_MODE_LIVE,
                    confirm_live_tts=True,
                )
        finally:
            os.environ.pop("MODIR_VOICE_LIVE_TTS_ENABLED", None)

        if result.get("success"):
            _sync_voice_artifacts_catalog(store, session_id)
        message = _clarify_voice_smoke_error(result.get("message"))
        return {
            "success": bool(result.get("success")),
            "voice_provider_mode": "real",
            "real_provider_called": result.get("real_provider_called"),
            "tts_executed": result.get("tts_executed"),
            "code": result.get("code"),
            "message": message,
        }

    # Mock TTS still requires approval + live_tts_requested (voice_live_tts_action_policy).
    approval_engine = VoiceApprovalOperationsEngine(store, project_root=store.project_root)
    approval = approval_engine.approve(
        session_id,
        request_live_tts=True,
        approved_by=UAT_TRIGGER,
        reason=REASON,
        ttl_minutes=60,
    )
    if not approval.success:
        return {
            "success": False,
            "voice_provider_mode": "mock_blocked",
            "code": approval.code,
            "message": f"Voice approval for mock TTS failed: {approval.reject_reasons}",
        }

    result = service.run(
        session_id,
        triggered_by=UAT_TRIGGER,
        reason=REASON,
        provider_mode=PROVIDER_MODE_MOCK,
        confirm_live_tts=False,
    )
    if result.get("success"):
        _patch_mock_voice_manifest_timing(store, session_id, config.duration_seconds)
        _sync_voice_artifacts_catalog(store, session_id)
    return {
        "success": bool(result.get("success")),
        "voice_provider_mode": "mock",
        "real_provider_called": False,
        "tts_executed": result.get("tts_executed"),
        "code": result.get("code"),
        "message": result.get("message"),
    }


def _patch_mock_voice_manifest_timing(
    store: ExecutionSessionStore,
    session_id: str,
    target_duration_seconds: float,
) -> None:
    """Mock TTS wall-clock duration is ~0; restore usable timing for subtitle cues."""
    manifest_path = store.artifact_dir(session_id, CATEGORY_VOICE) / "voice_manifest.json"
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if str(manifest.get("provider_mode") or "").lower() != "mock":
        return
    try:
        current = float(manifest.get("duration_seconds") or 0)
    except (TypeError, ValueError):
        current = 0.0
    if current >= 1.0:
        return

    files = [_dict(item) for item in (manifest.get("files") or [])]
    char_total = sum(int(f.get("character_count") or 0) for f in files) or 1
    effective_total = max(float(target_duration_seconds), 15.0)
    manifest["duration_seconds"] = round(effective_total, 3)

    updated_files: list[dict[str, Any]] = []
    for file_rec in files:
        rec = dict(file_rec)
        share = int(rec.get("character_count") or 1) / char_total
        rec["duration_seconds"] = round(max(1.0, effective_total * share), 3)
        updated_files.append(rec)
    manifest["files"] = updated_files
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    session = store.load_session(session_id)
    runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
    category_runtime = dict(_dict(runtime.get("category_runtime")))
    voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
    voice_slot["duration_seconds"] = manifest["duration_seconds"]
    voice_slot["voice_manifest_path"] = str(manifest_path.resolve())
    category_runtime[CATEGORY_VOICE] = voice_slot
    runtime["category_runtime"] = category_runtime
    session["execution_runtime"] = runtime
    store.save_session(session, overwrite=True)


def _sync_voice_artifacts_catalog(store: ExecutionSessionStore, session_id: str) -> None:
    """Mirror voice slot artifacts into artifacts_by_category for assembly planning."""
    session = store.load_session(session_id)
    runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
    voice_slot = dict(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VOICE)))
    artifacts = list(voice_slot.get("artifacts") or [])
    if not artifacts:
        return
    by_category = dict(_dict(runtime.get("artifacts_by_category")))
    by_category[CATEGORY_VOICE] = artifacts
    runtime["artifacts_by_category"] = by_category
    session["execution_runtime"] = runtime
    store.save_session(session, overwrite=True)


def _relax_narration_timing_for_subtitles(store: ExecutionSessionStore, session_id: str) -> None:
    """Remove tight beat-plan windows so subtitle cues distribute across target duration."""
    session = store.load_session(session_id)
    brief = dict(_dict(session.get("brief_snapshot")))
    mutated = False

    run_context = dict(_dict(brief.get("run_context")))
    story_intelligence = dict(_dict(run_context.get("story_intelligence")))
    story_architecture = dict(_dict(story_intelligence.get("story_architecture")))
    beat_plans = story_architecture.get("beat_plans")
    if isinstance(beat_plans, list):
        updated: list[dict[str, Any]] = []
        for raw in beat_plans:
            item = dict(_dict(raw))
            if "start_second" in item or "end_second" in item:
                item.pop("start_second", None)
                item.pop("end_second", None)
                mutated = True
            updated.append(item)
        story_architecture["beat_plans"] = updated
        story_intelligence["story_architecture"] = story_architecture
        run_context["story_intelligence"] = story_intelligence
        brief["run_context"] = run_context

    blueprint = dict(_dict(brief.get("story_blueprint")))
    beats = blueprint.get("beats")
    if isinstance(beats, list):
        updated_beats: list[dict[str, Any]] = []
        for raw in beats:
            item = dict(_dict(raw))
            if "start_second" in item or "end_second" in item:
                item.pop("start_second", None)
                item.pop("end_second", None)
                mutated = True
            updated_beats.append(item)
        blueprint["beats"] = updated_beats
        brief["story_blueprint"] = blueprint

    if mutated:
        session["brief_snapshot"] = brief
        store.save_session(session, overwrite=True)


def _run_subtitle_stage(
    store: ExecutionSessionStore,
    session_id: str,
    *,
    timing_strategy: str = "auto",
) -> dict[str, Any]:
    service = SubtitleRunService(store)
    result = service.run(
        session_id,
        formats=["srt", "ass", "vtt"],
        timing_strategy=timing_strategy,
        triggered_by=UAT_TRIGGER,
    )
    return {
        "success": bool(result.get("success")),
        "formats_written": list(result.get("formats_written") or []),
        "manifest_path": result.get("manifest_path"),
        "cue_count": result.get("cue_count"),
        "code": result.get("code"),
        "message": result.get("message"),
    }


def _run_assembly_stage(
    store: ExecutionSessionStore,
    session_id: str,
    config: UatRuntimeConfig,
    *,
    mock_paid_providers: bool,
    mock_assembly_executor: bool = False,
    allow_mock_assembly_fallback: bool = False,
) -> dict[str, Any]:
    service = AssemblyRunService(store)
    dry = service.run(session_id, dry_run=True, triggered_by=UAT_TRIGGER, reason=REASON)
    if not dry.get("success"):
        return {
            "success": False,
            "assembly_mode": "dry_run_failed",
            "code": dry.get("code"),
            "message": dry.get("message"),
        }

    if (
        not config.confirm_real_assembly
        and not mock_paid_providers
        and not allow_mock_assembly_fallback
        and not mock_assembly_executor
    ):
        return {
            "success": False,
            "assembly_mode": "blocked",
            "code": "ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED",
            "message": "Real assembly requires --confirm-real-assembly.",
            "dry_run": dry,
        }

    use_mock_assembly = mock_assembly_executor or (
        not config.confirm_real_assembly and (mock_paid_providers or allow_mock_assembly_fallback)
    )
    if use_mock_assembly:
        output_dir = (
            Path(store.project_root)
            / "storage"
            / "content_brain"
            / "execution"
            / "artifacts"
            / session_id
            / CATEGORY_ASSEMBLY_GENERATION
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        final_path = output_dir / EXPECTED_OUTPUT
        final_path.write_bytes(b"\x00\x00\x00\x1cftypmp42" + b"\x00" * 128)
        manifest_path = output_dir / "assembly_manifest.json"
        manifest_path.write_text(
            json.dumps({"real_assembly_executed": False, "uat_mock_assembly": True}),
            encoding="utf-8",
        )
        return {
            "success": True,
            "assembly_mode": "mock",
            "final_video_path": str(final_path.resolve()),
            "manifest_path": str(manifest_path.resolve()),
            "real_assembly_executed": False,
        }

    if not config.confirm_real_assembly:
        return {
            "success": False,
            "assembly_mode": "blocked",
            "code": "ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED",
            "message": "Real assembly requires --confirm-real-assembly.",
        }

    ffmpeg = check_ffmpeg_availability()
    if not ffmpeg.available:
        return {
            "success": False,
            "assembly_mode": "blocked",
            "code": "ASSEMBLY_FFMPEG_FAILED",
            "message": ffmpeg.error or "FFmpeg not available.",
        }

    approval_engine = AssemblyApprovalOperationsEngine(store, project_root=store.project_root)
    approval = approval_engine.approve(
        session_id,
        request_real_assembly=True,
        approved_by=UAT_TRIGGER,
        reason=REASON,
        ttl_minutes=60,
    )
    if not approval.success:
        return {
            "success": False,
            "assembly_mode": "blocked",
            "code": approval.code,
            "message": f"Assembly approval failed: {approval.reject_reasons}",
        }

    try:
        os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = "true"
        os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = "true"
        result = service.run(
            session_id,
            dry_run=False,
            confirm_real_assembly=True,
            triggered_by=UAT_TRIGGER,
            reason=REASON,
            overwrite=False,
            timeout_seconds=UAT_ASSEMBLY_TIMEOUT_SECONDS,
            max_output_bytes=UAT_MAX_ASSEMBLY_OUTPUT_BYTES,
        )
    finally:
        os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
        os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)

    assembly_dir = store.artifact_dir(session_id, CATEGORY_ASSEMBLY_GENERATION)
    final_path = assembly_dir / EXPECTED_OUTPUT
    return {
        "success": bool(result.get("success")),
        "assembly_mode": "real" if result.get("real_assembly_executed") else "failed",
        "real_assembly_executed": result.get("real_assembly_executed"),
        "output_created": result.get("output_created"),
        "final_video_path": str(final_path.resolve()) if final_path.is_file() else None,
        "manifest_path": str((assembly_dir / "assembly_manifest.json").resolve())
        if (assembly_dir / "assembly_manifest.json").is_file()
        else None,
        "code": result.get("code"),
        "message": result.get("message"),
    }


def _write_review_template(
    session_id: str,
    config: UatRuntimeConfig,
    artifact_folder: str,
    final_video_path: str | None,
    *,
    project_root: Path,
) -> Path:
    reviews_dir = _reviews_dir(project_root)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    path = reviews_dir / f"{session_id}_review_template.json"
    payload = {
        "review_version": REVIEW_VERSION,
        "session_id": session_id,
        "submitted_at": None,
        "submitted_by": None,
        "uat_inputs": {
            "topic": config.topic,
            "platform": config.platform,
            "target_duration_seconds": config.duration_seconds,
            "video_provider": config.video_provider,
            "voice_provider": config.voice_provider,
        },
        "artifact_paths": {
            "artifact_folder": artifact_folder,
            "final_video": final_video_path,
        },
        "story_quality_score": None,
        "visual_quality_score": None,
        "voice_quality_score": None,
        "subtitle_quality_score": None,
        "continuity_score": None,
        "overall_quality_score": None,
        "comments": {
            "felt_good": "",
            "felt_wrong": "",
            "should_improve": "",
        },
        "publishable": None,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_uat_report(session_id: str, data: dict[str, Any], *, project_root: Path) -> Path:
    uat_dir = _uat_runs_dir(project_root)
    uat_dir.mkdir(parents=True, exist_ok=True)
    path = uat_dir / f"{session_id}_uat_report.md"
    config = data.get("config") or {}
    stages = data.get("stages") or {}
    lines = [
        f"# UAT Run Report — `{session_id}`",
        "",
        f"**Date:** {data.get('timestamp')}",
        f"**Status:** {'PASS' if data.get('success') else 'FAIL'}",
        "",
        "## Runtime routing",
        "",
    ]
    routing = data.get("routing") or {}
    if routing:
        lines.extend(
            [
                f"- **Runtime:** `{routing.get('runtime_name')}`",
                f"- **Route:** `{routing.get('route_name')}`",
                f"- **Phase I continuity:** `{routing.get('is_phase_i_continuity')}`",
                f"- **Approval plan:** `{routing.get('approval_plan')}`",
                "",
                "> This UAT Runtime is generic and does not run Phase I 3-clip continuity chaining. "
                "Use Execution Center → Runway Live Smoke → 3-Clip Continuity (Phase I) for Phase I.",
                "",
            ]
        )
    lines.extend(
        [
        "## Inputs",
        "",
        f"- **Topic:** {config.get('topic')}",
        f"- **Platform:** {config.get('platform')}",
        f"- **Duration (s):** {config.get('duration_seconds')}",
        f"- **Video provider:** {config.get('video_provider')}",
        f"- **Voice provider:** {config.get('voice_provider')}",
        f"- **Confirm real voice:** {config.get('confirm_real_voice')}",
        f"- **Confirm real assembly:** {config.get('confirm_real_assembly')}",
        "",
        "## Provider modes",
        "",
        f"- **Video:** `{stages.get('video', {}).get('video_provider_mode')}`",
        f"- **Voice:** `{stages.get('voice', {}).get('voice_provider_mode')}`",
        f"- **Assembly:** `{stages.get('assembly', {}).get('assembly_mode')}`",
        "",
        "## Outputs",
        "",
        f"- **Artifact folder:** `{data.get('artifact_folder')}`",
        f"- **Final video:** `{data.get('final_video_path')}`",
        f"- **Review template:** `{data.get('review_template_path')}`",
        "",
        "## Stage summary",
        "",
        "```json",
        json.dumps(stages, indent=2),
        "```",
        "",
        "## Warnings / errors",
        "",
        ]
    )
    for item in data.get("warnings") or []:
        lines.append(f"- {item}")
    for item in data.get("errors") or []:
        lines.append(f"- **ERROR:** {item}")
    lines.extend(
        [
            "",
            "## Next steps — human review",
            "",
            "1. Watch `FINAL_PUBLISH_READY.mp4`.",
            "2. Fill in scores (0–10) in the review template JSON.",
            "3. Save completed review as `{session_id}_review.json` in `user_acceptance_reviews/`.",
            "4. Do **not** publish automatically — UAT mode only.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_uat_pipeline(
    project_root: Path,
    config: UatRuntimeConfig,
    *,
    mock_paid_providers: bool = False,
    mock_assembly_executor: bool = False,
    allow_mock_assembly_fallback: bool = False,
    session_id: str | None = None,
) -> dict[str, Any]:
    config = config.normalized()
    if not config.topic:
        raise ValueError("Topic is required for UAT pipeline.")

    config, smoke_warnings, smoke_meta = apply_live_voice_smoke_duration_guard(config)

    session_id = session_id or generate_uat_session_id()
    store = ExecutionSessionStore(project_root)
    warnings: list[str] = list(smoke_warnings)
    errors: list[str] = []
    stages: dict[str, Any] = {}
    video_mock = mock_paid_providers or config.video_provider == "mock"

    _seed_uat_session_shell(store, session_id, config)
    if smoke_meta:
        session = store.load_session(session_id)
        runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
        operations = dict(_dict(runtime.get("operations")))
        uat_block = dict(_dict(operations.get("uat_run")))
        uat_block["smoke_duration_guard"] = smoke_meta
        uat_block["requested_duration_seconds"] = smoke_meta.get("original_duration_seconds")
        operations["uat_run"] = uat_block
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        store.save_session(session, overwrite=True)
        _update_uat_progress(
            store,
            session_id,
            stage="content_brain",
            message=smoke_warnings[0],
            level="warning",
        )

    try:
        orchestrator = ContentBriefOrchestrator(project_root=project_root)
        brief_result = orchestrator.run(
            ContentBriefRunRequest(
                niche=config.niche,
                topic=config.topic,
                platform=_resolve_platform(config.platform),
                user_duration_seconds=config.duration_seconds,
                provider_name=config.video_provider,
                record_uniqueness_on_success=False,
                record_story_memory_on_success=False,
            )
        )

        session = SessionPopulationBuilder().build(brief_result)
        session = _pipeline_session(session)
        session = _attach_uat_metadata(session, config, session_id)
        session["provider"] = config.video_provider
        store.save_session(session, overwrite=True)

        stages["content_brain"] = {
            "success": True,
            "brief_id": brief_result.brief_id,
            "decision": brief_result.decision_package.decision.value,
            "clip_count": brief_result.video_format_plan.clip_count,
            "production_ready": brief_result.production_ready,
        }
        _update_uat_progress(
            store,
            session_id,
            stage="content_brain",
            message="Content brief generated.",
            stage_result=stages["content_brain"],
        )

        try:
            adapter = SessionPromptAdapter()
            bundle = adapter.build(store.load_session(session_id), config.video_provider)
            if bundle.clip_count > UAT_MAX_VIDEO_CLIPS:
                warnings.append(f"Clip count capped at {UAT_MAX_VIDEO_CLIPS}.")
        except Exception as exc:
            warnings.append(f"Prompt adapter note: {exc}")

        _update_uat_progress(store, session_id, stage="video", message="Running video stage.")
        video = _run_video_stage(
            store,
            session_id,
            config,
            mock_paid_providers=video_mock,
        )
        stages["video"] = video
        if not video.get("success"):
            errors.append(video.get("message") or "Video stage failed.")
            raise RuntimeError(errors[-1])
        _update_uat_progress(
            store,
            session_id,
            stage="video",
            message="Video stage completed.",
            stage_result=video,
        )

        _update_uat_progress(store, session_id, stage="voice", message="Running voice stage.")
        voice = _run_voice_stage(
            store,
            session_id,
            config,
            mock_paid_providers=mock_paid_providers,
        )
        stages["voice"] = voice
        if not voice.get("success"):
            errors.append(voice.get("message") or "Voice stage failed.")
            raise RuntimeError(errors[-1])
        _update_uat_progress(
            store,
            session_id,
            stage="voice",
            message="Voice stage completed.",
            stage_result=voice,
        )

        segment_count = int(
            _dict(_dict(store.load_session(session_id).get("execution_runtime")).get("category_runtime", {}))
            .get(CATEGORY_VOICE, {})
            .get("segment_count")
            or 0
        )
        if segment_count > UAT_MAX_VOICE_SEGMENTS:
            warnings.append(f"Voice segment count {segment_count} exceeds UAT cap {UAT_MAX_VOICE_SEGMENTS}.")

        subtitle_timing = (
            "equal_chunk"
            if voice.get("voice_provider_mode") == "mock"
            else "auto"
        )
        if voice.get("voice_provider_mode") == "mock":
            _relax_narration_timing_for_subtitles(store, session_id)
        _update_uat_progress(store, session_id, stage="subtitle", message="Running subtitle stage.")
        subtitle = _run_subtitle_stage(store, session_id, timing_strategy=subtitle_timing)
        stages["subtitle"] = subtitle
        if not subtitle.get("success"):
            errors.append(subtitle.get("message") or "Subtitle stage failed.")
            raise RuntimeError(errors[-1])
        _update_uat_progress(
            store,
            session_id,
            stage="subtitle",
            message="Subtitle stage completed.",
            stage_result=subtitle,
        )

        _update_uat_progress(store, session_id, stage="assembly", message="Running assembly stage.")
        assembly = _run_assembly_stage(
            store,
            session_id,
            config,
            mock_paid_providers=mock_paid_providers,
            mock_assembly_executor=mock_assembly_executor,
            allow_mock_assembly_fallback=allow_mock_assembly_fallback,
        )
        stages["assembly"] = assembly
        if not assembly.get("success"):
            errors.append(assembly.get("message") or "Assembly stage failed.")
            raise RuntimeError(errors[-1])
        _update_uat_progress(
            store,
            session_id,
            stage="assembly",
            message="Assembly stage completed.",
            stage_result=assembly,
        )

        artifact_folder = str(store.artifact_dir(session_id, CATEGORY_VIDEO).parent.resolve())
        final_video_path = assembly.get("final_video_path")
        review_path = _write_review_template(
            session_id,
            config,
            artifact_folder,
            final_video_path,
            project_root=project_root,
        )

        try:
            approval_engine = AssemblyApprovalOperationsEngine(store, project_root=project_root)
            approval_engine.expire(session_id, reason="Post-UAT approval expire", expired_by=UAT_TRIGGER)
        except Exception:
            pass

        report_payload = {
            "timestamp": _now(),
            "success": True,
            "session_id": session_id,
            "routing": uat_routing_snapshot(
                clip_count=int(stages.get("content_brain", {}).get("clip_count") or 0) or None,
            ),
            "config": {
                "topic": config.topic,
                "platform": config.platform,
                "duration_seconds": config.duration_seconds,
                "video_provider": config.video_provider,
                "voice_provider": config.voice_provider,
                "confirm_real_voice": config.confirm_real_voice,
                "confirm_real_video": config.confirm_real_video,
                "confirm_real_assembly": config.confirm_real_assembly,
            },
            "stages": stages,
            "artifact_folder": artifact_folder,
            "final_video_path": final_video_path,
            "review_template_path": str(review_path.resolve()),
            "warnings": warnings,
            "errors": errors,
            "flags_after": {
                "MODIR_VOICE_LIVE_TTS_ENABLED": os.getenv("MODIR_VOICE_LIVE_TTS_ENABLED"),
                "MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED": os.getenv("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"),
                "ASSEMBLY_RUNTIME_EXECUTION_APPROVED": os.getenv("ASSEMBLY_RUNTIME_EXECUTION_APPROVED"),
            },
        }
        report_path = write_uat_report(session_id, report_payload, project_root=project_root)
        report_payload["runtime_report_path"] = str(report_path.resolve())

        runtime = _dict(store.load_session(session_id).get("execution_runtime"))
        operations = dict(_dict(runtime.get("operations")))
        uat_block = dict(_dict(operations.get("uat_run")))
        uat_block["status"] = "completed"
        uat_block["completed_at"] = _now()
        uat_block["stages"] = stages
        uat_block["current_stage"] = "final_mp4"
        uat_block["artifact_folder"] = artifact_folder
        uat_block["final_video_path"] = final_video_path
        uat_block["review_template_path"] = str(review_path.resolve())
        uat_block["report_path"] = str(report_path.resolve())
        uat_block["warnings"] = warnings
        uat_block["errors"] = errors
        operations["uat_run"] = uat_block
        runtime["operations"] = operations
        session_final = store.load_session(session_id)
        session_final["execution_runtime"] = runtime
        store.save_session(session_final, overwrite=True)

        _update_uat_progress(
            store,
            session_id,
            stage="final_mp4",
            message="UAT pipeline completed.",
            status="completed",
        )
        return report_payload
    except Exception as exc:
        _mark_uat_failed(store, session_id, str(exc))
        raise


def _seed_uat_session_shell(
    store: ExecutionSessionStore,
    session_id: str,
    config: UatRuntimeConfig,
) -> None:
    try:
        store.load_session(session_id)
        return
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    runtime = ensure_multi_category_shell({})
    operations = dict(build_uat_operations_block(config, session_id))
    uat_block = dict(_dict(operations.get("uat_run")))
    uat_block.setdefault("progress_log", [])
    uat_block.setdefault("stages", {})
    uat_block["status"] = "running"
    uat_block["current_stage"] = "content_brain"
    uat_block["started_at"] = _now()
    operations["uat_run"] = uat_block
    runtime["operations"] = operations
    store.save_session(
        {
            "execution_session_id": session_id,
            "created_at": _now(),
            "updated_at": _now(),
            "execution_runtime": runtime,
        },
        overwrite=True,
    )


def _flags_active_snapshot() -> dict[str, bool]:
    return {
        "MODIR_VOICE_LIVE_TTS_ENABLED": os.getenv("MODIR_VOICE_LIVE_TTS_ENABLED") == "true",
        "MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED": os.getenv("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED") == "true",
    }


def build_uat_status_payload(session: dict[str, Any]) -> dict[str, Any]:
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations"))
    uat_block = _dict(operations.get("uat_run"))
    if not uat_block:
        raise KeyError("Session is not a UAT run.")

    from content_brain.execution.runway_browser_observability import (
        extract_runway_browser_obs_from_session,
    )

    session_id = str(session.get("execution_session_id") or uat_block.get("session_id") or "")
    runway_obs_payload = extract_runway_browser_obs_from_session(session)
    routing = {
        key: uat_block.get(key)
        for key in (
            "runtime_name",
            "route_name",
            "is_phase_i_continuity",
            "continuity_enabled",
            "use_starter_image",
            "use_frame_chain",
            "approval_plan",
            "clip_count",
            "expected_approval_gate_count",
            "use_frame_after_clips",
            "story_brief_present",
            "starter_prompt_chars",
            "continuity_notes",
        )
        if key in uat_block
    }
    return {
        "session_id": session_id,
        "status": str(uat_block.get("status") or "unknown"),
        "runtime_name": routing.get("runtime_name"),
        "route_name": routing.get("route_name"),
        "is_phase_i_continuity": routing.get("is_phase_i_continuity"),
        "routing": routing,
        "current_stage": uat_block.get("current_stage"),
        "failed_stage": uat_block.get("failed_stage"),
        "stages": _dict(uat_block.get("stages")),
        "progress_log": list(uat_block.get("progress_log") or []),
        "final_video_path": uat_block.get("final_video_path"),
        "artifact_folder": uat_block.get("artifact_folder"),
        "report_path": uat_block.get("report_path"),
        "review_template_path": uat_block.get("review_template_path"),
        "warnings": list(uat_block.get("warnings") or []),
        "errors": list(uat_block.get("errors") or []),
        "flags_active": _flags_active_snapshot(),
        "api_version": "12d_v1",
        "runway_browser_obs": runway_obs_payload.get("runway_browser_obs") or {},
        "video_runtime": runway_obs_payload.get("video_runtime") or {},
    }


def validate_uat_config(config: UatRuntimeConfig) -> UatRuntimeConfig:
    config = config.normalized()
    if not config.topic:
        raise ValueError("topic is required")
    if config.confirm_real_voice and config.voice_provider != "elevenlabs":
        raise ValueError("confirm_real_voice requires voice_provider=elevenlabs")
    if config.confirm_real_video and config.video_provider != "runway_browser":
        raise ValueError("confirm_real_video requires video_provider=runway_browser")
    if config.confirm_real_assembly and config.voice_provider == "elevenlabs" and not config.confirm_real_voice:
        pass
    return config


class UATRuntimeEngine:
    """Shared UAT orchestrator for CLI (sync) and API (async background worker)."""

    _global_lock = threading.Lock()
    _active_session_id: str | None = None

    def __init__(
        self,
        project_root: Path,
        *,
        store: ExecutionSessionStore | None = None,
    ):
        self._project_root = Path(project_root)
        self._store = store or ExecutionSessionStore(self._project_root)

    @classmethod
    def active_session_id(cls) -> str | None:
        with cls._global_lock:
            return cls._active_session_id

    def _claim_active(self, session_id: str) -> None:
        with self._global_lock:
            if self._active_session_id and self._active_session_id != session_id:
                raise UatRunAlreadyActiveError(self._active_session_id)
            self._active_session_id = session_id

    def _release_active(self, session_id: str) -> None:
        with self._global_lock:
            if self._active_session_id == session_id:
                self._active_session_id = None

    def run_sync(
        self,
        config: UatRuntimeConfig,
        *,
        mock_paid_providers: bool = False,
        mock_assembly_executor: bool = False,
        allow_mock_assembly_fallback: bool = False,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        config = validate_uat_config(config)
        session_id = session_id or generate_uat_session_id()
        self._claim_active(session_id)
        try:
            return run_uat_pipeline(
                self._project_root,
                config,
                mock_paid_providers=mock_paid_providers,
                mock_assembly_executor=mock_assembly_executor,
                allow_mock_assembly_fallback=allow_mock_assembly_fallback,
                session_id=session_id,
            )
        finally:
            self._release_active(session_id)

    def start(
        self,
        config: UatRuntimeConfig,
        *,
        mock_paid_providers: bool = False,
    ) -> dict[str, Any]:
        config = validate_uat_config(config)
        session_id = generate_uat_session_id()
        self._claim_active(session_id)
        _seed_uat_session_shell(self._store, session_id, config)

        video_mock = mock_paid_providers or config.video_provider == "mock"
        allow_mock_fallback = not config.confirm_real_assembly

        def _worker() -> None:
            try:
                run_uat_pipeline(
                    self._project_root,
                    config,
                    mock_paid_providers=video_mock,
                    mock_assembly_executor=False,
                    allow_mock_assembly_fallback=allow_mock_fallback,
                    session_id=session_id,
                )
            except Exception:
                pass
            finally:
                self._release_active(session_id)

        thread = threading.Thread(target=_worker, name=f"uat-{session_id}", daemon=True)
        thread.start()
        return self.get_status(session_id)

    def get_status(self, session_id: str) -> dict[str, Any]:
        if not str(session_id).startswith(UAT_SESSION_PREFIX):
            raise KeyError(f"Not a UAT session id: {session_id}")
        session = self._store.load_session(session_id)
        return build_uat_status_payload(session)

    def submit_review(self, session_id: str, submission: UatReviewSubmission) -> dict[str, Any]:
        if not str(session_id).startswith(UAT_SESSION_PREFIX):
            raise KeyError(f"Not a UAT session id: {session_id}")

        reviews_dir = _reviews_dir(self._project_root)
        reviews_dir.mkdir(parents=True, exist_ok=True)
        review_path = reviews_dir / f"{session_id}_review.json"
        if review_path.is_file():
            raise UatReviewAlreadySubmittedError(f"Review already submitted for {session_id}")

        for field_name in (
            "story_quality_score",
            "visual_quality_score",
            "voice_quality_score",
            "subtitle_quality_score",
            "continuity_score",
            "overall_quality_score",
        ):
            value = getattr(submission, field_name)
            if not isinstance(value, int) or value < 0 or value > 10:
                raise ValueError(f"{field_name} must be an integer between 0 and 10")

        template_path = reviews_dir / f"{session_id}_review_template.json"
        template: dict[str, Any] = {}
        if template_path.is_file():
            template = json.loads(template_path.read_text(encoding="utf-8"))

        submitted_at = _now()
        payload = {
            **template,
            "review_version": REVIEW_VERSION,
            "session_id": session_id,
            "submitted_at": submitted_at,
            "submitted_by": submission.submitted_by,
            "story_quality_score": submission.story_quality_score,
            "visual_quality_score": submission.visual_quality_score,
            "voice_quality_score": submission.voice_quality_score,
            "subtitle_quality_score": submission.subtitle_quality_score,
            "continuity_score": submission.continuity_score,
            "overall_quality_score": submission.overall_quality_score,
            "comments": submission.comments,
            "publishable": submission.publishable,
        }
        review_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "success": True,
            "session_id": session_id,
            "review_path": str(review_path.resolve()),
            "submitted_at": submitted_at,
            "api_version": "12d_v1",
        }


__all__ = [
    "UATRuntimeEngine",
    "UatReviewSubmission",
    "UatRunAlreadyActiveError",
    "UatReviewAlreadySubmittedError",
    "build_uat_status_payload",
    "run_uat_pipeline",
    "validate_uat_config",
    "write_uat_report",
]


