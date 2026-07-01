"""Platform → default aspect ratio mapping for Product Studio."""

from __future__ import annotations

PLATFORM_ASPECT_DEFAULTS: dict[str, str] = {
    "tiktok": "9:16",
    "instagram_reels": "9:16",
    "youtube_shorts": "9:16",
    "youtube_long": "16:9",
    "multi": "9:16",
}

VERTICAL_PLATFORMS: frozenset[str] = frozenset({"tiktok", "instagram_reels", "youtube_shorts", "multi"})
HORIZONTAL_PLATFORMS: frozenset[str] = frozenset({"youtube_long"})


def normalize_platform_id(platform: str) -> str:
    key = str(platform or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "instagram": "instagram_reels",
        "reels": "instagram_reels",
        "shorts": "youtube_shorts",
        "youtube": "youtube_long",
        "longform": "youtube_long",
        "long_form": "youtube_long",
    }
    return aliases.get(key, key)


def default_aspect_ratio_for_platform(platform: str) -> str:
    return PLATFORM_ASPECT_DEFAULTS.get(normalize_platform_id(platform), "9:16")


def resolve_aspect_ratio(
    *,
    platform: str,
    aspect_ratio: str | None = None,
    aspect_ratio_manual: bool = False,
) -> str:
    explicit = str(aspect_ratio or "").strip()
    platform_key = normalize_platform_id(platform)
    platform_default = default_aspect_ratio_for_platform(platform)
    if aspect_ratio_manual and explicit in {"9:16", "16:9"}:
        return explicit
    if explicit == "16:9" and platform_key in VERTICAL_PLATFORMS:
        return "9:16"
    if explicit in {"9:16", "16:9"}:
        return explicit
    return platform_default


__all__ = [
    "PLATFORM_ASPECT_DEFAULTS",
    "default_aspect_ratio_for_platform",
    "normalize_platform_id",
    "resolve_aspect_ratio",
]
