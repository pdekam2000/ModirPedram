"""Resolve pwmap run videos for public media serving (Instagram video_url uploads)."""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any

RUN_ID_PATTERN = re.compile(r"^pwmap_[A-Za-z0-9_]+$")


def normalize_run_id(run_id: str) -> str:
    return str(run_id or "").strip()


def is_valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.match(normalize_run_id(run_id)))


def resolve_pwmap_run_video(project_root: str | Path, run_id: str) -> Path | None:
    """Return the best publish-ready mp4 for a pwmap run."""
    run_id_text = normalize_run_id(run_id)
    if not is_valid_run_id(run_id_text):
        return None
    root = Path(project_root).resolve()
    run_dir = root / "outputs" / "pwmap_agent_runs" / run_id_text
    if not run_dir.is_dir():
        return None

    patterns = (
        str(run_dir / "publish" / "FINAL_BRANDED_PUBLISH_READY.mp4"),
        str(run_dir / "**" / "FINAL*.mp4"),
        str(run_dir / "**" / "*.mp4"),
    )
    for pattern in patterns:
        matches = [
            Path(item)
            for item in glob.glob(pattern, recursive=True)
            if Path(item).is_file() and Path(item).stat().st_size > 0
        ]
        if not matches:
            continue
        matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return matches[0]
    return None


def _pwmap_run_dir(project_root: str | Path, run_id: str) -> Path | None:
    run_id_text = normalize_run_id(run_id)
    if run_id_text and not run_id_text.startswith("pwmap_"):
        run_id_text = f"pwmap_{run_id_text}"
    if not is_valid_run_id(run_id_text):
        return None
    run_dir = Path(project_root).resolve() / "outputs" / "pwmap_agent_runs" / run_id_text
    return run_dir if run_dir.is_dir() else None


def _platform_from_payload(payload: dict[str, Any]) -> str:
    platform = str(payload.get("platform") or "").strip()
    if platform:
        return platform
    targets = payload.get("platform_targets")
    if isinstance(targets, list) and targets:
        return str(targets[0] or "").strip()
    return ""


def resolve_run_platform(project_root: str | Path, run_id: str) -> str:
    """Read platform from run folder metadata (job.json first, then runtime artifacts)."""
    run_dir = _pwmap_run_dir(project_root, run_id)
    if run_dir is None:
        return ""

    for relative in (
        "job.json",
        "normalized_result.json",
        "product_multiclip_runtime.json",
        "pipeline_trace.json",
    ):
        path = run_dir / relative
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        platform = _platform_from_payload(payload)
        if not platform and relative == "normalized_result.json":
            for nested_key in ("preflight", "preflight_snapshot"):
                nested = payload.get(nested_key)
                if isinstance(nested, dict):
                    platform = _platform_from_payload(nested)
                    if platform:
                        break
        if platform:
            return platform
    return ""


def verify_run_platform_for_upload(
    project_root: str | Path,
    run_id: str,
    *,
    job_platform: str,
) -> tuple[bool, str, str]:
    """Fail closed when run metadata platform does not match the automation job platform."""
    from content_brain.automation.platform_upload_guard import normalize_platform

    expected = normalize_platform(job_platform)
    actual = normalize_platform(resolve_run_platform(project_root, run_id))
    if not actual:
        return False, "run_platform_unknown", ""
    if expected == "instagram_reels" and actual not in {"instagram_reels", "instagram"}:
        return False, f"instagram_run_platform_mismatch:{actual}", actual
    if expected == "youtube_shorts" and actual not in {"youtube_shorts", "youtube"}:
        return False, f"youtube_run_platform_mismatch:{actual}", actual
    if expected == "tiktok" and actual != "tiktok":
        return False, f"tiktok_run_platform_mismatch:{actual}", actual
    return True, "", actual


def find_latest_run_for_platform(project_root: str | Path, platform: str) -> tuple[str, Path | None]:
    """Return (run_id, final_video_path) for the newest run matching platform."""
    root = Path(project_root).resolve()
    runs_root = root / "outputs" / "pwmap_agent_runs"
    if not runs_root.is_dir():
        return "", None

    expected = str(platform or "").strip().lower()
    for run_dir in sorted(runs_root.glob("pwmap_*"), reverse=True):
        run_platform = str(resolve_run_platform(root, run_dir.name) or "").lower()
        if expected not in run_platform and run_platform not in {expected.replace("_reels", ""), expected}:
            if "instagram" in expected and "instagram" not in run_platform:
                continue
            if "youtube" in expected and "youtube" not in run_platform:
                continue
            if expected == "tiktok" and run_platform != "tiktok":
                continue
        finals = list(run_dir.glob("publish/FINAL*.mp4"))
        if not finals:
            finals = list(run_dir.glob("**/FINAL*.mp4"))
        if finals:
            return run_dir.name, finals[0]
    return "", None


__all__ = [
    "find_latest_run_for_platform",
    "is_valid_run_id",
    "normalize_run_id",
    "resolve_pwmap_run_video",
    "resolve_run_platform",
    "verify_run_platform_for_upload",
]
