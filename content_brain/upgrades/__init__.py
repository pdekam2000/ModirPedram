"""Upgrade Center foundation — patch-ready registry stub."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.upgrades.patch_upload_service import list_uploaded_patches, upload_patch_package

UPGRADE_CENTER_VERSION = "upgrade_center_foundation_v1"

FUTURE_PATCHES = [
    "Auto Upload Patch",
    "Real ElevenLabs Voice Patch",
    "Burned Subtitle Patch",
    "TikTok Upload Patch",
    "YouTube Upload Patch",
    "Instagram Upload Patch",
    "Advanced Calendar Automation Patch",
    "Multi-channel Management Patch",
    "Music/SFX Patch",
    "Suno Music Patch",
]


def list_future_patches() -> list[str]:
    return list(FUTURE_PATCHES)


def list_upgrade_center_patches(project_root: str | Path) -> dict[str, Any]:
    uploaded = list_uploaded_patches(project_root)
    return {
        "future_patches": list_future_patches(),
        "uploaded_patches": uploaded,
        "patches": list_future_patches() + [item["label"] for item in uploaded],
    }


__all__ = [
    "FUTURE_PATCHES",
    "UPGRADE_CENTER_VERSION",
    "list_future_patches",
    "list_upgrade_center_patches",
    "list_uploaded_patches",
    "upload_patch_package",
]
