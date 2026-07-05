"""Branding asset storage under project_brain/assets/branding/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

BRANDING_ASSETS_SUBDIR = Path("project_brain") / "assets" / "branding"
LEGACY_LOGO_SUBDIR = Path("project_brain") / "channel_assets"

MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_CTA_GRAPHIC_BYTES = 2 * 1024 * 1024
MAX_INTRO_OUTRO_IMAGE_BYTES = 5 * 1024 * 1024
MAX_INTRO_OUTRO_VIDEO_BYTES = 25 * 1024 * 1024

ASSET_KINDS = {
    "logo": {"max_bytes": MAX_LOGO_BYTES, "allow_video": False},
    "cta_graphic": {"max_bytes": MAX_CTA_GRAPHIC_BYTES, "allow_video": False},
    "intro_image": {"max_bytes": MAX_INTRO_OUTRO_IMAGE_BYTES, "allow_video": False},
    "intro_video": {"max_bytes": MAX_INTRO_OUTRO_VIDEO_BYTES, "allow_video": True},
    "outro_image": {"max_bytes": MAX_INTRO_OUTRO_IMAGE_BYTES, "allow_video": False},
    "outro_video": {"max_bytes": MAX_INTRO_OUTRO_VIDEO_BYTES, "allow_video": True},
}


def detect_image_extension(payload: bytes) -> str | None:
    if payload.startswith(b"\x89PNG"):
        return ".png"
    if len(payload) >= 3 and payload[:3] == b"\xff\xd8\xff":
        return ".jpg"
    return None


def validate_branding_upload(
    payload: bytes,
    *,
    kind: str,
    content_type: str = "",
    filename: str = "",
) -> tuple[str, str]:
    spec = ASSET_KINDS.get(kind)
    if spec is None:
        raise ValueError(f"Unsupported branding asset kind: {kind}")
    if not payload:
        raise ValueError("Upload is empty.")
    if len(payload) > int(spec["max_bytes"]):
        max_mb = int(spec["max_bytes"]) / (1024 * 1024)
        raise ValueError(f"File exceeds {max_mb:.0f}MB limit for {kind}.")

    lower_name = str(filename or "").lower()
    lower_type = str(content_type or "").lower()

    if spec["allow_video"]:
        is_mp4 = payload[4:8] == b"ftyp" or lower_name.endswith(".mp4") or "mp4" in lower_type
        if not is_mp4:
            raise ValueError(f"{kind} must be an MP4 video file.")
        return ".mp4", "video/mp4"

    ext = detect_image_extension(payload)
    if ext is None:
        raise ValueError(f"{kind} must be PNG or JPEG/JPG.")
    return ext, "image/png" if ext == ".png" else "image/jpeg"


class BrandingAssetsStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.assets_dir = self.project_root / BRANDING_ASSETS_SUBDIR
        self.legacy_logo_dir = self.project_root / LEGACY_LOGO_SUBDIR

    def _path_for(self, kind: str, ext: str) -> Path:
        return self.assets_dir / f"{kind}{ext}"

    def save_asset(self, kind: str, payload: bytes, *, content_type: str = "", filename: str = "") -> str:
        ext, _ = validate_branding_upload(payload, kind=kind, content_type=content_type, filename=filename)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        for existing in self.assets_dir.glob(f"{kind}.*"):
            if existing.is_file():
                existing.unlink(missing_ok=True)
        target = self._path_for(kind, ext)
        target.write_bytes(payload)
        return str(target.resolve())

    def asset_path(self, kind: str) -> Path | None:
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        matches = sorted(self.assets_dir.glob(f"{kind}.*"))
        for path in matches:
            if path.is_file() and path.stat().st_size > 0:
                return path
        if kind == "logo":
            legacy = self.legacy_logo_dir / "logo.png"
            if legacy.is_file() and legacy.stat().st_size > 0:
                return legacy
        return None

    def asset_exists(self, kind: str) -> bool:
        return self.asset_path(kind) is not None

    def logo_status(self) -> dict[str, Any]:
        path = self.asset_path("logo")
        return {
            "logo_path": str(path) if path else "",
            "logo_exists": path is not None,
        }

    def save_logo_bytes(self, payload: bytes, *, content_type: str = "", filename: str = "") -> str:
        return self.save_asset("logo", payload, content_type=content_type, filename=filename)

    @property
    def logo_path(self) -> Path:
        return self.asset_path("logo") or (self.assets_dir / "logo.png")


__all__ = [
    "ASSET_KINDS",
    "BRANDING_ASSETS_SUBDIR",
    "BrandingAssetsStore",
    "detect_image_extension",
    "validate_branding_upload",
]
