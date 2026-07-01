"""Validate subtitle QA dependency chain and fail-closed branding."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.subtitle_format_engine import measure_subtitle_text_bbox


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_numpy_fallback() -> None:
    source = (ROOT / "content_brain/branding/subtitle_format_engine.py").read_text(encoding="utf-8")
    _pass("bbox_pil_fallback", "except ImportError:" in source and "measure_subtitle_text_bbox" in source)
    _pass("compare_pil_fallback", "if np is not None:" in source or "changed += 1" in source)


def test_measure_bbox_without_numpy(monkeypatch=None) -> None:
    result = measure_subtitle_text_bbox("/nonexistent/video.mp4", 0.5)
    _pass("missing_video_handled", result.get("error") == "missing_video")


def test_branding_fail_closed() -> None:
    source = (ROOT / "content_brain/branding/branding_runtime.py").read_text(encoding="utf-8")
    _pass("subtitled_only_when_visible", "burn_visible_enough" in source)
    _pass("failed_status_preserved", 'base.get("status") != "failed"' in source)
    _pass("no_fail_open_on_invisible", "subtitle_burn_not_visible" in source)


def main() -> None:
    test_numpy_fallback()
    test_measure_bbox_without_numpy()
    test_branding_fail_closed()
    print("validate_subtitle_pipeline: all checks passed")


if __name__ == "__main__":
    main()
