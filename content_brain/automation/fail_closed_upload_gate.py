"""Fail-closed automation upload gate — block partial/incomplete publish chains."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from content_brain.execution.pwmap_clip_assembly_guard import verify_clips_unique_for_assembly
from content_brain.execution.product_subtitle_branding_publish import FINAL_BRANDED_PUBLISH_READY_NAME
from content_brain.publish.youtube_metadata_generator import YOUTUBE_METADATA_FILENAME

GATE_VERSION = "fail_closed_upload_gate_v1"
ASSEMBLY_BLOCKED_STATUS = "blocked_duplicate_or_missing_clips"


def resolve_run_dir(project_root: str | Path, run_id: str, report: dict[str, Any]) -> Path | None:
    run_dir_text = str(report.get("run_dir") or report.get("output_folder") or "")
    if run_dir_text:
        candidate = Path(run_dir_text)
        if candidate.is_dir():
            return candidate
    if run_id:
        root = Path(project_root).resolve()
        for candidate in (
            root / "outputs" / "pwmap_agent_runs" / run_id,
            root / "outputs" / "runs" / run_id,
        ):
            if candidate.is_dir():
                return candidate
    return None


def resolve_publish_dir(report: dict[str, Any], run_dir: Path | None) -> Path | None:
    publish_text = str(
        report.get("publish_package_path")
        or report.get("final_publish_package")
        or ""
    ).strip()
    if publish_text:
        candidate = Path(publish_text)
        if candidate.is_dir():
            return candidate
        if candidate.parent.is_dir() and candidate.name.endswith(".json"):
            return candidate.parent
    if run_dir:
        publish = run_dir / "publish"
        if publish.is_dir():
            return publish
    return None


def _planned_clip_count(report: dict[str, Any], planned_clip_count: int) -> int:
    if planned_clip_count > 0:
        return int(planned_clip_count)
    for key in ("expected_clip_count", "clip_count"):
        value = int(report.get(key) or 0)
        if value > 0:
            return value
    multiclip = dict(report.get("multiclip_execution_plan") or {})
    return int(multiclip.get("clip_count") or 0)


def _completed_clip_count(report: dict[str, Any], run_dir: Path | None, planned: int) -> int:
    completed = int(report.get("clips_completed") or 0)
    if completed <= 0:
        completed = len(report.get("clips") or [])
    if completed <= 0 and run_dir and planned > 0:
        completed = sum(
            1 for index in range(1, planned + 1) if (run_dir / f"clip_{index}.mp4").is_file()
        )
    return completed


def evaluate_automation_upload_gate(
    *,
    project_root: str | Path,
    generation_report: dict[str, Any] | None,
    run_id: str = "",
    planned_clip_count: int = 0,
    publish_package_path: str = "",
) -> tuple[bool, str]:
    """Return (allowed, reason). Upload only when the full publish chain succeeded."""
    report = dict(generation_report or {})
    run_status = str(report.get("status") or "").strip().lower()
    resolved_run_id = str(run_id or report.get("run_id") or report.get("session_id") or "")
    planned = _planned_clip_count(report, planned_clip_count)
    run_dir = resolve_run_dir(project_root, resolved_run_id, report)

    if report.get("ok") is False or run_status in {
        "partial_failed",
        "partial",
        "failed",
        "duplicate_failed",
        "publish_chain_failed",
        "visual_repetition_failed",
    }:
        return False, "blocked_partial_failed"

    if run_status and run_status not in {"completed", "ok"}:
        return False, "blocked_partial_failed"

    if report.get("youtube_upload_allowed") is False:
        return False, "blocked_partial_failed"

    completed = _completed_clip_count(report, run_dir, planned)
    if planned > 0 and completed != planned:
        return False, "blocked_missing_clip"

    if run_dir and planned > 0:
        guard = verify_clips_unique_for_assembly(run_dir=run_dir, clip_count=planned)
        if not guard.get("assembly_allowed"):
            if guard.get("duplicate_pairs"):
                return False, "blocked_duplicate_clips"
            return False, "blocked_missing_clip"

    merge_info = dict(report.get("merge_info") or {})
    assembly_status = str(report.get("assembly_status") or merge_info.get("assembly_status") or "")
    assembly_complete = bool(report.get("assembly_complete"))
    if planned > 1:
        if assembly_status == ASSEMBLY_BLOCKED_STATUS:
            return False, "blocked_missing_assembly"
        if merge_info.get("duplicate_chain_failed"):
            return False, "blocked_duplicate_clips"
        if not merge_info.get("merged") and not assembly_complete:
            return False, "blocked_missing_assembly"
        if assembly_status and assembly_status not in {"completed", "assembly_complete"}:
            return False, "blocked_missing_assembly"

    branding_status = str(report.get("branding_status") or "")
    if branding_status and branding_status not in {"completed", "branding_complete"}:
        return False, "blocked_missing_branding"

    publish_ready = bool(report.get("publish_ready") or report.get("publish_package_ready"))
    if not publish_ready:
        return False, "blocked_publish_not_ready"

    publish_dir = resolve_publish_dir(report, run_dir)
    if publish_package_path:
        candidate = Path(publish_package_path)
        if candidate.is_dir():
            publish_dir = candidate

    branded_path = ""
    if str(report.get("final_branded_publish_video_path") or "").strip():
        branded_path = str(report["final_branded_publish_video_path"])
    elif publish_dir:
        candidate = publish_dir / FINAL_BRANDED_PUBLISH_READY_NAME
        if candidate.is_file():
            branded_path = str(candidate)

    if not branded_path or not Path(branded_path).is_file():
        return False, "blocked_missing_branding"

    metadata_path = str(report.get("youtube_metadata_path") or "")
    if not metadata_path and publish_dir:
        candidate = publish_dir / YOUTUBE_METADATA_FILENAME
        if candidate.is_file():
            metadata_path = str(candidate)
    if not metadata_path or not Path(metadata_path).is_file():
        return False, "blocked_publish_not_ready"

    return True, "ok"


__all__ = [
    "ASSEMBLY_BLOCKED_STATUS",
    "GATE_VERSION",
    "evaluate_automation_upload_gate",
    "resolve_publish_dir",
    "resolve_run_dir",
]
