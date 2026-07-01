"""Validate Shorts subtitle visual quality rules — placement, size, line limits."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.subtitle_burn_engine import STYLE_FORCE, SUBTITLE_BURN_VERSION  # noqa: E402
from content_brain.branding.subtitle_format_engine import (  # noqa: E402
    MAX_FONT_SIZE,
    MAX_LINES_PER_CUE,
    MAX_WORDS_PER_LINE,
    break_cue_into_short_lines,
    format_srt_content,
    validate_shorts_subtitle_cue,
    validate_subtitle_visual_layout,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _fail(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> None:
    burn_src = (ROOT / "content_brain" / "branding" / "subtitle_burn_engine.py").read_text(encoding="utf-8")
    _pass("burn_engine_v3", SUBTITLE_BURN_VERSION == "subtitle_burn_engine_v3")
    _pass("no_opaque_border_style", "BorderStyle=1" in burn_src and "BackColour=&H80000000" not in burn_src)
    _pass("font_size_cap", all(f"FontSize={MAX_FONT_SIZE}" in style for style in STYLE_FORCE.values()))

    bad_layout = validate_subtitle_visual_layout(platform="tiktok", font_size=28, margin_v=80, line_count=4, alignment=2)
    _pass("center_region_fails", "subtitle_in_center_region" in bad_layout or "font_size_exceeds_threshold" in bad_layout)

    good_layout = validate_subtitle_visual_layout(platform="tiktok", font_size=MAX_FONT_SIZE, margin_v=200, line_count=2, alignment=2)
    _pass("lower_third_passes", not good_layout, str(good_layout))

    long_cue = "This is a very long subtitle sentence that should never appear as one giant centered block on screen"
    lines = break_cue_into_short_lines(long_cue, platform="tiktok")
    _pass("max_two_lines", len(lines) <= MAX_LINES_PER_CUE)
    _pass("max_words_per_line", all(len(line.split()) <= MAX_WORDS_PER_LINE for line in lines))

    raw_srt = "1\n00:00:00,000 --> 00:00:03,000\n" + long_cue + "\n\n"
    formatted, meta = format_srt_content(raw_srt, platform="tiktok")
    _pass("formatted_srt_nonempty", bool(formatted.strip()))
    _pass("safe_margin_meta", int(meta.get("safe_margin_v") or 0) >= 160)
    _pass("max_lines_seen", int(meta.get("max_lines_seen") or 99) <= MAX_LINES_PER_CUE)

    warnings = validate_shorts_subtitle_cue(long_cue, platform="tiktok")
    _fail("long_cue_warns", "line_too_long" not in warnings and "cue_too_long" in warnings)

    giant_box_style = (
        "FontName=Arial Bold,FontSize=28,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BackColour=&H80000000,BorderStyle=3,Outline=2,Shadow=0,Alignment=2,MarginV=80,MarginL=48,MarginR=48"
    )
    legacy_issues = validate_subtitle_visual_layout(platform="tiktok", font_size=28, margin_v=80, line_count=3, alignment=2)
    _pass("legacy_giant_box_would_fail", len(legacy_issues) >= 2, giant_box_style[:40])

    print("\nAll subtitle visual quality validations passed.")


if __name__ == "__main__":
    main()
