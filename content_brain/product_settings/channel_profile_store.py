"""Persistent product channel profile for User Mode Settings."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRODUCT_SETTINGS_SUBDIR = Path("project_brain") / "product_settings"
PROFILE_FILENAME = "channel_profile.json"

DEFAULT_CHANNEL_PROFILE: dict[str, Any] = {
    "channel_name": "My Channel",
    "main_niche": "selfcare",
    "sub_niche": "women skincare",
    "channel_topic": "women skincare",
    "tiktok_channel_topic": "",
    "instagram_channel_topic": "",
    "target_audience": "young women interested in skincare routines",
    "language": "English",
    "tone_style": "cinematic",
    "visual_style": "cinematic realistic",
    "default_platform": "youtube_shorts",
    "default_duration_seconds": 30,
    "default_provider": "runway",
    "default_voice": "",
    "default_narration_provider": "elevenlabs",
    "music_provider": "local",
    "music_track_path": "assets/audio/music/whimsical_adventure.mp3",
    "music_volume": 0.16,
    "music_background_volume": 0.16,
    "ducking_strength": 0.35,
    "music_fade_in_seconds": 1.5,
    "music_fade_out_seconds": 2.0,
    "cta_preset": "follow_for_more",
    "cta_custom_slogan": "",
    "upload_platforms": ["tiktok", "instagram_reels", "youtube_shorts"],
    "preferred_topics": [],
    "forbidden_topics": [],
    "content_formats": [],
    "use_ai_director_default": True,
    "use_prompt_critic_default": True,
    "branding_enabled": True,
    "logo_enabled": True,
    "logo_position": "top_right",
    "logo_scale": 0.12,
    "subtitle_enabled": True,
    "subtitle_style": "tiktok",
    "subtitle_position": "lower_third",
    "cta_enabled": True,
    "cta_text": "Subscribe",
    "cta_position": "top_right",
    "cta_start_seconds": 5,
    "cta_end_seconds": 24,
    "cta_frequency": "end",
    "intro_enabled": False,
    "intro_text": "",
    "intro_duration": 2.0,
    "outro_enabled": False,
    "outro_text": "",
    "outro_duration": 2.0,
    "youtube_upload_enabled": False,
    "youtube_privacy": "private",
    "youtube_default_description": "",
    "youtube_default_hashtags": [],
    "youtube_upload_confirmed": False,
    "youtube_credentials_configured": False,
    "youtube_oauth_client_path": "",
    "youtube_made_for_kids": False,
    "youtube_require_confirmation": True,
    "local_mode": True,
    "asset_vault_enabled": True,
    "asset_copy_mode": "copy",
    "ambience_folder": "assets/audio/ambience",
    "sfx_folder": "assets/audio/sfx",
    "default_narrator_voice": "",
    "child_friendly_voice": "",
    "character_voice_2": "",
    "character_voice_mode": "multi_voice",
    "narration_style": "child_story",
    "updated_at": "",
}

LIST_PROFILE_FIELDS = (
    "upload_platforms",
    "preferred_topics",
    "forbidden_topics",
    "content_formats",
)


class ProductChannelProfileStore:
    """JSON-backed channel profile used by Product Studio Settings."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.profile_path = self.project_root / PRODUCT_SETTINGS_SUBDIR / PROFILE_FILENAME

    def load(self) -> dict[str, Any]:
        if not self.profile_path.is_file():
            return dict(DEFAULT_CHANNEL_PROFILE)
        try:
            payload = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_CHANNEL_PROFILE)
        if not isinstance(payload, dict):
            return dict(DEFAULT_CHANNEL_PROFILE)
        merged = dict(DEFAULT_CHANNEL_PROFILE)
        merged.update(payload)
        return merged

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        for key in DEFAULT_CHANNEL_PROFILE:
            if key == "updated_at":
                continue
            if key in payload and payload[key] is not None:
                current[key] = payload[key]
        for list_key in LIST_PROFILE_FIELDS:
            if list_key in payload:
                current[list_key] = list(payload.get(list_key) or [])
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.load()
