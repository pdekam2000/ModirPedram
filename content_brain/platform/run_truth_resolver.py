"""Canonical run truth resolver — disk-backed counts, candidate vs approved video."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from content_brain.execution.kling_useframe_generation_completion_gate import sha256_file
from content_brain.execution.pwmap_runway_agent_adapter import validate_mp4_path
from content_brain.platform.delivery_truth_loader import build_delivery_truth_panel

RUN_TRUTH_RESOLVER_VERSION = "run_truth_resolver_v1"

CLIP_FILE_PATTERN = re.compile(r"^clip_(\d+)\.mp4$", re.IGNORECASE)
CANDIDATE_VIDEO_NAMES = ("video_merged.mp4", "video.mp4")


def discover_pwmap_clip_files(run_dir: str | Path) -> list[dict[str, Any]]:
    """Return valid clip_N.mp4 artifacts only (never video.mp4)."""
    base = Path(run_dir).resolve()
    if not base.is_dir():
        return []
    clips: list[dict[str, Any]] = []
    for path in sorted(base.iterdir()):
        if not path.is_file():
            continue
        match = CLIP_FILE_PATTERN.match(path.name)
        if not match:
            continue
        verify = validate_mp4_path(path)
        if verify.get("valid"):
            clips.append(
                {
                    "clip_index": int(match.group(1)),
                    "path": str(path.resolve()).replace("\\", "/"),
                    "size_bytes": int(verify.get("size_bytes") or 0),
                }
            )
    return clips


def resolve_candidate_video_path(run_dir: str | Path) -> str:
    base = Path(run_dir).resolve()
    publish = base / "publish"
    for name in ("FINAL_BRANDED_PUBLISH_READY.mp4", "FINAL_PUBLISH_READY.mp4"):
        candidate = publish / name
        if validate_mp4_path(candidate).get("valid"):
            return str(candidate.resolve()).replace("\\", "/")
    for name in CANDIDATE_VIDEO_NAMES:
        candidate = base / name
        if validate_mp4_path(candidate).get("valid"):
            return str(candidate.resolve()).replace("\\", "/")
    return ""


def resolve_publish_package_ready(run_dir: str | Path) -> bool:
    publish = Path(run_dir).resolve() / "publish"
    package = publish / "publish_package.json"
    if not package.is_file():
        return False
    try:
        import json

        payload = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("publish_ready"))


def analyze_clip_duplicate_status(clips: list[dict[str, Any]]) -> dict[str, Any]:
    """Disk-backed per-clip duplicate analysis for Results."""
    from content_brain.execution.pwmap_clip_duplicate_guard import DUPLICATE_ERROR

    statuses: list[dict[str, Any]] = []
    seen_hashes: dict[str, int] = {}
    duplicate_pairs: list[dict[str, Any]] = []
    for item in clips:
        path = str(item.get("path") or "")
        clip_index = int(item.get("clip_index") or 0)
        file_hash = sha256_file(path) if path else ""
        status = "exists"
        if clip_index > 1 and file_hash and file_hash in seen_hashes:
            status = "duplicate_failed"
            duplicate_pairs.append(
                {"clip_a": seen_hashes[file_hash], "clip_b": clip_index, "sha256": file_hash}
            )
        elif file_hash:
            seen_hashes[file_hash] = clip_index
        statuses.append(
            {
                "clip_index": clip_index,
                "path": path,
                "sha256": file_hash,
                "status": status,
                "error": DUPLICATE_ERROR if status == "duplicate_failed" else "",
            }
        )
    duplicate_chain_failed = bool(duplicate_pairs)
    return {
        "clip_statuses": statuses,
        "duplicate_pairs": duplicate_pairs,
        "duplicate_chain_failed": duplicate_chain_failed,
        "duplicate_clips_status": "failed" if duplicate_chain_failed else "pass",
    }


def compute_video_approval_state(
    *,
    delivery_truth: dict[str, Any],
    visual_report: dict[str, Any] | None,
    publish_package_ready: bool,
    candidate_video_path: str,
    duplicate_chain_failed: bool = False,
) -> dict[str, Any]:
    visual = dict(visual_report or {})
    diversity_ok = visual.get("status") != "visual_repetition_failed" and bool(
        visual.get("youtube_upload_allowed", True)
    )
    audit_pass = str(delivery_truth.get("status") or "").upper() == "PASS"
    approved = bool(
        candidate_video_path
        and audit_pass
        and diversity_ok
        and publish_package_ready
        and delivery_truth.get("approved")
        and not duplicate_chain_failed
    )
    if approved:
        label = "Latest Approved Video"
    elif candidate_video_path:
        label = "Unapproved Candidate Video"
    else:
        label = ""
    return {
        "approved": approved,
        "video_display_label": label,
        "latest_approved_video_path": candidate_video_path if approved else "",
        "latest_candidate_video_path": candidate_video_path if not approved else "",
        "diversity_ok": diversity_ok,
        "audit_pass": audit_pass,
        "publish_package_ready": publish_package_ready,
    }


def enrich_pwmap_results_truth(
    project_root: str | Path,
    payload: dict[str, Any],
    *,
    run_dir: str = "",
    run_id: str = "",
    visual_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge disk-backed truth into pwmap Results payload."""
    merged = dict(payload)
    run_dir_text = str(run_dir or merged.get("run_dir") or merged.get("run_folder") or "")
    run_id_text = str(run_id or merged.get("selected_run_id") or merged.get("run_id") or "")
    clips = discover_pwmap_clip_files(run_dir_text) if run_dir_text else []
    duplicate_analysis = analyze_clip_duplicate_status(clips)
    downloaded_clip_count = len(clips)
    selected_duration_seconds = int(
        merged.get("selected_duration_seconds")
        or (merged.get("multiclip_execution_plan") or {}).get("duration_seconds")
        or (merged.get("multiclip_execution_plan") or {}).get("requested_duration_seconds")
        or merged.get("planned_duration_seconds")
        or 0
    )
    requested_clip_count = int(
        merged.get("expected_clip_count")
        or (merged.get("multiclip_execution_plan") or {}).get("clip_count")
        or merged.get("clip_count")
        or downloaded_clip_count
    )
    clip_3_not_applicable = requested_clip_count <= 2
    duplicate_chain_failed = bool(duplicate_analysis.get("duplicate_chain_failed"))
    candidate_video_path = resolve_candidate_video_path(run_dir_text) if run_dir_text else ""
    publish_ready = resolve_publish_package_ready(run_dir_text) if run_dir_text else bool(
        merged.get("publish_package_ready")
    )

    delivery_truth = build_delivery_truth_panel(
        project_root,
        run_id=run_id_text,
        run_dir=run_dir_text,
    )
    approval = compute_video_approval_state(
        delivery_truth=delivery_truth,
        visual_report=visual_report,
        publish_package_ready=publish_ready,
        candidate_video_path=candidate_video_path,
        duplicate_chain_failed=duplicate_chain_failed,
    )

    latest_attempt = dict(merged.get("latest_run_attempt") or {})
    if run_id_text and str(latest_attempt.get("run_id") or "") == run_id_text:
        latest_attempt["clips_completed"] = downloaded_clip_count
        latest_attempt["downloaded_clip_count"] = downloaded_clip_count
    attempt_status = str(latest_attempt.get("status") or merged.get("status") or "")
    partial = bool(
        latest_attempt.get("message") == "partial_finalization"
        or "partial" in attempt_status
        or (downloaded_clip_count > 0 and downloaded_clip_count < requested_clip_count)
    )
    unified_status = attempt_status or (
        "failed"
        if duplicate_chain_failed
        else (
            "completed"
            if approval["approved"]
            else "failed" if partial or not candidate_video_path else str(merged.get("status") or "")
        )
    )

    merged.update(
        {
            "downloaded_clip_count": downloaded_clip_count,
            "clip_count": requested_clip_count,
            "expected_clip_count": requested_clip_count,
            "clips_completed": downloaded_clip_count,
            "latest_attempt_clips_completed": downloaded_clip_count,
            "latest_run_attempt": latest_attempt,
            "status": unified_status,
            "generation_status": unified_status,
            "latest_attempt_status": attempt_status,
            "latest_attempt_message": str(latest_attempt.get("message") or ""),
            "candidate_video_path": candidate_video_path,
            "latest_candidate_video_path": approval["latest_candidate_video_path"],
            "latest_approved_video_path": approval["latest_approved_video_path"],
            "video_display_label": approval["video_display_label"],
            "video_approved": approval["approved"],
            "delivery_truth": delivery_truth,
            "delivery_truth_status": str(delivery_truth.get("status") or "FAIL"),
            "delivery_truth_checks": dict(delivery_truth.get("checks") or {}),
            "approved_run_id": run_id_text if approval["approved"] else "",
            "publish_package_ready": publish_ready,
            "publish_status": "PUBLISHED_PACKAGE_CREATED" if publish_ready else "PWMAP_OUTPUT",
            "assembly_status": str(merged.get("assembly_status") or ("completed" if publish_ready else "")),
            "has_downloads_only": bool(downloaded_clip_count > 0 and not publish_ready),
            "post_processing_status": "completed" if publish_ready else (
                "blocked" if visual_report and visual_report.get("status") == "visual_repetition_failed" else ""
            ),
            "post_processing_missing": bool(downloaded_clip_count > 0 and not publish_ready),
            "selected_duration_seconds": selected_duration_seconds,
            "duplicate_chain_failed": duplicate_chain_failed,
            "duplicate_clips_status": duplicate_analysis.get("duplicate_clips_status") or "pass",
            "clip_statuses": duplicate_analysis.get("clip_statuses") or [],
            "clip_3_not_applicable": clip_3_not_applicable,
            "clip_3_status": "not_applicable" if clip_3_not_applicable else "",
            "run_truth": {
                "version": RUN_TRUTH_RESOLVER_VERSION,
                "selected_duration_seconds": selected_duration_seconds,
                "requested_clip_count": requested_clip_count,
                "downloaded_clip_count": downloaded_clip_count,
                "assembled_final_exists": publish_ready,
                "candidate_video_path": candidate_video_path,
                "partial_finalization": partial,
                "duplicate_chain_failed": duplicate_chain_failed,
                "duplicate_pairs": duplicate_analysis.get("duplicate_pairs") or [],
                "clip_3_not_applicable": clip_3_not_applicable,
                "visual_diversity_status": str((visual_report or {}).get("status") or ""),
                "youtube_upload_allowed": bool((visual_report or {}).get("youtube_upload_allowed", True)),
            },
        }
    )
    if not approval["approved"]:
        merged["final_branded_video_path"] = candidate_video_path
    return merged


__all__ = [
    "RUN_TRUTH_RESOLVER_VERSION",
    "analyze_clip_duplicate_status",
    "compute_video_approval_state",
    "discover_pwmap_clip_files",
    "enrich_pwmap_results_truth",
    "resolve_candidate_video_path",
    "resolve_publish_package_ready",
]
