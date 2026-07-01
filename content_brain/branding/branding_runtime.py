"""Branding runtime orchestrator — runs after audio merge, before publish package."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.audio.audio_merge_engine import NARRATED_VIDEO_NAME
from content_brain.branding.cta_engine import CTA_FREQUENCY_END, apply_cta_overlay, resolve_cta_text
from content_brain.branding.intro_outro_engine import generate_intro_card, generate_outro_card, merge_intro_outro
from content_brain.branding.logo_overlay_engine import apply_logo_overlay
from content_brain.branding.subtitle_burn_engine import SUBTITLED_VIDEO_NAME, SUBTITLE_STYLE_TIKTOK, burn_subtitles
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

BRANDING_RUNTIME_VERSION = "branding_runtime_v1"
FINAL_BRANDED_VIDEO_NAME = "FINAL_BRANDED_VIDEO.mp4"
FINAL_BRANDED_VIDEO_CANONICAL_NAME = "FINAL_BRANDED_VIDEO_CANONICAL.mp4"
FINAL_BRANDED_VIDEO_V2_NAME = "FINAL_BRANDED_VIDEO_v2.mp4"
FINAL_BRANDED_VIDEO_V3_NAME = "FINAL_BRANDED_VIDEO_v3.mp4"
FINAL_BRANDED_VIDEO_V4_NAME = "FINAL_BRANDED_VIDEO_v4.mp4"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
ASSEMBLY_ASSEMBLED = "ASSEMBLED"
STEP_PASS = "PASS"
STEP_SKIP = "SKIP"
STEP_FAIL = "FAIL"


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _manifest_path(project_root: Path) -> Path:
    return project_root / "project_brain" / "runtime_state" / "runway_phase_i_branding_manifest.json"


def _step_status(result_status: str) -> str:
    if result_status in {"COMPLETED", "MERGED"}:
        return STEP_PASS
    if result_status in {"SKIPPED", "PLAN_ONLY"}:
        return STEP_SKIP
    return STEP_FAIL


def _branding_settings(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "branding_enabled": bool(profile.get("branding_enabled", True)),
        "logo_enabled": bool(profile.get("logo_enabled", True)),
        "logo_position": str(profile.get("logo_position") or "top_right"),
        "logo_scale": float(profile.get("logo_scale") or 0.12),
        "subtitle_enabled": bool(profile.get("subtitle_enabled", True)),
        "subtitle_style": str(profile.get("subtitle_style") or SUBTITLE_STYLE_TIKTOK),
        "subtitle_position": str(profile.get("subtitle_position") or "lower_third"),
        "cta_enabled": bool(profile.get("cta_enabled", True)),
        "cta_text": str(profile.get("cta_text") or "Follow for more"),
        "cta_position": str(profile.get("cta_position") or "bottom_center"),
        "cta_preset": str(profile.get("cta_preset") or "follow_for_more"),
        "cta_custom_slogan": str(profile.get("cta_custom_slogan") or ""),
        "cta_frequency": str(profile.get("cta_frequency") or CTA_FREQUENCY_END),
        "intro_enabled": bool(profile.get("intro_enabled", False)),
        "intro_text": str(profile.get("intro_text") or profile.get("channel_name") or ""),
        "intro_duration": float(profile.get("intro_duration") or 2.0),
        "outro_enabled": bool(profile.get("outro_enabled", False)),
        "outro_text": str(profile.get("outro_text") or "Follow for more"),
        "outro_duration": float(profile.get("outro_duration") or 2.0),
    }


def run_branding_runtime(
    *,
    project_root: str | Path,
    report: Any,
    assembly_manifest: dict[str, Any],
    audio_post_result: dict[str, Any] | None = None,
    output_dir: str | Path | None = None,
    ffmpeg_probe: Any | None = None,
    branded_video_name: str = FINAL_BRANDED_VIDEO_CANONICAL_NAME,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    profile = ProductChannelProfileStore(root).load()
    settings = _branding_settings(profile)
    audio_post_result = dict(audio_post_result or {})
    assembly_status = str(assembly_manifest.get("status") or "")
    assembly_video = Path(str(assembly_manifest.get("output_path") or root / "outputs" / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"))
    narrated = Path(str(audio_post_result.get("narrated_video_path") or ""))
    source_video = narrated if narrated.is_file() and narrated.stat().st_size > 0 else assembly_video
    work_dir = Path(output_dir or source_video.parent).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    base = {
        "version": BRANDING_RUNTIME_VERSION,
        "status": "skipped",
        "branding_enabled": settings["branding_enabled"],
        "branded_video_name": branded_video_name,
        "final_branded_video_path": "",
        "subtitled_video_path": "",
        "intro_video_path": "",
        "outro_video_path": "",
        "steps": {
            "subtitles": {"status": STEP_SKIP},
            "logo": {"status": STEP_SKIP},
            "cta": {"status": STEP_SKIP},
            "intro": {"status": STEP_SKIP},
            "outro": {"status": STEP_SKIP},
        },
        "settings": settings,
        "cta_suggestions": [],
        "cta_suggestion_source": "",
        "warnings": [],
        "created_at": _now(),
    }

    if assembly_status != ASSEMBLY_ASSEMBLED or not source_video.is_file() or source_video.stat().st_size <= 0:
        base["status"] = "skipped_assembly_not_ready"
        base["warnings"].append("assembly_not_assembled")
        _write_manifest(root, base)
        return base

    if not settings["branding_enabled"]:
        branded = work_dir / branded_video_name
        shutil.copy2(source_video, branded)
        base["status"] = "skipped_branding_disabled"
        base["final_branded_video_path"] = str(branded.resolve())
        _write_manifest(root, base)
        return base

    current_video = source_video
    staging = work_dir / "branding_staging"
    staging.mkdir(parents=True, exist_ok=True)

    subtitle_paths = [str(item) for item in (audio_post_result.get("subtitle_paths") or []) if item]
    styled_ass = str(audio_post_result.get("styled_ass_path") or "")
    subtitle_file = Path(styled_ass) if styled_ass else Path(subtitle_paths[0] if subtitle_paths else "")
    if settings["subtitle_enabled"] and subtitle_file.is_file():
        subtitled_out = staging / SUBTITLED_VIDEO_NAME
        subtitle_result = burn_subtitles(
            input_video_path=current_video,
            subtitle_path=subtitle_file,
            output_path=subtitled_out,
            subtitle_style=settings["subtitle_style"],
            subtitle_position=settings["subtitle_position"],
            ffmpeg_probe=ffmpeg_probe,
        )
        burn_meta = dict(subtitle_result.metadata or {})
        step_payload = subtitle_result.to_dict()
        step_payload["burn_visible_enough"] = burn_meta.get("burn_visible_enough")
        step_payload["burn_psnr_avg"] = burn_meta.get("burn_psnr_avg")
        step_payload["font_size"] = burn_meta.get("font_size")
        base["steps"]["subtitles"] = step_payload
        base["steps"]["subtitles"]["status"] = _step_status(subtitle_result.status)
        if subtitle_result.status == "COMPLETED" and burn_meta.get("burn_visible_enough"):
            base["subtitle_status"] = "Subtitle: PASS — visible lower-third subtitles burned"
        elif subtitle_result.status == "COMPLETED":
            base["subtitle_status"] = "Subtitle: FAILED — burn ran but text not visible"
            base["status"] = "failed"
            base["warnings"].append("subtitle_burn_not_visible")
        elif subtitle_result.status == "SKIPPED":
            base["subtitle_status"] = "Subtitle: SKIPPED — subtitle file missing"
        else:
            base["subtitle_status"] = "Subtitle: FAILED — burn failed"
        if subtitle_result.status == "COMPLETED" and burn_meta.get("burn_visible_enough"):
            current_video = Path(subtitle_result.output_path)
            base["subtitled_video_path"] = subtitle_result.output_path
        elif subtitle_result.status == "COMPLETED":
            base["warnings"].append("subtitle_burn_not_visible")
            base["status"] = "failed"
        elif subtitle_result.status == "FAILED":
            base["warnings"].append(f"subtitle_burn_failed:{subtitle_result.error}")
            base["status"] = "failed"
    elif settings["subtitle_enabled"]:
        base["steps"]["subtitles"]["status"] = STEP_SKIP
        base["subtitle_status"] = "Subtitle: SKIPPED — subtitle source missing"
        base["warnings"].append("subtitle_source_missing")

    if settings["logo_enabled"]:
        logo_out = staging / "logo_overlay.mp4"
        logo_result = apply_logo_overlay(
            project_root=root,
            input_video_path=current_video,
            output_path=logo_out,
            logo_position=settings["logo_position"],
            logo_scale=settings["logo_scale"],
            ffmpeg_probe=ffmpeg_probe,
        )
        base["steps"]["logo"] = logo_result.to_dict()
        base["steps"]["logo"]["status"] = _step_status(logo_result.status)
        if logo_result.status == "COMPLETED":
            current_video = Path(logo_result.output_path)
        elif logo_result.status == "FAILED":
            base["warnings"].append(f"logo_overlay_failed:{logo_result.error}")

    cta_text, suggestions, suggestion_source = resolve_cta_text(
        profile=profile,
        channel_name=str(profile.get("channel_name") or ""),
        platform=str(profile.get("default_platform") or "tiktok"),
        topic=str(getattr(report, "content_brain_topic", "") if not isinstance(report, dict) else report.get("content_brain_topic") or ""),
        use_openai=True,
    )
    if settings.get("cta_preset") == "custom" and settings.get("cta_custom_slogan"):
        cta_text = str(settings["cta_custom_slogan"])
    elif settings.get("cta_text"):
        cta_text = str(settings["cta_text"])
    base["cta_suggestions"] = suggestions
    base["cta_suggestion_source"] = suggestion_source

    if settings["cta_enabled"] and cta_text:
        cta_out = staging / "cta_overlay.mp4"
        cta_result = apply_cta_overlay(
            input_video_path=current_video,
            output_path=cta_out,
            cta_text=cta_text,
            cta_position=settings["cta_position"],
            cta_frequency=settings["cta_frequency"],
            duration_seconds=float(audio_post_result.get("duration_seconds") or 30.0),
            ffmpeg_probe=ffmpeg_probe,
        )
        base["steps"]["cta"] = cta_result.to_dict()
        base["steps"]["cta"]["status"] = _step_status(cta_result.status)
        if cta_result.status == "COMPLETED":
            current_video = Path(cta_result.output_path)
        elif cta_result.status == "FAILED":
            base["warnings"].append(f"cta_overlay_failed:{cta_result.error}")

    intro_path = ""
    outro_path = ""
    if settings["intro_enabled"] and settings["intro_text"].strip():
        intro_result = generate_intro_card(
            output_dir=staging,
            intro_text=settings["intro_text"],
            intro_duration=settings["intro_duration"],
            ffmpeg_probe=ffmpeg_probe,
        )
        base["steps"]["intro"] = intro_result.to_dict()
        base["steps"]["intro"]["status"] = _step_status(intro_result.status)
        if intro_result.status == "COMPLETED":
            intro_path = intro_result.output_path
            base["intro_video_path"] = intro_path
        elif intro_result.status == "FAILED":
            base["warnings"].append(f"intro_failed:{intro_result.error}")

    if settings["outro_enabled"] and settings["outro_text"].strip():
        outro_result = generate_outro_card(
            output_dir=staging,
            outro_text=settings["outro_text"],
            outro_duration=settings["outro_duration"],
            ffmpeg_probe=ffmpeg_probe,
        )
        base["steps"]["outro"] = outro_result.to_dict()
        base["steps"]["outro"]["status"] = _step_status(outro_result.status)
        if outro_result.status == "COMPLETED":
            outro_path = outro_result.output_path
            base["outro_video_path"] = outro_path
        elif outro_result.status == "FAILED":
            base["warnings"].append(f"outro_failed:{outro_result.error}")

    branded_out = work_dir / branded_video_name
    if intro_path or outro_path:
        merge_result = merge_intro_outro(
            intro_path=intro_path or None,
            main_video_path=current_video,
            outro_path=outro_path or None,
            output_path=branded_out,
            ffmpeg_probe=ffmpeg_probe,
        )
        base["steps"]["intro_outro_merge"] = merge_result.to_dict()
        if merge_result.status == "COMPLETED":
            base["final_branded_video_path"] = merge_result.output_path
        else:
            shutil.copy2(current_video, branded_out)
            base["final_branded_video_path"] = str(branded_out.resolve())
            if merge_result.status == "FAILED":
                base["warnings"].append(f"intro_outro_merge_failed:{merge_result.error}")
    else:
        shutil.copy2(current_video, branded_out)
        base["final_branded_video_path"] = str(branded_out.resolve())

    if base.get("status") != "failed":
        base["status"] = "completed"
    base["music_status"] = str((audio_post_result or {}).get("music_status") or "")
    _write_manifest(root, base)
    return base


def _write_manifest(project_root: Path, payload: dict[str, Any]) -> None:
    path = _manifest_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


__all__ = [
    "BRANDING_RUNTIME_VERSION",
    "FINAL_BRANDED_VIDEO_CANONICAL_NAME",
    "FINAL_BRANDED_VIDEO_NAME",
    "FINAL_BRANDED_VIDEO_V2_NAME",
    "FINAL_BRANDED_VIDEO_V3_NAME",
    "FINAL_BRANDED_VIDEO_V4_NAME",
    "run_branding_runtime",
]
