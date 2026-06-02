"""
Phase 10K-d — cooperative worker cancel validation.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from content_brain.execution.operations_control_engine import OperationsControlEngine
from content_brain.execution.operations_policy import OperationsPolicy
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.execution.runtime_job_registry import RuntimeJobRegistry
from content_brain.execution.runtime_worker_engine import RuntimeWorkerEngine
from content_brain.execution.session_store import ExecutionSessionStore
from project_brain.validate_registry_cleanup import cleanup_validation_registry
from ui.api.main import app


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _load(root: Path, session_id: str) -> dict:
    return json.loads(
        (root / "storage" / "content_brain" / "execution" / "sessions" / f"{session_id}.json").read_text(
            encoding="utf-8"
        )
    )


def _write(store: ExecutionSessionStore, session: dict) -> None:
    store.save_session(session, overwrite=True)


def _cancel_coop_session(root: Path, session_id: str, *, clip_count: int = 3) -> dict:
    """Build a preflight-safe DEQUEUED session for cooperative cancel (provider-independent)."""
    session = copy.deepcopy(_load(root, "exec_10i_dequeued_demo"))
    session["execution_session_id"] = session_id
    session["state"] = "DEQUEUED"
    session["provider"] = "runway_browser"
    session.setdefault("provider_selection", {})
    session["provider_selection"]["primary_provider"] = "runway_browser"
    session["provider_selection"].setdefault("category_selections", {})
    session["provider_selection"]["category_selections"]["video_generation"] = {
        "provider": "runway",
        "execution_mode": "browser",
    }
    format_plan = session["brief_snapshot"]["video_format_plan"]
    format_plan["clip_count"] = clip_count
    format_plan["provider_name"] = "runway_browser"
    format_plan["format_type"] = "multi_clip_runway"
    format_plan["capability"] = "text_to_video"
    shots = session["brief_snapshot"]["run_context"]["story_intelligence"]["schema_director_shots"]
    while len(shots) < clip_count:
        shots.append(copy.deepcopy(shots[0]))
        shots[-1]["clip_number"] = len(shots)
    session.pop("execution_runtime", None)
    session.pop("operations_control", None)
    return session


def _cancel_response_ok(response: object | None) -> tuple[bool, str]:
    if response is None:
        return False, "cancel response missing"
    if isinstance(response, dict):
        ok = bool(response.get("ok"))
        return ok, f"dict ok={ok}"
    ok = bool(getattr(response, "ok", False))
    return ok, f"ok={ok}"


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    worker = RuntimeWorkerEngine(store)
    ops = OperationsControlEngine(store)
    registry = RuntimeJobRegistry(store)
    client = TestClient(app)
    results: list[dict] = []

    session_id = "exec_10kd_cancel_coop"
    cleanup_validation_registry(store, extra_session_ids=(session_id,))
    session = _cancel_coop_session(root, session_id, clip_count=3)
    _write(store, session)

    def slow_execute_clips(self, prompts, provider, artifact_root, policy, *, session_id=None):
        paths: list[str] = []
        for index in range(1, len(prompts) + 1):
            if session_id and self._cancellation_requested(session_id):
                break
            marker = artifact_root / f"clip_{index:02d}.mock"
            marker.write_text(f"mock clip {index}\n", encoding="utf-8")
            paths.append(str(marker))
            time.sleep(0.35)
        return paths

    cancel_result: dict = {}

    def request_cancel():
        time.sleep(0.5)
        for _ in range(60):
            active = registry.get_active_for_session(session_id)
            if active:
                cancel_result["active_found"] = True
                cancel_result["response"] = ops.cancel(
                    session_id,
                    reason="validation cooperative cancel",
                    actor="validate",
                )
                return
            time.sleep(0.1)
        cancel_result["active_found"] = False

    with patch.object(ProviderRuntimeEngine, "_execute_clips", slow_execute_clips):
        cancel_thread = threading.Thread(target=request_cancel, daemon=True)
        cancel_thread.start()
        submit = worker.submit(
            session_id,
            actor="validate",
            policy=OperationsPolicy(skip_provider_execution=True),
            force_worker=True,
            skip_browser_probes=True,
        )
        cancel_thread.join(timeout=15.0)

        for _ in range(40):
            if registry.get_active_for_session(session_id) is None:
                break
            time.sleep(0.15)

    final = store.load_session(session_id)
    runtime = final.get("execution_runtime") or {}
    operations = runtime.get("operations") or {}
    artifacts = (runtime.get("artifacts_by_category") or {}).get("video_generation") or []

    results.append(_pass("worker_submit_accepted", submit.accepted is True, submit.dispatch_id or ""))
    if not cancel_result.get("active_found"):
        results.append(
            _pass(
                "cancel_request_ok",
                False,
                "cancel never invoked: no active job found before timeout (session did not reach RUNNING)",
            )
        )
    else:
        cancel_ok, cancel_detail = _cancel_response_ok(cancel_result.get("response"))
        results.append(_pass("cancel_request_ok", cancel_ok is True, cancel_detail))
    results.append(_pass("final_state_cancelled", final.get("state") == "CANCELLED"))
    results.append(_pass("runtime_state_cancelled", runtime.get("state") == "CANCELLED"))
    results.append(_pass("not_failed", final.get("state") != "FAILED"))
    results.append(_pass("registry_clean", registry.get_active_for_session(session_id) is None))
    results.append(
        _pass(
            "partial_artifacts_preserved",
            0 < len(artifacts) < 3,
            f"artifacts={len(artifacts)}",
        )
    )
    results.append(
        _pass(
            "cancellation_metadata",
            bool(operations.get("cancellation")),
            json.dumps(operations.get("cancellation") or {}),
        )
    )
    results.append(
        _pass(
            "audit_events",
            any(e.get("event_type") == "CANCELLATION_ACKNOWLEDGED" for e in final.get("provider_audit_log") or []),
        )
    )

    status = client.get(f"/sessions/{session_id}/runtime/status").json()
    results.append(_pass("runtime_status_cancelled", status.get("state") == "CANCELLED"))
    results.append(_pass("runtime_status_not_stale", status.get("job", {}).get("stale") is False))

    legacy = ops.eligibility("exec_test_001")
    results.append(_pass("legacy_eligibility_ok", legacy["current_state"] == "SIMULATED"))

    cleanup_validation_registry(store, extra_session_ids=(session_id,))

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
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
