"""Pre-assembly clip uniqueness guard — blocks stitch/upload on duplicate bytes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.kling_useframe_generation_completion_gate import sha256_file

GUARD_VERSION = "pwmap_clip_assembly_guard_v1"
DUPLICATE_ASSEMBLY_ERROR = "Duplicate clip bytes detected; assembly blocked."


def verify_clips_unique_for_assembly(
    *,
    run_dir: Path,
    clip_count: int,
) -> dict[str, Any]:
    """Verify clip_1..clip_N on disk have distinct SHA-256 before stitching."""
    clip_paths = [run_dir / f"clip_{index}.mp4" for index in range(1, max(1, clip_count) + 1)]
    existing = [path for path in clip_paths if path.is_file()]
    if len(existing) < 2:
        return {
            "version": GUARD_VERSION,
            "ok": True,
            "assembly_allowed": True,
            "clip_count": len(existing),
            "duplicate_pairs": [],
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
        "clip_count": len(hashes),
        "duplicate_pairs": duplicate_pairs,
        "error": DUPLICATE_ASSEMBLY_ERROR if blocked else "",
        "youtube_upload_allowed": not blocked,
    }


__all__ = [
    "DUPLICATE_ASSEMBLY_ERROR",
    "GUARD_VERSION",
    "verify_clips_unique_for_assembly",
]
