"""Validate prior-clip continuity language injection for story-first Kling Frame prompts."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_TO_VIDEO_MODE  # noqa: E402
from content_brain.execution.kling_frame_to_video_planner import (  # noqa: E402
    plan_kling_frame_to_video_content,
    validate_kling_frame_content_plan,
)
from content_brain.execution.kling_product_run import _uses_frame_to_video  # noqa: E402
from content_brain.execution.kling_use_frame_runtime import (  # noqa: E402
    CONTINUITY_METHOD_USE_FRAME,
    USE_FRAME_CHAIN_FILENAME,
)
from content_brain.story.story_first_prompt_engine import (  # noqa: E402
    STORY_FIRST_PROMPT_MIN_CHARS,
    STORY_FIRST_TARGET_STORY_RATIO,
    TECHNICAL_SECTION_MARKER,
    audit_story_first_prompt,
    ensure_prior_clip_continuity_language,
    has_prior_clip_continuity_language,
    validate_kling_frame_plan_story_first,
)

ROBOT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpers. "
    "Cinematic emotional sci-fi. Native audio."
)

OPENAI_CLIP2_WITHOUT_MARKERS = (
    "Character behavior stays specific to this chapter role (Payoff). The young woman and wounded robot dog "
    "sprint forward, continuing immediately from the glowing path deeper into the scene. Native in-scene audio "
    "carries rain, breath, and mechanical whimpers without external narration. "
    + ("Sensory detail accumulates: neon reflections, wet pavement, distant sirens, emotional tension rising. " * 55)
    + f" {TECHNICAL_SECTION_MARKER} Visual style: cinematic sci-fi. Audio style: native in-scene only. "
    "Camera style: tracking shot. Continuity anchor: same young woman and wounded robot dog in neon rain alley."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _continuity_validator_passes(prompt: str, clip_index: int) -> bool:
    if clip_index <= 1:
        return True
    lowered = prompt.lower()
    return "previous" in lowered or "resumes" in lowered


def test_openai_style_gap_fails_without_injection() -> None:
    sample = OPENAI_CLIP2_WITHOUT_MARKERS[:2500]
    _pass("sample_missing_markers", not has_prior_clip_continuity_language(sample))
    _pass("sample_has_continuing", "continuing immediately from" in sample.lower())
    _pass("continuity_validator_would_fail", not _continuity_validator_passes(sample, 2))


def test_ensure_injects_required_markers() -> None:
    sample = OPENAI_CLIP2_WITHOUT_MARKERS[:2500]
    fixed = ensure_prior_clip_continuity_language(
        sample,
        clip_index=2,
        prior_bridge_hint="glowing path deeper into the scene",
        cast="young woman and wounded robot dog",
        emotion="determined fear",
        style="cinematic sci-fi",
        mood="dramatic",
        camera_direction="tracking shot",
        continuity_anchor="same cast in neon rain alley",
    )
    lowered = fixed.lower()
    _pass("injected_resumes", "resumes" in lowered)
    _pass("injected_previous", "previous" in lowered)
    _pass("injected_continuing", "continuing immediately from" in lowered)
    audit = audit_story_first_prompt(fixed)
    _pass("injected_length", audit.prompt_length >= STORY_FIRST_PROMPT_MIN_CHARS, str(audit.prompt_length))
    _pass("injected_story_ratio", audit.story_percent >= STORY_FIRST_TARGET_STORY_RATIO * 100, f"{audit.story_percent}%")


def test_clip1_passes() -> None:
    plan = plan_kling_frame_to_video_content(
        topic=ROBOT_TOPIC,
        planned_duration_seconds=45,
        characters=["young woman", "wounded robot dog"],
        environment="neon cyberpunk city during heavy rain",
    )
    clip1 = plan.clips[0]
    _pass("clip1_no_continuity_required", _continuity_validator_passes(clip1.prompt, 1))
    audit = audit_story_first_prompt(clip1.prompt)
    _pass("clip1_length", audit.prompt_length >= STORY_FIRST_PROMPT_MIN_CHARS, str(audit.prompt_length))
    _pass("clip1_story_ratio", audit.story_percent >= STORY_FIRST_TARGET_STORY_RATIO * 100, f"{audit.story_percent}%")


def test_clip2_and_clip3_pass_with_mock_openai() -> None:
    def _mock_openai(**kwargs: object) -> tuple[str | None, dict]:
        clip_index = int(kwargs.get("clip_index") or 1)
        if clip_index == 1:
            from content_brain.story.story_first_prompt_engine import compose_story_first_frame_prompt

            compose_keys = {
                "topic", "cast", "environment", "beat", "emotion", "chapter_role",
                "story_objective", "visual_progression", "dialogue", "dialogue_goal",
                "clip_index", "total_clips", "prior_bridge_hint", "bridge_hint",
                "conflict_level", "mood", "style", "camera_direction",
                "continuity_anchor", "directives_summary",
            }
            compose_kwargs = {k: v for k, v in kwargs.items() if k in compose_keys}
            return compose_story_first_frame_prompt(**compose_kwargs), {"openai_applied": True}
        return OPENAI_CLIP2_WITHOUT_MARKERS[:2500], {"openai_applied": True}

    with patch(
        "content_brain.story.kling_story_first_openai_writer.try_write_story_first_prompt_openai",
        side_effect=_mock_openai,
    ):
        plan = plan_kling_frame_to_video_content(
            topic=ROBOT_TOPIC,
            planned_duration_seconds=45,
            characters=["young woman", "wounded robot dog"],
            environment="neon cyberpunk city during heavy rain",
        )

    for clip in plan.clips:
        audit = audit_story_first_prompt(clip.prompt)
        _pass(f"clip{clip.clip_index}_continuity_validator", _continuity_validator_passes(clip.prompt, clip.clip_index))
        _pass(f"clip{clip.clip_index}_length", audit.prompt_length >= STORY_FIRST_PROMPT_MIN_CHARS, str(audit.prompt_length))
        _pass(
            f"clip{clip.clip_index}_story_ratio",
            audit.story_percent >= STORY_FIRST_TARGET_STORY_RATIO * 100,
            f"{audit.story_percent}%",
        )
        if clip.clip_index > 1:
            authorship = (clip.chapter_progression or {}).get("prompt_authorship") or {}
            _pass(
                f"clip{clip.clip_index}_injection_note",
                "prior_clip_continuity_injected" in (authorship.get("notes") or []),
                str(authorship.get("notes")),
            )


def test_full_plan_validators_pass() -> None:
    plan = plan_kling_frame_to_video_content(
        topic=ROBOT_TOPIC,
        planned_duration_seconds=45,
        characters=["young woman", "wounded robot dog"],
        environment="neon cyberpunk city during heavy rain",
    )
    story_ok, story_errors, _ = validate_kling_frame_plan_story_first(plan)
    ok, errors = validate_kling_frame_content_plan(plan)
    _pass("story_first_validator", story_ok, str(story_errors))
    _pass("continuity_content_validator", ok, str(errors))


def test_use_frame_chain_unchanged() -> None:
    use_frame_src = (ROOT / "content_brain/execution/kling_use_frame_runtime.py").read_text(encoding="utf-8")
    frame_chain_src = (ROOT / "content_brain/execution/kling_frame_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("use_frame_chain_filename", USE_FRAME_CHAIN_FILENAME == "use_frame_chain.json")
    _pass("use_frame_method_constant", CONTINUITY_METHOD_USE_FRAME == "use_frame")
    _pass("apply_continuity_fn", "def apply_continuity_for_next_clip" in use_frame_src)
    _pass("frame_chain_runtime", "kling_frame_continuity_runtime" in frame_chain_src)
    preflight = {"kling_shot_mode": KLING_FRAME_TO_VIDEO_MODE, "kling_frame_to_video_plan": {"clip_count": 3}}
    _pass("frame_route_primary", _uses_frame_to_video(preflight) is True)


def main() -> int:
    print("validate_story_first_continuity_language_fix")
    test_openai_style_gap_fails_without_injection()
    test_ensure_injects_required_markers()
    test_clip1_passes()
    test_clip2_and_clip3_pass_with_mock_openai()
    test_full_plan_validators_pass()
    test_use_frame_chain_unchanged()
    print("All story-first continuity language fix checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
