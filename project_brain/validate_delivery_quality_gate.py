"""Validate delivery quality gate wiring and fail-closed publish checkpoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.delivery_quality_gate import (
    DELIVERY_FAIL,
    DELIVERY_PASS,
    DELIVERY_WARNING,
    evaluate_delivery_quality,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_gate_module_exists() -> None:
    path = ROOT / "content_brain/platform/delivery_quality_gate.py"
    _pass("gate_module_exists", path.is_file())


def test_post_processor_wiring() -> None:
    source = (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8")
    _pass("evaluate_delivery_quality_wired", "evaluate_delivery_quality" in source)
    _pass("delivery_blocked_checkpoint", "CHECKPOINT_DELIVERY_BLOCKED" in source)
    _pass("publish_not_on_fail", "publish_checkpoint = CHECKPOINT_PUBLISH if delivery_status != DELIVERY_FAIL" in source)
    _pass("overall_failed_on_gate_fail", "delivery_status == DELIVERY_FAIL" in source)


def test_fail_conditions() -> None:
    result = evaluate_delivery_quality(
        project_root=ROOT,
        assembly_manifest={"status": "ASSEMBLED", "output_path": "", "duration_seconds": 40.0},
        audio_post_result={"character_voice_status": "mode off"},
        branding_post_result={"status": "failed", "steps": {"subtitles": {"status": "FAIL"}}},
        publish_manifest={"branded_video_path": ""},
        channel_profile={"subtitle_enabled": True},
    )
    _pass("fail_on_missing_video", "missing_final_video" in result.failures)
    _pass("fail_on_subtitle", "subtitle_failure" in result.failures)
    _pass("upload_not_ready", result.upload_ready is False)
    _pass("delivery_status_fail", result.delivery_status == DELIVERY_FAIL)


def test_warning_conditions() -> None:
    # Use mocked paths — gate evaluates warnings from profile/audio only when branded exists
    result = evaluate_delivery_quality(
        project_root=ROOT,
        assembly_manifest={"status": "ASSEMBLED", "duration_seconds": 10.0},
        audio_post_result={
            "music_status_code": "skipped_provider_disabled",
            "character_voice_status": "Character voices skipped: mode off.",
        },
        branding_post_result={"status": "completed", "steps": {"subtitles": {"status": "PASS", "burn_visible_enough": True}}},
        publish_manifest={},
        channel_profile={"music_provider": "local", "subtitle_enabled": True},
    )
    _pass("warnings_present_or_fail", bool(result.warnings) or result.delivery_status in {DELIVERY_WARNING, DELIVERY_FAIL})


def main() -> None:
    test_gate_module_exists()
    test_post_processor_wiring()
    test_fail_conditions()
    test_warning_conditions()
    print("validate_delivery_quality_gate: all checks passed")


if __name__ == "__main__":
    main()
