"""Product Studio — multi-clip orchestration over validated pwmap adapter paths."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from content_brain.execution.product_publish_pipeline_trace import (
    ORCHESTRATOR_VERSION,
    PipelineTrace,
    bootstrap_trace_from_pwmap_result,
    load_pipeline_trace,
    run_publish_post_processing_chain,
    save_pipeline_trace,
)

_logger = logging.getLogger("modiragent.product_multiclip_orchestrator")

from content_brain.execution.product_multiclip_execution_plan import (
    EXECUTION_MODE_USE_FRAME,
    MultiClipExecutionPlan,
    build_generation_runtime_status,
    build_multiclip_execution_plan,
)
from content_brain.execution.pwmap_runway_agent_adapter import (
    LEGACY_INTERNAL_RUNTIME,
    PWMAP_AGENT_RUNTIME,
    run_pwmap_product_studio_generate,
)
from content_brain.execution.pwmap_finalization import register_pwmap_product_studio_run
from utils.ffmpeg_stitcher import FFmpegStitcher


def _probe_video_duration_seconds(video_path: Path) -> float | None:
    if not video_path.is_file():
        return None
    try:
        from utils.ffmpeg_stitcher import FFmpegStitcher as _  # noqa: F401
        import shutil
        import subprocess

        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return None
        return float(completed.stdout.strip())
    except (OSError, ValueError):
        return None


def finalize_multiclip_output(
    *,
    run_dir: Path,
    clip_count: int,
    execution_mode: str,
) -> dict[str, Any]:
    from content_brain.execution.pwmap_clip_assembly_guard import verify_clips_unique_for_assembly

    assembly_guard = verify_clips_unique_for_assembly(run_dir=run_dir, clip_count=clip_count)
    if not assembly_guard.get("assembly_allowed"):
        return {
            "merged": False,
            "video_path": "",
            "stitched_clip_count": int(assembly_guard.get("clip_count") or 0),
            "merge_note": assembly_guard.get("error") or "Duplicate clips blocked assembly.",
            "assembly_guard": assembly_guard,
            "assembly_status": assembly_guard.get("assembly_status") or "blocked_duplicate_or_missing_clips",
            "duplicate_chain_failed": True,
            "youtube_upload_allowed": False,
        }

    if clip_count <= 1 or execution_mode != EXECUTION_MODE_USE_FRAME:
        video = run_dir / "video.mp4"
        return {
            "merged": False,
            "video_path": str(video.resolve()).replace("\\", "/") if video.is_file() else "",
            "stitched_clip_count": 1 if video.is_file() else 0,
            "assembly_status": "completed" if video.is_file() else "",
        }

    clip_paths = [run_dir / f"clip_{index}.mp4" for index in range(1, clip_count + 1)]
    existing = [path for path in clip_paths if path.is_file()]
    if len(existing) < clip_count:
        return {
            "merged": False,
            "video_path": "",
            "stitched_clip_count": len(existing),
            "assembly_status": "blocked_duplicate_or_missing_clips",
            "merge_note": "Insufficient clip artifacts for stitch.",
            "youtube_upload_allowed": False,
        }

    merged_path = run_dir / "video_merged.mp4"
    final_path = run_dir / "video.mp4"
    stitcher = FFmpegStitcher()
    stitcher.stitch_clips([str(path) for path in existing], str(merged_path))
    if merged_path.is_file():
        import shutil

        shutil.copy2(merged_path, final_path)
    return {
        "merged": True,
        "video_path": str(final_path.resolve()).replace("\\", "/"),
        "stitched_clip_count": len(existing),
        "merged_output_path": str(merged_path.resolve()).replace("\\", "/"),
    }


def _write_runtime_artifacts(run_dir: Path, payload: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "product_multiclip_runtime.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_product_multiclip_generate(
    *,
    project_root: str | Path,
    payload: dict[str, Any],
    preflight: dict[str, Any],
    pwmap_root: str | Path | None = None,
) -> dict[str, Any]:
    """Route Product Studio generation through existing pwmap paths with multi-clip finalize."""
    started = time.time()
    multiclip_plan = build_multiclip_execution_plan(
        preflight,
        native_audio=bool(payload.get("native_audio", True)),
    )
    planned_status = build_generation_runtime_status(
        clip_count=multiclip_plan.clip_count,
        completed_clips=0,
        generation_state="generating",
    )

    from content_brain.execution.pwmap_runway_agent_adapter import (
        ensure_kling_cinematic_preflight,
        extract_prompts_from_preflight,
    )
    from content_brain.execution.product_visual_diversity_guard import (
        detect_prompt_repetition_risk,
        detect_post_generation_visual_repetition,
        save_visual_diversity_report,
    )

    working_preflight = dict(preflight)
    try:
        working_preflight = ensure_kling_cinematic_preflight(
            project_root=project_root,
            payload=payload,
            preflight=preflight,
        )
        clip_prompts, _prompt_meta = extract_prompts_from_preflight(working_preflight)
    except Exception:
        clip_prompts = []
    prompt_diversity_report = detect_prompt_repetition_risk(clip_prompts) if clip_prompts else None
    preflight_trace = PipelineTrace(orchestrator_version=ORCHESTRATOR_VERSION)
    preflight_trace.mark("story_planning", status="completed")
    if prompt_diversity_report and prompt_diversity_report.blocked:
        blocked_payload = prompt_diversity_report.to_dict()
        blocked_payload.update(
            {
                "ok": False,
                "status": "prompt_repetition_blocked",
                "repetition_risk": "high",
                "error": "prompt_repetition_risk_high",
                "message": "Clip prompts are too similar — generation blocked before spending credits.",
                "multiclip_execution_plan": multiclip_plan.to_dict(),
                "generation_runtime_status": planned_status,
                "publish_ready": False,
                "publish_package_ready": False,
                "youtube_upload_allowed": False,
            }
        )
        return blocked_payload

    pwmap_result = run_pwmap_product_studio_generate(
        project_root=project_root,
        payload=dict(payload),
        preflight=working_preflight,
        pwmap_root=pwmap_root,
    )
    elapsed_seconds = round(time.time() - started, 2)
    pwmap_result["multiclip_execution_plan"] = multiclip_plan.to_dict()
    pwmap_result["clip_execution_mode"] = multiclip_plan.execution_mode
    pwmap_result["execution_mode"] = multiclip_plan.execution_mode
    pwmap_result["use_frame_enabled"] = multiclip_plan.use_frame_enabled
    pwmap_result["planned_duration_seconds"] = multiclip_plan.duration_seconds
    pwmap_result["generation_time_seconds"] = elapsed_seconds
    pwmap_result["provider_runtime"] = PWMAP_AGENT_RUNTIME
    pwmap_result["legacy_internal_runtime"] = LEGACY_INTERNAL_RUNTIME

    if str(pwmap_result.get("status") or "") == "dry_run":
        pwmap_result["generation_runtime_status"] = planned_status
        pwmap_result["publish_ready"] = False
        pwmap_result["publish_package_ready"] = False
        pwmap_result["youtube_upload_allowed"] = False
        return pwmap_result

    run_dir_text = str(pwmap_result.get("run_dir") or pwmap_result.get("output_folder") or "")
    run_dir = Path(run_dir_text) if run_dir_text else None
    clip_details = list(pwmap_result.get("clips") or [])

    if pwmap_result.get("ok") and run_dir and run_dir.is_dir():
        post_report = detect_post_generation_visual_repetition(
            run_dir=run_dir,
            clip_count=multiclip_plan.clip_count,
            prompt_report=prompt_diversity_report,
        )
        save_visual_diversity_report(run_dir, post_report)
        pwmap_result["visual_diversity"] = post_report.to_dict()
        pwmap_result["visual_diversity_score"] = post_report.visual_diversity_score
        pwmap_result["visual_diversity_status"] = post_report.status
        pwmap_result["repetition_risk"] = post_report.repetition_risk
        pwmap_result["similar_clip_pairs"] = [pair.to_dict() for pair in post_report.similar_clip_pairs]
        pwmap_result["repeated_clip_warning"] = post_report.repeated_clip_warning
        pwmap_result["youtube_upload_allowed"] = post_report.youtube_upload_allowed
        if post_report.status == "visual_repetition_failed":
            pwmap_result["ok"] = False
            pwmap_result["status"] = "visual_repetition_failed"
            pwmap_result["publish_ready"] = False
            pwmap_result["publish_package_ready"] = False
            pwmap_result["error"] = "visual_repetition_failed"
            register_pwmap_product_studio_run(
                project_root=project_root,
                run_id=str(pwmap_result.get("run_id") or ""),
                topic=str(preflight.get("authoritative_topic") or ""),
                ok=False,
                clips=list(pwmap_result.get("clips") or clip_details),
                video_path=str(pwmap_result.get("video_path") or ""),
                run_dir=str(run_dir.resolve()).replace("\\", "/"),
                partial=True,
            )
            return pwmap_result

        merge_info = finalize_multiclip_output(
            run_dir=run_dir,
            clip_count=multiclip_plan.clip_count,
            execution_mode=multiclip_plan.execution_mode,
        )
        if merge_info.get("duplicate_chain_failed"):
            pwmap_result["ok"] = False
            pwmap_result["status"] = "duplicate_failed"
            pwmap_result["duplicate_chain_failed"] = True
            pwmap_result["publish_ready"] = False
            pwmap_result["publish_package_ready"] = False
            pwmap_result["youtube_upload_allowed"] = False
            pwmap_result["error"] = merge_info.get("merge_note") or "duplicate_assembly_blocked"
        if merge_info.get("video_path"):
            pwmap_result["video_path"] = merge_info["video_path"]
            pwmap_result["download_path"] = merge_info["video_path"]
        pwmap_result["merge_info"] = merge_info
        completed = int(merge_info.get("stitched_clip_count") or len(clip_details) or 0)
        final_state = "merge_complete" if merge_info.get("merged") else (
            "completed" if pwmap_result.get("ok") else "failed"
        )
        runtime_status = build_generation_runtime_status(
            clip_count=multiclip_plan.clip_count,
            completed_clips=max(completed, multiclip_plan.clip_count if pwmap_result.get("ok") else 0),
            generation_state=final_state,
            clip_details=clip_details,
        )
        pwmap_result["generation_runtime_status"] = runtime_status
        final_video = Path(str(merge_info.get("video_path") or pwmap_result.get("video_path") or ""))
        duration_probe = _probe_video_duration_seconds(final_video)
        if duration_probe is not None:
            pwmap_result["final_video_duration_seconds"] = round(duration_probe, 2)
        _write_runtime_artifacts(
            run_dir,
            {
                "multiclip_execution_plan": multiclip_plan.to_dict(),
                "generation_runtime_status": runtime_status,
                "merge_info": merge_info,
                "generation_time_seconds": elapsed_seconds,
                "final_video_duration_seconds": pwmap_result.get("final_video_duration_seconds"),
            },
        )
        normalized_path = run_dir / "normalized_result.json"
        if normalized_path.is_file():
            try:
                normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
                normalized.update(
                    {
                        "video_path": pwmap_result.get("video_path"),
                        "download_path": pwmap_result.get("download_path"),
                        "multiclip_execution_plan": multiclip_plan.to_dict(),
                        "generation_runtime_status": runtime_status,
                        "merge_info": merge_info,
                        "generation_time_seconds": elapsed_seconds,
                        "execution_mode": multiclip_plan.execution_mode,
                        "final_video_duration_seconds": pwmap_result.get("final_video_duration_seconds"),
                    }
                )
                normalized_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
            except (OSError, json.JSONDecodeError):
                pass
        register_pwmap_product_studio_run(
            project_root=project_root,
            run_id=str(pwmap_result.get("run_id") or ""),
            topic=str(preflight.get("authoritative_topic") or ""),
            ok=bool(pwmap_result.get("ok")),
            clips=list(pwmap_result.get("clips") or clip_details),
            video_path=str(pwmap_result.get("video_path") or ""),
            run_dir=str(run_dir.resolve()).replace("\\", "/"),
            partial=str(pwmap_result.get("status") or "") == "partial",
        )
        run_id_text = str(pwmap_result.get("run_id") or run_dir.name)
        topic_text = str(preflight.get("authoritative_topic") or "")
        pipeline_trace = bootstrap_trace_from_pwmap_result(
            run_id=run_id_text,
            pwmap_result=pwmap_result,
            multiclip_plan=multiclip_plan.to_dict(),
        )
        for stage_name, stage_payload in preflight_trace.stages.items():
            if stage_name not in pipeline_trace.stages:
                pipeline_trace.stages[stage_name] = stage_payload
        save_pipeline_trace(run_dir, pipeline_trace)
        _logger.info(
            "Starting publish post-processing chain run_id=%s last_completed=%s",
            run_id_text,
            pipeline_trace.last_completed_stage,
        )
        chain_result = run_publish_post_processing_chain(
            project_root=project_root,
            run_dir=run_dir,
            run_id=run_id_text,
            topic=topic_text,
            expected_clip_count=multiclip_plan.clip_count,
            preflight=preflight,
            trace=pipeline_trace,
            visual_diversity=post_report.to_dict() if post_report else None,
            attempt_auto_youtube_upload=True,
            automation_mode=bool(payload.get("automation_mode")),
        )
        assembly_result = dict(chain_result.get("assembly") or {})
        branding_publish_result = dict(chain_result.get("branding_publish") or {})
        pwmap_result["assembly"] = assembly_result
        pwmap_result["assembly_status"] = chain_result.get("assembly_status") or assembly_result.get("assembly_status")
        pwmap_result["assembly_complete"] = bool(chain_result.get("assembly_complete") or assembly_result.get("assembly_complete"))
        pwmap_result["publish_package_ready"] = bool(chain_result.get("publish_package_ready"))
        pwmap_result["publish_package_path"] = chain_result.get("publish_package_path")
        pwmap_result["final_publish_video_path"] = chain_result.get("final_publish_video_path")
        pwmap_result["source_clip_count"] = chain_result.get("source_clip_count")
        if chain_result.get("final_publish_video_path"):
            pwmap_result["video_path"] = chain_result["final_publish_video_path"]
            pwmap_result["download_path"] = chain_result["final_publish_video_path"]
        if assembly_result.get("duration_seconds") is not None:
            pwmap_result["final_video_duration_seconds"] = round(float(assembly_result["duration_seconds"]), 2)
        if chain_result.get("youtube_metadata"):
            pwmap_result["youtube_metadata"] = chain_result.get("youtube_metadata")
            pwmap_result["youtube_metadata_path"] = chain_result.get("youtube_metadata_path")
        if not chain_result.get("ok"):
            pwmap_result["ok"] = False
            pwmap_result["status"] = chain_result.get("status") or "publish_chain_failed"
            pwmap_result["missing_clip_index"] = assembly_result.get("missing_clip_index")
            pwmap_result["missing_clip_indices"] = assembly_result.get("missing_clip_indices")
            pwmap_result["recovery_possible"] = bool(assembly_result.get("recovery_possible"))
            pwmap_result["error"] = chain_result.get("error")
        if branding_publish_result:
            pwmap_result["branding_publish"] = branding_publish_result
            pwmap_result["branding_status"] = branding_publish_result.get("branding_status")
            pwmap_result["subtitle_status"] = branding_publish_result.get("subtitle_status")
            pwmap_result["audio_status"] = branding_publish_result.get("audio_status")
            pwmap_result["logo_status"] = branding_publish_result.get("logo_status")
            pwmap_result["cta_status"] = branding_publish_result.get("cta_status")
            pwmap_result["intro_status"] = branding_publish_result.get("intro_status")
            pwmap_result["outro_status"] = branding_publish_result.get("outro_status")
            pwmap_result["subtitle_count"] = branding_publish_result.get("subtitle_count")
            pwmap_result["subtitle_language"] = branding_publish_result.get("subtitle_language")
            pwmap_result["normalization_applied"] = branding_publish_result.get("normalization_applied")
            pwmap_result["lufs_value"] = branding_publish_result.get("lufs_value")
            pwmap_result["final_branded_publish_video_path"] = branding_publish_result.get("final_branded_publish_video_path")
            if branding_publish_result.get("publish_ready"):
                pwmap_result["publish_package_ready"] = True
                pwmap_result["video_path"] = branding_publish_result["final_branded_publish_video_path"]
                pwmap_result["download_path"] = branding_publish_result["final_branded_publish_video_path"]
        pwmap_result["pipeline_trace"] = chain_result.get("pipeline_trace") or load_pipeline_trace(run_dir) or {}
        pwmap_result["stop_stage"] = chain_result.get("stop_stage") or pwmap_result["pipeline_trace"].get("stop_stage") or ""
        pwmap_result["last_completed_stage"] = (
            chain_result.get("last_completed_stage")
            or pwmap_result["pipeline_trace"].get("last_completed_stage")
            or ""
        )
        if chain_result.get("youtube_upload"):
            pwmap_result["youtube_upload"] = chain_result["youtube_upload"]
        if chain_result.get("platform_uploads"):
            pwmap_result["platform_uploads"] = chain_result["platform_uploads"]
        if chain_result.get("upload_platform_targets"):
            pwmap_result["upload_platform_targets"] = chain_result["upload_platform_targets"]
        for field in (
            "youtube_upload_status",
            "youtube_video_id",
            "youtube_url",
            "youtube_visibility",
            "youtube_upload_time",
            "auto_upload_enabled",
            "auto_upload_started",
            "youtube_upload_blocked_reason",
        ):
            if chain_result.get(field) is not None:
                pwmap_result[field] = chain_result[field]
        pwmap_result["orchestrator_version"] = ORCHESTRATOR_VERSION
        runtime_payload = {
            "multiclip_execution_plan": multiclip_plan.to_dict(),
            "generation_runtime_status": runtime_status,
            "merge_info": merge_info,
            "generation_time_seconds": elapsed_seconds,
            "final_video_duration_seconds": pwmap_result.get("final_video_duration_seconds"),
            "pipeline_trace": pwmap_result.get("pipeline_trace"),
            "orchestrator_version": ORCHESTRATOR_VERSION,
            "publish_package_ready": pwmap_result.get("publish_package_ready"),
            "assembly_status": pwmap_result.get("assembly_status"),
            "branding_status": pwmap_result.get("branding_status"),
            "youtube_upload_status": pwmap_result.get("youtube_upload_status"),
            "auto_upload_enabled": pwmap_result.get("auto_upload_enabled"),
        }
        _write_runtime_artifacts(run_dir, runtime_payload)
        if normalized_path.is_file():
            try:
                normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
                normalized.update(
                    {
                        "video_path": pwmap_result.get("video_path"),
                        "download_path": pwmap_result.get("download_path"),
                        "publish_package_path": pwmap_result.get("publish_package_path"),
                        "final_publish_video_path": pwmap_result.get("final_publish_video_path"),
                        "assembly_status": pwmap_result.get("assembly_status"),
                        "assembly_complete": pwmap_result.get("assembly_complete"),
                        "publish_package_ready": pwmap_result.get("publish_package_ready"),
                        "source_clip_count": pwmap_result.get("source_clip_count"),
                        "youtube_metadata_path": pwmap_result.get("youtube_metadata_path"),
                        "missing_clip_index": pwmap_result.get("missing_clip_index"),
                        "recovery_possible": pwmap_result.get("recovery_possible"),
                        "branding_status": pwmap_result.get("branding_status"),
                        "subtitle_status": pwmap_result.get("subtitle_status"),
                        "audio_status": pwmap_result.get("audio_status"),
                        "final_branded_publish_video_path": pwmap_result.get("final_branded_publish_video_path"),
                        "logo_status": pwmap_result.get("logo_status"),
                        "cta_status": pwmap_result.get("cta_status"),
                        "intro_status": pwmap_result.get("intro_status"),
                        "outro_status": pwmap_result.get("outro_status"),
                        "subtitle_count": pwmap_result.get("subtitle_count"),
                        "normalization_applied": pwmap_result.get("normalization_applied"),
                        "pipeline_trace": pwmap_result.get("pipeline_trace"),
                        "stop_stage": pwmap_result.get("stop_stage"),
                        "last_completed_stage": pwmap_result.get("last_completed_stage"),
                        "orchestrator_version": ORCHESTRATOR_VERSION,
                    }
                )
                normalized_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
            except (OSError, json.JSONDecodeError):
                pass
    else:
        partial_clips = list(pwmap_result.get("clips") or clip_details)
        if run_dir and run_dir.is_dir() and partial_clips:
            from content_brain.execution.pwmap_finalization import verify_and_recover_clip_downloads

            last_result_path = run_dir / "last_result.json"
            last_result = {}
            if last_result_path.is_file():
                try:
                    last_result = json.loads(last_result_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    last_result = {}
            verify = verify_and_recover_clip_downloads(
                run_dir=run_dir,
                last_result=last_result,
                copied_clips=partial_clips,
            )
            if verify["valid_clip_count"] > 0:
                pwmap_result["status"] = "partial_failed"
                pwmap_result["ok"] = False
                pwmap_result["recovery_available"] = True
                pwmap_result["youtube_upload_allowed"] = False
                pwmap_result["publish_ready"] = False
                pwmap_result["publish_package_ready"] = False
                pwmap_result["clips"] = verify["verified_clips"]
                pwmap_result["clip_count"] = verify["valid_clip_count"]
                pwmap_result["video_path"] = ""
                pwmap_result["download_path"] = ""
                register_pwmap_product_studio_run(
                    project_root=project_root,
                    run_id=str(pwmap_result.get("run_id") or ""),
                    topic=str(preflight.get("authoritative_topic") or ""),
                    ok=False,
                    clips=verify["verified_clips"],
                    video_path=str(pwmap_result.get("video_path") or ""),
                    run_dir=str(run_dir.resolve()).replace("\\", "/"),
                    partial=True,
                )
        pwmap_result["generation_runtime_status"] = build_generation_runtime_status(
            clip_count=multiclip_plan.clip_count,
            completed_clips=0,
            generation_state="failed",
            clip_details=clip_details,
        )
        pwmap_result["generation_runtime_status"]["planned_status"] = planned_status

    pwmap_result["clip_count"] = multiclip_plan.clip_count
    pwmap_result["kling_clip_count"] = multiclip_plan.clip_count
    return pwmap_result


__all__ = [
    "MultiClipExecutionPlan",
    "ORCHESTRATOR_VERSION",
    "finalize_multiclip_output",
    "run_product_multiclip_generate",
]
