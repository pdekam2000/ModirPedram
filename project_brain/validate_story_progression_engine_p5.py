"""Validate Story Progression Engine P5."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content  # noqa: E402
from content_brain.story.story_progression_engine import (  # noqa: E402
    CHAPTER_ROLES_BY_CLIP_COUNT,
    build_story_progression_plan,
    chapter_roles_for_clip_count,
    validate_story_progression_plan,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_chapter_count_by_duration() -> None:
    cases = ((15, 1), (30, 2), (45, 3), (60, 4), (75, 5), (90, 6))
    for seconds, expected in cases:
        plan = build_story_progression_plan(planned_duration_seconds=seconds, topic="robot dog neon city")
        _pass(f"{seconds}s_chapter_count", len(plan.chapters) == expected, str(len(plan.chapters)))


def test_chapter_roles_never_duplicate_incorrectly() -> None:
    for clip_count, roles in CHAPTER_ROLES_BY_CLIP_COUNT.items():
        plan = build_story_progression_plan(planned_duration_seconds=clip_count * 15, clip_count=clip_count)
        assigned = [c.chapter_role for c in plan.chapters]
        _pass(f"roles_match_{clip_count}", assigned == list(roles), str(assigned))
        _pass(f"unique_roles_{clip_count}", len(set(assigned)) == len(assigned))


def test_conflict_increases_before_resolution() -> None:
    for clip_count in (3, 4, 5, 6):
        plan = build_story_progression_plan(planned_duration_seconds=clip_count * 15, clip_count=clip_count)
        rising = [c for c in plan.chapters if c.chapter_role not in {"resolution", "payoff"}]
        ok = all(
            rising[i].conflict_level <= rising[i + 1].conflict_level for i in range(len(rising) - 1)
        )
        _pass(f"conflict_rises_{clip_count}clips", ok)


def test_resolution_appears_last() -> None:
    for clip_count in (2, 3, 4, 5, 6):
        plan = build_story_progression_plan(planned_duration_seconds=clip_count * 15, clip_count=clip_count)
        last_role = plan.chapters[-1].chapter_role
        expected_last = "payoff" if clip_count == 2 else "resolution"
        _pass(f"last_role_{clip_count}clips", last_role == expected_last, last_role)


def test_frame_planner_consumes_progression() -> None:
    plan = plan_kling_frame_to_video_content(topic="young boy and baby dragon", planned_duration_seconds=60)
    _pass("frame_plan_has_progression", bool(plan.story_progression.get("chapters")))
    _pass("four_clips_60s", plan.clip_count == 4)
    roles = [clip.chapter_progression.get("chapter_role") for clip in plan.clips]
    _pass("60s_roles", roles == ["hook", "escalation", "conflict", "resolution"], str(roles))
    for clip in plan.clips:
        from content_brain.story.story_first_prompt_engine import validate_cinematic_story_body

        story_part = clip.prompt.split("--- Technical execution ---", 1)[0]
        ok, _ = validate_cinematic_story_body(story_part)
        _pass(f"clip{clip.clip_index}_cinematic_prose", ok)
        _pass(
            f"clip{clip.clip_index}_progression_metadata",
            bool(clip.chapter_progression.get("chapter_role")),
        )
    ok, _ = validate_story_progression_plan(
        build_story_progression_plan(planned_duration_seconds=60, topic="young boy and baby dragon")
    )
    _pass("progression_validates", ok)


def test_character_continuity_preserved() -> None:
    plan = plan_kling_frame_to_video_content(topic="robot dog neon city", planned_duration_seconds=45)
    for clip in plan.clips:
        prompt = clip.prompt.lower()
        from content_brain.story.story_first_prompt_engine import validate_cinematic_story_body

        story_part = clip.prompt.split("--- Technical execution ---", 1)[0]
        ok, _ = validate_cinematic_story_body(story_part)
        _pass(f"clip{clip.clip_index}_cinematic_prose", ok)
        _pass(f"clip{clip.clip_index}_continuity_anchor", "continuity anchor" in prompt)
        if clip.clip_index > 1:
            _pass(
                f"clip{clip.clip_index}_handoff_language",
                "continuing immediately from" in prompt or "resumes" in prompt,
            )
            _pass(f"clip{clip.clip_index}_no_repeat_beats", "without repeating" in prompt or "repeating what" in prompt)


def test_multishot_pipeline_unaffected() -> None:
    multishot = (ROOT / "content_brain/execution/kling_continuity_runtime.py").read_text(encoding="utf-8")
    native_planner = (ROOT / "content_brain/execution/kling_native_audio_planner.py").read_text(encoding="utf-8")
    _pass("multishot_chain_fn", "def run_kling_continuity_chain" in multishot)
    _pass("multishot_plan_fn", "def plan_kling_native_audio_content" in native_planner)
    _pass("multishot_preflight", "def build_kling_preflight_api_payload" in native_planner)


def main() -> int:
    print("validate_story_progression_engine_p5")
    test_chapter_count_by_duration()
    test_chapter_roles_never_duplicate_incorrectly()
    test_conflict_increases_before_resolution()
    test_resolution_appears_last()
    test_frame_planner_consumes_progression()
    test_character_continuity_preserved()
    test_multishot_pipeline_unaffected()
    print("All Story Progression Engine P5 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
