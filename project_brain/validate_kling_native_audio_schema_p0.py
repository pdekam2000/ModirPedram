"""Validate Kling Native Audio schema P0 — duration mapping and plan invariants."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_config import (  # noqa: E402
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    FIRST_FRAME_PRIOR_CLIP,
    FIRST_FRAME_USER_UPLOAD,
    build_continuity_chain_from_plan,
    build_kling_native_audio_plan,
    normalize_kling_duration,
    validate_kling_native_audio_plan,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_15s_one_clip() -> None:
    planned, count, _ = normalize_kling_duration(15)
    _pass("15s_planned", planned == 15)
    _pass("15s_one_clip", count == 1)


def test_30s_two_clips() -> None:
    planned, count, _ = normalize_kling_duration(30)
    _pass("30s_planned", planned == 30)
    _pass("30s_two_clips", count == 2)


def test_45s_three_clips() -> None:
    planned, count, _ = normalize_kling_duration(45)
    _pass("45s_planned", planned == 45)
    _pass("45s_three_clips", count == 3)


def test_60s_four_clips() -> None:
    planned, count, _ = normalize_kling_duration(60)
    _pass("60s_planned", planned == 60)
    _pass("60s_four_clips", count == 4)


def test_40s_rounds_to_45_with_warning() -> None:
    planned, count, warnings = normalize_kling_duration(40)
    _pass("40s_rounds_planned_45", planned == 45, str(planned))
    _pass("40s_rounds_clip_count_3", count == 3)
    _pass("40s_has_warning", any("40" in w and "45" in w for w in warnings), str(warnings))


def test_every_clip_shot_1_12s() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=60)
    _pass("shot_1_all_12s", all(c.shot_1.duration_seconds == SHOT_1_DURATION_SECONDS == 12 for c in plan.clips))


def test_every_clip_shot_2_3s() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=60)
    _pass("shot_2_all_3s", all(c.shot_2.duration_seconds == SHOT_2_DURATION_SECONDS == 3 for c in plan.clips))


def test_plan_disables_elevenlabs() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=30)
    _pass("use_elevenlabs_false", plan.use_elevenlabs is False)


def test_plan_disables_external_music() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=30)
    _pass("use_external_music_false", plan.use_external_music is False)


def test_native_audio_required_true() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=30)
    _pass("native_audio_required", plan.native_audio_required is True)


def test_subtitles_required() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=30)
    _pass("subtitle_required", plan.subtitle_required is True)


def test_continuity_chain_clip_n_to_n_plus_1() -> None:
    plan = build_kling_native_audio_plan(requested_duration_seconds=45, topic="dragon benchmark")
    chain = build_continuity_chain_from_plan(plan, run_id="test_run_001")
    _pass("chain_clip_count", chain.clip_count == 3)
    _pass("chain_two_links", len(chain.links) == 2)
    _pass("link_1_to_2", chain.links[0].from_clip_index == 1 and chain.links[0].to_clip_index == 2)
    _pass("link_2_to_3", chain.links[1].from_clip_index == 2 and chain.links[1].to_clip_index == 3)
    _pass("frame_source_clip1_upload", chain.frame_sources[0].source == FIRST_FRAME_USER_UPLOAD)
    _pass("frame_source_clip2_prior", chain.frame_sources[1].source == FIRST_FRAME_PRIOR_CLIP)
    _pass("frame_source_clip2_prior_index", chain.frame_sources[1].prior_clip_index == 1)
    ok, errors = validate_kling_native_audio_plan(plan)
    _pass("plan_validate_ok", ok, str(errors))


def main() -> int:
    print("validate_kling_native_audio_schema_p0")
    test_15s_one_clip()
    test_30s_two_clips()
    test_45s_three_clips()
    test_60s_four_clips()
    test_40s_rounds_to_45_with_warning()
    test_every_clip_shot_1_12s()
    test_every_clip_shot_2_3s()
    test_plan_disables_elevenlabs()
    test_plan_disables_external_music()
    test_native_audio_required_true()
    test_subtitles_required()
    test_continuity_chain_clip_n_to_n_plus_1()
    print("All Kling Native Audio schema P0 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
