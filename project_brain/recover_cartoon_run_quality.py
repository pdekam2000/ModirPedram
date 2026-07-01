"""Recover post-processing quality v3 for the cartoon cat run — no Runway credits."""

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

from content_brain.audio.local_audio_assets import ensure_local_audio_assets  # noqa: E402
from content_brain.branding.branding_runtime import FINAL_BRANDED_VIDEO_V3_NAME  # noqa: E402
from content_brain.execution.post_processing_recovery import recover_post_processing_inplace  # noqa: E402
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore  # noqa: E402

TARGET_RUN_ID = "cb_e2e_20260611_225308_dc20bc1f"
TARGET_RUN_DIR = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"


def _ensure_quality_profile() -> None:
    store = ProductChannelProfileStore(ROOT)
    profile = store.load()
    profile["music_provider"] = "local"
    profile["music_track_path"] = "assets/audio/music/whimsical_adventure.mp3"
    profile["music_volume"] = 0.30
    profile["ducking_strength"] = 0.18
    profile["ambience_folder"] = "assets/audio/ambience"
    profile["sfx_folder"] = "assets/audio/sfx"
    profile["subtitle_position"] = "lower_third"
    profile["narration_style"] = "child_story"
    profile["character_voice_mode"] = "multi_voice"
    profile.setdefault("default_narrator_voice", profile.get("default_voice") or "")
    profile.setdefault("child_friendly_voice", profile.get("default_voice") or "")
    profile.setdefault("character_voice_2", profile.get("child_friendly_voice") or profile.get("default_voice") or "")
    store.save(profile)


def _load_report() -> dict:
    for rel in (
        "project_brain/runway_phase_i_3clip_last_report.json",
        "project_brain/runway_live_smoke_last_report.json",
    ):
        path = ROOT / rel
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    return {
        "content_brain_run_id": TARGET_RUN_ID,
        "content_brain_topic": "Cute orange cartoon cat explorer",
        "clip_count": 3,
        "simulate": False,
        "ok": True,
        "downloaded_file_paths": [
            "downloads/runway/runway_clip_1_session_20260611_232949.mp4",
            "downloads/runway/runway_clip_2_session_20260611_234246.mp4",
            "downloads/runway/runway_clip_3_session_20260611_235854.mp4",
        ],
    }


def main() -> int:
    ensure_local_audio_assets(ROOT)
    _ensure_quality_profile()
    report = _load_report()
    report["content_brain_run_id"] = TARGET_RUN_ID
    report["downloaded_file_paths"] = [
        str(ROOT / "downloads" / "runway" / "runway_clip_1_session_20260611_232949.mp4"),
        str(ROOT / "downloads" / "runway" / "runway_clip_2_session_20260611_234246.mp4"),
        str(ROOT / "downloads" / "runway" / "runway_clip_3_session_20260611_235854.mp4"),
    ]
    summary = recover_post_processing_inplace(
        ROOT,
        run_dir=TARGET_RUN_DIR,
        report=report,
        reassemble=False,
        branded_video_name=FINAL_BRANDED_VIDEO_V3_NAME,
        register_asset=True,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
