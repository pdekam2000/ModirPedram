"""PHASE QUALITY-FIX-3 — real subtitle visibility validation on burned MP4."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.subtitle_format_engine import (
    MIN_BURN_FONT_SIZE,
    MAX_SUBTITLE_PSNR_DB,
    compare_subtitle_burn_visibility,
    compute_burn_font_size,
    validate_subtitle_visual_layout,
)

TARGET_RUN_DIR = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _read_ass_font_size(ass_path: Path) -> int | None:
    if not ass_path.is_file():
        return None
    match = re.search(r"Style:\s*[^,]+,[^,]+,(\d+),", ass_path.read_text(encoding="utf-8"))
    if not match:
        return None
    return int(match.group(1))


def _resolve_run_paths() -> tuple[Path, Path, Path, Path]:
    run_dir = TARGET_RUN_DIR
    publish = run_dir / "publish"
    final_dir = run_dir / "final"
    styled_ass = publish / "subtitles" / "subtitles_styled.ass"
    pre_burn = final_dir / "FINAL_RUNWAY_PHASE_I_MUSIC.mp4"
    if not pre_burn.is_file():
        pre_burn = final_dir / "FINAL_RUNWAY_PHASE_I_ENV.mp4"
    if not pre_burn.is_file():
        pre_burn = final_dir / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4"
    subtitled = final_dir / "FINAL_RUNWAY_PHASE_I_SUBTITLED.mp4"
    branded_v3 = publish / "FINAL_BRANDED_VIDEO_v3.mp4"
    after = branded_v3 if branded_v3.is_file() else subtitled
    return styled_ass, pre_burn, after, subtitled


def main() -> None:
    print("=== validate_subtitle_real_visibility ===")
    styled_ass, pre_burn, after_video, subtitled = _resolve_run_paths()

    _pass("styled_ass_exists", styled_ass.is_file(), str(styled_ass))
    _pass("final_subtitled_or_branded_exists", after_video.is_file(), str(after_video))

    font_size = _read_ass_font_size(styled_ass) or compute_burn_font_size(1280)
    _pass("ass_font_size_minimum", font_size >= MIN_BURN_FONT_SIZE, f"font_size={font_size}")
    _pass("preferred_font_size_range", font_size >= 52, f"font_size={font_size}")

    layout_issues = validate_subtitle_visual_layout(
        platform="youtube_shorts",
        font_size=font_size,
        margin_v=155,
        line_count=2,
        alignment=2,
        video_height=1280,
    )
    _pass("lower_third_layout", not layout_issues, str(layout_issues))

    compare_source = subtitled if subtitled.is_file() else after_video
    if pre_burn.is_file() and compare_source.is_file():
        visibility = compare_subtitle_burn_visibility(
            before_video=pre_burn,
            after_video=compare_source,
            sample_seconds=2.0,
        )
        psnr = visibility.get("psnr_avg")
        _pass("frame_psnr_measured", psnr is not None, f"psnr={psnr}")
        if psnr is not None:
            _pass("subtitle_visible_psnr", psnr <= MAX_SUBTITLE_PSNR_DB, f"psnr={psnr} threshold={MAX_SUBTITLE_PSNR_DB}")
    else:
        _pass("pre_burn_video_available", False, f"pre={pre_burn} after={compare_source}")

    print("=== complete ===")


if __name__ == "__main__":
    main()
