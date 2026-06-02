"""
Phase 10J-c — background worker with preflight gate, heartbeat, and cost telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import threading
import time
from typing import Any

from content_brain.execution.cost_telemetry import (
    OUTCOME_CANCELLED,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_PREFLIGHT_FAILED,
    finalize_cost_telemetry,
    init_cost_telemetry,
)
from content_brain.execution.operations_cancel import (
    CANCEL_REJECT_CODE,
    PHASE_CANCELLATION_REQUESTED,
    STATE_CANCELLED,
    is_cancellation_requested,
)
from content_brain.execution.operations_policy import OperationsPolicy
from content_brain.execution.provider_mode_router import ProviderModeRouter
from content_brain.execution.provider_preflight_validator import ProviderPreflightValidator
from content_brain.execution.provider_runtime_engine import (
    ProviderRuntimeEngine,
    generate_audit_event_id,
    generate_dispatch_id,
)
from content_brain.execution.runtime_job_registry import (
    JobAlreadyActiveError,
    JobRecord,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_JOB_ACCEPTED,
    PHASE_PREFLIGHT_FAILED,
    PHASE_PREFLIGHT_PASSED,
    PHASE_PREFLIGHT_RUNNING,
    PHASE_RUNNING,
    RuntimeJobRegistry,
)
from content_brain.execution.session_store import ExecutionSessionStore

ENGINE_NAME = "RuntimeWorkerEngine"
ENGINE_VERSION = "10j_v1"
OPERATIONS_VERSION = "10j_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _elapsed_seconds(start_at: str | None) -> int | None:
    if not start_at:
        return None
    try:
        start = datetime.strptime(start_at, TIMESTAMP_FORMAT)
    except ValueError:
        return None
    return max(0, int((datetime.now() - start).total_seconds()))


@dataclass
class WorkerSubmitResult:
    accepted: bool
    session_id: str
    dispatch_id: str | None = None
    async_mode: bool = False
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    session: dict[str, Any] | None = None


class RuntimeWorkerEngine:
    """
    Background job lifecycle shell around ProviderRuntimeEngine.

    Dry-run (`skip_provider_execution=True`) stays synchronous unless `force_worker=True`.
    """

    def __init__(self, store: ExecutionSessionStore):
        self.store = store
        self.registry = RuntimeJobRegistry(store)
        self.runtime = ProviderRuntimeEngine(store)
        self.preflight = ProviderPreflightValidator(store)
        self.mode_router = ProviderModeRouter(project_root=store.project_root)
        self._session_locks: dict[str, threading.Lock] = {}
        self._lock_guard = threading.Lock()

    def submit(
        self,
        session_id: str,
        *,
        actor: str = "system",
        policy: OperationsPolicy | None = None,
        force_worker: bool = False,
        skip_browser_probes: bool = False,
        skip_api_connectivity: bool = False,
        execution_mode_override: str | None = None,
    ) -> WorkerSubmitResult:
        policy = policy or OperationsPolicy()
        if policy.skip_provider_execution and not force_worker:
            return self._submit_sync(
                session_id,
                actor=actor,
                policy=policy,
            )

        try:
            session = self.store.load_session(session_id)
        except FileNotFoundError:
            return WorkerSubmitResult(
                accepted=False,
                session_id=session_id,
                reject_code="NOT_FOUND",
                reject_reasons=[f"Session not found: {session_id}"],
            )

        ok, reasons, code = self.runtime.validate_dispatch_eligibility(
            session,
            policy.to_runtime_policy(),
        )
        if not ok:
            return WorkerSubmitResult(
                accepted=False,
                session_id=session_id,
                reject_code=code,
                reject_reasons=reasons,
            )

        if self.registry.get_active_for_session(session_id):
            return WorkerSubmitResult(
                accepted=False,
                session_id=session_id,
                reject_code="JOB_ALREADY_ACTIVE",
                reject_reasons=[f"Active job already exists for session {session_id}."],
            )

        dispatch_id = generate_dispatch_id()
        resolution = self.mode_router.resolve(session, execution_mode_override=execution_mode_override)
        record = JobRecord(
            job_id=dispatch_id,
            session_id=session_id,
            phase=PHASE_JOB_ACCEPTED,
            provider_family=resolution.provider_family if resolution else None,
            provider_execution_mode=resolution.provider_execution_mode if resolution else None,
            provider_resolved=resolution.router_key if resolution else None,
            learning_key=resolution.learning_key if resolution else None,
            accepted_at=_now(),
        )
        try:
            self.registry.register(record)
        except JobAlreadyActiveError:
            return WorkerSubmitResult(
                accepted=False,
                session_id=session_id,
                reject_code="JOB_ALREADY_ACTIVE",
                reject_reasons=[f"Active job already exists for session {session_id}."],
            )

        worker = threading.Thread(
            target=self._run_worker,
            name=f"runtime-worker-{dispatch_id}",
            daemon=True,
            kwargs={
                "session_id": session_id,
                "dispatch_id": dispatch_id,
                "actor": actor,
                "policy": policy,
                "skip_browser_probes": skip_browser_probes,
                "skip_api_connectivity": skip_api_connectivity,
                "execution_mode_override": execution_mode_override,
            },
        )
        worker.start()
        return WorkerSubmitResult(
            accepted=True,
            session_id=session_id,
            dispatch_id=dispatch_id,
            async_mode=True,
        )

    def _submit_sync(
        self,
        session_id: str,
        *,
        actor: str,
        policy: OperationsPolicy,
    ) -> WorkerSubmitResult:
        result = self.runtime.dispatch_by_id(
            session_id,
            actor=actor,
            policy=policy.to_runtime_policy(),
        )
        session = result.session or {}
        return WorkerSubmitResult(
            accepted=result.success,
            session_id=session_id,
            dispatch_id=_dict(session.get("execution_runtime")).get("dispatch_id"),
            async_mode=False,
            reject_code=result.reject_code,
            reject_reasons=result.reject_reasons,
            session=session,
        )

    def _run_worker(
        self,
        *,
        session_id: str,
        dispatch_id: str,
        actor: str,
        policy: OperationsPolicy,
        skip_browser_probes: bool,
        skip_api_connectivity: bool,
        execution_mode_override: str | None,
    ) -> None:
        stop_heartbeat = threading.Event()
        heartbeat_thread: threading.Thread | None = None
        telemetry_start = _now()
        outcome = OUTCOME_FAILED

        try:
            session = self.store.load_session(session_id)
            resolution = self.mode_router.resolve(session, execution_mode_override=execution_mode_override)
            if not resolution:
                self._fail_preflight(
                    session_id=session_id,
                    dispatch_id=dispatch_id,
                    actor=actor,
                    policy=policy,
                    preflight_result=None,
                    reject_code="INVALID_PROVIDER",
                    reasons=["Could not resolve provider family/mode."],
                    telemetry_start=telemetry_start,
                )
                return

            operations = self._build_operations(
                dispatch_id=dispatch_id,
                resolution=resolution,
                policy=policy,
                phase=PHASE_JOB_ACCEPTED,
            )
            operations["cost_telemetry"] = init_cost_telemetry(
                session=session,
                resolution=resolution,
                dispatch_id=dispatch_id,
                start_time=telemetry_start,
            )
            session = self._merge_operations(session, operations)
            self._audit(
                session,
                "JOB_ACCEPTED",
                actor,
                dispatch_id,
                {
                    "provider_family": resolution.provider_family,
                    "provider_execution_mode": resolution.provider_execution_mode,
                    "learning_key": resolution.learning_key,
                },
            )
            self._audit(
                session,
                "MODE_RESOLVED",
                actor,
                dispatch_id,
                resolution.to_dict(),
            )
            self.store.save_session(session, overwrite=True)

            if self._cancellation_requested(session_id):
                self._cooperative_cancel_worker(
                    session_id=session_id,
                    dispatch_id=dispatch_id,
                    actor=actor,
                    telemetry_start=telemetry_start,
                )
                return

            self.registry.update(
                dispatch_id,
                phase=PHASE_PREFLIGHT_RUNNING,
                thread_id=threading.get_ident(),
            )
            session = self._set_worker_phase(session, PHASE_PREFLIGHT_RUNNING)
            self.store.save_session(session, overwrite=True)

            if self._cancellation_requested(session_id):
                self._cooperative_cancel_worker(
                    session_id=session_id,
                    dispatch_id=dispatch_id,
                    actor=actor,
                    telemetry_start=telemetry_start,
                )
                return

            active_browser_jobs = self.registry.count_active_browser_jobs()
            preflight = self.preflight.validate(
                session,
                policy,
                execution_mode_override=execution_mode_override,
                skip_browser_probes=skip_browser_probes,
                skip_api_connectivity=skip_api_connectivity,
                active_browser_jobs=active_browser_jobs,
            )
            session = self.store.load_session(session_id)
            operations = _dict(_dict(session.get("execution_runtime")).get("operations"))
            operations["preflight"] = preflight.to_dict()
            session = self._merge_operations(session, operations)

            if not preflight.passed:
                self._fail_preflight(
                    session_id=session_id,
                    dispatch_id=dispatch_id,
                    actor=actor,
                    policy=policy,
                    preflight_result=preflight,
                    reject_code=preflight.reject_code or "PREFLIGHT_FAILED",
                    reasons=preflight.reject_reasons or ["Preflight failed."],
                    telemetry_start=telemetry_start,
                    session=session,
                )
                return

            self.registry.update(dispatch_id, phase=PHASE_PREFLIGHT_PASSED)
            session = self._set_worker_phase(session, PHASE_PREFLIGHT_PASSED)
            self._audit(
                session,
                "PREFLIGHT_PASSED",
                actor,
                dispatch_id,
                {
                    "provider_execution_mode": preflight.provider_execution_mode,
                    "learning_key": preflight.learning_key,
                    "checks_passed": len(preflight.checks),
                },
            )
            session = self._apply_provider_resolution(session, preflight)
            self.store.save_session(session, overwrite=True)

            if self._cancellation_requested(session_id):
                self._cooperative_cancel_worker(
                    session_id=session_id,
                    dispatch_id=dispatch_id,
                    actor=actor,
                    telemetry_start=telemetry_start,
                )
                return

            self.registry.update(dispatch_id, phase=PHASE_RUNNING)
            session = self._set_worker_phase(session, PHASE_RUNNING)
            self.store.save_session(session, overwrite=True)

            clip_target = self._clip_target(session)
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name=f"runtime-heartbeat-{dispatch_id}",
                daemon=True,
                kwargs={
                    "session_id": session_id,
                    "dispatch_id": dispatch_id,
                    "policy": policy,
                    "clip_target": clip_target,
                    "stop_event": stop_heartbeat,
                },
            )
            heartbeat_thread.start()

            if self._cancellation_requested(session_id):
                stop_heartbeat.set()
                if heartbeat_thread.is_alive():
                    heartbeat_thread.join(timeout=2.0)
                self._cooperative_cancel_worker(
                    session_id=session_id,
                    dispatch_id=dispatch_id,
                    actor=actor,
                    telemetry_start=telemetry_start,
                )
                return

            dispatch_result = self.runtime.dispatch_by_id(
                session_id,
                actor=actor,
                policy=policy.to_runtime_policy(),
                dispatch_id=dispatch_id,
            )
            stop_heartbeat.set()
            if heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=2.0)

            session = dispatch_result.session or self.store.load_session(session_id)
            operations = _dict(_dict(session.get("execution_runtime")).get("operations"))
            operations.setdefault("cost_telemetry", init_cost_telemetry(
                session=session,
                resolution=resolution,
                dispatch_id=dispatch_id,
                start_time=telemetry_start,
            ))

            if dispatch_result.reject_code == CANCEL_REJECT_CODE:
                outcome = OUTCOME_CANCELLED
                if not operations.get("cancellation"):
                    operations = self._set_worker_phase_dict(operations, STATE_CANCELLED)
            elif dispatch_result.success:
                outcome = OUTCOME_COMPLETED
                operations = self._set_worker_phase_dict(operations, PHASE_COMPLETED)
                self._audit(
                    session,
                    "COMPLETED",
                    actor,
                    dispatch_id,
                    {"worker": True, "provider_execution_mode": preflight.provider_execution_mode},
                )
            else:
                outcome = OUTCOME_FAILED
                operations = self._set_worker_phase_dict(operations, PHASE_FAILED)
                self._audit(
                    session,
                    "FAILED",
                    actor,
                    dispatch_id,
                    {
                        "code": dispatch_result.reject_code,
                        "reasons": dispatch_result.reject_reasons,
                        "provider_execution_mode": preflight.provider_execution_mode,
                    },
                )

            operations["cost_telemetry"] = finalize_cost_telemetry(
                operations["cost_telemetry"],
                outcome=outcome,
            )
            session = self._merge_operations(session, operations)
            if dispatch_result.reject_code != CANCEL_REJECT_CODE:
                self._audit(
                    session,
                    "COST_TELEMETRY_RECORDED",
                    actor,
                    dispatch_id,
                    {"cost_telemetry": operations["cost_telemetry"]},
                )
                self._audit(session, "JOB_FINALIZED", actor, dispatch_id, {"phase": operations["worker"]["phase"]})
            else:
                self._audit(
                    session,
                    "COST_TELEMETRY_RECORDED",
                    actor,
                    dispatch_id,
                    {"cost_telemetry": operations["cost_telemetry"]},
                )
                self._audit(session, "JOB_FINALIZED", actor, dispatch_id, {"phase": STATE_CANCELLED})
            self.store.save_session(session, overwrite=True)
            terminal_phase = STATE_CANCELLED if dispatch_result.reject_code == CANCEL_REJECT_CODE else operations["worker"]["phase"]
            self.registry.finalize(
                dispatch_id,
                phase=terminal_phase,
                terminal_snapshot={
                    "session_id": session_id,
                    "outcome": outcome,
                    "cost_telemetry": operations["cost_telemetry"],
                    "runtime_state": _dict(session.get("execution_runtime")).get("state"),
                },
            )
        except Exception as exc:
            stop_heartbeat.set()
            if heartbeat_thread and heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=2.0)
            try:
                session = self.store.load_session(session_id)
            except Exception:
                session = {"execution_session_id": session_id}
            self._mark_worker_failed(
                session,
                dispatch_id=dispatch_id,
                actor=actor,
                code="PROVIDER_RUNTIME_ERROR",
                reasons=[str(exc)],
                telemetry_start=telemetry_start,
            )
            self.registry.finalize(dispatch_id, phase=PHASE_FAILED)

    def _fail_preflight(
        self,
        *,
        session_id: str,
        dispatch_id: str,
        actor: str,
        policy: OperationsPolicy,
        preflight_result: Any,
        reject_code: str,
        reasons: list[str],
        telemetry_start: str,
        session: dict[str, Any] | None = None,
    ) -> None:
        session = session or self.store.load_session(session_id)
        timestamp = _now()
        operations = _dict(_dict(session.get("execution_runtime")).get("operations"))
        operations = self._set_worker_phase_dict(operations, PHASE_PREFLIGHT_FAILED)
        if preflight_result is not None:
            operations["preflight"] = preflight_result.to_dict()

        resolution = self.mode_router.resolve(session)
        telemetry = operations.get("cost_telemetry")
        if not telemetry:
            if resolution:
                telemetry = init_cost_telemetry(
                    session=session,
                    resolution=resolution,
                    dispatch_id=dispatch_id,
                    start_time=telemetry_start,
                )
            else:
                telemetry = {"dispatch_id": dispatch_id, "start_time": telemetry_start}
        operations["cost_telemetry"] = finalize_cost_telemetry(
            telemetry,
            outcome=OUTCOME_PREFLIGHT_FAILED,
            end_time=timestamp,
        )

        runtime = _dict(session.get("execution_runtime"))
        runtime["operations"] = operations
        runtime["state"] = "FAILED"
        runtime["failure"] = {
            "code": reject_code,
            "message": "; ".join(reasons),
            "failed_at": timestamp,
            "category": "PREFLIGHT_REJECT",
        }
        session["execution_runtime"] = runtime
        session["state"] = "FAILED"
        session["updated_at"] = timestamp
        session["session_schema_version"] = "10j_v1"
        self._append_state_history(session, "FAILED", timestamp, f"preflight failed: {reject_code}")
        self._audit(
            session,
            "PREFLIGHT_FAILED",
            actor,
            dispatch_id,
            {
                "code": reject_code,
                "reasons": reasons,
                "provider_execution_mode": operations.get("provider_execution_mode"),
            },
        )
        self._audit(
            session,
            "COST_TELEMETRY_RECORDED",
            actor,
            dispatch_id,
            {"cost_telemetry": operations["cost_telemetry"]},
        )
        self._audit(session, "JOB_FINALIZED", actor, dispatch_id, {"phase": PHASE_PREFLIGHT_FAILED})
        self.store.save_session(session, overwrite=True)
        self.registry.finalize(
            dispatch_id,
            phase=PHASE_PREFLIGHT_FAILED,
            terminal_snapshot={
                "session_id": session_id,
                "reject_code": reject_code,
                "cost_telemetry": operations["cost_telemetry"],
            },
        )

    def _mark_worker_failed(
        self,
        session: dict[str, Any],
        *,
        dispatch_id: str,
        actor: str,
        code: str,
        reasons: list[str],
        telemetry_start: str,
    ) -> None:
        session_id = ExecutionSessionStore.extract_session_id(session)
        timestamp = _now()
        operations = _dict(_dict(session.get("execution_runtime")).get("operations"))
        operations = self._set_worker_phase_dict(operations, PHASE_FAILED)
        telemetry = operations.get("cost_telemetry") or {"dispatch_id": dispatch_id, "start_time": telemetry_start}
        operations["cost_telemetry"] = finalize_cost_telemetry(
            telemetry,
            outcome=OUTCOME_FAILED,
            end_time=timestamp,
        )
        runtime = _dict(session.get("execution_runtime"))
        runtime["operations"] = operations
        runtime["state"] = "FAILED"
        runtime["failure"] = {
            "code": code,
            "message": "; ".join(reasons),
            "failed_at": timestamp,
        }
        session["execution_runtime"] = runtime
        session["state"] = "FAILED"
        session["updated_at"] = timestamp
        self._audit(session, "FAILED", actor, dispatch_id, {"code": code, "reasons": reasons})
        self._audit(
            session,
            "COST_TELEMETRY_RECORDED",
            actor,
            dispatch_id,
            {"cost_telemetry": operations["cost_telemetry"]},
        )
        self.store.save_session(session, overwrite=True)
        self.registry.finalize(
            dispatch_id,
            phase=PHASE_FAILED,
            terminal_snapshot={"session_id": session_id, "reject_code": code},
        )

    def _heartbeat_loop(
        self,
        *,
        session_id: str,
        dispatch_id: str,
        policy: OperationsPolicy,
        clip_target: int | None,
        stop_event: threading.Event,
    ) -> None:
        tick = 0
        record = JobRecord(job_id=dispatch_id, session_id=session_id, phase=PHASE_RUNNING)
        while not stop_event.wait(policy.heartbeat_interval_seconds):
            tick += 1
            active = self.registry.get_active_for_session(session_id)
            if active:
                record = active
            stale, stale_reason = self.registry.evaluate_stale(
                record,
                stale_after_seconds=policy.stale_after_seconds,
            )
            elapsed = _elapsed_seconds(record.accepted_at)
            self.registry.heartbeat_snapshot(
                record,
                clip_target=clip_target,
                clip_observed=None,
                elapsed_seconds=elapsed,
            )

            with self._session_lock(session_id):
                try:
                    session = self.store.load_session(session_id)
                except Exception:
                    continue
                operations = _dict(_dict(session.get("execution_runtime")).get("operations"))
                worker = _dict(operations.get("worker"))
                worker["phase"] = PHASE_RUNNING
                worker["heartbeat_at"] = _now()
                worker["thread_alive"] = True
                worker["stale"] = stale
                worker["stale_reason"] = stale_reason
                worker["elapsed_seconds"] = elapsed
                operations["worker"] = worker
                session = self._merge_operations(session, operations)
                self.store.save_session(session, overwrite=True)

            if tick % 4 == 0:
                try:
                    session = self.store.load_session(session_id)
                    self._audit(
                        session,
                        "HEARTBEAT",
                        "worker",
                        dispatch_id,
                        {
                            "elapsed_seconds": elapsed,
                            "stale": stale,
                            "clip_target": clip_target,
                        },
                    )
                    self.store.save_session(session, overwrite=True)
                except Exception:
                    pass

    def _build_operations(
        self,
        *,
        dispatch_id: str,
        resolution: Any,
        policy: OperationsPolicy,
        phase: str,
    ) -> dict[str, Any]:
        timestamp = _now()
        return {
            "operations_version": OPERATIONS_VERSION,
            "job_id": dispatch_id,
            "dispatch_mode": "async",
            "provider_family": resolution.provider_family,
            "provider_execution_mode": resolution.provider_execution_mode,
            "provider_resolved": resolution.router_key,
            "learning_key": resolution.learning_key,
            "router_key": resolution.router_key,
            "worker": {
                "engine": ENGINE_NAME,
                "engine_version": ENGINE_VERSION,
                "started_at": timestamp,
                "heartbeat_at": timestamp,
                "phase": phase,
                "thread_alive": True,
                "stale": False,
                "stale_reason": None,
            },
            "preflight": None,
            "validation": {"validated_at": None, "passed": None, "checks": []},
            "timing": {
                "preflight_ms": None,
                "provider_ms": None,
                "validation_ms": None,
                "total_ms": None,
            },
            "policy_snapshot": policy.snapshot(),
        }

    def _merge_operations(self, session: dict[str, Any], operations: dict[str, Any]) -> dict[str, Any]:
        session = dict(session)
        runtime = dict(_dict(session.get("execution_runtime")))
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return session

    def _set_worker_phase(self, session: dict[str, Any], phase: str) -> dict[str, Any]:
        operations = _dict(_dict(session.get("execution_runtime")).get("operations"))
        operations = self._set_worker_phase_dict(operations, phase)
        return self._merge_operations(session, operations)

    @staticmethod
    def _set_worker_phase_dict(operations: dict[str, Any], phase: str) -> dict[str, Any]:
        merged = dict(operations)
        worker = dict(_dict(merged.get("worker")))
        worker["phase"] = phase
        worker["heartbeat_at"] = _now()
        worker["thread_alive"] = phase == PHASE_RUNNING
        merged["worker"] = worker
        return merged

    @staticmethod
    def _apply_provider_resolution(session: dict[str, Any], preflight: Any) -> dict[str, Any]:
        session = dict(session)
        router_key = preflight.provider_resolved
        if not router_key:
            return session
        session["provider"] = router_key
        provider_selection = dict(_dict(session.get("provider_selection")))
        provider_selection["primary_provider"] = router_key
        category_selections = dict(_dict(provider_selection.get("category_selections")))
        video_sel = dict(_dict(category_selections.get("video_generation")))
        video_sel["provider"] = router_key
        category_selections["video_generation"] = video_sel
        provider_selection["category_selections"] = category_selections
        session["provider_selection"] = provider_selection
        return session

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

    def _cancellation_requested(self, session_id: str) -> bool:
        try:
            session = self.store.load_session(session_id)
        except FileNotFoundError:
            return False
        return is_cancellation_requested(session)

    def _cooperative_cancel_worker(
        self,
        *,
        session_id: str,
        dispatch_id: str,
        actor: str,
        telemetry_start: str,
    ) -> None:
        session = self.store.load_session(session_id)
        runtime = _dict(session.get("execution_runtime"))
        session = self.runtime._mark_cooperative_cancelled(
            session,
            actor=actor,
            dispatch_id=dispatch_id,
            execution_runtime=runtime,
            partial_clip_paths=[],
        )
        operations = _dict(_dict(session.get("execution_runtime")).get("operations"))
        resolution = self.mode_router.resolve(session)
        telemetry = operations.get("cost_telemetry")
        if not telemetry and resolution:
            telemetry = init_cost_telemetry(
                session=session,
                resolution=resolution,
                dispatch_id=dispatch_id,
                start_time=telemetry_start,
            )
        elif not telemetry:
            telemetry = {"dispatch_id": dispatch_id, "start_time": telemetry_start}
        operations["cost_telemetry"] = finalize_cost_telemetry(
            telemetry,
            outcome=OUTCOME_CANCELLED,
            end_time=_now(),
        )
        session = self._merge_operations(session, operations)
        self._audit(
            session,
            "WORKER_CANCELLED",
            actor,
            dispatch_id,
            _dict(operations.get("cancellation")),
        )
        self._audit(
            session,
            "COST_TELEMETRY_RECORDED",
            actor,
            dispatch_id,
            {"cost_telemetry": operations["cost_telemetry"]},
        )
        self._audit(session, "JOB_FINALIZED", actor, dispatch_id, {"phase": STATE_CANCELLED})
        self.store.save_session(session, overwrite=True)
        self.registry.finalize(
            dispatch_id,
            phase=STATE_CANCELLED,
            terminal_snapshot={
                "session_id": session_id,
                "outcome": OUTCOME_CANCELLED,
                "cost_telemetry": operations["cost_telemetry"],
                "runtime_state": STATE_CANCELLED,
            },
        )

    def _session_lock(self, session_id: str) -> threading.Lock:
        with self._lock_guard:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[session_id] = lock
            return lock

    def _audit(
        self,
        session: dict[str, Any],
        event_type: str,
        actor: str,
        dispatch_id: str,
        details: dict[str, Any],
    ) -> None:
        event = {
            "event_id": generate_audit_event_id(),
            "event_type": event_type,
            "at": _now(),
            "dispatch_id": dispatch_id,
            "actor": actor,
            "details": details,
        }
        audit_log = list(session.get("provider_audit_log") or [])
        audit_log.append(event)
        session["provider_audit_log"] = audit_log
        self.store.append_global_provider_audit(
            {
                **event,
                "execution_session_id": ExecutionSessionStore.extract_session_id(session),
                "session_uuid": session.get("session_uuid"),
            }
        )

    @staticmethod
    def _append_state_history(session: dict[str, Any], state: str, timestamp: str, reason: str) -> None:
        history = list(session.get("state_history") or [])
        history.append({"at": timestamp, "state": state, "reason": reason})
        session["state_history"] = history


__all__ = [
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "RuntimeWorkerEngine",
    "WorkerSubmitResult",
]
