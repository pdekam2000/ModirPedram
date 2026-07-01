"""Scheduling — JSON persistence for plans and jobs."""

from __future__ import annotations

import json
from pathlib import Path

from content_brain.scheduling.schedule_models import ScheduledVideoJob, VideoSchedulePlan


class ScheduleStore:
    def __init__(self, project_root: str | Path = ".") -> None:
        root = Path(project_root).resolve()
        self.base = root / "storage" / "content_brain" / "schedules"
        self.plans_dir = self.base / "plans"
        self.jobs_dir = self.base / "jobs"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def save_plan(self, plan: VideoSchedulePlan) -> Path:
        path = self.plans_dir / f"{plan.schedule_id}.json"
        path.write_text(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_plan(self, schedule_id: str) -> VideoSchedulePlan:
        path = self.plans_dir / f"{schedule_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return VideoSchedulePlan.from_dict(payload)

    def list_plans(self) -> list[VideoSchedulePlan]:
        plans: list[VideoSchedulePlan] = []
        for path in sorted(self.plans_dir.glob("*.json")):
            plans.append(VideoSchedulePlan.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return plans

    def save_jobs(self, schedule_id: str, jobs: list[ScheduledVideoJob]) -> Path:
        path = self.jobs_dir / f"{schedule_id}_jobs.json"
        payload = [job.to_dict() for job in jobs]
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_jobs(self, schedule_id: str) -> list[ScheduledVideoJob]:
        path = self.jobs_dir / f"{schedule_id}_jobs.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [ScheduledVideoJob.from_dict(item) for item in payload]
