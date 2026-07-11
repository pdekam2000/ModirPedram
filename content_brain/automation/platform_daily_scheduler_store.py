"""Per-platform daily automation settings — persisted independently per platform."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.json_utf8 import dumps_json, repair_mojibake_text

PLATFORM_DAILY_SCHEDULER_VERSION = "platform_daily_scheduler_v1"
SETTINGS_PATH = Path("project_brain") / "automation" / "platform_daily_scheduler.json"

PLATFORMS = ("youtube_shorts", "instagram_reels", "tiktok")

ALLOWED_DURATION_SECONDS = (15, 30, 45, 60)

PLATFORM_DURATION_ROOT_KEYS: dict[str, str] = {
    "youtube_shorts": "youtube_duration_seconds",
    "instagram_reels": "instagram_duration_seconds",
    "tiktok": "tiktok_duration_seconds",
}

DEFAULT_PLATFORM_ENTRY: dict[str, Any] = {
    "enabled": False,
    "topic": "",
    "videos_per_day": 3,
    "interval_hours": 4,
    "start_hour": 8,
    "duration_seconds": 30,
}

DEFAULT_STATE: dict[str, Any] = {
    "version": PLATFORM_DAILY_SCHEDULER_VERSION,
    "youtube_duration_seconds": 45,
    "instagram_duration_seconds": 45,
    "tiktok_duration_seconds": 30,
    "platforms": {platform: dict(DEFAULT_PLATFORM_ENTRY) for platform in PLATFORMS},
    "updated_at": "",
}


def _normalize_duration_seconds(value: Any) -> int:
    seconds = int(value or 30)
    if seconds in ALLOWED_DURATION_SECONDS:
        return seconds
    return 30


def get_platform_duration(platform: str, state: dict[str, Any] | None = None) -> int:
    """Return configured duration for a platform from scheduler state."""
    platform_key = str(platform or "").strip().lower()
    if platform_key in {"youtube", "youtube_shorts"}:
        platform_key = "youtube_shorts"
    elif platform_key in {"instagram", "instagram_reels"}:
        platform_key = "instagram_reels"
    elif platform_key == "tiktok":
        platform_key = "tiktok"
    if platform_key not in PLATFORMS:
        platform_key = "youtube_shorts"
    payload = dict(state or {})
    entry = dict((payload.get("platforms") or {}).get(platform_key) or {})
    root_key = PLATFORM_DURATION_ROOT_KEYS.get(platform_key, "")
    for candidate in (
        entry.get("duration_seconds"),
        payload.get(root_key) if root_key else None,
        DEFAULT_STATE.get(root_key) if root_key else None,
    ):
        normalized = _normalize_duration_seconds(candidate)
        if normalized in ALLOWED_DURATION_SECONDS:
            return normalized
    return 30


def resolve_platform_duration_seconds(
    project_root: str | Path,
    platform: str,
    *,
    profile: dict[str, Any] | None = None,
) -> int:
    """Scheduler platform duration → channel profile default → code default."""
    store = PlatformDailySchedulerStore(project_root)
    scheduled = store.get_platform_duration(platform)
    if profile is None:
        from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

        profile = ProductChannelProfileStore(project_root).load()
    profile_default = int(profile.get("default_duration_seconds") or 30)
    if scheduled in ALLOWED_DURATION_SECONDS:
        return scheduled
    if profile_default in ALLOWED_DURATION_SECONDS:
        return profile_default
    return 30


def _sync_duration_root_keys(state: dict[str, Any]) -> dict[str, Any]:
    """Platform entries are source of truth; root keys mirror them for persistence."""
    platforms = dict(state.get("platforms") or {})
    for platform, root_key in PLATFORM_DURATION_ROOT_KEYS.items():
        entry = dict(platforms.get(platform) or DEFAULT_PLATFORM_ENTRY)
        duration = _normalize_duration_seconds(entry.get("duration_seconds"))
        entry["duration_seconds"] = duration
        state[root_key] = duration
        platforms[platform] = entry
    state["platforms"] = platforms
    return state


class PlatformDailySchedulerStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / SETTINGS_PATH

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_platform_duration(self, platform: str) -> int:
        return get_platform_duration(platform, self.load())

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._with_profile_topics(_sync_duration_root_keys(dict(DEFAULT_STATE)))
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._with_profile_topics(_sync_duration_root_keys(dict(DEFAULT_STATE)))
        if not isinstance(payload, dict):
            return self._with_profile_topics(_sync_duration_root_keys(dict(DEFAULT_STATE)))
        payload = repair_mojibake_text(payload)
        merged = dict(DEFAULT_STATE)
        merged.update(payload)
        platforms: dict[str, Any] = {}
        raw_platforms = dict(payload.get("platforms") or {})
        for platform in PLATFORMS:
            entry = dict(DEFAULT_PLATFORM_ENTRY)
            if isinstance(raw_platforms.get(platform), dict):
                entry.update(raw_platforms[platform])
            platforms[platform] = entry
        merged["platforms"] = platforms
        return self._with_profile_topics(_sync_duration_root_keys(merged))

    def _with_profile_topics(self, state: dict[str, Any]) -> dict[str, Any]:
        from content_brain.automation.platform_daily_scheduler import display_platform_topic, resolve_platform_job_title
        from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

        profile = ProductChannelProfileStore(self.project_root).load()
        platforms = dict(state.get("platforms") or {})
        for platform in PLATFORMS:
            entry = dict(DEFAULT_PLATFORM_ENTRY)
            entry.update(platforms.get(platform) or {})
            if not str(entry.get("topic") or "").strip():
                entry["topic"] = resolve_platform_job_title(platform, profile, "")
            else:
                entry["topic"] = display_platform_topic(platform, profile, str(entry.get("topic") or ""))
            platforms[platform] = entry
        state["platforms"] = platforms
        return state

    def save_platform(self, platform: str, updates: dict[str, Any]) -> dict[str, Any]:
        platform_key = str(platform or "").strip().lower()
        if platform_key not in PLATFORMS:
            raise ValueError(f"unsupported platform: {platform}")
        current = self.load()
        platforms = dict(current.get("platforms") or {})
        entry = dict(platforms.get(platform_key) or DEFAULT_PLATFORM_ENTRY)
        for key in ("enabled", "topic", "videos_per_day", "interval_hours", "start_hour", "duration_seconds"):
            if key in updates and updates[key] is not None:
                entry[key] = updates[key]
        entry["enabled"] = bool(entry.get("enabled"))
        entry["videos_per_day"] = max(1, min(5, int(entry.get("videos_per_day") or 3)))
        entry["interval_hours"] = max(1, min(8, int(entry.get("interval_hours") or 4)))
        entry["start_hour"] = max(0, min(23, int(entry.get("start_hour") or 8)))
        entry["duration_seconds"] = _normalize_duration_seconds(entry.get("duration_seconds"))
        entry["topic"] = str(entry.get("topic") or "").strip()
        platforms[platform_key] = entry
        current["platforms"] = platforms
        current = _sync_duration_root_keys(current)
        current["updated_at"] = self._now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dumps_json(current), encoding="utf-8")
        return self.load()

    def save_all(self, payload: dict[str, Any]) -> dict[str, Any]:
        platforms_payload = dict(payload.get("platforms") or {})
        for platform, updates in platforms_payload.items():
            if isinstance(updates, dict):
                self.save_platform(platform, updates)
        return self.load()

    def enabled_daily_cap(self) -> int:
        total = 0
        for platform in PLATFORMS:
            entry = dict((self.load().get("platforms") or {}).get(platform) or {})
            if entry.get("enabled"):
                total += int(entry.get("videos_per_day") or 0)
        return max(total, 0)

    def any_platform_enabled(self) -> bool:
        return self.enabled_daily_cap() > 0

    def record_platform_completion(self, platform: str) -> dict[str, Any]:
        from datetime import date

        today = date.today().isoformat()
        current = self.load()
        completion = dict(current.get("daily_completion") or {})
        if completion.get("date") != today:
            completion = {"date": today, "platforms": {}, "completed_today": 0}
        platforms = dict(completion.get("platforms") or {})
        platforms[str(platform)] = int(platforms.get(str(platform)) or 0) + 1
        completion["platforms"] = platforms
        completion["completed_today"] = int(completion.get("completed_today") or 0) + 1
        current["daily_completion"] = completion
        current["updated_at"] = self._now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dumps_json(current), encoding="utf-8")
        return completion

    def reset_daily_completion(self, platform: str | None = None) -> dict[str, Any]:
        from datetime import date

        from content_brain.automation.automation_queue import normalize_platform_alias

        today = date.today().isoformat()
        current = self.load()
        completion = dict(current.get("daily_completion") or {})
        if completion.get("date") != today:
            completion = {"date": today, "platforms": {}, "completed_today": 0}
            current["daily_completion"] = completion
            current["updated_at"] = self._now()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(dumps_json(current), encoding="utf-8")
            return completion

        platforms = dict(completion.get("platforms") or {})
        normalized = normalize_platform_alias(platform)
        if normalized is None:
            platforms = {}
            completion["completed_today"] = 0
        else:
            platforms[normalized] = 0
            completion["completed_today"] = sum(int(value or 0) for value in platforms.values())
        completion["platforms"] = platforms
        completion["date"] = today
        current["daily_completion"] = completion
        current["updated_at"] = self._now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dumps_json(current), encoding="utf-8")
        return completion


__all__ = [
    "DEFAULT_PLATFORM_ENTRY",
    "PLATFORMS",
    "PLATFORM_DAILY_SCHEDULER_VERSION",
    "PlatformDailySchedulerStore",
    "get_platform_duration",
    "resolve_platform_duration_seconds",
]
