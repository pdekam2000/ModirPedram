"""
Phase I — generic last-frame Use Frame validation (any clip_count > 1).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_dry_run import build_continuity_plan, run_dry_run
from content_brain.execution.runway_continuity_models import SEMI_AUTO_STATUS_COMPLETED
from content_brain.execution.runway_live_smoke_test import (
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
)
from content_brain.execution.runway_phase_i_last_frame_use_frame import (
    USE_FRAME_SOURCE_LAST_SAFE,
    compute_last_safe_seek_seconds,
    parse_duration_seconds,
    prepare_last_frame_use_frame_for_clip,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

SAMPLE_STORY = "Astronaut continuity chain; last-frame Use Frame generic test."


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_ui_map() -> dict:
    from project_brain.validate_runway_live_smoke_test import _mock_ui_map as base_mock

    return base_mock()


def _unit_seek_math() -> None:
    seek_10, strat_10 = compute_last_safe_seek_seconds(10.0)
    _pass("seek_10s_near_end", 8.5 <= seek_10 <= 9.5, f"{seek_10} ({strat_10})")
    seek_5, _ = compute_last_safe_seek_seconds(5.0)
    _pass("seek_5s_near_end", 4.0 <= seek_5 <= 4.8, str(seek_5))
    _pass("parse_10s", parse_duration_seconds("10s") == 10.0)


def _unit_no_hardcoded_clip23() -> None:
    mod = (ROOT / "content_brain/execution/runway_phase_i_last_frame_use_frame.py").read_text(
        encoding="utf-8"
    )
    semi = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(
        encoding="utf-8"
    )
    _pass("generic_prepare_function", "prepare_last_frame_use_frame_for_clip" in mod)
    _pass("semi_uses_prepare", "prepare_last_frame_use_frame_for_clip" in semi)
    _pass("no_hardcoded_clip_2_only", "clip_index == 2" not in semi.split("use_frame_for_clip")[1][:400])
    _pass("target_minus_one", "target - 1" in mod or "clip_index - 1" in mod)


def _unit_sim_use_frame_chain() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="last_frame_test")

    for previous in (1, 2, 3, 4):
        nav.phase_i_artifact_tracker().simulate_add_card(
            card_type="video",
            prompt_text=f"clip {previous}",
            buttons=["Download MP4", "Use Frame"],
        )
        nav.phase_i_artifact_tracker().assign_new_card(
            nav.phase_i_artifact_tracker().clip_video_role(previous),
            prefer_type="video",
        )

    for target in (2, 3, 4, 5):
        result = prepare_last_frame_use_frame_for_clip(nav, target)
        _pass(
            f"clip_{target}_seeked_from_{target - 1}",
            result.previous_clip_seeked_to_last_frame
            and result.use_frame_source_clip == target - 1,
            result.use_frame_source,
        )
        _pass(f"clip_{target}_last_safe_source", result.use_frame_source == USE_FRAME_SOURCE_LAST_SAFE)
        _pass(f"clip_{target}_use_frame_clicked", result.use_frame_clicked is True)


def _unit_starter_not_source_for_clip2() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="starter_guard")
    tracker = nav.phase_i_artifact_tracker()
    starter_fp = tracker.simulate_add_card(card_type="image", prompt_text="starter")
    tracker.assignments["starter_image_card"] = tracker._card_from_raw(
        tracker._simulated_cards[0],
        role="starter_image_card",
    )
    tracker.simulate_add_card(card_type="video", prompt_text="clip 1", buttons=["Use Frame"])
    tracker.assign_new_card(tracker.clip_video_role(1), prefer_type="video")
    result = prepare_last_frame_use_frame_for_clip(nav, 2)
    clip1 = tracker.get_assigned(tracker.clip_video_role(1))
    _pass("clip2_source_is_clip1", result.use_frame_source_clip == 1)
    _pass("starter_not_clip1_fp", clip1 is not None and clip1.card_fingerprint != starter_fp)


def _unit_use_frame_below_video_scope() -> None:
    tracker_src = (ROOT / "content_brain/execution/runway_phase_i_artifact_tracker.py").read_text(
        encoding="utf-8"
    )
    _pass("expand_card_control_scope", "__expandCardControlScope" in tracker_src)
    _pass("below_video_band", "__nodesBelowVideoBand" in tracker_src)
    _pass("apps_menu_use_frame_fallback", "__clickAppsMenuUseFrame" in tracker_src)
    _pass("click_prefers_button", "clickables" in tracker_src and "score(a)" in tracker_src)


def _unit_plan_scales_clip_count() -> None:
    for clip_count in (3, 5):
        plan = build_continuity_plan(
            project_id=f"plan_{clip_count}",
            starter_image_prompt="starter",
            clip_prompts=[f"c{i}" for i in range(1, clip_count + 1)],
        )
        dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
        use_steps = sorted(
            s.step_id.split("_", 1)[-1]
            for s in dry.steps
            if "use_frame_for_clip_" in s.step_id
        )
        expected = [f"use_frame_for_clip_{i}" for i in range(2, clip_count + 1)]
        _pass(f"use_frame_steps_{clip_count}", use_steps == expected, str(use_steps))
        gates = [s for s in dry.steps if s.requires_operator_approval]
        _pass(
            f"approval_gates_{clip_count}",
            len(gates) == expected_approval_gate_count(clip_count),
            str(len(gates)),
        )


def _unit_sim_rehearsal_clip3() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="last_frame_sim_3",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim3_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    entry2 = report.use_frame_last_frame_by_clip.get("2") or {}
    entry3 = report.use_frame_last_frame_by_clip.get("3") or {}
    _pass("clip2_seeked", bool(entry2.get("previous_clip_seeked_to_last_frame")))
    _pass("clip3_seeked", bool(entry3.get("previous_clip_seeked_to_last_frame")))
    _pass("clip2_source_clip1", entry2.get("use_frame_source_clip") == 1)
    _pass("clip3_source_clip2", entry3.get("use_frame_source_clip") == 2)
    from content_brain.execution.runway_live_smoke_test import (
        flatten_use_frame_last_frame_report_fields,
    )

    flat = flatten_use_frame_last_frame_report_fields(report.use_frame_last_frame_by_clip)
    _pass("flat_clip2_fields", flat.get("clip_2_use_frame_source") == USE_FRAME_SOURCE_LAST_SAFE)


def _unit_fallback_diagnostic() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="fallback_diag")
    nav._strict_completion_test_override = {
        "generation_in_progress": True,
        "progress_text": "50%",
        "reason": "generation_in_progress",
    }
    result = prepare_last_frame_use_frame_for_clip(nav, 2, allow_first_frame_fallback=False)
    _pass("incomplete_blocks", not result.use_frame_clicked)
    _pass("fallback_not_auto", not result.first_frame_fallback_used)


def _unit_no_forbidden_changes() -> None:
    story = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")
    prompt = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("story_brief_untouched", "build_runway_story_brief" in story)
    _pass("prompt_builder_untouched", "build_continuity_prompts" in prompt)
    _pass("no_provider_mutation", "prepare_last_frame_use_frame" not in provider)


def main() -> int:
    print("[validate_phase_i_last_frame_use_frame] Generic last-frame Use Frame")
    _unit_seek_math()
    _unit_no_hardcoded_clip23()
    _unit_use_frame_below_video_scope()
    _unit_sim_use_frame_chain()
    _unit_starter_not_source_for_clip2()
    _unit_plan_scales_clip_count()
    _unit_sim_rehearsal_clip3()
    _unit_fallback_diagnostic()
    _unit_no_forbidden_changes()
    print("\n[validate_phase_i_last_frame_use_frame] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
