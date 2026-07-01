"""Validate OpenAI-primary authorship for Kling story-first Frame prompts."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_planner import (  # noqa: E402
    PLANNER_VERSION,
    plan_kling_frame_to_video_content,
    validate_kling_frame_content_plan,
)
from content_brain.story.kling_story_first_openai_writer import (  # noqa: E402
    OPENAI_WRITER_VERSION,
    try_write_story_first_prompt_openai,
)
from content_brain.story.story_first_prompt_engine import (  # noqa: E402
    STORY_FIRST_PROMPT_MIN_CHARS,
    STORY_FIRST_TARGET_STORY_RATIO,
    TECHNICAL_SECTION_MARKER,
    audit_story_first_prompt,
    compose_story_first_frame_prompt,
    compose_story_first_frame_prompt_primary,
)

ROBOT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpers. "
    "Cinematic emotional sci-fi. Native audio."
)

OPENAI_SAMPLE = (
    "Rain hammers a neon alley where a young woman kneels beside a wounded robot dog. "
    "Her hands tremble against its damaged flank; the machine whimpers softly, almost lost under the downpour. "
    "Magenta and cyan ripple across wet pavement as distant sirens pulse through the canyon of buildings. "
    "She scans the alley mouth — danger is closing — and whispers, \"Stay with me. We move on my count.\" "
    "Steam bursts from a grate; a sparking conduit hisses overhead; drones sweep white cones of light that force "
    "them to duck into shadow. She pulls the dog closer, boots splashing, fear and determination fighting on her face. "
    + ("She commits to a glowing corridor ahead, every step raising the cost of hesitation. " * 48)
    + f" {TECHNICAL_SECTION_MARKER} Visual style: cinematic sci-fi, moody neon. "
    "Audio style: native in-scene only. Camera style: slow push-in with shallow depth. "
    "Continuity anchor: same young woman and wounded robot dog, same rain-slick neon alley."
)[:2500]


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_openai_writer_module_exists() -> None:
    _pass("openai_writer_version", bool(OPENAI_WRITER_VERSION))
    _pass("planner_version_openai", "openai" in PLANNER_VERSION)


def test_local_fallback_when_openai_unavailable() -> None:
    plan = plan_kling_frame_to_video_content(
        topic=ROBOT_TOPIC,
        planned_duration_seconds=30,
        characters=["young woman", "wounded robot dog"],
        environment="neon cyberpunk city during heavy rain",
    )
    ok, errors = validate_kling_frame_content_plan(plan)
    _pass("local_fallback_plan_valid", ok, str(errors))
    for clip in plan.clips:
        audit = audit_story_first_prompt(clip.prompt)
        authorship = (clip.chapter_progression or {}).get("prompt_authorship") or {}
        _pass(f"clip_{clip.clip_index}_length", audit.prompt_length >= STORY_FIRST_PROMPT_MIN_CHARS, str(audit.prompt_length))
        _pass(f"clip_{clip.clip_index}_story_ratio", audit.story_percent >= STORY_FIRST_TARGET_STORY_RATIO * 100, f"{audit.story_percent}%")
        _pass(f"clip_{clip.clip_index}_authorship_recorded", bool(authorship.get("source")))
        _pass(
            f"clip_{clip.clip_index}_local_fallback",
            authorship.get("source") == "local_template",
            str(authorship),
        )


def test_openai_primary_path_mocked() -> None:
    with patch(
        "content_brain.story.kling_story_first_openai_writer._openai_text_completion",
        return_value=(OPENAI_SAMPLE, "gpt-4.1-mini", ["openai_kling_prompt_applied:gpt-4.1-mini"]),
    ):
        prompt, meta = compose_story_first_frame_prompt_primary(
            prefer_openai=True,
            topic=ROBOT_TOPIC,
            cast="young woman and wounded robot dog",
            environment="neon cyberpunk city during heavy rain",
            beat="Escape begins",
            emotion="determined fear",
            chapter_role="Hook",
            story_objective="Establish empathy and stakes",
            visual_progression="Close coverage into corridor commit",
            dialogue="Stay with me. We move on my count.",
            dialogue_goal="Whispered reassurance",
            clip_index=1,
            total_clips=2,
            prior_bridge_hint="",
            bridge_hint="hidden shelter entrance ahead",
            conflict_level=1,
            mood="cinematic sci-fi",
            style="cinematic realistic",
            camera_direction="slow push-in",
            continuity_anchor="same young woman and wounded robot dog in neon rain alley",
            directives_summary="Native cinematic in-scene audio only",
            character_continuity="Same young woman and wounded robot dog appearance",
            environment_continuity="Same neon rain alley layout",
        )
    audit = audit_story_first_prompt(prompt)
    _pass("openai_mock_applied", meta.get("openai_applied") is True, str(meta))
    _pass("openai_mock_source", meta.get("source") == "openai")
    _pass("openai_mock_length", audit.prompt_length >= STORY_FIRST_PROMPT_MIN_CHARS, str(audit.prompt_length))
    _pass("openai_mock_story_ratio", audit.story_percent >= STORY_FIRST_TARGET_STORY_RATIO * 100, f"{audit.story_percent}%")
    from content_brain.story.story_first_prompt_engine import find_forbidden_story_metadata

    story_part = prompt.split(TECHNICAL_SECTION_MARKER, 1)[0]
    _pass("openai_mock_no_metadata", not find_forbidden_story_metadata(story_part))


def test_openai_invalid_falls_back_to_local() -> None:
    with patch(
        "content_brain.story.kling_story_first_openai_writer._openai_text_completion",
        return_value=("Too short.", "gpt-4.1-mini", ["openai_kling_prompt_applied:gpt-4.1-mini"]),
    ):
        prompt, meta = compose_story_first_frame_prompt_primary(
            prefer_openai=True,
            topic=ROBOT_TOPIC,
            cast="young woman and wounded robot dog",
            environment="neon cyberpunk city during heavy rain",
            beat="Escape begins",
            emotion="determined fear",
            chapter_role="Hook",
            story_objective="Establish empathy and stakes",
            visual_progression="Close coverage into corridor commit",
            dialogue="Stay with me.",
            dialogue_goal="Whispered reassurance",
            clip_index=1,
            total_clips=2,
            prior_bridge_hint="",
            bridge_hint="hidden shelter entrance ahead",
            conflict_level=1,
            mood="cinematic sci-fi",
            style="cinematic realistic",
            camera_direction="slow push-in",
            continuity_anchor="same alley",
            directives_summary="Native in-scene audio only",
            character_continuity="Same characters",
            environment_continuity="Same environment",
        )
    local = compose_story_first_frame_prompt(
        topic=ROBOT_TOPIC,
        cast="young woman and wounded robot dog",
        environment="neon cyberpunk city during heavy rain",
        beat="Escape begins",
        emotion="determined fear",
        chapter_role="Hook",
        story_objective="Establish empathy and stakes",
        visual_progression="Close coverage into corridor commit",
        dialogue="Stay with me.",
        dialogue_goal="Whispered reassurance",
        clip_index=1,
        total_clips=2,
        prior_bridge_hint="",
        bridge_hint="hidden shelter entrance ahead",
        conflict_level=1,
        mood="cinematic sci-fi",
        style="cinematic realistic",
        camera_direction="slow push-in",
        continuity_anchor="same alley",
        directives_summary="Native in-scene audio only",
    )
    _pass("invalid_openai_fallback", meta.get("source") == "local_template", str(meta))
    _pass("fallback_prompt_long_enough", len(prompt) >= STORY_FIRST_PROMPT_MIN_CHARS, str(len(prompt)))
    _pass("fallback_matches_local_template", len(prompt) == len(local))


def test_try_write_dry_run_returns_none() -> None:
    result, meta = try_write_story_first_prompt_openai(
        dry_run=True,
        topic=ROBOT_TOPIC,
        cast="young woman",
        environment="neon city",
        beat="beat",
        emotion="fear",
        chapter_role="Hook",
        story_objective="obj",
        visual_progression="vis",
        dialogue="",
        dialogue_goal="goal",
        clip_index=1,
        total_clips=1,
        prior_bridge_hint="",
        bridge_hint="",
        conflict_level=1,
        mood="mood",
        style="style",
        camera_direction="cam",
        continuity_anchor="anchor",
        directives_summary="native audio",
    )
    _pass("dry_run_none", result is None)
    _pass("dry_run_note", any("dry_run" in n for n in meta.get("notes") or []))


def main() -> int:
    print("validate_kling_prompt_openai_authorship")
    test_openai_writer_module_exists()
    test_local_fallback_when_openai_unavailable()
    test_openai_primary_path_mocked()
    test_openai_invalid_falls_back_to_local()
    test_try_write_dry_run_returns_none()
    print("All Kling prompt OpenAI authorship checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
