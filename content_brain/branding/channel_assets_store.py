"""Channel asset storage — backward-compatible wrapper for branding assets."""

from __future__ import annotations

from pathlib import Path

from content_brain.branding.branding_assets_store import BRANDING_ASSETS_SUBDIR, BrandingAssetsStore

CHANNEL_ASSETS_SUBDIR = BRANDING_ASSETS_SUBDIR
LOGO_FILENAME = "logo.png"


class ChannelAssetsStore(BrandingAssetsStore):
    """Legacy name — stores assets under project_brain/assets/branding/."""

    pass


__all__ = ["CHANNEL_ASSETS_SUBDIR", "ChannelAssetsStore", "LOGO_FILENAME"]
