"""Provider runtime operations for Execution Center API (10I sync + 10J async worker)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from content_brain.execution.category_runtime_compat import build_category_runtime_view
from content_brain.execution.operations_policy import OperationsPolicy
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.execution.runtime_job_registry import RuntimeJobRegistry, TERMINAL_PHASES
from content_brain.execution.runtime_worker_engine import RuntimeWorkerEngine
from content_brain.execution.session_store import ExecutionSessionStore

API_VERSION = "0.5.0"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _elapsed_seconds(start_at: str | None) -> int | None:
    parsed = _parse_timestamp(start_at)
    if not parsed:
        return None
    return max(0, int((datetime.now() - parsed).total_seconds()))


class RuntimeService:
    def __init__(self, store: ExecutionSessionStore):
        self._store = store
        self._engine = ProviderRuntimeEngine(store)
        self._worker = RuntimeWorkerEngine(store)
        self._registry = RuntimeJobRegistry(store)
        self._policy = OperationsPolicy()

    def dispatch(
        self,
        session_id: str,
        *,
        actor: str = "api",
        skip_provider_execution: bool = False,
    ) -> dict[str, Any]:
        policy = OperationsPolicy(skip_provider_execution=skip_provider_execution)

        if skip_provider_execution:
            return self._dispatch_sync(session_id, actor=actor, policy=policy)

        return self._dispatch_async(session_id, actor=actor, policy=policy)

    def _dispatch_sync(
        self,
        session_id: str,
        *,
        actor: str,
        policy: OperationsPolicy,
    ) -> dict[str, Any]:
        result = self._engine.dispatch_by_id(
            session_id,
            actor=actor,
            policy=policy.to_runtime_policy(),
        )
        session = result.session or {}
        return {
            "success": result.success,
            "accepted": result.success,
            "async_mode": False,
            "dispatch_mode": "sync",
            "session_id": session_id,
            "dispatch_id": _dict(session.get("execution_runtime")).get("dispatch_id"),
            "state": session.get("state"),
            "execution_runtime": session.get("execution_runtime"),
            "reject_code": result.reject_code,
            "reject_reasons": result.reject_reasons,
            "api_version": API_VERSION,
        }

    def _dispatch_async(
        self,
        session_id: str,
        *,
        actor: str,
        policy: OperationsPolicy,
    ) -> dict[str, Any]:
        submit = self._worker.submit(session_id, actor=actor, policy=policy)
        if not submit.accepted:
            return {
                "success": False,
                "accepted": False,
                "async_mode": True,
                "dispatch_mode": "async",
                "session_id": session_id,
                "dispatch_id": submit.dispatch_id,
                "state": None,
                "execution_runtime": None,
                "reject_code": submit.reject_code,
                "reject_reasons": submit.reject_reasons,
                "api_version": API_VERSION,
            }

        session = self._store.load_session(session_id)
        return {
            "success": True,
            "accepted": True,
            "async_mode": True,
            "dispatch_mode": "async",
            "session_id": session_id,
            "dispatch_id": submit.dispatch_id,
            "state": session.get("state"),
            "execution_runtime": session.get("execution_runtime"),
            "reject_code": None,
            "reject_reasons": [],
            "api_version": API_VERSION,
        }

    def status(self, session_id: str) -> dict[str, Any]:
        session = self._store.load_session(session_id)
        runtime = _dict(session.get("execution_runtime"))
        operations = _dict(runtime.get("operations"))
        worker = _dict(operations.get("worker"))
        artifacts = (runtime.get("artifacts_by_category") or {}).get("video_generation") or []

        dispatch_id = runtime.get("dispatch_id") or operations.get("job_id")
        active_job = self._registry.get_active_for_session(session_id)
        if active_job and not dispatch_id:
            dispatch_id = active_job.job_id

        stale_after = self._policy.stale_after_seconds
        stale = bool(worker.get("stale"))
        stale_reason = worker.get("stale_reason")
        heartbeat_at = worker.get("heartbeat_at") or (active_job.heartbeat_at if active_job else None)
        accepted_at = active_job.accepted_at if active_job else worker.get("started_at")

        if active_job:
            registry_stale, registry_reason = self._registry.evaluate_stale(
                active_job,
                stale_after_seconds=stale_after,
            )
            stale = stale or registry_stale
            stale_reason = stale_reason or registry_reason
            heartbeat_at = heartbeat_at or active_job.heartbeat_at

        elapsed = worker.get("elapsed_seconds")
        if elapsed is None:
            elapsed = _elapsed_seconds(accepted_at or runtime.get("running_at"))

        clip_target = self._clip_target(session)
        operations_phase = worker.get("phase") or (active_job.phase if active_job else None)
        job_active = active_job is not None
        if operations_phase in TERMINAL_PHASES:
            job_active = False

        job_block: dict[str, Any] = {
            "active": job_active,
            "phase": operations_phase,
            "dispatch_id": dispatch_id,
            "accepted_at": accepted_at,
            "heartbeat_at": heartbeat_at,
            "elapsed_seconds": elapsed,
            "stale": stale,
            "stale_reason": stale_reason,
            "stale_after_seconds": stale_after,
            "thread_alive": worker.get("thread_alive") if worker else (job_active or None),
            "provider_family": operations.get("provider_family") or (active_job.provider_family if active_job else None),
            "provider_execution_mode": operations.get("provider_execution_mode")
            or (active_job.provider_execution_mode if active_job else None),
            "cancellation_requested": bool(_dict(session.get("operations_control")).get("cancel_requested")),
            "cancellation": operations.get("cancellation"),
        }

        if session.get("state") == "CANCELLED" or runtime.get("state") == "CANCELLED":
            job_block["active"] = False
            job_block["stale"] = False
            job_block["stale_reason"] = None

        heartbeat_block: dict[str, Any] = {
            "heartbeat_at": heartbeat_at,
            "elapsed_seconds": elapsed,
            "stale": stale,
            "stale_reason": stale_reason,
            "stale_after_seconds": stale_after,
            "clip_target": clip_target,
            "clip_observed": None,
        }

        snapshot = self._registry.load_snapshot(str(dispatch_id)) if dispatch_id else None
        if snapshot and not heartbeat_at:
            heartbeat_block["heartbeat_at"] = snapshot.get("heartbeat_at")
            heartbeat_block["elapsed_seconds"] = snapshot.get("elapsed_seconds")

        preflight = operations.get("preflight")
        cost_telemetry = operations.get("cost_telemetry")
        validation = _dict(operations.get("validation"))
        clip_validated = validation.get("clip_valid")
        if clip_validated is None and validation.get("passed") is True:
            clip_validated = validation.get("clip_valid") or len(artifacts) if isinstance(artifacts, list) else 0

        return {
            "session_id": session_id,
            "state": session.get("state"),
            "category_runtime_slots": build_category_runtime_view(runtime),
            "runtime_state": runtime.get("state"),
            "provider_category": runtime.get("provider_category"),
            "provider_resolved": runtime.get("provider_resolved") or operations.get("provider_resolved"),
            "provider_family": operations.get("provider_family"),
            "provider_execution_mode": operations.get("provider_execution_mode"),
            "learning_key": operations.get("learning_key"),
            "operations_phase": operations_phase,
            "dispatch_id": dispatch_id,
            "dispatched_at": runtime.get("dispatched_at"),
            "running_at": runtime.get("running_at"),
            "completed_at": runtime.get("completed_at"),
            "clip_artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
            "failure": runtime.get("failure"),
            "preflight": preflight,
            "cost_telemetry": cost_telemetry,
            "job": job_block,
            "heartbeat": heartbeat_block,
            "progress": {
                "clip_target": clip_target,
                "clip_artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
                "clip_validated_count": int(clip_validated) if clip_validated is not None else 0,
            },
            "execution_runtime": runtime or None,
            "api_version": API_VERSION,
        }

    @staticmethod
    def _clip_target(session: dict[str, Any]) -> int | None:
        brief = _dict(session.get("brief_snapshot"))
        format_plan = _dict(brief.get("video_format_plan"))
        simulation = _dict(session.get("simulation_report"))
        try:
            value = int(format_plan.get("clip_count") or simulation.get("estimated_clip_count") or 0)
            return value or None
        except (TypeError, ValueError):
            return None
