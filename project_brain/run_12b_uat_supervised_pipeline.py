"""
Phase 12B — supervised UAT pipeline (CLI-first, one topic → one final video).

Run:
  python -m project_brain.run_12b_uat_supervised_pipeline \\
    --topic "cat in the streets of Los Angeles" \\
    --platform youtube_shorts \\
    --duration-seconds 45 \\
    --video-provider runway_browser \\
    --voice-provider elevenlabs \\
    --confirm-real-voice \\
    --confirm-real-assembly \\
    --open-folder
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from content_brain.execution.uat_runtime_engine import (
    UATRuntimeEngine,
    run_uat_pipeline,
    write_uat_report,
)
from content_brain.execution.uat_runtime_profile import UatRuntimeConfig, uat_default_duration_seconds
from core.env_bootstrap import bootstrap_project_env

# Re-export stage helpers for validate_12b_uat_supervised_pipeline.
from content_brain.execution.uat_runtime_engine import (  # noqa: F401
    _run_assembly_stage,
    _run_voice_stage,
)


def parse_uat_args(argv: list[str] | None = None) -> UatRuntimeConfig:
    parser = argparse.ArgumentParser(description="Phase 12B — supervised UAT pipeline (one topic, one video).")
    parser.add_argument("--topic", required=True, help="Video topic (required).")
    parser.add_argument("--platform", default="youtube_shorts", help="Target platform.")
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=None,
        help="Target duration (15–90s). Default: 10s Runway/mock, 8s Hailuo.",
    )
    parser.add_argument("--video-provider", default="runway_browser", help="Video provider (default: runway_browser).")
    parser.add_argument("--voice-provider", default="elevenlabs", help="Voice provider (elevenlabs or mock).")
    parser.add_argument("--niche", default="general", help="Content niche profile.")
    parser.add_argument("--confirm-real-voice", action="store_true", help="Enable gated live ElevenLabs TTS.")
    parser.add_argument(
        "--confirm-real-video",
        action="store_true",
        help="Enable supervised real Runway browser video (requires Chrome CDP + login).",
    )
    parser.add_argument("--confirm-real-assembly", action="store_true", help="Enable gated real FFmpeg assembly.")
    parser.add_argument("--open-folder", action="store_true", help="Open artifact folder after completion (Windows).")
    args = parser.parse_args(argv)
    duration = args.duration_seconds
    if duration is None:
        duration = uat_default_duration_seconds(args.video_provider)
    return UatRuntimeConfig(
        topic=args.topic,
        platform=args.platform,
        duration_seconds=duration,
        video_provider=args.video_provider,
        voice_provider=args.voice_provider,
        confirm_real_voice=bool(args.confirm_real_voice),
        confirm_real_video=bool(args.confirm_real_video),
        confirm_real_assembly=bool(args.confirm_real_assembly),
        open_folder=bool(args.open_folder),
        niche=args.niche,
    ).normalized()


def _open_folder(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def main(argv: list[str] | None = None) -> int:
    bootstrap = bootstrap_project_env()
    root = Path(bootstrap["project_root"])
    config = parse_uat_args(argv)
    print(f"Phase 12B — UAT pipeline starting for topic: {config.topic!r}")

    engine = UATRuntimeEngine(root)
    try:
        result = engine.run_sync(config)
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        return 1

    if config.open_folder and result.get("artifact_folder"):
        try:
            _open_folder(result["artifact_folder"])
        except OSError as exc:
            result.setdefault("warnings", []).append(f"Could not open folder: {exc}")

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nReport: {result.get('runtime_report_path')}")
    print(f"Review template: {result.get('review_template_path')}")
    print(f"\n{'PASS' if result.get('success') else 'FAIL'} — 12B UAT pipeline")
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
