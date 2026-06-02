"""
Phase 10J-c — active job index, snapshots, and concurrency helpers.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import time
from typing import Any, Iterator

from content_brain.execution.provider_mode_catalog import EXECUTION_MODE_BROWSER
from content_brain.execution.session_store import ExecutionSessionStore

REGISTRY_VERSION = "10j_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

PHASE_JOB_ACCEPTED = "JOB_ACCEPTED"
PHASE_PREFLIGHT_RUNNING = "PREFLIGHT_RUNNING"
PHASE_PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
PHASE_PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
PHASE_RUNNING = "RUNNING"
PHASE_COMPLETED = "COMPLETED"
PHASE_FAILED = "FAILED"

TERMINAL_PHASES = frozenset(
    {
        PHASE_PREFLIGHT_FAILED,
        PHASE_COMPLETED,
        PHASE_FAILED,
    }
)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), TIMESTAMP_FORMAT)
    except ValueError:
        return None


@dataclass
class JobRecord:
    job_id: str
    session_id: str
    phase: str = PHASE_JOB_ACCEPTED
    provider_family: str | None = None
    provider_execution_mode: str | None = None
    provider_resolved: str | None = None
    learning_key: str | None = None
    accepted_at: str = field(default_factory=_now)
    heartbeat_at: str | None = None
    thread_id: int | None = None
    stale: bool = False
    stale_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "phase": self.phase,
            "provider_family": self.provider_family,
            "provider_execution_mode": self.provider_execution_mode,
            "provider_resolved": self.provider_resolved,
            "learning_key": self.learning_key,
            "accepted_at": self.accepted_at,
            "heartbeat_at": self.heartbeat_at,
            "thread_id": self.thread_id,
            "stale": self.stale,
            "stale_reason": self.stale_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> JobRecord:
        return cls(
            job_id=str(payload.get("job_id") or ""),
            session_id=str(payload.get("session_id") or ""),
            phase=str(payload.get("phase") or PHASE_JOB_ACCEPTED),
            provider_family=payload.get("provider_family"),
            provider_execution_mode=payload.get("provider_execution_mode"),
            provider_resolved=payload.get("provider_resolved"),
            learning_key=payload.get("learning_key"),
            accepted_at=str(payload.get("accepted_at") or _now()),
            heartbeat_at=payload.get("heartbeat_at"),
            thread_id=payload.get("thread_id"),
            stale=bool(payload.get("stale")),
            stale_reason=payload.get("stale_reason"),
        )


class RuntimeJobRegistry:
    """Manages active_jobs.json and per-job snapshots on disk."""

    def __init__(self, store: ExecutionSessionStore):
        self.store = store

    @property
    def active_jobs_path(self) -> os.PathLike[str]:
        return self.store.active_jobs_path

    def load_index(self) -> dict[str, Any]:
        return self.store.load_active_jobs()

    def save_index(self, index: dict[str, Any]) -> None:
        self.store.save_active_jobs(index)

    @contextmanager
    def mutex(self) -> Iterator[None]:
        with self.store.file_mutex("active_jobs"):
            yield

    def list_active(self) -> list[JobRecord]:
        index = self.load_index()
        items = index.get("items") if isinstance(index.get("items"), list) else []
        return [JobRecord.from_dict(item) for item in items if isinstance(item, dict)]

    def get_active_for_session(self, session_id: str) -> JobRecord | None:
        cleaned = str(session_id or "").strip()
        for record in self.list_active():
            if record.session_id == cleaned and record.phase not in TERMINAL_PHASES:
                return record
        return None

    def count_active_browser_jobs(self) -> int:
        count = 0
        for record in self.list_active():
            if record.phase in TERMINAL_PHASES:
                continue
            if str(record.provider_execution_mode or "").lower() == EXECUTION_MODE_BROWSER:
                count += 1
        return count

    def register(self, record: JobRecord) -> JobRecord:
        with self.mutex():
            if self.get_active_for_session(record.session_id):
                raise JobAlreadyActiveError(record.session_id)
            index = self.load_index()
            items = list(index.get("items") or [])
            items.append(record.to_dict())
            index["items"] = items
            index["registry_version"] = REGISTRY_VERSION
            index["updated_at"] = _now()
            self.save_index(index)
        self.write_snapshot(record.job_id, record.to_dict())
        return record

    def update(self, job_id: str, **fields: Any) -> JobRecord | None:
        with self.mutex():
            index = self.load_index()
            items = list(index.get("items") or [])
            updated: JobRecord | None = None
            for index_pos, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                if str(item.get("job_id")) != str(job_id):
                    continue
                merged = {**item, **fields}
                items[index_pos] = merged
                updated = JobRecord.from_dict(merged)
                break
            if updated is None:
                return None
            index["items"] = items
            index["updated_at"] = _now()
            self.save_index(index)
        snapshot = self.load_snapshot(job_id) or {}
        snapshot.update(updated.to_dict())
        self.write_snapshot(job_id, snapshot)
        return updated

    def remove(self, job_id: str) -> JobRecord | None:
        with self.mutex():
            index = self.load_index()
            items = list(index.get("items") or [])
            removed: JobRecord | None = None
            kept: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if str(item.get("job_id")) == str(job_id):
                    removed = JobRecord.from_dict(item)
                    continue
                kept.append(item)
            if removed is None:
                return None
            index["items"] = kept
            index["updated_at"] = _now()
            self.save_index(index)
        return removed

    def finalize(self, job_id: str, *, phase: str, terminal_snapshot: dict[str, Any] | None = None) -> None:
        snapshot = self.load_snapshot(job_id) or {}
        snapshot.update(terminal_snapshot or {})
        snapshot["phase"] = phase
        snapshot["finalized_at"] = _now()
        self.write_snapshot(job_id, snapshot)
        self.remove(job_id)

    def write_snapshot(self, job_id: str, payload: dict[str, Any]) -> None:
        path = self.store.job_snapshot_path(job_id)
        self.store.atomic_write_json(path, payload)

    def load_snapshot(self, job_id: str) -> dict[str, Any] | None:
        path = self.store.job_snapshot_path(job_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def heartbeat_snapshot(
        self,
        record: JobRecord,
        *,
        clip_target: int | None = None,
        clip_observed: int | None = None,
        elapsed_seconds: int | None = None,
    ) -> dict[str, Any]:
        heartbeat_at = _now()
        payload = {
            **record.to_dict(),
            "heartbeat_at": heartbeat_at,
            "elapsed_seconds": elapsed_seconds,
            "clip_target": clip_target,
            "clip_observed": clip_observed,
            "thread_alive": True,
        }
        self.update(
            record.job_id,
            heartbeat_at=heartbeat_at,
            stale=False,
            stale_reason=None,
        )
        snapshot = self.load_snapshot(record.job_id) or {}
        snapshot.update(payload)
        self.write_snapshot(record.job_id, snapshot)
        return payload

    def evaluate_stale(
        self,
        record: JobRecord,
        *,
        stale_after_seconds: int,
    ) -> tuple[bool, str | None]:
        """Warning-only stale detection — never auto-fails the job."""
        if record.phase in TERMINAL_PHASES:
            return False, None
        heartbeat_at = record.heartbeat_at or record.accepted_at
        parsed = _parse_timestamp(heartbeat_at)
        if not parsed:
            return False, None
        age = (datetime.now() - parsed).total_seconds()
        if age > stale_after_seconds:
            reason = "HEARTBEAT_TIMEOUT"
            self.update(record.job_id, stale=True, stale_reason=reason)
            return True, reason
        return False, None


class JobAlreadyActiveError(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Active job already exists for session: {session_id}")


__all__ = [
    "REGISTRY_VERSION",
    "PHASE_JOB_ACCEPTED",
    "PHASE_PREFLIGHT_RUNNING",
    "PHASE_PREFLIGHT_PASSED",
    "PHASE_PREFLIGHT_FAILED",
    "PHASE_RUNNING",
    "PHASE_COMPLETED",
    "PHASE_FAILED",
    "TERMINAL_PHASES",
    "JobRecord",
    "RuntimeJobRegistry",
    "JobAlreadyActiveError",
]
