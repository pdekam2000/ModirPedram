"""Validate cinematic story prompts (no metadata labels in story body)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_planner import (
    plan_kling_frame_to_video_content,
    validate_kling_frame_content_plan,
)
from content_brain.story.kling_story_first_openai_writer import SYSTEM_PROMPT, _build_openai_brief
from content_brain.story.story_first_prompt_engine import (
    FORBIDDEN_STORY_METADATA_PHRASES,
    STORY_FIRST_PROMPT_MIN_CHARS,
    STORY_FIRST_TARGET_STORY_RATIO,
    TECHNICAL_SECTION_MARKER,
    audit_story_first_prompt,
    compose_story_first_frame_prompt,
    find_forbidden_story_metadata,
    validate_cinematic_story_body,
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


def test_local_prompts_are_cinematic() -> None:
    plan = plan_kling_frame_to_video_content(
        topic=ROBOT_TOPIC,
        planned_duration_seconds=45,
        characters=["young woman", "wounded robot dog"],
        environment="neon cyberpunk city during heavy rain",
    )
    ok, errors = validate_kling_frame_content_plan(plan)
    _pass("content_plan_valid", ok, str(errors))
    for clip in plan.clips:
        story_part = clip.prompt.split(TECHNICAL_SECTION_MARKER, 1)[0]
        hits = find_forbidden_story_metadata(story_part)
        _pass(f"clip{clip.clip_index}_no_metadata", not hits, str(hits))
        audit = audit_story_first_prompt(clip.prompt)
        _pass(f"clip{clip.clip_index}_length", audit.prompt_length >= STORY_FIRST_PROMPT_MIN_CHARS, str(audit.prompt_length))
        _pass(
            f"clip{clip.clip_index}_story_ratio",
            audit.story_percent >= STORY_FIRST_TARGET_STORY_RATIO * 100,
            f"{audit.story_percent}%",
        )


def test_openai_brief_is_internal_only() -> None:
    brief = _build_openai_brief(
        topic=ROBOT_TOPIC,
        cast="young woman and wounded robot dog",
        environment="neon city",
        beat="escape begins",
        emotion="fear",
        chapter_role="Hook",
        story_objective="establish empathy",
        visual_progression="close tracking",
        dialogue="Stay with me.",
        dialogue_goal="whisper reassurance",
        clip_index=1,
        total_clips=2,
        prior_bridge_hint="",
        bridge_hint="shelter",
        conflict_level=1,
        mood="sci-fi",
        style="cinematic",
        camera_direction="dolly",
        continuity_anchor="same alley",
        directives_summary="native audio",
        character_continuity="same cast",
        environment_continuity="same alley",
    )
    _pass("brief_has_internal_instruction", "_instruction" in brief)
    _pass("system_forbids_metadata", "FORBIDDEN" in SYSTEM_PROMPT and "Chapter role:" in SYSTEM_PROMPT)


def test_legacy_metadata_would_fail() -> None:
    legacy = (
        "The chapter opens on cast. Character behavior stays specific to this chapter role (Hook). "
        "Conflict level 1 shows in pacing. Dialogue goal for this chapter: whisper reassurance."
    )
    ok, errors = validate_cinematic_story_body(legacy)
    _pass("legacy_metadata_fails", not ok)
    _pass("legacy_has_multiple_hits", len(errors) >= 3, str(len(errors)))


def test_compose_sample_excerpt() -> None:
    prompt = compose_story_first_frame_prompt(
        topic=ROBOT_TOPIC,
        cast="young woman and wounded robot dog",
        environment="neon cyberpunk city during heavy rain",
        beat="They run through alleys",
        emotion="determined fear",
        chapter_role="Hook",
        story_objective="Establish empathy",
        visual_progression="Close tracking through rain",
        dialogue="Stay with me.",
        dialogue_goal="Whisper reassurance",
        clip_index=1,
        total_clips=2,
        prior_bridge_hint="",
        bridge_hint="hidden shelter",
        conflict_level=1,
        mood="cinematic sci-fi",
        style="cinematic realistic",
        camera_direction="slow push-in",
        continuity_anchor="same cast in neon rain alley",
        directives_summary="native in-scene audio",
    )
    excerpt = prompt[:220].lower()
    _pass("sample_not_chapter_opens", "the chapter opens" not in excerpt)
    _pass("sample_not_conflict_level", "conflict level" not in prompt.lower())
    _pass("sample_has_action", "rain" in excerpt or "motion" in excerpt or "inside" in excerpt)


def main() -> int:
    print("validate_cinematic_story_prompt")
    test_local_prompts_are_cinematic()
    test_openai_brief_is_internal_only()
    test_legacy_metadata_would_fail()
    test_compose_sample_excerpt()
    print("All cinematic story prompt checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
