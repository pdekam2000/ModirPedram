"""Scheduling — planner engine (planning only, no generation execution)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from content_brain.scheduling.duration_planner import plan_duration, validate_duration_seconds
from content_brain.scheduling.schedule_models import PLATFORMS, ScheduledVideoJob, TOPIC_SOURCES, VideoSchedulePlan


class SchedulePlannerError(ValueError):
    pass


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _weekday_dates(start: date, end: date, weekdays: set[int] | None = None) -> list[date]:
    allowed = weekdays or {0, 1, 2, 3, 4}
    return [d for d in _date_range(start, end) if d.weekday() in allowed]


def validate_schedule_plan(plan: VideoSchedulePlan) -> list[str]:
    errors: list[str] = []
    if not plan.title.strip():
        errors.append("title is required")
    if plan.mode not in {"daily", "weekly", "monthly", "custom"}:
        errors.append(f"invalid mode: {plan.mode}")
    if plan.videos_per_day < 1:
        errors.append("videos_per_day must be >= 1")
    ok, duration_msgs = validate_duration_seconds(plan.duration_seconds)
    if not ok:
        errors.extend(duration_msgs)
    if plan.topic_source not in TOPIC_SOURCES:
        errors.append(f"invalid topic_source: {plan.topic_source}")
    if plan.topic_source == "custom" and not plan.custom_topic.strip():
        errors.append("custom_topic required when topic_source is custom")
    if plan.topic_source == "topic_list" and not plan.topic_list:
        errors.append("topic_list required when topic_source is topic_list")
    if not plan.platforms:
        errors.append("at least one platform is required")
    for platform in plan.platforms:
        if platform not in PLATFORMS:
            errors.append(f"unsupported platform: {platform}")
    if not plan.start_date or not plan.end_date:
        errors.append("start_date and end_date are required")
    else:
        try:
            if _parse_date(plan.start_date) > _parse_date(plan.end_date):
                errors.append("start_date must be before end_date")
        except ValueError:
            errors.append("dates must be YYYY-MM-DD")
    return errors


def resolve_topic_for_job(
    *,
    plan: VideoSchedulePlan,
    channel_niche: str = "",
    channel_topic: str = "",
    job_index: int = 0,
    planned_date: str = "",
) -> str:
    if plan.topic_source == "custom":
        return plan.custom_topic.strip()
    if plan.topic_source == "topic_list":
        topics = [t.strip() for t in plan.topic_list if t.strip()]
        if not topics:
            return channel_topic or channel_niche
        return topics[job_index % len(topics)]
    base = channel_topic.strip() or channel_niche.strip() or "channel topic"
    if plan.mode == "monthly":
        return f"{base} — day {planned_date}"
    return base


def generate_jobs_for_plan(
    plan: VideoSchedulePlan,
    *,
    channel_niche: str = "",
    channel_topic: str = "",
    only_date: str | None = None,
) -> list[ScheduledVideoJob]:
    errors = validate_schedule_plan(plan)
    if errors:
        raise SchedulePlannerError("; ".join(errors))

    duration_plan = plan_duration(duration_seconds=plan.duration_seconds, provider=plan.provider)
    plan.clip_count = duration_plan.clip_count

    start = _parse_date(plan.start_date)
    end = _parse_date(plan.end_date)
    if plan.mode == "weekly":
        dates = _weekday_dates(start, end)
    elif plan.mode == "monthly":
        dates = _date_range(start, end)
    else:
        dates = _date_range(start, end)

    if only_date:
        target = _parse_date(only_date)
        dates = [d for d in dates if d == target]

    jobs: list[ScheduledVideoJob] = []
    job_index = 0
    for planned in dates:
        for slot in range(plan.videos_per_day):
            topic = resolve_topic_for_job(
                plan=plan,
                channel_niche=channel_niche,
                channel_topic=channel_topic,
                job_index=job_index,
                planned_date=planned.isoformat(),
            )
            jobs.append(
                ScheduledVideoJob(
                    schedule_id=plan.schedule_id,
                    planned_date=planned.isoformat(),
                    planned_time=plan.run_time,
                    topic=topic,
                    duration_seconds=plan.duration_seconds,
                    clip_count=duration_plan.clip_count,
                    platform_targets=list(plan.platforms),
                    status="planned",
                )
            )
            job_index += 1
    return jobs


def preview_schedule(plan: VideoSchedulePlan, **kwargs: Any) -> dict[str, Any]:
    jobs = generate_jobs_for_plan(plan, **kwargs)
    return {
        "plan": plan.to_dict(),
        "job_count": len(jobs),
        "jobs_preview": [job.to_dict() for job in jobs[:20]],
        "truncated": len(jobs) > 20,
    }
