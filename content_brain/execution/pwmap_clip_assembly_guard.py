"""Pre-assembly clip uniqueness guard — blocks stitch/upload on duplicate bytes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.kling_useframe_generation_completion_gate import sha256_file

GUARD_VERSION = "pwmap_clip_assembly_guard_v2_missing_and_duplicate"
DUPLICATE_ASSEMBLY_ERROR = "Duplicate clip bytes detected; assembly blocked."
MISSING_CLIPS_ERROR = "Missing clip artifacts; assembly blocked."
ASSEMBLY_BLOCKED_STATUS = "blocked_duplicate_or_missing_clips"


def verify_clips_unique_for_assembly(
    *,
    run_dir: Path,
    clip_count: int,
) -> dict[str, Any]:
    """Verify clip_1..clip_N exist on disk and have distinct SHA-256 before stitching."""
    planned = max(1, int(clip_count))
    clip_paths = [run_dir / f"clip_{index}.mp4" for index in range(1, planned + 1)]
    existing = [path for path in clip_paths if path.is_file()]
    missing_indices = [index for index, path in enumerate(clip_paths, start=1) if not path.is_file()]

    if planned > 1 and missing_indices:
        return {
            "version": GUARD_VERSION,
            "ok": False,
            "assembly_allowed": False,
            "assembly_status": ASSEMBLY_BLOCKED_STATUS,
            "clip_count": len(existing),
            "expected_clip_count": planned,
            "missing_clip_indices": missing_indices,
            "duplicate_pairs": [],
            "error": MISSING_CLIPS_ERROR,
            "youtube_upload_allowed": False,
        }

    if len(existing) < 2:
        return {
            "version": GUARD_VERSION,
            "ok": True,
            "assembly_allowed": True,
            "assembly_status": "completed" if planned <= 1 else "",
            "clip_count": len(existing),
            "expected_clip_count": planned,
            "duplicate_pairs": [],
            "youtube_upload_allowed": planned <= 1,
        }

    hashes: dict[int, str] = {}
    for index, path in enumerate(clip_paths, start=1):
        if path.is_file():
            hashes[index] = sha256_file(path)

    duplicate_pairs: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for index, file_hash in hashes.items():
        if file_hash in seen:
            duplicate_pairs.append(
                {"clip_a": seen[file_hash], "clip_b": index, "sha256": file_hash}
            )
        else:
            seen[file_hash] = index

    blocked = bool(duplicate_pairs)
    return {
        "version": GUARD_VERSION,
        "ok": not blocked,
        "assembly_allowed": not blocked,
        "assembly_status": ASSEMBLY_BLOCKED_STATUS if blocked else "ready",
        "clip_count": len(hashes),
        "expected_clip_count": planned,
        "duplicate_pairs": duplicate_pairs,
        "error": DUPLICATE_ASSEMBLY_ERROR if blocked else "",
        "youtube_upload_allowed": not blocked,
    }


__all__ = [
    "ASSEMBLY_BLOCKED_STATUS",
    "DUPLICATE_ASSEMBLY_ERROR",
    "GUARD_VERSION",
    "MISSING_CLIPS_ERROR",
    "verify_clips_unique_for_assembly",
]
