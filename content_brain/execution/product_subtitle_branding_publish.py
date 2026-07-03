"""Product Studio subtitle, branding, and publish package runtime."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.branding.branding_runtime import _branding_settings
from content_brain.branding.cta_engine import CTA_FREQUENCY_END, apply_cta_overlay, resolve_cta_text
from content_brain.branding.intro_outro_engine import generate_intro_card, generate_outro_card, merge_intro_outro
from content_brain.branding.logo_overlay_engine import apply_logo_overlay
from content_brain.branding.subtitle_burn_engine import SUBTITLED_VIDEO_NAME, burn_subtitles
from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability
from content_brain.execution.product_assembly_bridge import FINAL_PUBLISH_READY_NAME
from content_brain.execution.pwmap_runway_agent_adapter import validate_mp4_path
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.publish.youtube_metadata_generator import YOUTUBE_METADATA_FILENAME

PRODUCT_SUBTITLE_BRANDING_PUBLISH_VERSION = "product_subtitle_branding_publish_v1"
FINAL_BRANDED_PUBLISH_READY_NAME = "FINAL_BRANDED_PUBLISH_READY.mp4"
BRANDING_MANIFEST_NAME = "branding_manifest.json"
PUBLISH_PACKAGE_NAME = "publish_package.json"

STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "branding_failed"
STATUS_DISABLED = "disabled"

SUBTITLE_MODE_NONE = "none"
SUBTITLE_MODE_GENERATED = "generated"
SUBTITLE_MODE_EXTERNAL = "external"
SUBTITLE_MODE_BURN_IN = "burn_in"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_settings(
    channel_profile: dict[str, Any],
    *,
    preflight: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preflight = dict(preflight or {})
    overrides = dict(overrides or {})
    base = _branding_settings(channel_profile)
    subtitle_mode = str(
        overrides.get("subtitle_mode")
        or preflight.get("subtitle_mode")
        or channel_profile.get("subtitle_mode")
        or (SUBTITLE_MODE_BURN_IN if base["subtitle_enabled"] else SUBTITLE_MODE_NONE)
    ).lower()
    if subtitle_mode not in {SUBTITLE_MODE_NONE, SUBTITLE_MODE_GENERATED, SUBTITLE_MODE_EXTERNAL, SUBTITLE_MODE_BURN_IN}:
        subtitle_mode = SUBTITLE_MODE_NONE if not base["subtitle_enabled"] else SUBTITLE_MODE_BURN_IN

    resolved = {
        **base,
        "subtitle_mode": subtitle_mode,
        "watermark_enabled": bool(
            overrides.get("watermark_enabled", channel_profile.get("watermark_enabled", base["logo_enabled"]))
        ),
        "logo_enabled": bool(overrides.get("logo_enabled", base["logo_enabled"])),
        "cta_enabled": bool(overrides.get("cta_enabled", channel_profile.get("cta_enabled", base["cta_enabled"]))),
        "intro_enabled": bool(overrides.get("intro_enabled", base["intro_enabled"])),
        "outro_enabled": bool(overrides.get("outro_enabled", base["outro_enabled"])),
        "intro_text": str(overrides.get("intro_text") or base.get("intro_text") or ""),
        "outro_text": str(overrides.get("outro_text") or base.get("outro_text") or ""),
        "audio_normalization_enabled": bool(
            overrides.get("audio_normalization_enabled", channel_profile.get("audio_normalization_enabled", False))
        ),
        "loudness_normalization_enabled": bool(
            overrides.get("loudness_normalization_enabled", channel_profile.get("loudness_normalization_enabled", False))
        ),
        "dialogue_normalization_enabled": bool(
            overrides.get("dialogue_normalization_enabled", channel_profile.get("dialogue_normalization_enabled", False))
        ),
        "music_normalization_enabled": bool(
            overrides.get("music_normalization_enabled", channel_profile.get("music_normalization_enabled", False))
        ),
        "target_lufs": float(overrides.get("target_lufs") or channel_profile.get("target_lufs") or -14.0),
        "subtitle_language": str(
            overrides.get("subtitle_language")
            or channel_profile.get("subtitle_language")
            or channel_profile.get("language")
            or "en"
        ),
        "external_subtitle_path": str(
            overrides.get("external_subtitle_path")
            or preflight.get("external_subtitle_path")
            or channel_profile.get("external_subtitle_path")
            or ""
        ),
        "cta_position": str(
            overrides.get("cta_position")
            or preflight.get("cta_position")
            or channel_profile.get("cta_position")
            or base.get("cta_position")
            or "top_right"
        ),
        "cta_start_seconds": float(
            overrides.get("cta_start_seconds")
            or preflight.get("cta_start_seconds")
            or channel_profile.get("cta_start_seconds")
            or base.get("cta_start_seconds")
            or 5
        ),
        "cta_end_seconds": float(
            overrides.get("cta_end_seconds")
            or preflight.get("cta_end_seconds")
            or channel_profile.get("cta_end_seconds")
            or base.get("cta_end_seconds")
            or 24
        ),
    }
    return resolved


def _find_external_subtitle(publish_dir: Path, settings: dict[str, Any]) -> Path | None:
    explicit = str(settings.get("external_subtitle_path") or "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
    subtitles_dir = publish_dir / "subtitles"
    if subtitles_dir.is_dir():
        for pattern in ("*.ass", "*.srt", "*.vtt"):
            matches = sorted(subtitles_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def _generate_subtitle_file(*, publish_dir: Path, topic: str, language: str) -> Path:
    subtitles_dir = publish_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    target = subtitles_dir / "generated.srt"
    hook = re.sub(r"\s+", " ", str(topic or "Product Studio video").strip()) or "Product Studio video"
    lines = [
        "1",
        "00:00:00,000 --> 00:00:04,000",
        hook[:120],
        "",
        "2",
        "00:00:04,000 --> 00:00:08,000",
        "Follow for more.",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _count_subtitle_cues(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    if path.suffix.lower() == ".srt":
        return len(re.findall(r"^\d+\s*$", text, flags=re.MULTILINE))
    return max(1, text.count("\n") // 3)


def _apply_audio_normalization(
    *,
    input_video: Path,
    output_video: Path,
    settings: dict[str, Any],
    ffmpeg_probe: Any | None = None,
) -> dict[str, Any]:
    enabled = any(
        [
            settings.get("audio_normalization_enabled"),
            settings.get("loudness_normalization_enabled"),
            settings.get("dialogue_normalization_enabled"),
            settings.get("music_normalization_enabled"),
        ]
    )
    if not enabled:
        return {
            "audio_status": STATUS_SKIPPED,
            "lufs_value": None,
            "normalization_applied": False,
            "ok": True,
        }

    from content_brain.branding.branding_ffmpeg import run_ffmpeg_filter

    target_lufs = float(settings.get("target_lufs") or -14.0)
    filter_expr = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
    result = run_ffmpeg_filter(
        input_path=input_video,
        output_path=output_video,
        vf_filter="null",
        ffmpeg_probe=ffmpeg_probe,
        copy_audio=False,
        extra_args=["-af", filter_expr, "-c:v", "copy"],
    )
    if result.status != "COMPLETED" or not output_video.is_file():
        return {
            "audio_status": STATUS_FAILED,
            "lufs_value": target_lufs,
            "normalization_applied": False,
            "ok": False,
            "error": result.error or "audio_normalization_failed",
        }
    return {
        "audio_status": STATUS_COMPLETED,
        "lufs_value": target_lufs,
        "normalization_applied": True,
        "ok": True,
    }


def run_product_subtitle_branding_publish(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    run_id: str,
    topic: str,
    preflight: dict[str, Any] | None = None,
    settings_overrides: dict[str, Any] | None = None,
    ffmpeg_probe: Any | None = None,
) -> dict[str, Any]:
    """Transform publish/FINAL_PUBLISH_READY.mp4 into FINAL_BRANDED_PUBLISH_READY.mp4."""
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve()
    publish_dir = run_path / "publish"
    source_video = publish_dir / FINAL_PUBLISH_READY_NAME
    branded_output = publish_dir / FINAL_BRANDED_PUBLISH_READY_NAME
    staging = publish_dir / "branding_staging"
    staging.mkdir(parents=True, exist_ok=True)

    profile = ProductChannelProfileStore(root).load()
    settings = _resolve_settings(profile, preflight=preflight, overrides=settings_overrides)
    probe = ffmpeg_probe if ffmpeg_probe is not None else check_ffmpeg_availability()

    base_result: dict[str, Any] = {
        "ok": False,
        "publish_ready": False,
        "branding_status": STATUS_SKIPPED,
        "subtitle_status": STATUS_SKIPPED,
        "audio_status": STATUS_SKIPPED,
        "final_branded_publish_video_path": "",
        "final_publish_video_path": "",
        "publish_package_path": str(publish_dir.resolve()).replace("\\", "/"),
        "branding_layers": [],
        "logo_enabled": bool(settings.get("logo_enabled")),
        "cta_enabled": bool(settings.get("cta_enabled")),
        "intro_enabled": bool(settings.get("intro_enabled")),
        "outro_enabled": bool(settings.get("outro_enabled")),
        "watermark_enabled": bool(settings.get("watermark_enabled")),
        "subtitle_count": 0,
        "subtitle_language": settings.get("subtitle_language"),
        "lufs_value": None,
        "normalization_applied": False,
        "error": "",
    }

    if not source_video.is_file() or not validate_mp4_path(source_video)["valid"]:
        base_result["error"] = "final_publish_ready_missing"
        base_result["branding_status"] = STATUS_FAILED
        _write_failure_artifacts(
            publish_dir=publish_dir,
            run_id=run_id,
            source_video=source_video,
            result=base_result,
            settings=settings,
        )
        return base_result

    base_result["final_publish_video_path"] = str(source_video.resolve()).replace("\\", "/")
    source_snapshot = publish_dir / "_source_snapshot.mp4"
    if not source_snapshot.is_file() or source_snapshot.stat().st_size != source_video.stat().st_size:
        shutil.copy2(source_video, source_snapshot)

    current_video = source_video
    branding_layers: list[str] = []
    hard_failure = False
    subtitle_payload: dict[str, Any] = {
        "subtitle_status": STATUS_DISABLED if settings["subtitle_mode"] == SUBTITLE_MODE_NONE else STATUS_SKIPPED,
        "subtitle_count": 0,
        "subtitle_language": settings.get("subtitle_language"),
    }

    subtitle_mode = settings["subtitle_mode"]
    subtitle_file: Path | None = None
    if subtitle_mode == SUBTITLE_MODE_EXTERNAL:
        subtitle_file = _find_external_subtitle(publish_dir, settings)
    elif subtitle_mode == SUBTITLE_MODE_GENERATED:
        subtitle_file = _generate_subtitle_file(
            publish_dir=publish_dir,
            topic=topic,
            language=str(settings.get("subtitle_language") or "en"),
        )
    elif subtitle_mode == SUBTITLE_MODE_BURN_IN:
        subtitle_file = _find_external_subtitle(publish_dir, settings) or _generate_subtitle_file(
            publish_dir=publish_dir,
            topic=topic,
            language=str(settings.get("subtitle_language") or "en"),
        )

    if subtitle_mode in {SUBTITLE_MODE_GENERATED, SUBTITLE_MODE_EXTERNAL} and subtitle_file:
        subtitle_payload["subtitle_status"] = STATUS_COMPLETED
        subtitle_payload["subtitle_count"] = _count_subtitle_cues(subtitle_file)
        branding_layers.append("subtitles_file")

    if subtitle_mode == SUBTITLE_MODE_BURN_IN and subtitle_file and subtitle_file.is_file():
        subtitled_out = staging / SUBTITLED_VIDEO_NAME
        burn = burn_subtitles(
            input_video_path=current_video,
            subtitle_path=subtitle_file,
            output_path=subtitled_out,
            subtitle_style=settings["subtitle_style"],
            subtitle_position=settings["subtitle_position"],
            ffmpeg_probe=probe,
        )
        subtitle_payload["subtitle_count"] = _count_subtitle_cues(subtitle_file)
        if burn.status == "COMPLETED" and subtitled_out.is_file():
            current_video = subtitled_out
            subtitle_payload["subtitle_status"] = STATUS_COMPLETED
            branding_layers.append("subtitles_burn_in")
        else:
            subtitle_payload["subtitle_status"] = STATUS_FAILED
            hard_failure = True
            base_result["error"] = burn.error or "subtitle_burn_failed"
    elif subtitle_mode == SUBTITLE_MODE_NONE:
        subtitle_payload["subtitle_status"] = STATUS_DISABLED

    if settings.get("logo_enabled") or settings.get("watermark_enabled"):
        logo_out = staging / "logo_overlay.mp4"
        logo = apply_logo_overlay(
            project_root=root,
            input_video_path=current_video,
            output_path=logo_out,
            logo_position=settings["logo_position"],
            logo_scale=settings["logo_scale"],
            ffmpeg_probe=probe,
        )
        if logo.status == "COMPLETED" and logo_out.is_file():
            current_video = logo_out
            branding_layers.append("logo" if settings.get("logo_enabled") else "watermark")
        elif logo.status == "FAILED":
            hard_failure = True
            base_result["error"] = logo.error or "logo_overlay_failed"
        else:
            branding_layers.append("logo_skipped")

    cta_text = str(settings.get("cta_text") or "")
    if settings.get("cta_enabled"):
        if not cta_text:
            cta_text, _, _ = resolve_cta_text(
                profile=profile,
                channel_name=str(profile.get("channel_name") or ""),
                platform=str(profile.get("default_platform") or "youtube_shorts"),
                topic=topic,
                use_openai=False,
            )
        if cta_text:
            cta_out = staging / "cta_overlay.mp4"
            cta = apply_cta_overlay(
                input_video_path=current_video,
                output_path=cta_out,
                cta_text=cta_text,
                cta_position=settings["cta_position"],
                cta_frequency=settings.get("cta_frequency") or CTA_FREQUENCY_END,
                cta_start_seconds=settings.get("cta_start_seconds"),
                cta_end_seconds=settings.get("cta_end_seconds"),
                duration_seconds=float(settings.get("cta_end_seconds") or 30.0),
                ffmpeg_probe=probe,
            )
            if cta.status == "COMPLETED" and cta_out.is_file():
                current_video = cta_out
                branding_layers.append("cta")
            elif cta.status == "FAILED":
                hard_failure = True
                base_result["error"] = cta.error or "cta_overlay_failed"

    intro_path = ""
    outro_path = ""
    if settings.get("intro_enabled") and str(settings.get("intro_text") or "").strip():
        intro = generate_intro_card(
            output_dir=staging,
            intro_text=str(settings["intro_text"]),
            intro_duration=float(settings.get("intro_duration") or 2.0),
            ffmpeg_probe=probe,
        )
        if intro.status == "COMPLETED":
            intro_path = intro.output_path
            branding_layers.append("intro")
        elif intro.status == "FAILED":
            hard_failure = True
            base_result["error"] = intro.error or "intro_failed"

    if settings.get("outro_enabled") and str(settings.get("outro_text") or "").strip():
        outro = generate_outro_card(
            output_dir=staging,
            outro_text=str(settings["outro_text"]),
            outro_duration=float(settings.get("outro_duration") or 2.0),
            ffmpeg_probe=probe,
        )
        if outro.status == "COMPLETED":
            outro_path = outro.output_path
            branding_layers.append("outro")
        elif outro.status == "FAILED":
            hard_failure = True
            base_result["error"] = outro.error or "outro_failed"

    audio_payload: dict[str, Any] = {
        "audio_status": STATUS_SKIPPED,
        "lufs_value": None,
        "normalization_applied": False,
    }
    if not hard_failure:
        merged_video = staging / "branded_pre_audio.mp4"
        if intro_path or outro_path:
            merge = merge_intro_outro(
                intro_path=intro_path or None,
                main_video_path=current_video,
                outro_path=outro_path or None,
                output_path=merged_video,
                ffmpeg_probe=probe,
            )
            if merge.status == "COMPLETED" and merged_video.is_file():
                current_video = merged_video
            elif merge.status == "FAILED":
                hard_failure = True
                base_result["error"] = merge.error or "intro_outro_merge_failed"
            else:
                shutil.copy2(current_video, merged_video)
                current_video = merged_video
        else:
            shutil.copy2(current_video, merged_video)
            current_video = merged_video

        audio_out = staging / "audio_normalized.mp4"
        audio_payload = _apply_audio_normalization(
            input_video=current_video,
            output_video=audio_out,
            settings=settings,
            ffmpeg_probe=probe,
        )
        if audio_payload.get("ok") and audio_payload.get("normalization_applied") and audio_out.is_file():
            current_video = audio_out
            branding_layers.append("audio_normalization")
        elif not audio_payload.get("ok") and audio_payload.get("audio_status") == STATUS_FAILED:
            hard_failure = True
            base_result["error"] = audio_payload.get("error") or "audio_normalization_failed"

    if hard_failure:
        if source_video.stat().st_size != source_snapshot.stat().st_size:
            shutil.copy2(source_snapshot, source_video)
        base_result.update(
            {
                "ok": False,
                "publish_ready": False,
                "branding_status": STATUS_FAILED,
                "subtitle_status": subtitle_payload.get("subtitle_status"),
                "audio_status": audio_payload.get("audio_status"),
                "branding_layers": branding_layers,
                "subtitle_count": subtitle_payload.get("subtitle_count", 0),
                "lufs_value": audio_payload.get("lufs_value"),
                "normalization_applied": bool(audio_payload.get("normalization_applied")),
            }
        )
        _write_failure_artifacts(
            publish_dir=publish_dir,
            run_id=run_id,
            source_video=source_video,
            result=base_result,
            settings=settings,
            subtitle_payload=subtitle_payload,
            audio_payload=audio_payload,
        )
        if branded_output.is_file():
            branded_output.unlink()
        return base_result

    shutil.copy2(current_video, branded_output)
    if not validate_mp4_path(branded_output)["valid"]:
        base_result["error"] = "branded_output_invalid"
        base_result["branding_status"] = STATUS_FAILED
        _write_failure_artifacts(
            publish_dir=publish_dir,
            run_id=run_id,
            source_video=source_video,
            result=base_result,
            settings=settings,
        )
        return base_result

    branding_status = STATUS_COMPLETED if branding_layers else STATUS_SKIPPED
    youtube_exists = (publish_dir / YOUTUBE_METADATA_FILENAME).is_file()
    final_branded = str(branded_output.resolve()).replace("\\", "/")
    result = {
        "ok": True,
        "publish_ready": True,
        "branding_status": branding_status,
        "subtitle_status": subtitle_payload.get("subtitle_status"),
        "audio_status": audio_payload.get("audio_status"),
        "final_branded_publish_video_path": final_branded,
        "final_publish_video_path": str(source_video.resolve()).replace("\\", "/"),
        "publish_package_path": str(publish_dir.resolve()).replace("\\", "/"),
        "branding_layers": branding_layers,
        "logo_enabled": bool(settings.get("logo_enabled")),
        "logo_status": STATUS_COMPLETED if "logo" in branding_layers else (STATUS_SKIPPED if not settings.get("logo_enabled") else STATUS_SKIPPED),
        "cta_enabled": bool(settings.get("cta_enabled")),
        "cta_status": STATUS_COMPLETED if "cta" in branding_layers else (STATUS_DISABLED if not settings.get("cta_enabled") else STATUS_SKIPPED),
        "intro_enabled": bool(settings.get("intro_enabled")),
        "intro_status": STATUS_COMPLETED if "intro" in branding_layers else STATUS_SKIPPED,
        "outro_enabled": bool(settings.get("outro_enabled")),
        "outro_status": STATUS_COMPLETED if "outro" in branding_layers else STATUS_SKIPPED,
        "watermark_enabled": bool(settings.get("watermark_enabled")),
        "subtitle_count": int(subtitle_payload.get("subtitle_count") or 0),
        "subtitle_language": subtitle_payload.get("subtitle_language"),
        "lufs_value": audio_payload.get("lufs_value"),
        "normalization_applied": bool(audio_payload.get("normalization_applied")),
        "youtube_metadata_exists": youtube_exists,
        "error": "",
    }
    _write_success_artifacts(
        publish_dir=publish_dir,
        run_id=run_id,
        topic=topic,
        result=result,
        settings=settings,
        subtitle_payload=subtitle_payload,
        audio_payload=audio_payload,
    )
    return result


def _write_success_artifacts(
    *,
    publish_dir: Path,
    run_id: str,
    topic: str,
    result: dict[str, Any],
    settings: dict[str, Any],
    subtitle_payload: dict[str, Any],
    audio_payload: dict[str, Any],
) -> None:
    branding_manifest = {
        "version": PRODUCT_SUBTITLE_BRANDING_PUBLISH_VERSION,
        "run_id": run_id,
        "topic": topic,
        "source_video": result.get("final_publish_video_path"),
        "output_video": result.get("final_branded_publish_video_path"),
        "branding_status": result.get("branding_status"),
        "branding_layers": list(result.get("branding_layers") or []),
        "logo_enabled": settings.get("logo_enabled"),
        "cta_enabled": settings.get("cta_enabled"),
        "intro_enabled": settings.get("intro_enabled"),
        "outro_enabled": settings.get("outro_enabled"),
        "watermark_enabled": settings.get("watermark_enabled"),
        "subtitle_status": subtitle_payload.get("subtitle_status"),
        "subtitle_count": subtitle_payload.get("subtitle_count"),
        "subtitle_language": subtitle_payload.get("subtitle_language"),
        "audio_status": audio_payload.get("audio_status"),
        "lufs_value": audio_payload.get("lufs_value"),
        "normalization_applied": audio_payload.get("normalization_applied"),
        "settings": settings,
        "created_at": _now_iso(),
    }
    publish_package = {
        "version": PRODUCT_SUBTITLE_BRANDING_PUBLISH_VERSION,
        "run_id": run_id,
        "publish_ready": bool(result.get("publish_ready")),
        "final_video": result.get("final_branded_publish_video_path"),
        "source_video": result.get("final_publish_video_path"),
        "subtitle_status": result.get("subtitle_status"),
        "branding_status": result.get("branding_status"),
        "audio_status": result.get("audio_status"),
        "youtube_metadata_exists": bool(result.get("youtube_metadata_exists")),
        "logo_status": result.get("logo_status"),
        "cta_status": result.get("cta_status"),
        "intro_status": result.get("intro_status"),
        "outro_status": result.get("outro_status"),
        "created_at": _now_iso(),
    }
    (publish_dir / BRANDING_MANIFEST_NAME).write_text(
        json.dumps(branding_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (publish_dir / PUBLISH_PACKAGE_NAME).write_text(
        json.dumps(publish_package, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_failure_artifacts(
    *,
    publish_dir: Path,
    run_id: str,
    source_video: Path,
    result: dict[str, Any],
    settings: dict[str, Any],
    subtitle_payload: dict[str, Any] | None = None,
    audio_payload: dict[str, Any] | None = None,
) -> None:
    publish_dir.mkdir(parents=True, exist_ok=True)
    subtitle_payload = dict(subtitle_payload or {})
    audio_payload = dict(audio_payload or {})
    branding_manifest = {
        "version": PRODUCT_SUBTITLE_BRANDING_PUBLISH_VERSION,
        "run_id": run_id,
        "source_video": str(source_video.resolve()).replace("\\", "/") if source_video.is_file() else "",
        "output_video": "",
        "branding_status": STATUS_FAILED,
        "branding_layers": list(result.get("branding_layers") or []),
        "subtitle_status": subtitle_payload.get("subtitle_status") or result.get("subtitle_status"),
        "subtitle_count": subtitle_payload.get("subtitle_count", 0),
        "subtitle_language": subtitle_payload.get("subtitle_language") or settings.get("subtitle_language"),
        "audio_status": audio_payload.get("audio_status") or result.get("audio_status"),
        "lufs_value": audio_payload.get("lufs_value"),
        "normalization_applied": audio_payload.get("normalization_applied"),
        "error": result.get("error"),
        "settings": settings,
        "created_at": _now_iso(),
    }
    publish_package = {
        "version": PRODUCT_SUBTITLE_BRANDING_PUBLISH_VERSION,
        "run_id": run_id,
        "publish_ready": False,
        "final_video": "",
        "source_video": branding_manifest["source_video"],
        "subtitle_status": branding_manifest["subtitle_status"],
        "branding_status": STATUS_FAILED,
        "audio_status": branding_manifest["audio_status"],
        "youtube_metadata_exists": (publish_dir / YOUTUBE_METADATA_FILENAME).is_file(),
        "error": result.get("error"),
        "created_at": _now_iso(),
    }
    (publish_dir / BRANDING_MANIFEST_NAME).write_text(
        json.dumps(branding_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (publish_dir / PUBLISH_PACKAGE_NAME).write_text(
        json.dumps(publish_package, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_product_publish_package_state(run_dir: str | Path) -> dict[str, Any]:
    publish_dir = Path(run_dir).resolve() / "publish"
    branding_manifest = {}
    publish_package = {}
    if (publish_dir / BRANDING_MANIFEST_NAME).is_file():
        try:
            branding_manifest = json.loads((publish_dir / BRANDING_MANIFEST_NAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            branding_manifest = {}
    if (publish_dir / PUBLISH_PACKAGE_NAME).is_file():
        try:
            publish_package = json.loads((publish_dir / PUBLISH_PACKAGE_NAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            publish_package = {}

    final_branded = str(
        publish_package.get("final_video")
        or branding_manifest.get("output_video")
        or ""
    )
    publish_ready = bool(publish_package.get("publish_ready")) and bool(final_branded)
    if publish_ready:
        publish_ready = validate_mp4_path(final_branded)["valid"]

    return {
        "publish_ready": publish_ready,
        "final_branded_publish_video_path": final_branded if publish_ready else "",
        "final_publish_video_path": str((publish_dir / FINAL_PUBLISH_READY_NAME).resolve()).replace("\\", "/")
        if (publish_dir / FINAL_PUBLISH_READY_NAME).is_file()
        else str(publish_package.get("source_video") or branding_manifest.get("source_video") or ""),
        "subtitle_status": publish_package.get("subtitle_status") or branding_manifest.get("subtitle_status") or "",
        "branding_status": publish_package.get("branding_status") or branding_manifest.get("branding_status") or "",
        "audio_status": publish_package.get("audio_status") or branding_manifest.get("audio_status") or "",
        "logo_status": publish_package.get("logo_status") or "",
        "cta_status": publish_package.get("cta_status") or "",
        "intro_status": publish_package.get("intro_status") or "",
        "outro_status": publish_package.get("outro_status") or "",
        "subtitle_count": int(branding_manifest.get("subtitle_count") or 0),
        "subtitle_language": branding_manifest.get("subtitle_language") or "",
        "branding_layers": list(branding_manifest.get("branding_layers") or []),
        "logo_enabled": branding_manifest.get("logo_enabled"),
        "cta_enabled": branding_manifest.get("cta_enabled"),
        "intro_enabled": branding_manifest.get("intro_enabled"),
        "outro_enabled": branding_manifest.get("outro_enabled"),
        "lufs_value": branding_manifest.get("lufs_value"),
        "normalization_applied": bool(branding_manifest.get("normalization_applied")),
        "youtube_metadata_exists": bool(publish_package.get("youtube_metadata_exists")),
        "publish_package_path": str(publish_dir.resolve()).replace("\\", "/") if publish_dir.is_dir() else "",
        "branding_manifest": branding_manifest,
        "publish_package": publish_package,
    }


__all__ = [
    "BRANDING_MANIFEST_NAME",
    "FINAL_BRANDED_PUBLISH_READY_NAME",
    "PRODUCT_SUBTITLE_BRANDING_PUBLISH_VERSION",
    "PUBLISH_PACKAGE_NAME",
    "load_product_publish_package_state",
    "run_product_subtitle_branding_publish",
]
