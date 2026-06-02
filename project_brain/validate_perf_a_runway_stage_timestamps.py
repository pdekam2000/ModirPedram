"""
Phase PERF-A — Runway stage timestamp instrumentation validation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_perf_timestamps import (
    STAGE_DOWNLOAD_COMPLETE,
    STAGE_DOWNLOAD_START,
    STAGE_GENERATE_CLICK,
    STAGE_URL_DETECTED,
    STAGE_VIDEO_VISIBLE,
    PERF_STAGES_ORDER,
    build_perf_report,
    mark_stage,
    maybe_mark_video_visible_in_ui,
    try_mark_perf_stage,
)
from content_brain.execution.runway_browser_observability import RunwayBrowserObservability
from content_brain.execution.session_store import ExecutionSessionStore
from orchestrators.runway_browser_orchestrator import RunwayBrowserOrchestrator
from providers.runway_output_url_classifier import is_real_runway_output_url


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


class _ObsSpy:
    def __init__(self) -> None:
        self.stages: list[str] = []

    def mark_perf_stage(self, stage: str) -> None:
        self.stages.append(stage)


def main() -> int:
    marks: dict[str, float] = {}
    base = time.monotonic()
    for i, stage in enumerate(PERF_STAGES_ORDER):
        marks[stage] = base + i * 2.0
    report = build_perf_report(marks, clip_index=1, wall_clock_anchor=1_700_000_000.0)
    durations = report.get("durations_seconds") or {}

    _pass("five_stages_defined", len(PERF_STAGES_ORDER) == 5)
    _pass(
        "generate_to_visible_duration",
        durations.get("generate_click_to_video_visible_in_ui") == 2.0,
        str(durations.get("generate_click_to_video_visible_in_ui")),
    )
    _pass(
        "visible_to_url_duration",
        durations.get("video_visible_in_ui_to_url_detected") == 2.0,
    )
    _pass(
        "url_to_download_start",
        durations.get("url_detected_to_download_start") == 2.0,
    )
    _pass(
        "download_start_to_complete",
        durations.get("download_start_to_download_complete") == 2.0,
    )
    _pass(
        "end_to_end_total",
        durations.get("generate_click_to_download_complete") == 8.0,
        str(durations.get("generate_click_to_download_complete")),
    )

    spy = _ObsSpy()
    marked = [False]
    real_url = "https://cdn.example.com/generated/clip.mp4"
    maybe_mark_video_visible_in_ui(
        spy,
        marked=marked,
        before_set=set(),
        current_sources=[real_url],
        visible_infos=[{"src": real_url}],
        is_real_url=is_real_runway_output_url,
    )
    _pass("video_visible_marked_once", spy.stages == [STAGE_VIDEO_VISIBLE])

    orch_src = (ROOT / "orchestrators/runway_browser_orchestrator.py").read_text(encoding="utf-8")
    obs_src = (ROOT / "content_brain/execution/runway_browser_observability.py").read_text(encoding="utf-8")
    _pass("orch_marks_download_stages", "STAGE_DOWNLOAD_START" in orch_src)
    _pass("orch_marks_url_detected", "STAGE_URL_DETECTED" in orch_src)
    _pass("obs_record_perf_report", "def record_perf_report" in obs_src)
    _pass("obs_mark_perf_stage", "def mark_perf_stage" in obs_src)
    _pass("provider_sets_clip_obs", "provider._runway_obs = clip_obs" in orch_src)

    # Session persist round-trip
    session_path = ROOT / "storage/content_brain/execution/sessions/validate_perf_a_obs_session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_id = "validate_perf_a_obs_session"
    session_path.write_text(
        json_min_session(session_id),
        encoding="utf-8",
    )
    store = ExecutionSessionStore(session_path.parent)
    obs = RunwayBrowserObservability(store, session_id, clip_index=1)
    obs.mark_perf_stage(STAGE_GENERATE_CLICK)
    time.sleep(0.01)
    obs.mark_perf_stage(STAGE_VIDEO_VISIBLE)
    obs.mark_perf_stage(STAGE_URL_DETECTED)
    obs.mark_perf_stage(STAGE_DOWNLOAD_START)
    obs.mark_perf_stage(STAGE_DOWNLOAD_COMPLETE)
    saved = obs.record_perf_report()
    _pass("persist_has_durations", bool(saved.get("durations_seconds")))

    print("[OK] validate_perf_a_runway_stage_timestamps")
    return 0


def json_min_session(session_id: str) -> str:
    import json

    return json.dumps(
        {
            "session_id": session_id,
            "execution_runtime": {"operations": {"runway_browser_obs": {}}},
        },
        indent=2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
