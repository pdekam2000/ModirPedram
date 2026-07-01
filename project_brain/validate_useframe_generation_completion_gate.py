"""Validate USEFRAME-GENERATION-COMPLETION-GATE."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_real_mp4_download_extractor import (  # noqa: E402
    KlingRealMp4ExtractResult,
    poll_extract_real_kling_mp4,
    resolve_scoped_video_card_for_extraction,
)
from content_brain.execution.kling_useframe_generation_completion_gate import (  # noqa: E402
    GATE_VERSION,
    GenerationCompletionGateContext,
    GenerationCompletionGateResult,
    artifact_signature_from_card,
    build_prior_artifact_signatures_from_clip,
    detect_queue_warning_visible,
    find_new_artifact_candidate,
    is_duplicate_artifact,
    recovery_blocked_by_gate,
    wait_for_generation_completion_gate,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_gate_module_version() -> None:
    _pass("gate_version", GATE_VERSION == "kling_useframe_generation_completion_gate_v1")


def test_queue_warning_blocks_recovery() -> None:
    page = MagicMock()
    page.evaluate.return_value = "Please wait for your last generation to complete"
    page.locator.return_value.count.return_value = 0
    visible, reason = detect_queue_warning_visible(page)
    _pass("queue_warning_detected", visible)
    gate = GenerationCompletionGateContext(
        require_new_artifact=True,
        prior_artifact_signatures=[{"card_fingerprint": "fp1", "media_urls": ["http://a.mp4"]}],
    )
    blocked, block_reason = recovery_blocked_by_gate(page, gate)
    _pass("recovery_blocked_queue", blocked)
    _pass("recovery_block_reason", "queue_warning" in block_reason)


def test_duplicate_artifact_rejected() -> None:
    prior = [{"card_fingerprint": "fp1", "media_urls": ["https://cdn/x/video.mp4"], "file_hash": "abc"}]
    candidate = {"card_fingerprint": "fp1", "media_urls": ["https://cdn/x/video.mp4"]}
    dup, reason = is_duplicate_artifact(candidate, prior)
    _pass("duplicate_fingerprint", dup and reason == "same_card_fingerprint")
    candidate2 = {"card_fingerprint": "fp2", "media_urls": ["https://cdn/x/video.mp4"]}
    dup2, reason2 = is_duplicate_artifact(candidate2, prior)
    _pass("duplicate_url", dup2 and reason2 == "same_media_url")


def test_old_artifact_rejected_for_clip2() -> None:
    prior = [{"card_fingerprint": "fp_clip1", "media_urls": ["https://cdn/clip1.mp4"]}]
    cards = [
        {
            "cardType": "video",
            "cardFingerprint": "fp_clip1",
            "mediaSrc": "https://cdn/clip1.mp4",
            "mediaUrls": ["https://cdn/clip1.mp4"],
            "cardBottom": 500.0,
        },
        {
            "cardType": "video",
            "cardFingerprint": "fp_clip2",
            "mediaSrc": "https://cdn/clip2.mp4",
            "mediaUrls": ["https://cdn/clip2.mp4"],
            "cardBottom": 700.0,
        },
    ]
    selected, meta = find_new_artifact_candidate(
        cards=cards,
        prior_artifacts=prior,
        baseline_video_card_count=1,
        baseline_fingerprints=["fp_clip1"],
    )
    _pass("new_artifact_selected", selected is not None)
    _pass("clip2_not_clip1", selected.get("card_fingerprint") == "fp_clip2")

    only_old = find_new_artifact_candidate(
        cards=[cards[0]],
        prior_artifacts=prior,
        baseline_video_card_count=1,
        baseline_fingerprints=["fp_clip1"],
    )
    _pass("only_old_rejected", only_old[0] is None)
    _pass("rejected_old_logged", bool(only_old[1].get("rejected_duplicates")))


def test_clip2_waits_for_generation_completion() -> None:
    live_src = (ROOT / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    _pass("live_engine_uses_gate", "wait_for_generation_completion_gate" in live_src)
    _pass("live_engine_gate_step", "generation_completion_gate" in live_src)
    _pass("live_engine_gate_before_download", "gate_context=gate_context" in live_src)
    result = GenerationCompletionGateResult(
        gate_passed=True,
        detail="new_artifact_confirmed:video_card_count_increased",
        new_artifact_confirmed=True,
        confirmed_artifact={"card_fingerprint": "fp_new"},
    )
    _pass("gate_result_model", result.gate_passed and result.new_artifact_confirmed)


def test_recovery_starts_only_after_new_artifact() -> None:
    page = MagicMock()
    page.evaluate.return_value = ""
    page.locator.return_value.count.return_value = 0
    page.get_by_role.return_value.count.return_value = 0

    gate = GenerationCompletionGateContext(
        require_new_artifact=True,
        prior_artifact_signatures=[{"card_fingerprint": "fp1", "media_urls": ["http://old.mp4"]}],
        baseline_video_card_count=1,
        baseline_card_fingerprints=["fp1"],
    )
    with patch(
        "content_brain.execution.kling_useframe_generation_completion_gate.PhaseIArtifactTracker"
    ) as tracker_cls:
        tracker = MagicMock()
        tracker.scan_artifact_cards.return_value = [
            {
                "cardType": "video",
                "cardFingerprint": "fp1",
                "mediaSrc": "http://old.mp4",
                "mediaUrls": ["http://old.mp4"],
            }
        ]
        tracker_cls.return_value = tracker
        blocked, reason = recovery_blocked_by_gate(page, gate)
    _pass("recovery_locked_no_new_artifact", blocked)
    _pass("recovery_locked_reason", "new_artifact_not_confirmed" in reason)


def test_poll_recovery_locked_when_gate_blocks() -> None:
    page = MagicMock()
    dest = Path(tempfile.mkdtemp()) / "video.mp4"
    clip_dir = dest.parent
    gate = GenerationCompletionGateContext(
        require_new_artifact=True,
        prior_artifact_signatures=[{"file_hash": "deadbeef"}],
    )
    with patch(
        "content_brain.execution.kling_useframe_generation_completion_gate.recovery_blocked_by_gate",
        return_value=(True, "queue_warning_visible:please wait"),
    ), patch(
        "content_brain.execution.kling_real_mp4_download_extractor.extract_real_kling_mp4"
    ) as extract_mock, patch("content_brain.execution.kling_real_mp4_download_extractor.time.sleep"):
        result = poll_extract_real_kling_mp4(
            page,
            dest,
            run_id="gate_test",
            clip_index=2,
            clip_dir=clip_dir,
            gate_context=gate,
            poll_interval_seconds=1,
            max_wait_seconds=1,
        )
    _pass("poll_not_ok_when_locked", not result.ok)
    _pass("extract_not_called_when_locked", not extract_mock.called)
    _pass("poll_logs_recovery_locked", any(a.get("recovery_locked") for a in result.poll_attempts))


def test_scoped_resolver_rejects_prior_clip() -> None:
    tracker = MagicMock()
    tracker.scan_artifact_cards.return_value = [
        {
            "cardType": "video",
            "cardPromptText": "clip 1",
            "mediaSrc": "https://cdn/clip1.mp4",
            "mediaUrls": ["https://cdn/clip1.mp4"],
            "cardBottom": 500.0,
            "cardFingerprint": "fp1",
        },
        {
            "cardType": "video",
            "cardPromptText": "clip 2",
            "mediaSrc": "https://cdn/clip2.mp4",
            "mediaUrls": ["https://cdn/clip2.mp4"],
            "cardBottom": 700.0,
            "cardFingerprint": "fp2",
        },
    ]
    card = MagicMock()
    card.to_dict.return_value = {"card_fingerprint": "fp2", "role": "clip_2_video_card"}
    tracker._card_from_raw.return_value = card
    prior = [{"card_fingerprint": "fp1", "media_urls": ["https://cdn/clip1.mp4"]}]
    selected, meta = resolve_scoped_video_card_for_extraction(
        tracker,
        2,
        exclude_signatures=prior,
        require_new_artifact=True,
        baseline_video_card_count=1,
        baseline_card_fingerprints=["fp1"],
    )
    _pass("scoped_selects_new", selected is not None)
    _pass("scoped_strategy_new", meta.get("selection_strategy") == "new_non_duplicate_artifact")


def test_build_prior_from_clip_dir() -> None:
    tmp = Path(tempfile.mkdtemp())
    clip_dir = tmp / "c1"
    clip_dir.mkdir(parents=True)
    (clip_dir / "mp4_extract_report.json").write_text(
        json.dumps(
            {
                "card_selection": {
                    "selected_card": {
                        "cardFingerprint": "fp_prior",
                        "mediaSrc": "https://cdn/prior.mp4",
                        "mediaUrls": ["https://cdn/prior.mp4"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    sigs = build_prior_artifact_signatures_from_clip(clip_dir)
    _pass("prior_from_report", bool(sigs))
    _pass("prior_fingerprint", sigs[0].get("card_fingerprint") == "fp_prior")


def test_continuity_runtime_wires_gate() -> None:
    src = (ROOT / "content_brain/execution/kling_frame_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("continuity_prior_signatures", "build_prior_artifact_signatures_from_clip" in src)
    _pass("continuity_require_new", "require_new_artifact" in src)


def main() -> int:
    print("validate_useframe_generation_completion_gate")
    test_gate_module_version()
    test_queue_warning_blocks_recovery()
    test_duplicate_artifact_rejected()
    test_old_artifact_rejected_for_clip2()
    test_clip2_waits_for_generation_completion()
    test_recovery_starts_only_after_new_artifact()
    test_poll_recovery_locked_when_gate_blocks()
    test_scoped_resolver_rejects_prior_clip()
    test_build_prior_from_clip_dir()
    test_continuity_runtime_wires_gate()
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
