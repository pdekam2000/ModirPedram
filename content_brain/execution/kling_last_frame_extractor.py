"""Extract continuity bridge frames from recovered Kling clip MP4s."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_ffmpeg_availability import resolve_ffmpeg_binary

EXTRACTOR_VERSION = "kling_last_frame_extractor_v1"
MIN_FRAME_BYTES = 1024
PROBE_TIMEOUT_SECONDS = 20
EXTRACT_TIMEOUT_SECONDS = 45


@dataclass(frozen=True)
class ExtractedLastFrame:
    video_path: str
    frame_path: str
    clip_index: int
    duration_seconds: float
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "frame_path": self.frame_path,
            "clip_index": self.clip_index,
            "duration_seconds": self.duration_seconds,
            "size_bytes": self.size_bytes,
        }


def continuity_dir(run_dir: str | Path) -> Path:
    path = Path(run_dir).resolve() / "continuity"
    path.mkdir(parents=True, exist_ok=True)
    return path


def continuity_frame_path(run_dir: str | Path, clip_index: int) -> Path:
    return continuity_dir(run_dir) / f"frame_c{clip_index}.png"


def _resolve_ffprobe_binary(ffmpeg_binary: str) -> str:
    ffmpeg_path = Path(ffmpeg_binary)
    for candidate_name in ("ffprobe.exe", "ffprobe"):
        candidate = ffmpeg_path.with_name(candidate_name)
        if candidate.is_file():
            return str(candidate.resolve())
    which = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    return which or "ffprobe"


def _run_command(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=max(1, int(timeout)),
        check=False,
    )


def _probe_duration_seconds(video_path: Path, ffmpeg_binary: str) -> float:
    ffprobe = _resolve_ffprobe_binary(ffmpeg_binary)
    proc = _run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        timeout=PROBE_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        return 0.0
    try:
        return max(0.0, float(str(proc.stdout or "").strip()))
    except ValueError:
        return 0.0


def extract_last_frame(video_path: str | Path, *, ffmpeg_binary: str | None = None) -> Path:
    """Extract the final video frame to a temporary PNG path (caller may move/rename)."""
    source = Path(video_path).resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"video not found or empty: {source}")

    binary = ffmpeg_binary or resolve_ffmpeg_binary()
    if not binary:
        raise RuntimeError("ffmpeg unavailable for last-frame extraction")

    temp_path = source.parent / f".last_frame_{source.stem}.png"
    args = [
        binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-sseof",
        "-0.15",
        "-i",
        str(source),
        "-frames:v",
        "1",
        str(temp_path),
    ]
    proc = _run_command(args, timeout=EXTRACT_TIMEOUT_SECONDS)
    if proc.returncode != 0 or not temp_path.is_file() or temp_path.stat().st_size <= 0:
        detail = (proc.stderr or proc.stdout or "last frame extraction failed").strip()
        raise RuntimeError(detail[:240])
    return temp_path


def save_frame(source_frame: str | Path, frame_path: str | Path) -> Path:
    """Persist an extracted frame to the canonical continuity path."""
    src = Path(source_frame).resolve()
    dest = Path(frame_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    if src.name.startswith(".last_frame_") and src.is_file():
        try:
            src.unlink()
        except OSError:
            pass
    return dest


def validate_frame(frame_path: str | Path, *, min_bytes: int = MIN_FRAME_BYTES) -> dict[str, Any]:
    path = Path(frame_path).resolve()
    ok = path.is_file() and path.stat().st_size >= max(1, int(min_bytes))
    return {
        "ok": ok,
        "frame_path": str(path),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "min_bytes": min_bytes,
        "is_png": path.suffix.lower() == ".png",
    }


def extract_and_save_continuity_frame(
    *,
    video_path: str | Path,
    run_dir: str | Path,
    clip_index: int,
) -> ExtractedLastFrame:
    """Extract last frame from clip MP4 and save to continuity/frame_cN.png."""
    source = Path(video_path).resolve()
    dest = continuity_frame_path(run_dir, clip_index)
    temp = extract_last_frame(source)
    saved = save_frame(temp, dest)
    validation = validate_frame(saved)
    if not validation.get("ok"):
        raise RuntimeError(f"continuity frame validation failed: {saved}")

    ffmpeg_binary = resolve_ffmpeg_binary() or ""
    duration = _probe_duration_seconds(source, ffmpeg_binary) if ffmpeg_binary else 0.0
    report = {
        "version": EXTRACTOR_VERSION,
        "clip_index": clip_index,
        "video_path": str(source),
        "frame_path": str(saved),
        "duration_seconds": duration,
        "validation": validation,
    }
    report_path = continuity_dir(run_dir) / f"extract_c{clip_index}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return ExtractedLastFrame(
        video_path=str(source),
        frame_path=str(saved),
        clip_index=int(clip_index),
        duration_seconds=duration,
        size_bytes=int(validation.get("size_bytes") or 0),
    )


__all__ = [
    "EXTRACTOR_VERSION",
    "ExtractedLastFrame",
    "continuity_dir",
    "continuity_frame_path",
    "extract_and_save_continuity_frame",
    "extract_last_frame",
    "save_frame",
    "validate_frame",
]
