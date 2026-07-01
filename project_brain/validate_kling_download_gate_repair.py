"""Validate KLING-DOWNLOAD-GATE-REPAIR — generation vs download gate separation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_continuity_runtime import (  # noqa: E402
    RUNTIME_VERSION,
    _clip_download_success,
    _clip_generation_success,
    _quarantine_invalid_mp4,
    evaluate_clip_download_gate,
    run_kling_frame_continuity_chain,
)
from content_brain.execution.kling_frame_to_video_models import (  # noqa: E402
    KLING_FRAME_TO_VIDEO_MODE,
)
from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content  # noqa: E402
from content_brain.execution.kling_multishot_live_engine import verify_recovered_mp4  # noqa: E402
from content_brain.execution.kling_use_frame_runtime import CONTINUITY_METHOD_USE_FRAME  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_generation_success_separate_from_download_fail() -> None:
    live_payload = {
        "generation_completed": True,
        "download_status": "failed",
        "download_verify_error": "Recovered file is not a real MP4",
        "steps": [{"label": "generation_wait", "status": "passed"}],
    }
    gate = evaluate_clip_download_gate(
        live_payload,
        "",
        cdp_url="http://127.0.0.1:9222",
        browser_output_ready=True,
        browser_output_detail="download_button_visible",
    )
    _pass("generation_success", gate["generation_success"] is True)
    _pass("download_failed", gate["download_success"] is False)
    _pass("clip_generation_completed", gate["clip_generation_status"] == "completed")
    _pass("download_status_failed", gate["download_status"] == "failed")
    _pass("recovery_needed", gate["recovery_needed"] is True)
    _pass("chain_may_continue", gate["continuity_source_available"] is True)


def test_fake_mp4_not_accepted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        clip_dir = Path(tmp) / "clips" / "c1"
        clip_dir.mkdir(parents=True)
        fake = clip_dir / "video.mp4"
        fake.write_bytes(b"not-an-mp4")
        verify = verify_recovered_mp4(fake)
        _pass("fake_not_real_mp4", verify.get("is_real_mp4") is False)
        _pass("download_success_rejects_fake", _clip_download_success(str(fake), {"download_status": "passed"}) is False)
        quarantined = _quarantine_invalid_mp4(fake, clip_dir)
        _pass("fake_quarantined", bool(quarantined), quarantined)
        _pass("fake_removed_from_clip_dir", not (clip_dir / "video.mp4").is_file())


def test_clip2_blocked_without_continuity_source() -> None:
    live_payload = {
        "generation_completed": True,
        "download_status": "failed",
        "steps": [{"label": "generation_wait", "status": "passed"}],
    }
    gate = evaluate_clip_download_gate(
        live_payload,
        "",
        cdp_url="http://127.0.0.1:9222",
        browser_output_ready=False,
        browser_output_detail="no_output",
    )
    _pass("generation_ok_no_browser", gate["generation_success"] is True)
    _pass("continuity_blocked", gate["continuity_source_available"] is False)


def test_download_failure_not_generation_failure() -> None:
    live_payload = {"download_status": "failed", "status": "download_failed"}
    _pass("generation_not_success_without_wait", _clip_generation_success(live_payload) is False)
    live_payload["steps"] = [{"label": "generation_wait", "status": "passed"}]
    _pass("generation_success_from_wait", _clip_generation_success(live_payload) is True)


def test_no_automatic_retry_generate() -> None:
    source = (ROOT / "content_brain/execution/kling_frame_continuity_runtime.py").read_text(encoding="utf-8")
    ensure_block = source.split("def _ensure_frame_mp4", 1)[1].split("def run_kling_frame_continuity_chain", 1)[0]
    chain_block = source.split("def run_kling_frame_continuity_chain", 1)[1]
    _pass("ensure_no_generate_click", "generate.locator.click" not in ensure_block)
    _pass("chain_single_live_call_per_clip", chain_block.count("run_kling_frame_to_video_live(") == 1)
    _pass("recover_not_regenerate", "recover_kling_frame_output" in ensure_block)


def test_no_credit_spending_in_gate_helpers() -> None:
    source = (ROOT / "content_brain/execution/kling_frame_continuity_runtime.py").read_text(encoding="utf-8")
    gate_block = source.split("def evaluate_clip_download_gate", 1)[1].split("\ndef ", 1)[0]
    quarantine_block = source.split("def _quarantine_invalid_mp4", 1)[1].split("\ndef ", 1)[0]
    browser_block = source.split("def _browser_output_ready", 1)[1].split("\ndef ", 1)[0]
    combined = gate_block + quarantine_block + browser_block
    _pass("gate_helpers_no_generate_click", "generate.locator.click" not in combined)
    _pass("gate_helpers_no_approval_gate", "grant_continuity_approval" not in combined)
    _pass("gate_helpers_no_credit_spend", "credits_spent" not in combined)
    verify_source = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    verify_block = verify_source.split("def verify_recovered_mp4", 1)[1].split("\ndef ", 1)[0]
    _pass("verify_mp4_no_credit_spend", "credits_spent" not in verify_block)


def test_chain_continues_after_download_fail_with_use_frame() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "kling_ft_gate_test"
        run_dir.mkdir(parents=True)
        plan = plan_kling_frame_to_video_content(
            topic="gate repair test",
            planned_duration_seconds=30,
            clip_count=2,
        )
        live_calls: list[dict[str, object]] = []

        def _fake_live(**kwargs: object):
            live_calls.append(dict(kwargs))
            clip_index = int(kwargs.get("clip_index") or 1)
            from content_brain.execution.kling_frame_to_video_live_engine import (
                KlingFrameLiveResult,
                STATUS_COMPLETED,
            )
            from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_TO_VIDEO_MODE

            return KlingFrameLiveResult(
                ok=True,
                status=STATUS_COMPLETED,
                run_id="kling_ft_gate_test",
                provider_mode=KLING_FRAME_TO_VIDEO_MODE,
                dry_run_prepare=False,
                generate_clicked=True,
                credits_spent=True,
                approved_by="validator",
                approved_at="2026-06-03T00:00:00+00:00",
                generation_completed=True,
            )

        def _fake_ensure(**kwargs: object):
            payload = dict(kwargs.get("live_payload") or {})
            payload["generation_completed"] = True
            payload["download_status"] = "failed"
            payload["download_verify_error"] = "Recovered file is not a real MP4"
            payload["recovery_available"] = True
            payload["steps"] = [{"label": "generation_wait", "status": "passed"}]
            return "", payload

        handoff_calls = 0

        def _fake_handoff(*args: object, **kwargs: object):
            nonlocal handoff_calls
            handoff_calls += 1
            return {
                "ok": True,
                "used_for_next_clip": True,
                "continuity_method": CONTINUITY_METHOD_USE_FRAME,
                "to_clip_index": 2,
            }

        with patch(
            "content_brain.execution.kling_frame_continuity_runtime.run_kling_frame_to_video_live",
            side_effect=_fake_live,
        ), patch(
            "content_brain.execution.kling_frame_continuity_runtime._ensure_frame_mp4",
            side_effect=_fake_ensure,
        ), patch(
            "content_brain.execution.kling_frame_continuity_runtime._browser_output_ready",
            return_value=(True, "download_button_visible"),
        ), patch(
            "playwright.sync_api.sync_playwright",
        ) as mock_pw:
            browser = MagicMock()
            page = MagicMock()
            browser.contexts = [MagicMock(pages=[page])]
            mock_pw.return_value.start.return_value.chromium.connect_over_cdp.return_value = browser
            with patch(
                "content_brain.execution.kling_frame_continuity_runtime.apply_continuity_for_next_clip",
                side_effect=_fake_handoff,
            ):
                clip_results, generation_report, download_report, final_video, _, continuity_chain = (
                    run_kling_frame_continuity_chain(
                        project_root=tmp,
                        run_id="kling_ft_gate_test",
                        run_dir=run_dir,
                        plan=plan,
                        approved_by="validator",
                        confirm_credit_spend=True,
                        starter_frame_path=None,
                        cdp_url="http://127.0.0.1:9222",
                        payload={"approve_all_clips": True},
                    )
                )

        _pass("two_clips_attempted", len(live_calls) == 2, f"calls={len(live_calls)}")
        _pass("clip2_continuity_frame_in_ui", live_calls[1].get("continuity_frame_in_ui") is True)
        _pass("clip2_no_local_mp4_required", live_calls[1].get("starter_frame_path") is None)
        _pass("use_frame_handoff_once", handoff_calls == 1)
        _pass("clip1_download_failed_reported", clip_results[0].get("download_status") == "failed")
        _pass("clip1_generation_completed", clip_results[0].get("clip_generation_status") == "completed")
        _pass("no_final_mp4", final_video == "")
        _pass("download_report_failed", download_report.get("status") == "failed")
        _pass("runtime_version", generation_report.get("version") == RUNTIME_VERSION)
        _pass("generation_mode", generation_report.get("generation_mode") == KLING_FRAME_TO_VIDEO_MODE)
        c1_live = run_dir / "clips" / "c1" / "live_run_result.json"
        _pass("clip1_live_written", c1_live.is_file())
        if c1_live.is_file():
            payload = json.loads(c1_live.read_text(encoding="utf-8"))
            _pass("clip1_recovery_available", payload.get("recovery_available") is True)


def main() -> None:
    print("KLING download gate repair validation")
    print(f"runtime: {RUNTIME_VERSION}")
    test_generation_success_separate_from_download_fail()
    test_fake_mp4_not_accepted()
    test_clip2_blocked_without_continuity_source()
    test_download_failure_not_generation_failure()
    test_no_automatic_retry_generate()
    test_no_credit_spending_in_gate_helpers()
    test_chain_continues_after_download_fail_with_use_frame()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
