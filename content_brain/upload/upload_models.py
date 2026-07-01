"""Upload package models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UPLOAD_MODELS_VERSION = "upload_models_v1"

PLATFORM_YOUTUBE = "youtube_shorts"
PLATFORM_TIKTOK = "tiktok"
PLATFORM_INSTAGRAM = "instagram_reels"

PRIVACY_PRIVATE = "private"
PRIVACY_UNLISTED = "unlisted"
PRIVACY_PUBLIC = "public"


@dataclass
class UploadTarget:
    platform: str
    enabled: bool = False
    status: str = "prepared"
    video_path: str = ""
    title: str = ""
    description: str = ""
    hashtags: list[str] = field(default_factory=list)
    privacy: str = PRIVACY_PRIVATE
    metadata_path: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "enabled": self.enabled,
            "status": self.status,
            "video_path": self.video_path,
            "title": self.title,
            "description": self.description,
            "hashtags": list(self.hashtags),
            "privacy": self.privacy,
            "metadata_path": self.metadata_path,
            "warnings": list(self.warnings),
        }


@dataclass
class UploadPackage:
    version: str = UPLOAD_MODELS_VERSION
    run_id: str = ""
    topic: str = ""
    package_dir: str = ""
    video_path: str = ""
    publish_package_path: str = ""
    auto_upload_enabled: bool = False
    targets: list[UploadTarget] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "topic": self.topic,
            "package_dir": self.package_dir,
            "video_path": self.video_path,
            "publish_package_path": self.publish_package_path,
            "auto_upload_enabled": self.auto_upload_enabled,
            "targets": [target.to_dict() for target in self.targets],
            "created_at": self.created_at,
        }


__all__ = [
    "PLATFORM_INSTAGRAM",
    "PLATFORM_TIKTOK",
    "PLATFORM_YOUTUBE",
    "PRIVACY_PRIVATE",
    "PRIVACY_PUBLIC",
    "PRIVACY_UNLISTED",
    "UPLOAD_MODELS_VERSION",
    "UploadPackage",
    "UploadTarget",
]
