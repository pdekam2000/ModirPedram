"""
Seed Phase 10J operations demo sessions (preflight fail, worker dry-run, mode metadata).

No real provider execution — uses skip_provider_execution and skip_browser_probes.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from content_brain.execution.operations_policy import OperationsPolicy
from content_brain.execution.provider_preflight_validator import ProviderPreflightValidator
from content_brain.execution.runtime_worker_engine import RuntimeWorkerEngine
from content_brain.execution.seed_runtime_demo_sessions import _ready_dequeued_session
from content_brain.execution.session_store import ExecutionSessionStore


def _summary(session: dict[str, Any] | None, label: str, **extra: Any) -> dict[str, Any]:
    session = session or {}
    runtime = session.get("execution_runtime") or {}
    operations = runtime.get("operations") or {}
    telemetry = operations.get("cost_telemetry") or {}
    return {
        "label": label,
        "execution_session_id": session.get("execution_session_id"),
        "state": session.get("state"),
        "runtime_state": runtime.get("state"),
        "operations_phase": (operations.get("worker") or {}).get("phase"),
        "provider_execution_mode": operations.get("provider_execution_mode"),
        "provider_family": operations.get("provider_family"),
        "learning_key": operations.get("learning_key"),
        "preflight_passed": (operations.get("preflight") or {}).get("passed"),
        "validation_passed": (operations.get("validation") or {}).get("passed"),
        "cost_outcome": telemetry.get("outcome"),
        "schema": session.get("session_schema_version"),
        **extra,
    }


def _seed_mode_metadata_dequeued(store: ExecutionSessionStore) -> dict[str, Any]:
    session = _ready_dequeued_session(store, "exec_10j_ops_mode_browser", "mode_browser_ready")
    session["provider"] = "runway"
    session["provider_execution_mode"] = "browser"
    session["provider_selection"]["primary_provider"] = "runway"
    session["provider_selection"]["category_selections"] = {
        "video_generation": {"provider": "runway", "execution_mode": "browser"},
    }
    session["session_schema_version"] = "10j_v1"
    store.save_session(session, overwrite=True)
    return _summary(store.load_session("exec_10j_ops_mode_browser"), "mode_browser_dequeued")


def _seed_preflight_fail(store: ExecutionSessionStore) -> dict[str, Any]:
    session = _ready_dequeued_session(store, "exec_10j_ops_preflight_fail", "preflight_fail")
    session["provider"] = "hailuo"
    session["provider_execution_mode"] = "api"
    session["provider_selection"]["primary_provider"] = "hailuo"
    session["session_schema_version"] = "10j_v1"
    store.save_session(session, overwrite=True)

    validator = ProviderPreflightValidator(store)
    result = validator.validate(
        store.load_session("exec_10j_ops_preflight_fail"),
        OperationsPolicy(),
        execution_mode_override="api",
    )
    session = store.load_session("exec_10j_ops_preflight_fail")
    runtime = session.setdefault("execution_runtime", {})
    operations = runtime.setdefault("operations", {})
    operations["preflight"] = result.to_dict()
    operations["provider_execution_mode"] = result.provider_execution_mode
    operations["provider_family"] = result.provider_family
    operations["learning_key"] = result.learning_key
    if not result.passed:
        session["state"] = "FAILED"
        runtime["state"] = "FAILED"
        runtime["failure"] = {
            "code": result.reject_code or "PREFLIGHT_FAILED",
            "message": "; ".join(result.reject_reasons or []),
            "category": "PREFLIGHT_REJECT",
        }
    store.save_session(session, overwrite=True)
    return _summary(
        session,
        "preflight_fail",
        reject_code=result.reject_code,
        preflight_passed=result.passed,
    )


def _seed_worker_dry_run_completed(store: ExecutionSessionStore) -> dict[str, Any]:
    session = _ready_dequeued_session(store, "exec_10j_ops_worker_completed", "worker_completed")
    session["provider"] = "hailuo"
    session["provider_selection"]["primary_provider"] = "hailuo"
    session["session_schema_version"] = "10j_v1"
    store.save_session(session, overwrite=True)

    worker = RuntimeWorkerEngine(store)
    policy = OperationsPolicy(skip_provider_execution=True)
    submit = worker.submit(
        "exec_10j_ops_worker_completed",
        actor="seed",
        policy=policy,
        force_worker=True,
        skip_browser_probes=True,
    )
    if not submit.accepted:
        return _summary(None, "worker_dry_run_completed", reject_code=submit.reject_code)

    session_id = "exec_10j_ops_worker_completed"
    session = store.load_session(session_id)
    for _ in range(40):
        session = store.load_session(session_id)
        if session.get("state") in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.25)

    return _summary(
        session,
        "worker_dry_run_completed",
        dispatch_id=submit.dispatch_id,
        async_mode=submit.async_mode,
    )


def seed_operations_demo_sessions(project_root: str | Path = ".") -> list[dict[str, Any]]:
    store = ExecutionSessionStore(project_root)
    return [
        _seed_mode_metadata_dequeued(store),
        _seed_preflight_fail(store),
        _seed_worker_dry_run_completed(store),
    ]


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    for row in seed_operations_demo_sessions(root):
        print(row)
