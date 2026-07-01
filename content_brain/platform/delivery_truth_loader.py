"""Load delivery truth audit for Results — final MP4 analysis only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.platform.canonical_run import load_canonical_run
from content_brain.quality.delivery_reality_auditor import audit_final_mp4_delivery
from content_brain.execution.pwmap_runway_agent_adapter import validate_mp4_path

DELIVERY_TRUTH_LOADER_VERSION = "delivery_truth_loader_v1"

CHECK_LABELS = {
    "subtitles": "Subtitles",
    "music": "Music",
    "ambience": "Ambience",
    "dialogue": "Dialogue",
    "voice_separation": "Voice Separation",
    "story_quality": "Story Quality",
}


def resolve_audit_mp4_for_run(
    run_dir: str | Path,
    *,
    project_root: str | Path | None = None,
) -> tuple[Path | None, str]:
    """Resolve MP4 to audit for a specific run folder only (no cross-run registry bleed)."""
    run_path = Path(run_dir).resolve()
    if not run_path.is_dir():
        return None, "missing"

    publish = run_path / "publish"
    for name in ("FINAL_BRANDED_PUBLISH_READY.mp4", "FINAL_PUBLISH_READY.mp4", "FINAL_BRANDED_VIDEO_CANONICAL.mp4"):
        candidate = publish / name
        if validate_mp4_path(candidate).get("valid"):
            return candidate.resolve(), "publish" if name != "FINAL_BRANDED_VIDEO_CANONICAL.mp4" else "canonical"

    for name in ("video_merged.mp4", "video.mp4"):
        candidate = run_path / name
        if validate_mp4_path(candidate).get("valid"):
            return candidate.resolve(), "candidate"

    return None, "missing"


def build_delivery_truth_panel(
    project_root: str | Path,
    *,
    run_id: str = "",
    run_dir: str = "",
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    canonical = load_canonical_run(root)
    canonical_run_id = str(canonical.get("run_id") or "")
    canonical_run_dir = str(run_dir or canonical.get("run_dir") or "")
    effective_run_id = str(run_id or canonical_run_id or "")

    audit_target = canonical_run_dir or str(run_dir or "")
    final_video, audit_kind = resolve_audit_mp4_for_run(audit_target, project_root=root) if audit_target else (None, "missing")
    if final_video is None and run_dir:
        final_video, audit_kind = resolve_audit_mp4_for_run(run_dir, project_root=root)

    audit_payload: dict[str, Any] = {
        "version": DELIVERY_TRUTH_LOADER_VERSION,
        "run_id": effective_run_id,
        "canonical_run_id": canonical_run_id,
        "final_video_path": "",
        "audit_target_kind": audit_kind,
        "status": "FAIL",
        "quality_score": 0,
        "approved": False,
        "checks": {key: {"label": label, "status": "FAIL"} for key, label in CHECK_LABELS.items()},
        "failures": ["final_mp4_missing"],
        "metrics": {},
    }

    if final_video is None:
        return audit_payload

    audit = audit_final_mp4_delivery(final_video)
    checks: dict[str, Any] = {}
    for key, label in CHECK_LABELS.items():
        ok = bool((audit.checks or {}).get(key))
        checks[key] = {"label": label, "status": "PASS" if ok else "FAIL"}

    approved = audit.status == "PASS" and audit_kind == "canonical" and effective_run_id == canonical_run_id
    audit_payload.update(
        {
            "run_id": effective_run_id,
            "canonical_run_id": canonical_run_id,
            "final_video_path": str(final_video.resolve()),
            "status": audit.status,
            "quality_score": audit.quality_score,
            "approved": approved,
            "checks": checks,
            "failures": list(audit.failures or []),
            "metrics": dict(audit.metrics or {}),
        }
    )
    return audit_payload


__all__ = ["DELIVERY_TRUTH_LOADER_VERSION", "CHECK_LABELS", "build_delivery_truth_panel", "resolve_audit_mp4_for_run"]
