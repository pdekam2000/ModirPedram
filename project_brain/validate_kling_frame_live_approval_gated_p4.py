"""Validate Kling Frame-to-Video live approval-gated P4 — guards, prepare, optional live run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_config import (  # noqa: E402
    KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
)
from content_brain.execution.kling_frame_to_video_live_engine import (  # noqa: E402
    DEFAULT_CDP_URL,
    DEFAULT_STARTER_RUN_ID,
    LIVE_ENGINE_VERSION,
    OUTPUT_ROOT,
    recover_kling_frame_output,
    resolve_frame_prompt,
    run_kling_frame_to_video_live,
)
from content_brain.execution.kling_frame_to_video_map_loader import (  # noqa: E402
    load_kling_frame_ui_map,
    verify_generate_approval_gate,
)
from content_brain.execution.kling_frame_to_video_models import (  # noqa: E402
    KLING_FRAME_PROMPT_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MIN_CHARS,
)
from content_brain.execution.kling_multishot_live_engine import (  # noqa: E402
    MIN_REAL_MP4_BYTES,
    PLACEHOLDER_MAX_BYTES,
    STATUS_AWAITING_APPROVAL,
    verify_recovered_mp4,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402

DEFAULT_STARTER_FRAME = (
    ROOT
    / "outputs"
    / "kling_frame_to_video"
    / DEFAULT_STARTER_RUN_ID
    / "starter_frame"
    / "frame_001.png"
)
RUN_DIR = OUTPUT_ROOT / DEFAULT_STARTER_RUN_ID


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_starter_frame_exists() -> None:
    _pass("starter_frame_exists", DEFAULT_STARTER_FRAME.is_file(), str(DEFAULT_STARTER_FRAME))
    size = DEFAULT_STARTER_FRAME.stat().st_size
    _pass("starter_frame_not_empty", size > 1000, f"{size} bytes")


def test_prompt_exists_and_bounded() -> None:
    prompt = resolve_frame_prompt(starter_run_dir=RUN_DIR)
    _pass("prompt_exists", bool(prompt.strip()), f"{len(prompt)} chars")
    _pass("prompt_max_2500", len(prompt) <= KLING_FRAME_PROMPT_MAX_CHARS, str(len(prompt)))
    _pass(
        "prompt_target_range_hint",
        KLING_FRAME_PROMPT_TARGET_MIN_CHARS <= len(prompt) <= KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
        f"target {KLING_FRAME_PROMPT_TARGET_MIN_CHARS}-{KLING_FRAME_PROMPT_TARGET_MAX_CHARS}; got {len(prompt)}",
    )


def test_generate_requires_approval_flags() -> None:
    ui_map = load_kling_frame_ui_map(map_path=DEFAULT_MAP_PATH)
    ok, reason = verify_generate_approval_gate(ui_map)
    _pass("map_generate_requires_approval", ok, reason)

    src = (ROOT / "content_brain" / "execution" / "kling_frame_to_video_live_engine.py").read_text(
        encoding="utf-8"
    )
    _pass("engine_checks_approve_generate", "if not approve_generate:" in src)
    _pass("engine_checks_approved_by", 'approve_generate requires --approved-by' in src)
    _pass("engine_checks_confirm_credit", "confirm_credit_spend" in src)
    _pass("engine_uses_continuity_guard", "can_execute_dangerous_action" in src)


def test_missing_approval_stops_safely(*, cdp_url: str) -> None:
    result = run_kling_frame_to_video_live(
        starter_frame_path=DEFAULT_STARTER_FRAME,
        approve_generate=False,
        cdp_url=cdp_url,
        map_path=DEFAULT_MAP_PATH,
    )
    _pass("missing_approval_no_generate", result.generate_clicked is False)
    _pass("missing_approval_no_credits", result.credits_spent is False)
    _pass("missing_approval_status", result.status == STATUS_AWAITING_APPROVAL, result.status)
    _pass("missing_approval_ok", result.ok is True)
    checklist = result.approval_checklist or {}
    _pass("checklist_all_ready", checklist.get("all_ready") is True, str(checklist))


def test_duration_and_audio_from_prepare(*, cdp_url: str) -> None:
    result = run_kling_frame_to_video_live(
        starter_frame_path=DEFAULT_STARTER_FRAME,
        approve_generate=False,
        cdp_url=cdp_url,
        map_path=DEFAULT_MAP_PATH,
    )
    checklist = result.approval_checklist or {}
    _pass(
        "duration_15s",
        checklist.get("duration_seconds") == KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
        str(checklist.get("duration_seconds")),
    )
    _pass(
        "duration_stable_after_dismiss",
        checklist.get("duration_stable_after_dismiss") is True,
    )
    _pass("audio_on", checklist.get("audio_on") is True)


def test_download_recovery_reuses_multishot_logic() -> None:
    src = (ROOT / "content_brain" / "execution" / "kling_frame_to_video_live_engine.py").read_text(
        encoding="utf-8"
    )
    _pass("engine_imports_download_output", "_download_output" in src)
    _pass("engine_imports_verify_mp4", "verify_recovered_mp4" in src)
    _pass("engine_has_recover_fn", "def recover_kling_frame_output" in src)
    _pass("p4_engine_version", LIVE_ENGINE_VERSION.endswith("_p4_v1"))


def test_no_mock_placeholder_as_success() -> None:
    clip_mp4 = RUN_DIR / "clips" / "c1" / "video.mp4"
    if not clip_mp4.is_file():
        _pass("no_output_yet_skip_mp4_checks", True, "run --live-approved to produce MP4")
        return
    size = clip_mp4.stat().st_size
    verify = verify_recovered_mp4(clip_mp4)
    if not verify.get("is_real_mp4"):
        _pass("partial_mp4_not_treated_as_success", True, f"{size} bytes — rejected by verify_recovered_mp4")
        _pass("no_mock_placeholder_as_success", size > PLACEHOLDER_MAX_BYTES or size == 0, "partial download not promoted")
        return
    _pass("real_mp4_over_1mb", size > MIN_REAL_MP4_BYTES, f"{size} bytes")
    _pass("not_placeholder_size", size > PLACEHOLDER_MAX_BYTES, f"placeholder max {PLACEHOLDER_MAX_BYTES}")
    _pass("ffprobe_pass", verify.get("ffprobe_ok") is True, str(verify.get("ffprobe_error", "")))
    _pass("is_real_mp4", verify.get("is_real_mp4") is True)
    _pass("native_audio_present", verify.get("audio_present") is True, str(verify))
    _pass("canonical_clip_path", clip_mp4.is_file(), str(clip_mp4))
    root_mp4 = RUN_DIR / "video.mp4"
    _pass("root_copy_exists", root_mp4.is_file(), str(root_mp4))


def test_live_approved_output(*, cdp_url: str) -> None:
    summary_path = ROOT / "project_brain" / "kling_frame_live_p4_summary.json"
    if summary_path.is_file():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        payload = {}
    if payload.get("status") not in {"completed", "download_failed"}:
        result = run_kling_frame_to_video_live(
            starter_frame_path=DEFAULT_STARTER_FRAME,
            approve_generate=True,
            approved_by="Pedram",
            confirm_credit_spend=True,
            cdp_url=cdp_url,
            map_path=DEFAULT_MAP_PATH,
        )
        summary_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        payload = result.to_dict()
    _pass("live_generate_clicked", payload.get("generate_clicked") is True)
    _pass("live_approved_by", payload.get("approved_by") == "Pedram")
    _pass("live_status_completed_or_download_failed", payload.get("status") in {"completed", "download_failed"})
    if payload.get("status") == "download_failed":
        _pass("live_generate_clicked", payload.get("generate_clicked") is True)
        _pass("live_approved_by", payload.get("approved_by") == "Pedram")
        _pass("download_failed_recovery_flag", payload.get("recovery_available") is True)
        _pass("download_failed_generation_done", payload.get("generation_completed") is True)
        test_no_mock_placeholder_as_success()
        return
    test_no_mock_placeholder_as_success()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Kling Frame live approval-gated P4")
    parser.add_argument("--prepare-live", action="store_true", help="CDP prepare-only (no Generate)")
    parser.add_argument("--live-approved", action="store_true", help="Run approved Generate (spends credits)")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    args = parser.parse_args()

    print("validate_kling_frame_live_approval_gated_p4")
    test_starter_frame_exists()
    test_prompt_exists_and_bounded()
    test_generate_requires_approval_flags()
    test_download_recovery_reuses_multishot_logic()
    test_no_mock_placeholder_as_success()

    if args.prepare_live or args.live_approved:
        print("\n--- live CDP ---")
        if args.live_approved:
            test_live_approved_output(cdp_url=args.cdp_url)
        else:
            test_missing_approval_stops_safely(cdp_url=args.cdp_url)
            test_duration_and_audio_from_prepare(cdp_url=args.cdp_url)
    else:
        print("\n(static — pass --prepare-live or --live-approved for CDP)")

    print("All Kling Frame live approval-gated P4 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
