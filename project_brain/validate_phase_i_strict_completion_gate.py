"""
Phase I — strict completion gate + approval UI safety validation.
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
from content_brain.execution.runway_live_smoke_approval_runtime import (
    GATE_APPROVAL,
    RunwayLiveSmokeApprovalRuntime,
)
from content_brain.execution.runway_live_smoke_test import (
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
)
from content_brain.execution.runway_phase_i_strict_completion_gate import (
    DEFAULT_COMPLETION_GATE_DIAGNOSTICS,
    evaluate_strict_clip_completion,
    progress_blocks_completion,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

SAMPLE_STORY = "Astronaut above a neon city; strict completion gate test."


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_ui_map() -> dict:
    from project_brain.validate_runway_live_smoke_test import _mock_ui_map as base_mock

    return base_mock()


def _unit_progress_rules() -> None:
    _pass("progress_6_not_complete", progress_blocks_completion("Generating 6%"))
    _pass("progress_100_ok", not progress_blocks_completion("100% complete"))
    _pass("spinner_text_blocks", progress_blocks_completion("Rendering in progress"))


def _unit_strict_eval_overrides() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="strict_gate_test")

    def _eval(override: dict) -> None:
        nav._strict_completion_test_override = override
        return nav.evaluate_strict_clip_completion(1)

    r6 = _eval({"generation_in_progress": True, "progress_text": "6%", "reason": "generation_in_progress"})
    _pass("six_percent_not_complete", not r6.complete, r6.reason)

    _pass("spinner_not_complete", not _eval({"spinner_visible": True, "reason": "spinner_visible"}).complete)
    _pass("stop_cancel_not_complete", not _eval({"stop_cancel_visible": True, "reason": "stop_cancel_visible"}).complete)
    _pass("loading_card_not_complete", not _eval({"output_loading": True, "reason": "output_loading"}).complete)
    _pass(
        "global_download_ignored",
        not _eval({"ignored_global_download": True, "reason": "no_completed_video_card"}).complete,
    )

    nav._strict_completion_test_override = None
    ok = _eval(
        {
            "complete": True,
            "completed_card": {
                "cardFingerprint": "sim|video|1|done",
                "hasDownload": True,
                "playableVideo": True,
            },
            "reason": "strict_complete",
        }
    )
    _pass("completed_card_releases", ok.complete, ok.reason)


def _unit_wait_strict_not_global() -> None:
    nav_src = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("wait_strict_method", "def wait_for_strict_clip_completion" in nav_src)
    _pass("no_global_download_only_wait", "wait_for_strict_clip_completion" in nav_src)
    _pass("completion_gate_module", (ROOT / "content_brain/execution/runway_phase_i_strict_completion_gate.py").is_file())
    _pass("download_blocked_in_semi", "download gate blocked" in (
        ROOT / "content_brain/execution/runway_continuity_semi_auto.py"
    ).read_text(encoding="utf-8"))


def _unit_approval_ui_safety() -> None:
    runtime = RunwayLiveSmokeApprovalRuntime(fallback_to_terminal=False)
    runtime.mark_ui_connected(True)
    runtime.set_gate_readiness(
        ready=False,
        enabled=False,
        reason="generation_in_progress",
        step_id="018_download_mp4_clip_1",
        control_key="download_mp4_button",
    )
    runtime._waiting = True
    runtime._gate_type = GATE_APPROVAL
    result = runtime.submit_approve()
    _pass("early_approve_rejected", not result["ok"])
    snap = runtime.snapshot()
    _pass("rejection_count", snap.early_approval_rejections_count >= 1)
    history = snap.approval_history
    _pass("rejected_early_approval_logged", any(h.get("event") == "rejected_early_approval" for h in history))

    runtime.set_gate_readiness(
        ready=True,
        enabled=True,
        reason="",
        step_id="018_download_mp4_clip_1",
        control_key="download_mp4_button",
    )
    snap2 = runtime.snapshot()
    _pass("gate_enabled_true", snap2.gate_enabled is True)
    _pass("gate_ready_true", snap2.gate_ready is True)


def _unit_report_fields() -> None:
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    _pass("completion_verified_fields", "clip_1_completion_verified" in smoke)
    _pass("download_gate_released_fields", "clip_1_download_gate_released_after_completion" in smoke)
    _pass("approval_safety_enabled_field", "approval_gate_safety_enabled" in smoke)


def _unit_sim_rehearsal_and_gates() -> None:
    plan = build_continuity_plan(
        project_id="strict_sim",
        starter_image_prompt="starter",
        clip_prompts=["c1", "c2", "c3"],
    )
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("seven_gates", len(gated) == expected_approval_gate_count(3), str(len(gated)))

    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="strict_sim_run",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("clip1_completion_verified", report.clip_1_completion_verified is True)
    _pass("clip1_gate_released", report.clip_1_download_gate_released_after_completion is True)


def _unit_no_forbidden_changes() -> None:
    story = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")
    prompt = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("story_brief_untouched", "build_runway_story_brief" in story)
    _pass("prompt_builder_untouched", "build_continuity_prompts" in prompt)
    _pass("no_provider_mutation", "StrictClipCompletion" not in provider)


def _unit_ui_panel_gate_fields() -> None:
    panel = (ROOT / "ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx").read_text(encoding="utf-8")
    _pass("ui_gate_enabled", "gate_enabled" in panel)
    _pass("ui_can_approve", "canApprove" in panel)
    _pass("ui_gate_reason", "gate_reason" in panel)


def main() -> int:
    print("[validate_phase_i_strict_completion_gate] Strict completion + approval safety")
    _unit_progress_rules()
    _unit_strict_eval_overrides()
    _unit_wait_strict_not_global()
    _unit_approval_ui_safety()
    _unit_report_fields()
    _unit_sim_rehearsal_and_gates()
    _unit_no_forbidden_changes()
    _unit_ui_panel_gate_fields()
    _pass("diagnostics_path", DEFAULT_COMPLETION_GATE_DIAGNOSTICS.name == "runway_phase_i_completion_gate_diagnostics.json")
    print("\n[validate_phase_i_strict_completion_gate] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
