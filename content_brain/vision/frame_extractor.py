"""Extract analysis frames from downloaded Runway clip videos."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_ffmpeg_availability import resolve_ffmpeg_binary

FRAME_EXTRACTOR_VERSION = "visual_continuity_frame_extractor_v1"
PROBE_TIMEOUT_SECONDS = 20
EXTRACT_TIMEOUT_SECONDS = 45


@dataclass(frozen=True)
class ExtractedFrames:
    video_path: str
    output_dir: str
    first_frame: str
    middle_frame: str
    last_frame: str

    def to_dict(self) -> dict[str, str]:
        return {
            "video_path": self.video_path,
            "output_dir": self.output_dir,
            "first_frame": self.first_frame,
            "middle_frame": self.middle_frame,
            "last_frame": self.last_frame,
        }

    def frame_paths(self) -> list[str]:
        return [self.first_frame, self.middle_frame, self.last_frame]


def _run_command(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=max(1, int(timeout)),
        check=False,
    )


def _resolve_ffprobe_binary(ffmpeg_binary: str) -> str:
    ffmpeg_path = Path(ffmpeg_binary)
    for candidate_name in ("ffprobe.exe", "ffprobe"):
        candidate = ffmpeg_path.with_name(candidate_name)
        if candidate.is_file():
            return str(candidate.resolve())
    which = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    return which or "ffprobe"


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


def _extract_single_frame(
    *,
    video_path: Path,
    output_path: Path,
    ffmpeg_binary: str,
    seek_seconds: float | None,
    sseof: bool = False,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = [ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-y"]
    if sseof:
        args.extend(["-sseof", "-0.15"])
    elif seek_seconds is not None:
        args.extend(["-ss", f"{max(0.0, seek_seconds):.3f}"])
    args.extend(["-i", str(video_path), "-frames:v", "1", str(output_path)])
    proc = _run_command(args, timeout=EXTRACT_TIMEOUT_SECONDS)
    if proc.returncode != 0 or not output_path.is_file() or output_path.stat().st_size <= 0:
        detail = (proc.stderr or proc.stdout or "frame extraction failed").strip()
        raise RuntimeError(detail[:240])


def extract_analysis_frames(
    video_path: str | Path,
    *,
    output_dir: str | Path,
    clip_index: int = 1,
) -> ExtractedFrames:
    """Extract first, middle, and last frames for visual continuity analysis."""
    source = Path(video_path).resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"video not found or empty: {source}")

    ffmpeg_binary = resolve_ffmpeg_binary()
    if not ffmpeg_binary:
        raise RuntimeError("ffmpeg unavailable for frame extraction")

    target_dir = Path(output_dir).resolve() / f"clip_{clip_index}"
    target_dir.mkdir(parents=True, exist_ok=True)
    first_path = target_dir / "frame_first.jpg"
    middle_path = target_dir / "frame_middle.jpg"
    last_path = target_dir / "frame_last.jpg"

    _extract_single_frame(
        video_path=source,
        output_path=first_path,
        ffmpeg_binary=ffmpeg_binary,
        seek_seconds=0.0,
    )
    duration = _probe_duration_seconds(source, ffmpeg_binary)
    middle_seek = max(0.0, duration / 2.0) if duration > 0 else 0.5
    _extract_single_frame(
        video_path=source,
        output_path=middle_path,
        ffmpeg_binary=ffmpeg_binary,
        seek_seconds=middle_seek,
    )
    _extract_single_frame(
        video_path=source,
        output_path=last_path,
        ffmpeg_binary=ffmpeg_binary,
        seek_seconds=None,
        sseof=True,
    )

    return ExtractedFrames(
        video_path=str(source),
        output_dir=str(target_dir),
        first_frame=str(first_path),
        middle_frame=str(middle_path),
        last_frame=str(last_path),
    )


__all__ = ["ExtractedFrames", "FRAME_EXTRACTOR_VERSION", "extract_analysis_frames"]
