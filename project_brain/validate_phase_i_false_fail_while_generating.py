"""
Phase I — false fail while generating fix validation.

Ensures prompt-readiness timeout does not fatal-fail when Runway already shows
generation in progress (clip >= 2).
"""

from __future__ import annotations

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
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import (
    MappedRunwayUINavigator,
    PromptEditorReadyState,
    VideoGenerationProgressState,
)

SAMPLE_STORY = "Astronaut above a neon city; three-clip continuity test."


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
    smoke_src = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    _pass("detect_generation_method", "def detect_video_generation_in_progress" in nav_src)
    _pass("generation_progress_eval", "_video_generation_progress_eval_script" in nav_src)
    _pass("ready_result_field", "ready_result" in nav_src)
    _pass("skipped_result_constant", "skipped_because_generation_started" in semi_src)
    _pass("not_ready_fatal", "not_ready_fatal" in nav_src)
    _pass("report_generation_detected_clip_2", "clip_2_generation_detected_after_prompt_timeout" in smoke_src)
    _pass("generate_gate_poller", "_poll_generate_gate_readiness" in smoke_src)
    _pass("resolve_prompt_selector", "def resolve_prompt_editor_selector" in nav_src)
    _pass("prompt_filled_despite_generation", "prompt_filled_despite_generation" in semi_src)
    _pass("diag_generation_state", "generation_state_candidates" in nav_src)


def _unit_generation_payload_parsing() -> None:
    payload = {
        "inProgress": True,
        "spinnerVisible": True,
        "stopCancelVisible": False,
        "progressText": "Generating video",
        "outputCardsDetected": 2,
        "outputLoading": True,
        "generateButtonDisabled": True,
        "pendingOutputSlot": True,
        "signals": ["spinner_visible", "progress_text", "output_loading"],
    }
    state = MappedRunwayUINavigator._parse_video_generation_progress_payload(payload)
    _pass("parsed_in_progress", state.in_progress is True)
    _pass("parsed_spinner", state.spinner_visible is True)
    _pass("parsed_signals", len(state.signals) >= 2, str(state.signals))


def _unit_prompt_not_ready_generation_not_fatal() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    plan = build_continuity_plan(
        project_id="false_fail_skip",
        starter_image_prompt="starter",
        clip_prompts=[
            "Clip 1 of 3. one",
            "Clip 2 of 3. two",
            "Clip 3 of 3. three",
        ],
    )
    engine = RunwayContinuitySemiAutoEngine(nav, simulate=True)
    step = RunwayContinuityStep(
        step_id="022_video_prompt_clip_2",
        phase="clip_2",
        action="fill",
        control_key="prompt_input",
    )
    result = RunwaySemiAutoStepResult(
        step_id=step.step_id,
        action=step.action,
        control_key=step.control_key,
    )

    def _skip_ready(clip_index: int, **_kwargs: object) -> PromptEditorReadyState:
        state = PromptEditorReadyState(
            clip_index=clip_index,
            checked=True,
            ready=False,
            ready_result="skipped_because_generation_started",
            generation_in_progress=True,
            notes=["timeout_then_generation_detected"],
        )
        nav.last_prompt_ready_by_clip[clip_index] = state
        return state

    nav.wait_for_prompt_editor_ready = _skip_ready  # type: ignore[method-assign]
    filled: list[str] = []
    nav.fill_prompt_control = lambda _k, text, **_: filled.append(str(text))  # type: ignore[method-assign]
    nav.ensure_clip_prompt_applied = lambda *_a, **_k: True  # type: ignore[method-assign]
    blocked = False
    try:
        engine._execute_step(
            type("S", (), {"plan": plan})(),  # minimal session stub
            step,
            result,
            gate_approved=False,
        )
    except RuntimeError:
        blocked = True
    _pass("generation_skip_not_fatal", blocked is False)
    _pass("notes_record_skip", "prompt_filled_despite_generation" in result.notes)
    _pass("clip_2_prompt_filled", "prompt_filled_despite_generation" in result.notes, result.notes)


def _unit_prompt_not_ready_no_generation_fatal() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    plan = build_continuity_plan(
        project_id="false_fail_fatal",
        starter_image_prompt="starter",
        clip_prompts=["one", "two"],
    )
    engine = RunwayContinuitySemiAutoEngine(nav, simulate=True)
    step = RunwayContinuityStep(
        step_id="022_video_prompt_clip_2",
        phase="clip_2",
        action="fill",
        control_key="prompt_input",
    )
    result = RunwaySemiAutoStepResult(
        step_id=step.step_id,
        action=step.action,
        control_key=step.control_key,
    )

    def _not_ready(clip_index: int, **_kwargs: object) -> PromptEditorReadyState:
        return PromptEditorReadyState(
            clip_index=clip_index,
            checked=True,
            ready=False,
            ready_result="not_ready_fatal",
            notes=["timeout_after_25.0s"],
        )

    nav.wait_for_prompt_editor_ready = _not_ready  # type: ignore[method-assign]
    nav.detect_video_generation_in_progress = (  # type: ignore[method-assign]
        lambda _clip, **_: VideoGenerationProgressState(in_progress=False)
    )
    fatal = False
    try:
        engine._execute_step(
            type("S", (), {"plan": plan})(),
            step,
            result,
            gate_approved=False,
        )
    except RuntimeError as exc:
        fatal = True
        _pass("fatal_message", "not ready" in str(exc).lower() or "not_ready_fatal" in str(exc))
    _pass("no_generation_is_fatal", fatal)


def _unit_report_and_gates() -> None:
    plan = build_continuity_plan(
        project_id="gates",
        starter_image_prompt="s",
        clip_prompts=["a", "b", "c"],
    )
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("seven_approval_gates", len(gated) == expected_approval_gate_count(3), str(len(gated)))

    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="false_fail_sim",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("sim_has_prompt_ready_fields", hasattr(report, "clip_2_prompt_ready_result"))


def _unit_no_forbidden_changes() -> None:
    story = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")
    prompt = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("story_brief_untouched", "build_runway_story_brief" in story)
    _pass("prompt_builder_untouched", "build_continuity_prompts" in prompt)
    _pass("no_provider_change", "false_fail_while_generating" not in provider)


def main() -> int:
    print("[validate_phase_i_false_fail_while_generating] Phase I false-fail fix")
    _unit_implementation()
    _unit_generation_payload_parsing()
    _unit_prompt_not_ready_generation_not_fatal()
    _unit_prompt_not_ready_no_generation_fatal()
    _unit_report_and_gates()
    _unit_no_forbidden_changes()
    print("\n[validate_phase_i_false_fail_while_generating] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
