"""Kling Multishot — constants and 2-shot continuity strategy."""

from __future__ import annotations

KLING_MULTISHOT_CONFIG_VERSION = "kling_multishot_config_v1"

# Canonical strategy (see KLING_STORY_ARCHITECTURE_DESIGN.md)
MULTISHOT_STRATEGY = "two_shot_continuity"
CLIP_DURATION_SECONDS = 15
SHOT_1_DURATION_SECONDS = 12
SHOT_2_DURATION_SECONDS = 3

REQUIRED_KLING_LABELS: tuple[str, ...] = (
    "provider_kling_3_pro",
    "multishot_tab",
    "audio_toggle_on",
    "first_frame_upload",
    "shot_1_prompt",
    "shot_2_prompt",
    "shot_1_duration_menu",
    "shot_1_duration_12s",
    "shot_2_duration_menu",
    "shot_2_duration_3s",
    "generate_button",
)

OPTIONAL_KLING_LABELS: tuple[str, ...] = (
    "add_shot_button",
    "shot_3_prompt",
    "shot_4_prompt",
    "shot_5_prompt",
)

APPROVAL_GATED_KLING_LABELS: frozenset[str] = frozenset({"generate_button"})

BLOCKED_CLICK_LABELS: frozenset[str] = frozenset({"generate_button"})

__all__ = [
    "APPROVAL_GATED_KLING_LABELS",
    "BLOCKED_CLICK_LABELS",
    "CLIP_DURATION_SECONDS",
    "KLING_MULTISHOT_CONFIG_VERSION",
    "MULTISHOT_STRATEGY",
    "OPTIONAL_KLING_LABELS",
    "REQUIRED_KLING_LABELS",
    "SHOT_1_DURATION_SECONDS",
    "SHOT_2_DURATION_SECONDS",
]
