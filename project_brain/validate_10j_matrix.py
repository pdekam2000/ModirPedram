"""
Phase 10J full validation matrix (10J-a through 10J-f).

Validation and documentation support only — no runtime feature changes.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from content_brain.execution.artifact_validation_engine import ArtifactValidationEngine
from content_brain.execution.cost_telemetry import finalize_cost_telemetry, init_cost_telemetry
from content_brain.execution.failure_taxonomy import classify_failure, is_retriable
from content_brain.execution.operations_policy import OperationsPolicy
from content_brain.execution.provider_mode_catalog import ProviderModeCatalog
from content_brain.execution.provider_mode_router import ProviderModeRouter
from content_brain.execution.provider_preflight_validator import ProviderPreflightValidator
from content_brain.execution.runtime_job_registry import RuntimeJobRegistry
from content_brain.execution.runtime_worker_engine import RuntimeWorkerEngine
from content_brain.execution.seed_operations_demo_sessions import seed_operations_demo_sessions
from content_brain.execution.seed_runtime_demo_sessions import seed_runtime_demo_sessions
from content_brain.execution.session_store import ExecutionSessionStore
from project_brain.validate_registry_cleanup import cleanup_validation_registry
from ui.api.main import app


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "phase": name.split("_")[0], "pass": ok, "detail": detail}


def validate_10j_a() -> list[dict]:
    results = []
    meta = classify_failure("BROWSER_UNAVAILABLE")
    results.append(_pass("10J-a_taxonomy", meta["category"] == "PREFLIGHT_REJECT" and is_retriable("BROWSER_UNAVAILABLE")))
    catalog = ProviderModeCatalog.load(".")
    resolution = catalog.resolve("runway", "browser")
    results.append(_pass("10J-a_catalog_runway_browser", resolution is not None and resolution.router_key == "runway_browser"))
    if resolution:
        block = init_cost_telemetry(session={}, resolution=resolution, dispatch_id="disp_test")
        final = finalize_cost_telemetry(block, outcome="COMPLETED")
        results.append(_pass("10J-a_cost_telemetry", final.get("outcome") == "COMPLETED" and final.get("duration_seconds") is not None))
    else:
        results.append(_pass("10J-a_cost_telemetry", False, "no resolution"))
    return results


def validate_10j_b(store: ExecutionSessionStore) -> list[dict]:
    results = []
    router = ProviderModeRouter(project_root=store.project_root)
    session = store.load_session("exec_10j_ops_mode_browser")
    resolution = router.resolve(session)
    results.append(_pass("10J-b_mode_router", resolution is not None and resolution.provider_execution_mode == "browser"))
    preflight = ProviderPreflightValidator(store).validate(
        store.load_session("exec_10i_dequeued_demo"),
        OperationsPolicy(),
        skip_browser_probes=True,
    )
    results.append(_pass("10J-b_preflight_pass", preflight.passed is True))
    api_fail = ProviderPreflightValidator(store).validate(
        {"provider": "hailuo", "provider_selection": {"primary_provider": "hailuo"}},
        OperationsPolicy(),
        execution_mode_override="api",
    )
    results.append(_pass("10J-b_preflight_hailuo_api_fail", api_fail.passed is False and api_fail.reject_code == "PROVIDER_NOT_IMPLEMENTED"))
    return results


def validate_10j_c(store: ExecutionSessionStore) -> list[dict]:
    results = []
    worker = RuntimeWorkerEngine(store)
    registry = RuntimeJobRegistry(store)
    from content_brain.execution.runtime_job_registry import JobRecord, PHASE_RUNNING

    cleanup_validation_registry(store, extra_session_ids=("exec_10i_dequeued_demo",))
    registry.register(
        JobRecord(job_id="disp_validate_active", session_id="exec_10i_dequeued_demo", phase=PHASE_RUNNING)
    )
    try:
        dup = worker.submit(
            "exec_10i_dequeued_demo",
            policy=OperationsPolicy(skip_provider_execution=True),
            force_worker=True,
            skip_browser_probes=True,
        )
        results.append(_pass("10J-c_job_already_active", dup.reject_code == "JOB_ALREADY_ACTIVE"))
    finally:
        registry.remove("disp_validate_active")
        cleanup_validation_registry(store, extra_session_ids=("exec_10i_dequeued_demo",))
    session = store.load_session("exec_10j_ops_worker_completed")
    ops = (session.get("execution_runtime") or {}).get("operations") or {}
    telemetry = ops.get("cost_telemetry") or {}
    results.append(_pass("10J-c_worker_telemetry", session.get("state") == "COMPLETED" and telemetry.get("outcome") == "COMPLETED"))
    results.append(_pass("10J-c_active_jobs_clean", len(RuntimeJobRegistry(store).list_active()) == 0))
    return results


def validate_10j_d() -> list[dict]:
    client = TestClient(app)
    results = []
    seed_runtime_demo_sessions(".")
    dry = client.post("/sessions/exec_10i_dequeued_demo/runtime/dispatch", json={"skip_provider_execution": True})
    results.append(_pass("10J-d_dry_run_200", dry.status_code == 200))
    seed_runtime_demo_sessions(".")
    async_resp = client.post("/sessions/exec_10i_dequeued_demo/runtime/dispatch", json={"skip_provider_execution": False})
    results.append(_pass("10J-d_async_202", async_resp.status_code == 202))
    st: dict = {}
    for _ in range(30):
        st = client.get("/sessions/exec_10i_dequeued_demo/runtime/status").json()
        if st.get("state") in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.25)
    results.append(_pass("10J-d_status_enriched", isinstance(st.get("job"), dict) and st.get("api_version") == "0.5.0"))
    results.append(_pass("10J-d_health_0.5", client.get("/health").json().get("version") == "0.6.0"))
    return results


def validate_10j_e() -> list[dict]:
    engine = ArtifactValidationEngine()
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "clip_01.mock"
        path.write_text("mock artifact for validation")
        ok = engine.validate([{"file_path": str(path), "clip_number": 1}], clip_target=1, dry_run=True)
        results.append(_pass("10J-e_mock_pass", ok.passed is True))
        results.append(_pass("10J-e_metadata", ok.enriched_artifacts[0].get("validation_status") == "valid"))
        fail = engine.validate([{"file_path": None, "clip_number": 1}], clip_target=1)
        results.append(_pass("10J-e_null_fail", fail.passed is False and fail.reject_code == "ARTIFACT_NULL_PATH"))
    store = ExecutionSessionStore(".")
    session = store.load_session("exec_10j_ops_worker_completed")
    validation = ((session or {}).get("execution_runtime") or {}).get("operations", {}).get("validation", {})
    results.append(_pass("10J-e_dispatch_validation", validation.get("passed") is True))
    return results


def validate_10j_f() -> list[dict]:
    from project_brain.validate_10jf_preapproval import test1_running_polling, test2_completed_stops, test3_legacy_session

    root = Path(".").resolve()
    t1 = test1_running_polling(root)
    t2 = test2_completed_stops(root)
    t3 = test3_legacy_session()
    return [
        _pass("10J-f_poll_running", t1.get("pass") is True, json.dumps(t1.get("intervals_seconds", []))),
        _pass("10J-f_poll_stops_terminal", t2.get("pass") is True),
        _pass("10J-f_legacy_session", t3.get("pass") is True),
    ]


def validate_seeds() -> list[dict]:
    rows = seed_operations_demo_sessions(".")
    labels = {row.get("label") for row in rows}
    return [
        _pass("10J-g_seed_mode_browser", "mode_browser_dequeued" in labels),
        _pass("10J-g_seed_preflight_fail", "preflight_fail" in labels),
        _pass("10J-g_seed_worker_completed", "worker_dry_run_completed" in labels),
    ]


def run_matrix() -> dict:
    store = ExecutionSessionStore(".")
    seed_runtime_demo_sessions(".")
    seed_operations_demo_sessions(".")
    sections = {
        "10J-a": validate_10j_a(),
        "10J-b": validate_10j_b(store),
        "10J-c": validate_10j_c(store),
        "10J-d": validate_10j_d(),
        "10J-e": validate_10j_e(),
        "10J-f": validate_10j_f(),
        "10J-g": validate_seeds(),
    }
    flat = [item for group in sections.values() for item in group]
    passed = sum(1 for item in flat if item["pass"])
    return {
        "sections": sections,
        "summary": {
            "total": len(flat),
            "passed": passed,
            "failed": len(flat) - passed,
            "all_pass": passed == len(flat),
        },
    }


if __name__ == "__main__":
    report = run_matrix()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
