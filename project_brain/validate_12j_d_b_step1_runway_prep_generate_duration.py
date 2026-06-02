"""
Phase 12J-D-B Step 1 — Runway prep, Generate locator, UAT provider-aware duration defaults.
"""

from __future__ import annotations

import ast
import inspect
import re
import subprocess
import sys
from pathlib import Path

from content_brain.execution.uat_runtime_profile import (
    UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER,
    UAT_MAX_DURATION_SECONDS,
    UAT_SINGLE_SEGMENT_SAFE_DURATION_BY_VIDEO_PROVIDER,
    uat_default_duration_seconds,
)
from content_brain.execution.runway_browser_observability import RUNWAY_BROWSER_STEPS
from providers.runway_browser_provider import RunwayBrowserProvider
from providers.runway_browser_support import RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS
from ui.api.schemas.uat_runtime import UatRunRequest


PROVIDER_PATH = Path("providers/runway_browser_provider.py")
OBS_PATH = Path("content_brain/execution/runway_browser_observability.py")
UAT_PAGE_PATH = Path("ui/web/src/pages/UatRuntimePage.tsx")
UAT_ELIGIBILITY_PATH = Path("ui/web/src/utils/uatRuntimeEligibility.ts")
SCHEMA_PATH = Path("ui/api/schemas/uat_runtime.py")


def _pass(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    if not ok:
        raise SystemExit(1)


def main() -> int:
    _pass("runway_browser_default_clip_duration_10", RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS == 10)

    _pass(
        "uat_runway_default_duration_10",
        uat_default_duration_seconds("runway_browser") == 10,
        str(UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER["runway_browser"]),
    )
    _pass(
        "uat_hailuo_default_duration_8",
        uat_default_duration_seconds("hailuo_browser") == 8,
        str(UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER["hailuo_browser"]),
    )
    _pass(
        "hailuo_smoke_safe_duration_unchanged",
        UAT_SINGLE_SEGMENT_SAFE_DURATION_BY_VIDEO_PROVIDER["hailuo_browser"] == 6,
    )
    _pass("uat_max_duration_90", UAT_MAX_DURATION_SECONDS == 90)

    schema_runway = UatRunRequest(topic="dog", video_provider="runway_browser")
    _pass(
        "schema_runway_default_10",
        schema_runway.duration_seconds == 10,
        str(schema_runway.duration_seconds),
    )
    schema_hailuo = UatRunRequest(topic="dog", video_provider="hailuo_browser")
    _pass(
        "schema_hailuo_default_8",
        schema_hailuo.duration_seconds == 8,
        str(schema_hailuo.duration_seconds),
    )
    schema_10 = UatRunRequest(topic="dog", video_provider="runway_browser", duration_seconds=10)
    _pass("schema_runway_10_allowed", schema_10.duration_seconds == 10)
    schema_8 = UatRunRequest(topic="dog", video_provider="hailuo_browser", duration_seconds=8)
    _pass("schema_hailuo_8_allowed", schema_8.duration_seconds == 8)

    page_src = UAT_PAGE_PATH.read_text(encoding="utf-8")
    _pass("uat_page_default_10", "durationSeconds: 10" in page_src)
    _pass(
        "uat_page_provider_switch_sets_default",
        "uatDefaultDurationSeconds(opt.id)" in page_src,
    )

    eligibility_src = UAT_ELIGIBILITY_PATH.read_text(encoding="utf-8")
    _pass("eligibility_hailuo_default_8", 'return 8' in eligibility_src or "return 8;" in eligibility_src)
    _pass("eligibility_runway_default_10", "uatDefaultDurationSeconds" in eligibility_src)

    for step in (
        "selecting_video_mode",
        "selecting_gen45_model",
        "clicking_try_it_now",
        "try_it_now_clicked",
        "waiting_for_generate_editor",
        "generate_editor_ready",
        "setting_duration_10s",
        "prompt_box_ready",
        "ready_for_generate",
    ):
        _pass(f"obs_step_{step}", step in RUNWAY_BROWSER_STEPS)

    provider_src = PROVIDER_PATH.read_text(encoding="utf-8")
    _pass("prep_calls_select_video_mode", "def select_video_mode" in provider_src)
    _pass("prep_obs_selecting_video_mode", '"selecting_video_mode"' in provider_src)
    _pass("prep_obs_selecting_gen45", '"selecting_gen45_model"' in provider_src)
    _pass("prep_obs_setting_duration", '"setting_duration_10s"' in provider_src)
    _pass("prep_obs_prompt_box_ready", '"prompt_box_ready"' in provider_src)
    _pass("prep_obs_ready_for_generate", '"ready_for_generate"' in provider_src)

    _pass(
        "generate_not_only_exact_generate_video",
        'get_by_text("Generate Video", exact=True)' not in provider_src
        or "exact=False" in provider_src,
    )
    _pass(
        "generate_role_button_regex",
        'get_by_role("button", name=re.compile(r"Generate"' in provider_src,
    )
    _pass("generate_supports_text_generate", 'get_by_text("Generate"' in provider_src)
    _pass("generate_clicked_log", "[RUNWAY_GENERATE_CLICKED]" in provider_src)

    _pass(
        "generate_requires_prompt_text",
        "_prompt_has_text" in provider_src and "Refusing to click Generate" in provider_src,
    )
    _pass(
        "generate_explicit_not_found_message",
        "Generate button not found" in provider_src,
    )

    _pass("try_it_now_click_method", "def click_try_it_now" in provider_src)
    _pass("try_it_now_visible_detect", "def is_try_it_now_visible" in provider_src)
    _pass("generate_editor_wait", "def wait_for_generate_editor" in provider_src)
    _pass("try_it_now_obs_steps", '"clicking_try_it_now"' in provider_src and '"generate_editor_ready"' in provider_src)

    prep_src = inspect.getsource(RunwayBrowserProvider.prepare_gen45_page)
    clip_src = inspect.getsource(RunwayBrowserProvider.prepare_clip_for_generate)
    _pass("prep_no_duration_on_page_prep", "set_duration_10s" not in prep_src)
    _pass(
        "clip_prompt_before_duration",
        clip_src.index("set_prompt_verified") < clip_src.index("set_duration_10s"),
    )
    _pass("clip_strict_duration", "set_duration_10s(strict=True)" in clip_src)
    _pass(
        "try_it_now_selector_priority",
        provider_src.index("Try it now") < provider_src.index('name="Try it"') if 'name="Try it"' in provider_src else True,
    )

    orch_src = Path("orchestrators/runway_browser_orchestrator.py").read_text(encoding="utf-8")
    _pass(
        "orchestrator_settings_in_prep_not_after_fill",
        "apply_default_settings" not in orch_src,
    )

    _pass(
        "provider_delegates_launch_to_browser_manager",
        "self.browser.launch()" in provider_src,
    )

    result = subprocess.run(
        [sys.executable, "project_brain/validate_12j_c2a_runway_browser_observability.py"],
        cwd=str(Path(".").resolve()),
        capture_output=True,
        text=True,
    )
    _pass(
        "c2a_observability_regression",
        result.returncode == 0,
        (result.stdout or result.stderr)[-400:],
    )

    print("\nAll Step 1 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
