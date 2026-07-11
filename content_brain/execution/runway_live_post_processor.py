"""
Live post-processing hook for Runway smoke runs — checkpoint, assembly, publish package.

Runs only after a successful non-simulate Runway run with all clips downloaded.
Does not touch Runway automation, selectors, or prompt builder internals.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability
from content_brain.audio.audio_post_processing import run_audio_post_processing
from content_brain.branding.branding_runtime import FINAL_BRANDED_VIDEO_CANONICAL_NAME, run_branding_runtime
from content_brain.platform.delivery_quality_gate import (
    DELIVERY_FAIL,
    evaluate_delivery_quality,
    write_delivery_quality_gate,
)
from content_brain.platform.media_probe import probe_duration_seconds
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.platform.canonical_delivery import (
    CANONICAL_BRANDED_VIDEO_NAME,
    archive_superseded_branded_variants,
    promote_canonical_final_video,
)
from content_brain.platform.run_output_versioning import (
    create_versioned_run_layout,
    finalize_versioned_run_layout,
    write_raw_downloads_manifest,
)
from content_brain.vision.visual_continuity_pipeline import run_visual_continuity_verification

POST_PROCESSOR_VERSION = "runway_live_post_processing_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
FINAL_VIDEO_NAME = "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
FFMPEG_TIMEOUT_SECONDS = 600

CHECKPOINT_STARTED = "run_completed_post_processing_started"
CHECKPOINT_ASSEMBLY = "assembly_completed"
CHECKPOINT_PUBLISH = "publish_completed"
CHECKPOINT_DELIVERY_BLOCKED = "delivery_gate_failed"

STATUS_SKIPPED = "skipped"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"

ASSEMBLY_ASSEMBLED = "ASSEMBLED"
ASSEMBLY_PLAN_ONLY = "PLAN_ONLY"
ASSEMBLY_FAILED = "FAILED"

PUBLISH_CREATED = "PUBLISHED_PACKAGE_CREATED"
PUBLISH_SKIPPED_PLAN_ONLY = "SKIPPED_ASSEMBLY_PLAN_ONLY"
PUBLISH_SKIPPED = "SKIPPED"
PUBLISH_FAILED = "FAILED"


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _report_value(report: Any, key: str, default: Any = None) -> Any:
    if isinstance(report, dict):
        return report.get(key, default)
    return getattr(report, key, default)


def _set_report_value(report: Any, key: str, value: Any) -> None:
    if isinstance(report, dict):
        report[key] = value
    else:
        setattr(report, key, value)


def _report_to_dict(report: Any) -> dict[str, Any]:
    if isinstance(report, dict):
        return dict(report)
    if hasattr(report, "to_dict"):
        return report.to_dict()
    return {item: _report_value(report, item) for item in dir(report) if not item.startswith("_")}


def _runtime_state_dir(project_root: Path) -> Path:
    return project_root / "project_brain" / "runtime_state"


def _checkpoint_path(project_root: Path) -> Path:
    return _runtime_state_dir(project_root) / "runway_phase_i_checkpoint.json"


def _assembly_manifest_path(project_root: Path) -> Path:
    return _runtime_state_dir(project_root) / "runway_phase_i_assembly_manifest.json"


def _publish_manifest_path(project_root: Path) -> Path:
    return _runtime_state_dir(project_root) / "runway_phase_i_publish_manifest.json"


def _final_video_path(project_root: Path) -> Path:
    return project_root / "outputs" / "final" / FINAL_VIDEO_NAME


def _publish_package_dir(project_root: Path) -> Path:
    return project_root / "outputs" / "publish" / "runway_phase_i"


def _default_prompts_path(project_root: Path) -> Path:
    return project_root / "project_brain" / "content_brain_test_results" / "latest.runway_prompts.txt"


def collect_valid_download_paths(downloaded_paths: list[str]) -> tuple[list[str], list[str]]:
    """Return (valid_paths, missing_or_empty_paths) using on-disk file checks."""
    valid: list[str] = []
    missing: list[str] = []
    for path_text in downloaded_paths:
        text = str(path_text or "").strip()
        if not text:
            missing.append(text)
            continue
        path = Path(text)
        if path.is_file() and path.stat().st_size > 0:
            valid.append(str(path.resolve()))
        else:
            missing.append(text)
    return valid, missing


def evaluate_post_processing_eligibility(report: Any) -> tuple[bool, str, dict[str, Any]]:
    """Return (eligible, reason, context). Fail closed on zero clips or empty downloads."""
    simulate = bool(_report_value(report, "simulate", True))
    if simulate:
        return False, "simulate_skipped", {}

    if not bool(_report_value(report, "ok", False)):
        return False, "run_not_ok", {}

    clip_count = int(_report_value(report, "clip_count", 0) or 0)
    if clip_count < 1:
        return False, "invalid_clip_count", {}

    clips_completed = int(_report_value(report, "clips_completed", 0) or 0)
    if clips_completed <= 0:
        return False, "zero_clips_completed", {}

    requested = clip_count
    downloaded_paths = [str(item) for item in (_report_value(report, "downloaded_file_paths", []) or []) if item]
    valid_downloads, missing = collect_valid_download_paths(downloaded_paths)

    if not valid_downloads:
        return False, "zero_valid_downloads", {"missing_files": missing}

    if len(valid_downloads) == requested:
        clips_downloaded = len(valid_downloads)
        if int(_report_value(report, "total_downloads_completed", 0) or 0) != clips_downloaded:
            _set_report_value(report, "total_downloads_completed", clips_downloaded)
        resolved_paths = valid_downloads[:requested]
    else:
        stale_counter = int(_report_value(report, "total_downloads_completed", 0) or 0)
        if stale_counter != requested:
            return False, f"downloads_mismatch:{stale_counter}!={requested}", {}
        if len(downloaded_paths) != requested:
            return False, f"paths_mismatch:{len(downloaded_paths)}!={requested}", {}
        if missing:
            return False, "missing_download_files", {"missing_files": missing}
        resolved_paths = downloaded_paths
        clips_downloaded = stale_counter

    return True, "eligible", {
        "clip_count": clip_count,
        "clips_downloaded": clips_downloaded,
        "downloaded_file_paths": resolved_paths,
        "clips_generated": int(_report_value(report, "clips_completed", 0) or clip_count),
        "run_id": str(_report_value(report, "content_brain_run_id", "") or ""),
        "topic": str(
            _report_value(report, "content_brain_topic", "")
            or _report_value(report, "topic_label", "")
            or _report_value(report, "story_idea", "")
            or ""
        ),
    }


def write_runway_phase_i_checkpoint(
    project_root: Path,
    *,
    run_id: str,
    topic: str,
    clip_count: int,
    clips_generated: int,
    clips_downloaded: int,
    downloaded_file_paths: list[str],
    checkpoint: str,
    simulate: bool,
    created_at: str | None = None,
    delivery_status: str = "",
    delivery_failures: list[str] | None = None,
) -> Path:
    path = _checkpoint_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _now()
    payload = {
        "version": POST_PROCESSOR_VERSION,
        "run_id": run_id,
        "topic": topic,
        "clip_count": clip_count,
        "clips_generated": clips_generated,
        "clips_downloaded": clips_downloaded,
        "downloaded_file_paths": list(downloaded_file_paths),
        "checkpoint": checkpoint,
        "simulate": bool(simulate),
        "created_at": created_at or now,
        "updated_at": now,
    }
    if delivery_status:
        payload["delivery_status"] = delivery_status
    if delivery_failures:
        payload["delivery_failures"] = list(delivery_failures)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _run_ffmpeg(ffmpeg_bin: str, args: list[str], *, timeout_seconds: int) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [ffmpeg_bin, *args],
            capture_output=True,
            text=True,
            timeout=max(1, timeout_seconds),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "FFmpeg timed out."
    except OSError as exc:
        return False, str(exc)

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return False, detail
    return True, ""


def run_assembly(
    project_root: Path,
    *,
    input_files: list[str],
    clip_count: int,
    ffmpeg_probe: Any | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    output_path = output_path or _final_video_path(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = _assembly_manifest_path(project_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    probe = ffmpeg_probe if ffmpeg_probe is not None else check_ffmpeg_availability()
    ffmpeg_available = bool(getattr(probe, "available", False))
    ffmpeg_bin = getattr(probe, "ffmpeg_path", None)

    base_manifest: dict[str, Any] = {
        "version": POST_PROCESSOR_VERSION,
        "status": ASSEMBLY_PLAN_ONLY,
        "clip_count": clip_count,
        "input_files": list(input_files),
        "output_path": str(output_path),
        "ffmpeg_available": ffmpeg_available,
        "ffmpeg_executed": False,
        "error": "",
        "created_at": _now(),
    }

    if not ffmpeg_available or not ffmpeg_bin:
        base_manifest["status"] = ASSEMBLY_PLAN_ONLY
        base_manifest["error"] = str(getattr(probe, "error", "") or "FFmpeg not available.")
        manifest_path.write_text(json.dumps(base_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return base_manifest

    from content_brain.execution.product_audio_source import strip_runway_audio_during_assembly

    strip_audio = strip_runway_audio_during_assembly(project_root)
    video_codec_args = ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    audio_args = ["-an"] if strip_audio else ["-c:a", "aac", "-b:a", "192k"]

    if len(input_files) == 1:
        ok, error = _run_ffmpeg(
            ffmpeg_bin,
            ["-y", "-i", input_files[0], *video_codec_args, *audio_args, str(output_path)],
            timeout_seconds=FFMPEG_TIMEOUT_SECONDS,
        )
    else:
        concat_list = output_path.parent / "runway_live_concat_list.txt"
        lines = [f"file '{Path(path_text).as_posix()}'" for path_text in input_files]
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, error = _run_ffmpeg(
            ffmpeg_bin,
            [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                *video_codec_args,
                *audio_args,
                str(output_path),
            ],
            timeout_seconds=FFMPEG_TIMEOUT_SECONDS,
        )

    base_manifest["ffmpeg_executed"] = True
    if not ok:
        base_manifest["status"] = ASSEMBLY_FAILED
        base_manifest["error"] = error
        manifest_path.write_text(json.dumps(base_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return base_manifest

    if not output_path.is_file() or output_path.stat().st_size <= 0:
        base_manifest["status"] = ASSEMBLY_FAILED
        base_manifest["error"] = "Final output missing or empty after FFmpeg."
        manifest_path.write_text(json.dumps(base_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return base_manifest

    base_manifest["status"] = ASSEMBLY_ASSEMBLED
    base_manifest["error"] = ""
    assembled_duration = probe_duration_seconds(output_path)
    if assembled_duration:
        base_manifest["duration_seconds"] = assembled_duration
    manifest_path.write_text(json.dumps(base_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return base_manifest


def run_publish_package(
    project_root: Path,
    *,
    assembly_manifest: dict[str, Any],
    run_id: str,
    topic: str,
    clip_count: int,
    downloaded_file_paths: list[str],
    audio_post_result: dict[str, Any] | None = None,
    branding_post_result: dict[str, Any] | None = None,
    package_dir: Path | None = None,
) -> dict[str, Any]:
    manifest_path = _publish_manifest_path(project_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    audio_post_result = dict(audio_post_result or {})
    branding_post_result = dict(branding_post_result or {})
    assembly_status = str(assembly_manifest.get("status") or "")
    final_video = Path(str(assembly_manifest.get("output_path") or _final_video_path(project_root)))

    if assembly_status != ASSEMBLY_ASSEMBLED or not final_video.is_file() or final_video.stat().st_size <= 0:
        payload = {
            "version": POST_PROCESSOR_VERSION,
            "status": PUBLISH_SKIPPED_PLAN_ONLY if assembly_status == ASSEMBLY_PLAN_ONLY else PUBLISH_SKIPPED,
            "final_video_path": str(final_video) if final_video.exists() else "",
            "package_folder": "",
            "metadata_path": "",
            "prompts_path": "",
            "subtitle_paths": [],
            "narration_plan_path": "",
            "warnings": warnings,
            "created_at": _now(),
        }
        manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    package_dir = package_dir or _publish_package_dir(project_root)
    package_dir.mkdir(parents=True, exist_ok=True)
    package_video = package_dir / FINAL_VIDEO_NAME
    shutil.copy2(final_video, package_video)

    narrated_source = Path(str(audio_post_result.get("narrated_video_path") or ""))
    package_narrated = package_dir / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4"
    narrated_video_path = ""
    if narrated_source.is_file() and narrated_source.stat().st_size > 0:
        shutil.copy2(narrated_source, package_narrated)
        narrated_video_path = str(package_narrated)

    branded_source = Path(str(branding_post_result.get("final_branded_video_path") or ""))
    branded_video_path = ""
    if branded_source.is_file() and branded_source.stat().st_size > 0:
        canonical_publish = promote_canonical_final_video(
            branded_source,
            publish_dir=package_dir,
            archive_superseded=True,
            run_id=run_id,
        )
        branded_video_path = str(canonical_publish)

    branding_settings = dict(branding_post_result.get("settings") or {})
    metadata_path = package_dir / "metadata.json"
    metadata = {
        "version": POST_PROCESSOR_VERSION,
        "run_id": run_id,
        "topic": topic,
        "clip_count": clip_count,
        "downloaded_file_paths": list(downloaded_file_paths),
        "final_video_path": str(package_video),
        "narrated_video_path": narrated_video_path,
        "branded_video_path": branded_video_path,
        "branding_enabled": bool(branding_post_result.get("branding_enabled", branding_settings.get("branding_enabled", False))),
        "subtitle_enabled": bool(branding_settings.get("subtitle_enabled", False)),
        "logo_enabled": bool(branding_settings.get("logo_enabled", False)),
        "cta_enabled": bool(branding_settings.get("cta_enabled", False)),
        "intro_enabled": bool(branding_settings.get("intro_enabled", False)),
        "outro_enabled": bool(branding_settings.get("outro_enabled", False)),
        "narration_provider": str(audio_post_result.get("narration_provider") or ""),
        "voice_id": str(audio_post_result.get("voice_id") or ""),
        "music_provider": str(audio_post_result.get("music_provider") or ""),
        "music_status": str(audio_post_result.get("music_status") or branding_post_result.get("music_status") or ""),
        "music_status_code": str(audio_post_result.get("music_status_code") or ""),
        "subtitle_status": str(branding_post_result.get("subtitle_status") or audio_post_result.get("subtitle_status") or ""),
        "ambience_status": str(audio_post_result.get("ambience_status") or ""),
        "sfx_status": str(audio_post_result.get("sfx_status") or ""),
        "subtitle_style_status": str(audio_post_result.get("subtitle_style_status") or ""),
        "character_voice_status": str(audio_post_result.get("character_voice_status") or ""),
        "duration_seconds": audio_post_result.get("duration_seconds"),
        "branding_status": str(branding_post_result.get("status") or ""),
        "created_at": _now(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    prompts_dir = package_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompts_path = prompts_dir / "runway_prompts.txt"
    source_prompts = _default_prompts_path(project_root)
    if source_prompts.is_file():
        shutil.copy2(source_prompts, prompts_path)
    else:
        prompts_path.write_text(f"# Runway prompts unavailable for run {run_id}\n", encoding="utf-8")
        warnings.append("runway_prompts_source_missing")

    subtitles_dir = package_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    srt_path = subtitles_dir / "subtitles.srt"
    vtt_path = subtitles_dir / "subtitles.vtt"
    def _copy_if_distinct(source: Path, target: Path) -> None:
        if not source.is_file():
            return
        if source.resolve() == target.resolve():
            return
        shutil.copy2(source, target)

    subtitle_paths = [str(item) for item in (audio_post_result.get("subtitle_paths") or []) if item]
    if len(subtitle_paths) >= 2 and Path(subtitle_paths[0]).is_file() and Path(subtitle_paths[1]).is_file():
        _copy_if_distinct(Path(subtitle_paths[0]), srt_path)
        _copy_if_distinct(Path(subtitle_paths[1]), vtt_path)
    else:
        srt_path.write_text("1\n00:00:00,000 --> 00:00:05,000\n[placeholder subtitles]\n", encoding="utf-8")
        vtt_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n[placeholder subtitles]\n", encoding="utf-8")
        if str(audio_post_result.get("status") or "") != "completed":
            warnings.append("subtitle_timing_placeholder_used")

    styled_ass = Path(str(audio_post_result.get("styled_ass_path") or ""))
    if styled_ass.is_file():
        _copy_if_distinct(styled_ass, subtitles_dir / "subtitles_styled.ass")

    narration_dir = package_dir / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)
    narration_script_path = narration_dir / "narration_script.txt"
    narration_audio_path = narration_dir / "narration.mp3"
    narration_plan_path = narration_dir / "narration_plan.json"

    script_source = Path(str(audio_post_result.get("narration_script_path") or ""))
    audio_source = Path(str(audio_post_result.get("narration_audio_path") or ""))
    timeline_plan_source = Path(str(audio_post_result.get("narration_plan_path") or ""))
    if script_source.is_file():
        _copy_if_distinct(script_source, narration_script_path)
    else:
        narration_script_path.write_text(f"# Narration script unavailable for run {run_id}\n", encoding="utf-8")
        warnings.append("narration_script_missing")
    if audio_source.is_file():
        _copy_if_distinct(audio_source, narration_audio_path)
    else:
        warnings.append("narration_audio_missing")

    timeline_payload = dict(audio_post_result.get("timeline_narration") or {})
    if timeline_plan_source.is_file():
        _copy_if_distinct(timeline_plan_source, narration_plan_path)
    elif timeline_payload.get("narration_plan_path") and Path(str(timeline_payload["narration_plan_path"])).is_file():
        _copy_if_distinct(Path(str(timeline_payload["narration_plan_path"])), narration_plan_path)
    else:
        narration_plan_path.write_text(
            json.dumps(
                {
                    "version": POST_PROCESSOR_VERSION,
                    "status": str(audio_post_result.get("status") or "not_run"),
                    "run_id": run_id,
                    "topic": topic,
                    "narration_provider": str(audio_post_result.get("narration_provider") or ""),
                    "voice_id": str(audio_post_result.get("voice_id") or ""),
                    "music_provider": str(audio_post_result.get("music_provider") or ""),
                    "music_status": str(audio_post_result.get("music_status") or ""),
                    "music_status_code": str(audio_post_result.get("music_status_code") or ""),
                    "narration_script_path": str(narration_script_path),
                    "narration_audio_path": str(narration_audio_path) if audio_source.is_file() else "",
                    "segments": list(timeline_payload.get("segments") or []),
                },
                indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    youtube_metadata_path = ""
    youtube_metadata: dict[str, Any] = {}
    try:
        from content_brain.publish.youtube_metadata_generator import generate_and_save_youtube_metadata

        profile_store = ProductChannelProfileStore(project_root)
        channel_profile = profile_store.load()
        narration_script = ""
        if narration_script_path.is_file():
            narration_script = narration_script_path.read_text(encoding="utf-8").strip()
        prompt_lines: list[str] = []
        if prompts_path.is_file():
            prompt_lines = [
                line.strip()
                for line in prompts_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        branded_or_final = branded_video_path or str(package_video)
        youtube_metadata = generate_and_save_youtube_metadata(
            publish_dir=package_dir,
            topic=topic,
            channel_profile=channel_profile,
            narration_script=narration_script,
            prompts=prompt_lines,
            duration_seconds=metadata.get("duration_seconds") or audio_post_result.get("duration_seconds"),
            clip_count=clip_count,
            platform_targets=list(channel_profile.get("upload_platforms") or []),
            final_video_path=branded_or_final,
        )
        youtube_metadata_path = str(
            youtube_metadata.get("metadata_path") or (package_dir / "youtube_metadata.json")
        )
        metadata["youtube_metadata_path"] = youtube_metadata_path
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        warnings.append(f"youtube_metadata_generation_failed:{exc}")

    payload = {
        "version": POST_PROCESSOR_VERSION,
        "status": PUBLISH_CREATED,
        "final_video_path": str(package_video),
        "narrated_video_path": narrated_video_path,
        "branded_video_path": branded_video_path,
        "branding_status": str(branding_post_result.get("status") or ""),
        "music_status": str(audio_post_result.get("music_status") or branding_post_result.get("music_status") or ""),
        "subtitle_status": str(branding_post_result.get("subtitle_status") or audio_post_result.get("subtitle_status") or ""),
        "branding_steps": dict(branding_post_result.get("steps") or {}),
        "package_folder": str(package_dir),
        "metadata_path": str(metadata_path),
        "youtube_metadata_path": youtube_metadata_path,
        "youtube_metadata": youtube_metadata,
        "prompts_path": str(prompts_path),
        "subtitle_paths": [str(srt_path), str(vtt_path)],
        "narration_script_path": str(narration_script_path),
        "narration_audio_path": str(narration_audio_path) if audio_source.is_file() else "",
        "narration_plan_path": str(narration_plan_path),
        "narration_provider": str(audio_post_result.get("narration_provider") or ""),
        "voice_id": str(audio_post_result.get("voice_id") or ""),
        "duration_seconds": audio_post_result.get("duration_seconds"),
        "warnings": warnings,
        "created_at": _now(),
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def apply_post_processing_result(report: Any, result: dict[str, Any]) -> None:
    _set_report_value(report, "post_processing_enabled", bool(result.get("enabled", False)))
    _set_report_value(report, "post_processing_status", str(result.get("status") or ""))
    _set_report_value(report, "assembly_status", str(result.get("assembly_status") or ""))
    _set_report_value(report, "final_video_path", str(result.get("final_video_path") or ""))
    _set_report_value(report, "publish_package_status", str(result.get("publish_package_status") or ""))
    _set_report_value(report, "publish_package_folder", str(result.get("publish_package_folder") or ""))
    _set_report_value(report, "visual_continuity_status", str(result.get("visual_continuity_status") or ""))
    _set_report_value(report, "visual_continuity_report_path", str(result.get("visual_continuity_report_path") or ""))
    _set_report_value(report, "visual_continuity_overall_pass", bool(result.get("visual_continuity_overall_pass")))
    _set_report_value(report, "visual_continuity_overall_score", float(result.get("visual_continuity_overall_score") or 0.0))
    _set_report_value(report, "branding_status", str(result.get("branding_status") or ""))
    _set_report_value(report, "final_branded_video_path", str(result.get("final_branded_video_path") or ""))
    _set_report_value(report, "versioned_run_dir", str(result.get("versioned_run_dir") or ""))
    _set_report_value(report, "delivery_status", str(result.get("delivery_status") or ""))
    _set_report_value(report, "delivery_gate_failures", list(result.get("delivery_gate_failures") or []))
    _set_report_value(report, "canonical_deliverable_path", str(result.get("canonical_deliverable_path") or ""))
    warnings = list(result.get("warnings") or [])
    existing = list(_report_value(report, "post_processing_warnings", []) or [])
    _set_report_value(report, "post_processing_warnings", existing + warnings)


def run_live_post_processing(report: Any, project_root: Path | None = None) -> dict[str, Any]:
    """
    Execute checkpoint → assembly → publish package for a successful live Runway report.

    Safe to call on ineligible reports — returns a skipped result without raising.
    """
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    eligible, reason, context = evaluate_post_processing_eligibility(report)
    warnings: list[str] = []

    if not eligible:
        result = {
            "version": POST_PROCESSOR_VERSION,
            "enabled": False,
            "status": STATUS_SKIPPED,
            "reason": reason,
            "assembly_status": "",
            "final_video_path": "",
            "publish_package_status": "",
            "publish_package_folder": "",
            "checkpoint_path": "",
            "assembly_manifest_path": "",
            "publish_manifest_path": "",
            "warnings": warnings,
        }
        apply_post_processing_result(report, result)
        return result

    clip_count = int(context["clip_count"])
    downloaded_paths = list(context["downloaded_file_paths"])
    run_id = str(context["run_id"])
    topic = str(context["topic"])
    clips_generated = int(context["clips_generated"])
    clips_downloaded = int(context["clips_downloaded"])
    checkpoint_created_at = _now()

    run_layout = create_versioned_run_layout(root, run_id=run_id, topic=topic)
    write_raw_downloads_manifest(run_layout, downloaded_paths)

    checkpoint_path = write_runway_phase_i_checkpoint(
        root,
        run_id=run_id,
        topic=topic,
        clip_count=clip_count,
        clips_generated=clips_generated,
        clips_downloaded=clips_downloaded,
        downloaded_file_paths=downloaded_paths,
        checkpoint=CHECKPOINT_STARTED,
        simulate=False,
        created_at=checkpoint_created_at,
    )

    visual_continuity_result: dict[str, Any] = {}
    try:
        visual_continuity_result = run_visual_continuity_verification(
            project_root=root,
            topic=topic,
            clip_video_paths=downloaded_paths,
            run_id=run_id,
        )
        if not visual_continuity_result.get("overall_pass"):
            warnings.append("visual_continuity_failed")
        warnings.extend(list(visual_continuity_result.get("warnings") or []))
    except Exception as exc:
        warnings.append(f"visual_continuity_error:{exc}")

    assembly_manifest = run_assembly(
        root,
        input_files=downloaded_paths,
        clip_count=clip_count,
        output_path=run_layout.final_video_path,
    )
    assembly_status = str(assembly_manifest.get("status") or "")
    if assembly_status == ASSEMBLY_PLAN_ONLY:
        warnings.append("ffmpeg_unavailable_assembly_plan_only")
    elif assembly_status == ASSEMBLY_FAILED:
        warnings.append(f"assembly_failed:{assembly_manifest.get('error') or 'unknown'}")

    write_runway_phase_i_checkpoint(
        root,
        run_id=run_id,
        topic=topic,
        clip_count=clip_count,
        clips_generated=clips_generated,
        clips_downloaded=clips_downloaded,
        downloaded_file_paths=downloaded_paths,
        checkpoint=CHECKPOINT_ASSEMBLY,
        simulate=False,
        created_at=checkpoint_created_at,
    )

    audio_post_result: dict[str, Any] = {}
    from content_brain.execution.product_audio_source import use_elevenlabs_narration

    if use_elevenlabs_narration(root):
        audio_post_result = run_audio_post_processing(
            project_root=root,
            report=report,
            assembly_manifest=assembly_manifest,
            run_dir=run_layout.run_dir,
        )
    else:
        audio_post_result = {"status": "skipped_runway_native", "narrated_video_path": str(assembly_manifest.get("output_path") or "")}
    audio_status = str(audio_post_result.get("status") or "")
    if audio_status not in {"completed", "skipped_provider_disabled", "skipped_assembly_not_ready", "skipped_runway_native"}:
        warnings.append(f"audio_post_processing:{audio_status}")
    warnings.extend(list(audio_post_result.get("warnings") or []))

    branding_post_result = run_branding_runtime(
        project_root=root,
        report=report,
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        output_dir=run_layout.final_dir,
    )
    branding_status = str(branding_post_result.get("status") or "")
    if branding_status not in {"completed", "skipped_branding_disabled"}:
        warnings.append(f"branding_runtime:{branding_status}")
    warnings.extend(list(branding_post_result.get("warnings") or []))

    publish_manifest = run_publish_package(
        root,
        assembly_manifest=assembly_manifest,
        run_id=run_id,
        topic=topic,
        clip_count=clip_count,
        downloaded_file_paths=downloaded_paths,
        audio_post_result=audio_post_result,
        branding_post_result=branding_post_result,
        package_dir=run_layout.publish_dir,
    )
    publish_status = str(publish_manifest.get("status") or "")
    warnings.extend(list(publish_manifest.get("warnings") or []))

    channel_profile = ProductChannelProfileStore(root).load()
    delivery_result = evaluate_delivery_quality(
        project_root=root,
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        branding_post_result=branding_post_result,
        publish_manifest=publish_manifest,
        channel_profile=channel_profile,
    )
    write_delivery_quality_gate(root, delivery_result, run_dir=run_layout.run_dir)
    delivery_status = delivery_result.delivery_status
    delivery_failures = list(delivery_result.failures)
    if delivery_failures:
        warnings.append(f"delivery_gate:{','.join(delivery_failures)}")
    warnings.extend(list(delivery_result.warnings))

    canonical_video = str(
        delivery_result.canonical_video_path
        or branding_post_result.get("final_branded_video_path")
        or assembly_manifest.get("output_path")
        or ""
    )
    quality_pipeline: dict[str, Any] = {"skipped": True, "reason": "no_canonical_video"}
    if canonical_video:
        from content_brain.quality.video_quality_judge import run_post_processing_quality_pipeline

        quality_pipeline = run_post_processing_quality_pipeline(
            project_root=root,
            run_dir=run_layout.run_dir,
            run_id=run_id,
            video_path=canonical_video,
            topic=topic,
            clip_count=clip_count,
        )
        if quality_pipeline.get("skipped"):
            warnings.append(f"video_quality_judge:{quality_pipeline.get('reason')}")

    publish_checkpoint = CHECKPOINT_PUBLISH if delivery_status != DELIVERY_FAIL else CHECKPOINT_DELIVERY_BLOCKED
    write_runway_phase_i_checkpoint(
        root,
        run_id=run_id,
        topic=topic,
        clip_count=clip_count,
        clips_generated=clips_generated,
        clips_downloaded=clips_downloaded,
        downloaded_file_paths=downloaded_paths,
        checkpoint=publish_checkpoint,
        simulate=False,
        created_at=checkpoint_created_at,
        delivery_status=delivery_status,
        delivery_failures=delivery_failures,
    )

    overall_status = STATUS_COMPLETED
    if assembly_status == ASSEMBLY_FAILED:
        overall_status = STATUS_FAILED
    elif delivery_status == DELIVERY_FAIL:
        overall_status = STATUS_FAILED
    elif assembly_status == ASSEMBLY_PLAN_ONLY:
        overall_status = STATUS_COMPLETED

    version_summary = finalize_versioned_run_layout(
        root,
        run_layout,
        assembly_manifest=assembly_manifest,
        publish_manifest=publish_manifest,
        visual_continuity_report=visual_continuity_result or None,
    )

    result = {
        "version": POST_PROCESSOR_VERSION,
        "enabled": True,
        "status": overall_status,
        "reason": reason,
        "assembly_status": assembly_status,
        "final_video_path": str(assembly_manifest.get("output_path") or ""),
        "publish_package_status": publish_status,
        "publish_package_folder": str(publish_manifest.get("package_folder") or ""),
        "checkpoint_path": str(checkpoint_path),
        "assembly_manifest_path": str(_assembly_manifest_path(root)),
        "publish_manifest_path": str(_publish_manifest_path(root)),
        "audio_post_processing_status": audio_status,
        "narrated_video_path": str(audio_post_result.get("narrated_video_path") or ""),
        "narration_provider": str(audio_post_result.get("narration_provider") or ""),
        "branding_status": branding_status,
        "final_branded_video_path": str(branding_post_result.get("final_branded_video_path") or ""),
        "branding_steps": dict(branding_post_result.get("steps") or {}),
        "visual_continuity_status": str(visual_continuity_result.get("status") or ("completed" if visual_continuity_result else "skipped")),
        "visual_continuity_report_path": str(visual_continuity_result.get("report_path") or ""),
        "visual_continuity_overall_pass": bool(visual_continuity_result.get("overall_pass")),
        "visual_continuity_overall_score": visual_continuity_result.get("overall_score"),
        "versioned_run_dir": str(run_layout.run_dir),
        "versioned_run_summary": version_summary,
        "delivery_status": delivery_status,
        "delivery_gate_failures": delivery_failures,
        "canonical_deliverable_path": str(delivery_result.canonical_video_path or branding_post_result.get("final_branded_video_path") or ""),
        "assembled_duration_seconds": delivery_result.assembled_duration_seconds,
        "deliverable_duration_seconds": delivery_result.deliverable_duration_seconds,
        "warnings": warnings,
        "report_snapshot": _report_to_dict(report),
        "video_quality_judge": dict(quality_pipeline.get("judge") or {}),
        "video_quality_judge_path": str(quality_pipeline.get("video_quality_judge_path") or ""),
        "video_quality_learning_proposed": bool(quality_pipeline.get("proposed_updates_path")),
        "video_quality_proposed_updates_path": str(quality_pipeline.get("proposed_updates_path") or ""),
    }
    apply_post_processing_result(report, result)
    return result


__all__ = [
    "POST_PROCESSOR_VERSION",
    "apply_post_processing_result",
    "collect_valid_download_paths",
    "evaluate_post_processing_eligibility",
    "run_assembly",
    "run_live_post_processing",
    "run_publish_package",
    "write_runway_phase_i_checkpoint",
]
