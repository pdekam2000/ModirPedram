"""Automation job runner — one job at a time with safety caps."""

from __future__ import annotations

import json
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
from content_brain.platform.automation_center_store import AutomationCenterStore
from content_brain.platform.browser_health_monitor import get_browser_health
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.upload_manager import UploadManager

RUNNER_VERSION = "automation_job_runner_v1"
POLL_INTERVAL_SECONDS = 5
MAX_WAIT_SECONDS = 7200


class AutomationJobRunner:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.queue = AutomationQueue(self.project_root)
        self.center = AutomationCenterStore(self.project_root)
        self.upload_manager = UploadManager(self.project_root)

    def get_status(self) -> dict[str, Any]:
        center = self.center.load()
        running = self.queue.running_job()
        next_job = self.queue.next_planned_job()
        jobs = self.queue.list_jobs()
        return {
            "version": RUNNER_VERSION,
            "enabled": bool(center.get("enabled")),
            "paused": bool(center.get("paused", True)),
            "feature_flags": dict(center.get("feature_flags") or {}),
            "running_job": running.to_dict() if running else None,
            "next_job": next_job.to_dict() if next_job else None,
            "queued_count": len([job for job in jobs if job.status == "planned"]),
            "completed_count": len([job for job in jobs if job.status == JOB_COMPLETED]),
            "failed_count": len([job for job in jobs if job.status == JOB_FAILED]),
            "completed_today": self.queue.completed_today_count(),
            "max_jobs_per_day": self.queue.max_jobs_per_day(),
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
        if self.queue.running_job() is not None:
            return False, "job_already_running"
        if self.queue.completed_today_count() >= self.queue.max_jobs_per_day():
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

    def start_next_job(
        self,
        *,
        product_service: Any,
        runway_service: Any,
        wait_for_runway: bool = True,
        poll_interval_seconds: int = POLL_INTERVAL_SECONDS,
        max_wait_seconds: int = MAX_WAIT_SECONDS,
    ) -> dict[str, Any]:
        ok, reason = self.preflight()
        if not ok:
            return {"ok": False, "status": JOB_SKIPPED, "reason": reason, "runner": self.get_status()}

        job = self.queue.next_planned_job()
        if job is None:
            scheduled = self._load_scheduled_jobs()
            if scheduled:
                self.queue.import_scheduled_jobs(scheduled)
                job = self.queue.next_planned_job()
        if job is None:
            return {"ok": False, "status": "no_jobs", "reason": "no_planned_jobs", "runner": self.get_status()}

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
        payload = {
            "topic_mode": "custom",
            "custom_topic": job.topic,
            "duration_seconds": job.duration,
            "clip_count": job.clip_count,
            "platform": (job.platform_targets[0] if job.platform_targets else profile.get("default_platform") or "youtube_shorts"),
            "provider": "runway",
            "use_ai_director": bool(profile.get("use_ai_director_default", True)),
            "use_prompt_critic": bool(profile.get("use_prompt_critic_default", True)),
            "execution_mode": "FULL_AUTO",
        }
        start_result = product_service.create_video_generate(payload, runway_service=runway_service)
        if not start_result.get("ok"):
            return {
                "ok": False,
                "error": str(start_result.get("message") or start_result.get("status") or "create_video_failed"),
                "stage": "content_brain_or_runway_start",
                "details": start_result,
            }

        run_id = str(start_result.get("session_id") or start_result.get("run_id") or "")
        if wait_for_runway:
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

        upload_package = self.upload_manager.prepare_full_upload_workflow(
            topic=job.topic,
            platform_targets=job.platform_targets,
            video_path=output_path or publish_path,
            publish_package_path=publish_path,
            run_id=run_id,
            use_openai=True,
        )

        return {
            "ok": True,
            "run_id": run_id,
            "output_path": output_path,
            "publish_package_path": publish_path,
            "upload_package_path": str(upload_package.get("package_dir") or ""),
            "upload_package": upload_package,
            "report": report,
            "start_result": start_result,
        }

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
            updated = self.queue.update_job(
                job_id,
                status=JOB_COMPLETED,
                run_id=str(result.get("run_id") or ""),
                output_path=str(result.get("output_path") or ""),
                publish_package_path=str(result.get("publish_package_path") or ""),
                upload_package_path=str(result.get("upload_package_path") or ""),
                error="",
            )
            center = self.center.load()
            history = list(center.get("run_history") or [])
            history.insert(0, updated.to_dict() if updated else {"job_id": job_id, "status": JOB_COMPLETED})
            self.center.save({"run_history": history[:100]})
            return {"ok": True, "status": JOB_COMPLETED, "job": updated.to_dict() if updated else {}, "result": result}

        error = str(result.get("error") or "automation_failed")
        updated = self.queue.update_job(job_id, status=JOB_FAILED, error=error)
        center = self.center.load()
        failed = list(center.get("failed_jobs") or [])
        failed.insert(0, {**(updated.to_dict() if updated else {"job_id": job_id}), "reason": error})
        self.center.save({"failed_jobs": failed[:100]})
        return {"ok": False, "status": JOB_FAILED, "job": updated.to_dict() if updated else {}, "error": error, "result": result}


__all__ = ["AutomationJobRunner", "RUNNER_VERSION"]
