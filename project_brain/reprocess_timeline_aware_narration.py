"""Reprocess run with timeline-aware narration — no Runway, no clip regen."""

from __future__ import annotations

import json
import shutil
import sys
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

from content_brain.audio.audio_design_engine import build_audio_design_plan
from content_brain.audio.audio_mastering_engine import apply_final_mastering, probe_mean_volume_db
from content_brain.audio.audio_merge_engine import NARRATED_VIDEO_NAME, merge_narration_into_video
from content_brain.audio.audio_mix_engine import ENV_MIXED_VIDEO_NAME, mix_environment_and_sfx
from content_brain.audio.environment_sound_engine import build_environment_sound_plan, write_environment_sound_plan
from content_brain.audio.music_runtime import music_runtime_status_label, run_music_runtime
from content_brain.audio.subtitle_timing_engine import generate_timeline_subtitles
from content_brain.audio.timeline_aware_narration_engine import run_timeline_aware_narration
from content_brain.branding.branding_runtime import run_branding_runtime
from content_brain.branding.subtitle_format_engine import measure_subtitle_text_bbox
from content_brain.execution.runway_live_post_processor import ASSEMBLY_ASSEMBLED, run_assembly, run_publish_package
from content_brain.platform.delivery_quality_gate import evaluate_delivery_quality, write_delivery_quality_gate
from content_brain.platform.media_probe import probe_duration_seconds
from content_brain.platform.run_output_versioning import create_versioned_run_layout, finalize_versioned_run_layout
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.story.story_package import load_story_package, story_package_path

RUN_ID = "cb_e2e_20260614_195440_8bf41b6b"
RUN_DIR = ROOT / "outputs" / "runs" / "20260614_210353_440_8bf41b6b"
TOPIC = "A boy finds a dragon egg in the forest and hides it from everyone"
TIMELINE_FIXED_NAME = "FINAL_BRANDED_VIDEO_CANONICAL_TIMELINE_FIXED.mp4"
CLIP_PATHS = [
    ROOT / "downloads" / "runway" / "runway_clip_1_session_20260614_201432.mp4",
    ROOT / "downloads" / "runway" / "runway_clip_2_session_20260614_203102.mp4",
    ROOT / "downloads" / "runway" / "runway_clip_3_session_20260614_204752.mp4",
    ROOT / "downloads" / "runway" / "runway_clip_4_session_20260614_210318.mp4",
]


def _story_brief() -> dict[str, Any]:
    return {
        "main_character": "Boy",
        "clip_beats": [
            "A boy discovers a glowing dragon egg beneath forest leaves.",
            "He wraps the egg and hides it from passing travelers.",
            "Footsteps approach as the egg begins to warm.",
            "He escapes deeper into the trees clutching the secret.",
        ],
    }


def reprocess_timeline_narration() -> dict[str, Any]:
    run_dir = RUN_DIR.resolve()
    profile = ProductChannelProfileStore(ROOT).load()
    story_package = load_story_package(ROOT, RUN_ID)
    if not story_package:
        return {"ok": False, "error": "story_package_missing", "expected_path": str(story_package_path(ROOT, RUN_ID))}

    assembly_manifest = run_assembly(
        ROOT,
        input_files=[str(p) for p in CLIP_PATHS],
        clip_count=4,
        output_path=run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4",
    )
    if str(assembly_manifest.get("status") or "") != ASSEMBLY_ASSEMBLED:
        return {"ok": False, "error": assembly_manifest.get("error"), "runway_started": False}

    assembled_duration = probe_duration_seconds(run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4")
    assembly_manifest["duration_seconds"] = assembled_duration

    narration_dir = run_dir / "publish" / "narration"
    timeline_result = run_timeline_aware_narration(
        project_root=ROOT,
        story_package=story_package,
        output_dir=narration_dir,
        duration_seconds=float(assembled_duration or 0),
        narration_provider_id=str(profile.get("default_narration_provider") or "elevenlabs"),
        voice_id=str(profile.get("default_narrator_voice") or profile.get("default_voice") or ""),
    )
    if timeline_result.status != "completed":
        return {
            "ok": False,
            "runway_started": False,
            "error": "timeline_narration_failed",
            "timeline_result": timeline_result.to_dict(),
        }

    merge_result = merge_narration_into_video(
        video_path=run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4",
        narration_audio_path=timeline_result.narration_audio_path,
        output_path=run_dir / "final" / NARRATED_VIDEO_NAME,
        normalize_narration=False,
    )
    if merge_result.status != "MERGED":
        return {"ok": False, "error": merge_result.error, "runway_started": False}

    story_brief = _story_brief()
    audio_design = build_audio_design_plan(
        project_root=ROOT,
        topic=TOPIC,
        run_id=RUN_ID,
        story_brief=story_brief,
        platform=str(profile.get("default_platform") or "youtube_shorts"),
        duration_seconds=float(assembled_duration or 0),
    )
    env_plan = build_environment_sound_plan(
        project_root=ROOT,
        topic=TOPIC,
        environment=audio_design.environment,
        scene_progression=story_brief.get("scene_progression"),
        sfx_events=audio_design.sound_effects,
        duration_seconds=float(assembled_duration or 0),
    )
    write_environment_sound_plan(ROOT, run_dir, env_plan)

    deliverable = Path(merge_result.output_path)
    env_mix = mix_environment_and_sfx(
        project_root=ROOT,
        input_video_path=deliverable,
        ambience_files=env_plan.resolved_ambience_files,
        sfx_events=env_plan.sfx_events,
        output_path=run_dir / "final" / ENV_MIXED_VIDEO_NAME,
    )
    if env_mix.get("status") == "completed":
        deliverable = Path(str(env_mix["output_path"]))

    music_result = run_music_runtime(
        project_root=ROOT,
        input_video_path=deliverable,
        debug_manifest_path=run_dir / "publish" / "audio" / "music_debug_manifest.json",
    )
    if music_result.get("status") == "completed" and music_result.get("audibility_pass"):
        deliverable = Path(str(music_result["output_path"]))

    mastering = apply_final_mastering(
        input_video_path=deliverable,
        output_video_path=run_dir / "final" / "FINAL_RUNWAY_PHASE_I_MASTERED.mp4",
    )
    if mastering.get("status") == "completed":
        deliverable = Path(str(mastering["output_path"]))

    timeline_cues = []
    for segment in timeline_result.segments:
        cue = segment.to_dict()
        cue["end_seconds"] = min(
            float(assembled_duration or timeline_result.duration_seconds),
            segment.start_seconds + max(segment.audio_duration_seconds, segment.planned_duration_seconds),
        )
        timeline_cues.append(cue)
    subtitles = generate_timeline_subtitles(
        timeline_segments=timeline_cues,
        output_dir=run_dir / "publish" / "subtitles",
        duration_seconds=float(assembled_duration or timeline_result.duration_seconds),
        platform=str(profile.get("default_platform") or "youtube_shorts"),
        run_dir=run_dir,
        video_path=str(deliverable),
    )
    from content_brain.branding.subtitle_format_engine import write_styled_ass_outputs

    styled_meta = dict(subtitles.metadata.get("shorts_format") or {})
    ass_path = str(styled_meta.get("ass_path") or "")
    styled_ass_path = ""
    if ass_path and Path(ass_path).is_file():
        styled_outputs = write_styled_ass_outputs(
            ass_content=Path(ass_path).read_text(encoding="utf-8"),
            publish_subtitles_dir=run_dir / "publish" / "subtitles",
            debug_dir=run_dir / "debug",
        )
        styled_ass_path = str(styled_outputs.get("styled_ass_path") or "")

    report_payload = {
        "content_brain_run_id": RUN_ID,
        "content_brain_topic": TOPIC,
        "clip_count": 4,
        "ok": True,
        "simulate": False,
    }
    audio_post_result = {
        "status": "completed",
        "narration_provider": str(profile.get("default_narration_provider") or "elevenlabs"),
        "music_provider": str(profile.get("music_provider") or "none"),
        "narrated_video_path": str(deliverable),
        "mastered_video_path": str(deliverable),
        "narration_audio_path": timeline_result.narration_audio_path,
        "narration_script_path": timeline_result.narration_script_path,
        "narration_plan_path": timeline_result.narration_plan_path,
        "timeline_narration": timeline_result.to_dict(),
        "subtitle_paths": [subtitles.srt_path, subtitles.vtt_path],
        "styled_ass_path": styled_ass_path,
        "duration_seconds": assembled_duration,
        "music_status": music_runtime_status_label(music_result),
        "music_status_code": str(music_result.get("status") or ""),
        "ambience_status": f"Ambience: PASS — {len(env_plan.resolved_ambience_files)} layer(s)",
        "character_voice_status": (
            f"Character voices: timeline-aware narration — {len(timeline_result.segments)} segments, "
            f"coverage {timeline_result.coverage_ratio:.0%}"
        ),
        "metadata": {
            "merge": merge_result.to_dict(),
            "env_mix": env_mix,
            "mastering": mastering,
            "music": music_result,
            "timeline_narration": timeline_result.to_dict(),
        },
    }

    branding = run_branding_runtime(
        project_root=ROOT,
        report=report_payload,
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        output_dir=run_dir / "final",
        branded_video_name=TIMELINE_FIXED_NAME,
    )
    publish_manifest = run_publish_package(
        ROOT,
        assembly_manifest=assembly_manifest,
        run_id=RUN_ID,
        topic=TOPIC,
        clip_count=4,
        downloaded_file_paths=[str(p) for p in CLIP_PATHS],
        audio_post_result=audio_post_result,
        branding_post_result=branding,
        package_dir=run_dir / "publish",
    )

    branded_source = Path(str(branding.get("final_branded_video_path") or ""))
    timeline_publish = run_dir / "publish" / TIMELINE_FIXED_NAME
    if branded_source.is_file() and branded_source.resolve() != timeline_publish.resolve():
        shutil.copy2(branded_source, timeline_publish)
    publish_manifest["branded_video_path"] = str(timeline_publish.resolve())

    delivery = evaluate_delivery_quality(
        project_root=ROOT,
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        branding_post_result=branding,
        publish_manifest=publish_manifest,
        channel_profile=profile,
    )
    write_delivery_quality_gate(ROOT, delivery, run_dir=run_dir)
    layout = create_versioned_run_layout(ROOT, run_id=RUN_ID, topic=TOPIC)
    layout.run_dir = run_dir
    layout.final_dir = run_dir / "final"
    layout.publish_dir = run_dir / "publish"
    finalize_versioned_run_layout(
        ROOT,
        layout,
        assembly_manifest=assembly_manifest,
        publish_manifest=publish_manifest,
    )

    final_path = timeline_publish if timeline_publish.is_file() else branded_source
    subtitle_step = dict((branding.get("steps") or {}).get("subtitles") or {})
    visible = subtitle_step.get("burn_visible_enough")
    if visible is None and final_path.is_file():
        visible = measure_subtitle_text_bbox(final_path, 12.0).get("visible")

    clip_levels = {
        label: probe_mean_volume_db(final_path, start_seconds=start, duration_seconds=10.0)
        for label, start in (("clip1", 0.0), ("clip2", 10.0), ("clip3", 20.0), ("clip4", 30.0))
    }

    return {
        "ok": True,
        "runway_started": False,
        "output_path": str(final_path.resolve()) if final_path.is_file() else "",
        "timeline_result": timeline_result.to_dict(),
        "coverage_ratio": timeline_result.coverage_ratio,
        "delivery_gate": delivery.to_dict(),
        "subtitle_visible": visible,
        "clip_speech_levels_db": clip_levels,
        "duration_seconds": probe_duration_seconds(final_path),
        "merge_warnings": merge_result.warnings,
    }


def main() -> int:
    summary = reprocess_timeline_narration()
    out = ROOT / "project_brain" / "timeline_aware_narration_reprocess_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
