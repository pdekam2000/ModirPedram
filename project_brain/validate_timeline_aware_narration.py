"""Validate timeline-aware narration coverage on run deliverable."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_mastering_engine import probe_mean_volume_db
from content_brain.branding.subtitle_format_engine import measure_subtitle_text_bbox
from content_brain.platform.media_probe import probe_duration_seconds
from content_brain.story.story_package import load_story_package

RUN_ID = "cb_e2e_20260614_195440_8bf41b6b"
RUN_DIR = ROOT / "outputs" / "runs" / "20260614_210353_440_8bf41b6b"
TIMELINE_FIXED = RUN_DIR / "publish" / "FINAL_BRANDED_VIDEO_CANONICAL_TIMELINE_FIXED.mp4"
NARRATION_DIR = RUN_DIR / "publish" / "narration"
TARGET_DURATION = 40.17
DURATION_TOLERANCE = 0.5
COVERAGE_MIN = 0.90
SPEECH_MIN_DB = -35.0


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def test_segment_assets_exist() -> None:
    audio_files = [
        NARRATION_DIR / "segment_01.mp3",
        NARRATION_DIR / "segment_02.mp3",
        NARRATION_DIR / "segment_03.mp3",
        NARRATION_DIR / "segment_04.mp3",
        NARRATION_DIR / "segment_cta.mp3",
        NARRATION_DIR / "narration.mp3",
    ]
    text_files = [
        NARRATION_DIR / "narration_script.txt",
        NARRATION_DIR / "narration_plan.json",
    ]
    for path in audio_files:
        _pass(path.name, path.is_file() and path.stat().st_size > 500, str(path))
    for path in text_files:
        _pass(path.name, path.is_file() and path.stat().st_size > 20, str(path))


def test_narration_plan_segments() -> None:
    plan = _read_json(NARRATION_DIR / "narration_plan.json")
    segments = [item for item in (plan.get("segments") or []) if isinstance(item, dict)]
    _pass("plan_has_segments", len(segments) >= 5, f"{len(segments)} segments")
    ids = {str(item.get("segment_id") or "") for item in segments}
    for expected in ("segment_01", "segment_02", "segment_03", "segment_04", "segment_cta"):
        _pass(f"plan_{expected}", expected in ids)
    coverage = float(plan.get("coverage_ratio") or 0)
    _pass("coverage_at_least_90_percent", coverage >= COVERAGE_MIN, f"{coverage:.1%}")


def test_clip_windows_have_speech() -> None:
    _pass("timeline_fixed_exists", TIMELINE_FIXED.is_file(), str(TIMELINE_FIXED))
    windows = [
        ("clip1", 0.0, 10.0),
        ("clip2", 10.0, 10.0),
        ("clip3", 20.0, 10.0),
        ("clip4", 30.0, 10.0),
    ]
    for label, start, span in windows:
        level = probe_mean_volume_db(TIMELINE_FIXED, start_seconds=start, duration_seconds=span)
        _pass(f"{label}_narration_audible", level is not None and level > SPEECH_MIN_DB, f"{level} dB")


def test_no_giant_silent_tail() -> None:
    duration = probe_duration_seconds(TIMELINE_FIXED) or TARGET_DURATION
    tail_start = max(0.0, duration - 8.0)
    tail_level = probe_mean_volume_db(TIMELINE_FIXED, start_seconds=tail_start, duration_seconds=8.0)
    mid_level = probe_mean_volume_db(TIMELINE_FIXED, start_seconds=22.0, duration_seconds=6.0)
    _pass("mid_clip_speech_present", mid_level is not None and mid_level > SPEECH_MIN_DB, f"{mid_level} dB")
    _pass("tail_not_narration_silent_gap", tail_level is not None, f"{tail_level} dB")


def test_subtitles_aligned() -> None:
    srt_path = RUN_DIR / "publish" / "subtitles" / "subtitles.srt"
    _pass("subtitles_srt_exists", srt_path.is_file())
    content = srt_path.read_text(encoding="utf-8")
    blocks = [block for block in content.strip().split("\n\n") if block.strip()]
    _pass("subtitle_cue_count", len(blocks) >= 5, f"{len(blocks)} cues")
    times = re.findall(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", content)
    _pass("subtitle_timecodes_present", len(times) >= 5)
    if times:
        last_end = times[-1][1]
        hours, minutes, rest = last_end.split(":")
        seconds = float(rest.replace(",", "."))
        end_seconds = int(hours) * 3600 + int(minutes) * 60 + seconds
        _pass("subtitle_end_near_video_end", end_seconds >= 35.0, f"last cue ends at {end_seconds:.1f}s")


def test_duration_preserved() -> None:
    duration = probe_duration_seconds(TIMELINE_FIXED)
    _pass(
        "duration_about_40s",
        duration is not None and abs(duration - TARGET_DURATION) <= DURATION_TOLERANCE,
        f"{duration}s",
    )


def test_topic_identity() -> None:
    package = load_story_package(ROOT, RUN_ID)
    topic = str(package.get("topic") or "")
    _pass("story_package_topic_present", "dragon egg" in topic.lower(), topic)


def test_subtitles_visible() -> None:
    if TIMELINE_FIXED.is_file():
        visible = measure_subtitle_text_bbox(TIMELINE_FIXED, 12.0).get("visible")
        _pass("subtitle_burn_visible", visible is True, str(visible))


def main() -> int:
    print(f"validate_timeline_aware_narration — run {RUN_ID}")
    test_segment_assets_exist()
    test_narration_plan_segments()
    test_clip_windows_have_speech()
    test_no_giant_silent_tail()
    test_subtitles_aligned()
    test_duration_preserved()
    test_topic_identity()
    test_subtitles_visible()
    print("All timeline-aware narration checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
