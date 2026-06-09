"""
Phase I — video playback controls mapping for last-frame seek validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_models import SEMI_AUTO_STATUS_COMPLETED
from content_brain.execution.runway_live_smoke_test import RunwayLiveSmokeRunner
from content_brain.execution.runway_phase_i_last_frame_use_frame import (
    last_frame_seek_eval_script,
    prepare_last_frame_use_frame_for_clip,
)
from content_brain.execution.runway_phase_i_video_playback_controls import (
    DEFAULT_PLAYBACK_CONTROLS_DIAGNOSTICS,
    SEEK_METHOD_HTML_VIDEO_CURRENT_TIME,
    SEEK_METHOD_TIMELINE_RANGE_IN_CARD,
    is_generation_abort_button_label,
    seek_script_uses_only_safe_playback,
)
from content_brain.execution.runway_ui_map_loader import resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

SAMPLE = "Playback controls mapping test."


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_ui_map() -> dict:
    from project_brain.validate_runway_live_smoke_test import _mock_ui_map as base_mock

    return base_mock()


def _unit_seek_script_html_video() -> None:
    script = last_frame_seek_eval_script()
    _pass("html_video_currentTime", "video.currentTime" in script)
    _pass("html_video_pause_api", "video.pause()" in script)
    _pass("timeline_fallback_range", 'type=\\"range\\"' in script or "timeline_percent" in script)
    _pass("timeline_fallback_duration_percent", "duration * timelinePercent" in script)
    _pass("returns_seek_method", "seekMethod" in script)
    _pass("no_generation_control_click_flag", "generationControlClickAttempted: false" in script)
    _pass("safe_playback_static_audit", seek_script_uses_only_safe_playback())


def _unit_generation_vs_playback_labels() -> None:
    _pass("stop_generation_is_abort", is_generation_abort_button_label("Stop generation"))
    _pass("cancel_render_is_abort", is_generation_abort_button_label("Cancel render"))
    _pass("play_is_not_abort", not is_generation_abort_button_label("Play"))
    _pass("pause_is_not_abort", not is_generation_abort_button_label("Pause"))


def _unit_live_runtime_wiring() -> None:
    semi = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(encoding="utf-8")
    nav = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    lf = (ROOT / "content_brain/execution/runway_phase_i_last_frame_use_frame.py").read_text(encoding="utf-8")
    _pass("semi_auto_prepare_last_frame", "prepare_last_frame_use_frame_for_clip" in semi)
    _pass("navigator_wrapper", "prepare_last_frame_use_frame_for_clip" in nav)
    _pass("playback_audit_in_live_seek", "audit_card_playback_controls" in lf)
    _pass("playback_diagnostics_write", "write_playback_controls_diagnostics" in lf)


def _unit_sim_seek_methods() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="playback_sim")
    tracker = nav.phase_i_artifact_tracker()
    for prev in (1, 2):
        tracker.simulate_add_card(card_type="video", prompt_text=f"c{prev}", buttons=["Use Frame"])
        tracker.assign_new_card(tracker.clip_video_role(prev), prefer_type="video")
    result = prepare_last_frame_use_frame_for_clip(nav, 2)
    _pass("sim_playback_method", result.playback_seek_method == "simulate")
    _pass("sim_generation_avoided", result.generation_controls_avoided is True)
    _pass("sim_seeked", result.previous_clip_seeked_to_last_frame is True)


def _unit_sim_rehearsal() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE,
        project_id="playback_controls_sim",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    entry = report.use_frame_last_frame_by_clip.get("2") or {}
    _pass("report_has_playback_method", bool(entry.get("playback_seek_method")))
    _pass("report_generation_avoided", entry.get("generation_controls_avoided") is True)


def _unit_report_and_module_exist() -> None:
    _pass(
        "mapping_report",
        (ROOT / "project_brain/PHASE_I_VIDEO_PLAYBACK_CONTROLS_MAPPING_REPORT.md").is_file(),
    )
    _pass(
        "playback_module",
        (ROOT / "content_brain/execution/runway_phase_i_video_playback_controls.py").is_file(),
    )


def main() -> int:
    print("[validate_phase_i_video_playback_controls] Playback controls for last-frame seek")
    _unit_seek_script_html_video()
    _unit_generation_vs_playback_labels()
    _unit_live_runtime_wiring()
    _unit_sim_seek_methods()
    _unit_sim_rehearsal()
    _unit_report_and_module_exist()
    _pass("diagnostics_path", DEFAULT_PLAYBACK_CONTROLS_DIAGNOSTICS.name.endswith(".json"))
    print("\n[validate_phase_i_video_playback_controls] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
