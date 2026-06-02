"""
Execution session store — read/write sessions under storage/content_brain/execution/.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator


def _first(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _first_number(*values: Any, default: float | None = None) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class ExecutionSessionStore:
    """Loads execution session JSON from disk."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.execution_root = (
            self.project_root / "storage" / "content_brain" / "execution"
        )
        self.sessions_dir = self.execution_root / "sessions"
        self.simulations_dir = self.execution_root / "simulations"
        self.queue_dir = self.execution_root / "queue"
        self.queue_index_path = self.queue_dir / "active_index.json"
        self.queue_audit_path = self.queue_dir / "audit.jsonl"
        self.artifacts_dir = self.execution_root / "artifacts"
        self.runtime_dir = self.execution_root / "runtime"
        self.jobs_dir = self.runtime_dir / "jobs"
        self.logs_dir = self.runtime_dir / "logs"
        self.active_jobs_path = self.runtime_dir / "active_jobs.json"
        self.locks_dir = self.runtime_dir / "locks"
        self.provider_audit_path = self.runtime_dir / "audit.jsonl"
        self.operations_audit_path = self.runtime_dir / "operations_audit.jsonl"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.simulations_dir.mkdir(parents=True, exist_ok=True)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def list_session_paths(self) -> list[Path]:
        paths = list(self.sessions_dir.glob("*.json"))
        paths.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return paths

    def load_session(self, session_id: str) -> dict[str, Any]:
        direct = self.sessions_dir / f"{session_id}.json"
        if direct.exists():
            return self._read_json(direct)

        for path in self.sessions_dir.glob("*.json"):
            data = self._read_json(path)
            if self.extract_session_id(data) == session_id:
                return data

        raise FileNotFoundError(f"Execution session not found: {session_id}")

    def load_session_from_path(self, path: Path) -> dict[str, Any]:
        return self._read_json(path)

    def list_summaries(self) -> list[dict[str, Any]]:
        summaries = []
        for path in self.list_session_paths():
            try:
                data = self._read_json(path)
            except Exception:
                continue
            summary = self.summarize(data)
            summary["file_path"] = str(path)
            summaries.append(summary)
        return summaries

    def summarize(self, data: dict[str, Any]) -> dict[str, Any]:
        provider_selection = data.get("provider_selection") or {}
        if not isinstance(provider_selection, dict):
            provider_selection = {}

        approval_request = data.get("approval_request") or {}
        if not isinstance(approval_request, dict):
            approval_request = {}

        approval_decision = data.get("approval_decision") or {}
        if not isinstance(approval_decision, dict):
            approval_decision = {}

        budget_decision = data.get("budget_decision") or {}
        if not isinstance(budget_decision, dict):
            budget_decision = {}

        confidence = data.get("execution_confidence") or {}
        if not isinstance(confidence, dict):
            confidence = {}

        score = _first_number(
            data.get("story_quality_score"),
            data.get("story_quality", {}).get("score")
            if isinstance(data.get("story_quality"), dict)
            else None,
            data.get("story_quality", {}).get("composite_score")
            if isinstance(data.get("story_quality"), dict)
            else None,
        )

        return {
            "session_id": self.extract_session_id(data),
            "session_uuid": _first(data.get("session_uuid"), default=""),
            "session_schema_version": _first(data.get("session_schema_version"), default=""),
            "brief_id": _first(data.get("brief_id")),
            "status": self.extract_status(data),
            "provider": self.extract_provider(data, provider_selection),
            "story_quality_score": score,
            "approval_state": self.extract_approval_state(
                data, approval_request, approval_decision
            ),
            "budget_state": self.extract_budget_state(data, budget_decision),
            "priority_band": _first(
                data.get("priority_band"),
                data.get("priority_decision", {}).get("priority_band")
                if isinstance(data.get("priority_decision"), dict)
                else None,
                default="—",
            ),
            "execution_confidence": _first_number(
                data.get("execution_confidence_score"),
                confidence.get("execution_confidence_score"),
                default=None,
            ),
            "created_at": _first(data.get("created_at"), default="—"),
            **self.extract_archive_summary(data),
        }

    @staticmethod
    def extract_archive_summary(data: dict[str, Any]) -> dict[str, Any]:
        control = data.get("operations_control") or {}
        if not isinstance(control, dict):
            control = {}
        archived = bool(control.get("archived"))
        return {
            "archived": archived,
            "archived_at": control.get("archived_at") if archived else None,
            "archived_by": control.get("archived_by") if archived else None,
            "archive_reason": control.get("archive_reason") if archived else None,
        }

    @staticmethod
    def extract_session_id(data: dict[str, Any]) -> str:
        return _first(
            data.get("execution_session_id"),
            data.get("session_id"),
            default="unknown",
        )

    @staticmethod
    def extract_status(data: dict[str, Any]) -> str:
        return _first(
            data.get("state"),
            data.get("status"),
            default="UNKNOWN",
        ).upper()

    @staticmethod
    def extract_provider(
        data: dict[str, Any],
        provider_selection: dict[str, Any],
    ) -> str:
        return _first(
            data.get("provider"),
            provider_selection.get("primary_provider"),
            provider_selection.get("selected_provider"),
            provider_selection.get("winner"),
            (
                provider_selection.get("provider")
                if isinstance(provider_selection.get("provider"), str)
                else None
            ),
            default="—",
        )

    @staticmethod
    def extract_approval_state(
        data: dict[str, Any],
        approval_request: dict[str, Any],
        approval_decision: dict[str, Any],
    ) -> str:
        return _first(
            data.get("approval_state"),
            approval_decision.get("status"),
            approval_decision.get("action"),
            approval_request.get("status"),
            "pending" if approval_request else "",
            default="—",
        )

    @staticmethod
    def extract_budget_state(
        data: dict[str, Any],
        budget_decision: dict[str, Any],
    ) -> str:
        if budget_decision.get("budget_allowed") is True:
            return "allowed"
        if budget_decision.get("budget_allowed") is False:
            return "blocked"
        budget_status = _first(
            budget_decision.get("budget_status"),
            budget_decision.get("budget_state"),
        )
        if budget_status == "WARNING":
            return "warning"
        if budget_status == "BUDGET_BLOCKED":
            return "blocked"
        if budget_status == "WITHIN_LIMIT":
            return "allowed"
        return _first(
            data.get("budget_state"),
            default="—",
        )

    def resolve_simulation_report(self, data: dict[str, Any]) -> dict[str, Any] | None:
        embedded = data.get("simulation_report")
        if isinstance(embedded, dict) and embedded:
            return embedded

        report_id = _first(data.get("simulation_report_id"))
        if not report_id:
            return None

        for candidate in (
            self.simulations_dir / f"{report_id}.json",
            self.simulations_dir / f"sim_{report_id}.json",
        ):
            if candidate.exists():
                return self._read_json(candidate)

        for path in self.simulations_dir.glob("*.json"):
            payload = self._read_json(path)
            if _first(payload.get("report_id")) == report_id:
                return payload

        return None

    def resolve_approval_decision(self, data: dict[str, Any]) -> dict[str, Any] | None:
        embedded = data.get("approval_decision")
        if isinstance(embedded, dict) and embedded:
            return embedded

        request = data.get("approval_request")
        if isinstance(request, dict) and request.get("status") == "pending":
            return {"status": "pending", "request": request}

        return None

    def build_timeline_events(self, data: dict[str, Any]) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []

        session_id = self.extract_session_id(data)
        created_at = _first(data.get("created_at"))

        if created_at:
            events.append(
                {
                    "timestamp": created_at,
                    "event_type": "SESSION",
                    "label": "SESSION_CREATED",
                    "status": "SUCCESS",
                    "message": f"Session {session_id} created.",
                }
            )

        for entry in data.get("timeline_events") or []:
            if not isinstance(entry, dict):
                continue
            events.append(
                {
                    "timestamp": _first(entry.get("timestamp"), entry.get("at")),
                    "event_type": _first(entry.get("event_type"), default="EVENT"),
                    "label": _first(entry.get("label"), entry.get("event")),
                    "status": _first(entry.get("status")),
                    "message": _first(entry.get("message"), entry.get("reason")),
                }
            )

        for entry in data.get("state_history") or []:
            if not isinstance(entry, dict):
                continue
            state = _first(entry.get("state"), entry.get("status"))
            events.append(
                {
                    "timestamp": _first(entry.get("at"), entry.get("timestamp")),
                    "event_type": "STATE",
                    "label": state,
                    "status": state,
                    "message": _first(entry.get("reason"), entry.get("message")),
                }
            )

        for entry in data.get("execution_log") or []:
            if not isinstance(entry, dict):
                continue
            events.append(
                {
                    "timestamp": _first(entry.get("timestamp")),
                    "event_type": "ACTION",
                    "label": _first(entry.get("action"), entry.get("label")),
                    "status": _first(entry.get("status")),
                    "message": _first(entry.get("message")),
                }
            )

        for entry in data.get("queue_audit_log") or []:
            if not isinstance(entry, dict):
                continue
            event_type = _first(entry.get("event_type"))
            events.append(
                {
                    "timestamp": _first(entry.get("at"), entry.get("timestamp")),
                    "event_type": "QUEUE",
                    "label": event_type,
                    "status": event_type,
                    "message": _first(
                        _dict(entry.get("details")).get("cancel_reason"),
                        _dict(entry.get("details")).get("expire_reason"),
                        _dict(entry.get("details")).get("reject_code"),
                        event_type,
                    ),
                }
            )

        for entry in data.get("provider_audit_log") or []:
            if not isinstance(entry, dict):
                continue
            event_type = _first(entry.get("event_type"))
            events.append(
                {
                    "timestamp": _first(entry.get("at"), entry.get("timestamp")),
                    "event_type": "PROVIDER",
                    "label": event_type,
                    "status": event_type,
                    "message": _first(
                        _dict(entry.get("details")).get("code"),
                        _dict(entry.get("details")).get("provider"),
                        event_type,
                    ),
                }
            )

        for entry in data.get("operations_audit_log") or []:
            if not isinstance(entry, dict):
                continue
            action = _first(entry.get("action"))
            events.append(
                {
                    "timestamp": _first(entry.get("timestamp"), entry.get("at")),
                    "event_type": "OPERATIONS",
                    "label": action.upper() if action else "OPERATIONS",
                    "status": "ALLOWED" if entry.get("allowed") else "BLOCKED",
                    "message": _first(entry.get("reason"), entry.get("blocked_reason"), action),
                }
            )

        updated_at = _first(data.get("updated_at"))
        status = self.extract_status(data)
        if updated_at:
            events.append(
                {
                    "timestamp": updated_at,
                    "event_type": "SESSION",
                    "label": "SESSION_STATUS",
                    "status": status,
                    "message": f"Current status: {status}",
                }
            )

        events.sort(key=lambda item: item.get("timestamp", ""))
        return events

    def save_session(self, data: dict[str, Any], *, overwrite: bool = False) -> Path:
        """Persist a session document to sessions/{execution_session_id}.json."""
        if not isinstance(data, dict):
            raise ValueError("Session payload must be a dict.")

        session_id = self.extract_session_id(data)
        if not session_id or session_id == "unknown":
            raise ValueError("Session must include execution_session_id.")

        path = self.sessions_dir / f"{session_id}.json"
        if path.exists() and not overwrite:
            existing = self._read_json(path)
            existing_uuid = _first(existing.get("session_uuid"))
            incoming_uuid = _first(data.get("session_uuid"))
            if existing_uuid and incoming_uuid and existing_uuid != incoming_uuid:
                raise ValueError(
                    f"Refusing to overwrite session {session_id!r}: session_uuid mismatch."
                )

        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def load_session_by_uuid(self, session_uuid: str) -> dict[str, Any]:
        cleaned = str(session_uuid or "").strip()
        if not cleaned:
            raise ValueError("session_uuid is required.")

        for path in self.list_session_paths():
            data = self._read_json(path)
            if _first(data.get("session_uuid")) == cleaned:
                return data

        raise FileNotFoundError(f"Execution session not found for uuid: {cleaned}")

    def load_queue_index(self) -> dict[str, Any]:
        if not self.queue_index_path.exists():
            return {"index_version": "10h_v1", "updated_at": "", "items": []}
        payload = self._read_json(self.queue_index_path)
        if not isinstance(payload.get("items"), list):
            payload["items"] = []
        return payload

    def save_queue_index(self, index: dict[str, Any]) -> Path:
        if not isinstance(index, dict):
            raise ValueError("Queue index must be a dict.")
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.queue_index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return self.queue_index_path

    def append_global_queue_audit(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise ValueError("Queue audit event must be a dict.")
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        with self.queue_audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def artifact_dir(self, session_id: str, category: str = "video_generation") -> Path:
        path = self.artifacts_dir / session_id / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def append_global_provider_audit(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise ValueError("Provider audit event must be a dict.")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with self.provider_audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def append_global_operations_audit(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise ValueError("Operations audit event must be a dict.")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with self.operations_audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def job_snapshot_path(self, dispatch_id: str) -> Path:
        cleaned = str(dispatch_id or "").strip()
        if not cleaned:
            raise ValueError("dispatch_id is required.")
        return self.jobs_dir / f"{cleaned}.json"

    def log_path_for_job(self, dispatch_id: str) -> Path:
        cleaned = str(dispatch_id or "").strip()
        if not cleaned:
            raise ValueError("dispatch_id is required.")
        return self.logs_dir / f"{cleaned}.log"

    def load_active_jobs(self) -> dict[str, Any]:
        if not self.active_jobs_path.exists():
            return {"registry_version": "10j_v1", "updated_at": "", "items": []}
        payload = self._read_json(self.active_jobs_path)
        if not isinstance(payload.get("items"), list):
            payload["items"] = []
        return payload

    def save_active_jobs(self, index: dict[str, Any]) -> Path:
        if not isinstance(index, dict):
            raise ValueError("Active jobs index must be a dict.")
        self.atomic_write_json(self.active_jobs_path, index)
        return self.active_jobs_path

    @staticmethod
    def atomic_write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(path)

    @contextmanager
    def file_mutex(self, name: str, *, timeout_seconds: float = 10.0) -> Iterator[None]:
        cleaned = str(name or "").strip().replace("/", "_").replace("\\", "_")
        if not cleaned:
            raise ValueError("Mutex name is required.")
        lock_path = self.locks_dir / f"{cleaned}.lock"
        deadline = time.monotonic() + timeout_seconds
        acquired = False
        while time.monotonic() < deadline:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                acquired = True
                break
            except FileExistsError:
                time.sleep(0.05)
        if not acquired:
            raise TimeoutError(f"Timed out acquiring lock: {cleaned}")
        try:
            yield
        finally:
            lock_path.unlink(missing_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object in {path}")
        return payload

    @staticmethod
    def format_json(payload: Any) -> str:
        if payload is None:
            return "(not available)"
        return json.dumps(payload, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    store = ExecutionSessionStore(".")
    summaries = store.list_summaries()
    print(f"Sessions: {len(summaries)}")
    for item in summaries[:5]:
        print(item)
