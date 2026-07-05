"""Channel logo overlay engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult, run_ffmpeg_complex
from content_brain.branding.channel_assets_store import ChannelAssetsStore

LOGO_OVERLAY_VERSION = "logo_overlay_engine_v2"
LOGO_MARGIN_PX = 10
LOGO_WIDTH_MIN_PX = 80
LOGO_WIDTH_MAX_PX = 100

POSITION_TOP_LEFT = "top_left"
POSITION_TOP_RIGHT = "top_right"
POSITION_BOTTOM_LEFT = "bottom_left"
POSITION_BOTTOM_RIGHT = "bottom_right"

_logger = logging.getLogger("modiragent.logo_overlay")


def resolve_channel_logo_path(
    project_root: str | Path,
    *,
    profile_logo_path: str | Path | None = None,
) -> Path | None:
    """Resolve logo from profile path, then branding assets store."""
    if profile_logo_path:
        candidate = Path(profile_logo_path)
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate.resolve()
    store_path = ChannelAssetsStore(project_root).asset_path("logo")
    if store_path and store_path.is_file() and store_path.stat().st_size > 0:
        return store_path.resolve()
    return None


def _logo_width_px(logo_scale: float) -> int:
    """Target 80–100px; logo_scale 0.12 ≈ 90px on typical short-form width."""
    estimated = int(max(0.05, min(0.20, float(logo_scale or 0.12))) * 750)
    return max(LOGO_WIDTH_MIN_PX, min(LOGO_WIDTH_MAX_PX, estimated))


def _ensure_png_logo(logo: Path) -> Path:
    """Convert JPEG logos to PNG with alpha so FFmpeg overlay has no white box."""
    suffix = logo.suffix.lower()
    if suffix not in {".jpg", ".jpeg"}:
        return logo
    try:
        from PIL import Image
    except ImportError:
        _logger.warning("Pillow not installed — cannot convert JPEG logo to PNG.")
        return logo

    png_path = logo.with_name(f"{logo.stem}_converted.png")
    try:
        img = Image.open(logo).convert("RGBA")
        img.save(png_path, "PNG")
        _logger.info("Logo converted JPEG → PNG: %s", png_path.name)
        return png_path.resolve()
    except Exception as exc:
        _logger.warning("Logo JPEG→PNG conversion failed (%s); using original.", exc)
        return logo


def _overlay_coords(position: str, *, margin: int = LOGO_MARGIN_PX) -> str:
    mapping = {
        POSITION_TOP_LEFT: f"{margin}:{margin}",
        POSITION_TOP_RIGHT: f"W-w-{margin}:{margin}",
        POSITION_BOTTOM_LEFT: f"{margin}:H-h-{margin}",
        POSITION_BOTTOM_RIGHT: f"W-w-{margin}:H-h-{margin}",
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
    logo = resolve_channel_logo_path(project_root, profile_logo_path=logo_path)

    if logo is None:
        tried = str(logo_path or ChannelAssetsStore(project_root).assets_dir / "logo.*")
        _logger.warning("Logo missing ✗: file not found at %s", tried)
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output),
            input_path=str(video),
            warnings=["logo_missing"],
            metadata={"logo_path_tried": tried},
        )

    logo = _ensure_png_logo(logo)

    logo_width_px = _logo_width_px(logo_scale)
    coords = _overlay_coords(logo_position)
    filter_complex = f"[1:v]scale={logo_width_px}:-1[logo];[0:v][logo]overlay={coords}[vout]"
    _logger.info(
        "Logo overlay FFmpeg: -i %s -i %s -filter_complex \"%s\"",
        video.name,
        logo.name,
        filter_complex,
    )

    result = run_ffmpeg_complex(
        input_paths=[video, logo],
        output_path=output,
        filter_complex=filter_complex,
        map_args=["-map", "[vout]"],
        ffmpeg_probe=ffmpeg_probe,
    )
    result.metadata.update(
        {
            "version": LOGO_OVERLAY_VERSION,
            "logo_path": str(logo),
            "logo_position": logo_position,
            "logo_scale": float(logo_scale),
            "logo_width_px": logo_width_px,
            "filter_complex": filter_complex,
        }
    )
    if result.status == "COMPLETED":
        _logger.info("Logo applied ✓: %s (%dpx, %s)", logo, logo_width_px, logo_position)
    elif result.status == "SKIPPED":
        _logger.warning("Logo skipped ✗: %s", result.warnings or result.error)
    else:
        _logger.error("Logo overlay failed ✗: %s", result.error or result.status)
    return result


__all__ = [
    "LOGO_OVERLAY_VERSION",
    "LOGO_MARGIN_PX",
    "LOGO_WIDTH_MAX_PX",
    "LOGO_WIDTH_MIN_PX",
    "POSITION_BOTTOM_LEFT",
    "POSITION_BOTTOM_RIGHT",
    "POSITION_TOP_LEFT",
    "POSITION_TOP_RIGHT",
    "apply_logo_overlay",
    "resolve_channel_logo_path",
]
