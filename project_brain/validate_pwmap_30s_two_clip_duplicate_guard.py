"""Validation — 30s two-clip duplicate guard (pwmap clip registration)."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.product_multiclip_execution_plan import (  # noqa: E402
    PRODUCT_DURATION_PRESETS,
    calculate_product_clip_count,
)
from content_brain.execution.pwmap_clip_duplicate_guard import (  # noqa: E402
    DUPLICATE_ERROR,
    apply_pwmap_clip_registration_guards,
    verify_clip_not_duplicate,
    verify_download_freshness,
    verify_use_frame_gate,
)
from content_brain.platform.run_truth_resolver import analyze_clip_duplicate_status  # noqa: E402
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []
FORENSIC_RUN_ID = "pwmap_20260628T123316_297556ee"
FORENSIC_RUN_DIR = ROOT / "outputs" / "pwmap_agent_runs" / FORENSIC_RUN_ID


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _write_min_mp4(path: Path, token: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"\x00" * 1_000_100 + token
    path.write_bytes(payload)


def main() -> int:
    print("validate_pwmap_30s_two_clip_duplicate_guard")
    print("=" * 60)

    _record("30s_maps_to_two_clips", calculate_product_clip_count(30) == 2, str(PRODUCT_DURATION_PRESETS.get(30)))
    _record("30s_preset_is_two", PRODUCT_DURATION_PRESETS.get(30) == 2)

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        clip1 = run_dir / "clip_1.mp4"
        clip2 = run_dir / "clip_2.mp4"
        _write_min_mp4(clip1, b"clip-a")
        _write_min_mp4(clip2, b"clip-b")

        last_result = {
            "clip_count": 2,
            "clips": [
                {"clip": 1, "download": str(clip1), "used_frame_from_previous": False, "finished_at": "2026-06-28 14:45:10"},
                {
                    "clip": 2,
                    "download": str(clip2),
                    "used_frame_from_previous": True,
                    "use_frame_second": 14.0,
                    "finished_at": "2026-06-28 15:01:09",
                },
            ],
        }
        stdout = (
            "CLIP 1/2\n[OK] Downloaded\n"
            "CLIP 2/2\n[step] Use frame from previous clip\n[OK] Use frame clicked (last frame).\n[OK] Downloaded\n"
        )
        copied = [
            {"clip": 1, "modir_path": str(clip1), "valid": True, "size_bytes": clip1.stat().st_size},
            {"clip": 2, "modir_path": str(clip2), "valid": True, "size_bytes": clip2.stat().st_size},
        ]
        guard_ok = apply_pwmap_clip_registration_guards(
            copied_clips=copied,
            last_result=last_result,
            subprocess_stdout=stdout,
            expected_clip_count=2,
        )
        _record(
            "different_hashes_pass_duplicate_guard",
            guard_ok.get("valid_clip_count") == 2 and not guard_ok.get("duplicate_chain_failed"),
            str(guard_ok.get("valid_clip_count")),
        )

        clip2.write_bytes(clip1.read_bytes())
        guard_dup = apply_pwmap_clip_registration_guards(
            copied_clips=copied,
            last_result=last_result,
            subprocess_stdout=stdout,
            expected_clip_count=2,
        )
        _record(
            "identical_hashes_detected",
            guard_dup.get("duplicate_chain_failed") is True,
            str(guard_dup.get("duplicate_pairs")),
        )
        guarded = guard_dup.get("guarded_clips") or []
        clip2_entry = guarded[1] if len(guarded) > 1 else {}
        _record(
            "duplicate_clip_marked_duplicate_failed",
            clip2_entry.get("status") == "duplicate_failed",
            str(clip2_entry.get("status")),
        )
        _record(
            "duplicate_error_message",
            DUPLICATE_ERROR in str(clip2_entry.get("error") or ""),
            str(clip2_entry.get("error") or "")[:80],
        )

    _record(
        "missing_clip_3_not_failure_for_30s",
        guard_dup.get("clip_3_not_applicable") is True and guard_dup.get("expected_clip_count") == 2,
        f"expected={guard_dup.get('expected_clip_count')}",
    )

    stale = verify_download_freshness(
        clip_index=2,
        clip_path=FORENSIC_RUN_DIR / "clip_2.mp4",
        prior_clips=[{"clip": 1, "sha256": hashlib.sha256((FORENSIC_RUN_DIR / "clip_1.mp4").read_bytes()).hexdigest()}],
        last_result_clip={"finished_at": "2026-06-28 14:45:10"},
    )
    _record(
        "stale_download_marked_ambiguous_or_duplicate",
        stale.get("download_status") in {"ambiguous_stale_output", "duplicate_hash"} or stale.get("status") in {"duplicate_hash", "ambiguous_stale_output"},
        str(stale.get("status")),
    )

    use_frame_missing = verify_use_frame_gate(
        clip_index=2,
        last_result_clip={"used_frame_from_previous": False},
        subprocess_stdout="CLIP 2/2\n",
    )
    _record(
        "use_frame_missing_blocks_clip_2",
        use_frame_missing.get("ok") is False,
        str(use_frame_missing.get("status")),
    )

    if FORENSIC_RUN_DIR.is_dir():
        disk_clips = [
            {"clip_index": 1, "path": str(FORENSIC_RUN_DIR / "clip_1.mp4")},
            {"clip_index": 2, "path": str(FORENSIC_RUN_DIR / "clip_2.mp4")},
        ]
        analysis = analyze_clip_duplicate_status(disk_clips)
        _record(
            "forensic_run_duplicate_chain_failed",
            analysis.get("duplicate_chain_failed") is True,
            str(analysis.get("duplicate_pairs")),
        )

        service = ProductStudioService(ROOT)
        merged = service._merge_pwmap_results(
            {
                "run_id": FORENSIC_RUN_ID,
                "selected_run_id": FORENSIC_RUN_ID,
                "run_dir": str(FORENSIC_RUN_DIR).replace("\\", "/"),
                "is_product_studio_pwmap": True,
                "expected_clip_count": 2,
                "multiclip_execution_plan": {"clip_count": 2, "requested_duration_seconds": 30, "duration_seconds": 30},
                "visual_diversity": __import__("json").loads(
                    (FORENSIC_RUN_DIR / "visual_diversity_report.json").read_text(encoding="utf-8")
                ),
            }
        )
        _record(
            "duplicate_candidate_not_approved",
            not merged.get("video_approved") and merged.get("duplicate_chain_failed") is True,
            f"approved={merged.get('video_approved')}",
        )
        _record(
            "visual_diversity_block_remains",
            merged.get("youtube_upload_allowed") is False,
            str(merged.get("youtube_upload_allowed")),
        )
        _record(
            "results_clip_3_not_applicable",
            merged.get("clip_3_not_applicable") is True,
            str(merged.get("clip_3_status")),
        )
        _record(
            "results_requested_two_downloaded_two",
            int(merged.get("expected_clip_count") or 0) == 2 and int(merged.get("downloaded_clip_count") or 0) == 2,
            f"req={merged.get('expected_clip_count')} dl={merged.get('downloaded_clip_count')}",
        )

    import project_brain.validate_results_run_truth_consistency as truth_validator  # noqa: E402

    truth_exit = truth_validator.main()
    _record("results_truth_validator_passes", truth_exit == PASS, str(truth_exit))

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"Passed: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("Failed:", ", ".join(failed))
        return FAIL
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
