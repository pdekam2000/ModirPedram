"""Channel logo overlay engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult, run_ffmpeg_complex
from content_brain.branding.channel_assets_store import ChannelAssetsStore

LOGO_OVERLAY_VERSION = "logo_overlay_engine_v1"

POSITION_TOP_LEFT = "top_left"
POSITION_TOP_RIGHT = "top_right"
POSITION_BOTTOM_LEFT = "bottom_left"
POSITION_BOTTOM_RIGHT = "bottom_right"


def _overlay_coords(position: str) -> str:
    mapping = {
        POSITION_TOP_LEFT: "40:40",
        POSITION_TOP_RIGHT: "W-w-40:40",
        POSITION_BOTTOM_LEFT: "40:H-h-40",
        POSITION_BOTTOM_RIGHT: "W-w-40:H-h-40",
    }
    return mapping.get(position, mapping[POSITION_TOP_RIGHT])


def apply_logo_overlay(
    *,
    project_root: str | Path,
    input_video_path: str | Path,
    output_path: str | Path,
    logo_path: str | Path | None = None,
    logo_position: str = POSITION_TOP_RIGHT,
    logo_scale: float = 0.12,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    video = Path(input_video_path)
    output = Path(output_path)
    logo = Path(logo_path) if logo_path else ChannelAssetsStore(project_root).logo_path

    if not logo.is_file() or logo.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output),
            input_path=str(video),
            warnings=["logo_missing"],
        )

    scale = max(0.05, min(0.35, float(logo_scale or 0.12)))
    coords = _overlay_coords(logo_position)
    filter_complex = f"[1:v]scale=iw*{scale}:-1[logo];[0:v][logo]overlay={coords}[vout]"
    result = run_ffmpeg_complex(
        input_paths=[video, logo],
        output_path=output,
        filter_complex=filter_complex,
        map_args=["-map", "[vout]", "-map", "0:a?"],
        ffmpeg_probe=ffmpeg_probe,
    )
    result.metadata.update(
        {
            "version": LOGO_OVERLAY_VERSION,
            "logo_path": str(logo.resolve()),
            "logo_position": logo_position,
            "logo_scale": scale,
        }
    )
    return result


__all__ = [
    "LOGO_OVERLAY_VERSION",
    "POSITION_BOTTOM_LEFT",
    "POSITION_BOTTOM_RIGHT",
    "POSITION_TOP_LEFT",
    "POSITION_TOP_RIGHT",
    "apply_logo_overlay",
]
