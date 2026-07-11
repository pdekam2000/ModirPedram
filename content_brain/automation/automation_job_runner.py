"""Automation job runner — one job at a time with safety caps."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from content_brain.automation.automation_queue import (
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_RUNNING,
    JOB_SKIPPED,
    AutomationJob,
    AutomationQueue,
)
from content_brain.platform.automation_center_store import AutomationCenterStore, is_auto_upload_enabled
from content_brain.platform.browser_health_monitor import get_browser_health
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.upload_manager import UploadManager

RUNNER_VERSION = "automation_job_runner_v1"
POLL_INTERVAL_SECONDS = 5
MAX_WAIT_SECONDS = 7200
logger = logging.getLogger(__name__)


def _upload_debug(step: str, result: Any) -> None:
    summary = result
    if isinstance(result, dict):
        summary = {
            key: result.get(key)
            for key in (
                "ok",
                "uploaded",
                "status",
                "reason",
                "error",
                "skipped",
                "video_path",
                "video_id",
                "video_url",
                "post_url",
                "platforms",
                "connect_required",
            )
            if key in result
        }
    message = f"[UPLOAD DEBUG] step: {step} result: {summary}"
    print(message, flush=True)
    logger.info(message)

from content_brain.automation.platform_upload_guard import (
    guard_upload_or_block,
    normalize_platform,
    resolve_job_upload_targets,
    upload_platform_allowed,
    validate_topic_for_platform,
)

AUTOMATION_PLATFORM_TOPIC_KEYS: dict[str, str] = {
    "youtube_shorts": "youtube_channel_topic",
    "instagram_reels": "instagram_channel_topic",
    "tiktok": "tiktok_channel_topic",
}


def _enforce_job_upload_targets(job: AutomationJob, platform: str) -> tuple[list[str], str]:
    """Return upload targets that match the job platform only — never cross-upload."""
    job_platform = normalize_platform(
        platform or (job.platform_targets[0] if job.platform_targets else "")
    )
    if not job_platform:
        return [], "job_platform_missing"
    targets = resolve_job_upload_targets(job.platform_targets)
    allowed = [
        target
        for target in targets
        if upload_platform_allowed(job_platform=job_platform, upload_platform=target)
    ]
    if targets and not allowed:
        reason = f"cross_platform_upload_blocked:{job_platform}->{','.join(targets)}"
        logger.error("Upload blocked for job %s: %s", job.job_id, reason)
        return [], reason
    if len(allowed) != len(targets):
        logger.error(
            "Stripped mismatched upload targets for job %s platform=%s was=%s now=%s",
            job.job_id,
            job_platform,
            targets,
            allowed,
        )
    return allowed, ""


def _validate_platform_topic_text(platform: str, text: str) -> tuple[bool, str]:
    ok, reason = validate_topic_for_platform(platform, text, source="channel_brief")
    return ok, reason


def _resolve_automation_channel_topic(profile: dict[str, Any], platform: str) -> str:
    """Automation jobs must use ONLY the platform-specific profile topic field."""
    if platform == "instagram_reels":
        brief = str(profile.get("instagram_channel_brief") or "").strip()
        if brief:
            return brief
    key = AUTOMATION_PLATFORM_TOPIC_KEYS.get(platform, "channel_topic")
    topic = str(profile.get(key) or "").strip()
    if not topic and platform == "youtube_shorts":
        topic = str(profile.get("channel_topic") or "").strip()
    return topic


class AutomationJobRunner:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.queue = AutomationQueue(self.project_root)
        self.center = AutomationCenterStore(self.project_root)
        self.upload_manager = UploadManager(self.project_root)

    def _daily_job_cap(self) -> int:
        from content_brain.automation.platform_daily_scheduler_store import PlatformDailySchedulerStore

        store_cap = PlatformDailySchedulerStore(self.project_root).enabled_daily_cap()
        if store_cap > 0:
            return store_cap
        return self.queue.max_jobs_per_day()

    def get_status(self) -> dict[str, Any]:
        center = self.center.load()
        running = self.queue.running_job()
        next_job = self.queue.next_planned_job(due_only=False)
        jobs = self.queue.list_jobs()
        daily_cap = self._daily_job_cap()
        next_queued = self.queue.next_planned_job(due_only=False)
        next_due = self.queue.next_planned_job(due_only=True)
        return {
            "version": RUNNER_VERSION,
            "enabled": bool(center.get("enabled")),
            "paused": bool(center.get("paused", True)),
            "feature_flags": dict(center.get("feature_flags") or {}),
            "running_job": running.to_dict() if running else None,
            "next_job": next_queued.to_dict() if next_queued else None,
            "next_due_job": next_due.to_dict() if next_due else None,
            "has_due_jobs": next_due is not None,
            "queued_count": len([job for job in jobs if job.status == "planned"]),
            "completed_count": len([job for job in jobs if job.status == JOB_COMPLETED]),
            "failed_count": len([job for job in jobs if job.status == JOB_FAILED]),
            "completed_today": self.queue.completed_today_count(),
            "max_jobs_per_day": daily_cap,
            "updated_at": center.get("updated_at") or "",
        }

    def pause(self) -> dict[str, Any]:
        return self.center.save({"paused": True})

    def resume(self) -> dict[str, Any]:
        return self.center.save({"paused": False, "enabled": True})

    def preflight(self) -> tuple[bool, str]:
        center = self.center.load()
        if not center.get("enabled"):
            return False, "automation_disabled"
        if center.get("paused", True):
            return False, "automation_paused"

        self.queue.recover_stale_running_jobs()

        if self.queue.running_job() is not None:
            return False, "job_already_running"
        if self.queue.completed_today_count() >= self._daily_job_cap():
            cancelled = self.queue.cancel_remaining_planned_jobs_for_today()
            if cancelled:
                logger.info("Cancelled %s remaining planned job(s) — daily cap reached.", cancelled)
            return False, "daily_job_cap_reached"

        health = get_browser_health(self.project_root)
        if not health.get("connected"):
            return False, "browser_disconnected"

        from core.env_bootstrap import bootstrap_project_env

        bootstrap_project_env(project_root=self.project_root)
        if not os.getenv("OPENAI_API_KEY", "").strip():
            return False, "openai_api_key_missing"

        runway_key = os.getenv("RUNWAY_API_KEY", "").strip()
        if not runway_key:
            # Browser-based Runway may run without API key; warn only in metadata.
            pass

        return True, "ready"

    def start_automation(
        self,
        *,
        product_service: Any,
        runway_service: Any,
        wait_for_runway: bool = True,
        poll_interval_seconds: int = POLL_INTERVAL_SECONDS,
        max_wait_seconds: int = MAX_WAIT_SECONDS,
    ) -> dict[str, Any]:
        """Enable automation, reset failed jobs, and immediately start the next due job."""
        self.center.save({"enabled": True, "paused": False})
        reset_count = self.queue.reset_failed_jobs_to_planned()
        start_result = self.start_next_job(
            product_service=product_service,
            runway_service=runway_service,
            wait_for_runway=wait_for_runway,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
            force=True,
        )
        start_result["reset_failed_count"] = reset_count
        start_result["automation_enabled"] = True
        return start_result

    def start_next_job(
        self,
        *,
        product_service: Any,
        runway_service: Any,
        wait_for_runway: bool = True,
        poll_interval_seconds: int = POLL_INTERVAL_SECONDS,
        max_wait_seconds: int = MAX_WAIT_SECONDS,
        force: bool = False,
    ) -> dict[str, Any]:
        ok, reason = self.preflight()
        if not ok:
            return {"ok": False, "status": JOB_SKIPPED, "reason": reason, "runner": self.get_status()}

        job = self.queue.next_planned_job(due_only=not force)
        if job is None:
            scheduled = self._load_scheduled_jobs()
            if scheduled:
                self.queue.import_scheduled_jobs(scheduled)
                job = self.queue.next_planned_job(due_only=not force)
        if job is None:
            return {"ok": False, "status": "no_jobs", "reason": "no_planned_jobs", "runner": self.get_status()}

        logger.info("Job starting with topic: %s", job.topic)
        self.queue.update_job(job.job_id, status=JOB_RUNNING, error="")
        try:
            result = self._execute_job(
                job,
                product_service=product_service,
                runway_service=runway_service,
                wait_for_runway=wait_for_runway,
                poll_interval_seconds=poll_interval_seconds,
                max_wait_seconds=max_wait_seconds,
            )
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        return self._finalize_job(job.job_id, result)

    def _execute_job(
        self,
        job: AutomationJob,
        *,
        product_service: Any,
        runway_service: Any,
        wait_for_runway: bool,
        poll_interval_seconds: int,
        max_wait_seconds: int,
    ) -> dict[str, Any]:
        profile = ProductChannelProfileStore(self.project_root).load()
        from content_brain.execution.product_multiclip_execution_plan import plan_product_duration

        platform = str(
            (job.platform_targets[0] if job.platform_targets else "")
            or profile.get("default_platform")
            or "youtube_shorts"
        )
        channel_topic = _resolve_automation_channel_topic(profile, platform)
        if not channel_topic:
            return {
                "ok": False,
                "error": f"missing_platform_topic:{platform}",
                "stage": "topic_resolution",
            }
        topic_ok, topic_reason = _validate_platform_topic_text(platform, channel_topic)
        if not topic_ok:
            logger.error(
                "Automation topic contamination for platform=%s reason=%s topic=%s",
                platform,
                topic_reason,
                channel_topic[:120],
            )
            return {
                "ok": False,
                "error": topic_reason,
                "stage": "topic_validation",
            }
        from content_brain.automation.platform_daily_scheduler_store import resolve_platform_duration_seconds

        duration_seconds = resolve_platform_duration_seconds(
            self.project_root,
            platform,
            profile=profile,
        )
        if job.duration and int(job.duration) != duration_seconds:
            logger.info(
                "Automation duration resolved platform=%s job_duration=%s scheduler_duration=%s",
                platform,
                job.duration,
                duration_seconds,
            )
            self.queue.update_job(job.job_id, duration=duration_seconds)
        product_duration = plan_product_duration(duration_seconds)
        clip_count = int(product_duration.get("clip_count") or 2)

        payload = {
            "topic_mode": "channel",
            "scheduler_topic": channel_topic,
            "duration_seconds": duration_seconds,
            "clip_count": clip_count,
            "platform": platform,
            "platform_targets": [platform],
            "provider": "runway",
            "provider_runtime": "pwmap_agent",
            "browser_automation": True,
            "skip_credit_guard": True,
            "automation_mode": True,
            "execute_preflight": True,
            "use_ai_director": bool(profile.get("use_ai_director_default", True)),
            "use_prompt_critic": bool(profile.get("use_prompt_critic_default", True)),
            "execution_mode": "FULL_AUTO",
        }
        if platform == "youtube_shorts":
            payload["youtube_channel_topic"] = channel_topic
        elif platform == "instagram_reels":
            payload["instagram_channel_topic"] = channel_topic
        elif platform == "tiktok":
            payload["tiktok_channel_topic"] = channel_topic
        logger.info(
            "Automation job starting platform=%s clip_count=%s topic=%s",
            platform,
            clip_count,
            channel_topic[:80],
        )
        start_result = product_service.create_video_generate(payload, runway_service=runway_service)
        _upload_debug("create_video_generate", start_result)
        start_ok = bool(start_result.get("ok"))
        has_publish_ready = bool(
            start_result.get("publish_package_ready")
            or start_result.get("publish_ready")
            or str(start_result.get("final_branded_publish_video_path") or "").strip()
        )
        if not start_ok and not has_publish_ready:
            failure = {
                "ok": False,
                "error": str(start_result.get("message") or start_result.get("status") or "create_video_failed"),
                "stage": "content_brain_or_runway_start",
                "details": start_result,
            }
            _upload_debug("create_video_generate_failed", failure)
            return failure
        if not start_ok and has_publish_ready:
            _upload_debug(
                "create_video_generate_partial_ok",
                {
                    "ok": start_ok,
                    "message": start_result.get("message"),
                    "publish_package_ready": start_result.get("publish_package_ready"),
                },
            )

        run_id = str(start_result.get("session_id") or start_result.get("run_id") or "")
        if self._is_pwmap_browser_result(start_result):
            report = dict(start_result)
            output_path, publish_path = self._resolve_pwmap_output_paths(start_result)
        elif wait_for_runway:
            runway_result = self._wait_for_runway(runway_service, poll_interval_seconds, max_wait_seconds)
            if not runway_result.get("ok"):
                return {
                    "ok": False,
                    "error": str(runway_result.get("error") or "runway_failed"),
                    "stage": "runway_execution",
                    "run_id": run_id,
                    "details": runway_result,
                }
            report = dict(runway_result.get("report") or {})
            run_id = str(report.get("content_brain_run_id") or run_id)
            output_path, publish_path = self._resolve_output_paths(report)
        else:
            report = {}
            output_path = ""
            publish_path = ""

        upload_package: dict[str, Any] = {}
        platform_uploads: dict[str, Any] = {"ok": False, "skipped": True, "reason": "auto_upload_disabled"}
        upload_targets, upload_block_reason = _enforce_job_upload_targets(job, platform)
        _upload_debug(
            "enforce_job_upload_targets",
            {"job_platform": normalize_platform(platform), "upload_targets": upload_targets, "block_reason": upload_block_reason},
        )
        yt_chain = dict(report.get("youtube_upload") or start_result.get("youtube_upload") or {})
        auto_upload_on = is_auto_upload_enabled(self.project_root)
        _upload_debug("auto_upload_enabled", {"enabled": auto_upload_on, "yt_chain": yt_chain})
        if auto_upload_on and not upload_targets:
            platform_uploads = {
                "ok": False,
                "skipped": True,
                "reason": upload_block_reason or "cross_platform_upload_blocked",
            }
            _upload_debug("upload_targets_blocked", platform_uploads)
        elif auto_upload_on:
            from content_brain.automation.fail_closed_upload_gate import evaluate_automation_upload_gate

            report_for_gate = dict(report or start_result)
            upload_allowed, upload_block_reason = evaluate_automation_upload_gate(
                project_root=self.project_root,
                generation_report=report_for_gate,
                run_id=run_id,
                planned_clip_count=int(job.clip_count or 0),
                publish_package_path=publish_path,
            )
            _upload_debug(
                "fail_closed_upload_gate",
                {
                    "allowed": upload_allowed,
                    "reason": upload_block_reason,
                    "status": report_for_gate.get("status"),
                    "clip_count": report_for_gate.get("clip_count"),
                },
            )
            if not upload_allowed:
                platform_uploads = {
                    "ok": False,
                    "skipped": True,
                    "reason": upload_block_reason,
                    "platforms": {},
                }
            elif not output_path and not publish_path:
                output_path, publish_path = self._resolve_pwmap_output_paths(report or start_result)
            upload_package = self.upload_manager.prepare_full_upload_workflow(
                topic=channel_topic,
                platform_targets=upload_targets,
                video_path=output_path or publish_path,
                publish_package_path=publish_path,
                run_id=run_id,
                use_openai=True,
                automation_mode=True,
            )
            _upload_debug("prepare_full_upload_workflow", upload_package)

            from content_brain.automation.auto_platform_upload import submit_automation_platform_uploads

            job_platform = normalize_platform(platform)
            youtube_job = job_platform == "youtube_shorts"
            instagram_job = job_platform == "instagram_reels"

            if youtube_job and (yt_chain.get("uploaded") or yt_chain.get("ok")):
                platform_uploads = {
                    "ok": True,
                    "platforms": {
                        "youtube_shorts": {
                            "ok": True,
                            "uploaded": True,
                            "status": "already_uploaded",
                            "post_url": str(yt_chain.get("youtube_url") or yt_chain.get("video_url") or ""),
                        }
                    },
                    "video_path": output_path or publish_path,
                }
                _upload_debug("platform_uploads_already_uploaded", platform_uploads)
            elif instagram_job and yt_chain.get("uploaded"):
                logger.error(
                    "Ignoring cross-platform YouTube upload for Instagram job %s run_id=%s",
                    job.job_id,
                    run_id,
                )
                platform_uploads = submit_automation_platform_uploads(
                    project_root=self.project_root,
                    platform_targets=upload_targets,
                    video_path=output_path or publish_path,
                    publish_package_path=publish_path,
                    upload_package=upload_package,
                    run_id=run_id,
                    topic=channel_topic,
                    automation_mode=True,
                    job_platform=platform,
                    generation_report=report or start_result,
                    skip_youtube_if_already_uploaded=True,
                )
                _upload_debug("submit_automation_platform_uploads", platform_uploads)
            else:
                platform_uploads = submit_automation_platform_uploads(
                    project_root=self.project_root,
                    platform_targets=upload_targets,
                    video_path=output_path or publish_path,
                    publish_package_path=publish_path,
                    upload_package=upload_package,
                    run_id=run_id,
                    topic=channel_topic,
                    automation_mode=True,
                    job_platform=platform,
                    generation_report=report or start_result,
                    skip_youtube_if_already_uploaded=youtube_job,
                )
                if not platform_uploads.get("ok") and youtube_job and yt_chain.get("blocked_reason"):
                    platform_uploads["publish_chain_blocked_reason"] = yt_chain.get("blocked_reason")
                _upload_debug("submit_automation_platform_uploads", platform_uploads)

        final_result = {
            "ok": True,
            "run_id": run_id,
            "output_path": output_path,
            "publish_package_path": publish_path,
            "upload_package_path": str(upload_package.get("package_dir") or ""),
            "upload_package": upload_package,
            "platform_uploads": platform_uploads,
            "report": report,
            "start_result": start_result,
        }
        _upload_debug("_execute_job_complete", final_result)
        return final_result

    def _is_pwmap_browser_result(self, result: dict[str, Any]) -> bool:
        if result.get("browser_automation") or result.get("skip_credit_guard"):
            return True
        if str(result.get("provider_runtime") or "") == "pwmap_agent":
            return True
        engine = str(result.get("execution_engine") or "")
        return "pwmap/runway_agent" in engine or result.get("preflight_mode") == "executed_via_pwmap_agent"

    def _resolve_pwmap_output_paths(self, result: dict[str, Any]) -> tuple[str, str]:
        output = str(
            result.get("final_branded_publish_video_path")
            or result.get("final_publish_video_path")
            or result.get("final_branded_video_path")
            or result.get("final_video_path")
            or result.get("video_path")
            or result.get("download_path")
            or ""
        )
        publish = str(result.get("publish_package_path") or result.get("publish_package_folder") or "")
        if not output:
            run_id = str(result.get("run_id") or result.get("session_id") or "")
            if run_id:
                run_dir = self.project_root / "outputs" / "pwmap_agent_runs" / run_id
                publish_dir = run_dir / "publish"
                for name in (
                    "FINAL_BRANDED_PUBLISH_READY.mp4",
                    "FINAL_PUBLISH_READY.mp4",
                    "FINAL_BRANDED_VIDEO_CANONICAL.mp4",
                ):
                    candidate = publish_dir / name
                    if candidate.is_file():
                        output = str(candidate.resolve())
                        publish = str(publish_dir.resolve())
                        break
        return output, publish

    def _wait_for_runway(
        self,
        runway_service: Any,
        poll_interval_seconds: int,
        max_wait_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.time() + max(1, int(max_wait_seconds))
        while time.time() < deadline:
            health = get_browser_health(self.project_root)
            if not health.get("connected"):
                return {"ok": False, "error": "browser_disconnected_during_run"}
            snapshot_payload = runway_service.snapshot()
            if not snapshot_payload.get("active"):
                report = dict(snapshot_payload.get("report") or {})
                if report.get("ok"):
                    return {"ok": True, "report": report}
                return {
                    "ok": False,
                    "error": str(report.get("stopped_reason") or report.get("errors") or "runway_run_failed"),
                    "report": report,
                }
            time.sleep(max(1, int(poll_interval_seconds)))
        return {"ok": False, "error": "runway_wait_timeout"}

    def _resolve_output_paths(self, report: dict[str, Any]) -> tuple[str, str]:
        branded = str(report.get("final_branded_video_path") or "")
        final_video = str(report.get("final_video_path") or "")
        publish = str(report.get("publish_package_folder") or "")
        if not publish:
            fallback = self.project_root / "outputs" / "publish" / "runway_phase_i"
            if fallback.is_dir():
                publish = str(fallback)
        output = branded or final_video
        return output, publish

    def _load_scheduled_jobs(self) -> list[dict[str, Any]]:
        from content_brain.automation.platform_daily_scheduler import sync_platform_daily_jobs

        try:
            sync_platform_daily_jobs(self.project_root)
        except Exception:
            pass
        jobs_dir = self.project_root / "storage" / "content_brain" / "schedules" / "jobs"
        if not jobs_dir.is_dir():
            return []
        imported: list[dict[str, Any]] = []
        for path in sorted(jobs_dir.glob("*_jobs.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, list):
                imported.extend(item for item in payload if isinstance(item, dict) and item.get("status") == "planned")
        return imported

    def _finalize_job(self, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
        if result.get("ok"):
            platform_uploads = dict(result.get("platform_uploads") or {})
            updated = self.queue.update_job(
                job_id,
                status=JOB_COMPLETED,
                run_id=str(result.get("run_id") or ""),
                output_path=str(result.get("output_path") or ""),
                publish_package_path=str(result.get("publish_package_path") or ""),
                upload_package_path=str(result.get("upload_package_path") or ""),
                upload_result=platform_uploads or None,
                error="",
            )
            center = self.center.load()
            history = list(center.get("run_history") or [])
            job_dict = updated.to_dict() if updated else {"job_id": job_id, "status": JOB_COMPLETED}
            history.insert(0, job_dict)
            self.center.save({"run_history": history[:100]})
            platform = str((job_dict.get("platform_targets") or ["youtube_shorts"])[0] or "youtube_shorts")
            try:
                from content_brain.automation.platform_daily_scheduler_store import PlatformDailySchedulerStore

                PlatformDailySchedulerStore(self.project_root).record_platform_completion(platform)
            except Exception:
                pass
            self._record_upload_history(job_dict, result)
            _upload_debug("_finalize_job_completed", {"job_id": job_id, "upload_result": platform_uploads})
            return {"ok": True, "status": JOB_COMPLETED, "job": job_dict, "result": result}

        error = str(result.get("error") or "automation_failed")
        updated = self.queue.update_job(job_id, status=JOB_FAILED, error=error)
        center = self.center.load()
        failed = list(center.get("failed_jobs") or [])
        job_dict = {**(updated.to_dict() if updated else {"job_id": job_id}), "reason": error}
        failed.insert(0, job_dict)
        self.center.save({"failed_jobs": failed[:100]})
        self._record_upload_history(job_dict, result, success=False, error=error)
        _upload_debug("_finalize_job_failed", {"job_id": job_id, "error": error, "result": result})
        return {"ok": False, "status": JOB_FAILED, "job": updated.to_dict() if updated else {}, "error": error, "result": result}

    def _record_upload_history(
        self,
        job: dict[str, Any],
        result: dict[str, Any],
        *,
        success: bool | None = None,
        error: str = "",
    ) -> None:
        from content_brain.automation.platform_daily_scheduler import display_platform_topic
        from content_brain.automation.upload_history_store import UploadHistoryStore
        from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

        platform = str((job.get("platform_targets") or ["youtube_shorts"])[0] or "youtube_shorts")
        profile = ProductChannelProfileStore(self.project_root).load()
        title = display_platform_topic(
            platform,
            profile,
            str(job.get("title") or job.get("topic") or ""),
        )
        run_id = str(result.get("run_id") or job.get("run_id") or "")
        uploads = dict(result.get("platform_uploads") or {})

        if uploads and not uploads.get("skipped"):
            history = UploadHistoryStore(self.project_root)
            for platform_key, upload_result in (uploads.get("platforms") or {}).items():
                if not isinstance(upload_result, dict):
                    continue
                post_url = str(
                    upload_result.get("post_url")
                    or upload_result.get("video_url")
                    or upload_result.get("youtube_url")
                    or ""
                )
                history.record(
                    platform=str(platform_key or platform),
                    title=title,
                    success=bool(upload_result.get("ok") or upload_result.get("uploaded")),
                    run_id=run_id,
                    youtube_url=post_url,
                    post_url=post_url,
                    error=str(upload_result.get("reason") or upload_result.get("error") or ""),
                )
            return

        upload_ok = success
        post_url = ""
        if upload_ok is None:
            report = dict(result.get("report") or {})
            upload_ok = bool(result.get("ok"))
            post_url = str(report.get("youtube_url") or report.get("video_url") or "")
        UploadHistoryStore(self.project_root).record(
            platform=platform,
            title=title,
            success=bool(upload_ok),
            run_id=run_id,
            youtube_url=post_url,
            post_url=post_url,
            error=error or str(uploads.get("reason") or uploads.get("error") or ""),
        )


__all__ = ["AutomationJobRunner", "RUNNER_VERSION"]
