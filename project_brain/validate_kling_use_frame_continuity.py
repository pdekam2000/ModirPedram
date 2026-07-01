"""Validate Kling Use Frame continuity integration."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_models import (  # noqa: E402
    KLING_FRAME_TO_VIDEO_MODE,
    normalize_kling_frame_story_duration,
)
from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content  # noqa: E402
from content_brain.execution.kling_product_run import _uses_frame_to_video  # noqa: E402
from content_brain.execution.kling_use_frame_runtime import (  # noqa: E402
    CONTINUITY_METHOD_USE_FRAME,
    RUNTIME_VERSION,
    USE_FRAME_CHAIN_FILENAME,
    UseFrameChainState,
    activate_use_frame,
    apply_continuity_for_next_clip,
    detect_use_frame_button,
    load_use_frame_chain,
    story_chapter_for_clip,
    use_frame_chain_path,
    validate_use_frame_availability,
    verify_reference_transferred,
    write_use_frame_chain,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_use_frame_detected() -> None:
    page = MagicMock()
    with patch(
        "content_brain.execution.kling_use_frame_runtime.try_locate_frame_control",
        return_value=MagicMock(strategy="text_use_frame", locator=page.locator.return_value),
    ):
        result = detect_use_frame_button(page, map_path=DEFAULT_MAP_PATH)
    _pass("use_frame_detected", result.get("detected") is True, str(result.get("strategy")))


def test_use_frame_activated() -> None:
    page = MagicMock()
    locator = MagicMock()
    with patch(
        "content_brain.execution.kling_use_frame_runtime.detect_use_frame_button",
        return_value={"detected": True, "locator": locator, "strategy": "text_use_frame"},
    ):
        result = activate_use_frame(page, from_clip_index=1, map_path=DEFAULT_MAP_PATH)
    _pass("use_frame_activated", result.get("activated") is True)
    locator.click.assert_called_once()


def test_continuity_metadata_written() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        state = UseFrameChainState(run_id="kling_ft_test", clip_count=2)
        state.clips.append({"clip": 1, "used_for_next_clip": True, "continuity_method": CONTINUITY_METHOD_USE_FRAME})
        payload = write_use_frame_chain(run_dir, state)
        path = use_frame_chain_path(run_dir)
        _pass("metadata_written", path.is_file(), str(path))
        loaded = load_use_frame_chain(run_dir)
        _pass("metadata_loads", loaded.get("run_id") == "kling_ft_test")
        _pass("chain_filename", USE_FRAME_CHAIN_FILENAME == "use_frame_chain.json")
        _pass("runtime_version", payload.get("version") == RUNTIME_VERSION)


def test_clip2_receives_clip1_continuity() -> None:
    page = MagicMock()
    with patch(
        "content_brain.execution.kling_use_frame_runtime.validate_use_frame_availability",
        return_value={"ok": True, "available": True},
    ), patch(
        "content_brain.execution.kling_use_frame_runtime.activate_use_frame",
        return_value={"ok": True, "activated": True, "from_clip_index": 1},
    ), patch(
        "content_brain.execution.kling_use_frame_runtime.verify_reference_transferred",
        return_value={"ok": True, "reference_transferred": True},
    ):
        handoff = apply_continuity_for_next_clip(
            page,
            run_dir=Path(tempfile.gettempdir()),
            from_clip_index=1,
            to_clip_index=2,
            video_path=Path(tempfile.gettempdir()) / "fake.mp4",
        )
    _pass("clip2_use_frame", handoff.get("continuity_method") == CONTINUITY_METHOD_USE_FRAME)
    _pass("clip2_used_for_next", handoff.get("used_for_next_clip") is True)


def test_fallback_when_use_frame_unavailable() -> None:
    page = MagicMock()
    with patch(
        "content_brain.execution.kling_use_frame_runtime.validate_use_frame_availability",
        return_value={"ok": False, "available": False},
    ), patch(
        "content_brain.execution.kling_use_frame_runtime._fallback_extract_and_upload",
        return_value={
            "ok": True,
            "uploaded": True,
            "continuity_method": "extract_last_frame_upload",
            "used_for_next_clip": True,
            "fallback_used": True,
        },
    ):
        handoff = apply_continuity_for_next_clip(
            page,
            run_dir=Path(tempfile.gettempdir()),
            from_clip_index=1,
            to_clip_index=2,
            video_path=Path(tempfile.gettempdir()) / "fake.mp4",
        )
    _pass("fallback_extract_upload", handoff.get("continuity_method") == "extract_last_frame_upload")
    _pass("fallback_flag", handoff.get("fallback_used") is True)


def test_story_progression_advances() -> None:
    plan30 = plan_kling_frame_to_video_content(topic="robot dog neon city", planned_duration_seconds=30)
    plan45 = plan_kling_frame_to_video_content(topic="robot dog neon city", planned_duration_seconds=45)
    plan60 = plan_kling_frame_to_video_content(topic="robot dog neon city", planned_duration_seconds=60)
    _pass("30s_two_clips", plan30.clip_count == 2, str(plan30.clip_count))
    _pass("45s_three_clips", plan45.clip_count == 3, str(plan45.clip_count))
    _pass("clip1_hook", plan30.clips[0].chapter_progression.get("chapter_label") == "Hook")
    _pass("clip2_payoff_30s", story_chapter_for_clip(2, clip_count=2) == "Payoff")
    _pass("clip3_conflict_60s", plan60.clips[2].chapter_progression.get("chapter_role") == "conflict")
    prompts_differ = plan45.clips[0].prompt != plan45.clips[1].prompt
    _pass("story_progression_prompts_differ", prompts_differ)
    _pass("planner_has_story_progression", bool(plan60.story_progression.get("chapters")))
    _pass("prompt_includes_chapter_role", bool(plan60.clips[0].chapter_progression.get("chapter_role")))


def test_frame_upload_path_unchanged() -> None:
    src = (ROOT / "content_brain" / "execution" / "kling_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("upload_frame_for_next_clip", "def upload_frame_for_next_clip" in src)
    _pass("first_frame_upload_control", 'try_locate_control(page, "first_frame_upload"' in src)


def test_multishot_path_unchanged() -> None:
    src = (ROOT / "content_brain" / "execution" / "kling_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("multishot_chain", "run_kling_multishot_live" in src)
    product = (ROOT / "content_brain" / "execution" / "kling_product_run.py").read_text(encoding="utf-8")
    _pass("multishot_route_preserved", "run_kling_continuity_chain" in product)


def test_download_recovery_unchanged() -> None:
    frame_engine = (ROOT / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    _pass("frame_recover_fn", "def recover_kling_frame_output" in frame_engine)
    _pass("frame_download_output", "_download_output" in frame_engine)


def test_no_generate_without_approval() -> None:
    src = (ROOT / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    frame_chain = (ROOT / "content_brain/execution/kling_frame_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("approval_gate", "if not approve_generate:" in src)
    _pass("approved_by_required", "approve_generate requires --approved-by" in src)
    _pass("confirm_credit_required", "confirm_credit_spend" in src)
    _pass("chain_uses_approval_clips", "clip_is_approved" in frame_chain)


def test_duration_model() -> None:
    for seconds, clips in ((15, 1), (30, 2), (45, 3), (60, 4), (75, 5), (90, 6)):
        planned, count, _ = normalize_kling_frame_story_duration(seconds)
        _pass(f"duration_{seconds}s", count == clips, f"planned={planned} count={count}")


def test_frame_primary_preflight() -> None:
    preflight = {"kling_shot_mode": KLING_FRAME_TO_VIDEO_MODE, "kling_frame_to_video_plan": {"clip_count": 2}}
    _pass("frame_route_detected", _uses_frame_to_video(preflight) is True)


def main() -> int:
    print("validate_kling_use_frame_continuity")
    test_use_frame_detected()
    test_use_frame_activated()
    test_continuity_metadata_written()
    test_clip2_receives_clip1_continuity()
    test_fallback_when_use_frame_unavailable()
    test_story_progression_advances()
    test_frame_upload_path_unchanged()
    test_multishot_path_unchanged()
    test_download_recovery_unchanged()
    test_no_generate_without_approval()
    test_duration_model()
    test_frame_primary_preflight()
    print("All Kling Use Frame continuity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
