"""Validate Kling Native Audio Content Planner P3."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_strategy_router import route_audio_strategy  # noqa: E402
from content_brain.execution.kling_multishot_config import (  # noqa: E402
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    KLING_PROVIDER_ID,
    KLING_SHOT_PROMPT_MAX_CHARS,
)
from content_brain.execution.kling_native_audio_planner import (  # noqa: E402
    plan_kling_from_audio_route,
    plan_kling_native_audio_content,
    validate_kling_content_plan,
)

DRAGON_TOPIC = (
    "A young boy discovers an injured baby dragon under twisted forest roots in a fantasy cinematic story"
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _assert_plan_ok(plan, label: str) -> None:
    ok, errors = validate_kling_content_plan(plan)
    _pass(f"{label}_validate", ok, "; ".join(errors[:3]))


def test_15s_one_clip() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=15)
    _pass("15s_clip_count", plan.clip_count == 1)
    _assert_plan_ok(plan, "15s")


def test_30s_two_clips() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=30)
    _pass("30s_clip_count", plan.clip_count == 2)
    _assert_plan_ok(plan, "30s")


def test_45s_three_clips() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=45)
    _pass("45s_clip_count", plan.clip_count == 3)
    _assert_plan_ok(plan, "45s")


def test_shot_1_duration_12s() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=60)
    _pass(
        "shot_1_12s",
        all(clip.shot_1.duration_seconds == SHOT_1_DURATION_SECONDS == 12 for clip in plan.clips),
    )


def test_shot_2_duration_3s() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=60)
    _pass(
        "shot_2_3s",
        all(clip.shot_2.duration_seconds == SHOT_2_DURATION_SECONDS == 3 for clip in plan.clips),
    )


def test_shot_prompt_max_512() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=60)
    for clip in plan.clips:
        _pass(f"clip_{clip.clip_index}_shot1_len", len(clip.shot_1.prompt) <= KLING_SHOT_PROMPT_MAX_CHARS)
        _pass(f"clip_{clip.clip_index}_shot2_len", len(clip.shot_2.prompt) <= KLING_SHOT_PROMPT_MAX_CHARS)


def test_native_audio_cues_present() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=30)
    cues = ("breathing", "voice", "ambience", "native cinematic audio", "whisper", "wind")
    for clip in plan.clips:
        hay = f"{clip.shot_1.prompt} {clip.shot_2.prompt}".lower()
        _pass(f"clip_{clip.clip_index}_audio_cues", any(token in hay for token in cues))


def test_no_elevenlabs() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=45)
    _pass("plan_use_elevenlabs_false", plan.use_elevenlabs is False)
    joined = " ".join(
        f"{clip.shot_1.prompt} {clip.shot_2.prompt}" for clip in plan.clips
    ).lower()
    _pass("prompts_no_elevenlabs", "elevenlabs" not in joined and "eleven labs" not in joined)


def test_no_external_music() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=45)
    _pass("plan_use_external_music_false", plan.use_external_music is False)
    joined = " ".join(
        f"{clip.shot_1.prompt} {clip.shot_2.prompt}" for clip in plan.clips
    ).lower()
    _pass("prompts_no_external_music", "external music" not in joined)


def test_continuity_anchors_exist() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=30)
    _pass("clip1_anchor", bool(plan.clips[0].shot_2.continuity_anchor))
    _pass("clip1_next_hint", bool(plan.clips[0].next_clip_reference_hint))


def test_clip_bridge_links_to_next_shot_1() -> None:
    plan = plan_kling_native_audio_content(topic=DRAGON_TOPIC, planned_duration_seconds=30)
    hint = plan.clips[0].next_clip_reference_hint.lower()
    shot_1 = plan.clips[1].shot_1.prompt.lower()
    _pass("clip2_references_bridge", "continuing from" in shot_1 or "same young boy" in shot_1)
    _pass("clip2_mentions_prior_hint_token", any(token in shot_1 for token in hint.split()[:4] if len(token) > 4))


def test_dragon_boy_two_character_prompts() -> None:
    plan = plan_kling_native_audio_content(
        topic=DRAGON_TOPIC,
        planned_duration_seconds=15,
        characters=["young boy", "baby dragon"],
        mood="tender wonder",
    )
    prompt = plan.clips[0].shot_1.prompt.lower()
    _pass("boy_present", "boy" in prompt)
    _pass("dragon_present", "dragon" in prompt)
    _pass("two_characters_in_shot_meta", len(plan.clips[0].shot_1.characters_present) == 2)


def test_router_feeds_planner() -> None:
    route = route_audio_strategy(topic=DRAGON_TOPIC, duration_seconds=30)
    plan = plan_kling_from_audio_route(topic=DRAGON_TOPIC, audio_route=route)
    _pass("router_plan_clip_count", plan.clip_count == 2)
    _pass("router_plan_provider", plan.provider == KLING_PROVIDER_ID)
    _assert_plan_ok(plan, "router_feed")


def test_regression_p0_p1_p2() -> None:
    scripts = (
        "project_brain/validate_kling_native_audio_schema_p0.py",
        "project_brain/validate_kling_native_audio_duration_planner_p1.py",
        "project_brain/validate_kling_native_audio_router_p2.py",
    )
    for script in scripts:
        result = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        _pass(f"regression_{Path(script).stem}", result.returncode == 0, result.stderr.strip() or result.stdout.strip()[-120:])


def main() -> int:
    print("validate_kling_native_audio_content_planner_p3")
    test_15s_one_clip()
    test_30s_two_clips()
    test_45s_three_clips()
    test_shot_1_duration_12s()
    test_shot_2_duration_3s()
    test_shot_prompt_max_512()
    test_native_audio_cues_present()
    test_no_elevenlabs()
    test_no_external_music()
    test_continuity_anchors_exist()
    test_clip_bridge_links_to_next_shot_1()
    test_dragon_boy_two_character_prompts()
    test_router_feeds_planner()
    test_regression_p0_p1_p2()
    print("All Kling Native Audio content planner P3 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
