"""
Phase I — artifact card tracking + CDP-preferred download validation.
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
from content_brain.execution.runway_phase_i_artifact_tracker import (
    DEFAULT_ARTIFACT_CARD_DIAGNOSTICS,
    ROLE_STARTER_IMAGE,
    PhaseIArtifactTracker,
    USE_FRAME_LABELS,
)
from content_brain.execution.runway_phase_i_cdp_download import (
    DEFAULT_DOWNLOAD_DIAGNOSTICS,
    STRATEGY_CDP_FETCH,
    STRATEGY_UI_FALLBACK,
    RunwayPhaseICdpDownloader,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

SAMPLE_STORY = "Astronaut above a neon city; three-clip continuity test."


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_ui_map() -> dict:
    from project_brain.validate_runway_live_smoke_test import _mock_ui_map as base_mock

    return base_mock()


def _unit_implementation() -> None:
    nav_src = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    semi_src = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(encoding="utf-8")
    tracker_src = (
        ROOT / "content_brain/execution/runway_phase_i_artifact_tracker.py"
    ).read_text(encoding="utf-8")
    cdp_src = (ROOT / "content_brain/execution/runway_phase_i_cdp_download.py").read_text(
        encoding="utf-8"
    )
    smoke_src = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    _pass("artifact_tracker_module", "class PhaseIArtifactTracker" in tracker_src)
    _pass("cdp_download_module", "class RunwayPhaseICdpDownloader" in cdp_src)
    _pass("download_assigned_clip_video", "def download_assigned_clip_video" in nav_src)
    _pass("ensure_clip_video_card", "def ensure_clip_video_card_assigned" in nav_src)
    _pass("in_card_label_visible", "def is_label_visible_in_clip_video_card" in nav_src)
    _pass("latest_video_card_role", "ROLE_LATEST_VIDEO" in tracker_src)
    _pass("latest_video_card_click", "click_label_on_latest_video_card" in tracker_src)
    _pass("latest_video_card_label_visible", "label_visible_on_latest_video_card" in tracker_src)
    _pass("scoped_use_frame", "def click_use_frame_for_next_clip" in nav_src)
    _pass("no_global_use_frame_fallback", "global_use_frame_button" not in nav_src.split("click_use_frame_for_next_clip")[1][:500])
    _pass("no_global_download_in_cdp", "global_ui_download_click" not in cdp_src)
    _pass("assign_clip_video", "def assign_clip_video_artifact" in nav_src)
    _pass("mark_consumed_not_delete", "mark_consumed" in tracker_src and "mark_consumed(ROLE_STARTER_IMAGE)" in nav_src)
    _pass("semi_scoped_download", "download_assigned_clip_video" in semi_src)
    _pass("cdp_preferred_config", 'download_strategy="cdp_preferred"' in smoke_src or "cdp_preferred" in cdp_src)
    _pass("report_download_strategy", "clip_1_download_strategy" in smoke_src)


def _unit_starter_vs_clip_tracking() -> None:
    tracker = PhaseIArtifactTracker(simulate=True, project_id="artifact_test")
    starter_fp = tracker.simulate_add_card(card_type="image", prompt_text="starter")
    tracker.assignments[ROLE_STARTER_IMAGE] = tracker._card_from_raw(
        tracker._simulated_cards[0],
        role=ROLE_STARTER_IMAGE,
    )
    tracker.snapshot_before_generation(phase="clip_1_video")
    tracker.mark_consumed(ROLE_STARTER_IMAGE)
    clip1 = tracker.assign_new_card(PhaseIArtifactTracker.clip_video_role(1), prefer_type="video")
    _pass("starter_assigned", tracker.get_assigned(ROLE_STARTER_IMAGE) is not None)
    _pass("clip1_assigned", clip1 is not None)
    _pass("starter_not_clip1", clip1 is not None and starter_fp != clip1.card_fingerprint)
    _pass("clip1_is_video", clip1 is not None and clip1.card_type == "video")
    tracker.ensure_starter_not_used_for_clip_ops(1)
    _pass("starter_not_used_for_clip1_ops", True)


def _unit_use_frame_scoped_to_prior_clip() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="use_frame_scope")
    tracker = nav.phase_i_artifact_tracker()
    tracker.simulate_add_card(card_type="video", prompt_text="clip 1", buttons=list(USE_FRAME_LABELS))
    c1 = tracker.assign_new_card(PhaseIArtifactTracker.clip_video_role(1), prefer_type="video")
    _pass("clip1_for_use_frame", c1 is not None)
    scoped = nav.click_use_frame_for_next_clip(2)
    _pass("use_frame_scoped_click", scoped is True)


def _unit_cdp_url_preferred_and_ui_fallback() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="cdp_test", session_id="sess-1")
    tracker = nav.phase_i_artifact_tracker()
    role = PhaseIArtifactTracker.clip_video_role(1)
    tracker.simulate_add_card(
        card_type="video",
        prompt_text="clip 1",
        buttons=["Download MP4"],
    )
    tracker.assign_new_card(role, prefer_type="video")
    attempt = nav.download_assigned_clip_video(1, approved=True)
    _pass("cdp_sim_download_ok", attempt.downloaded is True, attempt.strategy)
    _pass("scoped_download", attempt.scoped_to_card is True)

    tracker2 = PhaseIArtifactTracker(simulate=True, project_id="fallback")
    tracker2.simulate_add_card(card_type="video", prompt_text="no url")
    tracker2.assignments[role] = tracker2._card_from_raw(tracker2._simulated_cards[0], role=role)
    tracker2.assignments[role].media_urls = []
    tracker2._simulated_cards[0]["mediaUrls"] = []
    downloader = RunwayPhaseICdpDownloader(
        download_dir=ROOT / "downloads" / "runway",
        tracker=tracker2,
        simulate=True,
        project_id="fallback",
        config=__import__(
            "content_brain.execution.runway_phase_i_cdp_download",
            fromlist=["RunwayPhaseICdpDownloadConfig"],
        ).RunwayPhaseICdpDownloadConfig(fallback_to_ui_download=True),
        ui_download_click=lambda: None,
    )
    fb = downloader.download_clip(1)
    _pass("fallback_strategy", fb.strategy in {STRATEGY_UI_FALLBACK, STRATEGY_CDP_FETCH}, fb.strategy)


def _unit_diagnostics_files() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="diag")
    nav.phase_i_artifact_tracker().write_diagnostics(context="unit_test")
    _pass("artifact_diag_exists", DEFAULT_ARTIFACT_CARD_DIAGNOSTICS.is_file())
    payload = json.loads(DEFAULT_ARTIFACT_CARD_DIAGNOSTICS.read_text(encoding="utf-8"))
    _pass("artifact_diag_assignments", "assignments" in payload)
    nav.download_assigned_clip_video(1, approved=True)
    _pass("download_diag_exists", DEFAULT_DOWNLOAD_DIAGNOSTICS.is_file())
    dl = json.loads(DEFAULT_DOWNLOAD_DIAGNOSTICS.read_text(encoding="utf-8"))
    _pass("download_diag_urls", "detected_media_urls" in dl)
    _pass("download_diag_strategy", "chosen_download_strategy" in dl)


def _unit_sim_rehearsal_and_gates() -> None:
    plan = build_continuity_plan(
        project_id="artifact_sim",
        starter_image_prompt="starter",
        clip_prompts=["c1", "c2", "c3"],
    )
    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("seven_gates", len(gated) == expected_approval_gate_count(3), str(len(gated)))

    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="artifact_sim_run",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("clip1_strategy_reported", bool(report.clip_1_download_strategy))
    _pass("clip2_scoped_reported", report.clip_2_download_scoped_to_card is True)
    _pass("paths_populated", len(report.downloaded_file_paths) >= 1)
    _pass("total_downloads", report.total_downloads_completed >= 1)


def _unit_no_forbidden_changes() -> None:
    story = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")
    prompt = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    _pass("story_brief_untouched", "build_runway_story_brief" in story)
    _pass("prompt_builder_untouched", "build_continuity_prompts" in prompt)
    _pass("no_provider_mutation", "PhaseIArtifactTracker" not in provider)


def main() -> int:
    print("[validate_phase_i_artifact_tracking_and_cdp_download] Artifact + CDP download")
    _unit_implementation()
    _unit_starter_vs_clip_tracking()
    _unit_use_frame_scoped_to_prior_clip()
    _unit_cdp_url_preferred_and_ui_fallback()
    _unit_diagnostics_files()
    _unit_sim_rehearsal_and_gates()
    _unit_no_forbidden_changes()
    print("\n[validate_phase_i_artifact_tracking_and_cdp_download] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
