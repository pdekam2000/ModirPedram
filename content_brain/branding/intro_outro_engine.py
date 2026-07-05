"""Intro and outro branded card generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult, run_ffmpeg_concat
from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability, resolve_ffmpeg_binary

INTRO_OUTRO_VERSION = "intro_outro_engine_v2"
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

    duration = max(1.0, min(5.0, float(duration_seconds or 1.5)))
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


def _subscribe_overlay_filters(style: str, custom_color: str = "#E62117") -> str:
    normalized = str(style or "classic_red").strip().lower()
    if normalized == "white":
        box_color = "white@0.95"
        text_color = "black"
    elif normalized == "custom":
        hex_color = str(custom_color or "#E62117").lstrip("#")
        box_color = f"0x{hex_color}@0.95" if len(hex_color) == 6 else "0xE62117@0.95"
        text_color = "white"
    else:
        box_color = "0xE62117@0.95"
        text_color = "white"
    return (
        f",drawbox=x=(w-300)/2:y=h-150:w=300:h=72:color={box_color}:t=fill,"
        f"drawtext=text='SUBSCRIBE':fontcolor={text_color}:fontsize=40:"
        f"x=(w-text_w)/2:y=h-135"
    )


def _fade_filter(effect: str, *, duration: float, is_outro: bool) -> str:
    normalized = str(effect or "none").strip().lower()
    fade_d = min(0.8, max(0.3, duration * 0.35))
    if normalized in {"none", ""}:
        return ""
    if is_outro or normalized in {"fade_out", "fade_out_image"}:
        start = max(0.0, duration - fade_d)
        return f",fade=t=out:st={start:.2f}:d={fade_d:.2f}"
    return f",fade=t=in:st=0:d={fade_d:.2f}"


def _run_ffmpeg_segment(args: list[str], *, output_path: Path, input_path: str = "") -> BrandingFfmpegResult:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output_path),
            input_path=input_path,
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error="Intro/outro segment generation timed out.",
        )
    except OSError as exc:
        return BrandingFfmpegResult(status="FAILED", output_path=str(output_path), input_path=input_path, error=str(exc))

    if proc.returncode != 0 or not output_path.is_file() or output_path.stat().st_size <= 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "intro_outro_segment_failed"
        return BrandingFfmpegResult(
            status="FAILED",
            output_path=str(output_path),
            input_path=input_path,
            ffmpeg_available=True,
            ffmpeg_executed=True,
            error=detail,
        )
    return BrandingFfmpegResult(
        status="COMPLETED",
        output_path=str(output_path.resolve()),
        input_path=input_path,
        ffmpeg_available=True,
        ffmpeg_executed=True,
    )


def _generate_image_segment(
    *,
    output_path: Path,
    image_path: Path,
    duration_seconds: float,
    fade_effect: str,
    is_outro: bool,
    subscribe_enabled: bool = False,
    subscribe_style: str = "classic_red",
    subscribe_custom_color: str = "#E62117",
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    probe = ffmpeg_probe if ffmpeg_probe is not None else check_ffmpeg_availability()
    available = bool(getattr(probe, "available", False))
    binary = getattr(probe, "ffmpeg_path", None) or resolve_ffmpeg_binary()
    if not available or not binary:
        return BrandingFfmpegResult(
            status="PLAN_ONLY",
            output_path=str(output_path),
            input_path=str(image_path),
            ffmpeg_available=False,
            error=str(getattr(probe, "error", "") or "FFmpeg not available."),
        )
    if not image_path.is_file() or image_path.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output_path),
            input_path=str(image_path),
            warnings=["intro_outro_image_missing"],
        )

    duration = max(1.0, min(5.0, float(duration_seconds or 2.0)))
    effect = str(fade_effect or "none").strip().lower()
    subscribe = _subscribe_overlay_filters(subscribe_style, subscribe_custom_color) if subscribe_enabled and is_outro else ""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if effect in {"slide_from_right", "slide_from_left"}:
        slide_d = min(0.6, duration * 0.4)
        x_expr = f"if(lte(t\\,{slide_d:.2f})\\,W*(1-t/{slide_d:.2f})\\,0)"
        if effect == "slide_from_left":
            x_expr = f"if(lte(t\\,{slide_d:.2f})\\,-W*(1-t/{slide_d:.2f})\\,0)"
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[img];"
            f"[1:v][img]overlay=x='{x_expr}':y=0,format=yuv420p{_fade_filter('none', duration=duration, is_outro=is_outro)}{subscribe}[vout]"
        )
        args = [
            binary,
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x111111:s=1080x1920:d={duration:.2f}",
            "-t",
            f"{duration:.2f}",
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output_path),
        ]
    else:
        vf = (
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
            f"{_fade_filter(fade_effect, duration=duration, is_outro=is_outro)}{subscribe}"
        )
        args = [
            binary,
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            f"{duration:.2f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output_path),
        ]

    result = _run_ffmpeg_segment(args, output_path=output_path, input_path=str(image_path))
    result.metadata.update(
        {
            "segment_type": "image",
            "duration_seconds": duration,
            "fade_effect": fade_effect,
            "subscribe_enabled": subscribe_enabled,
        }
    )
    return result


def _generate_video_clip_segment(
    *,
    output_path: Path,
    video_path: Path,
    max_duration_seconds: float = 5.0,
    fade_effect: str = "fade_in",
    is_outro: bool = False,
    subscribe_enabled: bool = False,
    subscribe_style: str = "classic_red",
    subscribe_custom_color: str = "#E62117",
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    probe = ffmpeg_probe if ffmpeg_probe is not None else check_ffmpeg_availability()
    available = bool(getattr(probe, "available", False))
    binary = getattr(probe, "ffmpeg_path", None) or resolve_ffmpeg_binary()
    if not available or not binary:
        return BrandingFfmpegResult(
            status="PLAN_ONLY",
            output_path=str(output_path),
            input_path=str(video_path),
            ffmpeg_available=False,
            error=str(getattr(probe, "error", "") or "FFmpeg not available."),
        )
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output_path),
            input_path=str(video_path),
            warnings=["intro_outro_video_missing"],
        )

    clip_duration = max(1.0, min(5.0, float(max_duration_seconds or 5.0)))
    subscribe = _subscribe_overlay_filters(subscribe_style, subscribe_custom_color) if subscribe_enabled and is_outro else ""
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
        f"{_fade_filter(fade_effect, duration=clip_duration, is_outro=is_outro)}{subscribe}"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        binary,
        "-y",
        "-i",
        str(video_path),
        "-t",
        f"{clip_duration:.2f}",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(output_path),
    ]
    result = _run_ffmpeg_segment(args, output_path=output_path, input_path=str(video_path))
    result.metadata.update({"segment_type": "video_clip", "duration_seconds": clip_duration, "fade_effect": fade_effect})
    return result


def generate_intro_segment(
    *,
    output_dir: str | Path,
    intro_type: str = "none",
    intro_text: str = "",
    intro_duration: float = 2.0,
    intro_image_path: str | Path | None = None,
    intro_video_path: str | Path | None = None,
    intro_fade_effect: str = "fade_in",
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    output = Path(output_dir) / INTRO_VIDEO_NAME
    normalized = str(intro_type or "none").strip().lower().replace("-", "_")
    if normalized in {"image_fade_in", "image"}:
        result = _generate_image_segment(
            output_path=output,
            image_path=Path(intro_image_path or ""),
            duration_seconds=intro_duration,
            fade_effect=intro_fade_effect,
            is_outro=False,
            ffmpeg_probe=ffmpeg_probe,
        )
    elif normalized in {"video_clip", "video"}:
        result = _generate_video_clip_segment(
            output_path=output,
            video_path=Path(intro_video_path or ""),
            max_duration_seconds=min(5.0, float(intro_duration or 5.0)),
            fade_effect=intro_fade_effect,
            is_outro=False,
            ffmpeg_probe=ffmpeg_probe,
        )
    elif intro_text.strip():
        result = _generate_card(
            output_path=output,
            card_text=intro_text,
            duration_seconds=intro_duration,
            ffmpeg_probe=ffmpeg_probe,
        )
    else:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output),
            input_path="",
            warnings=["intro_not_configured"],
        )
    result.metadata["version"] = INTRO_OUTRO_VERSION
    result.metadata["card_type"] = "intro"
    result.metadata["intro_type"] = normalized
    return result


def generate_outro_segment(
    *,
    output_dir: str | Path,
    outro_type: str = "none",
    outro_text: str = "",
    outro_duration: float = 3.0,
    outro_image_path: str | Path | None = None,
    outro_video_path: str | Path | None = None,
    outro_fade_effect: str = "fade_out",
    outro_subscribe_enabled: bool = True,
    outro_subscribe_style: str = "classic_red",
    outro_subscribe_custom_color: str = "#E62117",
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    output = Path(output_dir) / OUTRO_VIDEO_NAME
    normalized = str(outro_type or "none").strip().lower().replace("-", "_")
    if normalized in {"image_fade_out", "image"}:
        result = _generate_image_segment(
            output_path=output,
            image_path=Path(outro_image_path or ""),
            duration_seconds=outro_duration,
            fade_effect=outro_fade_effect,
            is_outro=True,
            subscribe_enabled=outro_subscribe_enabled,
            subscribe_style=outro_subscribe_style,
            subscribe_custom_color=outro_subscribe_custom_color,
            ffmpeg_probe=ffmpeg_probe,
        )
    elif normalized in {"video_clip", "video"}:
        result = _generate_video_clip_segment(
            output_path=output,
            video_path=Path(outro_video_path or ""),
            max_duration_seconds=min(5.0, float(outro_duration or 5.0)),
            fade_effect=outro_fade_effect,
            is_outro=True,
            subscribe_enabled=outro_subscribe_enabled,
            subscribe_style=outro_subscribe_style,
            subscribe_custom_color=outro_subscribe_custom_color,
            ffmpeg_probe=ffmpeg_probe,
        )
    elif outro_text.strip():
        result = _generate_card(
            output_path=output,
            card_text=outro_text,
            duration_seconds=outro_duration,
            ffmpeg_probe=ffmpeg_probe,
        )
    else:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output),
            input_path="",
            warnings=["outro_not_configured"],
        )
    result.metadata["version"] = INTRO_OUTRO_VERSION
    result.metadata["card_type"] = "outro"
    result.metadata["outro_type"] = normalized
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
    "generate_intro_segment",
    "generate_outro_card",
    "generate_outro_segment",
    "merge_intro_outro",
]
