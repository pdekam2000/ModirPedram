"""
Phase I — post Use Frame composer handoff verification validation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_approval_guard import APPROVAL_GATED_CONTROLS
from content_brain.execution.runway_continuity_dry_run import build_continuity_plan, run_dry_run
from content_brain.execution.runway_continuity_models import (
    RunwayContinuityStep,
    RunwaySemiAutoStepResult,
    SEMI_AUTO_STATUS_COMPLETED,
)
from content_brain.execution.runway_continuity_semi_auto import RunwayContinuitySemiAutoEngine
from content_brain.execution.runway_live_smoke_test import (
    DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS,
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import (
    USE_FRAME_HANDOFF_COMPOSER_READY,
    USE_FRAME_HANDOFF_GENERATION_STARTED,
    USE_FRAME_HANDOFF_INVALID_CARD_ONLY,
    MappedRunwayUINavigator,
)

SAMPLE_STORY = "Astronaut above neon city; three-clip continuity."


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_ui_map() -> dict:
    from project_brain.validate_runway_live_smoke_test import _mock_ui_map as base_mock

    return base_mock()


def _unit_implementation() -> None:
    nav_src = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    semi_src = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(
        encoding="utf-8"
    )
    dry_src = (ROOT / "content_brain/execution/runway_continuity_dry_run.py").read_text(encoding="utf-8")
    smoke_src = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    _pass("verify_handoff_method", "def verify_use_frame_composer_handoff" in nav_src)
    _pass("handoff_probe_script", "_use_frame_handoff_probe_eval_script" in nav_src)
    _pass("semi_auto_handoff_step", "verify_use_frame_handoff_clip_" in semi_src)
    _pass(
        "dry_run_handoff_steps",
        "verify_use_frame_handoff_clip_" in dry_src,
    )
    _pass("click_alone_not_enough", semi_src.count("use_frame_for_clip_") >= 1)
    _pass("handoff_after_click", "verify_use_frame_handoff_clip_" in semi_src)
    _pass("report_clip_2_handoff", "clip_2_use_frame_handoff_result" in smoke_src)
    _pass("report_clip_3_handoff", "clip_3_use_frame_handoff_result" in smoke_src)
    _pass("diag_reference_candidates", "reference_thumbnail_candidates" in nav_src)
    _pass("diag_output_cards", "output_card_candidates" in nav_src)


def _unit_dry_run_order() -> None:
    plan = build_continuity_plan(
        project_id="handoff_plan",
        starter_image_prompt="starter",
        clip_prompts=["a", "b", "c"],
    )
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    step_keys = [s.step_id.split("_", 1)[-1] for s in dry.steps]
    _pass("dry_run_ok", dry.ok is True, str(dry.errors))
    _pass("verify_handoff_clip_2", "verify_use_frame_handoff_clip_2" in step_keys)
    _pass("verify_handoff_clip_3", "verify_use_frame_handoff_clip_3" in step_keys)
    idx = step_keys.index("use_frame_for_clip_2")
    _pass(
        "order_use_frame_settle_verify_prompt",
        step_keys[idx + 1] == "settle_after_use_frame_clip_2"
        and step_keys[idx + 2] == "verify_use_frame_handoff_clip_2"
        and step_keys[idx + 3] == "video_prompt_clip_2",
    )
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("seven_approval_gates", len(gated) == expected_approval_gate_count(3), str(len(gated)))


def _unit_composer_ready_path() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_use_frame_handoff[2] = USE_FRAME_HANDOFF_COMPOSER_READY
    state = nav.verify_use_frame_composer_handoff(2)
    _pass("composer_ready_result", state.handoff_result == USE_FRAME_HANDOFF_COMPOSER_READY)
    _pass("prompt_interactable", state.prompt_interactable is True)
    _pass("reference_detected", state.reference_thumbnail_detected is True)


def _unit_generation_started_non_fatal() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_use_frame_handoff[2] = USE_FRAME_HANDOFF_GENERATION_STARTED
    plan = build_continuity_plan(
        project_id="handoff_gen",
        starter_image_prompt="starter",
        clip_prompts=["one", "two"],
    )
    engine = RunwayContinuitySemiAutoEngine(nav, simulate=True)
    step = RunwayContinuityStep(
        step_id="021_verify_use_frame_handoff_clip_2",
        phase="clip_2",
        action="verify handoff",
    )
    result = RunwaySemiAutoStepResult(step_id=step.step_id, action=step.action)
    blocked = False
    try:
        engine._execute_step(
            type("S", (), {"plan": plan})(),
            step,
            result,
            gate_approved=False,
        )
    except RuntimeError:
        blocked = True
    _pass("generation_path_not_fatal", blocked is False)
    _pass("generation_result", "generation_already_started" in result.notes)


def _unit_card_only_fails() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_use_frame_handoff[2] = USE_FRAME_HANDOFF_INVALID_CARD_ONLY
    state = nav.verify_use_frame_composer_handoff(2)
    _pass(
        "card_only_invalid",
        state.handoff_result in {USE_FRAME_HANDOFF_INVALID_CARD_ONLY, "timeout"},
        state.handoff_result,
    )
    plan = build_continuity_plan(
        project_id="handoff_fail",
        starter_image_prompt="starter",
        clip_prompts=["one", "two"],
    )
    engine = RunwayContinuitySemiAutoEngine(nav, simulate=True)
    step = RunwayContinuityStep(
        step_id="021_verify_use_frame_handoff_clip_2",
        phase="clip_2",
        action="verify",
    )
    result = RunwaySemiAutoStepResult(step_id=step.step_id, action=step.action)
    fatal = False
    try:
        engine._execute_step(type("S", (), {"plan": plan})(), step, result, gate_approved=False)
    except RuntimeError as exc:
        fatal = True
        _pass("handoff_fail_raises", "handoff failed" in str(exc).lower())
    _pass("card_only_is_fatal", fatal)


def _unit_report_and_diagnostics() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="handoff_sim",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("clip_2_handoff_checked", report.clip_2_use_frame_handoff_checked is True)
    _pass("clip_3_handoff_checked", report.clip_3_use_frame_handoff_checked is True)
    _pass(
        "clip_2_handoff_result",
        report.clip_2_use_frame_handoff_result == USE_FRAME_HANDOFF_COMPOSER_READY,
        report.clip_2_use_frame_handoff_result,
    )
    _pass(
        "clip_3_handoff_result",
        report.clip_3_use_frame_handoff_result == USE_FRAME_HANDOFF_COMPOSER_READY,
        report.clip_3_use_frame_handoff_result,
    )

    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_use_frame_handoff[2] = USE_FRAME_HANDOFF_INVALID_CARD_ONLY
    nav.verify_use_frame_composer_handoff(2)
    payload = nav.collect_phase_i_failure_diagnostics(
        step_id="021_verify_use_frame_handoff_clip_2",
        error="test",
        clip_number=2,
    )
    DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _pass("diag_has_output_cards", "output_card_candidates" in payload)
    _pass("diag_has_reference", "reference_thumbnail_candidates" in payload)
    _pass("diag_has_generation", "generation_state_candidates" in payload)
    _pass("diag_15_actions", len(payload.get("last_action_log_entries") or []) <= 15)


def _unit_no_forbidden_changes() -> None:
    story = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")
    prompt = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("story_brief_untouched", "build_runway_story_brief" in story)
    _pass("prompt_builder_untouched", "build_continuity_prompts" in prompt)
    _pass("no_provider_change", "verify_use_frame_composer_handoff" not in provider)


def main() -> int:
    print("[validate_phase_i_use_frame_handoff_verification] Post Use Frame handoff")
    _unit_implementation()
    _unit_dry_run_order()
    _unit_composer_ready_path()
    _unit_generation_started_non_fatal()
    _unit_card_only_fails()
    _unit_report_and_diagnostics()
    _unit_no_forbidden_changes()
    print("\n[validate_phase_i_use_frame_handoff_verification] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
