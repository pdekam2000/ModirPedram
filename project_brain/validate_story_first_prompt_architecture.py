"""Validate Story-First prompt architecture for Kling Frame-to-Video."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_models import (  # noqa: E402
    KLING_FRAME_PROMPT_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MIN_CHARS,
)
from content_brain.execution.kling_frame_to_video_planner import (  # noqa: E402
    plan_kling_frame_to_video_content,
    validate_kling_frame_content_plan,
)
from content_brain.story.story_first_prompt_engine import (  # noqa: E402
    STORY_FIRST_GENERATION_FAIL_STORY_RATIO,
    STORY_FIRST_PROMPT_HARD_MIN,
    STORY_FIRST_PROMPT_MIN_CHARS,
    STORY_FIRST_PROMPT_TARGET_MAX,
    STORY_FIRST_PROMPT_TARGET_MIN,
    STORY_FIRST_TARGET_STORY_RATIO,
    audit_story_first_prompt,
    validate_story_first_prompt_for_generation,
)

ROBOT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpers. "
    "Cinematic emotional sci-fi. Native audio."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_constants() -> None:
    _pass("hard_min_2000", STORY_FIRST_PROMPT_HARD_MIN == 2000)
    _pass("min_2300", STORY_FIRST_PROMPT_MIN_CHARS == 2300)
    _pass("target_min_2400", STORY_FIRST_PROMPT_TARGET_MIN == 2400)
    _pass("target_max_2500", STORY_FIRST_PROMPT_TARGET_MAX == 2500)
    _pass("model_target_sync", KLING_FRAME_PROMPT_TARGET_MIN_CHARS == 2400 and KLING_FRAME_PROMPT_TARGET_MAX_CHARS == 2500)


def test_prompt_length_and_ratio() -> None:
    plan = plan_kling_frame_to_video_content(
        topic=ROBOT_TOPIC,
        planned_duration_seconds=30,
        characters=["young woman", "wounded robot dog"],
        environment="neon cyberpunk city during heavy rain",
    )
    for clip in plan.clips:
        audit = audit_story_first_prompt(clip.prompt)
        _pass(f"clip_{clip.clip_index}_hard_min", audit.prompt_length >= STORY_FIRST_PROMPT_HARD_MIN, str(audit.prompt_length))
        _pass(f"clip_{clip.clip_index}_recommended_min", audit.prompt_length >= STORY_FIRST_PROMPT_MIN_CHARS, str(audit.prompt_length))
        _pass(f"clip_{clip.clip_index}_under_max", audit.prompt_length <= KLING_FRAME_PROMPT_MAX_CHARS)
        _pass(
            f"clip_{clip.clip_index}_story_ratio",
            audit.story_percent >= STORY_FIRST_TARGET_STORY_RATIO * 100,
            f"{audit.story_percent}%",
        )
        _pass(
            f"clip_{clip.clip_index}_technical_ratio",
            audit.technical_percent <= (1 - STORY_FIRST_TARGET_STORY_RATIO) * 100 + 1,
            f"{audit.technical_percent}%",
        )
        _pass(f"clip_{clip.clip_index}_audit_fields", all(
            hasattr(audit, field) for field in (
                "story_percent",
                "technical_percent",
                "character_count",
                "dialogue_density",
                "emotion_density",
                "prompt_length",
            )
        ))


def test_generation_validation_floor() -> None:
    plan = plan_kling_frame_to_video_content(topic=ROBOT_TOPIC, planned_duration_seconds=15)
    ok, audit = validate_story_first_prompt_for_generation(plan.clips[0].prompt)
    _pass("generation_ok", ok)
    _pass("story_floor", audit.story_percent >= STORY_FIRST_GENERATION_FAIL_STORY_RATIO * 100, str(audit.story_percent))


def test_fail_short_prompt() -> None:
    ok, audit = validate_story_first_prompt_for_generation("Short metadata prompt.")
    _pass("short_fail", not ok)
    _pass("short_length", any("prompt_length" in err for err in audit.errors))


def test_fail_low_story_ratio() -> None:
    story = (
        "A young woman kneels beside a wounded robot dog in rain. She whispers reassurance. "
        "Neon reflections ripple across wet pavement."
    )
    technical_body = (
        "Visual style: cinematic sci-fi, moody neon. Audio style: native in-scene only. "
        "Camera style: slow dolly with shallow depth. Continuity anchor: same alley, same outfits. "
    ) * 45
    prompt = f"{story}\n\n--- Technical execution --- {technical_body}"
    prompt = prompt[:2500]
    ok, audit = validate_story_first_prompt_for_generation(prompt)
    _pass("low_story_ratio_fail", not ok)
    _pass("low_story_floor", any("story_percent" in err for err in audit.errors))


def test_content_plan_validator() -> None:
    plan = plan_kling_frame_to_video_content(topic=ROBOT_TOPIC, planned_duration_seconds=30)
    ok, errors = validate_kling_frame_content_plan(plan)
    _pass("content_plan_ok", ok, str(errors))


def test_preview_audit_embedded() -> None:
    from content_brain.execution.kling_frame_to_video_planner import build_kling_frame_clip_prompts_preview

    plan = plan_kling_frame_to_video_content(topic=ROBOT_TOPIC, planned_duration_seconds=30)
    preview = build_kling_frame_clip_prompts_preview(plan)
    _pass("preview_audit", all("story_first_audit" in item for item in preview))


def main() -> int:
    print("validate_story_first_prompt_architecture")
    test_constants()
    test_prompt_length_and_ratio()
    test_generation_validation_floor()
    test_fail_short_prompt()
    test_fail_low_story_ratio()
    test_content_plan_validator()
    test_preview_audit_embedded()
    print("All Story-First prompt architecture checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
