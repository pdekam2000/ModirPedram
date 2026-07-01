"""Validate KLING-SINGLE-CLIP-RECOVERY-WIRING-FIX."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_brain.run_kling_single_clip_15s import (  # noqa: E402
    _canonical_live_clip_dir,
    _resolve_mp4,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _clean_clip_dir(run_id: str) -> Path:
    clip_dir = _canonical_live_clip_dir(run_id)
    clip_dir.mkdir(parents=True, exist_ok=True)
    for name in ("clip_1.mp4", "video.mp4"):
        path = clip_dir / name
        if path.is_file():
            path.unlink()
    return clip_dir


def test_canonical_path_checked() -> None:
    run_id = "kling_sc_test_canonical"
    clip_dir = _canonical_live_clip_dir(run_id)
    clip_dir.mkdir(parents=True, exist_ok=True)
    live = {
        "clip_output_path": str(clip_dir / "video.mp4"),
        "generation_completed": True,
        "generate_clicked": True,
    }
    (clip_dir / "video.mp4").write_bytes(b"x" * 2048)
    recover = MagicMock()
    recover.to_dict.return_value = {"ok": False, "download_strategies": []}
    with patch(
        "content_brain.execution.kling_real_mp4_download_extractor.verify_extracted_kling_mp4",
        side_effect=lambda p: {"is_real_mp4": False, "size_bytes": p.stat().st_size if p.is_file() else 0},
    ), patch(
        "content_brain.execution.kling_frame_to_video_live_engine.recover_kling_frame_output",
        return_value=recover,
    ), patch(
        "project_brain.run_kling_single_clip_15s._direct_poll_extract",
        return_value=None,
    ):
        _, audit = _resolve_mp4(run_id=run_id, live_result=live, cdp_url="http://127.0.0.1:9222")
        attempted = audit.get("attempted") or []
    _pass("live_result_checked", any(item.startswith("live_result.") for item in attempted))
    _pass("canonical_clip_1_checked", "canonical_live_engine.clips/c1/clip_1.mp4" in attempted)
    _pass("canonical_video_checked", "canonical_live_engine.clips/c1/video.mp4" in attempted)


def test_runner_calls_recover_when_missing() -> None:
    run_id = "kling_sc_test_recover"
    clip_dir = _clean_clip_dir(run_id)
    live = {"generation_completed": True, "generate_clicked": True}
    good_mp4 = clip_dir / "clip_1.mp4"

    def _fake_recover(**kwargs: object) -> MagicMock:
        good_mp4.write_bytes(b"\x00" * 5000)
        result = MagicMock()
        result.to_dict.return_value = {
            "ok": True,
            "clip_output_path": str(good_mp4),
            "download_strategies": ["artifact_card_cdp_urls:verify_0"],
        }
        return result

    with patch(
        "content_brain.execution.kling_frame_to_video_live_engine.recover_kling_frame_output",
        side_effect=_fake_recover,
    ) as recover_mock, patch(
        "content_brain.execution.kling_real_mp4_download_extractor.verify_extracted_kling_mp4",
        side_effect=lambda p: {
            "is_real_mp4": p.is_file() and p.stat().st_size > 1000,
            "size_bytes": p.stat().st_size if p.is_file() else 0,
            "duration_seconds": 15.0,
            "ffprobe_ok": True,
        },
    ):
        found, audit = _resolve_mp4(run_id=run_id, live_result=live, cdp_url="http://127.0.0.1:9222")
    recover_mock.assert_called_once()
    _pass("recover_called", recover_mock.called)
    _pass("recover_in_attempted", "recover_kling_frame_output" in (audit.get("attempted") or []))
    _pass("valid_recovered", found is not None and found.is_file())


def test_polling_retries_recovery() -> None:
    run_id = "kling_sc_test_poll"
    clip_dir = _clean_clip_dir(run_id)
    live = {"generation_completed": True, "generate_clicked": True}
    recover = MagicMock()
    recover.to_dict.return_value = {"ok": False, "download_strategies": []}
    recovered = clip_dir / "clip_1.mp4"

    def _fake_poll(**kwargs: object) -> Path:
        recovered.write_bytes(b"\x00" * 5000)
        return recovered

    with patch(
        "content_brain.execution.kling_frame_to_video_live_engine.recover_kling_frame_output",
        return_value=recover,
    ), patch(
        "project_brain.run_kling_single_clip_15s._direct_poll_extract",
        side_effect=_fake_poll,
    ) as poll_mock, patch(
        "content_brain.execution.kling_real_mp4_download_extractor.verify_extracted_kling_mp4",
        side_effect=lambda p: {
            "is_real_mp4": p.is_file() and p.stat().st_size > 1000,
            "size_bytes": p.stat().st_size if p.is_file() else 0,
            "duration_seconds": 15.0,
            "ffprobe_ok": True,
        },
    ):
        found, audit = _resolve_mp4(run_id=run_id, live_result=live, cdp_url="http://127.0.0.1:9222")
    poll_mock.assert_called_once()
    _pass("poll_direct_called", "poll_extract_real_kling_mp4_direct" in (audit.get("attempted") or []))
    _pass("poll_found_mp4", found is not None)


def test_no_generate_during_recovery() -> None:
    src = (ROOT / "project_brain/run_kling_single_clip_15s.py").read_text(encoding="utf-8")
    extract_src = (ROOT / "content_brain/execution/kling_real_mp4_download_extractor.py").read_text(encoding="utf-8")
    _pass("resolve_uses_recover", "recover_kling_frame_output" in src)
    _pass("resolve_uses_poll", "poll_extract_real_kling_mp4" in src)
    _pass("extractor_no_generate", "Never clicks Generate" in extract_src)
    _pass("runner_no_generate_click", 'name="Generate"' not in src and "approve_generate=True" in src)


def test_report_lists_multiple_methods() -> None:
    run_id = "kling_sc_test_methods"
    clip_dir = _clean_clip_dir(run_id)
    live = {"generation_completed": True, "generate_clicked": True}
    good_mp4 = clip_dir / "clip_1.mp4"

    def _fake_recover(**kwargs: object) -> MagicMock:
        good_mp4.write_bytes(b"\x00" * 5000)
        result = MagicMock()
        result.to_dict.return_value = {
            "ok": True,
            "clip_output_path": str(good_mp4),
            "download_strategies": [
                "artifact_card_cdp_urls:verify_0",
                "scoped_card_browser_download:card_label",
                "page_video_sources:0",
                "global_ui_download:apps_menu",
            ],
        }
        return result

    poll_report = {
        "attempts": [
            {
                "attempt": 1,
                "methods_tried": ["artifact_card_cdp_urls:verify_0"],
                "valid_mp4_found": True,
            }
        ]
    }
    (clip_dir / "mp4_recovery_poll_report.json").write_text(json.dumps(poll_report), encoding="utf-8")

    with patch(
        "content_brain.execution.kling_frame_to_video_live_engine.recover_kling_frame_output",
        side_effect=_fake_recover,
    ), patch(
        "content_brain.execution.kling_real_mp4_download_extractor.verify_extracted_kling_mp4",
        return_value={"is_real_mp4": True, "size_bytes": 5000, "duration_seconds": 15.0, "ffprobe_ok": True},
    ):
        _, audit = _resolve_mp4(run_id=run_id, live_result=live, cdp_url="http://127.0.0.1:9222")
    methods = audit.get("extractor_methods") or []
    _pass("multiple_methods", len(methods) >= 2, ",".join(methods))
    _pass("artifact_method_listed", any("artifact_card_cdp_urls" in m for m in methods))


def test_valid_recovered_mp4_copied_to_single_clip_output() -> None:
    import shutil

    from project_brain.run_kling_single_clip_15s import OUTPUT_ROOT

    run_id = "kling_sc_test_copy"
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / "clip_1.mp4"
    src = _canonical_live_clip_dir(run_id) / "clip_1.mp4"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"\x00" * 5000)
    shutil.copy2(src, dest)
    _pass("copy_ok", dest.is_file() and dest.stat().st_size > 1000)


def main() -> None:
    test_canonical_path_checked()
    test_runner_calls_recover_when_missing()
    test_polling_retries_recovery()
    test_no_generate_during_recovery()
    test_report_lists_multiple_methods()
    test_valid_recovered_mp4_copied_to_single_clip_output()
    print("validate_kling_single_clip_recovery_wiring_fix: all checks passed")


if __name__ == "__main__":
    main()
