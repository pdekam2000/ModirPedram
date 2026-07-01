"""Validate Kling Frame-to-Video architecture switch — design + schema, no credits."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_models import (  # noqa: E402
    KLING_FRAME_PROMPT_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MIN_CHARS,
    KLING_FRAME_TO_VIDEO_MODE,
    KLING_FRAME_TO_VIDEO_PLAN_VERSION,
    KLING_MULTISHOT_MODE,
    select_kling_generation_mode,
    validate_kling_frame_to_video_plan,
)
from content_brain.execution.kling_frame_to_video_planner import (  # noqa: E402
    PLANNER_VERSION,
    plan_kling_frame_to_video_content,
    validate_kling_frame_content_plan,
)
from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    KLING_SHOT_PROMPT_MAX_CHARS,
    build_kling_native_audio_plan,
    validate_kling_native_audio_plan,
)

ROBOT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpsers. "
    'The woman whispers: "Stay with me... we\'re almost safe." '
    "Cinematic emotional sci-fi. Native audio."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_frame_mode_in_architecture_doc() -> None:
    doc = (ROOT / "project_brain/KLING_FRAME_TO_VIDEO_ARCHITECTURE.md").read_text(encoding="utf-8")
    _pass("architecture_doc_exists", doc.strip() != "")
    _pass("frame_mode_preferred", "preferred" in doc.lower() and "frame-to-video" in doc.lower())
    _pass("roadmap_p0_p6", all(f"P{i}" in doc for i in range(7)))


def test_multishot_remains_fallback() -> None:
    story_doc = (ROOT / "project_brain/KLING_STORY_ARCHITECTURE_DESIGN.md").read_text(encoding="utf-8")
    arch_doc = (ROOT / "project_brain/KLING_FRAME_TO_VIDEO_ARCHITECTURE.md").read_text(encoding="utf-8")
    _pass("story_doc_fallback", "fallback" in story_doc.lower())
    _pass("arch_doc_multishot_fallback", KLING_MULTISHOT_MODE in arch_doc)
    _pass("planner_fallback_constant", KLING_MULTISHOT_MODE == "kling_multishot_native_audio")


def test_provider_mode_names_defined() -> None:
    _pass("frame_mode_id", KLING_FRAME_TO_VIDEO_MODE == "kling_frame_to_video_native_audio")
    _pass("multishot_mode_id", KLING_MULTISHOT_MODE == "kling_multishot_native_audio")
    selected = select_kling_generation_mode(
        topic=ROBOT_TOPIC,
        genre="sci-fi",
        mood="emotional",
        has_dialogue=True,
    )
    _pass("auto_selects_frame", selected == KLING_FRAME_TO_VIDEO_MODE)
    fallback = select_kling_generation_mode(topic=ROBOT_TOPIC, frame_mode_available=False)
    _pass("unavailable_falls_back", fallback == KLING_MULTISHOT_MODE)


def test_planner_schema_defined() -> None:
    plan = plan_kling_frame_to_video_content(
        topic=ROBOT_TOPIC,
        planned_duration_seconds=30,
        platform="youtube_shorts",
        characters=["young woman", "wounded robot dog"],
        environment="neon cyberpunk city during heavy rain",
    )
    _pass("plan_version", plan.version == KLING_FRAME_TO_VIDEO_PLAN_VERSION)
    _pass("plan_two_clips", plan.clip_count == 2 and len(plan.clips) == 2)
    clip = plan.clips[0].to_dict()
    for key in (
        "clip_index",
        "duration_seconds",
        "first_frame_source",
        "end_frame_source",
        "prompt",
        "character_continuity",
        "environment_continuity",
        "dialogue",
        "native_audio_directives",
        "camera_direction",
        "continuity_anchor",
        "next_clip_reference_hint",
    ):
        _pass(f"clip_field_{key}", key in clip)
    ok, errors = validate_kling_frame_to_video_plan(plan)
    _pass("schema_validate", ok, str(errors))
    ok2, errors2 = validate_kling_frame_content_plan(plan)
    _pass("content_validate", ok2, str(errors2))


def test_continuity_rule_defined() -> None:
    doc = (ROOT / "project_brain/KLING_FRAME_TO_VIDEO_ARCHITECTURE.md").read_text(encoding="utf-8")
    _pass("continuity_extract_rule", "extract last frame" in doc.lower() or "frame_c" in doc)
    _pass("continuity_first_frame_handoff", "first_frame" in doc.lower())
    plan = plan_kling_frame_to_video_content(topic=ROBOT_TOPIC, planned_duration_seconds=30)
    _pass("clip2_prior_frame_source", plan.clips[1].first_frame_source == "prior_clip_shot2_final_frame")
    _pass("clip2_continuity_language", "continuing immediately from" in plan.clips[1].prompt.lower())


def test_prompt_max_2500_documented() -> None:
    doc = (ROOT / "project_brain/KLING_FRAME_TO_VIDEO_ARCHITECTURE.md").read_text(encoding="utf-8")
    _pass("max_2500_constant", KLING_FRAME_PROMPT_MAX_CHARS == 2500)
    _pass("target_range_constants", KLING_FRAME_PROMPT_TARGET_MIN_CHARS == 2400 and KLING_FRAME_PROMPT_TARGET_MAX_CHARS == 2500)
    _pass("max_2500_in_doc", "2500" in doc)
    plan = plan_kling_frame_to_video_content(topic=ROBOT_TOPIC, planned_duration_seconds=30)
    for clip in plan.clips:
        _pass(f"clip_{clip.clip_index}_under_max", len(clip.prompt) <= KLING_FRAME_PROMPT_MAX_CHARS)
        _pass(f"clip_{clip.clip_index}_story_first_min", len(clip.prompt) >= 2300, str(len(clip.prompt)))


def test_no_generate_in_new_modules() -> None:
    for rel in (
        "content_brain/execution/kling_frame_to_video_models.py",
        "content_brain/execution/kling_frame_to_video_planner.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        _pass(f"{rel}_no_generate_click", "generate.locator.click" not in source)
        _pass(f"{rel}_no_live_engine", "run_kling_multishot_live" not in source)


def test_multishot_tests_still_pass() -> None:
    scripts = [
        "project_brain/validate_kling_native_audio_schema_p0.py",
        "project_brain/validate_kling_native_audio_content_planner_p3.py",
        "project_brain/validate_kling_continuity_chain_v1.py",
    ]
    for script in scripts:
        proc = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        _pass(f"{script}_exit_0", proc.returncode == 0, (proc.stderr or proc.stdout)[-240:])


def test_multishot_schema_unchanged() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=30)
    ok, errors = validate_kling_native_audio_plan(plan)
    _pass("multishot_plan_valid", ok, str(errors))
    _pass("multishot_prompt_limit_512", KLING_SHOT_PROMPT_MAX_CHARS == 512)


def main() -> None:
    test_frame_mode_in_architecture_doc()
    test_multishot_remains_fallback()
    test_provider_mode_names_defined()
    test_planner_schema_defined()
    test_continuity_rule_defined()
    test_prompt_max_2500_documented()
    test_no_generate_in_new_modules()
    test_multishot_schema_unchanged()
    test_multishot_tests_still_pass()
    print("validate_kling_frame_architecture_switch: all checks passed")


if __name__ == "__main__":
    main()
