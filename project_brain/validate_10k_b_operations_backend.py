"""
Phase 10K-b backend validation — operations control engine + API.
"""

from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from content_brain.execution.operations_control_engine import OperationsControlEngine
from content_brain.execution.runtime_job_registry import JobRecord, PHASE_RUNNING, RuntimeJobRegistry
from content_brain.execution.session_store import ExecutionSessionStore
from project_brain.validate_registry_cleanup import cleanup_validation_registry
from ui.api.main import app


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _write_session(store: ExecutionSessionStore, session: dict) -> None:
    store.save_session(session, overwrite=True)


def _load_template(root: Path, session_id: str) -> dict:
    path = root / "storage" / "content_brain" / "execution" / "sessions" / f"{session_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(session_id)


def _audit_count(store: ExecutionSessionStore) -> int:
    path = store.operations_audit_path
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    engine = OperationsControlEngine(store)
    registry = RuntimeJobRegistry(store)
    client = TestClient(app)
    results: list[dict] = []

    cleanup_validation_registry(store)

    audit_before = _audit_count(store)

    # --- eligibility: FAILED retry allowed ---
    failed = copy.deepcopy(_load_template(root, "exec_10j_ops_preflight_fail"))
    failed_id = "exec_10k_val_failed"
    failed["execution_session_id"] = failed_id
    failed["state"] = "FAILED"
    _write_session(store, failed)
    elig = engine.eligibility(failed_id)
    results.append(_pass("retry_allowed_FAILED", elig["actions"]["retry"]["allowed"] is True))

    # --- retry blocked RUNNING ---
    running = copy.deepcopy(_load_template(root, "exec_10jf_poll_running"))
    running_id = "exec_10k_val_running"
    running["execution_session_id"] = running_id
    running["state"] = "RUNNING"
    _write_session(store, running)
    registry.register(
        JobRecord(job_id="disp_10k_val_running", session_id=running_id, phase=PHASE_RUNNING)
    )
    try:
        elig_run = engine.eligibility(running_id)
        results.append(_pass("retry_blocked_RUNNING", elig_run["actions"]["retry"]["allowed"] is False))
        results.append(_pass("cancel_allowed_RUNNING_active_job", elig_run["actions"]["cancel"]["allowed"] is True))
    finally:
        registry.remove("disp_10k_val_running")

    # --- cancel blocked COMPLETED ---
    completed = copy.deepcopy(_load_template(root, "exec_10j_ops_worker_completed"))
    completed_id = "exec_10k_val_completed"
    completed["execution_session_id"] = completed_id
    completed["state"] = "COMPLETED"
    _write_session(store, completed)
    elig_done = engine.eligibility(completed_id)
    results.append(_pass("cancel_blocked_COMPLETED", elig_done["actions"]["cancel"]["allowed"] is False))
    results.append(_pass("archive_allowed_COMPLETED", elig_done["actions"]["archive"]["allowed"] is True))

    # --- cancel blocked FAILED ---
    elig_failed = engine.eligibility(failed_id)
    results.append(_pass("cancel_blocked_FAILED", elig_failed["actions"]["cancel"]["allowed"] is False))
    results.append(_pass("archive_allowed_FAILED", elig_failed["actions"]["archive"]["allowed"] is True))

    # --- archive blocked active RUNNING without saving duplicate ---
    running_no_job = copy.deepcopy(running)
    running_no_job["execution_session_id"] = "exec_10k_val_running_nojob"
    running_no_job["state"] = "RUNNING"
    _write_session(store, running_no_job)
    elig_no_job = engine.eligibility("exec_10k_val_running_nojob")
    results.append(_pass("archive_blocked_RUNNING", elig_no_job["actions"]["archive"]["allowed"] is False))
    results.append(_pass("cancel_blocked_RUNNING_no_job", elig_no_job["actions"]["cancel"]["allowed"] is False))

    # --- requeue allowed FAILED / blocked COMPLETED ---
    results.append(_pass("requeue_allowed_FAILED", elig_failed["actions"]["requeue"]["allowed"] is True))
    results.append(_pass("requeue_blocked_COMPLETED", elig_done["actions"]["requeue"]["allowed"] is False))

    cancelled = copy.deepcopy(failed)
    cancelled_id = "exec_10k_val_cancelled"
    cancelled["execution_session_id"] = cancelled_id
    cancelled["state"] = "CANCELLED"
    _write_session(store, cancelled)
    elig_cancel = engine.eligibility(cancelled_id)
    results.append(_pass("requeue_allowed_CANCELLED", elig_cancel["actions"]["requeue"]["allowed"] is True))
    results.append(_pass("archive_allowed_CANCELLED", elig_cancel["actions"]["archive"]["allowed"] is True))

    # --- legacy session eligibility ---
    legacy = engine.eligibility("exec_test_001")
    results.append(
        _pass(
            "legacy_eligibility_no_crash",
            legacy["current_state"] == "SIMULATED"
            and legacy["actions"]["retry"]["allowed"] is False,
        )
    )

    # --- retry action ---
    retry_result = engine.retry(failed_id, reason="validation retry")
    results.append(_pass("retry_action_ok", retry_result.ok is True and retry_result.next_state == "DEQUEUED"))
    refreshed_failed = store.load_session(failed_id)
    results.append(
        _pass(
            "retry_preserves_failure_history",
            bool((refreshed_failed.get("operations_control") or {}).get("attempt_history")),
        )
    )

    # --- archive action ---
    archive_result = engine.archive(completed_id, reason="validation archive")
    results.append(_pass("archive_action_ok", archive_result.ok is True))
    archived = store.load_session(completed_id)
    results.append(_pass("archive_sets_flag", bool((archived.get("operations_control") or {}).get("archived"))))

    # --- cancel with active job ---
    _write_session(store, running)
    registry.register(
        JobRecord(job_id="disp_10k_val_cancel", session_id=running_id, phase=PHASE_RUNNING)
    )
    try:
        cancel_result = engine.cancel(running_id, reason="validation cancel")
        session_after_cancel = store.load_session(running_id)
        results.append(
            _pass(
                "cancel_action_ok",
                cancel_result.ok is True and "requested" in (cancel_result.message or "").lower(),
            )
        )
        results.append(
            _pass(
                "cancel_sets_requested",
                bool((session_after_cancel.get("operations_control") or {}).get("cancel_requested")),
            )
        )
        results.append(
            _pass(
                "cancel_keeps_job_until_ack",
                registry.get_active_for_session(running_id) is not None,
            )
        )
    finally:
        registry.remove("disp_10k_val_cancel")

    # --- requeue action ---
    requeue_result = engine.requeue(cancelled_id, reason="validation requeue")
    results.append(_pass("requeue_action_ok", requeue_result.ok is True and requeue_result.next_state == "QUEUED"))

    # --- audit events written ---
    audit_after = _audit_count(store)
    results.append(_pass("audit_events_written", audit_after > audit_before))

    cancelled_session = store.load_session(cancelled_id)
    results.append(
        _pass(
            "session_operations_audit_log",
            len(cancelled_session.get("operations_audit_log") or []) >= 1,
        )
    )

    # --- no provider dispatch import/call in engine module ---
    module_path = Path(inspect.getfile(OperationsControlEngine)).read_text(encoding="utf-8")
    results.append(
        _pass(
            "no_provider_dispatch_in_engine",
            "from content_brain.execution.provider_runtime_engine" not in module_path
            and "dispatch_by_id(" not in module_path
            and ".dispatch(" not in module_path,
        )
    )

    with patch("content_brain.execution.provider_runtime_engine.ProviderRuntimeEngine.dispatch_by_id") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("Provider dispatch must not be called")
        engine.retry(failed_id, reason="no dispatch check")
        results.append(_pass("retry_does_not_dispatch", True))

    # --- API endpoints ---
    api_archive_session = copy.deepcopy(_load_template(root, "exec_10j_ops_preflight_fail"))
    api_archive_session["execution_session_id"] = "exec_10k_val_api_archive"
    api_archive_session["state"] = "FAILED"
    _write_session(store, api_archive_session)

    api_elig = client.get("/sessions/exec_test_001/actions/eligibility")
    results.append(_pass("api_eligibility_200", api_elig.status_code == 200))
    results.append(_pass("api_version_0.6.0", client.get("/health").json().get("version") == "0.6.0"))

    api_archive = client.post(
        "/sessions/exec_10k_val_api_archive/actions/archive",
        json={"reason": "api archive test", "actor": "validate"},
    )
    results.append(_pass("api_archive_ok", api_archive.status_code == 200 and api_archive.json().get("ok") is True))

    api_retry_block = client.post(
        "/sessions/exec_10k_val_running/actions/retry",
        json={"reason": "should block", "actor": "validate"},
    )
    results.append(_pass("api_retry_blocked_409", api_retry_block.status_code == 409))

    api_cancel_no_reason = client.post(
        "/sessions/exec_10k_val_running_nojob/actions/cancel",
        json={"reason": "", "actor": "validate"},
    )
    results.append(_pass("api_cancel_reason_required_400", api_cancel_no_reason.status_code == 400))

    cleanup_validation_registry(store)

    passed = sum(1 for item in results if item["pass"])
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_pass": passed == len(results),
        },
    }


if __name__ == "__main__":
    report = run_matrix(".")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
