"""
Phase 12B — User Acceptance Test runtime profile (caps and session helpers).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

UAT_PROFILE_VERSION = "12b_v1"
UAT_SESSION_PREFIX = "exec_uat_"
UAT_TRIGGER = "operator_uat"

UAT_MIN_DURATION_SECONDS = 15
UAT_MAX_DURATION_SECONDS = 90
UAT_MAX_VIDEO_CLIPS = 6
UAT_MAX_VOICE_SEGMENTS = 8
UAT_MAX_ASSEMBLY_OUTPUT_BYTES = 50_000_000
UAT_ASSEMBLY_TIMEOUT_SECONDS = 300
UAT_MAX_ESTIMATED_VOICE_COST_USD = 1.0

# Live ElevenLabs smoke (11H-2d) allows max 1 voice segment — UAT-only guard (Option A).
UAT_LIVE_VOICE_SMOKE_MAX_SEGMENTS = 1
UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS = 6
UAT_SINGLE_SEGMENT_SAFE_DURATION_BY_VIDEO_PROVIDER: dict[str, int] = {
    "runway_browser": 10,
    "hailuo_browser": 6,
    "mock": 10,
}

# Provider-aware UAT form defaults (not a global duration for all video providers).
UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER: dict[str, int] = {
    "runway_browser": 10,
    "hailuo_browser": 8,
    "mock": 10,
}

PLATFORM_ALIASES: dict[str, str] = {
    "youtube_shorts": "youtube_shorts",
    "youtube shorts": "youtube_shorts",
    "shorts": "youtube_shorts",
    "tiktok": "tiktok",
    "instagram_reels": "instagram_reels",
    "reels": "instagram_reels",
}

VIDEO_PROVIDER_ALIASES: dict[str, str] = {
    "runway_browser": "runway_browser",
    "runway": "runway_browser",
    "hailuo_browser": "hailuo_browser",
    "hailuo": "hailuo_browser",
}

VOICE_PROVIDER_ALIASES: dict[str, str] = {
    "elevenlabs": "elevenlabs",
    "live_elevenlabs": "elevenlabs",
    "mock": "mock",
}


def generate_uat_session_id(*, now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"{UAT_SESSION_PREFIX}{stamp}"


def normalize_platform(value: str) -> str:
    key = str(value or "").strip().lower().replace("-", "_")
    return PLATFORM_ALIASES.get(key, key or "youtube_shorts")


def normalize_video_provider(value: str) -> str:
    key = str(value or "").strip().lower().replace("-", "_")
    return VIDEO_PROVIDER_ALIASES.get(key, key or "runway_browser")


def normalize_voice_provider(value: str) -> str:
    key = str(value or "").strip().lower().replace("-", "_")
    return VOICE_PROVIDER_ALIASES.get(key, key or "elevenlabs")


def clamp_duration(seconds: int, *, smoke_single_segment: bool = False) -> int:
    min_seconds = UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS if smoke_single_segment else UAT_MIN_DURATION_SECONDS
    return max(min_seconds, min(int(seconds), UAT_MAX_DURATION_SECONDS))


def uat_single_segment_safe_duration(video_provider: str) -> int:
    key = normalize_video_provider(video_provider)
    return UAT_SINGLE_SEGMENT_SAFE_DURATION_BY_VIDEO_PROVIDER.get(key, 10)


def uat_default_duration_seconds(video_provider: str) -> int:
    key = normalize_video_provider(video_provider)
    return UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER.get(key, 10)


def is_e2e_full_duration_validation() -> bool:
    """Phase E2E-40S — allow requested duration when validation harness sets env flag."""
    return os.getenv("UAT_E2E_VALIDATION_FULL_DURATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def requires_live_voice_smoke_guard(config: UatRuntimeConfig) -> bool:
    if is_e2e_full_duration_validation():
        return False
    return config.voice_provider == "elevenlabs" and config.confirm_real_voice


def apply_live_voice_smoke_duration_guard(
    config: UatRuntimeConfig,
) -> tuple[UatRuntimeConfig, list[str], dict[str, int]]:
    """
    Option A — before segment planning, reduce duration so clip/segment count stays
    within 11H-2d live-voice smoke cap (1 segment). UAT-only; does not change providers.
    """
    if not requires_live_voice_smoke_guard(config):
        return config, [], {}

    safe_duration = uat_single_segment_safe_duration(config.video_provider)
    original = int(config.duration_seconds)
    if original <= safe_duration:
        return config, [], {}

    warning = (
        f"Live voice smoke safety: duration reduced from {original}s to {safe_duration}s "
        f"to satisfy the 11H-2d single-segment smoke cap (max {UAT_LIVE_VOICE_SMOKE_MAX_SEGMENTS} segment). "
        "This is a smoke safety limit, not a Content Brain failure."
    )
    adjusted = UatRuntimeConfig(
        topic=config.topic,
        platform=config.platform,
        duration_seconds=safe_duration,
        video_provider=config.video_provider,
        voice_provider=config.voice_provider,
        confirm_real_voice=config.confirm_real_voice,
        confirm_real_video=config.confirm_real_video,
        confirm_real_assembly=config.confirm_real_assembly,
        open_folder=config.open_folder,
        niche=config.niche,
        triggered_by=config.triggered_by,
    ).normalized(smoke_single_segment=True)

    meta = {
        "original_duration_seconds": original,
        "smoke_adjusted_duration_seconds": adjusted.duration_seconds,
    }
    return adjusted, [warning], meta


@dataclass
class UatRuntimeConfig:
    topic: str
    platform: str = "youtube_shorts"
    duration_seconds: int = 10
    video_provider: str = "runway_browser"
    voice_provider: str = "elevenlabs"
    confirm_real_voice: bool = False
    confirm_real_video: bool = False
    confirm_real_assembly: bool = False
    open_folder: bool = False
    niche: str = "general"
    triggered_by: str = UAT_TRIGGER

    def normalized(self, *, smoke_single_segment: bool = False) -> UatRuntimeConfig:
        return UatRuntimeConfig(
            topic=str(self.topic or "").strip(),
            platform=normalize_platform(self.platform),
            duration_seconds=clamp_duration(self.duration_seconds, smoke_single_segment=smoke_single_segment),
            video_provider=normalize_video_provider(self.video_provider),
            voice_provider=normalize_voice_provider(self.voice_provider),
            confirm_real_voice=bool(self.confirm_real_voice),
            confirm_real_video=bool(self.confirm_real_video),
            confirm_real_assembly=bool(self.confirm_real_assembly),
            open_folder=bool(self.open_folder),
            niche=str(self.niche or "general").strip() or "general",
            triggered_by=self.triggered_by,
        )


def uat_caps_snapshot() -> dict[str, int | float | str]:
    return {
        "profile_version": UAT_PROFILE_VERSION,
        "min_duration_seconds": UAT_MIN_DURATION_SECONDS,
        "max_duration_seconds": UAT_MAX_DURATION_SECONDS,
        "max_video_clips": UAT_MAX_VIDEO_CLIPS,
        "max_voice_segments": UAT_MAX_VOICE_SEGMENTS,
        "max_assembly_output_bytes": UAT_MAX_ASSEMBLY_OUTPUT_BYTES,
        "assembly_timeout_seconds": UAT_ASSEMBLY_TIMEOUT_SECONDS,
        "max_estimated_voice_cost_usd": UAT_MAX_ESTIMATED_VOICE_COST_USD,
        "live_voice_smoke_max_segments": UAT_LIVE_VOICE_SMOKE_MAX_SEGMENTS,
        "single_segment_safe_duration_runway_browser": UAT_SINGLE_SEGMENT_SAFE_DURATION_BY_VIDEO_PROVIDER[
            "runway_browser"
        ],
        "default_duration_runway_browser": UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER["runway_browser"],
        "default_duration_hailuo_browser": UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER["hailuo_browser"],
    }


def build_uat_operations_block(config: UatRuntimeConfig, session_id: str) -> dict[str, Any]:
    return {
        "uat_run": {
            "mode": "user_acceptance_test",
            "profile_version": UAT_PROFILE_VERSION,
            "session_id": session_id,
            "topic": config.topic,
            "platform": config.platform,
            "target_duration_seconds": config.duration_seconds,
            "video_provider": config.video_provider,
            "voice_provider": config.voice_provider,
            "confirm_real_voice": config.confirm_real_voice,
            "confirm_real_video": config.confirm_real_video,
            "confirm_real_assembly": config.confirm_real_assembly,
            "triggered_by": config.triggered_by,
            "status": "running",
        }
    }


__all__ = [
    "UAT_PROFILE_VERSION",
    "UAT_SESSION_PREFIX",
    "UAT_TRIGGER",
    "UAT_MIN_DURATION_SECONDS",
    "UAT_MAX_DURATION_SECONDS",
    "UAT_MAX_VIDEO_CLIPS",
    "UAT_MAX_VOICE_SEGMENTS",
    "UAT_MAX_ASSEMBLY_OUTPUT_BYTES",
    "UAT_ASSEMBLY_TIMEOUT_SECONDS",
    "UAT_MAX_ESTIMATED_VOICE_COST_USD",
    "UAT_LIVE_VOICE_SMOKE_MAX_SEGMENTS",
    "UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS",
    "UAT_SINGLE_SEGMENT_SAFE_DURATION_BY_VIDEO_PROVIDER",
    "UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER",
    "uat_default_duration_seconds",
    "uat_single_segment_safe_duration",
    "is_e2e_full_duration_validation",
    "requires_live_voice_smoke_guard",
    "apply_live_voice_smoke_duration_guard",
    "UatRuntimeConfig",
    "generate_uat_session_id",
    "normalize_platform",
    "normalize_video_provider",
    "normalize_voice_provider",
    "clamp_duration",
    "uat_caps_snapshot",
    "build_uat_operations_block",
]
