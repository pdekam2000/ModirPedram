"""
Phase RUNWAY-STARTER-TO-VIDEO-F — continuity prompt builder validation.

Prompt generation only — no browser, Generate, Download, credits, or provider execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_dry_run import build_continuity_plan, run_dry_run
from content_brain.execution.runway_prompt_builder import (
    CLIP_DURATION_SECONDS,
    CLIP_PROMPT_HARD_MAX,
    CLIP_PROMPT_SOFT_MAX,
    CLIP_PROMPT_SOFT_MIN,
    STARTER_IMAGE_MAX_CHARS,
    PromptBuilderInput,
    RunwayPromptBuilder,
    _contains_forbidden_visual,
    build_continuity_prompts,
    validate_prompt_bundle,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH

SAMPLE_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere, "
    "neon teal and amber reflections, dramatic volumetric fog, ultra realistic detail. "
    "Clip 1: rain intensifies as she turns toward the skyline. "
    "Clip 2: she walks along the platform edge with city lights pulsing below. "
    "Clip 3: she reaches a dormant launch cradle and places her gloved hand on its surface."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    path = ROOT / "content_brain" / "execution" / "runway_prompt_builder.py"
    text = path.read_text(encoding="utf-8")
    provider = (ROOT / "providers" / "runway_browser_provider.py").read_text(encoding="utf-8")

    _pass("builder_exists", path.is_file())
    _pass("no_browser_import", "BrowserManager" not in text)
    _pass("no_playwright", "playwright" not in text.lower())
    _pass("no_generate_click", "click_generate" not in text)
    _pass("no_download", "download_mp4" not in text)
    _pass("no_provider_import", "from providers.runway_browser_provider" not in text)
    _pass("provider_untouched", "runway_prompt_builder" not in provider)
    _pass("char_limits_defined", all(
        token in text
        for token in ("RUNWAY_PROMPT_MAX_CHARS = 5000", "CLIP_PROMPT_SOFT_MIN = 2500", "CLIP_PROMPT_HARD_MAX = RUNWAY_PROMPT_MAX_CHARS")
    ))


def _unit_build_basic_bundle() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, project_id="f_test", clip_count=3)
    _pass("starter_present", bool(bundle.starter_image_prompt))
    _pass("three_clips", len(bundle.clip_prompts) == 3)
    _pass("starter_max", len(bundle.starter_image_prompt) <= STARTER_IMAGE_MAX_CHARS)
    for index, prompt in enumerate(bundle.clip_prompts, start=1):
        _pass(f"clip_{index}_hard_max", len(prompt) <= CLIP_PROMPT_HARD_MAX, str(len(prompt)))
        _pass(f"clip_{index}_soft_min", len(prompt) >= CLIP_PROMPT_SOFT_MIN, str(len(prompt)))
        _pass(f"clip_{index}_soft_max", len(prompt) <= CLIP_PROMPT_SOFT_MAX, str(len(prompt)))


def _unit_continuity_language() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, clip_count=3)
    _pass("starter_vertical", "9:16" in bundle.starter_image_prompt)
    _pass("starter_cinematic", "cinematic" in bundle.starter_image_prompt.lower())
    _pass("anchors_character", bool(bundle.continuity_anchors.character))
    _pass("anchors_location", bool(bundle.continuity_anchors.location))

    for index, prompt in enumerate(bundle.clip_prompts, start=1):
        lowered = prompt.lower()
        _pass(f"clip_{index}_continuity_lock", "continuity lock" in lowered)
        _pass(f"clip_{index}_no_scene_jump", "no scene jump" in lowered)
        _pass(f"clip_{index}_10_seconds", "10 second" in lowered)
        _pass(f"clip_{index}_no_text", "no text" in lowered and "no subtitles" in lowered)


def _unit_forbidden_terms_sanitized() -> None:
    dirty = (
        "Hero subject in neon alley with subtitles and logo watermark visible on screen. "
        "She walks forward for ten seconds."
    )
    bundle = build_continuity_prompts(dirty, clip_count=1)
    combined = bundle.starter_image_prompt + " " + " ".join(bundle.clip_prompts)
    _pass("forbidden_terms_sanitized", not _contains_forbidden_visual(combined))


def _unit_director_shots_integration() -> None:
    bundle = RunwayPromptBuilder().build(
        PromptBuilderInput(
            story_idea=SAMPLE_STORY,
            clip_count=2,
            director_shots=[
                {
                    "clip_number": 1,
                    "prompt": "Medium close on astronaut visor reflecting city lights.",
                    "camera_shot": "Medium close-up",
                    "camera_movement": "Slow push-in",
                    "action": "Turns head toward horizon",
                    "lighting": "Neon rim light",
                    "continuity_notes": "Matches starter frame wardrobe and location.",
                },
                {
                    "clip_number": 2,
                    "prompt": "Wide vertical tracking along platform edge.",
                    "camera_shot": "Medium-wide tracking",
                    "camera_movement": "Lateral track",
                    "action": "Walks three steps and stops at railing",
                    "continuity_notes": "Continuous rain and palette from clip 1.",
                },
            ],
        )
    )
    _pass("director_clip_count", len(bundle.clip_prompts) == 2)
    _pass("director_action_in_clip_1", "Turns head toward horizon" in bundle.clip_prompts[0])
    _pass("director_continuity_note", "Continuous rain" in bundle.clip_prompts[1])


def _unit_plan_bridge() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, project_id="plan_bridge", clip_count=2)
    plan = bundle.to_continuity_plan()
    _pass("plan_project_id", plan.project_id == "plan_bridge")
    _pass("plan_starter_matches", plan.starter_image_prompt == bundle.starter_image_prompt)
    _pass("plan_clip_count", len(plan.clip_prompts) == 2)


def _unit_validation_clean() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, clip_count=3)
    quality_warnings = validate_prompt_bundle(bundle)
    _pass("validation_no_fatal_warnings", len(quality_warnings) == 0, str(quality_warnings))


def _unit_empty_story_fails() -> None:
    failed = False
    try:
        build_continuity_prompts("   ")
    except ValueError:
        failed = True
    _pass("empty_story_rejected", failed)


def _unit_dry_run_chain_no_browser() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, project_id="dry_chain", clip_count=3)
    plan = bundle.to_continuity_plan()
    if not DEFAULT_MAP_PATH.is_file():
        print("  [SKIP] live map missing for dry-run chain")
        return
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    _pass("dry_run_from_prompts_ok", dry.ok is True, str(dry.errors))
    _pass("dry_run_steps", len(dry.steps) >= 20)


def main() -> int:
    print("[validate_runway_starter_to_video_prompt_builder] Static checks")
    _static_checks()

    print("\n[validate_runway_starter_to_video_prompt_builder] Unit checks")
    _unit_build_basic_bundle()
    _unit_continuity_language()
    _unit_forbidden_terms_sanitized()
    _unit_director_shots_integration()
    _unit_plan_bridge()
    _unit_validation_clean()
    _unit_empty_story_fails()
    _unit_dry_run_chain_no_browser()

    print("\n[validate_runway_starter_to_video_prompt_builder] Limits reference")
    print(f"  starter_image max: {STARTER_IMAGE_MAX_CHARS}")
    print(f"  clip soft target: {CLIP_PROMPT_SOFT_MIN}-{CLIP_PROMPT_SOFT_MAX}")
    print(f"  clip hard max: {CLIP_PROMPT_HARD_MAX}")
    print(f"  clip duration: {CLIP_DURATION_SECONDS}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
