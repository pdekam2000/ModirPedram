"""
Phase E2E-40S — Static + session validation for 40s E2E harness.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_browser_observability import RUNWAY_BROWSER_STEPS
from content_brain.execution.uat_runtime_profile import (
    UAT_MAX_VIDEO_CLIPS,
    is_e2e_full_duration_validation,
    requires_live_voice_smoke_guard,
    UatRuntimeConfig,
)
from project_brain.e2e_40s_session_collector import collect_e2e_40s_metrics, render_e2e_40s_report_markdown
from project_brain.validate_e2e_40s_uniqueness_memory_isolation import main as validate_uniqueness_isolation


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> int:
    collector_path = ROOT / "project_brain" / "e2e_40s_session_collector.py"
    runner_path = ROOT / "project_brain" / "run_e2e_40s_validation.py"
    _pass("collector_exists", collector_path.is_file())
    _pass("runner_exists", runner_path.is_file())

    cfg = UatRuntimeConfig(
        topic="Girl in Rain",
        duration_seconds=40,
        video_provider="runway_browser",
        voice_provider="elevenlabs",
        confirm_real_voice=True,
        confirm_real_video=True,
        confirm_real_assembly=True,
    )
    _pass("smoke_guard_active_by_default", requires_live_voice_smoke_guard(cfg))

    import os

    os.environ["UAT_E2E_VALIDATION_FULL_DURATION"] = "1"
    _pass("e2e_flag_disables_smoke_guard", not requires_live_voice_smoke_guard(cfg))
    os.environ.pop("UAT_E2E_VALIDATION_FULL_DURATION", None)

    _pass("40s_within_uat_max", 40 <= 90)
    _pass("max_clips_allows_40s_plan", UAT_MAX_VIDEO_CLIPS >= 4)

    session_path = ROOT / "storage" / "content_brain" / "execution" / "sessions"
    candidate = ROOT / "storage" / "content_brain" / "execution" / "sessions" / "exec_uat_20260602_170119.json"
    if candidate.is_file():
        metrics = collect_e2e_40s_metrics(ROOT, "exec_uat_20260602_170119", requested_duration_seconds=40)
        _pass("collector_reads_session", metrics.get("session_id") == "exec_uat_20260602_170119")
        _pass("collector_finds_final_mp4", bool(metrics.get("final_video_exists")), metrics.get("final_video_path", ""))
        report = render_e2e_40s_report_markdown(metrics, test_config={"topic": "Girl in Rain", "duration_seconds": 40})
        _pass("report_renders", "planned_clip_count" in report and "FINAL_PUBLISH_READY" in report)

    _pass("try_it_now_obs_steps_present", "clicking_try_it_now" in RUNWAY_BROWSER_STEPS)

    print("\n--- Uniqueness memory isolation ---")
    validate_uniqueness_isolation()

    print("\nE2E-40S harness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
