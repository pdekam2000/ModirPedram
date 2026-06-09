"""
Phase RUNWAY-STARTER-TO-VIDEO-I — 3-clip live continuity validation.

Structural + simulate=True rehearsal by default (no CDP required for PASS).
Optional --live runs real CDP continuity with operator UI approvals.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_approval_guard import APPROVAL_GATED_CONTROLS
from content_brain.execution.runway_continuity_dry_run import build_continuity_plan, run_dry_run
from content_brain.execution.runway_continuity_models import SEMI_AUTO_STATUS_COMPLETED
from content_brain.execution.runway_live_smoke_test import (
    PHASE_I_CLIP_COUNT,
    PHASE_I_VERSION,
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
    render_phase_i_3clip_report_md,
    run_live_smoke_test,
)
from content_brain.execution.runway_prompt_builder import build_continuity_prompts
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH

SAMPLE_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere, "
    "neon teal and amber reflections, dramatic volumetric fog, ultra realistic detail. "
    "Clip 1: rain intensifies as she turns toward the skyline. "
    "Clip 2: she walks along the platform edge with city lights pulsing below. "
    "Clip 3: she reaches a dormant launch cradle and places her gloved hand on its surface."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    semi_auto = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")

    _pass("phase_i_version", f'PHASE_I_VERSION = "{PHASE_I_VERSION}"' in smoke)
    _pass("phase_i_clip_count", f"PHASE_I_CLIP_COUNT = {PHASE_I_CLIP_COUNT}" in smoke)
    _pass("runner_clip_count_param", "clip_count: int" in smoke)
    _pass("expected_approval_gate_count", "def expected_approval_gate_count" in smoke)
    _pass("phase_i_report_md", (ROOT / "project_brain/PHASE_RUNWAY_STARTER_TO_VIDEO_I_3CLIP_LIVE_REPORT.md").is_file())
    _pass("use_frame_in_semi_auto", "use_frame_for_clip_" in semi_auto)
    _pass("remove_image_final_clip", "remove_image_clip_" in semi_auto)
    _pass("no_provider_mutation", "validate_runway_phase_i" not in provider)


def _unit_three_clip_plan() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, project_id="phase_i_plan", clip_count=3)
    plan = bundle.to_continuity_plan()
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)

    step_keys = [s.step_id.split("_", 1)[-1] for s in dry.steps]
    _pass("dry_run_ok", dry.ok is True, str(dry.errors))
    _pass("three_clip_prompts", len(plan.clip_prompts) == 3)
    _pass("use_frame_clip_2", "use_frame_for_clip_2" in step_keys)
    _pass("use_frame_clip_3", "use_frame_for_clip_3" in step_keys)
    _pass("no_use_frame_clip_1", "use_frame_for_clip_1" not in step_keys)
    _pass("final_remove_image", "remove_image_clip_3" in step_keys)
    _pass("no_use_frame_after_final", "use_frame_for_clip_4" not in step_keys)

    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("seven_approval_gates", len(gated) == expected_approval_gate_count(3), str(len(gated)))


def _unit_simulated_three_clip_rehearsal() -> None:
    approvals: list[tuple[str, str]] = []

    def auto_approve(control_key: str, step_id: str, label: str) -> bool:
        approvals.append((control_key, step_id))
        return True

    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="phase_i_sim_rehearsal",
        operator="validator",
        simulate=True,
        clip_count=PHASE_I_CLIP_COUNT,
        approval_callback=auto_approve,
        manual_ack_callback=lambda *_args: True,
    ).run()

    _pass("sim_rehearsal_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("sim_seven_approvals", len(approvals) == expected_approval_gate_count(3), str(approvals))
    _pass("sim_three_generates", report.video_generates_approved_count == 3, str(report.video_generates_approved_count))
    _pass("sim_three_downloads", report.downloads_approved_count == 3, str(report.downloads_approved_count))
    _pass("sim_use_frame_after_1_and_2", report.use_frame_after_clips == [1, 2], str(report.use_frame_after_clips))
    _pass("sim_remove_image", report.remove_image_executed is True)
    _pass("sim_three_clips_completed", report.clips_completed == 3, str(report.clips_completed))
    _pass("sim_use_to_video", report.video_transition_verified is True)
    _pass("sim_report_md", len(render_phase_i_3clip_report_md(report)) > 800)


def _unit_use_frame_only_after_non_final_clips() -> None:
    plan = build_continuity_plan(
        project_id="phase_i_use_frame",
        starter_image_prompt="starter",
        clip_prompts=["clip one", "clip two", "clip three"],
    )
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    step_keys = [s.step_id.split("_", 1)[-1] for s in dry.steps]
    _pass("use_frame_before_clip_2", "use_frame_for_clip_2" in step_keys)
    _pass("use_frame_before_clip_3", "use_frame_for_clip_3" in step_keys)
    idx_2 = step_keys.index("use_frame_for_clip_2")
    idx_3 = step_keys.index("use_frame_for_clip_3")
    idx_final_dl = step_keys.index("final_download_clip_3")
    _pass(
        "verify_handoff_after_use_frame_clip_2",
        step_keys[idx_2 + 1] == "settle_after_use_frame_clip_2"
        and step_keys[idx_2 + 2] == "verify_use_frame_handoff_clip_2"
        and step_keys[idx_2 + 3].startswith("video_prompt_clip_2"),
    )
    _pass(
        "verify_handoff_after_use_frame_clip_3",
        step_keys[idx_3 + 1] == "settle_after_use_frame_clip_3"
        and step_keys[idx_3 + 2] == "verify_use_frame_handoff_clip_3"
        and step_keys[idx_3 + 3].startswith("video_prompt_clip_3"),
    )
    _pass(
        "settle_after_download_clip_1",
        "settle_after_download_clip_1" in step_keys,
    )
    _pass(
        "no_use_frame_after_final_download",
        idx_final_dl == len(step_keys) - 2 or "use_frame" not in step_keys[idx_final_dl + 1 :],
    )


def _unit_live_approval_expectations() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, clip_count=3)
    plan = bundle.to_continuity_plan()
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]

    image_gates = [s for s in gated if s.control_key == "image_generate_button"]
    generate_gates = [s for s in gated if s.control_key == "generate_button"]
    download_gates = [s for s in gated if s.control_key == "download_mp4_button"]

    _pass("one_image_generate_gate", len(image_gates) == 1)
    _pass("three_video_generate_gates", len(generate_gates) == 3)
    _pass("three_download_gates", len(download_gates) == 3)


def main() -> int:
    live = "--live" in sys.argv
    print(f"[validate_runway_phase_i_3clip_live_continuity] {PHASE_I_VERSION}")
    print("[validate_runway_phase_i_3clip_live_continuity] Static")
    _static_checks()
    print("\n[validate_runway_phase_i_3clip_live_continuity] Unit")
    _unit_three_clip_plan()
    _unit_live_approval_expectations()
    _unit_use_frame_only_after_non_final_clips()
    _unit_simulated_three_clip_rehearsal()

    if live:
        print("\n[validate_runway_phase_i_3clip_live_continuity] LIVE (CDP + operator approvals)")
        report = run_live_smoke_test(
            SAMPLE_STORY,
            project_id="phase_i_live",
            operator="operator",
            simulate=False,
            clip_count=PHASE_I_CLIP_COUNT,
        )
        _pass("live_completed", report.ok is True, report.final_status)
        _pass("live_seven_approvals", len(report.approvals_granted) == expected_approval_gate_count(3))
    else:
        print("\n[validate_runway_phase_i_3clip_live_continuity] simulate=True rehearsal PASS (no CDP)")
        print("Live CDP: python project_brain/validate_runway_phase_i_3clip_live_continuity.py --live")

    print("\n[validate_runway_phase_i_3clip_live_continuity] All structural checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
