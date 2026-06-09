"""
Phase I — starter image pre-clean + Use for Video routing validation.

Structural + simulate=True only (no CDP / credit spend).
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
    DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS,
    PHASE_I_CLIP_COUNT,
    RunwayLiveSmokeRunner,
    _write_phase_i_failure_diagnostics,
    expected_approval_gate_count,
)
from content_brain.execution.runway_prompt_builder import build_continuity_prompts
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH
from content_brain.execution.runway_ui_navigator import (
    MappedRunwayUINavigator,
    USE_FOR_VIDEO_ACTION_LABELS,
)

SAMPLE_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_sources() -> None:
    dry_run = (ROOT / "content_brain/execution/runway_continuity_dry_run.py").read_text(encoding="utf-8")
    semi_auto = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(encoding="utf-8")
    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    story_brief = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")
    prompt_builder = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")

    _pass("preclean_step_in_plan", "preclean_starter_image_workspace" in dry_run)
    _pass("use_starter_step_in_plan", "use_starter_image_for_video" in dry_run)
    _pass("semi_auto_preclean_handler", "preclean_starter_image_workspace" in semi_auto)
    _pass("semi_auto_use_starter_handler", "use_starter_image_for_video" in semi_auto)
    _pass("navigator_preclean_method", "def preclean_starter_image_workspace" in navigator)
    _pass("navigator_use_starter_method", "def use_starter_image_for_video" in navigator)
    _pass("use_for_video_labels", "Use for Video" in USE_FOR_VIDEO_ACTION_LABELS)
    _pass("apply_label", "Apply" in USE_FOR_VIDEO_ACTION_LABELS)
    live_smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    _pass("failure_diagnostics_writer", "runway_phase_i_last_failure_diagnostics.json" in live_smoke)
    _pass("no_provider_mutation", "validate_runway_phase_i_starter" not in provider)
    _pass("story_brief_intact", "RunwayStoryBriefBuilder" in story_brief)
    _pass("prompt_builder_intact", "build_continuity_prompts" in prompt_builder)


def _unit_step_order() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, project_id="phase_i_use_for_video", clip_count=3)
    dry = run_dry_run(bundle.to_continuity_plan(), map_path=DEFAULT_MAP_PATH)
    step_keys = [s.step_id.split("_", 1)[-1] for s in dry.steps]

    idx_wait = step_keys.index("wait_for_image_ready_manual")
    idx_use = step_keys.index("use_starter_image_for_video")
    idx_prompt = step_keys.index("video_prompt_clip_1")
    idx_preclean = step_keys.index("preclean_starter_image_workspace")
    idx_generate = step_keys.index("image_generate_manual_required")

    _pass("dry_run_ok", dry.ok is True, str(dry.errors))
    _pass("preclean_before_generate", idx_preclean < idx_generate)
    _pass("use_starter_after_wait", idx_use > idx_wait)
    _pass("use_starter_before_video_prompt", idx_use < idx_prompt)
    _pass("no_legacy_image_use_to_video_step", "image_use_to_video" not in step_keys)
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("seven_gates_unchanged", len(gated) == expected_approval_gate_count(3), str(len(gated)))


def _unit_preclean_simulate() -> None:
    nav = MappedRunwayUINavigator.from_map(map_path=DEFAULT_MAP_PATH, simulate=True)
    clean = nav.preclean_starter_image_workspace()
    _pass("preclean_no_stale_safe", clean.preclean_attempted is True)
    _pass("preclean_no_stale_detected", clean.stale_image_preview_detected is False)
    _pass("preclean_no_stale_closed", clean.stale_preview_closed is False)

    nav2 = MappedRunwayUINavigator.from_map(map_path=DEFAULT_MAP_PATH, simulate=True)
    nav2._simulated_stale_preview_open = True
    stale = nav2.preclean_starter_image_workspace()
    _pass("preclean_stale_detected", stale.stale_image_preview_detected is True)
    _pass("preclean_stale_closed", stale.stale_preview_closed is True)


def _unit_use_starter_simulate() -> None:
    nav = MappedRunwayUINavigator.from_map(map_path=DEFAULT_MAP_PATH, simulate=True)
    nav.snapshot_generation_image_cards_before_generate()
    nav._ensure_simulated_post_generate_cards(SAMPLE_STORY)
    latest = nav.use_starter_image_for_video(SAMPLE_STORY)
    _pass("use_starter_transition", latest.video_transition_verified is True)
    _pass("use_starter_action_used", bool(latest.use_for_video_action_used))
    _pass("use_starter_candidates", len(latest.use_for_video_candidates) >= 1)


def _unit_failure_diagnostics_json() -> None:
    nav = MappedRunwayUINavigator.from_map(map_path=DEFAULT_MAP_PATH, simulate=True)
    nav.preclean_starter_image_workspace()
    nav.snapshot_generation_image_cards_before_generate()
    nav._ensure_simulated_post_generate_cards(SAMPLE_STORY)
    try:
        nav.use_starter_image_for_video(SAMPLE_STORY)
    except Exception:
        pass
    _write_phase_i_failure_diagnostics(
        nav,
        step_id="012_use_starter_image_for_video",
        error="simulated failure",
        selector_attempted="prompt_input",
        screenshot_path="",
    )
    _pass("diagnostics_file_written", DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS.is_file())
    payload = json.loads(DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS.read_text(encoding="utf-8"))
    _pass("diagnostics_has_step", payload.get("step_id") == "012_use_starter_image_for_video")
    _pass("diagnostics_has_preclean_notes", "preclean_notes" in payload)
    _pass("diagnostics_has_candidates_field", "use_for_video_candidates_visible" in payload)


def _unit_three_clip_rehearsal() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="phase_i_use_for_video_rehearsal",
        operator="validator",
        simulate=True,
        clip_count=PHASE_I_CLIP_COUNT,
        approval_callback=lambda *_args: True,
        manual_ack_callback=lambda *_args: True,
    ).run()
    _pass("rehearsal_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("rehearsal_preclean_attempted", report.preclean_attempted is True)
    _pass("rehearsal_video_transition", report.video_transition_verified is True)


def main() -> None:
    print("validate_runway_phase_i_starter_image_use_for_video")
    _static_sources()
    _unit_step_order()
    _unit_preclean_simulate()
    _unit_use_starter_simulate()
    _unit_failure_diagnostics_json()
    _unit_three_clip_rehearsal()
    print("\nAll Phase I starter image Use for Video checks passed.")


if __name__ == "__main__":
    main()
