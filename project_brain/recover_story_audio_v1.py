"""Recover cinematic story audio for an existing run — no Runway, browser, or credits."""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
from content_brain.execution.post_processing_recovery import recover_post_processing_inplace  # noqa: E402
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore  # noqa: E402
from content_brain.story.story_package import load_story_package, story_package_path  # noqa: E402

DEFAULT_RUN_ID = "cb_e2e_20260611_225308_dc20bc1f"
DEFAULT_RUN_DIR = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"
DEFAULT_TOPIC = "Cute orange cartoon cat explorer"


def _read_json(path: Path) -> dict:
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


def recover_story_audio(
    *,
    project_root: Path | None = None,
    run_dir: Path | None = None,
    run_id: str = "",
    topic: str = "",
    rebrand: bool = True,
) -> dict:
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

    cinematic = run_cinematic_audio_pipeline(
        project_root=root,
        run_dir=run_path,
        story_package=story_package,
        video_path=video_path,
        duration_seconds=duration,
        narration_provider=provider,
        allow_local_fallback=True,
    )

    summary = {
        "ok": cinematic.get("status") == "completed",
        "run_id": run_id,
        "run_dir": str(run_path),
        "story_package_path": str(story_package_path(root, run_id)),
        "cinematic": cinematic,
    }

    if rebrand and summary["ok"]:
        report = {
            "content_brain_run_id": run_id,
            "content_brain_topic": topic,
            "clip_count": int(story_package.get("metadata", {}).get("clip_count") or 3),
            "simulate": False,
            "ok": True,
        }
        recovery = recover_post_processing_inplace(
            root,
            run_dir=run_path,
            report=report,
            reassemble=False,
            register_asset=False,
        )
        summary["post_processing_recovery"] = recovery
        summary["ok"] = bool(recovery.get("ok"))

    return summary


def main() -> int:
    summary = recover_story_audio()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
