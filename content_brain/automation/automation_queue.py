"""Automation job queue — planned/running/completed/failed jobs."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.json_utf8 import dumps_json, repair_mojibake_text

AUTOMATION_QUEUE_VERSION = "automation_queue_v1"
JOBS_PATH = Path("project_brain") / "automation" / "automation_jobs.json"

JOB_PLANNED = "planned"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_SKIPPED = "skipped"
JOB_CANCELLED = "cancelled"

TERMINAL_STATUSES = {JOB_COMPLETED, JOB_FAILED, JOB_SKIPPED, JOB_CANCELLED}

PLATFORM_ALIASES = {
    "youtube": "youtube_shorts",
    "youtube_shorts": "youtube_shorts",
    "instagram": "instagram_reels",
    "instagram_reels": "instagram_reels",
    "tiktok": "tiktok",
}


def normalize_platform_alias(platform: str | None) -> str | None:
    if platform is None:
        return None
    key = str(platform or "").strip().lower()
    if not key:
        return None
    return PLATFORM_ALIASES.get(key, key)


def _is_today(stamp: str) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    return str(stamp or "")[:10] == today


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_timestamp(raw: str) -> datetime | None:
    stamp = str(raw or "").strip()
    if not stamp:
        return None
    try:
        if stamp.endswith("Z"):
            stamp = stamp[:-1] + "+00:00"
        dt = datetime.fromisoformat(stamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


STALE_RUNNING_MINUTES = 20


@dataclass
class AutomationJob:
    job_id: str = ""
    topic: str = ""
    title: str = ""
    duration: int = 30
    clip_count: int = 3
    platform_targets: list[str] = field(default_factory=lambda: ["youtube_shorts"])
    status: str = JOB_PLANNED
    scheduled_time: str = ""
    run_id: str = ""
    output_path: str = ""
    publish_package_path: str = ""
    upload_package_path: str = ""
    upload_result: dict[str, Any] | None = None
    error: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = f"auto_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "topic": self.topic,
            "title": self.title,
            "duration": int(self.duration),
            "clip_count": int(self.clip_count),
            "platform_targets": list(self.platform_targets),
            "status": self.status,
            "scheduled_time": self.scheduled_time,
            "run_id": self.run_id,
            "output_path": self.output_path,
            "publish_package_path": self.publish_package_path,
            "upload_package_path": self.upload_package_path,
            "upload_result": self.upload_result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AutomationJob:
        return cls(
            job_id=str(payload.get("job_id") or ""),
            topic=str(payload.get("topic") or ""),
            title=str(payload.get("title") or ""),
            duration=int(payload.get("duration") or payload.get("duration_seconds") or 30),
            clip_count=int(payload.get("clip_count") or 3),
            platform_targets=[str(item) for item in (payload.get("platform_targets") or payload.get("platforms") or ["youtube_shorts"]) if item],
            status=str(payload.get("status") or JOB_PLANNED),
            scheduled_time=str(payload.get("scheduled_time") or ""),
            run_id=str(payload.get("run_id") or ""),
            output_path=str(payload.get("output_path") or ""),
            publish_package_path=str(payload.get("publish_package_path") or ""),
            upload_package_path=str(payload.get("upload_package_path") or ""),
            upload_result=payload.get("upload_result") if isinstance(payload.get("upload_result"), dict) else None,
            error=str(payload.get("error") or ""),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
        )


class AutomationQueue:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / JOBS_PATH

    def _load_payload(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": AUTOMATION_QUEUE_VERSION, "jobs": [], "max_jobs_per_day": 5}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": AUTOMATION_QUEUE_VERSION, "jobs": [], "max_jobs_per_day": 5}
        if not isinstance(payload, dict):
            return {"version": AUTOMATION_QUEUE_VERSION, "jobs": [], "max_jobs_per_day": 5}
        payload = repair_mojibake_text(payload)
        payload.setdefault("jobs", [])
        payload.setdefault("max_jobs_per_day", 5)
        return payload

    def _save_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dumps_json(payload), encoding="utf-8")

    def list_jobs(self) -> list[AutomationJob]:
        payload = self._load_payload()
        return [AutomationJob.from_dict(item) for item in payload.get("jobs") or [] if isinstance(item, dict)]

    def get_job(self, job_id: str) -> AutomationJob | None:
        for job in self.list_jobs():
            if job.job_id == job_id:
                return job
        return None

    def create_job(self, payload: dict[str, Any]) -> AutomationJob:
        job = AutomationJob.from_dict(payload)
        if job.status not in TERMINAL_STATUSES:
            job.status = JOB_PLANNED
        store = self._load_payload()
        jobs = [item.to_dict() for item in self.list_jobs()]
        jobs.append(job.to_dict())
        store["jobs"] = jobs[-200:]
        self._save_payload(store)
        return job

    def update_job(self, job_id: str, **fields: Any) -> AutomationJob | None:
        store = self._load_payload()
        updated: AutomationJob | None = None
        jobs: list[dict[str, Any]] = []
        for raw in store.get("jobs") or []:
            if not isinstance(raw, dict):
                continue
            if str(raw.get("job_id") or "") != job_id:
                jobs.append(raw)
                continue
            job = AutomationJob.from_dict(raw)
            for key, value in fields.items():
                if hasattr(job, key) and value is not None:
                    setattr(job, key, value)
            job.updated_at = _now()
            updated = job
            jobs.append(job.to_dict())
        if updated is None:
            return None
        store["jobs"] = jobs
        self._save_payload(store)
        return updated

    def cancel_job(self, job_id: str) -> AutomationJob | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        if job.status in {JOB_RUNNING}:
            return self.update_job(job_id, status=JOB_FAILED, error="cancelled_while_running")
        return self.update_job(job_id, status=JOB_CANCELLED, error="cancelled_by_operator")

    def cancel_jobs_by_topic_keywords(
        self,
        keywords: tuple[str, ...] = ("forest", "glowing", "mystery", "trail", "shelter", "nautilus", "fossil"),
        *,
        include_running: bool = True,
    ) -> list[str]:
        """Cancel or fail jobs whose topic/title matches stale story keywords."""
        cancelled: list[str] = []
        needles = tuple(k.lower() for k in keywords if str(k).strip())
        for job in self.list_jobs():
            if job.status in TERMINAL_STATUSES:
                continue
            if job.status == JOB_RUNNING and not include_running:
                continue
            haystack = f"{job.topic} {job.title}".lower()
            if not any(needle in haystack for needle in needles):
                continue
            if job.status == JOB_RUNNING:
                self.update_job(job.job_id, status=JOB_FAILED, error="cancelled_stale_topic")
            else:
                self.update_job(job.job_id, status=JOB_CANCELLED, error="cancelled_stale_topic")
            cancelled.append(job.job_id)
        return cancelled

    def cancel_all_running_jobs(self, *, reason: str = "cancelled_by_operator") -> list[str]:
        stopped: list[str] = []
        for job in self.list_jobs():
            if job.status != JOB_RUNNING:
                continue
            self.update_job(job.job_id, status=JOB_FAILED, error=reason)
            stopped.append(job.job_id)
        return stopped

    def running_job(self) -> AutomationJob | None:
        for job in self.list_jobs():
            if job.status == JOB_RUNNING:
                return job
        return None

    def completed_today_count(self) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        count = 0
        for job in self.list_jobs():
            if job.status != JOB_COMPLETED:
                continue
            stamp = (job.updated_at or job.created_at or "")[:10]
            if stamp == today:
                count += 1
        return count

    def _job_scheduled_date(self, job: AutomationJob) -> str:
        return (job.scheduled_time or job.created_at or "")[:10]

    def active_jobs_today_for_platform(self, platform: str) -> int:
        """Count today's platform slots used (completed + planned + running).

        Failed jobs do not permanently burn daily slots — after a bug fix, new
        planned jobs must still be creatable the same day.
        """
        today = datetime.now(timezone.utc).date().isoformat()
        count = 0
        for job in self.list_jobs():
            if job.status not in {JOB_PLANNED, JOB_RUNNING, JOB_COMPLETED}:
                continue
            plat = str((job.platform_targets[0] if job.platform_targets else "") or "")
            if plat != platform:
                continue
            if self._job_scheduled_date(job) == today:
                count += 1
        return count

    def cancel_remaining_planned_jobs_for_today(self, *, reason: str = "daily_cap_reached") -> int:
        """Cancel all planned jobs scheduled for today once the daily cap is reached."""
        today = datetime.now(timezone.utc).date().isoformat()
        cancelled = 0
        for job in self.list_jobs():
            if job.status != JOB_PLANNED:
                continue
            if self._job_scheduled_date(job) != today:
                continue
            self.update_job(job.job_id, status=JOB_CANCELLED, error=reason)
            cancelled += 1
        return cancelled

    def cancel_stale_planned_jobs(self, *, reason: str = "stale_planned_from_prior_day") -> int:
        """Cancel planned jobs scheduled before today so they cannot replay after midnight."""
        today = datetime.now(timezone.utc).date().isoformat()
        cancelled = 0
        for job in self.list_jobs():
            if job.status != JOB_PLANNED:
                continue
            scheduled = self._job_scheduled_date(job)
            if scheduled and scheduled < today:
                self.update_job(job.job_id, status=JOB_CANCELLED, error=reason)
                cancelled += 1
        return cancelled

    def cancel_excess_planned_jobs_for_platform(self, platform: str, *, daily_cap: int, reason: str) -> int:
        """Cancel planned jobs when a platform already used its daily slots (incl. failures)."""
        if daily_cap <= 0:
            return 0
        if self.active_jobs_today_for_platform(platform) < daily_cap:
            return 0
        today = datetime.now(timezone.utc).date().isoformat()
        cancelled = 0
        for job in self.list_jobs():
            if job.status != JOB_PLANNED:
                continue
            plat = str((job.platform_targets[0] if job.platform_targets else "") or "")
            if plat != platform:
                continue
            if self._job_scheduled_date(job) != today:
                continue
            self.update_job(job.job_id, status=JOB_CANCELLED, error=reason)
            cancelled += 1
        return cancelled

    def enforce_platform_daily_caps(self, platform_caps: dict[str, int]) -> int:
        """Cancel planned jobs for platforms that already hit videos_per_day."""
        total = 0
        for platform, cap in platform_caps.items():
            if cap <= 0:
                continue
            total += self.cancel_excess_planned_jobs_for_platform(
                platform,
                daily_cap=int(cap),
                reason="platform_daily_cap_reached",
            )
        return total

    def max_jobs_per_day(self) -> int:
        return int(self._load_payload().get("max_jobs_per_day") or 5)

    def set_max_jobs_per_day(self, value: int) -> None:
        store = self._load_payload()
        store["max_jobs_per_day"] = max(1, min(20, int(value)))
        self._save_payload(store)

    def import_scheduled_jobs(self, scheduled_jobs: list[dict[str, Any]]) -> list[AutomationJob]:
        from content_brain.automation.platform_daily_scheduler_store import (
            PLATFORMS,
            PlatformDailySchedulerStore,
            resolve_platform_duration_seconds,
        )

        scheduler = PlatformDailySchedulerStore(self.project_root)
        platform_state = dict((scheduler.load().get("platforms") or {}))
        platform_caps: dict[str, int] = {}
        for platform in PLATFORMS:
            entry = dict(platform_state.get(platform) or {})
            if entry.get("enabled"):
                platform_caps[platform] = max(1, min(5, int(entry.get("videos_per_day") or 3)))
            else:
                platform_caps[platform] = 0

        created: list[AutomationJob] = []
        existing_keys = set()
        for job in self.list_jobs():
            if job.status not in {JOB_PLANNED, JOB_RUNNING}:
                continue
            platform = (job.platform_targets[0] if job.platform_targets else "")
            existing_keys.add((platform, job.scheduled_time, job.topic))
        for raw in scheduled_jobs:
            topic = str(raw.get("topic") or "").strip()
            if not topic:
                continue
            platform = str((raw.get("platform_targets") or raw.get("platforms") or ["youtube_shorts"])[0] or "")
            scheduled_duration = int(
                raw.get("duration_seconds")
                or resolve_platform_duration_seconds(self.project_root, platform)
            )
            daily_cap = int(platform_caps.get(platform) or 0)
            if daily_cap <= 0:
                continue
            if self.active_jobs_today_for_platform(platform) >= daily_cap:
                continue
            scheduled_time = f"{raw.get('planned_date') or ''}T{raw.get('planned_time') or ''}".strip("T")
            key = (platform, scheduled_time, topic)
            if key in existing_keys:
                for existing in self.list_jobs():
                    if existing.status != JOB_PLANNED:
                        continue
                    existing_platform = str((existing.platform_targets[0] if existing.platform_targets else "") or "")
                    if (
                        existing_platform == platform
                        and existing.scheduled_time == scheduled_time
                        and existing.topic == topic
                    ):
                        self.update_job(
                            existing.job_id,
                            duration=scheduled_duration,
                            clip_count=int(raw.get("clip_count") or 2),
                        )
                continue
            job = self.create_job(
                {
                    "topic": topic,
                    "title": str(raw.get("title") or topic),
                    "duration": scheduled_duration,
                    "clip_count": int(raw.get("clip_count") or 3),
                    "platform_targets": list(raw.get("platform_targets") or raw.get("platforms") or ["youtube_shorts"]),
                    "scheduled_time": scheduled_time,
                    "status": JOB_PLANNED,
                }
            )
            created.append(job)
            existing_keys.add(key)

        for raw in scheduled_jobs:
            topic = str(raw.get("topic") or "").strip()
            if not topic:
                continue
            platform = str((raw.get("platform_targets") or raw.get("platforms") or ["youtube_shorts"])[0] or "")
            scheduled_duration = int(
                raw.get("duration_seconds")
                or resolve_platform_duration_seconds(self.project_root, platform)
            )
            scheduled_time = f"{raw.get('planned_date') or ''}T{raw.get('planned_time') or ''}".strip("T")
            for existing in self.list_jobs():
                if existing.status != JOB_PLANNED:
                    continue
                existing_platform = str((existing.platform_targets[0] if existing.platform_targets else "") or "")
                if existing_platform != platform or existing.scheduled_time != scheduled_time:
                    continue
                if existing.topic != topic or existing.clip_count != int(raw.get("clip_count") or 2):
                    self.update_job(
                        existing.job_id,
                        topic=topic,
                        title=topic,
                        duration=scheduled_duration,
                        clip_count=int(raw.get("clip_count") or 2),
                    )
        return created

    def _parse_scheduled_time(self, raw: str) -> datetime | None:
        stamp = str(raw or "").strip()
        if not stamp:
            return None
        try:
            if stamp.endswith("Z"):
                return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if "T" in stamp:
                parsed = datetime.fromisoformat(stamp)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
                return parsed
        except ValueError:
            return None
        return None

    def _job_is_due(self, job: AutomationJob) -> bool:
        due_at = self._parse_scheduled_time(job.scheduled_time)
        if due_at is None:
            return True
        now = datetime.now(due_at.tzinfo) if due_at.tzinfo else datetime.now()
        return now >= due_at

    def next_planned_job(self, *, due_only: bool = True) -> AutomationJob | None:
        jobs = self.list_jobs()
        planned = [job for job in jobs if job.status == JOB_PLANNED]
        if due_only:
            planned = [job for job in planned if self._job_is_due(job)]
        planned.sort(key=lambda item: item.scheduled_time or item.created_at)
        return planned[0] if planned else None

    def due_planned_jobs(self) -> list[AutomationJob]:
        jobs = self.list_jobs()
        planned = [job for job in jobs if job.status == JOB_PLANNED and self._job_is_due(job)]
        planned.sort(key=lambda item: item.scheduled_time or item.created_at)
        return planned

    def reset_failed_jobs_to_planned(self) -> int:
        store = self._load_payload()
        reset_count = 0
        jobs: list[dict[str, Any]] = []
        for raw in store.get("jobs") or []:
            if not isinstance(raw, dict):
                continue
            if str(raw.get("status") or "") == JOB_FAILED:
                job = AutomationJob.from_dict(raw)
                job.status = JOB_PLANNED
                job.error = ""
                job.run_id = ""
                job.output_path = ""
                job.publish_package_path = ""
                job.upload_package_path = ""
                job.updated_at = _now()
                jobs.append(job.to_dict())
                reset_count += 1
            else:
                jobs.append(raw)
        store["jobs"] = jobs
        self._save_payload(store)
        return reset_count

    def recover_stale_running_jobs(self, *, max_age_minutes: int = STALE_RUNNING_MINUTES) -> list[str]:
        """Mark stuck running jobs as failed when they never acquired a run_id."""
        recovered: list[str] = []
        now = datetime.now(timezone.utc)
        for job in self.list_jobs():
            if job.status != JOB_RUNNING:
                continue
            if str(job.run_id or "").strip():
                continue
            anchor = _parse_iso_timestamp(job.updated_at) or _parse_iso_timestamp(job.created_at)
            if anchor is None:
                age_minutes = float(max_age_minutes) + 1.0
            else:
                age_minutes = (now - anchor).total_seconds() / 60.0
            if age_minutes < max_age_minutes:
                continue
            self.update_job(
                job.job_id,
                status=JOB_FAILED,
                error="stale_running_recovered",
                run_id="",
            )
            recovered.append(job.job_id)
        return recovered

    def dedupe_planned_jobs(self) -> int:
        """Cancel duplicate planned jobs that share platform, schedule, and topic."""
        store = self._load_payload()
        jobs = list(store.get("jobs") or [])
        seen: set[tuple[str, str, str]] = set()
        cancelled = 0
        for job in jobs:
            if not isinstance(job, dict):
                continue
            if str(job.get("status") or "") != JOB_PLANNED:
                continue
            platform = normalize_platform_alias(job.get("platform")) or ""
            if not platform and isinstance(job.get("platform_targets"), list):
                platform = normalize_platform_alias(str(job["platform_targets"][0] if job["platform_targets"] else "")) or ""
            scheduled = str(job.get("scheduled_time") or "")
            topic = str(job.get("topic") or "").strip().lower()
            key = (platform, scheduled, topic)
            if key in seen:
                job["status"] = JOB_CANCELLED
                job["updated_at"] = _now()
                job["error"] = "duplicate_planned_removed"
                cancelled += 1
            else:
                seen.add(key)
        if cancelled:
            store["jobs"] = jobs
            self._save_payload(store)
        return cancelled

    def reset_daily_counter(self, platform: str | None = None) -> dict[str, Any]:
        """Reset today's completed jobs back to planned; optional single-platform filter."""
        normalized = normalize_platform_alias(platform)
        store = self._load_payload()
        reset_count = 0
        jobs: list[dict[str, Any]] = []
        for raw in store.get("jobs") or []:
            if not isinstance(raw, dict):
                continue
            job = AutomationJob.from_dict(raw)
            primary = normalize_platform_alias(
                str((job.platform_targets[0] if job.platform_targets else "") or "")
            )
            should_reset = (
                job.status == JOB_COMPLETED
                and _is_today(job.updated_at or job.created_at)
                and (normalized is None or primary == normalized)
            )
            if should_reset:
                job.status = JOB_PLANNED
                job.error = ""
                job.run_id = ""
                job.output_path = ""
                job.publish_package_path = ""
                job.upload_package_path = ""
                job.updated_at = _now()
                reset_count += 1
            jobs.append(job.to_dict())
        store["jobs"] = jobs
        self._save_payload(store)
        return {
            "jobs_reset": reset_count,
            "platform": normalized or "all",
            "completed_today": self.completed_today_count(),
        }


def reset_daily_counter(project_root: str | Path, platform: str | None = None) -> dict[str, Any]:
    return AutomationQueue(project_root).reset_daily_counter(platform)


__all__ = [
    "AUTOMATION_QUEUE_VERSION",
    "AutomationJob",
    "AutomationQueue",
    "JOB_CANCELLED",
    "JOB_COMPLETED",
    "JOB_FAILED",
    "JOB_PLANNED",
    "JOB_RUNNING",
    "JOB_SKIPPED",
    "normalize_platform_alias",
    "reset_daily_counter",
]
