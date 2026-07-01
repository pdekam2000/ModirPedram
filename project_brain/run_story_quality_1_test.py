"""PHASE STORY-QUALITY-1 — new cartoon test run (not recovery)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from content_brain.audio.cinematic_audio_runtime import run_cinematic_audio_pipeline  # noqa: E402
from content_brain.audio.local_audio_assets import ensure_local_audio_assets  # noqa: E402
from content_brain.audio.subtitle_timing_engine import generate_timed_subtitles  # noqa: E402
from content_brain.branding.branding_runtime import FINAL_BRANDED_VIDEO_V4_NAME, run_branding_runtime  # noqa: E402
from content_brain.execution.runway_live_post_processor import ASSEMBLY_ASSEMBLED  # noqa: E402
from content_brain.platform.asset_library import register_published_asset  # noqa: E402
from content_brain.platform.final_delivery_registry import update_final_delivery_registry  # noqa: E402
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore  # noqa: E402
from content_brain.story.story_package import build_and_save_story_package  # noqa: E402
from project_brain.validate_story_entertainment_quality import (  # noqa: E402
    audit_story_entertainment_quality,
    render_audit_markdown,
)

SOURCE_VIDEO_RUN = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"
TOPIC = "Cute orange cartoon cat explorer"
TEST_VERSION = "run_story_quality_1_v1"


def _now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _ensure_profile() -> None:
    store = ProductChannelProfileStore(ROOT)
    profile = store.load()
    profile["music_provider"] = "local"
    profile["music_track_path"] = "assets/audio/music/whimsical_adventure.mp3"
    profile["music_volume"] = 0.30
    profile["character_voice_mode"] = "multi_voice"
    profile.setdefault("default_narrator_voice", profile.get("default_voice") or "")
    profile.setdefault("child_friendly_voice", profile.get("default_voice") or "")
    profile.setdefault("character_voice_2", profile.get("child_friendly_voice") or profile.get("default_voice") or "")
    store.save(profile)


def _extract_subtitle_screenshots(video_path: Path, output_dir: Path, seconds: list[float]) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for seek in seconds:
        png = output_dir / f"subtitle_frame_{seek:.1f}s.png"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(seek),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(png),
            ],
            check=False,
        )
        if png.is_file():
            paths.append(str(png.resolve()))
    return paths


def run_story_quality_1_test() -> dict[str, Any]:
    ensure_local_audio_assets(ROOT)
    _ensure_profile()

    run_id = f"cb_sq1_{_now_slug()}_{uuid.uuid4().hex[:8]}"
    run_dir = ROOT / "outputs" / "runs" / f"{_now_slug()}_{uuid.uuid4().hex[:8]}"
    for folder in ("final", "publish", "audio", "timeline", "metadata", "publish/subtitles", "debug/story_quality_1"):
        (run_dir / folder).mkdir(parents=True, exist_ok=True)

    source_video = SOURCE_VIDEO_RUN / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
    if not source_video.is_file():
        return {"ok": False, "error": "source_video_missing", "source": str(source_video)}

    video_path = run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
    shutil.copy2(source_video, video_path)
    assembly_manifest = {
        "status": ASSEMBLY_ASSEMBLED,
        "output_path": str(video_path.resolve()),
        "duration_seconds": 12.0,
    }
    (run_dir / "metadata" / "assembly_manifest.json").write_text(json.dumps(assembly_manifest, indent=2), encoding="utf-8")
    (run_dir / "metadata" / "run_summary.json").write_text(
        json.dumps({"run_id": run_id, "topic": TOPIC, "clip_count": 3}, indent=2),
        encoding="utf-8",
    )

    package, package_path = build_and_save_story_package(
        project_root=ROOT,
        topic=TOPIC,
        run_id=run_id,
        clip_count=3,
        duration_seconds=12.0,
    )

    profile = ProductChannelProfileStore(ROOT).load()
    provider = str(profile.get("default_narration_provider") or "elevenlabs")

    cinematic = run_cinematic_audio_pipeline(
        project_root=ROOT,
        run_dir=run_dir,
        story_package=package.to_dict(),
        video_path=video_path,
        duration_seconds=12.0,
        narration_provider=provider,
        allow_local_fallback=True,
    )
    if cinematic.get("status") != "completed":
        return {"ok": False, "error": "cinematic_pipeline_failed", "cinematic": cinematic, "run_dir": str(run_dir)}

    timeline = _read_json(run_dir / "timeline" / "dialogue_timeline.json")
    script_lines = [
        f"{line.get('speaker')}: {line.get('text')}"
        for line in timeline.get("lines") or []
        if isinstance(line, dict)
    ]
    subtitles = generate_timed_subtitles(
        script="\n".join(script_lines),
        narration_audio_path=str(cinematic.get("cinematic_audio_path") or ""),
        output_dir=run_dir / "publish" / "subtitles",
        segments=script_lines,
        platform=str(profile.get("default_platform") or "tiktok"),
        run_dir=run_dir,
        video_path=str(cinematic.get("cinematic_video_path") or video_path),
    )
    styled_meta = dict(subtitles.metadata.get("shorts_format") or {})
    audio_post_result = {
        "status": "completed",
        "narrated_video_path": cinematic.get("cinematic_video_path"),
        "cinematic_video_path": cinematic.get("cinematic_video_path"),
        "cinematic_audio_path": cinematic.get("cinematic_audio_path"),
        "duration_seconds": subtitles.duration_seconds or 12.0,
        "subtitle_paths": [subtitles.srt_path, subtitles.vtt_path],
        "styled_ass_path": str(styled_meta.get("ass_path") or ""),
    }

    branding = run_branding_runtime(
        project_root=ROOT,
        report={"content_brain_run_id": run_id, "content_brain_topic": TOPIC, "clip_count": 3, "ok": True},
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        output_dir=run_dir / "final",
        branded_video_name=FINAL_BRANDED_VIDEO_V4_NAME,
    )

    branded_source = Path(str(branding.get("final_branded_video_path") or ""))
    publish_v4 = run_dir / "publish" / FINAL_BRANDED_VIDEO_V4_NAME
    if branded_source.is_file():
        shutil.copy2(branded_source, publish_v4)

    asset_result = register_published_asset(
        ROOT,
        publish_manifest={
            "status": "PUBLISHED_PACKAGE_CREATED",
            "branded_video_path": str(publish_v4.resolve()),
            "branded_video_name": publish_v4.name,
        },
        run_id=run_id,
        topic=TOPIC,
        run_dir=run_dir,
        assembly_manifest=assembly_manifest,
    )
    update_final_delivery_registry(
        ROOT,
        run_id=run_id,
        latest_video=publish_v4,
        latest_publish_package=run_dir / "publish",
        latest_asset=str(asset_result.get("final_video_path") or ""),
        branded_video_name=publish_v4.name,
        approved=branding.get("status") == "completed",
        topic=TOPIC,
        clips_completed=3,
        assembly_status="ASSEMBLED",
        reality_audit_passed=True,
        force=True,
    )

    entertainment = audit_story_entertainment_quality(
        project_root=ROOT,
        run_dir=run_dir,
        story_package=package.to_dict(),
    )
    audit_md = ROOT / "project_brain" / "STORY_ENTERTAINMENT_AUDIT.md"
    audit_md.write_text(
        render_audit_markdown(
            entertainment,
            run_id=run_id,
            final_video=str(publish_v4.resolve()) if publish_v4.is_file() else "",
        ),
        encoding="utf-8",
    )

    screenshots = _extract_subtitle_screenshots(
        publish_v4,
        run_dir / "debug" / "story_quality_1",
        [1.0, 3.0, 5.0, 8.0],
    )

    voice_cast = _read_json(run_dir / "audio" / "voice_cast_runtime.json")
    music_plan = package.music_plan.to_dict()
    transcript = [
        f"{line.get('speaker')}: {line.get('text')}"
        for line in timeline.get("lines") or []
        if isinstance(line, dict)
    ]

    summary = {
        "ok": cinematic.get("status") == "completed" and branding.get("status") == "completed",
        "version": TEST_VERSION,
        "run_id": run_id,
        "run_dir": str(run_dir.resolve()),
        "story_package_path": str(package_path.resolve()),
        "final_video_path": str(publish_v4.resolve()) if publish_v4.is_file() else "",
        "subtitle_screenshots": screenshots,
        "dialogue_transcript": transcript,
        "voice_cast_summary": {
            "voice_count": voice_cast.get("voice_count"),
            "speaker_map": voice_cast.get("speaker_map"),
            "provider": voice_cast.get("provider"),
        },
        "music_summary": {
            "mood": music_plan.get("mood"),
            "style_label": (music_plan.get("metadata") or {}).get("style_label"),
            "track_hint": music_plan.get("track_hint"),
            "asset_quality": ((music_plan.get("metadata") or {}).get("music_mood_selector") or {}).get("asset_quality"),
            "warnings": (music_plan.get("metadata") or {}).get("music_mood_selector", {}).get("warnings", []),
        },
        "entertainment_audit": entertainment.to_dict(),
        "branding_status": branding.get("status"),
        "subtitle_status": branding.get("subtitle_status"),
    }
    (run_dir / "debug" / "story_quality_1" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    summary = run_story_quality_1_test()
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
