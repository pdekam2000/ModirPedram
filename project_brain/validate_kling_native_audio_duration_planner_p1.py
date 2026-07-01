"""Validate Kling Native Audio duration planner P1 — Kling + Runway/Hailuo compatibility."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    KLING_PROVIDER_ID,
    KLING_SHOT_PROMPT_MAX_CHARS,
)
from content_brain.scheduling.duration_planner import (  # noqa: E402
    calculate_clip_count,
    kling_duration_preflight_metadata,
    plan_duration,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_kling_15_one_clip() -> None:
    plan = plan_duration(duration_seconds=15, provider=KLING_PROVIDER_ID)
    _pass("kling_15_clip_count", plan.clip_count == 1)
    _pass("kling_15_planned", plan.duration_seconds == 15)


def test_kling_30_two_clips() -> None:
    plan = plan_duration(duration_seconds=30, provider="kling_3_pro_native")
    _pass("kling_30_clip_count", plan.clip_count == 2)


def test_kling_45_three_clips() -> None:
    plan = plan_duration(duration_seconds=45, audio_strategy="kling_native_audio", provider="runway")
    _pass("kling_45_via_audio_strategy", plan.clip_count == 3)
    _pass("kling_45_provider_resolved", plan.provider == KLING_PROVIDER_ID)


def test_kling_60_four_clips() -> None:
    plan = plan_duration(duration_seconds=60, provider=KLING_PROVIDER_ID)
    _pass("kling_60_clip_count", plan.clip_count == 4)


def test_kling_40_rounds_to_45() -> None:
    plan = plan_duration(duration_seconds=40, provider=KLING_PROVIDER_ID)
    _pass("kling_40_planned_45", plan.duration_seconds == 45)
    _pass("kling_40_clip_count_3", plan.clip_count == 3)
    _pass("kling_40_warning", any("40" in w and "45" in w for w in plan.warnings))


def test_kling_75_capped_at_60() -> None:
    plan = plan_duration(duration_seconds=75, provider=KLING_PROVIDER_ID)
    _pass("kling_75_planned_60", plan.duration_seconds == 60)
    _pass("kling_75_clip_count_4", plan.clip_count == 4)
    _pass("kling_75_cap_warning", any("60" in w for w in plan.warnings))


def test_runway_40_unchanged() -> None:
    plan = plan_duration(duration_seconds=40, provider="runway")
    _pass("runway_40_duration", plan.duration_seconds == 40)
    _pass("runway_40_clip_count", plan.clip_count == 4)
    _pass("runway_40_not_kling", plan.kling_native_audio is False)
    _pass("runway_40_calc_helper", calculate_clip_count(duration_seconds=40, provider="runway") == 4)


def test_hailuo_unchanged() -> None:
    plan = plan_duration(duration_seconds=40, provider="hailuo")
    _pass("hailuo_40_duration", plan.duration_seconds == 40)
    _pass("hailuo_40_clip_count", plan.clip_count == 5)
    _pass("hailuo_24_clip_count", calculate_clip_count(duration_seconds=24, provider="hailuo") == 3)
    _pass("hailuo_not_kling", plan.kling_native_audio is False)


def test_preflight_shot_mode() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "dragon story",
            "duration_seconds": 30,
            "provider": KLING_PROVIDER_ID,
            "audio_strategy": "kling_native_audio",
        }
    )
    kling = pre.get("kling_duration_plan") or {}
    _pass("preflight_kling_block", bool(kling))
    _pass("preflight_shot_mode", kling.get("shot_mode") == "two_shot_continuity")


def test_preflight_native_provider() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "dragon story",
            "duration_seconds": 15,
            "provider": KLING_PROVIDER_ID,
        }
    )
    kling = pre.get("kling_duration_plan") or {}
    _pass("preflight_provider", kling.get("provider") == KLING_PROVIDER_ID)
    _pass("preflight_top_provider", pre.get("provider") == KLING_PROVIDER_ID)


def test_kling_elevenlabs_disabled() -> None:
    plan = plan_duration(duration_seconds=30, provider=KLING_PROVIDER_ID)
    meta = kling_duration_preflight_metadata(plan)
    _pass("plan_use_elevenlabs_false", plan.use_elevenlabs is False)
    _pass("meta_use_elevenlabs_false", meta.get("use_elevenlabs") is False)


def test_kling_external_music_disabled() -> None:
    plan = plan_duration(duration_seconds=30, provider=KLING_PROVIDER_ID)
    meta = kling_duration_preflight_metadata(plan)
    _pass("plan_use_external_music_false", plan.use_external_music is False)
    _pass("meta_use_external_music_false", meta.get("use_external_music") is False)
    _pass("shot_prompt_max_chars_512", meta.get("shot_prompt_max_chars") == KLING_SHOT_PROMPT_MAX_CHARS == 512)


def main() -> int:
    print("validate_kling_native_audio_duration_planner_p1")
    test_kling_15_one_clip()
    test_kling_30_two_clips()
    test_kling_45_three_clips()
    test_kling_60_four_clips()
    test_kling_40_rounds_to_45()
    test_kling_75_capped_at_60()
    test_runway_40_unchanged()
    test_hailuo_unchanged()
    test_preflight_shot_mode()
    test_preflight_native_provider()
    test_kling_elevenlabs_disabled()
    test_kling_external_music_disabled()
    print("All Kling Native Audio duration planner P1 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
