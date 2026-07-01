"""Scheduling — data models for video plans and planned jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

SCHEDULE_MODES = ("daily", "weekly", "monthly", "custom")
TOPIC_SOURCES = ("channel", "custom", "topic_list")
JOB_STATUSES = ("planned", "ready", "generated", "published", "failed", "skipped")
PLATFORMS = ("tiktok", "instagram_reels", "youtube_shorts")


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class VideoSchedulePlan:
    schedule_id: str = ""
    title: str = ""
    mode: str = "daily"
    videos_per_day: int = 1
    duration_seconds: int = 30
    clip_count: int = 3
    topic_source: str = "channel"
    custom_topic: str = ""
    topic_list: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=lambda: ["tiktok"])
    provider: str = "runway"
    start_date: str = ""
    end_date: str = ""
    run_time: str = "09:00"
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.schedule_id:
            self.schedule_id = f"sched_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "title": self.title,
            "mode": self.mode,
            "videos_per_day": self.videos_per_day,
            "duration_seconds": self.duration_seconds,
            "clip_count": self.clip_count,
            "topic_source": self.topic_source,
            "custom_topic": self.custom_topic,
            "topic_list": list(self.topic_list),
            "platforms": list(self.platforms),
            "provider": self.provider,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "run_time": self.run_time,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VideoSchedulePlan:
        return cls(
            schedule_id=str(payload.get("schedule_id") or ""),
            title=str(payload.get("title") or ""),
            mode=str(payload.get("mode") or "daily"),
            videos_per_day=int(payload.get("videos_per_day") or 1),
            duration_seconds=int(payload.get("duration_seconds") or 30),
            clip_count=int(payload.get("clip_count") or 1),
            topic_source=str(payload.get("topic_source") or "channel"),
            custom_topic=str(payload.get("custom_topic") or ""),
            topic_list=[str(x) for x in (payload.get("topic_list") or [])],
            platforms=[str(x) for x in (payload.get("platforms") or ["tiktok"])],
            provider=str(payload.get("provider") or "runway"),
            start_date=str(payload.get("start_date") or ""),
            end_date=str(payload.get("end_date") or ""),
            run_time=str(payload.get("run_time") or "09:00"),
            enabled=bool(payload.get("enabled", True)),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
        )


@dataclass
class ScheduledVideoJob:
    job_id: str = ""
    schedule_id: str = ""
    planned_date: str = ""
    planned_time: str = ""
    topic: str = ""
    duration_seconds: int = 30
    clip_count: int = 1
    platform_targets: list[str] = field(default_factory=list)
    status: str = "planned"
    output_package_path: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = f"job_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "schedule_id": self.schedule_id,
            "planned_date": self.planned_date,
            "planned_time": self.planned_time,
            "topic": self.topic,
            "duration_seconds": self.duration_seconds,
            "clip_count": self.clip_count,
            "platform_targets": list(self.platform_targets),
            "status": self.status,
            "output_package_path": self.output_package_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ScheduledVideoJob:
        return cls(
            job_id=str(payload.get("job_id") or ""),
            schedule_id=str(payload.get("schedule_id") or ""),
            planned_date=str(payload.get("planned_date") or ""),
            planned_time=str(payload.get("planned_time") or ""),
            topic=str(payload.get("topic") or ""),
            duration_seconds=int(payload.get("duration_seconds") or 30),
            clip_count=int(payload.get("clip_count") or 1),
            platform_targets=[str(x) for x in (payload.get("platform_targets") or [])],
            status=str(payload.get("status") or "planned"),
            output_package_path=str(payload.get("output_package_path") or ""),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
        )
