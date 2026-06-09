"""
Phase RUNWAY-STARTER-TO-VIDEO-E — semi-automation validation.

Uses simulate mode by default (no browser, no real Generate/Download).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_approval_guard import (
    APPROVAL_GATED_CONTROLS,
    STATE_REQUIRED,
    can_execute_dangerous_action,
    evaluate_runway_continuity_approval_gate,
    grant_continuity_approval,
)
from content_brain.execution.runway_continuity_dry_run import build_continuity_plan, run_dry_run
from content_brain.execution.runway_continuity_semi_auto import (
    SAFETY_GATES,
    build_semi_auto_session,
    run_semi_auto_prepare,
    run_semi_auto_with_approval,
)
from content_brain.execution.runway_continuity_models import (
    SEMI_AUTO_STATUS_AWAITING_APPROVAL,
    SEMI_AUTO_STATUS_COMPLETED,
)
from content_brain.execution.runway_ui_map_loader import (
    DEFAULT_MAP_PATH,
    STARTER_TO_VIDEO_CANONICAL_CONTROLS,
    resolve_runway_ui_controls,
)
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator
from project_brain.validate_runway_starter_to_video_dry_run import _good_control, _mock_ui_map

MAP_PATH = DEFAULT_MAP_PATH


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    paths = {
        "approval_guard": ROOT / "content_brain/execution/runway_continuity_approval_guard.py",
        "navigator": ROOT / "content_brain/execution/runway_ui_navigator.py",
        "semi_auto": ROOT / "content_brain/execution/runway_continuity_semi_auto.py",
    }
    for name, path in paths.items():
        _pass(f"{name}_exists", path.is_file())

    semi_auto = paths["semi_auto"].read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("no_provider_import", "from providers.runway_browser_provider" not in semi_auto)
    _pass("provider_untouched", "runway_continuity_semi_auto" not in provider)
    _pass("approval_gates_present", "no_autonomous_generate" in semi_auto)
    _pass("approval_gates_download", "no_autonomous_download" in semi_auto)
    _pass("dangerous_controls_gated", all(c in semi_auto for c in APPROVAL_GATED_CONTROLS))


def _unit_approval_blocks_without_grant() -> None:
    gate = evaluate_runway_continuity_approval_gate(
        control_key="generate_button",
        step_id="012_video_generate_manual_required_clip_1",
    )
    _pass("generate_requires_approval", gate.approval_state == STATE_REQUIRED)
    _pass("generate_blocked", not gate.continuity_eligible)
    _pass("cannot_execute_unapproved", not can_execute_dangerous_action("generate_button"))


def _unit_approval_grants_execute() -> None:
    approvals = grant_continuity_approval(
        control_key="download_mp4_button",
        step_id="014_download_mp4_clip_1",
        approved_by="operator",
        reason="test",
    )
    _pass("download_approved", can_execute_dangerous_action(
        "download_mp4_button",
        step_id="014_download_mp4_clip_1",
        approvals=approvals,
    ))


def _unit_navigator_blocks_dangerous_click() -> None:
    nav = MappedRunwayUINavigator.from_map(ui_map=_mock_ui_map(), simulate=True)
    blocked = False
    try:
        nav.click_control("generate_button")
    except PermissionError:
        blocked = True
    _pass("navigator_blocks_generate", blocked)


def _unit_prepare_pauses_before_image_generate() -> None:
    plan = build_continuity_plan(
        project_id="pause_test",
        starter_image_prompt="Starter prompt for semi-auto.",
        clip_prompts=["Clip 1"],
    )
    result = run_semi_auto_prepare(plan, ui_map=_mock_ui_map(), simulate=True)
    _pass("prepare_ok", result.ok)
    _pass("awaiting_approval", result.session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL)
    _pass("awaiting_image_generate", result.session.awaiting_control_key == "image_generate_button")
    done_steps = [s for s in result.session.step_results if s.status == "done"]
    _pass("auto_prep_ran", len(done_steps) >= 4, f"done={len(done_steps)}")


def _unit_simulated_full_three_clip_flow() -> None:
    plan = build_continuity_plan(
        project_id="semi_auto_three",
        starter_image_prompt="Vertical neon portrait starter.",
        clip_prompts=["Clip 1", "Clip 2", "Clip 3"],
    )
    approvals = []
    for step in build_semi_auto_session(plan, ui_map=_mock_ui_map()).steps:
        if step.control_key in APPROVAL_GATED_CONTROLS:
            approvals.append(
                {
                    "control_key": step.control_key,
                    "step_id": step.step_id,
                    "approved_by": "operator",
                }
            )
    result = run_semi_auto_with_approval(
        plan,
        ui_map=_mock_ui_map(),
        simulate=True,
        approvals=approvals,
    )
    _pass("three_clip_completed", result.session.status == SEMI_AUTO_STATUS_COMPLETED, result.session.status)
    gated_done = [
        s
        for s in result.session.step_results
        if s.control_key in APPROVAL_GATED_CONTROLS and s.status == "done"
    ]
    _pass("dangerous_steps_had_approval", all(s.approval_granted for s in gated_done), f"count={len(gated_done)}")


def _unit_completion_wait_simulated() -> None:
    nav = MappedRunwayUINavigator.from_map(ui_map=_mock_ui_map(), simulate=True)
    signals = nav.wait_for_completion_signal(max_wait_minutes=1)
    _pass("completion_signal", "download_mp4_button" in signals or "use_frame_button" in signals)


def _unit_safety_gates() -> None:
    _pass("safety_gate_count", len(SAFETY_GATES) >= 6)
    _pass("no_autonomous_generate_gate", "no_autonomous_generate" in SAFETY_GATES)


def validate_live_map() -> int:
    if not MAP_PATH.is_file():
        print(f"[validate_runway_starter_to_video_semi_auto] Missing map: {MAP_PATH}")
        return 1

    snap = resolve_runway_ui_controls(map_path=MAP_PATH)
    print("\n[validate_runway_starter_to_video_semi_auto] Live map")
    print(f"  Controls: {len(snap.controls)}/{len(STARTER_TO_VIDEO_CANONICAL_CONTROLS)}")
    print(f"  Missing: {snap.missing or '(none)'}")
    print(f"  image_quality_menu: {'yes' if 'image_quality_menu' in snap.controls else 'NO'}")
    print(f"  image_quality_1k: {'yes' if 'image_quality_1k' in snap.controls else 'NO'}")
    print(f"  image_quality_2k: {'yes' if 'image_quality_2k' in snap.controls else 'NO'}")
    print(f"  image_quality_4k: {'yes' if 'image_quality_4k' in snap.controls else 'NO'}")
    print(f"  image_count_menu: {'yes' if 'image_count_menu' in snap.controls else 'NO'}")
    print(f"  image_count_1: {'yes' if 'image_count_1' in snap.controls else 'NO'}")
    print(f"  image_count_4: {'yes' if 'image_count_4' in snap.controls else 'NO'}")

    dry = run_dry_run(
        build_continuity_plan(
            project_id="live",
            starter_image_prompt="Live map starter.",
            clip_prompts=["A", "B"],
        ),
        map_path=MAP_PATH,
    )
    _pass("live_dry_run_ok", dry.ok is True, str(dry.errors))

    prep = run_semi_auto_prepare(
        build_continuity_plan(
            project_id="live_prep",
            starter_image_prompt="Live prep starter.",
            clip_prompts=["Clip 1"],
        ),
        map_path=MAP_PATH,
        simulate=True,
    )
    _pass("live_prepare_ok", prep.ok)
    _pass("live_pauses_at_generate", prep.session.awaiting_control_key == "image_generate_button")
    return 0


def main() -> int:
    print("[validate_runway_starter_to_video_semi_auto] Unit checks")
    _static_checks()
    _unit_approval_blocks_without_grant()
    _unit_approval_grants_execute()
    _unit_navigator_blocks_dangerous_click()
    _unit_prepare_pauses_before_image_generate()
    _unit_completion_wait_simulated()
    _unit_safety_gates()
    _unit_simulated_full_three_clip_flow()

    print("\n[validate_runway_starter_to_video_semi_auto] Live map")
    return validate_live_map()


if __name__ == "__main__":
    raise SystemExit(main())
