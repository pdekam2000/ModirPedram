"""
Phase I — Clip 2 workspace transition fix validation.

Ensures post-download/post-use-frame settle steps, prompt editor readiness checks,
stale transition clearing, diagnostics fields, and dry-run plan updates — without
touching StoryBrief, Prompt Builder content, or Provider Router.
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
from content_brain.execution.runway_continuity_models import SEMI_AUTO_STATUS_COMPLETED
from content_brain.execution.runway_live_smoke_test import (
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

SAMPLE_STORY = (
    "A lone astronaut on a rain-soaked platform above a cyberpunk city at night. "
    "Clip 1: rain intensifies. Clip 2: she walks the edge. Clip 3: she touches a launch cradle."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _unit_stale_transition_not_reused() -> None:
    semi = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(
        encoding="utf-8"
    )
    nav = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("clear_stale_transition_method", "clear_stale_video_transition_for_clip" in nav)
    _pass(
        "video_prompt_no_stale_transition_gate",
        "video transition not verified before filling video prompt" not in semi,
    )
    _pass(
        "clip_ge_2_clears_stale",
        "clip_index >= 2" in semi and "clear_stale_video_transition_for_clip" in semi,
    )
    _pass("wait_before_fill", "wait_for_prompt_editor_ready" in semi)


def _unit_settle_and_readiness_steps() -> None:
    plan = build_continuity_plan(
        project_id="clip2_fix",
        starter_image_prompt="starter",
        clip_prompts=["one", "two", "three"],
    )
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    step_keys = [s.step_id.split("_", 1)[-1] for s in dry.steps]
    _pass("dry_run_ok", dry.ok is True, str(dry.errors))
    _pass("post_download_settle_clip_1", "settle_after_download_clip_1" in step_keys)
    _pass("post_download_settle_clip_2", "settle_after_download_clip_2" in step_keys)
    _pass("no_settle_after_final_download", "settle_after_download_clip_3" not in step_keys)
    _pass("post_use_frame_settle_clip_2", "settle_after_use_frame_clip_2" in step_keys)
    _pass("post_use_frame_settle_clip_3", "settle_after_use_frame_clip_3" in step_keys)

    dl1 = step_keys.index("download_mp4_clip_1")
    _pass(
        "download_then_settle_clip_1",
        step_keys[dl1 + 1] == "settle_after_download_clip_1",
    )
    uf2 = step_keys.index("use_frame_for_clip_2")
    _pass(
        "use_frame_then_handoff_verify_clip_2",
        step_keys[uf2 + 1] == "settle_after_use_frame_clip_2"
        and step_keys[uf2 + 2] == "verify_use_frame_handoff_clip_2"
        and step_keys[uf2 + 3].startswith("video_prompt_clip_2"),
    )
    _pass("verify_use_frame_handoff_clip_2", "verify_use_frame_handoff_clip_2" in step_keys)

    nav_src = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("settle_after_download_impl", "def settle_after_download_clip" in nav_src)
    _pass("settle_after_use_frame_impl", "def settle_after_use_frame_clip" in nav_src)
    _pass("wait_for_prompt_editor_ready_impl", "def wait_for_prompt_editor_ready" in nav_src)


def _unit_prompt_readiness_before_clips() -> None:
    semi = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(
        encoding="utf-8"
    )
    _pass("readiness_before_video_prompt", "wait_for_prompt_editor_ready(clip_index)" in semi)
    _pass("readiness_clip_2_path", "video_prompt_clip_" in semi)


def _unit_diagnostics() -> None:
    nav_src = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("diagnostics_clip_number", '"clip_number"' in nav_src)
    _pass("diagnostics_prompt_candidates", "prompt_candidates_found" in nav_src)
    _pass("diagnostics_action_log", "last_action_log_entries" in nav_src)
    _pass("diagnostics_dialogs", "visible_dialogs_modals" in nav_src)

    nav = MappedRunwayUINavigator.from_map(simulate=True)
    payload = nav.collect_phase_i_failure_diagnostics(
        step_id="020_video_prompt_clip_2",
        error="test",
        clip_number=2,
    )
    _pass("diag_has_clip_number", payload.get("clip_number") == 2)
    _pass("diag_has_prompt_candidates", "prompt_candidates_found" in payload)


def _unit_report_fields() -> None:
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    _pass("clip_2_prompt_ready_checked", "clip_2_prompt_ready_checked" in smoke)
    _pass("clip_2_prompt_ready_result", "clip_2_prompt_ready_result" in smoke)
    _pass("clip_3_prompt_ready_checked", "clip_3_prompt_ready_checked" in smoke)
    _pass("clip_3_prompt_ready_result", "clip_3_prompt_ready_result" in smoke)


def _unit_no_forbidden_changes() -> None:
    story = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(
        encoding="utf-8"
    )
    prompt = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("story_brief_unchanged_marker", "build_runway_story_brief" in story)
    _pass("prompt_builder_unchanged_marker", "build_continuity_prompts" in prompt)
    _pass("no_provider_router_in_fix_validator", "clip2_workspace" not in provider)

    plan = build_continuity_plan(
        project_id="gates",
        starter_image_prompt="s",
        clip_prompts=["a", "b", "c"],
    )
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass(
        "approval_gate_count_remains_7",
        len(gated) == expected_approval_gate_count(3),
        str(len(gated)),
    )


def _unit_simulated_rehearsal() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="clip2_fix_sim",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("sim_clip_2_ready_checked", report.clip_2_prompt_ready_checked is True)
    _pass("sim_clip_3_ready_checked", report.clip_3_prompt_ready_checked is True)
    _pass("sim_clip_2_ready_result", report.clip_2_prompt_ready_result == "ready")
    _pass("sim_clip_3_ready_result", report.clip_3_prompt_ready_result == "ready")


def main() -> int:
    print("[validate_phase_i_clip2_workspace_transition_fix] Phase I Clip 2 transition fix")
    _unit_stale_transition_not_reused()
    _unit_settle_and_readiness_steps()
    _unit_prompt_readiness_before_clips()
    _unit_diagnostics()
    _unit_report_fields()
    _unit_no_forbidden_changes()
    _unit_simulated_rehearsal()
    print("\n[validate_phase_i_clip2_workspace_transition_fix] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
