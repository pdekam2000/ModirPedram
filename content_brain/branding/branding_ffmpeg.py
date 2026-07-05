"""Shared FFmpeg helpers for branding engines."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability, resolve_ffmpeg_binary
from content_brain.platform.media_probe import probe_has_audio_stream

FFMPEG_TIMEOUT_SECONDS = 600
_logger = logging.getLogger("modiragent.branding_ffmpeg")


@dataclass
class BrandingFfmpegResult:
    status: str
    output_path: str
    input_path: str
    ffmpeg_executed: bool = False
    ffmpeg_available: bool = False
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output_path": self.output_path,
            "input_path": self.input_path,
            "ffmpeg_executed": self.ffmpeg_executed,
            "ffmpeg_available": self.ffmpeg_available,
            "error": self.error,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


def _probe(ffmpeg_probe: Any | None) -> tuple[bool, str | None, str]:
    probe = ffmpeg_probe if ffmpeg_probe is not None else check_ffmpeg_availability()
    available = bool(getattr(probe, "available", False))
    binary = getattr(probe, "ffmpeg_path", None) or resolve_ffmpeg_binary()
    error = str(getattr(probe, "error", "") or "FFmpeg not available.")
    return available, binary, error


def run_ffmpeg_filter(
    *,
    input_path: str | Path,
    output_path: str | Path,
    vf_filter: str,
    ffmpeg_probe: Any | None = None,
    copy_audio: bool = True,
    extra_args: list[str] | None = None,
    working_directory: str | Path | None = None,
) -> BrandingFfmpegResult:
    source = Path(input_path)
    output = Path(output_path)
    if not source.is_file() or source.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(source),
            error="Input video missing or empty.",
        )

    available, binary, probe_error = _probe(ffmpeg_probe)
    if not available or not binary:
        return BrandingFfmpegResult(
            status="PLAN_ONLY",
            output_path=str(output),
            input_path=str(source),
            ffmpeg_available=False,
            error=probe_error,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    args = ["-y", "-i", str(source), "-vf", vf_filter, "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if copy_audio:
        args.extend(["-c:a", "copy"])
    else:
        args.append("-an")
    if extra_args:
        args.extend(extra_args)
    args.append(str(output))

    try:
        proc = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
            cwd=str(working_directory) if working_directory else None,
        )
    except subprocess.TimeoutExpired:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(source),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="FFmpeg timed out.",
        )
    except OSError as exc:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(source),
            ffmpeg_available=True,
            error=str(exc),
        )

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(source),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error=detail,
        )

    if not output.is_file() or output.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(source),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="Output missing or empty after FFmpeg.",
        )

    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(output.resolve()),
        input_path=str(source.resolve()),
        ffmpeg_available=True,
        ffmpeg_executed=True,
        metadata={"vf_filter": vf_filter},
    )


def run_ffmpeg_complex(
    *,
    input_paths: list[str | Path],
    output_path: str | Path,
    filter_complex: str,
    map_args: list[str],
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    if not input_paths:
        return BrandingFfmpegResult(status="FAILED", output_path=str(output_path), input_path="", error="No inputs.")

    available, binary, probe_error = _probe(ffmpeg_probe)
    if not available or not binary:
        return BrandingFfmpegResult(
            status="PLAN_ONLY",
            output_path=str(output_path),
            input_path=str(input_paths[0]),
            ffmpeg_available=False,
            error=probe_error,
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    args = ["-y"]
    for item in input_paths:
        args.extend(["-i", str(item)])
    args.extend(["-filter_complex", filter_complex, *map_args, "-c:v", "libx264", "-pix_fmt", "yuv420p"])
    primary_video = Path(input_paths[0])
    if probe_has_audio_stream(primary_video):
        if "-map" not in map_args or "0:a" not in map_args:
            args.extend(["-map", "0:a?", "-c:a", "copy"])
    else:
        _logger.debug("Logo/branding overlay: no audio stream on %s — video-only output", primary_video)
    args.append(str(output))

    try:
        proc = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(input_paths[0]),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="FFmpeg timed out.",
        )
    except OSError as exc:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(input_paths[0]),
            ffmpeg_available=True,
            error=str(exc),
        )

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(input_paths[0]),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error=detail,
        )

    if not output.is_file() or output.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(input_paths[0]),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="Output missing or empty after FFmpeg.",
        )

    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(output.resolve()),
        input_path=str(Path(input_paths[0]).resolve()),
        ffmpeg_available=True,
        ffmpeg_executed=True,
        metadata={"filter_complex": filter_complex},
    )


def run_ffmpeg_concat(
    *,
    segment_paths: list[str | Path],
    output_path: str | Path,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    if not segment_paths:
        return BrandingFfmpegResult(status="FAILED", output_path=str(output_path), input_path="", error="No segments.")

    available, binary, probe_error = _probe(ffmpeg_probe)
    if not available or not binary:
        return BrandingFfmpegResult(
            status="PLAN_ONLY",
            output_path=str(output_path),
            input_path=str(segment_paths[0]),
            ffmpeg_available=False,
            error=probe_error,
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    list_path = output.parent / "branding_concat_list.txt"
    list_path.write_text("\n".join(f"file '{Path(item).as_posix()}'" for item in segment_paths) + "\n", encoding="utf-8")

    args = [
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(output),
    ]
    try:
        proc = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(segment_paths[0]),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="FFmpeg concat timed out.",
        )
    except OSError as exc:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(segment_paths[0]),
            ffmpeg_available=True,
            error=str(exc),
        )

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(segment_paths[0]),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error=detail,
        )

    if not output.is_file() or output.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output),
            input_path=str(segment_paths[0]),
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="Concat output missing or empty.",
        )

    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(output.resolve()),
        input_path=str(Path(segment_paths[0]).resolve()),
        ffmpeg_available=True,
        ffmpeg_executed=True,
        metadata={"segments": [str(item) for item in segment_paths]},
    )


__all__ = [
    "BrandingFfmpegResult",
    "run_ffmpeg_complex",
    "run_ffmpeg_concat",
    "run_ffmpeg_filter",
]
