"""PHASE QUALITY-FIX-2 — subtitle color/style validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.subtitle_format_engine import (
    HIGHLIGHT_COLOURS_BGR,
    MIN_BURN_FONT_SIZE,
    ass_contains_highlight_colours,
    compute_burn_font_size,
    format_ass_content,
    validate_subtitle_visual_layout,
    write_styled_ass_outputs,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_subtitle_color_style_v1 ===")
    sample_srt = """1
00:00:00,000 --> 00:00:03,000
Introduce the cute orange
cat and explorer

2
00:00:03,000 --> 00:00:06,000
Magical forest adventure
with sparkle discovery
"""
    ass_content, meta = format_ass_content(sample_srt, platform="youtube_shorts", video_height=1280)
    font_size = int(meta.get("font_size") or compute_burn_font_size(1280))
    _pass("ass_contains_highlight_colours", ass_contains_highlight_colours(ass_content))
    _pass("highlight_palette_size", len(HIGHLIGHT_COLOURS_BGR) >= 3)
    _pass("burn_font_size_minimum", font_size >= MIN_BURN_FONT_SIZE, f"font_size={font_size}")
    _pass("lower_third_margin", 130 <= int(meta.get("margin_v", 0)) <= 180)
    layout_issues = validate_subtitle_visual_layout(
        platform="youtube_shorts",
        font_size=font_size,
        margin_v=meta.get("margin_v"),
        line_count=2,
        video_height=1280,
    )
    _pass("lower_third_layout_pass", not layout_issues, str(layout_issues))
    _pass("border_style_outline", ",1,4,2,2," in ass_content.replace(" ", ""))
    _pass("no_fontsize_14_burn", f",{font_size}," in ass_content.split("ShortsLowerThird")[1].split("\n")[0])
    _pass("ass_uses_primary_override_tags", "\\1c" in ass_content)

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        publish = tmp / "publish" / "subtitles"
        debug = tmp / "debug"
        outputs = write_styled_ass_outputs(ass_content=ass_content, publish_subtitles_dir=publish, debug_dir=debug)
        _pass("styled_ass_written", Path(outputs["styled_ass_path"]).is_file())
        preview = Path(outputs.get("subtitle_style_preview_path") or "")
        _pass("preview_written", preview.is_file(), str(preview))
    print("=== complete ===")


if __name__ == "__main__":
    main()
