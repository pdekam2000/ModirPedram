"""Per-platform daily job generation with upload interval spacing."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from content_brain.automation.platform_daily_scheduler_store import PLATFORMS, PlatformDailySchedulerStore
from content_brain.scheduling.duration_planner import plan_duration
from content_brain.scheduling.schedule_models import ScheduledVideoJob
from content_brain.execution.product_multiclip_execution_plan import plan_product_duration

PLATFORM_TOPIC_PROFILE_KEYS: dict[str, str] = {
    "youtube_shorts": "youtube_channel_topic",
    "instagram_reels": "instagram_channel_topic",
    "tiktok": "tiktok_channel_topic",
}

PLATFORM_UPLOAD_ENABLED_KEYS: dict[str, str] = {
    "youtube_shorts": "youtube_upload_enabled",
    "instagram_reels": "instagram_upload_enabled",
    "tiktok": "tiktok_upload_enabled",
}

MAX_JOB_TOPIC_CHARS = 120
JOB_TOPIC_DISPLAY_MAX = 80


def truncate_topic_display(text: str, max_len: int = JOB_TOPIC_DISPLAY_MAX) -> str:
    """UI-safe single-line topic label."""
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def resolve_platform_job_title(platform: str, profile: dict[str, Any], entry_topic: str = "") -> str:
    """Short automation job label — never the full channel brief document."""
    stored = " ".join(str(entry_topic or "").split()).strip()
    if stored and len(stored) <= MAX_JOB_TOPIC_CHARS:
        return stored

    from content_brain.execution.youtube_science_channel import CHANNEL_NAME

    if platform == "youtube_shorts":
        name = str(profile.get("channel_name") or CHANNEL_NAME).strip()
        return f"{name} — YouTube Shorts"
    if platform == "instagram_reels":
        return display_platform_topic(platform, profile, entry_topic)
    if platform == "tiktok":
        return display_platform_topic(platform, profile, entry_topic)
    return str(profile.get("channel_name") or platform.replace("_", " ").title())


def resolve_platform_topic(
    platform: str,
    profile: dict[str, Any],
    *,
    entry_topic: str = "",
    use_global_fallback: bool = True,
) -> str:
    """Resolve the full channel brief for prompts — not for automation job.topic."""
    if platform == "instagram_reels":
        brief = str(profile.get("instagram_channel_brief") or "").strip()
        if brief:
            return brief
    specific_key = PLATFORM_TOPIC_PROFILE_KEYS.get(platform, "channel_topic")
    specific = str(profile.get(specific_key) or "").strip()
    if specific:
        return specific
    stored = str(entry_topic or "").strip()
    if stored:
        return stored
    if use_global_fallback:
        return str(profile.get("channel_topic") or profile.get("main_niche") or "").strip()
    return ""


def display_platform_topic(platform: str, profile: dict[str, Any], entry_topic: str = "") -> str:
    """Short label for Upload Center / scheduler UI — never the OpenAI channel brief."""
    if platform == "instagram_reels":
        short = str(profile.get("instagram_channel_topic") or "").strip()
        if short and len(short) <= MAX_JOB_TOPIC_CHARS and not short.upper().startswith("INSTAGRAM CONTENT"):
            return short
        stored = " ".join(str(entry_topic or "").split()).strip()
        if stored and len(stored) <= MAX_JOB_TOPIC_CHARS and not stored.upper().startswith("INSTAGRAM CONTENT"):
            return stored
        return "Perfumery Ingredients — Daily Fragrance Education"
    if platform == "tiktok":
        short = str(profile.get("tiktok_channel_topic") or "").strip()
        if short and len(short) <= MAX_JOB_TOPIC_CHARS:
            return short
        return "Quick Fitness Tips — TikTok"
    return resolve_platform_job_title(platform, profile, entry_topic)


def _topic_needs_short_title(topic: str) -> bool:
    text = str(topic or "").strip()
    if not text:
        return True
    if len(text) > MAX_JOB_TOPIC_CHARS:
        return True
    upper = text.upper()
    return upper.startswith("MAIN CHANNEL TOPIC") or upper.startswith("MAIN INSTAGRAM CONTENT TOPIC")


def repair_planned_job_durations(project_root: str | Path) -> int:
    """Sync planned job durations from platform scheduler settings."""
    from content_brain.automation.automation_queue import JOB_PLANNED, JOB_RUNNING, AutomationQueue
    from content_brain.automation.platform_daily_scheduler_store import PlatformDailySchedulerStore

    store = PlatformDailySchedulerStore(project_root)
    queue = AutomationQueue(project_root)
    repaired = 0
    for job in queue.list_jobs():
        if job.status not in {JOB_PLANNED, JOB_RUNNING}:
            continue
        platform = str((job.platform_targets[0] if job.platform_targets else "") or "youtube_shorts")
        expected = store.get_platform_duration(platform)
        if int(job.duration or 0) == expected:
            continue
        product_duration = plan_product_duration(expected)
        queue.update_job(
            job.job_id,
            duration=expected,
            clip_count=int(product_duration.get("clip_count") or 2),
        )
        repaired += 1
    return repaired


def repair_planned_job_topics(project_root: str | Path) -> int:
    """Replace long brief text on planned/running jobs with short platform titles."""
    from content_brain.automation.automation_queue import JOB_PLANNED, JOB_RUNNING, AutomationQueue
    from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

    store = PlatformDailySchedulerStore(project_root)
    state = store.load()
    profile = ProductChannelProfileStore(project_root).load()
    queue = AutomationQueue(project_root)
    repaired = 0
    for job in queue.list_jobs():
        if job.status not in {JOB_PLANNED, JOB_RUNNING}:
            continue
        platform = str((job.platform_targets[0] if job.platform_targets else "") or "")
        entry = dict((state.get("platforms") or {}).get(platform) or {})
        short_title = resolve_platform_job_title(platform, profile, str(entry.get("topic") or ""))
        if job.topic == short_title and job.title == short_title:
            continue
        if not _topic_needs_short_title(job.topic) and not _topic_needs_short_title(job.title):
            continue
        queue.update_job(job.job_id, topic=short_title, title=short_title)
        repaired += 1
    return repaired


def compute_upload_times(*, videos_per_day: int, interval_hours: int, start_hour: int = 8) -> list[str]:
    times: list[str] = []
    count = max(1, min(5, int(videos_per_day)))
    step = max(1, min(8, int(interval_hours)))
    base = max(0, min(23, int(start_hour)))
    for index in range(count):
        hour = min(23, base + index * step)
        times.append(f"{hour:02d}:00")
    return times


def build_platform_daily_jobs(project_root: str | Path) -> list[dict[str, Any]]:
    """Build today's job specs using each platform's own topic from platform settings."""
    from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

    store = PlatformDailySchedulerStore(project_root)
    state = store.load()
    profile = ProductChannelProfileStore(project_root).load()
    today = date.today().isoformat()
    created: list[dict[str, Any]] = []

    for platform in PLATFORMS:
        entry = dict((state.get("platforms") or {}).get(platform) or {})
        if not entry.get("enabled"):
            continue
        job_title = resolve_platform_job_title(
            platform,
            profile,
            str(entry.get("topic") or ""),
        )
        if not job_title:
            continue
        duration_seconds = int(entry.get("duration_seconds") or 30)
        product_duration = plan_product_duration(duration_seconds)
        duration_plan = plan_duration(duration_seconds=duration_seconds, provider="runway")
        times = compute_upload_times(
            videos_per_day=int(entry.get("videos_per_day") or 3),
            interval_hours=int(entry.get("interval_hours") or 4),
            start_hour=int(entry.get("start_hour") or 8),
        )
        for planned_time in times:
            job = ScheduledVideoJob(
                schedule_id=f"daily_{platform}",
                planned_date=today,
                planned_time=planned_time,
                topic=job_title,
                duration_seconds=duration_seconds,
                clip_count=int(product_duration.get("clip_count") or duration_plan.clip_count),
                platform_targets=[platform],
                status="planned",
            )
            payload = job.to_dict()
            payload["title"] = job_title
            created.append(payload)

    return created


def sync_scheduler_enabled_from_profile(
    project_root: str | Path,
    profile: dict[str, Any] | None = None,
) -> list[str]:
    """Enable scheduler platforms from profile upload flags — never auto-disable.

    Upload Center is the only place that turns a platform OFF (`save_platform(enabled=False)`).
    A stale/false profile upload flag must not wipe scheduler.enabled on every sync tick.
    """
    from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

    if profile is None:
        profile = ProductChannelProfileStore(project_root).load()
    upload_platforms = {str(platform).strip().lower() for platform in (profile.get("upload_platforms") or [])}
    store = PlatformDailySchedulerStore(project_root)
    synced: list[str] = []
    for platform in PLATFORMS:
        flag_key = PLATFORM_UPLOAD_ENABLED_KEYS.get(platform, "")
        profile_wants_enabled = platform in upload_platforms and bool(profile.get(flag_key))
        entry = dict((store.load().get("platforms") or {}).get(platform) or {})
        already_enabled = bool(entry.get("enabled"))
        # Only promote OFF → ON from profile. Never demote ON → OFF here.
        if profile_wants_enabled and not already_enabled:
            store.save_platform(platform, {"enabled": True})
            synced.append(platform)
        # Explicit protection: never auto-disable Instagram (or any platform) from profile sync.
    return synced


def sync_platform_daily_jobs(project_root: str | Path) -> dict[str, Any]:
    """Create today's planned jobs for each enabled platform (independent schedules)."""
    from content_brain.automation.automation_queue import AutomationQueue

    sync_scheduler_enabled_from_profile(project_root)
    store = PlatformDailySchedulerStore(project_root)
    today = date.today().isoformat()
    queue = AutomationQueue(project_root)
    stale_cancelled = queue.cancel_stale_planned_jobs()
    platform_state = dict((store.load().get("platforms") or {}))
    platform_caps = {
        platform: max(1, min(5, int(dict(platform_state.get(platform) or {}).get("videos_per_day") or 3)))
        for platform in PLATFORMS
        if dict(platform_state.get(platform) or {}).get("enabled")
    }
    excess_cancelled = queue.enforce_platform_daily_caps(platform_caps)
    repaired = repair_planned_job_topics(project_root)
    duration_repaired = repair_planned_job_durations(project_root)
    created = build_platform_daily_jobs(project_root)

    if created:
        queue.set_max_jobs_per_day(max(1, store.enabled_daily_cap()))
        imported = queue.import_scheduled_jobs(created)
        return {
            "date": today,
            "job_count": len(imported),
            "planned_count": len(created),
            "stale_cancelled": stale_cancelled,
            "excess_cancelled": excess_cancelled,
            "repaired_topics": repaired,
            "repaired_durations": duration_repaired,
            "daily_cap": store.enabled_daily_cap(),
            "platforms": list({platform for job in imported for platform in job.platform_targets}),
        }

    return {
        "date": today,
        "job_count": 0,
        "planned_count": 0,
        "stale_cancelled": stale_cancelled,
        "excess_cancelled": excess_cancelled,
        "repaired_topics": repaired,
        "repaired_durations": duration_repaired,
        "daily_cap": store.enabled_daily_cap(),
        "platforms": [],
    }


def get_platform_scheduler_status(project_root: str | Path) -> dict[str, Any]:
    from content_brain.automation.upload_history_store import UploadHistoryStore
    from content_brain.platform.automation_center_store import AutomationCenterStore
    from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

    store = PlatformDailySchedulerStore(project_root)
    state = store.load()
    profile = ProductChannelProfileStore(project_root).load()
    center = AutomationCenterStore(project_root).load()
    history = UploadHistoryStore(project_root).list_all()
    platforms_out: dict[str, Any] = {}
    for platform in PLATFORMS:
        entry = dict((state.get("platforms") or {}).get(platform) or {})
        entry["topic"] = display_platform_topic(platform, profile, str(entry.get("topic") or ""))
        upload_times = compute_upload_times(
            videos_per_day=int(entry.get("videos_per_day") or 3),
            interval_hours=int(entry.get("interval_hours") or 4),
            start_hour=int(entry.get("start_hour") or 8),
        )
        last_success = next((item for item in history.get(platform, []) if item.get("success")), None)
        sanitized_history: list[dict[str, Any]] = []
        for item in list(history.get(platform) or [])[:20]:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["title"] = display_platform_topic(platform, profile, str(row.get("title") or ""))
            sanitized_history.append(row)
        platforms_out[platform] = {
            **entry,
            "upload_times_preview": upload_times,
            "last_upload_success": bool(last_success),
            "upload_history": sanitized_history,
        }
    return {
        "version": state.get("version"),
        "youtube_duration_seconds": state.get("youtube_duration_seconds"),
        "instagram_duration_seconds": state.get("instagram_duration_seconds"),
        "tiktok_duration_seconds": state.get("tiktok_duration_seconds"),
        "automation_enabled": bool(center.get("enabled")),
        "automation_paused": bool(center.get("paused", True)),
        "daily_job_cap": store.enabled_daily_cap(),
        "platforms": platforms_out,
        "updated_at": state.get("updated_at") or "",
    }


__all__ = [
    "JOB_TOPIC_DISPLAY_MAX",
    "MAX_JOB_TOPIC_CHARS",
    "PLATFORM_TOPIC_PROFILE_KEYS",
    "PLATFORM_UPLOAD_ENABLED_KEYS",
    "build_platform_daily_jobs",
    "compute_upload_times",
    "display_platform_topic",
    "get_platform_scheduler_status",
    "repair_planned_job_topics",
    "resolve_platform_job_title",
    "resolve_platform_topic",
    "sync_platform_daily_jobs",
    "sync_scheduler_enabled_from_profile",
    "truncate_topic_display",
]
