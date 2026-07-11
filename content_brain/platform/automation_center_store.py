"""Automation Center foundation state — planning/control only (V1)."""



from __future__ import annotations



import json

from datetime import datetime, timezone

from pathlib import Path

from typing import Any

from content_brain.platform.json_utf8 import dumps_json, repair_mojibake_text



AUTOMATION_VERSION = "platform_automation_center_v1"

AUTOMATION_PATH = Path("project_brain") / "platform" / "automation_center.json"



DEFAULT_STATE: dict[str, Any] = {

    "version": AUTOMATION_VERSION,

    "enabled": False,

    "paused": True,

    "daily_schedule_overview": [],

    "queued_jobs": [],

    "run_history": [],

    "failed_jobs": [],

    "feature_flags": {

        "auto_generate": False,

        "auto_voice": True,

        "auto_publish_package": False,

        "auto_upload": True,

        "suno_music": False,

        "analytics": False,

    },

    "updated_at": "",

}





class AutomationCenterStore:

    def __init__(self, project_root: str | Path) -> None:

        self.project_root = Path(project_root).resolve()

        self.path = self.project_root / AUTOMATION_PATH



    def _now(self) -> str:

        return datetime.now(timezone.utc).isoformat()



    def load(self) -> dict[str, Any]:

        if not self.path.is_file():

            return dict(DEFAULT_STATE)

        try:

            payload = json.loads(self.path.read_text(encoding="utf-8"))

        except (OSError, json.JSONDecodeError):

            return dict(DEFAULT_STATE)

        merged = dict(DEFAULT_STATE)

        merged.update(repair_mojibake_text(payload) if isinstance(payload, dict) else {})

        stored_flags = dict(merged.get("feature_flags") or {})

        default_flags = dict(DEFAULT_STATE["feature_flags"])

        for key, default_val in default_flags.items():

            stored_flags.setdefault(key, default_val)

        merged["feature_flags"] = stored_flags

        return merged



    def save(self, payload: dict[str, Any]) -> dict[str, Any]:

        current = self.load()

        for key in ("enabled", "paused", "daily_schedule_overview", "queued_jobs", "run_history", "failed_jobs", "feature_flags"):

            if key not in payload or payload[key] is None:

                continue

            if key == "feature_flags" and isinstance(payload[key], dict):

                merged_flags = dict(current.get("feature_flags") or {})

                merged_flags.update(payload[key])

                current[key] = merged_flags

                continue

            current[key] = payload[key]

        current["updated_at"] = self._now()

        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.path.write_text(dumps_json(current), encoding="utf-8")

        return self.load()



    def queue_manual_job(self, job: dict[str, Any]) -> dict[str, Any]:

        current = self.load()

        queued = list(current.get("queued_jobs") or [])

        queued.append({**job, "queued_at": self._now(), "status": "queued"})

        current["queued_jobs"] = queued[-50:]

        return self.save(current)



    def pop_next_job(self) -> dict[str, Any] | None:

        current = self.load()

        queued = list(current.get("queued_jobs") or [])

        if not queued:

            return None

        job = queued.pop(0)

        history = list(current.get("run_history") or [])

        history.insert(0, {**job, "started_at": self._now(), "status": "manual_started"})

        current["queued_jobs"] = queued

        current["run_history"] = history[:100]

        return self.save(current)



    def record_failed_job(self, job: dict[str, Any], reason: str) -> dict[str, Any]:

        current = self.load()

        failed = list(current.get("failed_jobs") or [])

        failed.insert(0, {**job, "failed_at": self._now(), "reason": reason})

        current["failed_jobs"] = failed[:100]

        return self.save(current)





def is_auto_upload_enabled(project_root: str | Path) -> bool:

    flags = AutomationCenterStore(project_root).load().get("feature_flags") or {}

    return bool(flags.get("auto_upload", True))

