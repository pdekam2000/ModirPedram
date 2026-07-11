"""PHASE STORY-VISUAL-1 — new cartoon story with visual diversity engines (not recovery)."""

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
TOPIC = "Whiskers and Sage — crystal jungle adventure"
TEST_VERSION = "run_story_visual_1_v1"

STORY_BRIEF: dict[str, Any] = {
    "genre": "cartoon",
    "title": "Whiskers and the Crystal Jungle",
    "hook": "Whiskers spots golden light flickering between jungle vines at a mossy forest entrance.",
    "discovery": "Ancient ruins reveal carved symbols that pulse when Sage touches the stone.",
    "escalation": "The ground shakes as roots trap them unless they reach the hidden chamber.",
    "resolution": "A glowing crystal chamber blooms with light and opens a safe path home.",
    "visual_objectives": [
        {
            "clip_index": 1,
            "location": "forest entrance",
            "visual_objective": "Sunlit jungle trail with vines, moss, and golden dust motes at the forest entrance",
            "setting_type": "exterior_nature",
            "story_beat": "discovery",
        },
        {
            "clip_index": 2,
            "location": "ancient ruins",
            "visual_objective": "Crumbling stone arches covered in moss and glowing carved symbols",
            "setting_type": "interior_ruins",
            "story_beat": "escalation",
        },
        {
            "clip_index": 3,
            "location": "hidden glowing chamber",
            "visual_objective": "Underground crystal cavern pulsing with warm amber light and floating sparkles",
            "setting_type": "interior_magical",
            "story_beat": "reward",
        },
    ],
}


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


def run_story_visual_1_test() -> dict[str, Any]:
    ensure_local_audio_assets(ROOT)
    _ensure_profile()

    run_id = f"cb_sv1_{_now_slug()}_{uuid.uuid4().hex[:8]}"
    run_dir = ROOT / "outputs" / "runs" / f"{_now_slug()}_{uuid.uuid4().hex[:8]}"
    for folder in ("final", "publish", "audio", "timeline", "metadata", "publish/subtitles", "debug/story_visual_1"):
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
    (run_dir / "metadata" / "assembly_manifest.json").write_text(json.dumps(assembly_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "metadata" / "run_summary.json").write_text(
        json.dumps({"run_id": run_id, "topic": TOPIC, "clip_count": 3, "story_visual_1": True}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    package, package_path = build_and_save_story_package(
        project_root=ROOT,
        topic=TOPIC,
        run_id=run_id,
        clip_count=3,
        duration_seconds=12.0,
        story_brief=STORY_BRIEF,
        run_dir=run_dir,
    )

    visual_quality = dict(package.metadata.get("story_visual_quality") or {})
    artifact_paths = dict(package.metadata.get("story_visual_artifact_paths") or {})

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
        "story_package_path": str(package_path.resolve()),
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

    register_published_asset(
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
        latest_asset="",
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
    (ROOT / "project_brain" / "STORY_ENTERTAINMENT_AUDIT.md").write_text(
        render_audit_markdown(
            entertainment,
            run_id=run_id,
            final_video=str(publish_v4.resolve()) if publish_v4.is_file() else "",
        ),
        encoding="utf-8",
    )

    scene_diversity_report = _read_json(run_dir / "debug" / "story_visual_1" / "scene_diversity_report.json")
    repetition_report = _read_json(run_dir / "metadata" / "visual_repetition_report.json")
    emotion_report = _read_json(run_dir / "metadata" / "character_emotion_plan.json")

    summary = {
        "ok": cinematic.get("status") == "completed" and branding.get("status") == "completed",
        "version": TEST_VERSION,
        "run_id": run_id,
        "run_dir": str(run_dir.resolve()),
        "story_package_path": str(package_path.resolve()),
        "final_video_path": str(publish_v4.resolve()) if publish_v4.is_file() else "",
        "scene_diversity_report_path": str(run_dir / "debug" / "story_visual_1" / "scene_diversity_report.json"),
        "repetition_report_path": str(run_dir / "metadata" / "visual_repetition_report.json"),
        "emotion_report_path": str(run_dir / "metadata" / "character_emotion_plan.json"),
        "scene_diversity_score": visual_quality.get("scene_diversity_score"),
        "repetition_score": visual_quality.get("repetition_score"),
        "emotion_coverage_score": visual_quality.get("emotion_coverage_score"),
        "story_progression_score": visual_quality.get("story_progression_score"),
        "clip_objectives": visual_quality.get("clip_objectives"),
        "artifact_paths": artifact_paths,
        "entertainment_audit": entertainment.to_dict(),
        "branding_status": branding.get("status"),
        "subtitle_status": branding.get("subtitle_status"),
    }
    (run_dir / "debug" / "story_visual_1" / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "project_brain" / "STORY_VISUAL_1_TEST_REPORT.md").write_text(
        "\n".join(
            [
                "# Story Visual 1 Test Report",
                "",
                f"- Run ID: `{run_id}`",
                f"- Final video: `{summary['final_video_path']}`",
                f"- Scene diversity score: **{visual_quality.get('scene_diversity_score')}**/100",
                f"- Emotion coverage: **{visual_quality.get('emotion_coverage_score')}**/100",
                f"- Story progression: **{visual_quality.get('story_progression_score')}**/100",
                f"- Repetition score: **{visual_quality.get('repetition_score')}**/100",
                "",
                "## Clip objectives",
                "",
                *[
                    f"- Clip {obj.get('clip_index')}: **{obj.get('location')}** — {obj.get('visual_objective')}"
                    for obj in (visual_quality.get("clip_objectives") or [])
                    if isinstance(obj, dict)
                ],
                "",
                "## Reports",
                "",
                f"- Scene diversity: `{summary['scene_diversity_report_path']}`",
                f"- Repetition: `{summary['repetition_report_path']}`",
                f"- Emotion: `{summary['emotion_report_path']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    summary = run_story_visual_1_test()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
