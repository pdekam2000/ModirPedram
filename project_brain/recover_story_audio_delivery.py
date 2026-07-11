"""Recover story-audio delivery layer — remix audio, reburn subtitles, rebrand to v4.

No Runway, browser automation, or provider credits when dialogue clips already exist.
"""

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

from content_brain.audio.cinematic_audio_runtime import run_cinematic_audio_pipeline  # noqa: E402
from content_brain.audio.local_audio_assets import ensure_local_audio_assets  # noqa: E402
from content_brain.audio.subtitle_timing_engine import generate_timed_subtitles  # noqa: E402
from content_brain.branding.branding_runtime import (  # noqa: E402
    FINAL_BRANDED_VIDEO_V4_NAME,
    run_branding_runtime,
)
from content_brain.execution.runway_live_post_processor import ASSEMBLY_ASSEMBLED  # noqa: E402
from content_brain.platform.asset_library import sha256_file  # noqa: E402
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore  # noqa: E402
from content_brain.quality.delivery_reality_auditor import audit_delivery_reality  # noqa: E402
from content_brain.story.story_package import load_story_package, story_package_path  # noqa: E402

DEFAULT_RUN_ID = "cb_e2e_20260611_225308_dc20bc1f"
DEFAULT_RUN_DIR = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"
DEFAULT_TOPIC = "Cute orange cartoon cat explorer"
RECOVERY_VERSION = "recover_story_audio_delivery_v1"


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


def _probe_duration(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        import subprocess

        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return float((proc.stdout or "0").strip())
    except (OSError, ValueError):
        return None


def _audit_snapshot(*, video_path: Path, mix_path: Path, timeline: dict[str, Any], duration: float) -> dict[str, Any]:
    return audit_delivery_reality(
        {
            "final_video_path": str(video_path),
            "cinematic_audio_path": str(mix_path),
            "cinematic_video_path": str(video_path),
            "duration_seconds": duration,
            "dialogue_timeline": timeline,
        }
    ).to_dict()


def recover_story_audio_delivery(
    *,
    project_root: Path | None = None,
    run_dir: Path | None = None,
    run_id: str = "",
    topic: str = "",
) -> dict[str, Any]:
    root = Path(project_root or ROOT).resolve()
    run_path = Path(run_dir or DEFAULT_RUN_DIR).resolve()
    run_id = str(run_id or _read_json(run_path / "metadata" / "run_summary.json").get("run_id") or DEFAULT_RUN_ID)
    topic = str(topic or _read_json(run_path / "metadata" / "run_summary.json").get("topic") or DEFAULT_TOPIC)

    ensure_local_audio_assets(root)
    _ensure_profile()

    story_package = load_story_package(root, run_id)
    if not story_package:
        return {"ok": False, "error": "story_package_missing", "expected_path": str(story_package_path(root, run_id))}

    assembly = _read_json(run_path / "metadata" / "assembly_manifest.json")
    video_path = Path(str(assembly.get("output_path") or run_path / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"))
    if not video_path.is_file():
        return {"ok": False, "error": "assembly_video_missing", "video_path": str(video_path)}

    duration = float(assembly.get("duration_seconds") or story_package.get("metadata", {}).get("duration_seconds") or 12.0)
    profile = ProductChannelProfileStore(root).load()
    provider = str(profile.get("default_narration_provider") or "elevenlabs")

    v3_publish = run_path / "publish" / "FINAL_BRANDED_VIDEO_v3.mp4"
    v3_final = run_path / "final" / "FINAL_BRANDED_VIDEO_v3.mp4"
    before_video = v3_publish if v3_publish.is_file() else v3_final
    before_mix = run_path / "audio" / "FINAL_CINEMATIC_AUDIO.mp3"
    before_timeline = _read_json(run_path / "timeline" / "dialogue_timeline.json")
    before_audit = _audit_snapshot(
        video_path=before_video,
        mix_path=before_mix,
        timeline=before_timeline,
        duration=duration,
    ) if before_video.is_file() else {"status": "SKIP", "reason": "v3_missing"}

    cinematic = run_cinematic_audio_pipeline(
        project_root=root,
        run_dir=run_path,
        story_package=story_package,
        video_path=video_path,
        duration_seconds=duration,
        narration_provider=provider,
        allow_local_fallback=True,
    )
    if cinematic.get("status") != "completed":
        return {
            "ok": False,
            "error": "cinematic_pipeline_failed",
            "run_id": run_id,
            "run_dir": str(run_path),
            "cinematic": cinematic,
            "before_audit": before_audit,
        }

    runtime_timeline = _read_json(run_path / "timeline" / "dialogue_timeline.json")
    script_lines = [
        f"{line.get('speaker')}: {line.get('text')}"
        for line in runtime_timeline.get("lines") or []
        if isinstance(line, dict)
    ]
    subtitle_dir = run_path / "publish" / "subtitles"
    subtitles = generate_timed_subtitles(
        script="\n".join(script_lines),
        narration_audio_path=str(cinematic.get("cinematic_audio_path") or ""),
        output_dir=subtitle_dir,
        segments=script_lines,
        platform=str(profile.get("default_platform") or "tiktok"),
        run_dir=run_path,
        video_path=str(cinematic.get("cinematic_video_path") or ""),
    )
    styled_meta = dict(subtitles.metadata.get("shorts_format") or {})
    styled_ass = str(styled_meta.get("ass_path") or "")

    report_payload = {
        "content_brain_run_id": run_id,
        "content_brain_topic": topic,
        "clip_count": int(story_package.get("metadata", {}).get("clip_count") or 3),
        "simulate": False,
        "ok": True,
    }
    audio_post_result = {
        "status": "completed",
        "narrated_video_path": cinematic.get("cinematic_video_path"),
        "cinematic_video_path": cinematic.get("cinematic_video_path"),
        "cinematic_audio_path": cinematic.get("cinematic_audio_path"),
        "duration_seconds": subtitles.duration_seconds or duration,
        "subtitle_paths": [subtitles.srt_path, subtitles.vtt_path],
        "styled_ass_path": styled_ass,
        "delivery_reality_audit": cinematic.get("delivery_reality_audit"),
    }

    branding = run_branding_runtime(
        project_root=root,
        report=report_payload,
        assembly_manifest=assembly if assembly else {"status": ASSEMBLY_ASSEMBLED, "output_path": str(video_path), "duration_seconds": duration},
        audio_post_result=audio_post_result,
        output_dir=run_path / "final",
        branded_video_name=FINAL_BRANDED_VIDEO_V4_NAME,
    )

    branded_source = Path(str(branding.get("final_branded_video_path") or ""))
    publish_v4 = run_path / "publish" / FINAL_BRANDED_VIDEO_V4_NAME
    if branded_source.is_file():
        publish_v4.parent.mkdir(parents=True, exist_ok=True)
        if not publish_v4.is_file() or sha256_file(branded_source) != sha256_file(publish_v4):
            shutil.copy2(branded_source, publish_v4)

    after_mix = Path(str(cinematic.get("cinematic_audio_path") or before_mix))
    after_audit = audit_delivery_reality(
        {
            "final_video_path": str(publish_v4 if publish_v4.is_file() else branded_source),
            "cinematic_audio_path": str(after_mix),
            "cinematic_video_path": str(cinematic.get("cinematic_video_path") or ""),
            "duration_seconds": duration,
            "dialogue_timeline": runtime_timeline,
            "ffmpeg_filter_proof": (cinematic.get("mix_result") or {}).get("ffmpeg_filter_proof"),
            "mix_version": (cinematic.get("mix_result") or {}).get("version"),
        },
        check_subtitles=True,
    )

    subtitle_step = dict((branding.get("steps") or {}).get("subtitles") or {})
    ok = (
        cinematic.get("status") == "completed"
        and branding.get("status") == "completed"
        and after_audit.status == "PASS"
        and bool(subtitle_step.get("burn_visible_enough"))
    )

    return {
        "ok": ok,
        "version": RECOVERY_VERSION,
        "run_id": run_id,
        "run_dir": str(run_path),
        "story_package_path": str(story_package_path(root, run_id)),
        "before": {
            "video_path": str(before_video) if before_video.is_file() else "",
            "mix_path": str(before_mix) if before_mix.is_file() else "",
            "mix_duration_seconds": _probe_duration(before_mix),
            "audit": before_audit,
        },
        "after": {
            "cinematic_audio_path": str(after_mix),
            "cinematic_video_path": cinematic.get("cinematic_video_path"),
            "mix_duration_seconds": _probe_duration(after_mix),
            "branded_video_path": str(branded_source),
            "publish_v4_path": str(publish_v4) if publish_v4.is_file() else "",
            "audio_delivery_report_path": cinematic.get("audio_delivery_report_path"),
            "audit": after_audit.to_dict(),
            "subtitle_burn": subtitle_step,
        },
        "cinematic": cinematic,
        "branding": branding,
    }


def main() -> int:
    summary = recover_story_audio_delivery()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
