"""
Phase UAT — Runway routing audit validator.

Confirms UAT Runtime is labeled generic (not Phase I) and Phase I live smoke
route preserves 3-clip continuity plan, 7 gates, and report fields.
No CDP / credit spend required.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_approval_guard import APPROVAL_GATED_CONTROLS
from content_brain.execution.runway_continuity_dry_run import build_continuity_plan, run_dry_run
from content_brain.execution.runway_live_smoke_test import (
    PHASE_I_CLIP_COUNT,
    ROUTE_NAME_PHASE_I,
    RUNTIME_NAME_PHASE_I,
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
)
from content_brain.execution.runway_prompt_builder import build_continuity_prompts
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH
from content_brain.execution.uat_runtime_profile import (
    UAT_APPROVAL_PLAN,
    UAT_IS_PHASE_I_CONTINUITY,
    UAT_ROUTE_NAME,
    UAT_RUNTIME_NAME,
    uat_routing_snapshot,
)

SAMPLE_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_routing_sources() -> None:
    uat_page = (ROOT / "ui/web/src/pages/UatRuntimePage.tsx").read_text(encoding="utf-8")
    uat_labels = (ROOT / "ui/web/src/utils/uatRuntimeLabels.ts").read_text(encoding="utf-8")
    uat_engine = (ROOT / "content_brain/execution/uat_runtime_engine.py").read_text(encoding="utf-8")
    uat_profile = (ROOT / "content_brain/execution/uat_runtime_profile.py").read_text(encoding="utf-8")
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    prompt_builder = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    story_brief = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")

    _pass("uat_runtime_name_constant", UAT_RUNTIME_NAME in uat_profile)
    _pass("uat_route_name_constant", UAT_ROUTE_NAME in uat_profile)
    _pass("uat_not_phase_i_flag", UAT_IS_PHASE_I_CONTINUITY is False)
    _pass("uat_ui_generic_label", "Generic UAT Runtime" in uat_labels)
    _pass("uat_ui_phase_i_warning", "Phase I continuity chaining" in uat_labels)
    _pass("uat_page_shows_warning", "UAT_PHASE_I_ROUTING_WARNING" in uat_page)
    _pass("uat_engine_routing_report", "uat_routing_snapshot" in uat_engine)
    _pass("uat_engine_no_live_smoke_import", "RunwayLiveSmokeRunner" not in uat_engine)
    _pass("phase_i_runtime_name_in_smoke", RUNTIME_NAME_PHASE_I in smoke)
    _pass("phase_i_route_name_in_smoke", ROUTE_NAME_PHASE_I in smoke)
    _pass("no_provider_mutation", "validate_uat_runway_phase_i" not in provider)
    _pass("prompt_builder_intact", "build_continuity_prompts" in prompt_builder)
    _pass("story_brief_builder_intact", "RunwayStoryBriefBuilder" in story_brief)


def _uat_generic_routing_metadata() -> None:
    routing = uat_routing_snapshot(clip_count=2)
    _pass("uat_labeled_generic", routing["runtime_name"] == UAT_RUNTIME_NAME)
    _pass("uat_route_generic", routing["route_name"] == UAT_ROUTE_NAME)
    _pass("uat_is_not_phase_i", routing["is_phase_i_continuity"] is False)
    _pass("uat_no_frame_chain", routing["use_frame_chain"] is False)
    _pass("uat_no_starter_image_flow", routing["use_starter_image"] is False)
    _pass("uat_not_7_gate_plan", routing["approval_plan"] != "phase_i_7_gate")
    _pass("uat_approval_plan_supervised", routing["approval_plan"] == UAT_APPROVAL_PLAN)
    _pass("uat_no_use_frame_after", routing["use_frame_after_clips"] == [])
    _pass("uat_no_story_brief_claim", routing["story_brief_present"] is False)
    _pass("uat_no_false_phase_i_in_notes", "Phase I 3-clip continuity" in " ".join(routing["continuity_notes"]))


def _phase_i_plan_structure() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, project_id="uat_routing_audit", clip_count=3)
    plan = bundle.to_continuity_plan()
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    step_keys = [s.step_id.split("_", 1)[-1] for s in dry.steps]
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]

    _pass("phase_i_clip_count_three", len(plan.clip_prompts) == 3)
    _pass("phase_i_seven_gates", len(gated) == expected_approval_gate_count(3), str(len(gated)))
    _pass("phase_i_starter_image_gate", "image_generate_manual_required" in step_keys)
    _pass("phase_i_use_frame_clip_2", "use_frame_for_clip_2" in step_keys)
    _pass("phase_i_use_frame_clip_3", "use_frame_for_clip_3" in step_keys)
    _pass("phase_i_remove_image", "remove_image_clip_3" in step_keys)


def _phase_i_simulated_runner_report() -> None:
    approvals: list[tuple[str, str]] = []

    def auto_approve(control_key: str, step_id: str, label: str) -> bool:
        approvals.append((control_key, step_id))
        return True

    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="uat_routing_phase_i_sim",
        operator="validator",
        simulate=True,
        clip_count=PHASE_I_CLIP_COUNT,
        approval_callback=auto_approve,
        manual_ack_callback=lambda *_args: True,
    ).run()

    payload = report.to_dict()
    _pass("phase_i_labeled_runtime", report.runtime_name == RUNTIME_NAME_PHASE_I)
    _pass("phase_i_labeled_route", report.route_name == ROUTE_NAME_PHASE_I)
    _pass("phase_i_is_phase_i_flag", report.is_phase_i_continuity is True)
    _pass("phase_i_clip_count_report", report.clip_count == 3)
    _pass("phase_i_seven_approvals", len(approvals) == expected_approval_gate_count(3), str(len(approvals)))
    _pass("phase_i_use_frame_after", report.use_frame_after_clips == [1, 2], str(report.use_frame_after_clips))
    _pass("phase_i_story_brief_present", report.story_brief_present is True)
    _pass("phase_i_starter_prompt_chars", report.starter_prompt_chars > 0, str(report.starter_prompt_chars))
    _pass("phase_i_report_route_field", payload.get("route_name") == ROUTE_NAME_PHASE_I)
    _pass("phase_i_report_is_phase_i", payload.get("is_phase_i_continuity") is True)


def _uat_does_not_use_phase_i_engine() -> None:
    uat_engine = (ROOT / "content_brain/execution/uat_runtime_engine.py").read_text(encoding="utf-8")
    _pass("uat_uses_provider_runtime", "ProviderRuntimeEngine" in uat_engine)
    _pass("uat_uses_content_brief", "ContentBriefOrchestrator" in uat_engine)
    _pass("uat_no_semi_auto_engine", "RunwayContinuitySemiAutoEngine" not in uat_engine)
    _pass("uat_no_build_continuity_prompts", "build_continuity_prompts" not in uat_engine)


def main() -> None:
    print("validate_uat_runway_phase_i_routing")
    _static_routing_sources()
    _uat_generic_routing_metadata()
    _uat_does_not_use_phase_i_engine()
    _phase_i_plan_structure()
    _phase_i_simulated_runner_report()
    print("\nAll UAT / Phase I routing checks passed.")


if __name__ == "__main__":
    main()
