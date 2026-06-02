"""
Phase PERF-A — Print Runway stage timestamps and durations from session JSON or synthetic demo.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_browser_observability import extract_runway_browser_obs_from_session
from content_brain.execution.runway_perf_timestamps import (
    STAGE_DURATIONS,
    STAGE_LABELS,
    STAGE_GENERATE_CLICK,
    STAGE_DOWNLOAD_COMPLETE,
    STAGE_DOWNLOAD_START,
    STAGE_URL_DETECTED,
    STAGE_VIDEO_VISIBLE,
    build_perf_report,
    format_perf_report_lines,
    mark_stage,
)
from content_brain.execution.session_store import ExecutionSessionStore


def _load_session(session_id: str) -> dict:
    store = ExecutionSessionStore(ROOT / "storage" / "content_brain" / "execution" / "sessions")
    return store.load_session(session_id)


def _print_clip_report(report: dict) -> None:
    for line in format_perf_report_lines(report):
        print(line)
    durations = report.get("durations_seconds") or {}
    labels = report.get("duration_labels") or {}
    print("  | Stage | Duration (s) |")
    print("  |-------|-------------|")
    for start, end in STAGE_DURATIONS:
        key = f"{start}_to_{end}"
        value = durations.get(key)
        if value is None:
            continue
        label = labels.get(key, key)
        print(f"  | {label} | {value:.3f} |")


def report_from_session(session_id: str) -> int:
    session = _load_session(session_id)
    extracted = extract_runway_browser_obs_from_session(session)
    obs = extracted.get("runway_browser_obs") or {}
    perf_clips = list(obs.get("perf_clips") or [])
    last = obs.get("last_perf_report")

    if not perf_clips and not last:
        print(f"No PERF-A data in session {session_id}.")
        print("Run a UAT with runway_browser after PERF-A instrumentation.")
        return 1

    print(f"PERF-A report for session: {session_id}\n")
    if perf_clips:
        for entry in sorted(perf_clips, key=lambda item: int(item.get("clip_index") or 0)):
            report = entry.get("perf_timestamps") or {}
            if report:
                _print_clip_report(report)
                print()
    elif isinstance(last, dict):
        _print_clip_report(last)
    return 0


def demo_synthetic_report() -> None:
    """Illustrate expected report shape (unit timing, not a live Runway run)."""
    marks: dict[str, float] = {}
    t = 0.0
    for stage in (
        STAGE_GENERATE_CLICK,
        STAGE_VIDEO_VISIBLE,
        STAGE_URL_DETECTED,
        STAGE_DOWNLOAD_START,
        STAGE_DOWNLOAD_COMPLETE,
    ):
        marks[stage] = t
        t += 12.5
    report = build_perf_report(marks, clip_index=1, wall_clock_anchor=1_700_000_000.0)
    print("Synthetic PERF-A example (not from production):\n")
    _print_clip_report(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Runway PERF-A stage timing report")
    parser.add_argument("--session-id", help="Execution session id (e.g. exec_uat_...)")
    parser.add_argument("--demo", action="store_true", help="Print synthetic example report")
    args = parser.parse_args()

    if args.demo:
        demo_synthetic_report()
        return 0
    if not args.session_id:
        parser.print_help()
        return 2
    return report_from_session(args.session_id)


if __name__ == "__main__":
    raise SystemExit(main())
