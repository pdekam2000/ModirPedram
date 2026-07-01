"""Automation API service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from content_brain.automation.automation_job_runner import AutomationJobRunner
from content_brain.automation.automation_queue import AutomationQueue, JOB_CANCELLED
from content_brain.comments.comment_agent import draft_comment_reply
from content_brain.platform.automation_center_store import AutomationCenterStore
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.upload_manager import UploadManager


class AutomationService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.runner = AutomationJobRunner(self.project_root)
        self.queue = AutomationQueue(self.project_root)
        self.center = AutomationCenterStore(self.project_root)
        self.upload_manager = UploadManager(self.project_root)
        self.profile_store = ProductChannelProfileStore(self.project_root)

    def get_status(self) -> dict[str, Any]:
        status = self.runner.get_status()
        jobs = self.queue.list_jobs()
        status["jobs"] = {
            "upcoming": [job.to_dict() for job in jobs if job.status == "planned"],
            "running": [job.to_dict() for job in jobs if job.status == "running"],
            "completed": [job.to_dict() for job in jobs if job.status == "completed"][:20],
            "failed": [job.to_dict() for job in jobs if job.status == "failed"][:20],
            "cancelled": [job.to_dict() for job in jobs if job.status == JOB_CANCELLED][:20],
        }
        status["comment_drafts"] = self._load_comment_drafts()
        status["upload_packages"] = self._list_upload_packages()
        return status

    def list_jobs(self) -> dict[str, Any]:
        jobs = [job.to_dict() for job in self.queue.list_jobs()]
        return {"jobs": jobs, "count": len(jobs)}

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self.profile_store.load()
        job = self.queue.create_job(
            {
                "title": payload.get("title") or payload.get("topic") or "Automation job",
                "topic": payload.get("topic") or profile.get("channel_topic") or "",
                "duration": int(payload.get("duration") or payload.get("duration_seconds") or profile.get("default_duration_seconds") or 30),
                "clip_count": int(payload.get("clip_count") or 3),
                "platform_targets": list(payload.get("platform_targets") or payload.get("platforms") or profile.get("upload_platforms") or ["youtube_shorts"]),
                "scheduled_time": str(payload.get("scheduled_time") or ""),
            }
        )
        center = self.center.load()
        queued = list(center.get("queued_jobs") or [])
        queued.append(job.to_dict())
        self.center.save({"queued_jobs": queued[-50:]})
        return {"ok": True, "job": job.to_dict()}

    def start_next(self, *, product_service: Any, runway_service: Any) -> dict[str, Any]:
        return self.runner.start_next_job(product_service=product_service, runway_service=runway_service)

    def pause(self) -> dict[str, Any]:
        state = self.runner.pause()
        return {"ok": True, "paused": True, "automation_center": state}

    def resume(self) -> dict[str, Any]:
        state = self.runner.resume()
        return {"ok": True, "paused": False, "automation_center": state}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        job = self.queue.cancel_job(job_id)
        if job is None:
            return {"ok": False, "message": "job_not_found"}
        return {"ok": True, "job": job.to_dict()}

    def prepare_upload(self, payload: dict[str, Any]) -> dict[str, Any]:
        manifest = self.upload_manager.prepare_full_upload_workflow(
            topic=str(payload.get("topic") or ""),
            platform_targets=list(payload.get("platform_targets") or payload.get("platforms") or ["youtube_shorts"]),
            video_path=str(payload.get("video_path") or ""),
            publish_package_path=str(payload.get("publish_package_path") or ""),
            run_id=str(payload.get("run_id") or ""),
            use_openai=bool(payload.get("use_openai", True)),
        )
        legacy = dict(manifest.get("legacy_package") or {})
        return {"ok": True, "upload_package": legacy or manifest, "upload_manifest": manifest}

    def submit_youtube(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.upload_manager.submit_youtube_upload(
            upload_package=dict(payload.get("upload_package") or {}),
            package_dir=str(payload.get("package_dir") or ""),
            run_id=str(payload.get("run_id") or ""),
            confirmed=bool(payload.get("confirmed")),
        )
        if result.get("ok") and bool(payload.get("confirmed")):
            self.profile_store.save({"youtube_upload_confirmed": True})
        return result

    def draft_comment_reply(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self.profile_store.load()
        draft = draft_comment_reply(
            comment_text=str(payload.get("comment_text") or ""),
            video_topic=str(payload.get("video_topic") or payload.get("topic") or profile.get("channel_topic") or ""),
            channel_tone=str(payload.get("channel_tone") or profile.get("tone_style") or "friendly"),
            language=str(payload.get("language") or profile.get("language") or "English"),
            use_openai=bool(payload.get("use_openai", True)),
        )
        drafts = self._load_comment_drafts()
        drafts.insert(0, draft)
        self._save_comment_drafts(drafts[:50])
        return {"ok": True, "draft": draft}

    def approve_comment_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        drafts = self._load_comment_drafts()
        index = int(payload.get("index") or 0)
        if index < 0 or index >= len(drafts):
            return {"ok": False, "message": "draft_not_found", "posted": False}
        draft = dict(drafts[index])
        draft["approval_status"] = "approved"
        draft["auto_posted"] = False
        draft["posted"] = False
        drafts[index] = draft
        self._save_comment_drafts(drafts)
        return {"ok": True, "draft": draft, "posted": False, "message": "Draft approved only — auto-posting disabled in V1."}

    def reject_comment_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        drafts = self._load_comment_drafts()
        index = int(payload.get("index") or 0)
        if index < 0 or index >= len(drafts):
            return {"ok": False, "message": "draft_not_found"}
        draft = dict(drafts[index])
        draft["approval_status"] = "rejected"
        drafts[index] = draft
        self._save_comment_drafts(drafts)
        return {"ok": True, "draft": draft}

    def _comment_drafts_path(self) -> Path:
        return self.project_root / "project_brain" / "automation" / "comment_drafts.json"

    def _load_comment_drafts(self) -> list[dict[str, Any]]:
        path = self._comment_drafts_path()
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return list(payload) if isinstance(payload, list) else []

    def _save_comment_drafts(self, drafts: list[dict[str, Any]]) -> None:
        path = self._comment_drafts_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(drafts, indent=2), encoding="utf-8")

    def _list_upload_packages(self) -> list[dict[str, Any]]:
        root = self.project_root / "outputs" / "upload_packages"
        if not root.is_dir():
            return []
        packages: list[dict[str, Any]] = []
        for manifest in sorted(root.glob("*/upload_package.json"), reverse=True)[:10]:
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(payload, dict):
                packages.append(payload)
        return packages


def get_automation_service(project_root: str | Path | None = None) -> AutomationService:
    if project_root is None:
        from ui.api.dependencies import get_project_root

        project_root = get_project_root()
    return AutomationService(project_root)
