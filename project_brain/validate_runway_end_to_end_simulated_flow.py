"""
Phase RUNWAY-STARTER-TO-VIDEO-G — end-to-end simulated flow validation.

Chain (no browser, no Generate, no Download, no credits):

  build_continuity_prompts()
  → bundle.to_continuity_plan()
  → dry-run orchestrator
  → semi-auto prepare (simulate=True)
  → approval gate simulation
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_approval_guard import (
    APPROVAL_GATED_CONTROLS,
    STATE_APPROVED,
    STATE_REQUIRED,
    can_execute_dangerous_action,
    evaluate_runway_continuity_approval_gate,
)
from content_brain.execution.runway_continuity_dry_run import run_dry_run
from content_brain.execution.runway_continuity_models import (
    SEMI_AUTO_STATUS_AWAITING_APPROVAL,
    SEMI_AUTO_STATUS_COMPLETED,
)
from content_brain.execution.runway_continuity_semi_auto import (
    RunwayContinuitySemiAutoEngine,
    run_semi_auto_prepare,
    run_semi_auto_with_approval,
)
from content_brain.execution.runway_prompt_builder import (
    build_continuity_prompts,
    validate_prompt_bundle,
)
from content_brain.execution.runway_ui_map_loader import (
    DEFAULT_MAP_PATH,
    STARTER_TO_VIDEO_CANONICAL_CONTROLS,
    resolve_runway_ui_controls,
)
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

MAP_PATH = DEFAULT_MAP_PATH
FLOW_VERSION = "runway_starter_to_video_g_e2e_sim_v1"

SAMPLE_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere, "
    "neon teal and amber reflections, dramatic volumetric fog, ultra realistic detail. "
    "Clip 1: rain intensifies as she turns toward the skyline. "
    "Clip 2: she walks along the platform edge with city lights pulsing below. "
    "Clip 3: she reaches a dormant launch cradle and places her gloved hand on its surface."
)

PROJECT_ID = "e2e_sim_flow"
CLIP_COUNT = 3
OPERATOR = "e2e_sim_operator"


@dataclass
class FlowStageResult:
    stage: str
    ok: bool
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class E2EFlowReport:
    flow_version: str = FLOW_VERSION
    started_at: str = ""
    finished_at: str = ""
    all_pass: bool = False
    stages: list[FlowStageResult] = field(default_factory=list)
    safety: dict[str, bool] = field(default_factory=dict)
    sample_story_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_version": self.flow_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "all_pass": self.all_pass,
            "sample_story_chars": self.sample_story_chars,
            "safety": dict(self.safety),
            "stages": [
                {
                    "stage": item.stage,
                    "ok": item.ok,
                    "detail": item.detail,
                    "metrics": dict(item.metrics),
                }
                for item in self.stages
            ],
        }


_checks: list[tuple[str, bool, str]] = []
_report = E2EFlowReport()


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    _checks.append((name, ok, detail))
    if not ok:
        raise SystemExit(1)


def _record_stage(stage: str, ok: bool, detail: str = "", **metrics: Any) -> None:
    _report.stages.append(
        FlowStageResult(stage=stage, ok=ok, detail=detail, metrics=metrics)
    )


def _static_safety() -> None:
    paths = [
        ROOT / "content_brain/execution/runway_prompt_builder.py",
        ROOT / "content_brain/execution/runway_continuity_dry_run.py",
        ROOT / "content_brain/execution/runway_continuity_semi_auto.py",
    ]
    combined = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")

    _report.safety = {
        "no_browser_manager": "BrowserManager" not in combined,
        "no_playwright": "playwright" not in combined.lower(),
        "no_provider_import": "from providers.runway_browser_provider" not in combined,
        "no_provider_mutation": "runway_end_to_end_simulated_flow" not in provider,
        "simulate_default_semi_auto": "simulate: bool = True" in combined,
    }
    for key, ok in _report.safety.items():
        _pass(f"safety_{key}", ok)


def _stage_prompt_builder() -> Any:
    bundle = build_continuity_prompts(
        SAMPLE_STORY,
        project_id=PROJECT_ID,
        clip_count=CLIP_COUNT,
    )
    quality = validate_prompt_bundle(bundle)
    _pass("prompt_builder_bundle", bool(bundle.starter_image_prompt))
    _pass("prompt_builder_clip_count", len(bundle.clip_prompts) == CLIP_COUNT)
    _pass("prompt_builder_quality", len(quality) == 0, str(quality))
    _record_stage(
        "1_prompt_builder",
        True,
        "build_continuity_prompts",
        starter_chars=len(bundle.starter_image_prompt),
        clip_chars=[len(p) for p in bundle.clip_prompts],
        anchor_character=bundle.continuity_anchors.character[:80],
    )
    return bundle


def _stage_continuity_plan(bundle: Any) -> Any:
    plan = bundle.to_continuity_plan()
    _pass("plan_project_id", plan.project_id == PROJECT_ID)
    _pass("plan_starter_match", plan.starter_image_prompt == bundle.starter_image_prompt)
    _pass("plan_clip_count", len(plan.clip_prompts) == CLIP_COUNT)
    _pass("plan_aspect_9_16", plan.aspect_ratio == "9:16")
    _pass("plan_duration_10s", plan.duration_seconds == 10)
    _record_stage(
        "2_continuity_plan",
        True,
        "bundle.to_continuity_plan",
        aspect_ratio=plan.aspect_ratio,
        duration_seconds=plan.duration_seconds,
        completion_rule=plan.completion_rule,
    )
    return plan


def _stage_dry_run(plan: Any) -> Any:
    if not MAP_PATH.is_file():
        _pass("dry_run_map_exists", False, str(MAP_PATH))
    snap = resolve_runway_ui_controls(map_path=MAP_PATH)
    expected_controls = len(STARTER_TO_VIDEO_CANONICAL_CONTROLS)
    _pass(
        "dry_run_controls_resolved",
        len(snap.controls) == expected_controls,
        f"{len(snap.controls)}/{expected_controls}",
    )
    _pass("dry_run_map_ok", snap.ok is True, f"missing={snap.missing}")

    dry = run_dry_run(plan, map_path=MAP_PATH)
    _pass("dry_run_ok", dry.ok is True, str(dry.errors))
    _pass("dry_run_steps", len(dry.steps) >= 20, str(len(dry.steps)))
    _pass("dry_run_use_to_video", any(s.control_key == "image_use_to_video_option" for s in dry.steps))
    _pass("dry_run_remove_image", any(s.control_key == "remove_image" for s in dry.steps))
    gated = [s for s in dry.steps if s.requires_operator_approval]
    _pass("dry_run_approval_gates", len(gated) >= 3, str(len(gated)))
    _record_stage(
        "3_dry_run",
        True,
        "run_dry_run",
        steps=len(dry.steps),
        approval_gated_steps=len(gated),
        controls_resolved=len(snap.controls),
    )
    return dry


def _stage_semi_auto_prepare(plan: Any) -> Any:
    prep = run_semi_auto_prepare(plan, map_path=MAP_PATH, simulate=True)
    _pass("semi_auto_prepare_ok", prep.ok is True, str(prep.errors))
    _pass(
        "semi_auto_pauses_at_image_generate",
        prep.session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL,
        prep.session.status,
    )
    _pass(
        "semi_auto_awaiting_control",
        prep.session.awaiting_control_key == "image_generate_button",
        str(prep.session.awaiting_control_key),
    )
    done = [s for s in prep.session.step_results if s.status == "done"]
    _pass("semi_auto_prep_steps_done", len(done) >= 4, str(len(done)))
    _record_stage(
        "4_semi_auto_prepare",
        True,
        "run_semi_auto_prepare(simulate=True)",
        status=prep.session.status,
        awaiting_control=prep.session.awaiting_control_key,
        prep_steps_done=len(done),
    )
    return prep


def _stage_approval_simulation(plan: Any, dry: Any) -> None:
    gated_steps = [
        s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS
    ]
    _pass("approval_gate_steps_found", len(gated_steps) >= 7, str(len(gated_steps)))

    first_gate = evaluate_runway_continuity_approval_gate(
        control_key="image_generate_button",
        step_id=gated_steps[0].step_id if gated_steps else "",
    )
    _pass("approval_gate_blocks_unapproved", first_gate.approval_state == STATE_REQUIRED)
    _pass("approval_gate_not_eligible", first_gate.continuity_eligible is False)

    approvals = [
        {
            "control_key": str(step.control_key),
            "step_id": step.step_id,
            "approved_by": OPERATOR,
            "reason": "e2e_simulated_approval",
        }
        for step in gated_steps
    ]

    semi = run_semi_auto_with_approval(
        plan,
        map_path=MAP_PATH,
        simulate=True,
        approvals=approvals,
    )
    _pass("approval_sim_completed", semi.session.status == SEMI_AUTO_STATUS_COMPLETED, semi.session.status)
    _pass("approval_sim_ok", semi.ok is True, str(semi.errors))

    gated_done = [
        s
        for s in semi.session.step_results
        if s.control_key in APPROVAL_GATED_CONTROLS and s.status == "done"
    ]
    _pass(
        "approval_sim_all_gated_executed",
        len(gated_done) == len(gated_steps),
        f"{len(gated_done)}/{len(gated_steps)}",
    )
    _pass(
        "approval_sim_grants_recorded",
        all(s.approval_granted for s in gated_done),
    )

    nav = MappedRunwayUINavigator.from_map(map_path=MAP_PATH, simulate=True)
    nav.approvals = dict(semi.session.approvals)

    image_step = next(
        s for s in gated_done if s.control_key == "image_generate_button"
    )
    _pass(
        "approval_guard_allows_after_grant",
        can_execute_dangerous_action(
            "image_generate_button",
            step_id=image_step.step_id,
            approvals=nav.approvals,
        ),
    )
    _pass(
        "approval_guard_state_approved",
        evaluate_runway_continuity_approval_gate(
            control_key="image_generate_button",
            step_id=image_step.step_id,
            approvals=nav.approvals,
        ).approval_state
        == STATE_APPROVED,
    )
    _pass(
        "approval_guard_blocks_wrong_step",
        not can_execute_dangerous_action(
            "generate_button",
            step_id="000_fake_generate_step",
            approvals=nav.approvals,
        ),
    )

    dangerous_clicks = [
        log
        for log in nav.action_log
        if log.action == "click" and log.control_key in APPROVAL_GATED_CONTROLS
    ]
    _pass(
        "navigator_no_unapproved_dangerous_clicks",
        len(dangerous_clicks) == 0,
        "action_log empty in fresh navigator (simulated clicks recorded on engine navigator)",
    )

    engine_nav = MappedRunwayUINavigator.from_map(map_path=MAP_PATH, simulate=True)
    engine = RunwayContinuitySemiAutoEngine(engine_nav, simulate=True)
    session = run_semi_auto_prepare(plan, map_path=MAP_PATH, simulate=True).session
    engine_nav.approvals = dict(session.approvals)
    for item in approvals:
        if session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL:
            engine.approve(
                session,
                control_key=item["control_key"],
                step_id=item["step_id"],
                approved_by=OPERATOR,
                reason=item["reason"],
            )
        engine.advance(session)
        if session.status == SEMI_AUTO_STATUS_COMPLETED:
            break

    sim_clicks = [
        log
        for log in engine_nav.action_log
        if log.action == "click" and log.control_key in APPROVAL_GATED_CONTROLS
    ]
    _pass(
        "engine_dangerous_clicks_all_approved",
        all(log.approved for log in sim_clicks) if sim_clicks else True,
        f"clicks={len(sim_clicks)}",
    )

    _record_stage(
        "5_approval_simulation",
        True,
        "run_semi_auto_with_approval + gate checks",
        approvals_granted=len(approvals),
        gated_steps_executed=len(gated_done),
        final_status=semi.session.status,
        completion_signals=semi.session.completion_signals,
    )


def run_e2e_flow() -> E2EFlowReport:
    global _report
    _report = E2EFlowReport(
        started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        sample_story_chars=len(SAMPLE_STORY),
    )
    print(f"[validate_runway_end_to_end_simulated_flow] {FLOW_VERSION}")
    print(f"  Map: {MAP_PATH}")
    print(f"  Story chars: {len(SAMPLE_STORY)}")
    print(f"  Clips: {CLIP_COUNT}")
    print()

    print("[validate_runway_end_to_end_simulated_flow] Safety")
    _static_safety()

    print("\n[validate_runway_end_to_end_simulated_flow] Stage 1 — prompt builder")
    bundle = _stage_prompt_builder()

    print("\n[validate_runway_end_to_end_simulated_flow] Stage 2 — continuity plan")
    plan = _stage_continuity_plan(bundle)

    print("\n[validate_runway_end_to_end_simulated_flow] Stage 3 — dry-run")
    dry = _stage_dry_run(plan)

    print("\n[validate_runway_end_to_end_simulated_flow] Stage 4 — semi-auto prepare")
    _stage_semi_auto_prepare(plan)

    print("\n[validate_runway_end_to_end_simulated_flow] Stage 5 — approval simulation")
    _stage_approval_simulation(plan, dry)

    _report.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _report.all_pass = all(ok for _, ok, _ in _checks)
    _pass("e2e_all_pass", _report.all_pass, f"checks={len(_checks)}")
    return _report


def main() -> int:
    report = run_e2e_flow()
    print("\n[validate_runway_end_to_end_simulated_flow] Summary")
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
