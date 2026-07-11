"""Recover post-processing for the latest live Runway report without re-running Runway."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_live_post_processor import (  # noqa: E402
    collect_valid_download_paths,
    evaluate_post_processing_eligibility,
    run_live_post_processing,
)


def _candidate_report_paths(project_root: Path) -> list[Path]:
    return [
        project_root / "project_brain" / "runway_phase_i_3clip_last_report.json",
        project_root / "project_brain" / "runway_live_smoke_last_report.json",
    ]


def load_latest_runway_report(project_root: Path) -> tuple[Path | None, dict[str, Any]]:
    for path in _candidate_report_paths(project_root):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return path, payload
    return None, {}


def persist_runway_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def recover_latest_run_post_processing(project_root: Path | None = None) -> dict[str, Any]:
    root = Path(project_root or ROOT).resolve()
    report_path, report = load_latest_runway_report(root)
    if report_path is None or not report:
        return {"ok": False, "error": "latest_runway_report_not_found"}

    clip_count = int(report.get("clip_count") or 0)
    paths = [str(item) for item in report.get("downloaded_file_paths") or [] if item]
    valid_downloads, missing = collect_valid_download_paths(paths)

    eligible, reason, _context = evaluate_post_processing_eligibility(report)
    summary: dict[str, Any] = {
        "ok": False,
        "report_path": str(report_path),
        "run_id": str(report.get("content_brain_run_id") or ""),
        "clip_count": clip_count,
        "valid_download_count": len(valid_downloads),
        "missing_downloads": missing,
        "eligible_before_run": eligible,
        "eligibility_reason": reason,
    }

    if not eligible:
        summary["error"] = f"post_processing_not_eligible:{reason}"
        return summary

    result = run_live_post_processing(report, project_root=root)
    persist_runway_report(report_path, report)

    summary.update(
        {
            "ok": result.get("status") == "completed",
            "post_processing_status": result.get("status"),
            "assembly_status": result.get("assembly_status"),
            "final_video_path": result.get("final_video_path"),
            "publish_package_status": result.get("publish_package_status"),
            "publish_package_folder": result.get("publish_package_folder"),
            "warnings": list(result.get("warnings") or []),
        }
    )
    return summary


def main() -> int:
    summary = recover_latest_run_post_processing(ROOT)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
