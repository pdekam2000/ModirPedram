"""PHASE DELIVERY-CANONICAL-1 — one run, one final video, one truth."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.asset_library import register_published_asset, sha256_file  # noqa: E402
from content_brain.platform.canonical_delivery import (  # noqa: E402
    CANONICAL_BRANDED_VIDEO_NAME,
    archive_superseded_branded_variants,
    canonical_publish_path,
    list_superseded_branded_files,
    promote_canonical_final_video,
    resolve_canonical_final_video,
)
from content_brain.platform.canonical_run import load_canonical_run  # noqa: E402
from content_brain.platform.delivery_truth_loader import build_delivery_truth_panel  # noqa: E402
from content_brain.platform.final_delivery_registry import (  # noqa: E402
    load_final_delivery_registry,
    save_final_delivery_registry,
    try_update_final_delivery_registry,
)
from content_brain.platform.results_run_loader import load_run_results  # noqa: E402
from content_brain.quality.delivery_reality_auditor import audit_final_mp4_delivery  # noqa: E402

REPORT_PATH = ROOT / "project_brain" / "DELIVERY_CANONICAL_REPORT.md"


def _pick_source_video(publish_dir: Path) -> Path:
    candidates = [
        publish_dir / "FINAL_BRANDED_VIDEO_subtitle_fixed.mp4",
        publish_dir / CANONICAL_BRANDED_VIDEO_NAME,
        publish_dir / "FINAL_BRANDED_VIDEO.mp4",
        publish_dir.parent / "final" / "FINAL_BRANDED_VIDEO.mp4",
    ]
    registry = load_final_delivery_registry(ROOT)
    reg_path = str(registry.get("canonical_final_video_path") or registry.get("latest_video") or "")
    if reg_path:
        candidates.insert(0, Path(reg_path))
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return path.resolve()
    raise FileNotFoundError("no_branded_source_for_canonical_promotion")


def _sync_publish_metadata(publish_dir: Path, *, run_id: str, canonical_path: Path) -> None:
    metadata_path = publish_dir / "metadata.json"
    payload: dict = {}
    if metadata_path.is_file():
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload["branded_video_path"] = str(canonical_path.resolve())
    payload["branded_video_name"] = CANONICAL_BRANDED_VIDEO_NAME
    payload["canonical_final_video_path"] = str(canonical_path.resolve())
    payload["run_id"] = run_id
    metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_report(body: str) -> None:
    REPORT_PATH.write_text(body, encoding="utf-8")


def main() -> int:
    canonical = load_canonical_run(ROOT)
    run_id = str(canonical.get("run_id") or "")
    topic = str(canonical.get("topic") or "")
    run_dir = Path(str(canonical.get("run_dir") or "")).resolve()
    publish_dir = Path(str(canonical.get("publish_dir") or run_dir / "publish")).resolve()

    before_superseded = [str(p) for p in list_superseded_branded_files(publish_dir, run_dir / "final")]
    source = _pick_source_video(publish_dir)
    canonical_path = promote_canonical_final_video(
        source,
        publish_dir=publish_dir,
        archive_superseded=True,
        run_id=run_id,
    )
    archive_superseded_branded_variants(
        publish_dir=publish_dir,
        final_dir=run_dir / "final",
        run_id=run_id,
    )
    after_superseded = [str(p) for p in list_superseded_branded_files(publish_dir, run_dir / "final")]

    audit = audit_final_mp4_delivery(canonical_path)
    _sync_publish_metadata(publish_dir, run_id=run_id, canonical_path=canonical_path)

    assembly_status = "ASSEMBLED"
    summary_path = run_dir / "metadata" / "run_summary.json"
    if summary_path.is_file():
        try:
            assembly_status = str(json.loads(summary_path.read_text(encoding="utf-8")).get("assembly_status") or assembly_status)
        except (OSError, json.JSONDecodeError):
            pass

    updated, registry, reason = try_update_final_delivery_registry(
        ROOT,
        run_id=run_id,
        canonical_final_video_path=canonical_path,
        latest_publish_package=publish_dir,
        approved=audit.status == "PASS",
        topic=topic,
        clips_completed=2,
        assembly_status=assembly_status,
        reality_audit_passed=audit.status == "PASS",
        force=True,
    )
    if not updated:
        registry = load_final_delivery_registry(ROOT)
        registry.update(
            {
                "latest_run_id": run_id,
                "canonical_final_video_path": str(canonical_path),
                "latest_publish_package": str(publish_dir),
                "approved": audit.status == "PASS",
                "delivery_reality_passed": audit.status == "PASS",
                "topic": topic,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        save_final_delivery_registry(ROOT, registry)

    publish_manifest = {
        "status": "PUBLISHED_PACKAGE_CREATED",
        "branded_video_path": str(canonical_path),
        "branded_video_name": CANONICAL_BRANDED_VIDEO_NAME,
        "duration_seconds": audit.metrics.get("duration_seconds"),
    }
    asset_result = register_published_asset(
        ROOT,
        publish_manifest=publish_manifest,
        run_id=run_id,
        topic=topic,
        run_dir=run_dir,
        assembly_manifest={"clip_count": 2, "status": assembly_status},
    )
    if asset_result.get("status") == "registered" and asset_result.get("final_video_path"):
        registry = load_final_delivery_registry(ROOT)
        registry["latest_asset"] = str(asset_result["final_video_path"])
        save_final_delivery_registry(ROOT, registry)

    delivery_truth = build_delivery_truth_panel(ROOT, run_id=run_id, run_dir=str(run_dir))
    results = load_run_results(ROOT, run_id=run_id)

    report_lines = [
        "# DELIVERY CANONICAL REPORT",
        "",
        f"- **Completed:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Run ID:** `{run_id}`",
        f"- **Topic:** {topic}",
        "",
        "## Canonical rule",
        "",
        f"Only **`{CANONICAL_BRANDED_VIDEO_NAME}`** is the final deliverable. Superseded branded variants are archived under `storage/archive/delivery_canonical_1/`.",
        "",
        "## Promotion",
        "",
        f"- **Source:** `{source}`",
        f"- **Canonical path:** `{canonical_path}`",
        f"- **Registry update:** `{reason}` / updated={updated}",
        "",
        "## Archive",
        "",
        f"- Superseded files before: {len(before_superseded)}",
        f"- Superseded files after (should be 0 in publish/final): {len(after_superseded)}",
        "",
        "## Audit",
        "",
        f"- **MP4 audit:** `{audit.status}` — failures: `{audit.failures}`",
        f"- **Delivery truth panel:** `{delivery_truth.get('status')}` — approved: `{delivery_truth.get('approved')}`",
        f"- **Results topic:** `{results.get('topic')}`",
        f"- **Results delivery_truth_status:** `{results.get('delivery_truth_status')}`",
        f"- **Results approved_run_id:** `{results.get('approved_run_id')}`",
        "",
        "## Asset library",
        "",
        f"- **Register status:** `{asset_result.get('status')}`",
        f"- **Vault path:** `{asset_result.get('final_video_path', '')}`",
        f"- **Checksum:** `{asset_result.get('checksum_sha256', '')}`",
        "",
        "## Registry",
        "",
        "```json",
        json.dumps(load_final_delivery_registry(ROOT), indent=2, ensure_ascii=False),
        "```",
    ]
    _write_report("\n".join(report_lines) + "\n")

    print(
        json.dumps(
            {
                "canonical_path": str(canonical_path),
                "audit_status": audit.status,
                "delivery_truth_status": delivery_truth.get("status"),
                "results_approved_run_id": results.get("approved_run_id"),
            },
            indent=2, ensure_ascii=False)
    )
    return 0 if audit.status == "PASS" and delivery_truth.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
