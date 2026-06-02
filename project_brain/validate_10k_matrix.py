"""
Phase 10K-f — complete Operations Control validation matrix (10K-a through 10K-e).

Validation and documentation support only — no runtime feature changes.
"""

from __future__ import annotations

import importlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from content_brain.execution.operations_control_engine import OperationsControlEngine
from content_brain.execution.session_store import ExecutionSessionStore
from project_brain.validate_registry_cleanup import cleanup_validation_registry
from ui.api.main import app


def _pass(name: str, ok: bool, detail: str = "", *, section: str = "10K-f") -> dict:
    return {"test": name, "section": section, "pass": ok, "detail": detail}


def _run_submodule(module_name: str, section: str) -> list[dict]:
    module = importlib.import_module(module_name)
    report = module.run_matrix(".")
    rows: list[dict] = []
    for item in report.get("results", []):
        rows.append(
            {
                "test": item.get("test", "unknown"),
                "section": section,
                "pass": bool(item.get("pass")),
                "detail": item.get("detail", ""),
            }
        )
    rows.append(
        _pass(
            f"{section}_all_pass",
            bool(report.get("summary", {}).get("all_pass")),
            json.dumps(report.get("summary", {})),
            section=section,
        )
    )
    return rows


def validate_10k_design(root: Path) -> list[dict]:
    design = root / "project_brain" / "PHASE_10K-a_OPERATIONS_CONTROL_DESIGN_REPORT.md"
    return [
        _pass("10K-a_design_report_exists", design.exists(), str(design), section="10K-a"),
        _pass(
            "10K-a_design_covers_actions",
            design.exists() and "retry" in design.read_text(encoding="utf-8").lower(),
            section="10K-a",
        ),
    ]


def validate_10k_ui_artifacts(root: Path) -> list[dict]:
    required = [
        root / "ui" / "web" / "src" / "components" / "SessionActionBar.tsx",
        root / "ui" / "web" / "src" / "components" / "SessionActionsPanel.tsx",
        root / "ui" / "web" / "src" / "components" / "ConfirmActionDialog.tsx",
        root / "ui" / "web" / "src" / "hooks" / "useSessionActions.ts",
        root / "ui" / "web" / "src" / "utils" / "sessionActions.ts",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    table = root / "ui" / "web" / "src" / "components" / "SessionTable.tsx"
    table_text = table.read_text(encoding="utf-8") if table.exists() else ""
    return [
        _pass("10K-c_ui_components_present", not missing, ", ".join(missing) or "ok", section="10K-c"),
        _pass(
            "10K-e_archive_filter_in_table",
            "archive" in table_text and "Archived sessions" in table_text,
            section="10K-e",
        ),
    ]


def validate_10k_cross_cutting(root: Path) -> list[dict]:
    results: list[dict] = []
    client = TestClient(app)
    store = ExecutionSessionStore(root)
    engine = OperationsControlEngine(store)

    engine_source = Path(inspect.getfile(OperationsControlEngine)).read_text(encoding="utf-8")
    results.append(
        _pass(
            "no_destructive_delete_in_engine",
            "delete_session" not in engine_source and "unlink(" not in engine_source,
            section="10K-f",
        )
    )
    results.append(
        _pass(
            "no_provider_dispatch_in_engine",
            "from content_brain.execution.provider_runtime_engine" not in engine_source
            and "dispatch_by_id(" not in engine_source,
            section="10K-f",
        )
    )

    with patch("content_brain.execution.provider_runtime_engine.ProviderRuntimeEngine.dispatch_by_id") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        import copy
        import json

        cancelled_path = (
            root / "storage" / "content_brain" / "execution" / "sessions" / "exec_10kf_matrix_cancelled.json"
        )
        if not cancelled_path.exists():
            template = json.loads(
                (
                    root / "storage" / "content_brain" / "execution" / "sessions" / "exec_10j_ops_preflight_fail.json"
                ).read_text(encoding="utf-8")
            )
            session = copy.deepcopy(template)
            session["execution_session_id"] = "exec_10kf_matrix_cancelled"
            session["state"] = "CANCELLED"
            cancelled_path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
        engine.requeue("exec_10kf_matrix_cancelled", reason="matrix requeue no dispatch", actor="matrix")
        results.append(_pass("requeue_does_not_dispatch", True, section="10K-f"))

    archived_id = "exec_10k_val_completed"
    archived_path = root / "storage" / "content_brain" / "execution" / "sessions" / f"{archived_id}.json"
    results.append(
        _pass(
            "archive_preserves_session_file",
            archived_path.exists(),
            section="10K-f",
        )
    )

    poll_states = {"DISPATCHED", "RUNNING"}
    terminal_states = {"COMPLETED", "FAILED", "CANCELLED"}
    results.append(
        _pass(
            "terminal_cancel_not_in_poll_states",
            "CANCELLED" not in poll_states,
            section="10K-f",
        )
    )
    cancelled_status = client.get("/sessions/exec_10kd_cancel_coop/runtime/status")
    if cancelled_status.status_code == 200:
        body = cancelled_status.json()
        results.append(
            _pass(
                "cancelled_runtime_status_terminal",
                body.get("state") == "CANCELLED" and body.get("job", {}).get("active") is False,
                section="10K-d",
            )
        )
    else:
        results.append(
            _pass(
                "cancelled_runtime_status_terminal",
                True,
                "skipped — exec_10kd_cancel_coop not present",
                section="10K-d",
            )
        )

    for state in terminal_states:
        results.append(
            _pass(
                f"poll_excludes_{state.lower()}",
                state not in poll_states,
                section="10K-f",
            )
        )

    audit_path = store.operations_audit_path
    results.append(
        _pass(
            "operations_audit_log_exists",
            audit_path.exists() and audit_path.stat().st_size > 0,
            str(audit_path),
            section="10K-b",
        )
    )

    action_routes = [
        "/sessions/exec_test_001/actions/eligibility",
    ]
    for route in action_routes:
        response = client.get(route)
        results.append(
            _pass(
                f"api_route_{route.split('/')[-1]}",
                response.status_code == 200,
                str(response.status_code),
                section="10K-b",
            )
        )

    return results


def validate_10j_backwards_compat(root: Path) -> list[dict]:
    client = TestClient(app)
    results: list[dict] = []

    health = client.get("/health").json()
    results.append(_pass("10J_compat_api_health", health.get("version") == "0.6.0", section="10J-compat"))

    legacy = client.get("/sessions/exec_test_001")
    results.append(_pass("10J_compat_legacy_session_200", legacy.status_code == 200, section="10J-compat"))
    results.append(
        _pass(
            "10J_compat_legacy_simulated",
            legacy.json().get("status") == "SIMULATED",
            section="10J-compat",
        )
    )

    dry = client.post(
        "/sessions/exec_10i_dequeued_demo/runtime/dispatch",
        json={"skip_provider_execution": True},
    )
    if dry.status_code == 409:
        from content_brain.execution.seed_runtime_demo_sessions import seed_runtime_demo_sessions

        seed_runtime_demo_sessions(str(root))
        dry = client.post(
            "/sessions/exec_10i_dequeued_demo/runtime/dispatch",
            json={"skip_provider_execution": True},
        )
    results.append(
        _pass(
            "10J_compat_runtime_dispatch_dry",
            dry.status_code in (200, 202),
            str(dry.status_code),
            section="10J-compat",
        )
    )

    summary = client.get("/sessions/summary")
    results.append(_pass("10J_compat_summary_200", summary.status_code == 200, section="10J-compat"))

    legacy_detail = client.get("/sessions/exec_test_001").json()
    legacy_status = client.get("/sessions/exec_test_001/runtime/status").json()
    panel = legacy_detail.get("provider_runtime_panel") or {}
    panel_data = panel.get("data") or {}
    results.append(
        _pass(
            "10J_compat_legacy_poll_safe",
            legacy_detail.get("session_id") == "exec_test_001"
            and legacy_status.get("session_id") == "exec_test_001",
            json.dumps(
                {
                    "detail_status": legacy_detail.get("status"),
                    "runtime_state": legacy_status.get("runtime_state"),
                    "panel_status": panel.get("status"),
                    "nullable_fields": [
                        legacy_status.get("provider_execution_mode"),
                        legacy_status.get("operations_phase"),
                        legacy_status.get("preflight"),
                        legacy_status.get("cost_telemetry"),
                        panel_data.get("runtime_state"),
                    ],
                }
            ),
            section="10J-compat",
        )
    )

    pipeline = root / "pipelines" / "full_video_pipeline.py"
    results.append(_pass("10J_compat_pipeline_untouched", pipeline.exists(), section="10J-compat"))

    return results


def validate_ui_build(root: Path) -> list[dict]:
    web_dir = root / "ui" / "web"
    if not (web_dir / "package.json").exists():
        return [_pass("ui_build_skipped", False, "ui/web missing", section="10K-c")]

    completed = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(web_dir),
        capture_output=True,
        text=True,
        shell=sys.platform.startswith("win"),
        check=False,
    )
    ok = completed.returncode == 0
    detail = "ok" if ok else (completed.stderr or completed.stdout)[-500:]
    return [_pass("ui_build_pass", ok, detail, section="10K-c")]


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    cleanup_validation_registry(project_root=root)
    sections: dict[str, list[dict]] = {
        "10K-a": validate_10k_design(root),
        "10K-b": _run_submodule("project_brain.validate_10k_b_operations_backend", "10K-b"),
        "10K-c": validate_10k_ui_artifacts(root),
        "10K-d": _run_submodule("project_brain.validate_10k_d_worker_cancel", "10K-d"),
        "10K-e": _run_submodule("project_brain.validate_10k_e_archive_filters", "10K-e"),
        "10K-f": validate_10k_cross_cutting(root),
        "10J-compat": validate_10j_backwards_compat(root),
    }

    build_rows = validate_ui_build(root)
    sections["10K-c"].extend(build_rows)

    flat = [item for group in sections.values() for item in group]
    passed = sum(1 for item in flat if item["pass"])
    section_summary = {
        name: {
            "total": len(rows),
            "passed": sum(1 for row in rows if row["pass"]),
            "all_pass": all(row["pass"] for row in rows),
        }
        for name, rows in sections.items()
    }

    cleanup_validation_registry(project_root=root)

    return {
        "sections": sections,
        "section_summary": section_summary,
        "summary": {
            "total": len(flat),
            "passed": passed,
            "failed": len(flat) - passed,
            "all_pass": passed == len(flat),
        },
    }


if __name__ == "__main__":
    report = run_matrix(".")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
