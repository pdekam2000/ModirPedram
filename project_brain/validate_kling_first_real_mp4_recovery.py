"""Validate first real Kling MP4 recovery for run kling_ms_20260617T035534_f392af70."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_live_engine import (
    MIN_REAL_MP4_BYTES,
    MIN_REAL_MP4_SECONDS,
    PLACEHOLDER_MAX_BYTES,
    verify_recovered_mp4,
)
from content_brain.execution.kling_product_run import (
    kling_clip_dir,
    kling_run_dir,
    load_kling_product_run_results,
    recover_kling_product_run,
)

TARGET_RUN_ID = "kling_ms_20260617T035534_f392af70"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_mp4_exists() -> None:
    clip_video = kling_clip_dir(kling_run_dir(ROOT, TARGET_RUN_ID), 1) / "video.mp4"
    root_video = kling_run_dir(ROOT, TARGET_RUN_ID) / "video.mp4"
    _pass("clip_mp4_exists", clip_video.is_file(), str(clip_video))
    _pass("root_mp4_exists", root_video.is_file(), str(root_video))


def test_size_over_1mb() -> None:
    clip_video = kling_clip_dir(kling_run_dir(ROOT, TARGET_RUN_ID), 1) / "video.mp4"
    size = clip_video.stat().st_size
    _pass("size_over_1mb", size > MIN_REAL_MP4_BYTES, f"{size} bytes")


def test_duration_detected() -> None:
    clip_video = kling_clip_dir(kling_run_dir(ROOT, TARGET_RUN_ID), 1) / "video.mp4"
    verify = verify_recovered_mp4(clip_video)
    _pass("duration_detected", verify.get("duration_seconds") is not None, str(verify.get("duration_seconds")))
    _pass("duration_over_1s", float(verify.get("duration_seconds") or 0) >= MIN_REAL_MP4_SECONDS)


def test_ffprobe_passes() -> None:
    clip_video = kling_clip_dir(kling_run_dir(ROOT, TARGET_RUN_ID), 1) / "video.mp4"
    verify = verify_recovered_mp4(clip_video)
    _pass("ffprobe_ok", verify.get("ffprobe_ok") is True)


def test_not_placeholder() -> None:
    clip_video = kling_clip_dir(kling_run_dir(ROOT, TARGET_RUN_ID), 1) / "video.mp4"
    size = clip_video.stat().st_size
    _pass("not_placeholder", size > PLACEHOLDER_MAX_BYTES, f"{size} > {PLACEHOLDER_MAX_BYTES}")


def test_recovery_does_not_generate() -> None:
    source = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    recover_block = source.split("def recover_kling_multishot_output", 1)[1].split("def run_kling_multishot_live", 1)[0]
    _pass("recovery_no_generate_click", "generate.locator.click" not in recover_block)


def test_recovery_spends_no_credits() -> None:
    payload = _read_json(kling_clip_dir(kling_run_dir(ROOT, TARGET_RUN_ID), 1) / "live_run_result.json")
    _pass("recovery_generate_clicked_false", payload.get("generate_clicked") is False)
    _pass("recovery_credits_spent_false", payload.get("credits_spent") is False)
    _pass("recovery_mode_true", payload.get("recovery_mode") is True)


def test_recovery_updates_metadata() -> None:
    metadata = _read_json(kling_run_dir(ROOT, TARGET_RUN_ID) / "metadata.json")
    _pass("metadata_output_ready", metadata.get("output_ready") is True)
    _pass("metadata_native_completed", metadata.get("native_audio_status") == "completed")
    _pass("metadata_generation_completed", metadata.get("generation_status") == "completed")


def test_recovery_updates_download_report() -> None:
    report = _read_json(kling_run_dir(ROOT, TARGET_RUN_ID) / "download_report.json")
    _pass("download_report_completed", report.get("status") == "completed")
    downloads = list(report.get("downloads") or [])
    clip_one = next((item for item in downloads if int(item.get("clip_index") or 0) == 1), {})
    _pass("download_report_clip1_ok", clip_one.get("ok") is True)
    _pass("download_report_has_path", bool(clip_one.get("download_path")))


def test_results_loader_output_ready() -> None:
    payload = load_kling_product_run_results(ROOT, run_id=TARGET_RUN_ID)
    assert payload is not None
    _pass("results_output_ready", payload.get("output_ready") is True)
    _pass("results_recovery_available_false", payload.get("recovery_available") is False)


def test_runway_cdp_strategy_used() -> None:
    payload = _read_json(kling_clip_dir(kling_run_dir(ROOT, TARGET_RUN_ID), 1) / "live_run_result.json")
    strategies = list(payload.get("download_strategies") or [])
    _pass("runway_cdp_used", any("runway_cdp:cdp_fetch" in item for item in strategies), ",".join(strategies))


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    test_mp4_exists()
    test_size_over_1mb()
    test_duration_detected()
    test_ffprobe_passes()
    test_not_placeholder()
    test_recovery_does_not_generate()
    test_recovery_spends_no_credits()
    test_recovery_updates_metadata()
    test_recovery_updates_download_report()
    test_results_loader_output_ready()
    test_runway_cdp_strategy_used()
    print("validate_kling_first_real_mp4_recovery: all checks passed")


if __name__ == "__main__":
    main()
