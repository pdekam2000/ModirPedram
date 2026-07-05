"""Per-platform daily automation settings — persisted independently per platform."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLATFORM_DAILY_SCHEDULER_VERSION = "platform_daily_scheduler_v1"
SETTINGS_PATH = Path("project_brain") / "automation" / "platform_daily_scheduler.json"

PLATFORMS = ("youtube_shorts", "instagram_reels", "tiktok")

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
    "platforms": {platform: dict(DEFAULT_PLATFORM_ENTRY) for platform in PLATFORMS},
    "updated_at": "",
}


class PlatformDailySchedulerStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / SETTINGS_PATH

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._with_profile_topics(dict(DEFAULT_STATE))
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._with_profile_topics(dict(DEFAULT_STATE))
        if not isinstance(payload, dict):
            return self._with_profile_topics(dict(DEFAULT_STATE))
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
        return self._with_profile_topics(merged)

    def _with_profile_topics(self, state: dict[str, Any]) -> dict[str, Any]:
        from content_brain.automation.platform_daily_scheduler import resolve_platform_job_title
        from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

        profile = ProductChannelProfileStore(self.project_root).load()
        platforms = dict(state.get("platforms") or {})
        for platform in PLATFORMS:
            entry = dict(DEFAULT_PLATFORM_ENTRY)
            entry.update(platforms.get(platform) or {})
            if not str(entry.get("topic") or "").strip():
                entry["topic"] = resolve_platform_job_title(platform, profile, "")
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
        entry["duration_seconds"] = max(15, min(60, int(entry.get("duration_seconds") or 30)))
        entry["topic"] = str(entry.get("topic") or "").strip()
        platforms[platform_key] = entry
        current["platforms"] = platforms
        current["updated_at"] = self._now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
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
        self.path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
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
            self.path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
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
        self.path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        return completion


__all__ = [
    "DEFAULT_PLATFORM_ENTRY",
    "PLATFORMS",
    "PLATFORM_DAILY_SCHEDULER_VERSION",
    "PlatformDailySchedulerStore",
]
