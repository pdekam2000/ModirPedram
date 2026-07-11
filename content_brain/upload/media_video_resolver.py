"""Resolve pwmap run videos for public media serving (Instagram video_url uploads)."""

from __future__ import annotations

import glob
import re
from pathlib import Path

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


__all__ = ["is_valid_run_id", "normalize_run_id", "resolve_pwmap_run_video"]
