"""PHASE DELIVERY-TRUTH-1 validation — canonical run sync + final MP4 audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.canonical_run import load_canonical_run, save_canonical_run, sync_canonical_run_from_index
from content_brain.platform.delivery_truth_loader import build_delivery_truth_panel
from content_brain.platform.final_delivery_registry import load_final_delivery_registry, save_final_delivery_registry
from content_brain.platform.results_run_loader import load_run_results
from content_brain.quality.delivery_reality_auditor import audit_final_mp4_delivery
from project_brain.archive_stale_delivery_artifacts import archive_stale_delivery_artifacts

VALIDATION_TOPIC = "Sunrise coastal kayak guide for beginners"
VALIDATION_RUN_ID = "cb_delivery_truth_1_validation"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("PHASE DELIVERY-TRUTH-1 — validation")
    print("=" * 60)

    archive_report = archive_stale_delivery_artifacts(ROOT)
    print(f"Archived to: {archive_report.get('archive_dir')}")

    canonical = sync_canonical_run_from_index(ROOT)
    _pass("canonical_run_set", bool(canonical.get("run_id")), str(canonical.get("run_id")))

    registry = load_final_delivery_registry(ROOT)
    registry["approved"] = False
    registry["delivery_reality_passed"] = False
    if str(registry.get("latest_run_id") or "") != str(canonical.get("run_id") or ""):
        registry["latest_run_id"] = str(canonical.get("run_id") or "")
        registry["latest_video"] = ""
        registry["latest_publish_package"] = ""
    save_final_delivery_registry(ROOT, registry)
    _pass("registry_unapproved", not registry.get("approved"))

    archived_cat_video = None
    for item in archive_report.get("moved") or []:
        target = str(item.get("target") or "")
        if target.endswith("FINAL_BRANDED_VIDEO_v4.mp4"):
            archived_cat_video = target
            break

    if archived_cat_video and Path(archived_cat_video).is_file():
        cat_audit = audit_final_mp4_delivery(archived_cat_video).to_dict()
        print("\nArchived cat MP4 audit (truth baseline):")
        print(json.dumps(cat_audit, indent=2))
        _pass("cat_mp4_audit_ran", cat_audit.get("status") in {"PASS", "FAIL"})
        if cat_audit.get("status") == "PASS":
            print("WARNING: archived cat MP4 unexpectedly passed full delivery audit")

    save_canonical_run(
        ROOT,
        {
            **canonical,
            "validation_topic": VALIDATION_TOPIC,
            "validation_run_id": VALIDATION_RUN_ID,
            "validation_note": "Full Runway pipeline required for new-topic validation run.",
        },
    )

    results = load_run_results(ROOT)
    _pass("results_loader_ok", isinstance(results, dict))
    _pass(
        "single_canonical_run_id",
        results.get("canonical_run_id") == results.get("selected_run_id")
        or results.get("canonical_run_id") == results.get("latest_attempt_run_id"),
        f"canonical={results.get('canonical_run_id')} selected={results.get('selected_run_id')}",
    )
    _pass("no_stale_cat_approved", not results.get("approved_run_id") or results.get("approved_run_id") == results.get("canonical_run_id"))

    delivery_truth = build_delivery_truth_panel(ROOT)
    print("\nCanonical delivery truth:")
    print(json.dumps(delivery_truth, indent=2))

    report = {
        "run_id": str(canonical.get("run_id") or ""),
        "topic": str(canonical.get("topic") or ""),
        "validation_topic": VALIDATION_TOPIC,
        "final_video_path": delivery_truth.get("final_video_path") or "",
        "subtitle_audit": delivery_truth.get("checks", {}).get("subtitles"),
        "music_audit": delivery_truth.get("checks", {}).get("music"),
        "ambience_audit": delivery_truth.get("checks", {}).get("ambience"),
        "dialogue_audit": delivery_truth.get("checks", {}).get("dialogue"),
        "voice_separation_result": delivery_truth.get("checks", {}).get("voice_separation"),
        "story_quality_result": delivery_truth.get("checks", {}).get("story_quality"),
        "approved": bool(delivery_truth.get("approved")),
        "delivery_truth_status": delivery_truth.get("status"),
        "archive_dir": archive_report.get("archive_dir"),
    }
    out_path = ROOT / "project_brain" / "DELIVERY_TRUTH_1_VALIDATION.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nValidation report written:", out_path)
    print(json.dumps(report, indent=2))
    print("=" * 60)
    print("DELIVERY-TRUTH-1 validation complete")


if __name__ == "__main__":
    main()
