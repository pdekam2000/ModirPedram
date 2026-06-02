"""
Phase PERF-A — Runway browser per-clip stage timestamps and duration report.
"""

from __future__ import annotations

import time
from typing import Any

PERF_VERSION = "perf_a_v1"

STAGE_GENERATE_CLICK = "generate_click"
STAGE_VIDEO_VISIBLE = "video_visible_in_ui"
STAGE_URL_DETECTED = "url_detected"
STAGE_DOWNLOAD_START = "download_start"
STAGE_DOWNLOAD_COMPLETE = "download_complete"

PERF_STAGES_ORDER: tuple[str, ...] = (
    STAGE_GENERATE_CLICK,
    STAGE_VIDEO_VISIBLE,
    STAGE_URL_DETECTED,
    STAGE_DOWNLOAD_START,
    STAGE_DOWNLOAD_COMPLETE,
)

STAGE_LABELS: dict[str, str] = {
    STAGE_GENERATE_CLICK: "Generate Click",
    STAGE_VIDEO_VISIBLE: "Video Visible in Runway UI",
    STAGE_URL_DETECTED: "URL Detected",
    STAGE_DOWNLOAD_START: "Download Start",
    STAGE_DOWNLOAD_COMPLETE: "Download Complete",
}

# Durations reported as (from_stage, to_stage) human labels.
STAGE_DURATIONS: tuple[tuple[str, str], ...] = (
    (STAGE_GENERATE_CLICK, STAGE_VIDEO_VISIBLE),
    (STAGE_VIDEO_VISIBLE, STAGE_URL_DETECTED),
    (STAGE_URL_DETECTED, STAGE_DOWNLOAD_START),
    (STAGE_DOWNLOAD_START, STAGE_DOWNLOAD_COMPLETE),
    (STAGE_GENERATE_CLICK, STAGE_DOWNLOAD_COMPLETE),
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mark_stage(marks: dict[str, float], stage: str) -> bool:
    """Record monotonic timestamp for stage (first mark wins). Returns True if newly marked."""
    if stage not in PERF_STAGES_ORDER:
        return False
    if stage in marks:
        return False
    marks[stage] = time.monotonic()
    return True


def _duration_seconds(marks: dict[str, float], start: str, end: str) -> float | None:
    if start not in marks or end not in marks:
        return None
    return round(marks[end] - marks[start], 3)


def build_perf_report(
    marks: dict[str, float],
    *,
    clip_index: int | None = None,
    wall_clock_anchor: float | None = None,
) -> dict[str, Any]:
    """
    Build JSON-safe perf report from monotonic marks.
    wall_clock_anchor: time.time() at generate_click if known (for ISO timestamps).
    """
    ordered_marks = {stage: marks[stage] for stage in PERF_STAGES_ORDER if stage in marks}
    timestamps_iso: dict[str, str] = {}
    if wall_clock_anchor is not None and STAGE_GENERATE_CLICK in marks:
        t0 = marks[STAGE_GENERATE_CLICK]
        for stage, mono in ordered_marks.items():
            timestamps_iso[stage] = time.strftime(
                "%Y-%m-%dT%H:%M:%S",
                time.gmtime(wall_clock_anchor + (mono - t0)),
            )

    durations: dict[str, float | None] = {}
    duration_labels: dict[str, str] = {}
    for start, end in STAGE_DURATIONS:
        key = f"{start}_to_{end}"
        durations[key] = _duration_seconds(marks, start, end)
        start_label = STAGE_LABELS.get(start, start)
        end_label = STAGE_LABELS.get(end, end)
        duration_labels[key] = f"{start_label} -> {end_label}"

    return {
        "perf_version": PERF_VERSION,
        "clip_index": clip_index,
        "marks_monotonic": {k: round(v, 6) for k, v in ordered_marks.items()},
        "timestamps_iso": timestamps_iso,
        "durations_seconds": durations,
        "duration_labels": duration_labels,
        "reported_at": _now_iso(),
    }


def try_mark_perf_stage(obs: Any, stage: str) -> None:
    if obs is not None and hasattr(obs, "mark_perf_stage"):
        obs.mark_perf_stage(stage)


def maybe_mark_video_visible_in_ui(
    obs: Any,
    *,
    marked: list[bool],
    before_set: set[str],
    current_sources: list[str],
    visible_infos: list[dict[str, Any]],
    is_real_url: Any,
) -> None:
    """First real post-generate video in DOM marks video_visible_in_ui."""
    if marked[0]:
        return
    for src in current_sources:
        text = str(src or "").strip()
        if text and text not in before_set and is_real_url(text):
            try_mark_perf_stage(obs, STAGE_VIDEO_VISIBLE)
            marked[0] = True
            return
    for item in visible_infos:
        text = str(item.get("src") or "").strip()
        if text and text not in before_set and is_real_url(text):
            try_mark_perf_stage(obs, STAGE_VIDEO_VISIBLE)
            marked[0] = True
            return


def format_perf_report_lines(report: dict[str, Any]) -> list[str]:
    """Human-readable lines for logs / markdown."""
    clip = report.get("clip_index")
    header = f"=== Runway PERF-A clip {clip} ===" if clip is not None else "=== Runway PERF-A ==="
    lines = [header]
    for stage in PERF_STAGES_ORDER:
        iso = (report.get("timestamps_iso") or {}).get(stage)
        mono = (report.get("marks_monotonic") or {}).get(stage)
        if iso is not None:
            lines.append(f"  {STAGE_LABELS[stage]}: {iso}")
        elif mono is not None:
            lines.append(f"  {STAGE_LABELS[stage]}: t+{mono:.3f}s (monotonic from clip start)")
    lines.append("  --- stage durations (seconds) ---")
    labels = report.get("duration_labels") or {}
    durations = report.get("durations_seconds") or {}
    for start, end in STAGE_DURATIONS:
        key = f"{start}_to_{end}"
        value = durations.get(key)
        if value is None:
            continue
        label = labels.get(key, key)
        lines.append(f"  {label}: {value:.3f}s")
    return lines


__all__ = [
    "PERF_VERSION",
    "STAGE_GENERATE_CLICK",
    "STAGE_VIDEO_VISIBLE",
    "STAGE_URL_DETECTED",
    "STAGE_DOWNLOAD_START",
    "STAGE_DOWNLOAD_COMPLETE",
    "PERF_STAGES_ORDER",
    "STAGE_LABELS",
    "mark_stage",
    "try_mark_perf_stage",
    "maybe_mark_video_visible_in_ui",
    "build_perf_report",
    "format_perf_report_lines",
]
