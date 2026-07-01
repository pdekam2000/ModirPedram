"""Validation — Results run truth consistency (disk-backed counts, delivery audit, labels)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.delivery_truth_loader import (  # noqa: E402
    build_delivery_truth_panel,
    resolve_audit_mp4_for_run,
)
from content_brain.platform.run_truth_resolver import (  # noqa: E402
    compute_video_approval_state,
    discover_pwmap_clip_files,
    enrich_pwmap_results_truth,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []

FORENSIC_RUN_ID = "pwmap_20260628T123316_297556ee"


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    print("validate_results_run_truth_consistency")
    print("=" * 60)

    run_dir = ROOT / "outputs" / "pwmap_agent_runs" / FORENSIC_RUN_ID
    run_dir_text = str(run_dir).replace("\\", "/")

    # --- unit: approval label rules ---
    fail_audit = compute_video_approval_state(
        delivery_truth={"status": "FAIL", "approved": False},
        visual_report={"status": "visual_repetition_failed", "youtube_upload_allowed": False},
        publish_package_ready=False,
        candidate_video_path=str(run_dir / "video.mp4"),
    )
    _record(
        "unapproved_candidate_label",
        fail_audit["video_display_label"] == "Unapproved Candidate Video"
        and not fail_audit["latest_approved_video_path"]
        and bool(fail_audit["latest_candidate_video_path"]),
        fail_audit["video_display_label"],
    )

    pass_all = compute_video_approval_state(
        delivery_truth={"status": "PASS", "approved": True},
        visual_report={"status": "ok", "youtube_upload_allowed": True},
        publish_package_ready=True,
        candidate_video_path="/tmp/final.mp4",
    )
    _record(
        "approved_label_only_when_gates_pass",
        pass_all["video_display_label"] == "Latest Approved Video" and pass_all["approved"],
        pass_all["video_display_label"],
    )

    _record(
        "completed_metadata_cannot_override_failed_delivery",
        not fail_audit["approved"] and fail_audit["audit_pass"] is False,
        f"approved={fail_audit['approved']}",
    )

    # --- disk: forensic run ---
    if run_dir.is_dir():
        clips = discover_pwmap_clip_files(run_dir)
        _record("forensic_two_clip_files", len(clips) == 2, str(len(clips)))
        _record("forensic_no_clip_3", not (run_dir / "clip_3.mp4").is_file())
        _record("forensic_no_publish_package", not (run_dir / "publish" / "publish_package.json").is_file())

        video = run_dir / "video.mp4"
        if video.is_file() and clips:
            clip_hash = _sha256(Path(clips[0]["path"]))
            video_hash = _sha256(video)
            _record(
                "forensic_visual_repetition_confirmed",
                clip_hash == video_hash,
                f"sha256={clip_hash[:16]}…",
            )

        audit_target, audit_kind = resolve_audit_mp4_for_run(run_dir, project_root=ROOT)
        _record(
            "existing_readable_video_audited",
            audit_target is not None
            and audit_kind == "candidate"
            and audit_target.name == "video.mp4"
            and FORENSIC_RUN_ID in str(audit_target),
            f"kind={audit_kind} path={audit_target}",
        )

        panel = build_delivery_truth_panel(ROOT, run_id=FORENSIC_RUN_ID, run_dir=run_dir_text)
        _record(
            "delivery_truth_has_checks_when_mp4_exists",
            bool(panel.get("final_video_path"))
            and FORENSIC_RUN_ID in str(panel.get("final_video_path") or "")
            and bool(panel.get("checks")),
            str(panel.get("final_video_path") or "missing"),
        )
        _record(
            "delivery_truth_not_empty_missing_message",
            panel.get("failures") != ["final_mp4_missing"],
            str(panel.get("failures")),
        )

        visual_report = json.loads((run_dir / "visual_diversity_report.json").read_text(encoding="utf-8"))
        service = ProductStudioService(ROOT)
        merged = service._merge_pwmap_results(
            {
                "run_id": FORENSIC_RUN_ID,
                "selected_run_id": FORENSIC_RUN_ID,
                "run_dir": run_dir_text,
                "run_folder": run_dir_text,
                "is_product_studio_pwmap": True,
                "clip_count": 2,
                "expected_clip_count": 2,
                "video_path": str(video),
                "metadata": {"status": "completed", "clip_count": 2},
                "visual_diversity": visual_report,
            }
        )
        _record(
            "merge_downloaded_clip_count_two",
            int(merged.get("downloaded_clip_count") or 0) == 2,
            str(merged.get("downloaded_clip_count")),
        )
        _record(
            "merge_not_latest_approved_when_unapproved",
            not merged.get("video_approved") and merged.get("video_display_label") == "Unapproved Candidate Video",
            merged.get("video_display_label", ""),
        )
        _record(
            "merge_clip_counts_not_mixed",
            int(merged.get("latest_attempt_clips_completed") or 0) == 2
            and int(merged.get("downloaded_clip_count") or 0) == 2,
            f"attempt={merged.get('latest_attempt_clips_completed')} downloaded={merged.get('downloaded_clip_count')}",
        )
        _record(
            "visual_diversity_blocks_youtube_upload",
            merged.get("youtube_upload_allowed") is False,
            str(merged.get("youtube_upload_allowed")),
        )
        _record(
            "publish_package_not_shown_without_package",
            not merged.get("publish_package_ready"),
            str(merged.get("publish_package_ready")),
        )
        _record(
            "no_contradictory_completed_failed_status",
            str(merged.get("status")) == "failed" or not merged.get("video_approved"),
            f"status={merged.get('status')} approved={merged.get('video_approved')}",
        )
        _record(
            "delivery_truth_status_present",
            bool(merged.get("delivery_truth_checks")),
            str(len(merged.get("delivery_truth_checks") or {})),
        )
    else:
        _record("forensic_run_dir_present", False, str(run_dir))

    # --- synthetic: missing video ---
    with patch(
        "content_brain.platform.run_truth_resolver.resolve_candidate_video_path",
        return_value="",
    ):
        synthetic = enrich_pwmap_results_truth(
            ROOT,
            {
                "run_id": "synthetic_missing",
                "run_dir": "/nonexistent/run",
                "latest_run_attempt": {"status": "failed", "message": "partial_finalization"},
                "status": "completed",
                "clip_count": 2,
            },
            run_dir="/nonexistent/run",
            run_id="synthetic_missing",
        )
    _record(
        "missing_video_no_approved_path",
        not synthetic.get("latest_approved_video_path") and not synthetic.get("video_approved"),
    )
    _record(
        "missing_video_unified_status_not_completed_override",
        str(synthetic.get("status")) != "completed" or not synthetic.get("video_approved"),
        str(synthetic.get("status")),
    )

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"Passed: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("Failed:", ", ".join(failed))
        return FAIL
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
