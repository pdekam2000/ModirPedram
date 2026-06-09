"""
Phase I — FULL_AUTO execution mode validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_auto_execution_controller import AUTO_BRIDGE_VERSION
from content_brain.execution.runway_execution_mode import (
    DEFAULT_LIVE_SMOKE_EXECUTION_MODE,
    EXECUTION_MODE_FULL_AUTO,
    EXECUTION_MODE_MANUAL,
    requires_operator_approval,
)
from content_brain.execution.runway_continuity_models import SEMI_AUTO_STATUS_COMPLETED
from content_brain.execution.runway_live_smoke_test import RunwayLiveSmokeRunner, run_live_smoke_test


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _unit_modules() -> None:
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content_brain/execution/runway_live_smoke_approval_runtime.py").read_text(encoding="utf-8")
    panel = (ROOT / "ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx").read_text(encoding="utf-8")
    _pass("default_full_auto", DEFAULT_LIVE_SMOKE_EXECUTION_MODE == EXECUTION_MODE_FULL_AUTO)
    _pass("auto_bridge", "build_auto_execution_controller" in smoke)
    _pass("timeline_fields", "auto_execution_timeline" in smoke)
    _pass("runtime_timeline", "set_execution_timeline" in runtime)
    _pass("ui_timeline", "Execution Timeline" in panel)


def _unit_mode_matrix() -> None:
    _pass("full_auto_generate", requires_operator_approval(EXECUTION_MODE_FULL_AUTO, "generate_button") is False)
    _pass("full_auto_download", requires_operator_approval(EXECUTION_MODE_FULL_AUTO, "download_mp4_button") is False)
    _pass("manual_generate", requires_operator_approval(EXECUTION_MODE_MANUAL, "generate_button") is True)


def _unit_simulate_full_auto() -> None:
    manual_calls: list[str] = []

    def _never_called(*_args: object) -> bool:
        manual_calls.append("approval")
        return False

    report = RunwayLiveSmokeRunner(
        story_idea="Auto pipeline validation run for three-clip continuity.",
        project_id="phase_i_full_auto_validate",
        simulate=True,
        clip_count=3,
        execution_mode=EXECUTION_MODE_FULL_AUTO,
        approval_callback=_never_called,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("simulate_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("no_manual_approval_calls", len(manual_calls) == 0, str(len(manual_calls)))
    _pass("auto_timeline_present", len(report.auto_execution_timeline) >= 1, str(len(report.auto_execution_timeline)))
    auto_grants = [item for item in report.approvals_granted if item.operator == "auto_execution"]
    timeline_actions = len(report.auto_execution_timeline)
    _pass(
        "auto_actions_recorded",
        timeline_actions >= 7 or len(auto_grants) >= 3,
        f"timeline={timeline_actions}; grants={len(auto_grants)}",
    )


def _unit_manual_fallback() -> None:
    report = run_live_smoke_test(
        "Manual fallback smoke validation topic.",
        project_id="phase_i_manual_validate",
        simulate=True,
        clip_count=1,
        execution_mode=EXECUTION_MODE_MANUAL,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    )
    _pass("manual_sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("manual_mode_preserved", report.execution_mode == EXECUTION_MODE_MANUAL)


def main() -> int:
    print("[validate_phase_i_full_auto_mode] Phase I FULL_AUTO mode")
    _unit_modules()
    _unit_mode_matrix()
    _unit_simulate_full_auto()
    _unit_manual_fallback()
    print("\n[validate_phase_i_full_auto_mode] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
