"""Per-platform video style resolution for Create Video / prompt generation."""

from __future__ import annotations

from typing import Any

PLATFORM_YOUTUBE = frozenset({"youtube_shorts", "youtube", "youtube_long"})
PLATFORM_INSTAGRAM = frozenset({"instagram_reels", "instagram"})
PLATFORM_TIKTOK = frozenset({"tiktok"})


def _normalize_platform(platform: str) -> str:
    return str(platform or "").strip().lower()


def resolve_platform_video_style(
    platform: str,
    profile: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> str:
    """Build visual_style string for the target platform (includes mood/pace hints)."""
    data = dict(payload or {})
    plat = _normalize_platform(platform)

    if plat in PLATFORM_YOUTUBE:
        base = str(
            data.get("youtube_video_style")
            or profile.get("youtube_video_style")
            or data.get("visual_style")
            or profile.get("visual_style")
            or profile.get("tone_style")
            or "cinematic realistic"
        ).strip()
        return base

    if plat in PLATFORM_INSTAGRAM:
        base = str(
            data.get("instagram_video_style")
            or profile.get("instagram_video_style")
            or "aesthetic"
        ).strip()
        mood = str(
            data.get("instagram_filter_mood")
            or profile.get("instagram_filter_mood")
            or "neutral"
        ).strip()
        return f"{base} — {mood} filter mood"

    if plat in PLATFORM_TIKTOK:
        base = str(
            data.get("tiktok_video_style")
            or profile.get("tiktok_video_style")
            or "energetic"
        ).strip()
        pace = str(data.get("tiktok_pace") or profile.get("tiktok_pace") or "medium").strip()
        return f"{base} — {pace} pace editing"

    return str(
        data.get("visual_style")
        or profile.get("visual_style")
        or profile.get("tone_style")
        or "cinematic realistic"
    ).strip()


def resolve_platform_mood(
    platform: str,
    profile: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> str:
    """Story ideation mood from platform-specific controls."""
    data = dict(payload or {})
    plat = _normalize_platform(platform)
    if plat in PLATFORM_INSTAGRAM:
        return str(
            data.get("instagram_filter_mood")
            or profile.get("instagram_filter_mood")
            or ""
        ).strip()
    if plat in PLATFORM_TIKTOK:
        return str(data.get("tiktok_pace") or profile.get("tiktok_pace") or "").strip()
    return str(data.get("mood") or data.get("tone") or profile.get("tone_style") or "").strip()


__all__ = [
    "resolve_platform_mood",
    "resolve_platform_video_style",
]
