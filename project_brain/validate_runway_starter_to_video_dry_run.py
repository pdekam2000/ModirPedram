"""
Phase RUNWAY-STARTER-TO-VIDEO-D — dry-run orchestrator validation.

No browser, no Generate, no Download, no provider execution.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_dry_run import (
    APPROVAL_GATED_CONTROLS,
    build_continuity_plan,
    build_dry_run_steps,
    run_dry_run,
)
from content_brain.execution.runway_continuity_models import (
    COMPLETION_RULE_EXPRESSION,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_IMAGE_COUNT,
    DEFAULT_IMAGE_QUALITY,
)
from content_brain.execution.runway_image_generation_config import (
    IMAGE_GENERATION_PROFILE_FAST_TEST,
    IMAGE_GENERATION_PROFILE_PREMIUM,
    IMAGE_GENERATION_PROFILE_STANDARD,
    image_count_control_key,
    image_quality_control_key,
    resolve_image_generation_profile,
)
from content_brain.execution.runway_ui_map_loader import (
    DEFAULT_MAP_PATH,
    STARTER_TO_VIDEO_CANONICAL_CONTROLS,
    resolve_runway_ui_controls,
)

MAP_PATH = DEFAULT_MAP_PATH


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _good_control(
    canonical: str,
    *,
    tag: str = "button",
    css: str | None = None,
    text: str = "",
) -> dict:
    selector = css or f"button[data-testid='{canonical}']"
    return {
        "label": canonical,
        "tag": tag,
        "text": text,
        "selector_candidates": {"css": selector},
        "metadata": {"tag": tag, "css_selector": selector, "text": text},
        "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=image",
    }


def _mock_ui_map() -> dict:
    labels = {}
    for key in STARTER_TO_VIDEO_CANONICAL_CONTROLS:
        labels[key] = _good_control(key)
    labels["use_frame_button"] = _good_control("use_frame_button", tag="span", css="span")
    labels["image_use_to_video_option"] = _good_control(
        "image_use_to_video_option",
        tag="span",
        css="span",
        text="Use in video",
    )
    return {"version": "test", "labels": labels}


def _static_checks() -> None:
    loader = (ROOT / "content_brain" / "execution" / "runway_ui_map_loader.py").read_text(encoding="utf-8")
    models = (ROOT / "content_brain" / "execution" / "runway_continuity_models.py").read_text(encoding="utf-8")
    dry_run = (ROOT / "content_brain" / "execution" / "runway_continuity_dry_run.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers" / "runway_browser_provider.py").read_text(encoding="utf-8")

    _pass("loader_exists", (ROOT / "content_brain" / "execution" / "runway_ui_map_loader.py").is_file())
    _pass("models_exists", (ROOT / "content_brain" / "execution" / "runway_continuity_models.py").is_file())
    _pass("dry_run_exists", (ROOT / "content_brain" / "execution" / "runway_continuity_dry_run.py").is_file())
    _pass("no_browser_provider_import", "from providers.runway_browser_provider" not in dry_run)
    _pass("no_generate_click", "click_generate" not in dry_run)
    _pass("no_download_click", ".click(" not in dry_run)
    _pass("provider_untouched_by_import", "runway_continuity" not in provider)
    _pass("image_use_to_video_in_loader", "image_use_to_video_option" in loader)
    _pass("remove_image_in_loader", "remove_image" in loader)
    _pass("image_count_controls_in_loader", "image_count_1" in loader and "image_count_4" in loader)
    _pass("image_quality_variants_in_loader", "image_quality_1k" in loader and "image_quality_4k" in loader)


def _unit_map_loader_body_fail() -> None:
    bad = _mock_ui_map()
    bad["labels"]["download_mp4_button"] = _good_control(
        "download_mp4_button", tag="body", css="body"
    )
    snap = resolve_runway_ui_controls(bad)
    _pass("body_selector_invalid", not snap.ok)
    _pass("body_in_invalid_list", any(i["control"] == "download_mp4_button" for i in snap.invalid))


def _unit_weak_selector_warn_only() -> None:
    ui = _mock_ui_map()
    ui["use_frame_button"] = _good_control("use_frame_button", tag="span", css="span")
    snap = resolve_runway_ui_controls(ui)
    _pass("weak_use_frame_ok", snap.ok)
    _pass("weak_use_frame_warn", any("use_frame_button" in w for w in snap.warnings))


def _unit_starter_workflow_steps() -> None:
    plan = build_continuity_plan(
        project_id="test",
        starter_image_prompt="Starter image prompt",
        clip_prompts=["clip one"],
    )
    steps = build_dry_run_steps(plan)
    step_ids = [s.step_id.split("_", 1)[1] if "_" in s.step_id else s.action for s in steps]
    actions = [s.action for s in steps]
    _pass("image_generation_open", any("image_generation_open" in s.step_id for s in steps))
    _pass("image_use_to_video", any(s.control_key == "image_use_to_video_option" for s in steps))
    _pass("starter_image_phase", any(s.phase == "starter_image" for s in steps))
    _pass("no_multishot_note", any("Multi-Shot" in (s.notes or "") for s in steps))


def _unit_completion_rule() -> None:
    plan = build_continuity_plan(
        project_id="test",
        starter_image_prompt="x",
        clip_prompts=["a"],
    )
    _pass("completion_rule", plan.completion_rule == COMPLETION_RULE_EXPRESSION)
    steps = build_dry_run_steps(plan)
    wait_steps = [s for s in steps if "wait_until_completion_signal" in s.step_id]
    _pass("wait_step_present", len(wait_steps) == 1)
    _pass("wait_mentions_download_or_frame", "download_mp4_button" in wait_steps[0].notes)


def _unit_defaults() -> None:
    plan = build_continuity_plan(
        project_id="test",
        starter_image_prompt="x",
        clip_prompts=["a"],
    )
    _pass("aspect_default_9_16", plan.aspect_ratio == DEFAULT_ASPECT_RATIO == "9:16")
    _pass("duration_default_10", plan.duration_seconds == DEFAULT_DURATION_SECONDS == 10)
    _pass("quality_default_2k", plan.image_quality == DEFAULT_IMAGE_QUALITY == "2K")
    _pass("count_default_1", plan.image_count == DEFAULT_IMAGE_COUNT == 1)


def _unit_image_generation_profiles() -> None:
    fast = resolve_image_generation_profile(IMAGE_GENERATION_PROFILE_FAST_TEST)
    standard = resolve_image_generation_profile(IMAGE_GENERATION_PROFILE_STANDARD)
    premium = resolve_image_generation_profile(IMAGE_GENERATION_PROFILE_PREMIUM)
    _pass("profile_fast_test_1k", fast.image_quality == "1K" and fast.image_count == 1)
    _pass("profile_standard_2k", standard.image_quality == "2K" and standard.image_count == 1)
    _pass("profile_premium_4k", premium.image_quality == "4K" and premium.image_count == 1)

    premium_plan = build_continuity_plan(
        project_id="premium",
        starter_image_prompt="x",
        clip_prompts=["a"],
        image_quality=premium.image_quality,
        image_count=premium.image_count,
    )
    steps = build_dry_run_steps(premium_plan)
    quality_steps = [s for s in steps if "select_image_quality" in s.step_id]
    count_steps = [s for s in steps if "select_image_count" in s.step_id]
    _pass(
        "premium_quality_control",
        quality_steps and quality_steps[0].control_key == image_quality_control_key("4K"),
    )
    _pass(
        "premium_count_control",
        count_steps and count_steps[0].control_key == image_count_control_key(1),
    )


def _unit_three_clip_step_count() -> None:
    plan = build_continuity_plan(
        project_id="three_clip",
        starter_image_prompt="starter",
        clip_prompts=["c1", "c2", "c3"],
    )
    result = run_dry_run(plan, ui_map=_mock_ui_map())
    _pass("three_clip_ok", result.ok is True, f"errors={result.errors}")
    _pass("three_clip_steps", len(result.steps) >= 20, f"count={len(result.steps)}")
    final_steps = [s for s in result.steps if s.control_key == "remove_image"]
    _pass("final_remove_image", len(final_steps) == 1)
    use_frame_steps = [s for s in result.steps if s.control_key == "use_frame_button"]
    _pass("use_frame_between_clips", len(use_frame_steps) == 2)


def _unit_missing_use_to_video_fails() -> None:
    ui = _mock_ui_map()
    del ui["labels"]["image_use_to_video_option"]
    plan = build_continuity_plan(
        project_id="fail",
        starter_image_prompt="x",
        clip_prompts=["a"],
    )
    result = run_dry_run(plan, ui_map=ui)
    _pass("missing_use_to_video_not_ok", result.ok is False)
    _pass("missing_use_to_video_error", any("image_use_to_video_option" in e for e in result.errors))


def _unit_missing_remove_image_fails() -> None:
    ui = _mock_ui_map()
    del ui["labels"]["remove_image"]
    plan = build_continuity_plan(
        project_id="fail",
        starter_image_prompt="x",
        clip_prompts=["a"],
    )
    result = run_dry_run(plan, ui_map=ui)
    _pass("missing_remove_image_not_ok", result.ok is False)
    _pass("missing_remove_image_error", any("remove_image" in e for e in result.errors))


def _unit_no_execution_calls() -> None:
    plan = build_continuity_plan(
        project_id="safe",
        starter_image_prompt="x",
        clip_prompts=["a", "b"],
    )
    result = run_dry_run(plan, ui_map=_mock_ui_map())
    _pass("all_steps_simulated", all(s.simulated for s in result.steps))
    gated = [s for s in result.steps if s.requires_operator_approval]
    _pass("approval_gated_present", len(gated) >= 3)
    _pass("generate_gated", any(s.control_key == "generate_button" and s.requires_operator_approval for s in gated))
    _pass("download_gated", any(s.control_key == "download_mp4_button" and s.requires_operator_approval for s in gated))
    _pass("image_generate_gated", any(s.control_key == "image_generate_button" for s in gated))
    _pass("safety_gates", "no_generate_click" in result.safety_gates)


def validate_live_map() -> int:
    if not MAP_PATH.is_file():
        print(f"[validate_runway_starter_to_video_dry_run] Missing map: {MAP_PATH}")
        return 1

    snap = resolve_runway_ui_controls(map_path=MAP_PATH)
    print("\n[validate_runway_starter_to_video_dry_run] Live map snapshot")
    print(f"  Path: {MAP_PATH}")
    print(f"  Controls resolved: {len(snap.controls)}")
    print(f"  Missing: {snap.missing or '(none)'}")
    print(f"  Invalid: {snap.invalid or '(none)'}")

    plan = build_continuity_plan(
        project_id="live_dry_run",
        starter_image_prompt="Vertical neon portrait starter frame.",
        clip_prompts=["Clip 1", "Clip 2", "Clip 3"],
    )
    result = run_dry_run(plan, map_path=MAP_PATH)
    print(f"  Dry-run ok: {result.ok}")
    print(f"  Steps: {len(result.steps)}")
    if result.errors:
        print("  Errors:")
        for err in result.errors:
            print(f"    - {err}")
    if result.warnings:
        print("  Warnings (first 5):")
        for warn in result.warnings[:5]:
            print(f"    - {warn}")

    # Live map may miss image_quality_* — report only, do not fail entire validator if continuity video controls ok
    _pass("live_steps_built", len(result.steps) > 0)
    _pass("live_has_use_to_video_step", any(s.control_key == "image_use_to_video_option" for s in result.steps))
    _pass("live_has_remove_image_step", any(s.control_key == "remove_image" for s in result.steps))
    return 0


def main() -> int:
    print("[validate_runway_starter_to_video_dry_run] Unit checks")
    _static_checks()
    _unit_map_loader_body_fail()
    _unit_weak_selector_warn_only()
    _unit_starter_workflow_steps()
    _unit_completion_rule()
    _unit_defaults()
    _unit_image_generation_profiles()
    _unit_three_clip_step_count()
    _unit_missing_use_to_video_fails()
    _unit_missing_remove_image_fails()
    _unit_no_execution_calls()

    print("\n[validate_runway_starter_to_video_dry_run] Live map (informational)")
    return validate_live_map()


if __name__ == "__main__":
    raise SystemExit(main())
