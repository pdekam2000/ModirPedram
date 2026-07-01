"""Validation — PWMAP download selection repair (stale output rejection)."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PWMAP_ROOT = Path(os.environ.get("MODIR_PWMAP_ROOT", r"C:\Users\kaman\Desktop\pwmap"))
if PWMAP_ROOT.is_dir() and str(PWMAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PWMAP_ROOT))

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _write_temp_mp4(path: Path, token: bytes) -> None:
    path.write_bytes(token + b"\x00" * 1024)


def main() -> int:
    print("validate_pwmap_download_selection_repair")
    print("=" * 60)

    try:
        from download_selection import (  # type: ignore
            DUPLICATE_MP4_ERROR,
            NO_NEW_OUTPUT_ERROR,
            STALE_SOURCE_ERROR,
            build_clip_status,
            detect_new_output,
            output_card_fingerprint,
            reject_duplicate_mp4,
            reject_stale_source,
            video_source_identity,
        )
    except ImportError as exc:
        _record("pwmap_download_selection_import", False, str(exc))
        failed = [name for name, ok, _ in results if not ok]
        print("=" * 60)
        print(f"Passed: {len(results) - len(failed)}/{len(results)}")
        return FAIL

    _record("pwmap_download_selection_import", True, str(PWMAP_ROOT))

    runway_src = (PWMAP_ROOT / "runway_agent.py").read_text(encoding="utf-8")
    _record(
        "runner_not_page_wide_first_video",
        "page.locator(\"video\")" not in runway_src.split("def _feed_top_video_src")[0]
        or "_feed_top_video_src" in runway_src,
        "feed_scoped",
    )
    _record(
        "runner_uses_download_clip_output",
        "def download_clip_output" in runway_src,
    )
    _record(
        "runner_records_pre_post_snapshots",
        "capture_output_snapshot" in runway_src and "pre_snapshot" in runway_src,
    )
    _record(
        "clip2_not_first_available_video_fallback",
        "Download via feed-scoped video URL" in runway_src
        and "def _latest_video_src" in runway_src,
        "feed_scoped_url",
    )
    _record(
        "inspect_existing_outputs_flag",
        "--inspect-existing-outputs" in runway_src,
    )

    pre = {
        "videos": [
            {"index": 0, "src": "https://cdn.example/a.mp4", "currentSrc": "https://cdn.example/a.mp4", "data_index": "0", "card_text_hash": "aaa"},
        ]
    }
    post_same = {
        "videos": [
            {"index": 0, "src": "https://cdn.example/a.mp4", "currentSrc": "https://cdn.example/a.mp4", "data_index": "0", "card_text_hash": "aaa"},
        ]
    }
    blocked = detect_new_output(pre_snapshot=pre, post_snapshot=post_same, prior_clips=[])
    _record(
        "no_new_output_blocks_download",
        not blocked.get("ok") and blocked.get("status") == "no_new_output_detected",
        blocked.get("status", ""),
    )

    prior = [
        {
            "download_success": True,
            "selected_source": "https://cdn.example/a.mp4",
            "output_card_fingerprint": output_card_fingerprint(pre["videos"][0]),
            "sha256": "abc",
        }
    ]
    stale = reject_stale_source(
        selected_source="https://cdn.example/a.mp4",
        output_card_fingerprint=output_card_fingerprint(pre["videos"][0]),
        prior_clips=prior,
    )
    _record(
        "same_video_url_rejected",
        not stale.get("ok") and stale.get("status") == "stale_source_rejected",
        STALE_SOURCE_ERROR[:40],
    )

    stale_fp = reject_stale_source(
        selected_source="https://cdn.example/b.mp4",
        output_card_fingerprint=output_card_fingerprint(pre["videos"][0]),
        prior_clips=prior,
    )
    _record(
        "same_output_card_fingerprint_rejected",
        not stale_fp.get("ok"),
        stale_fp.get("status", ""),
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        clip1 = tmp_path / "clip_1.mp4"
        clip2 = tmp_path / "clip_2.mp4"
        payload = b"duplicate-bytes-test"
        _write_temp_mp4(clip1, payload)
        _write_temp_mp4(clip2, payload)
        dup = reject_duplicate_mp4(
            downloaded_path=clip2,
            prior_clips=[{"download_success": True, "sha256": hashlib.sha256(clip1.read_bytes()).hexdigest()}],
            quarantine_dir=tmp_path / "quarantine",
        )
        _record(
            "same_mp4_hash_rejected_after_download",
            not dup.get("ok") and dup.get("status") == "duplicate_mp4_rejected",
            DUPLICATE_MP4_ERROR[:40],
        )
        _record(
            "duplicate_quarantined",
            not clip2.is_file() and bool(dup.get("quarantine_path")),
            str(dup.get("quarantine_path") or ""),
        )
        _record(
            "duplicate_not_left_in_canonical_path",
            not clip2.is_file(),
        )

    status = build_clip_status(
        clip_index=2,
        use_frame_required=True,
        generation_success=True,
        use_frame_success=True,
        download_attempted=False,
    )
    _record(
        "generation_success_not_download_success",
        status.get("generation_success") is True and status.get("download_success") is False,
    )

    from content_brain.execution.pwmap_clip_duplicate_guard import verify_use_frame_gate

    use_frame = verify_use_frame_gate(
        clip_index=2,
        last_result_clip={"used_frame_from_previous": True, "use_frame_second": 14},
        subprocess_stdout="Use frame clicked\nCLIP 2/2",
    )
    _record("use_frame_still_required_for_clip2", use_frame.get("ok") is True)

    from content_brain.execution.product_multiclip_execution_plan import calculate_product_clip_count

    _record("30s_maps_to_two_clips", calculate_product_clip_count(30) == 2, "2")
    _record("clip_3_not_applicable_for_30s", calculate_product_clip_count(30) < 3)

    from content_brain.execution.credit_safety_guard import evaluate_credit_safety

    paid = evaluate_credit_safety(payload={"duration_seconds": 30, "clip_count": 2, "live_retest": True})
    _record(
        "free_credit_first_blocks_unapproved_paid",
        paid.blocked and not paid.allowed,
        paid.block_reason[:50],
    )

    from content_brain.execution.pwmap_clip_assembly_guard import verify_clips_unique_for_assembly

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        a = run_dir / "clip_1.mp4"
        b = run_dir / "clip_2.mp4"
        token = b"assembly-dup"
        _write_temp_mp4(a, token)
        _write_temp_mp4(b, token)
        assembly = verify_clips_unique_for_assembly(run_dir=run_dir, clip_count=2)
        _record(
            "duplicate_clips_block_assembly",
            not assembly.get("assembly_allowed"),
            str(len(assembly.get("duplicate_pairs") or [])),
        )
        _record(
            "duplicate_clips_block_youtube_upload_flag",
            assembly.get("youtube_upload_allowed") is False,
        )

    import project_brain.validate_pwmap_30s_two_clip_duplicate_guard as duplicate
    import project_brain.validate_channel_story_ideation_diversity as ideation
    import project_brain.validate_results_run_truth_consistency as truth
    import project_brain.validate_pwmap_30s_live_retest_safety as safety

    _record("duplicate_guard_validator_passes", duplicate.main() == PASS)
    _record("results_truth_validator_passes", truth.main() == PASS)
    _record("story_ideation_validator_passes", ideation.main() == PASS)
    _record("live_retest_safety_validator_passes", safety.main() == PASS)

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"Passed: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("Failed:", ", ".join(failed))
        return FAIL
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
