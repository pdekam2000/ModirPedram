"""Validate Kling preflight schema mismatch fix — frame + multishot warning paths."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_models import (  # noqa: E402
    KLING_FRAME_PROMPT_MAX_CHARS,
    KLING_FRAME_TO_VIDEO_MODE,
)
from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content  # noqa: E402
from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    KLING_SHOT_PROMPT_MAX_CHARS,
    build_kling_native_audio_plan,
)
from content_brain.execution.kling_native_audio_planner import (  # noqa: E402
    collect_kling_preflight_warnings,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _kling_payload(**overrides: object) -> dict:
    base = {
        "topic_mode": "custom",
        "custom_topic": "young boy and baby dragon in neon ruins cinematic native audio",
        "duration_seconds": 30,
        "platform": "youtube",
        "provider": "kling",
        "audio_strategy": "kling_native_audio",
    }
    base.update(overrides)
    return base


def test_frame_preflight_returns_ok() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    _pass("frame_preflight_ok", pre.get("ok") is True)
    _pass("frame_shot_mode", pre.get("kling_shot_mode") == KLING_FRAME_TO_VIDEO_MODE)
    _pass("frame_plan_present", bool(pre.get("kling_frame_to_video_plan")))


def test_frame_warnings_no_attribute_error() -> None:
    plan = plan_kling_frame_to_video_content(
        topic="young boy and baby dragon neon city",
        planned_duration_seconds=30,
    )
    warnings = collect_kling_preflight_warnings(
        plan=plan,
        authoritative_topic="young boy and baby dragon neon city",
    )
    _pass("frame_warnings_list", isinstance(warnings, list))


def test_frame_prompt_length_warning() -> None:
    plan = plan_kling_frame_to_video_content(
        topic="young boy and baby dragon neon city",
        planned_duration_seconds=15,
    )
    long_prompt = "x" * (KLING_FRAME_PROMPT_MAX_CHARS + 50)
    plan.clips[0].prompt = long_prompt
    warnings = collect_kling_preflight_warnings(
        plan=plan,
        authoritative_topic="young boy and baby dragon",
    )
    _pass(
        "frame_prompt_too_long",
        any("prompt_too_long" in w and "_frame=" in w for w in warnings),
        str(warnings),
    )


def test_multishot_warnings_still_work() -> None:
    plan = build_kling_native_audio_plan(
        topic="robot dog neon city",
        requested_duration_seconds=30,
    )
    plan.clips[0].shot_1.prompt = "y" * (KLING_SHOT_PROMPT_MAX_CHARS + 10)
    warnings = collect_kling_preflight_warnings(
        plan=plan,
        authoritative_topic="robot dog neon city",
    )
    _pass(
        "multishot_shot1_warning",
        any("prompt_too_long" in w and "shot_1" in w for w in warnings),
        str(warnings),
    )


def test_runway_preflight_unchanged() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "Ancient Rome secrets underground vault",
            "duration_seconds": 30,
            "platform": "youtube",
            "provider": "runway",
            "audio_strategy": "narrator",
        }
    )
    _pass("runway_preflight_ok", pre.get("ok") is True)
    _pass("runway_provider", pre.get("provider") == "runway")


def test_hailuo_preflight_unchanged() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "Wild wolves crossing misty ridge at dawn",
            "duration_seconds": 40,
            "platform": "youtube",
            "provider": "hailuo",
            "audio_strategy": "auto",
        }
    )
    _pass("hailuo_preflight_ok", pre.get("ok") is True)
    _pass("hailuo_provider", str(pre.get("provider") or "").lower() == "hailuo")


def test_generate_preflight_stage_no_schema_error() -> None:
    service = ProductStudioService(ROOT)
    try:
        pre = service.create_video_preflight(_kling_payload())
    except AttributeError as exc:
        _pass("generate_preflight_no_attribute_error", False, str(exc))
        return
    _pass("generate_preflight_no_attribute_error", pre.get("ok") is True)
    _pass("generate_preflight_frame_mode", pre.get("kling_shot_mode") == KLING_FRAME_TO_VIDEO_MODE)
    _pass("generate_preflight_has_clips", bool(pre.get("kling_clip_count")))
    frame_plan = pre.get("kling_frame_to_video_plan") or {}
    clips = frame_plan.get("clips") or []
    _pass("generate_preflight_frame_clips", bool(clips))
    _pass(
        "generate_preflight_frame_clip_schema",
        all("prompt" in clip and "shot_1" not in clip for clip in clips),
    )


def test_no_shot1_access_for_frame_clips() -> None:
    source = inspect.getsource(collect_kling_preflight_warnings)
    helper = inspect.getsource(
        __import__(
            "content_brain.execution.kling_native_audio_planner",
            fromlist=["_clip_prompt_length_warnings"],
        )._clip_prompt_length_warnings
    )
    frame_clip = plan_kling_frame_to_video_content(topic="test", planned_duration_seconds=15).clips[0]
    _pass("frame_clip_has_prompt", hasattr(frame_clip, "prompt"))
    _pass("frame_clip_no_shot1", not hasattr(frame_clip, "shot_1"))
    warnings = collect_kling_preflight_warnings(plan=MagicMock(clips=[frame_clip], duration_warnings=()), authoritative_topic="test")
    _pass("frame_mock_warnings_ok", isinstance(warnings, list))
    _pass("collector_uses_helper", "_clip_prompt_length_warnings" in source)
    _pass("helper_branches_frame", "KLING_FRAME_PROMPT_MAX_CHARS" in helper)
    _pass("helper_branches_multishot", "shot_1" in helper)


def main() -> int:
    print("validate_kling_preflight_schema_mismatch_fix")
    test_frame_preflight_returns_ok()
    test_frame_warnings_no_attribute_error()
    test_frame_prompt_length_warning()
    test_multishot_warnings_still_work()
    test_runway_preflight_unchanged()
    test_hailuo_preflight_unchanged()
    test_generate_preflight_stage_no_schema_error()
    test_no_shot1_access_for_frame_clips()
    print("All Kling preflight schema mismatch fix checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
