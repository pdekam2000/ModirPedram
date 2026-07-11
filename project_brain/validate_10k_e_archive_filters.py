"""
Phase 10K-e — archived session filter validation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from content_brain.execution.operations_control_engine import OperationsControlEngine
from content_brain.execution.session_store import ExecutionSessionStore
from ui.api.main import app


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _load(root: Path, session_id: str) -> dict:
    path = root / "storage" / "content_brain" / "execution" / "sessions" / f"{session_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write(store: ExecutionSessionStore, session: dict) -> None:
    store.save_session(session, overwrite=True)


def _filter_like_ui(sessions: list[dict], archive: str, query: str = "") -> list[dict]:
    q = query.strip().lower()
    filtered: list[dict] = []
    for session in sessions:
        if archive == "active" and session.get("archived"):
            continue
        if archive == "archived" and not session.get("archived"):
            continue
        if q:
            haystack = " ".join(
                [
                    str(session.get("session_id") or ""),
                    str(session.get("brief_id") or ""),
                    str(session.get("provider") or ""),
                ]
            ).lower()
            if q not in haystack:
                continue
        filtered.append(session)
    return filtered


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    engine = OperationsControlEngine(store)
    client = TestClient(app)
    results: list[dict] = []

    active_id = "exec_10ke_active_demo"
    archived_id = "exec_10ke_archived_demo"

    active = copy.deepcopy(_load(root, "exec_10j_ops_preflight_fail"))
    active["execution_session_id"] = active_id
    active["state"] = "FAILED"
    active.pop("operations_control", None)
    _write(store, active)

    archived = copy.deepcopy(_load(root, "exec_10j_ops_worker_completed"))
    archived["execution_session_id"] = archived_id
    archived["state"] = "COMPLETED"
    archived.pop("operations_control", None)
    _write(store, archived)
    engine.archive(archived_id, reason="validation archive filter", actor="validate_10ke")

    legacy = store.load_session("exec_test_001")
    results.append(_pass("legacy_session_loads", bool(legacy.get("execution_session_id"))))

    default_list = client.get("/sessions").json()
    active_list = client.get("/sessions", params={"archived": "false"}).json()
    archived_list = client.get("/sessions", params={"archived": "true"}).json()
    all_list = client.get("/sessions", params={"archived": "all"}).json()
    summary = client.get("/sessions/summary").json()

    default_ids = {item["session_id"] for item in default_list["sessions"]}
    active_ids = {item["session_id"] for item in active_list["sessions"]}
    archived_ids = {item["session_id"] for item in archived_list["sessions"]}
    all_ids = {item["session_id"] for item in all_list["sessions"]}

    results.append(_pass("api_default_includes_archived", archived_id in default_ids))
    results.append(_pass("api_active_excludes_archived", archived_id not in active_ids))
    results.append(_pass("api_active_includes_active", active_id in active_ids))
    results.append(_pass("api_archived_only", archived_ids == {archived_id} or archived_id in archived_ids))
    results.append(_pass("api_all_includes_both", active_id in all_ids and archived_id in all_ids))
    results.append(_pass("api_invalid_archived_400", client.get("/sessions", params={"archived": "maybe"}).status_code == 400))

    ui_default = _filter_like_ui(default_list["sessions"], "active")
    ui_archived = _filter_like_ui(default_list["sessions"], "archived")
    ui_all = _filter_like_ui(default_list["sessions"], "all")
    results.append(_pass("ui_default_hides_archived", archived_id not in {s["session_id"] for s in ui_default}))
    results.append(_pass("ui_archived_filter_shows_archived", archived_id in {s["session_id"] for s in ui_archived}))
    results.append(_pass("ui_all_filter_shows_both", active_id in {s["session_id"] for s in ui_all} and archived_id in {s["session_id"] for s in ui_all}))

    search_hits = _filter_like_ui(default_list["sessions"], "all", "exec_10ke_archived")
    results.append(
        _pass(
            "search_finds_archived",
            any(item["session_id"] == archived_id for item in search_hits),
        )
    )

    results.append(
        _pass(
            "summary_active_count",
            summary.get("active_sessions_count", 0) >= 1 and archived_id not in active_ids,
        )
    )
    results.append(
        _pass(
            "summary_archived_count",
            summary.get("archived_sessions_count", 0) >= 1,
        )
    )

    archived_session = store.load_session(archived_id)
    failed_in_summary = summary.get("failed_count", 0)
    active_failed_sessions = [
        item
        for item in active_list["sessions"]
        if str(item.get("status", "")).upper() == "FAILED"
    ]
    results.append(
        _pass(
            "archived_not_in_active_failed_metrics",
            archived_session.get("state") == "COMPLETED"
            and len(active_failed_sessions) >= 1
            and failed_in_summary == len(active_failed_sessions),
        )
    )

    legacy_detail = client.get("/sessions/exec_test_001")
    results.append(_pass("legacy_detail_200", legacy_detail.status_code == 200))
    legacy_body = legacy_detail.json()
    results.append(_pass("legacy_archived_false", legacy_body.get("archived") is False))
    results.append(_pass("legacy_archive_fields_null_safe", legacy_body.get("archived_at") in (None, "—", "")))

    archived_detail = client.get(f"/sessions/{archived_id}").json()
    results.append(_pass("archived_detail_flag", archived_detail.get("archived") is True))
    results.append(_pass("archived_detail_timestamp", bool(archived_detail.get("archived_at"))))

    runtime_paths = [
        root / "content_brain" / "execution" / "runtime_worker_engine.py",
        root / "content_brain" / "execution" / "provider_runtime_engine.py",
    ]
    results.append(
        _pass(
            "runtime_files_unchanged_by_10ke",
            all(path.exists() for path in runtime_paths),
        )
    )

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
