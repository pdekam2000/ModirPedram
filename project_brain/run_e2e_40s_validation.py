"""
Phase E2E-40S — Run or analyze full production UAT pipeline at 40s (validation only).

Usage:
  python project_brain/run_e2e_40s_validation.py --run
  python project_brain/run_e2e_40s_validation.py --session-id exec_uat_YYYYMMDD_HHMMSS
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.env_bootstrap import bootstrap_project_env

bootstrap_project_env()

from content_brain.execution.uat_real_video_bridge import validate_runway_browser_operator_ready
from content_brain.execution.uat_runtime_engine import UATRuntimeEngine
from content_brain.execution.uat_runtime_profile import UatRuntimeConfig
from project_brain.e2e_40s_planning_probe import run_e2e_40s_planning_probe
from project_brain.e2e_40s_session_collector import collect_e2e_40s_metrics, render_e2e_40s_report_markdown

REPORT_PATH = ROOT / "project_brain" / "PHASE_E2E_40S_VALIDATION_REPORT.md"

TEST_CONFIG = {
    "topic": "Girl in Rain",
    "platform": "youtube_shorts",
    "duration_seconds": 40,
    "video_provider": "runway_browser",
    "voice_provider": "elevenlabs",
    "confirm_real_voice": True,
    "confirm_real_video": True,
    "confirm_real_assembly": True,
    "subtitles_enabled": True,
    "e2e_full_duration": True,
}


def _build_config() -> UatRuntimeConfig:
    return UatRuntimeConfig(
        topic=TEST_CONFIG["topic"],
        platform=TEST_CONFIG["platform"],
        duration_seconds=int(TEST_CONFIG["duration_seconds"]),
        video_provider=TEST_CONFIG["video_provider"],
        voice_provider=TEST_CONFIG["voice_provider"],
        confirm_real_voice=TEST_CONFIG["confirm_real_voice"],
        confirm_real_video=TEST_CONFIG["confirm_real_video"],
        confirm_real_assembly=TEST_CONFIG["confirm_real_assembly"],
        niche="general",
    ).normalized()


def run_pipeline() -> dict:
    os.environ["UAT_E2E_VALIDATION_FULL_DURATION"] = "1"
    validate_runway_browser_operator_ready(ROOT)
    engine = UATRuntimeEngine(ROOT)
    print("[E2E-40S] Starting full pipeline (40s, real Runway + ElevenLabs + assembly + subtitles)...")
    return engine.run_sync(_build_config())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase E2E-40S validation runner")
    parser.add_argument("--run", action="store_true", help="Execute full UAT pipeline (long-running).")
    parser.add_argument("--session-id", help="Analyze existing session instead of running.")
    args = parser.parse_args(argv)

    session_id = args.session_id
    result: dict | None = None

    probe = run_e2e_40s_planning_probe(
        ROOT,
        topic=TEST_CONFIG["topic"],
        platform=TEST_CONFIG["platform"],
        user_duration_seconds=int(TEST_CONFIG["duration_seconds"]),
        provider_name=TEST_CONFIG["video_provider"],
    )
    print(
        f"[E2E-40S] Planning probe: decision={probe.get('decision')} "
        f"clips={probe.get('planned_clip_count')} "
        f"production_memory_unchanged={probe.get('production_memory_unchanged')}"
    )

    if args.run:
        try:
            result = run_pipeline()
            session_id = str(result.get("session_id") or "")
            print(f"[E2E-40S] Pipeline finished session_id={session_id} status={result.get('status')}")
        except Exception as exc:
            print(f"[E2E-40S] Pipeline failed: {exc}")
            print(f"[E2E-40S] See PHASE_E2E_40S_VALIDATION_REPORT.md (update with --session-id if partial session exists).")
            return 1

    if not session_id:
        print("Provide --run or --session-id")
        return 2

    metrics = collect_e2e_40s_metrics(
        ROOT,
        session_id,
        requested_duration_seconds=int(TEST_CONFIG["duration_seconds"]),
    )
    report = render_e2e_40s_report_markdown(metrics, test_config=TEST_CONFIG)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"[E2E-40S] Report written: {REPORT_PATH}")
    print(
        f"[E2E-40S] planned={metrics.get('planned_clip_count')} "
        f"generated={metrics.get('generated_clip_count')} "
        f"downloaded={metrics.get('downloaded_clip_count')} "
        f"final={metrics.get('final_video_exists')}"
    )
    return 0 if metrics.get("final_video_exists") else 1


if __name__ == "__main__":
    raise SystemExit(main())
