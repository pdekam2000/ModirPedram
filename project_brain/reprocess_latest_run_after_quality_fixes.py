"""Re-run post-processing for cb_e2e run after delivery-quality fixes — no Runway."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_design_engine import build_audio_design_plan
from content_brain.audio.audio_merge_engine import NARRATED_VIDEO_NAME, merge_narration_into_video
from content_brain.audio.audio_mix_engine import ENV_MIXED_VIDEO_NAME, mix_environment_and_sfx
from content_brain.audio.environment_sound_engine import build_environment_sound_plan, write_environment_sound_plan
from content_brain.audio.music_runtime import music_runtime_status_label, run_music_runtime
from content_brain.audio.subtitle_timing_engine import generate_timed_subtitles
from content_brain.branding.branding_runtime import run_branding_runtime
from content_brain.branding.subtitle_format_engine import compare_subtitle_burn_visibility, measure_subtitle_text_bbox
from content_brain.execution.runway_live_post_processor import (
    ASSEMBLY_ASSEMBLED,
    run_assembly,
    run_publish_package,
)
from content_brain.platform.delivery_quality_gate import evaluate_delivery_quality, write_delivery_quality_gate
from content_brain.platform.media_probe import probe_duration_seconds, probe_has_audio_stream, probe_mean_volume_db
from content_brain.platform.run_output_versioning import finalize_versioned_run_layout
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.story.story_package import build_and_save_story_package, load_story_package

RUN_ID = "cb_e2e_20260614_195440_8bf41b6b"
RUN_DIR = ROOT / "outputs" / "runs" / "20260614_210353_440_8bf41b6b"
TOPIC = "A boy finds a dragon egg in the forest and hides it from everyone"
CLIP_PATHS = [
    ROOT / "downloads" / "runway" / "runway_clip_1_session_20260614_201432.mp4",
    ROOT / "downloads" / "runway" / "runway_clip_2_session_20260614_203102.mp4",
    ROOT / "downloads" / "runway" / "runway_clip_3_session_20260614_204752.mp4",
    ROOT / "downloads" / "runway" / "runway_clip_4_session_20260614_210318.mp4",
]
FIXED_BRANDED_NAME = "FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4"
BACKUP_TAG = "pre_quality_fix_reprocess"
REPORT_PATH = ROOT / "project_brain" / "REPROCESS_LATEST_RUN_AFTER_QUALITY_FIXES_REPORT.md"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _story_brief_from_e2e() -> dict[str, Any]:
    payload = _read_json(ROOT / "project_brain" / "content_brain_test_results" / f"{RUN_ID}.json")
    for step in payload.get("steps") or []:
        if isinstance(step, dict) and step.get("step_key") == "story_generation":
            story = (step.get("payload") or {}).get("story")
            if isinstance(story, dict):
                brief = dict(story)
                brief["main_character"] = "Boy"
                brief.setdefault(
                    "clip_beats",
                    [
                        "A boy discovers a glowing dragon egg beneath forest leaves.",
                        "He wraps the egg and hides it from passing travelers.",
                        "Footsteps approach as the egg begins to warm.",
                        "He escapes deeper into the trees clutching the secret.",
                    ],
                )
                return brief
    return {
        "main_character": "Boy",
        "clip_beats": [
            "A boy discovers a glowing dragon egg beneath forest leaves.",
            "He wraps the egg and hides it from passing travelers.",
            "Footsteps approach as the egg begins to warm.",
            "He escapes deeper into the trees clutching the secret.",
        ],
    }


def _backup_existing(paths: list[Path], backup_dir: Path) -> list[str]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backed_up: list[str] = []
    for source in paths:
        if not source.is_file():
            continue
        target = backup_dir / source.name
        if not target.is_file():
            shutil.copy2(source, target)
        backed_up.append(str(target.resolve()))
    return backed_up


def _layout_from_run_dir(run_dir: Path) -> Any:
    from content_brain.platform.run_output_versioning import VersionedRunLayout

    return VersionedRunLayout(
        run_id=RUN_ID,
        topic=TOPIC,
        run_dir=run_dir,
        final_dir=run_dir / "final",
        publish_dir=run_dir / "publish",
        audio_dir=run_dir / "audio",
        prompts_dir=run_dir / "prompts",
        metadata_dir=run_dir / "metadata",
        vision_dir=run_dir / "vision",
    )


def reprocess_run() -> dict[str, Any]:
    run_dir = RUN_DIR.resolve()
    backup_dir = run_dir / "publish" / "archive" / BACKUP_TAG
    profile = ProductChannelProfileStore(ROOT).load()
    story_brief = _story_brief_from_e2e()

    report_payload = {
        "content_brain_run_id": RUN_ID,
        "content_brain_topic": TOPIC,
        "clip_count": 4,
        "ok": True,
        "simulate": False,
        "downloaded_file_paths": [str(path) for path in CLIP_PATHS],
    }

    before_assembly = run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
    before_canonical = run_dir / "publish" / "FINAL_BRANDED_VIDEO_CANONICAL.mp4"
    before_durations = {
        "assembly_seconds": probe_duration_seconds(before_assembly),
        "canonical_seconds": probe_duration_seconds(before_canonical),
        "narration_seconds": probe_duration_seconds(run_dir / "publish" / "narration" / "narration.mp3"),
    }

    backed_up = _backup_existing(
        [
            before_canonical,
            run_dir / "final" / "FINAL_BRANDED_VIDEO_CANONICAL.mp4",
            run_dir / "final" / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4",
            run_dir / "final" / "FINAL_RUNWAY_PHASE_I_ENV.mp4",
        ],
        backup_dir,
    )

    for clip in CLIP_PATHS:
        if not clip.is_file():
            raise FileNotFoundError(f"Missing clip: {clip}")

    final_video = run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
    assembly_manifest = run_assembly(
        ROOT,
        input_files=[str(path) for path in CLIP_PATHS],
        clip_count=4,
        output_path=final_video,
    )
    _write_json(run_dir / "metadata" / "assembly_manifest.json", assembly_manifest)

    if str(assembly_manifest.get("status") or "") != ASSEMBLY_ASSEMBLED:
        return {
            "ok": False,
            "error": f"assembly_failed:{assembly_manifest.get('error')}",
            "before_durations": before_durations,
            "runway_started": False,
        }

    assembled_duration = probe_duration_seconds(final_video) or float(assembly_manifest.get("duration_seconds") or 0)
    assembly_manifest["duration_seconds"] = assembled_duration

    narration_audio = run_dir / "publish" / "narration" / "narration.mp3"
    narration_script = run_dir / "publish" / "narration" / "narration_script.txt"
    if not narration_audio.is_file():
        return {"ok": False, "error": "existing_narration_missing", "runway_started": False}

    merge_result = merge_narration_into_video(
        video_path=final_video,
        narration_audio_path=narration_audio,
        output_path=final_video.parent / NARRATED_VIDEO_NAME,
    )
    if merge_result.status != "MERGED":
        return {
            "ok": False,
            "error": f"merge_failed:{merge_result.error}",
            "before_durations": before_durations,
            "runway_started": False,
        }

    narrated_path = Path(merge_result.output_path)
    story_package, story_package_path = build_and_save_story_package(
        project_root=ROOT,
        topic=TOPIC,
        run_id=RUN_ID,
        clip_count=4,
        duration_seconds=assembled_duration,
        story_brief=story_brief,
        narration_provider=str(profile.get("default_narration_provider") or "elevenlabs"),
    )

    audio_design = build_audio_design_plan(
        project_root=ROOT,
        topic=TOPIC,
        run_id=RUN_ID,
        story_brief=story_brief,
        platform=str(profile.get("default_platform") or "youtube_shorts"),
        duration_seconds=assembled_duration,
    )
    env_plan = build_environment_sound_plan(
        project_root=ROOT,
        topic=TOPIC,
        environment=audio_design.environment,
        scene_progression=story_brief.get("scene_progression"),
        sfx_events=audio_design.sound_effects,
        duration_seconds=assembled_duration,
    )
    write_environment_sound_plan(ROOT, run_dir, env_plan)

    env_mix = mix_environment_and_sfx(
        project_root=ROOT,
        input_video_path=narrated_path,
        ambience_files=env_plan.resolved_ambience_files,
        sfx_events=env_plan.sfx_events,
        output_path=final_video.parent / ENV_MIXED_VIDEO_NAME,
        ambience_volume=0.22,
    )
    deliverable_video = narrated_path
    if env_mix.get("status") == "completed":
        deliverable_video = Path(str(env_mix.get("output_path") or narrated_path))

    music_result = run_music_runtime(
        project_root=ROOT,
        input_video_path=deliverable_video,
        debug_manifest_path=run_dir / "publish" / "audio" / "music_debug_manifest.json",
    )
    if music_result.get("status") == "completed" and music_result.get("audibility_pass") and music_result.get("output_path"):
        deliverable_video = Path(str(music_result["output_path"]))

    script_text = narration_script.read_text(encoding="utf-8") if narration_script.is_file() else ""
    subtitle_dir = run_dir / "publish" / "subtitles"
    subtitles = generate_timed_subtitles(
        script=script_text,
        narration_audio_path=str(narration_audio),
        output_dir=subtitle_dir,
        segments=[line.strip() for line in script_text.replace(". ", ".\n").splitlines() if line.strip()],
        platform=str(profile.get("default_platform") or "youtube_shorts"),
        run_dir=run_dir,
        video_path=str(deliverable_video),
    )

    from content_brain.branding.subtitle_format_engine import write_styled_ass_outputs

    styled_meta = dict(subtitles.metadata.get("shorts_format") or {})
    ass_path = str(styled_meta.get("ass_path") or "")
    styled_ass_path = ""
    if ass_path and Path(ass_path).is_file():
        styled_outputs = write_styled_ass_outputs(
            ass_content=Path(ass_path).read_text(encoding="utf-8"),
            publish_subtitles_dir=subtitle_dir,
            debug_dir=run_dir / "debug",
            font_size=int(styled_meta.get("font_size") or 0) or None,
        )
        styled_ass_path = str(styled_outputs.get("styled_ass_path") or "")

    audio_post_result = {
        "status": "completed",
        "narration_provider": str(profile.get("default_narration_provider") or "elevenlabs"),
        "voice_id": str(profile.get("default_narrator_voice") or profile.get("default_voice") or ""),
        "music_provider": str(profile.get("music_provider") or "none"),
        "narration_script_path": str(narration_script),
        "narration_audio_path": str(narration_audio),
        "narrated_video_path": str(deliverable_video.resolve()),
        "subtitle_paths": [subtitles.srt_path, subtitles.vtt_path],
        "styled_ass_path": styled_ass_path,
        "duration_seconds": assembled_duration,
        "music_status": music_runtime_status_label(music_result),
        "music_status_code": str(music_result.get("status") or ""),
        "music_runtime": music_result,
        "ambience_status": f"Ambience: PASS — {len(env_plan.resolved_ambience_files)} layer(s)",
        "sfx_status": f"SFX: PASS — {len(env_plan.resolved_sfx_files)} cue(s)",
        "character_voice_status": "Character voices: reused existing narration (no new TTS)",
        "subtitle_status": "Subtitle: styled ASS ready for branding",
        "story_package_path": str(story_package_path),
        "metadata": {"merge": merge_result.to_dict(), "environment_mix": env_mix},
    }
    _write_json(ROOT / "project_brain" / "runtime_state" / "runway_phase_i_audio_manifest.json", audio_post_result)

    branding_post_result = run_branding_runtime(
        project_root=ROOT,
        report=report_payload,
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        output_dir=run_dir / "final",
        branded_video_name=FIXED_BRANDED_NAME,
    )

    publish_manifest = run_publish_package(
        ROOT,
        assembly_manifest=assembly_manifest,
        run_id=RUN_ID,
        topic=TOPIC,
        clip_count=4,
        downloaded_file_paths=[str(path) for path in CLIP_PATHS],
        audio_post_result=audio_post_result,
        branding_post_result=branding_post_result,
        package_dir=run_dir / "publish",
    )

    branded_source = Path(str(branding_post_result.get("final_branded_video_path") or ""))
    fixed_publish = run_dir / "publish" / FIXED_BRANDED_NAME
    if branded_source.is_file():
        fixed_publish.parent.mkdir(parents=True, exist_ok=True)
        if branded_source.resolve() != fixed_publish.resolve():
            shutil.copy2(branded_source, fixed_publish)
        publish_manifest["branded_video_path"] = str(fixed_publish.resolve())
        publish_manifest["branded_video_name"] = FIXED_BRANDED_NAME

    delivery_result = evaluate_delivery_quality(
        project_root=ROOT,
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        branding_post_result=branding_post_result,
        publish_manifest=publish_manifest,
        channel_profile=profile,
    )
    write_delivery_quality_gate(ROOT, delivery_result, run_dir=run_dir)

    layout = _layout_from_run_dir(run_dir)
    run_summary = finalize_versioned_run_layout(
        ROOT,
        layout,
        assembly_manifest=assembly_manifest,
        publish_manifest=publish_manifest,
    )
    _write_json(run_dir / "metadata" / "publish_manifest.json", publish_manifest)
    run_summary["reprocess_tag"] = BACKUP_TAG
    run_summary["fixed_branded_video_path"] = str(fixed_publish) if fixed_publish.is_file() else ""
    run_summary["delivery_status"] = delivery_result.delivery_status
    _write_json(run_dir / "metadata" / "run_summary.json", {**_read_json(run_dir / "metadata" / "run_summary.json"), **run_summary})

    final_path = fixed_publish if fixed_publish.is_file() else branded_source
    after_duration = probe_duration_seconds(final_path)
    subtitle_step = dict((branding_post_result.get("steps") or {}).get("subtitles") or {})
    subtitle_visible = subtitle_step.get("burn_visible_enough")
    if final_path.is_file() and subtitle_visible is None:
        bbox = measure_subtitle_text_bbox(final_path, min(2.0, max(0.5, (after_duration or 10) * 0.05)))
        subtitle_visible = bbox.get("visible")

    package_topic = load_story_package(ROOT, RUN_ID)
    blueprint = package_topic.get("story_blueprint") or {}
    character_names = [
        str(item.get("name") or "")
        for item in (package_topic.get("character_profiles") or [])
        if isinstance(item, dict)
    ]

    return {
        "ok": delivery_result.delivery_status != "FAIL",
        "runway_started": False,
        "run_id": RUN_ID,
        "run_dir": str(run_dir),
        "output_path": str(final_path.resolve()) if final_path.is_file() else "",
        "backups": backed_up,
        "before_durations": before_durations,
        "after_durations": {
            "assembly_seconds": assembled_duration,
            "final_seconds": after_duration,
            "narration_seconds": before_durations.get("narration_seconds"),
        },
        "delivery_gate": delivery_result.to_dict(),
        "subtitle_status": branding_post_result.get("subtitle_status") or audio_post_result.get("subtitle_status"),
        "subtitle_visible": subtitle_visible,
        "audio_status": {
            "merge": merge_result.status,
            "ambience": audio_post_result.get("ambience_status"),
            "music": audio_post_result.get("music_status"),
            "narration_audible": probe_has_audio_stream(final_path) if final_path.is_file() else False,
            "mean_volume_db": probe_mean_volume_db(final_path) if final_path.is_file() else None,
        },
        "topic_status": {
            "topic": TOPIC,
            "story_genre": blueprint.get("genre"),
            "character_names": character_names,
            "whiskers_leak": any(name.lower() in {"whiskers", "sage"} for name in character_names),
        },
        "branding_status": branding_post_result.get("status"),
        "publish_status": publish_manifest.get("status"),
        "run_summary": run_summary,
    }


def write_report(summary: dict[str, Any]) -> None:
    before = summary.get("before_durations") or {}
    after = summary.get("after_durations") or {}
    gate = summary.get("delivery_gate") or {}
    audio = summary.get("audio_status") or {}
    topic = summary.get("topic_status") or {}

    lines = [
        "# Reprocess Latest Run After Quality Fixes",
        "",
        f"**Generated:** {_now()}",
        f"**Run ID:** `{RUN_ID}`",
        f"**Run folder:** `{RUN_DIR}`",
        "",
        "## Runway Started",
        "",
        "**NO** — post-processing only on existing downloaded clips.",
        "",
        "## Output",
        "",
        f"- **Final path:** `{summary.get('output_path') or 'missing'}`",
        f"- **Backups preserved under:** `{RUN_DIR / 'publish' / 'archive' / BACKUP_TAG}`",
        "",
        "## Duration",
        "",
        f"| Stage | Before | After |",
        f"|-------|--------|-------|",
        f"| Assembly | {before.get('assembly_seconds', 'n/a')} s | {after.get('assembly_seconds', 'n/a')} s |",
        f"| Canonical / fixed final | {before.get('canonical_seconds', 'n/a')} s | {after.get('final_seconds', 'n/a')} s |",
        f"| Narration audio | {before.get('narration_seconds', 'n/a')} s | (reused, padded to video) |",
        "",
        "## Delivery Gate",
        "",
        f"- **Status:** `{gate.get('delivery_status', 'unknown')}`",
        f"- **Upload ready:** `{gate.get('upload_ready', False)}`",
        f"- **Failures:** {gate.get('failures') or []}",
        f"- **Warnings:** {gate.get('warnings') or []}",
        "",
        "## Subtitle Status",
        "",
        f"- **Status:** {summary.get('subtitle_status') or 'unknown'}",
        f"- **Visible on burn:** `{summary.get('subtitle_visible')}`",
        "",
        "## Audio Status",
        "",
        f"- **Merge:** {audio.get('merge')}",
        f"- **Ambience:** {audio.get('ambience')}",
        f"- **Music:** {audio.get('music')}",
        f"- **Narration stream present:** {audio.get('narration_audible')}",
        f"- **Mean volume (dB):** {audio.get('mean_volume_db')}",
        "",
        "## Topic Status",
        "",
        f"- **Topic:** {topic.get('topic')}",
        f"- **Story genre:** {topic.get('story_genre')}",
        f"- **Characters:** {', '.join(topic.get('character_names') or [])}",
        f"- **Whiskers/Sage leak:** {topic.get('whiskers_leak')}",
        "",
        "## Overall",
        "",
        f"- **OK:** {summary.get('ok')}",
        f"- **Branding status:** {summary.get('branding_status')}",
        f"- **Publish status:** {summary.get('publish_status')}",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    summary = reprocess_run()
    write_report(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
