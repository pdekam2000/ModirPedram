"""Validate Kling Native Audio preflight API wiring P4."""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_config import (  # noqa: E402
    MULTISHOT_STRATEGY,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    KLING_AUDIO_STRATEGY,
    KLING_PROVIDER_ID,
    KLING_SHOT_PROMPT_MAX_CHARS,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

DRAGON_TOPIC = (
    "A young boy discovers an injured baby dragon under twisted forest roots in a fantasy cinematic story"
)

BROWSER_AUTOMATION_TOKENS = (
    "kling_multishot_live",
    "playwright",
    "cdp",
    "click_generate",
    "ProviderRuntimeEngine",
    "run_kling",
    "browser_automation",
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _kling_payload(**overrides: object) -> dict:
    payload = {
        "topic_mode": "custom",
        "custom_topic": DRAGON_TOPIC,
        "duration_seconds": 30,
        "provider": "auto",
        "audio_strategy": "auto",
    }
    payload.update(overrides)
    return payload


def _assert_kling_preflight(pre: dict, *, clip_count: int | None = None) -> None:
    _pass("has_audio_strategy_route", bool(pre.get("audio_strategy_route")))
    _pass("has_kling_duration_plan", bool(pre.get("kling_duration_plan")))
    _pass("has_kling_native_audio_plan", bool(pre.get("kling_native_audio_plan")))
    _pass("kling_provider", pre.get("provider") == KLING_PROVIDER_ID)
    _pass("kling_audio_strategy", pre.get("audio_strategy") == KLING_AUDIO_STRATEGY)
    _pass("kling_shot_mode", pre.get("kling_shot_mode") == MULTISHOT_STRATEGY == "two_shot_continuity")
    if clip_count is not None:
        _pass("kling_clip_count", pre.get("kling_clip_count") == clip_count)
    prompts = list(pre.get("kling_clip_prompts") or [])
    _pass("kling_clip_prompts_nonempty", bool(prompts))
    for item in prompts:
        _pass(
            f"clip_{item.get('clip_index')}_shot1_duration",
            item.get("shot_1_duration_seconds") == SHOT_1_DURATION_SECONDS,
        )
        _pass(
            f"clip_{item.get('clip_index')}_shot2_duration",
            item.get("shot_2_duration_seconds") == SHOT_2_DURATION_SECONDS,
        )
        _pass(f"clip_{item.get('clip_index')}_shot1_prompt", bool(item.get("shot_1_prompt")))
        _pass(f"clip_{item.get('clip_index')}_shot2_prompt", bool(item.get("shot_2_prompt")))
        _pass(
            f"clip_{item.get('clip_index')}_shot1_len",
            len(str(item.get("shot_1_prompt") or "")) <= KLING_SHOT_PROMPT_MAX_CHARS,
        )
        _pass(
            f"clip_{item.get('clip_index')}_shot2_len",
            len(str(item.get("shot_2_prompt") or "")) <= KLING_SHOT_PROMPT_MAX_CHARS,
        )
        if int(item.get("clip_index") or 0) < int(pre.get("kling_clip_count") or 0):
            _pass(
                f"clip_{item.get('clip_index')}_continuity_anchor",
                bool(item.get("continuity_anchor")),
            )
            _pass(
                f"clip_{item.get('clip_index')}_next_hint",
                bool(item.get("next_clip_reference_hint")),
            )


def test_auto_dragon_returns_kling_route() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    _assert_kling_preflight(pre, clip_count=2)


def test_explicit_kling_audio_strategy() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        _kling_payload(audio_strategy=KLING_AUDIO_STRATEGY, provider="runway")
    )
    _assert_kling_preflight(pre, clip_count=2)


def test_explicit_kling_provider() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        _kling_payload(provider=KLING_PROVIDER_ID, audio_strategy="auto", duration_seconds=15)
    )
    _assert_kling_preflight(pre, clip_count=1)


def test_30s_two_clips() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload(duration_seconds=30))
    _pass("30s_two_clips", pre.get("kling_clip_count") == 2)


def test_40s_rounds_to_45_three_clips() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload(duration_seconds=40))
    _pass("40s_planned_45", pre.get("duration_plan", {}).get("duration_seconds") == 45)
    _pass("40s_three_clips", pre.get("kling_clip_count") == 3)
    warnings = list(pre.get("warnings") or [])
    _pass("40s_round_warning", any("40" in w and "45" in w for w in warnings))


def test_flags_disabled_and_native_required() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    _pass("use_elevenlabs_false", pre.get("use_elevenlabs") is False)
    _pass("use_external_music_false", pre.get("use_external_music") is False)
    _pass("native_audio_required_true", pre.get("native_audio_required") is True)
    _pass("subtitle_required_true", pre.get("subtitle_required") is True)


def test_preflight_preview_only_no_browser_automation() -> None:
    service = ProductStudioService(ROOT)
    source = inspect.getsource(service.create_video_preflight).lower()
    for token in BROWSER_AUTOMATION_TOKENS:
        _pass(f"no_{token}_in_preflight", token.lower() not in source)
    pre = service.create_video_preflight(_kling_payload())
    _pass("preflight_mode_preview", pre.get("preflight_mode") == "preview_only")


def test_runway_narrator_preflight_unchanged() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "Educational documentary mystery about science facts and history",
            "audio_strategy": "narrator",
            "provider": "runway",
            "duration_seconds": 30,
        }
    )
    _pass("narrator_strategy", pre.get("audio_strategy") == "narrator")
    _pass("runway_provider", pre.get("provider") == "runway")
    _pass("no_kling_native_plan", not pre.get("kling_native_audio_plan"))


def test_music_only_preflight_unchanged() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "Luxury aesthetic travel reel fashion montage with no dialogue",
            "audio_strategy": "music_only",
            "provider": "runway",
            "duration_seconds": 30,
        }
    )
    _pass("music_only_strategy", pre.get("audio_strategy") == "music_only")
    _pass("no_kling_native_plan", not pre.get("kling_native_audio_plan"))


def test_regression_p0_through_p3() -> None:
    scripts = (
        "project_brain/validate_kling_native_audio_schema_p0.py",
        "project_brain/validate_kling_native_audio_duration_planner_p1.py",
        "project_brain/validate_kling_native_audio_router_p2.py",
        "project_brain/validate_kling_native_audio_content_planner_p3.py",
    )
    for script in scripts:
        result = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        _pass(
            f"regression_{Path(script).stem}",
            result.returncode == 0,
            result.stderr.strip() or result.stdout.strip()[-120:],
        )


def main() -> int:
    print("validate_kling_native_audio_preflight_api_p4")
    test_auto_dragon_returns_kling_route()
    test_explicit_kling_audio_strategy()
    test_explicit_kling_provider()
    test_30s_two_clips()
    test_40s_rounds_to_45_three_clips()
    test_flags_disabled_and_native_required()
    test_preflight_preview_only_no_browser_automation()
    test_runway_narrator_preflight_unchanged()
    test_music_only_preflight_unchanged()
    test_regression_p0_through_p3()
    print("All Kling Native Audio preflight API P4 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
