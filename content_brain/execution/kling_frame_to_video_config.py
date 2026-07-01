"""Kling Frame-to-Video — UI map constants and required labels (P1)."""

from __future__ import annotations

KLING_FRAME_TO_VIDEO_CONFIG_VERSION = "kling_frame_to_video_config_v1"
KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS = 15
KLING_FRAME_TO_VIDEO_MIN_DURATION_SECONDS = 3

REQUIRED_KLING_FRAME_LABELS: tuple[str, ...] = (
    "kling_frame_to_video_mode",
    "frame_prompt_box",
    "first_frame_upload",
    "end_frame_upload",
    "duration_slider_handle",
    "duration_slider_track",
    "duration_display_value",
    "audio_toggle_on",
    "generate_button",
    "download_button",
    "use_frame_button",
)

OPTIONAL_KLING_FRAME_LABELS: tuple[str, ...] = (
    "provider_kling_3_pro",
    "download_mp4_button",
    "latest_video_download_button",
)

BLOCKED_KLING_FRAME_CLICK_LABELS: frozenset[str] = frozenset({"generate_button"})

DOWNLOAD_BUTTON_ALIASES: tuple[str, ...] = ("download_button", "download_mp4_button", "latest_video_download_button")

KLING_FRAME_LIVE_DRY_RUN_P2_VERSION = "kling_frame_live_dry_run_p2_v2"

# P2 live dry-run checklist — locate/verify only; no Generate, credits, or download.
KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS: tuple[str, ...] = (
    "frame_mode",
    "prompt",
    "first_frame_upload",
    "duration_reaches_15s",
    "duration_popover_closed",
    "duration_stable_after_dismiss",
    "audio_on",
    "generate_visible",
)

# Legacy aggregate — true only when all duration sub-checks pass.
KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS: tuple[str, ...] = (
    "duration_reaches_15s",
    "duration_popover_closed",
    "duration_stable_after_dismiss",
)

KLING_FRAME_LIVE_DRY_RUN_P2_LABELS: dict[str, str] = {
    "frame_mode": "kling_frame_to_video_mode",
    "prompt": "frame_prompt_box",
    "first_frame_upload": "first_frame_upload",
    "duration_reaches_15s": "duration_display_value",
    "duration_popover_closed": "duration_display_value",
    "duration_stable_after_dismiss": "duration_display_value",
    "audio_on": "audio_toggle_on",
    "generate_visible": "generate_button",
}

BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS: frozenset[str] = frozenset(
    {"generate_click", "download", "upload_file", "credit_spend"}
)

__all__ = [
    "BLOCKED_KLING_FRAME_CLICK_LABELS",
    "BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS",
    "DOWNLOAD_BUTTON_ALIASES",
    "KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS",
    "KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS",
    "KLING_FRAME_LIVE_DRY_RUN_P2_LABELS",
    "KLING_FRAME_LIVE_DRY_RUN_P2_VERSION",
    "KLING_FRAME_TO_VIDEO_CONFIG_VERSION",
    "KLING_FRAME_TO_VIDEO_MIN_DURATION_SECONDS",
    "KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS",
    "OPTIONAL_KLING_FRAME_LABELS",
    "REQUIRED_KLING_FRAME_LABELS",
]
