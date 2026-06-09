"""
Phase I — strict completion card scoping validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_phase_i_artifact_tracker import PhaseIArtifactTracker
from content_brain.execution.runway_phase_i_strict_completion_gate import (
    card_is_complete_candidate,
    card_is_offscreen_or_stale,
    card_scoped_state_dict,
    evaluate_strict_clip_completion,
    fingerprint_document_top,
    progress_blocks_completion,
    _evaluate_payload,
    _partition_video_cards,
    _resolve_target_card,
)
from content_brain.execution.runway_ui_map_loader import resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_ui_map() -> dict:
    from project_brain.validate_runway_live_smoke_test import _mock_ui_map as base_mock

    return base_mock()


class _NavStub:
    simulate = False

    def detect_video_generation_in_progress(self, clip_index: int):
        class _Gen:
            in_progress = True
            progress_text = "Get notifications when your generations are complete. Don't show again Later Enable"
            spinner_visible = False
            stop_cancel_visible = True
            output_loading = False
            signals = ["stop_cancel_visible"]

            def to_dict(self):
                return {
                    "in_progress": self.in_progress,
                    "progress_text": self.progress_text,
                    "spinner_visible": self.spinner_visible,
                    "stop_cancel_visible": self.stop_cancel_visible,
                    "output_loading": self.output_loading,
                    "signals": list(self.signals),
                }

        return _Gen()

    def phase_i_artifact_tracker(self):
        return PhaseIArtifactTracker(simulate=True)

    def _require_page(self):
        raise RuntimeError("no page in stub")


def _unit_notification_banner_ignored() -> None:
    banner = "Get notifications when your generations are complete. Don't show again Later Enable"
    _pass("notification_banner_not_blocking", not progress_blocks_completion(banner), banner)


def _unit_stale_card_rejection() -> None:
    stale = {
        "cardFingerprint": "488|-247|608|439|video|an old man quiet beach",
        "cardType": "video",
        "cardViewportTop": -247,
        "cardViewportBottom": 192,
        "cardWidth": 608,
        "cardHeight": 439,
        "cardPromptText": "an old man quiet beach",
    }
    stale_flag, reason = card_is_offscreen_or_stale(stale)
    _pass("stale_negative_y_rejected", stale_flag, reason)
    _pass("fingerprint_negative_top", fingerprint_document_top(stale["cardFingerprint"]) == -247.0)

    visible = {
        "cardFingerprint": "488|900|608|439|video|continuity lock same character",
        "cardType": "video",
        "cardViewportTop": 120,
        "cardViewportBottom": 559,
        "cardWidth": 608,
        "cardHeight": 439,
        "cardBottom": 1459,
        "cardPromptText": "continuity lock same character",
        "playableVideo": True,
        "hasAppsMenu": True,
    }
    ok_flag, _ = card_is_offscreen_or_stale(visible)
    _pass("visible_current_card_accepted", not ok_flag)


def _unit_card_complete_overrides_global() -> None:
    nav = _NavStub()
    from content_brain.execution.runway_phase_i_strict_completion_gate import StrictClipCompletionResult

    payload = {
        "artifactCards": [
            {
                "cardFingerprint": "488|900|608|439|video|clip1 done",
                "cardType": "video",
                "cardBottom": 1500,
                "cardViewportTop": 100,
                "cardViewportBottom": 539,
                "cardViewportVisible": True,
                "cardWidth": 608,
                "cardHeight": 439,
                "playableVideo": True,
                "hasAppsMenu": True,
                "hasDownload": False,
                "videoLoading": False,
                "cardLoading": False,
                "cardSpinnerVisible": False,
                "cardProgressVisible": False,
            }
        ],
        "rejectedCards": [
            {"cardFingerprint": "488|-247|608|439|video|old", "reason": "negative_viewport_y"}
        ],
        "downloadButtonCandidates": ["download mp4"],
        "ignoredGlobalDownload": True,
        "useFrameInPrior": False,
    }
    base = StrictClipCompletionResult(clip_index=1)
    base.generation_in_progress = True
    base.stop_cancel_visible = True
    base.progress_text = "Get notifications when your generations are complete. Don't show again Later Enable"
    nav_stub = _NavStub()
    evaluated = _evaluate_payload(
        nav_stub,
        base,
        payload,
        clip_index=1,
        assigned_fingerprint="",
        require_use_frame=False,
        expected_prompt_tokens=[],
    )
    _pass("card_complete_despite_global", evaluated.complete, evaluated.reason)
    _pass("override_note", any("overrides_global" in n for n in evaluated.notes))
    _pass("rejected_stale_logged", len(evaluated.rejected_cards) >= 1)


def _unit_bottom_most_candidate() -> None:
    cards = [
        {
            "cardFingerprint": "a|100|1|1|video|older",
            "cardType": "video",
            "cardBottom": 800,
            "cardViewportTop": 10,
            "cardViewportBottom": 400,
            "cardWidth": 200,
            "cardHeight": 200,
            "playableVideo": True,
            "hasDownload": True,
        },
        {
            "cardFingerprint": "b|900|1|1|video|newest",
            "cardType": "video",
            "cardBottom": 1200,
            "cardViewportTop": 50,
            "cardViewportBottom": 450,
            "cardWidth": 200,
            "cardHeight": 200,
            "playableVideo": True,
            "hasAppsMenu": True,
        },
    ]
    candidates, rejected = _partition_video_cards(cards, expected_prompt_tokens=[])
    target = _resolve_target_card(candidates=candidates, assigned_fingerprint="")
    _pass("bottom_most_selected", target is not None and "newest" in target["cardFingerprint"])
    _pass("complete_candidate_apps", card_is_complete_candidate(candidates[0]))


def _unit_assignment_persistence() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="card_scope_test")
    nav.mark_clip_generating(1)
    pending = nav.evaluate_strict_clip_completion(1)
    _pass("generating_not_complete", not pending.complete, pending.reason)
    nav.clear_clip_generating(1)
    done = nav.evaluate_strict_clip_completion(1)
    _pass("simulate_complete", done.complete, done.reason)
    tracker = nav.phase_i_artifact_tracker()
    latest = tracker.get_latest_video_card()
    _pass("latest_video_persisted", latest is not None and bool(latest.card_fingerprint))
    _pass(
        "persisted_fp_matches",
        done.persisted_assignment_fingerprint == latest.card_fingerprint,
    )


def _unit_diagnostics_shape() -> None:
    card = {
        "cardFingerprint": "x|1|2|3|video|t",
        "cardType": "video",
        "playableVideo": True,
        "hasAppsMenu": True,
    }
    scoped = card_scoped_state_dict(card)
    _pass("scoped_has_apps", scoped.get("hasAppsMenu") is True)
    _pass("scoped_complete_flag", scoped.get("completeCandidate") is True)


def _unit_existing_override_contract() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav.configure_phase_i_artifact_tracking(project_id="card_scope_override")

    def _eval(override: dict):
        nav._strict_completion_test_override = override
        return nav.evaluate_strict_clip_completion(1)

    r6 = _eval({"generation_in_progress": True, "progress_text": "6%", "reason": "generation_in_progress"})
    _pass("six_percent_still_blocks", not r6.complete, r6.reason)
    nav._strict_completion_test_override = None


def main() -> int:
    print("[validate_phase_i_strict_completion_card_scoping] Card-scoped strict completion")
    _unit_notification_banner_ignored()
    _unit_stale_card_rejection()
    _unit_card_complete_overrides_global()
    _unit_bottom_most_candidate()
    _unit_assignment_persistence()
    _unit_diagnostics_shape()
    _unit_existing_override_contract()
    print("\n[validate_phase_i_strict_completion_card_scoping] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
