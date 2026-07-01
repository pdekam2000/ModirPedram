"""Automation job queue — planned/running/completed/failed jobs."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUTOMATION_QUEUE_VERSION = "automation_queue_v1"
JOBS_PATH = Path("project_brain") / "automation" / "automation_jobs.json"

JOB_PLANNED = "planned"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_SKIPPED = "skipped"
JOB_CANCELLED = "cancelled"

TERMINAL_STATUSES = {JOB_COMPLETED, JOB_FAILED, JOB_SKIPPED, JOB_CANCELLED}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        payload.setdefault("jobs", [])
        payload.setdefault("max_jobs_per_day", 5)
        return payload

    def _save_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

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

    def next_planned_job(self) -> AutomationJob | None:
        jobs = self.list_jobs()
        planned = [job for job in jobs if job.status == JOB_PLANNED]
        planned.sort(key=lambda item: item.scheduled_time or item.created_at)
        return planned[0] if planned else None

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

    def max_jobs_per_day(self) -> int:
        return int(self._load_payload().get("max_jobs_per_day") or 5)

    def set_max_jobs_per_day(self, value: int) -> None:
        store = self._load_payload()
        store["max_jobs_per_day"] = max(1, min(20, int(value)))
        self._save_payload(store)

    def import_scheduled_jobs(self, scheduled_jobs: list[dict[str, Any]]) -> list[AutomationJob]:
        created: list[AutomationJob] = []
        existing_topics = {(job.topic, job.scheduled_time) for job in self.list_jobs()}
        for raw in scheduled_jobs:
            topic = str(raw.get("topic") or "").strip()
            if not topic:
                continue
            scheduled_time = f"{raw.get('planned_date') or ''}T{raw.get('planned_time') or ''}".strip("T")
            key = (topic, scheduled_time)
            if key in existing_topics:
                continue
            job = self.create_job(
                {
                    "topic": topic,
                    "title": str(raw.get("title") or topic),
                    "duration": int(raw.get("duration_seconds") or 30),
                    "clip_count": int(raw.get("clip_count") or 3),
                    "platform_targets": list(raw.get("platform_targets") or raw.get("platforms") or ["youtube_shorts"]),
                    "scheduled_time": scheduled_time,
                    "status": JOB_PLANNED,
                }
            )
            created.append(job)
            existing_topics.add(key)
        return created


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
]
