#!/usr/bin/env python3
"""
Phase RUNWAY-STARTER-TO-VIDEO-H — run first live operator-approved smoke test.

Prerequisites:
  1. Chrome open with CDP on http://127.0.0.1:9222 (Open Browser in app)
  2. Logged into Runway in that Chrome session
  3. runway_ui_map.json validated (19/19 controls)

Usage:
  python project_brain/run_runway_live_smoke_test.py --story "Your idea..."
  python project_brain/run_runway_live_smoke_test.py --story-file path/to/story.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_live_smoke_test import (
    DEFAULT_REPORT_MD,
    LIVE_SMOKE_VERSION,
    MAX_COMPLETION_WAIT_MINUTES,
    PHASE_I_CLIP_COUNT,
    SMOKE_CLIP_COUNT,
    run_live_smoke_test,
)

DEFAULT_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere, "
    "neon teal and amber reflections, dramatic volumetric fog, ultra realistic detail. "
    "She turns slowly toward the skyline as rain intensifies."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Runway live smoke test (Phase H)")
    parser.add_argument("--story", default="", help="Story / video idea text")
    parser.add_argument("--story-file", default="", help="Path to story text file")
    parser.add_argument("--project-id", default="live_smoke_h")
    parser.add_argument("--clip-count", type=int, default=SMOKE_CLIP_COUNT, help="Video clip count (Phase I uses 3)")
    parser.add_argument("--operator", default="operator")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Dry rehearsal only (no CDP). For structural testing — not a live smoke pass.",
    )
    parser.add_argument(
        "--ui-approval",
        action="store_true",
        help="Use Runtime Studio approval bridge (UI buttons). Falls back to terminal APPROVE/READY if UI not connected.",
    )
    args = parser.parse_args()

    story = str(args.story or "").strip()
    if args.story_file:
        story = Path(args.story_file).read_text(encoding="utf-8").strip()
    if not story:
        story = DEFAULT_STORY

    clip_count = max(1, int(args.clip_count))
    if clip_count == PHASE_I_CLIP_COUNT:
        args.project_id = args.project_id if args.project_id != "live_smoke_h" else "phase_i_live"

    print(f"[run_runway_live_smoke_test] {LIVE_SMOKE_VERSION if clip_count == 1 else 'runway_starter_to_video_i_3clip_v1'}")
    print(f"  Clips: {clip_count}")
    print(f"  Max completion wait: {MAX_COMPLETION_WAIT_MINUTES} min")
    print(f"  simulate: {args.simulate}")
    print(f"  project_id: {args.project_id}")
    print()
    if not args.simulate and not args.ui_approval:
        print("Live mode: Generate and Download require typing APPROVE at each gate.")
        print("Manual image-ready hold requires typing READY.")
        print()
    elif not args.simulate and args.ui_approval:
        print("Live mode: approval gates routed to Runtime Studio UI bridge.")
        print("Open Execution Center → Runway Live Smoke tab, or attach Runtime Studio panel.")
        print("Terminal APPROVE/READY remains fallback if UI is not connected within ~1.5s.")
        print()

    approvals_log: list[tuple[str, str]] = []
    ui_runtime = None
    if args.ui_approval and not args.simulate:
        from content_brain.execution.runway_live_smoke_approval_runtime import RunwayLiveSmokeApprovalRuntime

        ui_runtime = RunwayLiveSmokeApprovalRuntime(
            operator=args.operator,
            project_id=args.project_id,
            fallback_to_terminal=True,
        )
        ui_runtime.set_run_status("running", detail="Live smoke run started with UI approval bridge")

    def auto_approve(control_key: str, step_id: str, label: str) -> bool:
        approvals_log.append((control_key, step_id))
        if args.simulate:
            print(f"[simulate] APPROVED {control_key} ({step_id})")
            return True
        if ui_runtime is not None:
            return ui_runtime.approval_callback(control_key, step_id, label)
        from content_brain.execution.runway_live_smoke_test import default_interactive_approval

        return default_interactive_approval(control_key, step_id, label)

    def auto_manual(step_id: str, action: str) -> bool:
        if args.simulate:
            print(f"[simulate] READY {step_id}")
            return True
        if ui_runtime is not None:
            return ui_runtime.manual_ack_callback(step_id, action)
        from content_brain.execution.runway_live_smoke_test import default_interactive_manual_ack

        return default_interactive_manual_ack(step_id, action)

    report = run_live_smoke_test(
        story,
        project_id=args.project_id,
        operator=args.operator,
        simulate=args.simulate,
        clip_count=clip_count,
        approval_callback=auto_approve,
        manual_ack_callback=auto_manual,
    )

    if ui_runtime is not None:
        ui_runtime.mark_run_finished(
            ok=report.ok,
            stopped_reason=report.stopped_reason,
            current_step_id=str(getattr(report, "current_step_id", "") or ""),
            last_action=str(getattr(report, "last_auto_action", "") or ""),
            next_action=str(getattr(report, "next_auto_action", "") or ""),
            validation_state=str(getattr(report, "auto_validation_state", "") or ""),
            timeline=list(getattr(report, "auto_execution_timeline", []) or []),
        )

    print()
    print(f"Result: {'PASS' if report.ok else 'FAIL'}")
    print(f"Report: {DEFAULT_REPORT_MD}")
    if report.errors:
        print("Errors:")
        for err in report.errors:
            print(f"  - {err}")
    if report.screenshots:
        print("Screenshots:")
        for shot in report.screenshots:
            print(f"  - {shot}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
