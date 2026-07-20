"""Resolve pwmap run videos for public media serving (Instagram video_url uploads)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RUN_ID_PATTERN = re.compile(r"^pwmap_[A-Za-z0-9_]+$")

# Prefer publish-ready branded finals; never prefer staging/intermediate clips.
_PREFERRED_FINAL_NAMES = (
    "FINAL_BRANDED_PUBLISH_READY.mp4",
    "FINAL_PUBLISH_READY.mp4",
    "FINAL_PRODUCT_STUDIO_VIDEO.mp4",
    "FINAL_BRANDED_VIDEO_CANONICAL.mp4",
)


def normalize_run_id(run_id: str) -> str:
    return str(run_id or "").strip()


def is_valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.match(normalize_run_id(run_id)))


def _is_usable_mp4(path: Path) -> bool:
    try:
        return path.is_file() and path.suffix.lower() == ".mp4" and path.stat().st_size > 0
    except OSError:
        return False


def _mp4_sort_key(path: Path) -> tuple[int, int, float]:
    """Lower tuple sorts first: prefer preferred names, then non-staging, then newest."""
    name = path.name
    try:
        preferred_rank = _PREFERRED_FINAL_NAMES.index(name)
    except ValueError:
        preferred_rank = 100
    staging_penalty = 1 if "branding_staging" in {part.lower() for part in path.parts} else 0
    try:
        mtime = -path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (preferred_rank, staging_penalty, mtime)


def _collect_mp4_files(run_dir: Path, *, final_only: bool) -> list[Path]:
    """Collect real MP4 files under a run dir. Skips directories and empty files."""
    files: list[Path] = []
    seen: set[Path] = set()
    if final_only:
        candidates: list[Path] = []
        publish = run_dir / "publish"
        if publish.is_dir():
            candidates.extend(publish.glob("FINAL*.mp4"))
        candidates.extend(run_dir.rglob("FINAL*.mp4"))
    else:
        candidates = list(run_dir.rglob("*.mp4"))

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        if not _is_usable_mp4(candidate):
            continue
        seen.add(resolved)
        files.append(candidate)
    files.sort(key=_mp4_sort_key)
    return files


def pick_best_run_video(run_dir: str | Path) -> Path | None:
    """Pick the best real MP4 file for a run (never a folder)."""
    root = Path(run_dir)
    if not root.is_dir():
        return None
    finals = _collect_mp4_files(root, final_only=True)
    if finals:
        return finals[0]
    any_mp4 = _collect_mp4_files(root, final_only=False)
    return any_mp4[0] if any_mp4 else None


def resolve_pwmap_run_video(project_root: str | Path, run_id: str) -> Path | None:
    """Return the best publish-ready mp4 for a pwmap run."""
    run_id_text = normalize_run_id(run_id)
    if not is_valid_run_id(run_id_text):
        return None
    root = Path(project_root).resolve()
    run_dir = root / "outputs" / "pwmap_agent_runs" / run_id_text
    if not run_dir.is_dir():
        return None
    return pick_best_run_video(run_dir)


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


def _platform_matches(expected: str, run_platform: str) -> bool:
    expected_key = str(expected or "").strip().lower()
    actual = str(run_platform or "").strip().lower()
    if not expected_key:
        return True
    if not actual:
        return False
    if expected_key in actual or actual in {expected_key.replace("_reels", ""), expected_key}:
        return True
    if "instagram" in expected_key and "instagram" in actual:
        return True
    if "youtube" in expected_key and "youtube" in actual:
        return True
    if expected_key == "tiktok" and actual == "tiktok":
        return True
    return False


def find_latest_run_for_platform(project_root: str | Path, platform: str) -> tuple[str, Path | None]:
    """Return (run_id, final_video_path) for the newest run matching platform.

    Always returns a real MP4 file path (never a directory). Prefers FINAL*.mp4,
    then any *.mp4. Skips branding_staging when better publish finals exist.
    """
    root = Path(project_root).resolve()
    runs_root = root / "outputs" / "pwmap_agent_runs"
    if not runs_root.is_dir():
        return "", None

    expected = str(platform or "").strip().lower()
    run_dirs = sorted(
        (p for p in runs_root.glob("pwmap_*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )

    # Pass 1: newest platform match that has a FINAL*.mp4 file.
    fallback: tuple[str, Path] | None = None
    for run_dir in run_dirs:
        run_platform = str(resolve_run_platform(root, run_dir.name) or "").lower()
        if not _platform_matches(expected, run_platform):
            continue
        finals = _collect_mp4_files(run_dir, final_only=True)
        if finals and _is_usable_mp4(finals[0]):
            return run_dir.name, finals[0].resolve()
        if fallback is None:
            any_mp4 = _collect_mp4_files(run_dir, final_only=False)
            if any_mp4 and _is_usable_mp4(any_mp4[0]):
                fallback = (run_dir.name, any_mp4[0].resolve())

    if fallback is not None:
        return fallback
    return "", None


__all__ = [
    "find_latest_run_for_platform",
    "is_valid_run_id",
    "normalize_run_id",
    "pick_best_run_video",
    "resolve_pwmap_run_video",
    "resolve_run_platform",
    "verify_run_platform_for_upload",
]
