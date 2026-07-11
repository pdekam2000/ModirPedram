"""Background automation scheduler — starts on API launch when automation is enabled."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

POLL_SECONDS = 30
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()


def _automation_should_run(project_root: Path) -> bool:
    from content_brain.automation.platform_daily_scheduler_store import PlatformDailySchedulerStore
    from content_brain.platform.automation_center_store import AutomationCenterStore

    center = AutomationCenterStore(project_root).load()
    if not center.get("enabled"):
        return False
    if center.get("paused", True):
        return False
    return PlatformDailySchedulerStore(project_root).any_platform_enabled()


def _tick(project_root: Path) -> None:
    from content_brain.automation.automation_job_runner import AutomationJobRunner
    from content_brain.automation.automation_queue import JOB_COMPLETED
    from content_brain.automation.platform_daily_scheduler import sync_platform_daily_jobs
    from ui.api.dependencies import get_product_studio_service, get_runway_live_smoke_service

    if not _automation_should_run(project_root):
        return

    try:
        sync_platform_daily_jobs(project_root)
    except Exception as exc:
        logger.warning("platform daily job sync failed: %s", exc)

    runner = AutomationJobRunner(project_root)
    daily_cap = runner._daily_job_cap()
    completed_today = runner.queue.completed_today_count()
    if completed_today >= daily_cap:
        cancelled = runner.queue.cancel_remaining_planned_jobs_for_today()
        if cancelled:
            logger.info("Cancelled %s remaining planned job(s) — daily cap reached.", cancelled)
        logger.info(
            "Daily cap reached: %s/%s videos completed. Next run tomorrow.",
            completed_today,
            daily_cap,
        )
        return

    due_jobs = runner.queue.due_planned_jobs()
    if not due_jobs:
        return

    recovered = runner.queue.recover_stale_running_jobs()
    if recovered:
        logger.warning("Recovered stale running job(s): %s", ", ".join(recovered))
    deduped = runner.queue.dedupe_planned_jobs()
    if deduped:
        logger.info("Cancelled %s duplicate planned job(s)", deduped)
    try:
        from content_brain.automation.platform_daily_scheduler_store import PLATFORMS, PlatformDailySchedulerStore

        scheduler = PlatformDailySchedulerStore(project_root)
        platform_state = dict((scheduler.load().get("platforms") or {}))
        platform_caps = {
            platform: max(1, min(5, int(dict(platform_state.get(platform) or {}).get("videos_per_day") or 3)))
            for platform in PLATFORMS
            if dict(platform_state.get(platform) or {}).get("enabled")
        }
        excess = runner.queue.enforce_platform_daily_caps(platform_caps)
        if excess:
            logger.info("Cancelled %s planned job(s) — per-platform daily cap reached.", excess)
    except Exception as exc:
        logger.debug("platform cap enforcement skipped: %s", exc)

    ok, reason = runner.preflight()
    if not ok:
        if reason == "daily_job_cap_reached":
            cancelled = runner.queue.cancel_remaining_planned_jobs_for_today()
            if cancelled:
                logger.info("Cancelled %s remaining planned job(s) — daily cap reached.", cancelled)
            logger.info(
                "Daily cap reached: %s/%s videos completed. Next run tomorrow.",
                completed_today,
                daily_cap,
            )
        elif reason not in {"job_already_running"}:
            logger.debug("automation preflight skipped: %s", reason)
        return

    due_job = due_jobs[0]
    scheduled_at = due_job.scheduled_time or due_job.created_at
    logger.info("Auto-starting job: %s at %s", due_job.topic, scheduled_at)

    product_service = get_product_studio_service()
    runway_service = get_runway_live_smoke_service()
    try:
        result = runner.start_next_job(product_service=product_service, runway_service=runway_service)
        status = str(result.get("status") or "")
        logger.info("automation tick result: %s", status)
        if status == JOB_COMPLETED:
            completed_after = runner.queue.completed_today_count()
            cap_after = runner._daily_job_cap()
            if completed_after >= cap_after:
                cancelled = runner.queue.cancel_remaining_planned_jobs_for_today()
                if cancelled:
                    logger.info("Cancelled %s remaining planned job(s) — daily cap reached.", cancelled)
                logger.info(
                    "Daily cap reached: %s/%s videos completed. Next run tomorrow.",
                    completed_after,
                    cap_after,
                )
    except Exception as exc:
        logger.exception("automation start_next failed: %s", exc)


def _scheduler_loop(project_root: Path) -> None:
    while not _scheduler_stop.is_set():
        try:
            _tick(project_root)
        except Exception as exc:
            logger.exception("automation scheduler tick error: %s", exc)
        _scheduler_stop.wait(POLL_SECONDS)


def start_background_scheduler(project_root: str | Path) -> dict[str, Any]:
    global _scheduler_thread
    root = Path(project_root).resolve()
    if _scheduler_thread and _scheduler_thread.is_alive():
        return {"ok": True, "status": "already_running"}
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(root,),
        name="modir-automation-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()
    logger.info("automation background scheduler started")
    try:
        _tick(root)
    except Exception as exc:
        logger.exception("automation scheduler immediate tick error: %s", exc)
    return {"ok": True, "status": "started", "poll_seconds": POLL_SECONDS}


def stop_background_scheduler() -> dict[str, Any]:
    _scheduler_stop.set()
    return {"ok": True, "status": "stopped"}


def reset_daily_counter(project_root: str | Path, platform: str | None = None) -> dict[str, Any]:
    """Reset daily completion counters and re-queue today's completed jobs."""
    from content_brain.automation.automation_queue import AutomationQueue, normalize_platform_alias
    from content_brain.automation.platform_daily_scheduler_store import PlatformDailySchedulerStore

    root = Path(project_root).resolve()
    queue_result = AutomationQueue(root).reset_daily_counter(platform)
    completion = PlatformDailySchedulerStore(root).reset_daily_completion(platform)
    scheduler_store = PlatformDailySchedulerStore(root)
    normalized = normalize_platform_alias(platform)

    if normalized is None:
        slots = max(scheduler_store.enabled_daily_cap(), 1)
        message = f"Daily counter reset ✓ — ready to generate {slots} new videos"
    else:
        entry = dict((scheduler_store.load().get("platforms") or {}).get(normalized) or {})
        slots = max(int(entry.get("videos_per_day") or 3), 1)
        label = {
            "youtube_shorts": "YouTube",
            "instagram_reels": "Instagram",
            "tiktok": "TikTok",
        }.get(normalized, normalized.replace("_", " ").title())
        message = f"{label} counter reset ✓ — ready to generate {slots} new videos"

    return {
        "ok": True,
        "message": message,
        "jobs_reset": int(queue_result.get("jobs_reset") or 0),
        "platform": str(queue_result.get("platform") or "all"),
        "completed_today": int(queue_result.get("completed_today") or 0),
        "daily_completion": completion,
    }


# Alias for startup hooks / external callers
start = start_background_scheduler


__all__ = ["start", "start_background_scheduler", "stop_background_scheduler", "reset_daily_counter", "POLL_SECONDS"]
