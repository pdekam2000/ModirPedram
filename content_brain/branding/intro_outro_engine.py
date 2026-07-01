"""Intro and outro branded card generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult, run_ffmpeg_concat
from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability, resolve_ffmpeg_binary

INTRO_OUTRO_VERSION = "intro_outro_engine_v1"
INTRO_VIDEO_NAME = "INTRO.mp4"
OUTRO_VIDEO_NAME = "OUTRO.mp4"
FFMPEG_TIMEOUT_SECONDS = 120


def _escape_drawtext(text: str) -> str:
    return str(text or "").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _generate_card(
    *,
    output_path: Path,
    card_text: str,
    duration_seconds: float,
    width: int = 1080,
    height: int = 1920,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    probe = ffmpeg_probe if ffmpeg_probe is not None else check_ffmpeg_availability()
    available = bool(getattr(probe, "available", False))
    binary = getattr(probe, "ffmpeg_path", None) or resolve_ffmpeg_binary()
    if not available or not binary:
        return BrandingFfmpegResult(
            status="PLAN_ONLY",
            output_path=str(output_path),
            input_path="",
            ffmpeg_available=False,
            error=str(getattr(probe, "error", "") or "FFmpeg not available."),
        )

    duration = max(1.0, min(2.0, float(duration_seconds or 1.5)))
    text = _escape_drawtext(card_text or "Channel Intro")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"color=c=0x111111:s={width}x{height}:d={duration:.2f},"
        f"drawtext=text='{text}':fontcolor=white:fontsize=48:borderw=2:bordercolor=black:"
        f"x=(w-text_w)/2:y=(h-text_h)/2"
    )
    args = [
        binary,
        "-y",
        "-f",
        "lavfi",
        "-i",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(output_path),
    ]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output_path),
            input_path="",
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="Intro/outro card generation timed out.",
        )
    except OSError as exc:
        return BrandingFfmpegResult(status="FAILED", output_path=str(output_path), input_path="", error=str(exc))

    if proc.returncode != 0 or not output_path.is_file() or output_path.stat().st_size <= 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "intro_outro_generation_failed"
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output_path),
            input_path="",
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error=detail,
        )

    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(output_path.resolve()),
        input_path="",
        ffmpeg_available=True,
        ffmpeg_executed=True,
        metadata={"card_text": card_text, "duration_seconds": duration},
    )


def generate_intro_card(
    *,
    output_dir: str | Path,
    intro_text: str,
    intro_duration: float = 2.0,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    output = Path(output_dir) / INTRO_VIDEO_NAME
    result = _generate_card(
        output_path=output,
        card_text=intro_text,
        duration_seconds=intro_duration,
        ffmpeg_probe=ffmpeg_probe,
    )
    result.metadata["version"] = INTRO_OUTRO_VERSION
    result.metadata["card_type"] = "intro"
    return result


def generate_outro_card(
    *,
    output_dir: str | Path,
    outro_text: str,
    outro_duration: float = 2.0,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    output = Path(output_dir) / OUTRO_VIDEO_NAME
    result = _generate_card(
        output_path=output,
        card_text=outro_text,
        duration_seconds=outro_duration,
        ffmpeg_probe=ffmpeg_probe,
    )
    result.metadata["version"] = INTRO_OUTRO_VERSION
    result.metadata["card_type"] = "outro"
    return result


def merge_intro_outro(
    *,
    intro_path: str | Path | None,
    main_video_path: str | Path,
    outro_path: str | Path | None,
    output_path: str | Path,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    segments: list[Path] = []
    if intro_path:
        intro = Path(intro_path)
        if intro.is_file() and intro.stat().st_size > 0:
            segments.append(intro)
    main = Path(main_video_path)
    if main.is_file() and main.stat().st_size > 0:
        segments.append(main)
    if outro_path:
        outro = Path(outro_path)
        if outro.is_file() and outro.stat().st_size > 0:
            segments.append(outro)

    if len(segments) <= 1:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output_path),
            input_path=str(main),
            warnings=["intro_outro_merge_not_needed"],
        )

    return run_ffmpeg_concat(segment_paths=segments, output_path=output_path, ffmpeg_probe=ffmpeg_probe)


__all__ = [
    "INTRO_OUTRO_VERSION",
    "INTRO_VIDEO_NAME",
    "OUTRO_VIDEO_NAME",
    "generate_intro_card",
    "generate_outro_card",
    "merge_intro_outro",
]
