"""
Phase I.5 — download verification + story progression validation.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_approval_guard import APPROVAL_GATED_CONTROLS
from content_brain.execution.runway_continuity_dry_run import run_dry_run
from content_brain.execution.runway_continuity_models import SEMI_AUTO_STATUS_COMPLETED
from content_brain.execution.runway_live_smoke_test import (
    PHASE_I_CLIP_COUNT,
    RunwayLiveSmokeRunner,
    expected_approval_gate_count,
)
from content_brain.execution.runway_phase_i_download_tracker import RunwayPhaseIDownloadTracker
from content_brain.execution.runway_prompt_builder import build_continuity_prompts
from content_brain.execution.runway_story_brief_builder import build_runway_story_brief
from content_brain.execution.runway_story_progression_validator import (
    beats_are_unique,
    validate_clip_beat_progression,
    validate_story_progression,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH

SAMPLE_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _unit_story_progression() -> None:
    brief = build_runway_story_brief(SAMPLE_STORY, clip_count=3, niche_style="cyberpunk")
    bundle = build_continuity_prompts(SAMPLE_STORY, clip_count=3, story_brief=brief, auto_story_brief=False)
    beat_checks = validate_clip_beat_progression(brief.clip_beats)
    progression = validate_story_progression(brief, bundle)

    _pass("three_clip_beats", len(brief.clip_beats) == 3)
    _pass("three_unique_beats", beats_are_unique(brief.clip_beats))
    _pass("discovery_present", beat_checks["discovery_present"], brief.clip_beats[0][:80])
    _pass("escalation_present", beat_checks["escalation_present"], brief.clip_beats[1][:80])
    _pass("payoff_present", beat_checks["payoff_present"], brief.clip_beats[2][:80])
    _pass("continuity_preserved_prompts", progression["continuity_preserved_all_clips"])
    _pass("character_locked", progression["character_locked"])
    _pass("setting_locked", progression["setting_locked"])
    _pass("progression_all_pass", progression["all_pass"], str(progression))


def _unit_download_tracker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        download_dir = Path(tmp)
        tracker = RunwayPhaseIDownloadTracker(download_dir, simulate=False, project_id="phase_i5_test")

        missing = tracker.verify_clip_download(1)
        _pass("missing_download_not_verified", missing.downloaded is False)

        file_a = download_dir / "runway_clip_1_test.mp4"
        file_b = download_dir / "runway_clip_2_test.mp4"
        file_a.write_bytes(b"clip-one-bytes")
        file_b.write_bytes(b"clip-two-bytes-longer")

        record_1 = tracker.verify_clip_download(1)
        _pass("clip_1_file_exists", record_1.downloaded is True, record_1.file_path)
        _pass("clip_1_size_positive", record_1.file_size_bytes > 0, str(record_1.file_size_bytes))

        record_2 = tracker.verify_clip_download(2)
        _pass("clip_2_file_exists", record_2.downloaded is True, record_2.file_path)
        _pass("filenames_unique", record_1.file_path != record_2.file_path)

        fields = tracker.report_fields(clip_count=3)
        _pass("report_clip_1_downloaded", fields["clip_1_downloaded"] is True)
        _pass("report_clip_2_downloaded", fields["clip_2_downloaded"] is True)
        _pass("report_clip_3_downloaded", fields["clip_3_downloaded"] is False)
        _pass("report_total_downloads", fields["total_downloads_completed"] == 2, str(fields))
        _pass("report_paths_populated", len(fields["downloaded_file_paths"]) == 2)


def _unit_report_fields_on_sim_rehearsal() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="phase_i5_sim",
        operator="validator",
        simulate=True,
        clip_count=PHASE_I_CLIP_COUNT,
        approval_callback=lambda *_args: True,
        manual_ack_callback=lambda *_args: True,
    ).run()

    payload = report.to_dict()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("report_has_clip_1_downloaded", "clip_1_downloaded" in payload)
    _pass("report_has_download_paths", "downloaded_file_paths" in payload)
    _pass("report_has_total_downloads", "total_downloads_completed" in payload)
    _pass("sim_three_downloads_completed", report.total_downloads_completed == 3, str(report.total_downloads_completed))
    _pass("sim_download_paths_unique", len(set(report.downloaded_file_paths)) == 3)
    _pass("sim_all_clip_flags_true", report.clip_1_downloaded and report.clip_2_downloaded and report.clip_3_downloaded)
    _pass("story_progression_audit_present", bool(report.story_progression_audit))
    _pass("story_progression_all_pass", report.story_progression_audit.get("all_pass") is True)


def _unit_seven_gates_unchanged() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, clip_count=3)
    dry = run_dry_run(bundle.to_continuity_plan(), map_path=DEFAULT_MAP_PATH)
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("seven_gates", len(gated) == expected_approval_gate_count(3), str(len(gated)))


def _static_no_assembly_voice() -> None:
    tracker = (ROOT / "content_brain/execution/runway_phase_i_download_tracker.py").read_text(encoding="utf-8")
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("tracker_no_ffmpeg", "ffmpeg" not in tracker.lower())
    _pass("tracker_no_assembly_runtime", "AssemblyRuntime" not in tracker)
    _pass("smoke_no_assembly_in_tracker_path", "AssemblyRuntime" not in smoke)
    _pass("no_provider_mutation", "validate_phase_i5" not in provider)


def main() -> None:
    print("validate_phase_i5_download_and_progression")
    _static_no_assembly_voice()
    _unit_story_progression()
    _unit_download_tracker()
    _unit_report_fields_on_sim_rehearsal()
    _unit_seven_gates_unchanged()
    print("\nAll Phase I.5 download + progression checks passed.")


if __name__ == "__main__":
    main()
