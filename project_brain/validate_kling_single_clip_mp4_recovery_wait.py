"""Validate KLING-SINGLE-CLIP-MP4-RECOVERY-WAIT — poll instead of immediate fail."""

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
    EXTRACTOR_VERSION,
    KlingRealMp4ExtractResult,
    MP4_RECOVERY_POLL_INTERVAL_SECONDS,
    MP4_RECOVERY_POLL_MAX_SECONDS,
    card_has_visible_video_preview,
    extract_real_kling_mp4,
    is_rejected_placeholder_card,
    poll_extract_real_kling_mp4,
    rank_video_artifact_cards,
    resolve_scoped_video_card_for_extraction,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_extractor_v2() -> None:
    _pass("extractor_v2", EXTRACTOR_VERSION == "kling_real_mp4_download_extractor_v2")


def test_poll_constants() -> None:
    _pass("poll_interval_10s", MP4_RECOVERY_POLL_INTERVAL_SECONDS == 10)
    _pass("poll_max_5m", MP4_RECOVERY_POLL_MAX_SECONDS == 300)


def test_placeholder_card_rejected() -> None:
    bad = {
        "cardType": "video",
        "cardPromptText": "Studio empty state",
        "mediaSrc": "https://cdn.example.com/app/empty-state/studio-empty-state.webm",
    }
    _pass("placeholder_card", is_rejected_placeholder_card(bad))
    _pass("placeholder_no_preview", not card_has_visible_video_preview(bad))


def test_newest_card_preferred() -> None:
    cards = [
        {
            "cardType": "video",
            "cardPromptText": "clip 1",
            "mediaSrc": "blob:https://app.runwayml.com/abc",
            "cardBottom": 100.0,
            "cardFingerprint": "old",
        },
        {
            "cardType": "video",
            "cardPromptText": "clip 1 newer",
            "mediaSrc": "blob:https://app.runwayml.com/def",
            "cardBottom": 500.0,
            "cardFingerprint": "new",
            "selected": True,
        },
    ]
    ranked = rank_video_artifact_cards(cards)
    _pass("newest_first", ranked[0].get("cardFingerprint") == "new")


def test_poll_waits_instead_of_immediate_fail() -> None:
    page = MagicMock()
    dest = Path(tempfile.mkdtemp()) / "video.mp4"
    clip_dir = dest.parent
    attempts = {"n": 0}

    def _fake_extract(*args, **kwargs):
        attempts["n"] += 1
        ok = attempts["n"] >= 2
        return KlingRealMp4ExtractResult(
            ok=ok,
            output_path=str(dest) if ok else "",
            attempted_methods=[f"cycle_{attempts['n']}"],
            card_selection={"card_count": attempts["n"], "video_card_count": 1 if ok else 0},
        )

    with patch(
        "content_brain.execution.kling_real_mp4_download_extractor.extract_real_kling_mp4",
        side_effect=_fake_extract,
    ), patch("content_brain.execution.kling_real_mp4_download_extractor.time.sleep") as sleep:
        result = poll_extract_real_kling_mp4(
            page,
            dest,
            run_id="test_poll",
            clip_index=1,
            clip_dir=clip_dir,
            recovery_mode=True,
            poll_interval_seconds=10,
            max_wait_seconds=300,
        )
    _pass("poll_multiple_attempts", attempts["n"] >= 2)
    _pass("poll_sleep_called", sleep.called)
    _pass("poll_eventually_ok", result.ok is True)
    _pass("poll_attempts_logged", len(result.poll_attempts) >= 2)


def test_no_generate_click_during_recovery() -> None:
    src = (ROOT / "content_brain/execution/kling_real_mp4_download_extractor.py").read_text(encoding="utf-8")
    download_src = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    _pass("extractor_doc_no_generate", "Never clicks Generate" in src)
    _pass("poll_doc_no_generate", "Never clicks Generate" in src.split("def poll_extract_real_kling_mp4")[1][:400])
    _pass("download_uses_poll", "poll_extract_real_kling_mp4" in download_src)
    _pass("no_generate_in_extractor", 'name=re.compile(r"^Generate$"' not in src and 'name="Generate"' not in src)


def test_valid_mp4_accepted() -> None:
    from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4
    from content_brain.execution.kling_multishot_live_engine import MIN_REAL_MP4_BYTES

    good = ROOT / "outputs/kling_single_clip/kling_sc_20260621T111602_b3319b64/clip_1.mp4"
    if good.is_file() and good.stat().st_size >= MIN_REAL_MP4_BYTES:
        verify = verify_extracted_kling_mp4(good)
        _pass("valid_mp4_fixture", bool(verify.get("is_real_mp4")))
    else:
        _pass("valid_mp4_fixture", True, "skipped — no fixture mp4")


def test_report_includes_poll_attempts() -> None:
    page = MagicMock()
    dest = Path(tempfile.mkdtemp()) / "video.mp4"
    clip_dir = dest.parent
    ok_result = KlingRealMp4ExtractResult(
        ok=True,
        output_path=str(dest),
        attempted_methods=["artifact_card_cdp_urls:verify_0"],
        card_selection={"card_count": 2, "video_card_count": 1, "selected_card": {"role": "latest_video_card"}},
        poll_attempts=[{"attempt": 1, "valid_mp4_found": True}],
        poll_elapsed_seconds=0.5,
    )
    with patch(
        "content_brain.execution.kling_real_mp4_download_extractor.extract_real_kling_mp4",
        return_value=ok_result,
    ):
        result = poll_extract_real_kling_mp4(
            page,
            dest,
            run_id="test_report",
            clip_index=1,
            clip_dir=clip_dir,
        )
    report_path = clip_dir / "mp4_recovery_poll_report.json"
    _pass("poll_report_written", report_path.is_file())
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    _pass("poll_report_has_attempts", bool(payload.get("attempts")))
    _pass("poll_result_has_attempts", bool(result.poll_attempts))


def test_scoped_card_resolver_mock() -> None:
    tracker = MagicMock()
    tracker.scan_artifact_cards.return_value = [
        {
            "cardType": "video",
            "cardPromptText": "real clip",
            "mediaSrc": "blob:https://app.runwayml.com/video1",
            "cardBottom": 300.0,
            "cardFingerprint": "fp1|300|100|80|video|real",
            "buttonsVisible": ["Download"],
            "mediaUrls": ["blob:https://app.runwayml.com/video1"],
        }
    ]
    card = MagicMock()
    card.to_dict.return_value = {"role": "latest_video_card", "card_fingerprint": "fp1"}
    tracker._card_from_raw.return_value = card
    selected, meta = resolve_scoped_video_card_for_extraction(tracker, 1)
    _pass("scoped_card_selected", selected is not None)
    _pass("scoped_card_meta", meta.get("card_count") == 1)


def main() -> None:
    test_extractor_v2()
    test_poll_constants()
    test_placeholder_card_rejected()
    test_newest_card_preferred()
    test_poll_waits_instead_of_immediate_fail()
    test_no_generate_click_during_recovery()
    test_valid_mp4_accepted()
    test_report_includes_poll_attempts()
    test_scoped_card_resolver_mock()
    print("validate_kling_single_clip_mp4_recovery_wait: all checks passed")


if __name__ == "__main__":
    main()
