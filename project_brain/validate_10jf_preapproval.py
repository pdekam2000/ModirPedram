"""
Phase 10J-f pre-approval validation — mirrors browser poll hook against live API on :8770.
Does not modify backend code; may write test session JSON only.
"""

from __future__ import annotations

import copy
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API_BASE = "http://127.0.0.1:8770"
POLL_INTERVAL = 5.0
SESSION_RUNNING = "exec_10jf_poll_running"
SESSION_LEGACY = "exec_test_001"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

POLL_STATES = {"DISPATCHED", "RUNNING"}
TERMINAL_STATES = {"COMPLETED", "FAILED"}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{API_BASE}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def should_poll(state: str | None) -> bool:
    return str(state or "").strip().upper() in POLL_STATES


def prepare_running_session(root: Path) -> None:
    source = root / "storage" / "content_brain" / "execution" / "sessions" / "exec_10i_completed_demo.json"
    target = root / "storage" / "content_brain" / "execution" / "sessions" / f"{SESSION_RUNNING}.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    data["execution_session_id"] = SESSION_RUNNING
    data["brief_id"] = "brief_10jf_poll"
    data["state"] = "RUNNING"
    data["updated_at"] = _now()
    runtime = data.setdefault("execution_runtime", {})
    runtime["state"] = "RUNNING"
    runtime["running_at"] = _now()
    runtime["completed_at"] = None
    operations = runtime.setdefault("operations", {})
    operations.update(
        {
            "operations_version": "10j_v1",
            "provider_family": "hailuo",
            "provider_execution_mode": "browser",
            "provider_resolved": "hailuo_browser",
            "learning_key": "hailuo_browser",
            "worker": {
                "phase": "RUNNING",
                "heartbeat_at": _now(),
                "started_at": _now(),
                "elapsed_seconds": 10,
                "thread_alive": True,
                "stale": False,
                "stale_reason": None,
            },
            "preflight": {"passed": True, "checked_at": _now()},
            "cost_telemetry": {
                "start_time": _now(),
                "duration_seconds": 10,
                "estimated_credits": 2.0,
                "outcome": None,
            },
        }
    )
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def bump_running_heartbeat(root: Path, *, elapsed: int) -> None:
    path = root / "storage" / "content_brain" / "execution" / "sessions" / f"{SESSION_RUNNING}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ts = _now()
    runtime = data.setdefault("execution_runtime", {})
    operations = runtime.setdefault("operations", {})
    worker = operations.setdefault("worker", {})
    worker["heartbeat_at"] = ts
    worker["elapsed_seconds"] = elapsed
    worker["phase"] = "RUNNING"
    heartbeat = {
        "heartbeat_at": ts,
        "elapsed_seconds": elapsed,
        "stale": False,
        "stale_reason": None,
        "stale_after_seconds": 120,
    }
    operations["worker"] = worker
    runtime["operations"] = operations
    data["updated_at"] = ts
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def mark_completed(root: Path) -> None:
    path = root / "storage" / "content_brain" / "execution" / "sessions" / f"{SESSION_RUNNING}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ts = _now()
    data["state"] = "COMPLETED"
    data["updated_at"] = ts
    runtime = data.setdefault("execution_runtime", {})
    runtime["state"] = "COMPLETED"
    runtime["completed_at"] = ts
    operations = runtime.setdefault("operations", {})
    worker = operations.setdefault("worker", {})
    worker["phase"] = "COMPLETED"
    worker["thread_alive"] = False
    worker["stale"] = False
    worker["stale_reason"] = None
    telemetry = operations.setdefault("cost_telemetry", {})
    telemetry["duration_seconds"] = 15
    telemetry["outcome"] = "COMPLETED"
    telemetry["end_time"] = ts
    operations["validation"] = {"passed": True, "validated_at": ts}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def simulate_poll_loop(session_id: str, *, max_ticks: int, stop_when_terminal: bool) -> dict:
    timestamps: list[float] = []
    payloads: list[dict] = []
    keep_polling = True
    ticks = 0

    while keep_polling and ticks < max_ticks:
        started = time.monotonic()
        timestamps.append(started)
        payload = _get(f"/sessions/{session_id}/runtime/status")
        payloads.append(payload)
        ticks += 1
        state = payload.get("state") or payload.get("runtime_state")
        keep_polling = should_poll(state)
        if stop_when_terminal and not keep_polling:
            break
        if keep_polling and ticks < max_ticks:
            time.sleep(POLL_INTERVAL)

    intervals = [round(timestamps[i] - timestamps[i - 1], 2) for i in range(1, len(timestamps))]
    return {
        "request_count": len(timestamps),
        "intervals_seconds": intervals,
        "payloads": payloads,
        "final_state": payloads[-1].get("state") if payloads else None,
        "still_polling": should_poll(payloads[-1].get("state") if payloads else None),
    }


def test1_running_polling(root: Path) -> dict:
    prepare_running_session(root)
    timestamps: list[float] = []
    payloads: list[dict] = []
    heartbeat_values: list[str | None] = []
    elapsed_values: list[int | None] = []

    for tick in range(3):
        elapsed = 10 + tick * 5
        bump_running_heartbeat(root, elapsed=elapsed)
        timestamps.append(time.monotonic())
        payload = _get(f"/sessions/{SESSION_RUNNING}/runtime/status")
        payloads.append(payload)
        heartbeat_values.append(
            (payload.get("heartbeat") or {}).get("heartbeat_at")
            or (payload.get("job") or {}).get("heartbeat_at")
        )
        elapsed_values.append(
            (payload.get("heartbeat") or {}).get("elapsed_seconds")
            or (payload.get("job") or {}).get("elapsed_seconds")
        )
        if tick < 2:
            time.sleep(POLL_INTERVAL)

    intervals = [round(timestamps[i] - timestamps[i - 1], 2) for i in range(1, len(timestamps))]
    phases = [p.get("operations_phase") or (p.get("job") or {}).get("phase") for p in payloads]
    intervals_ok = all(4.5 <= gap <= 5.8 for gap in intervals)
    heartbeat_changed = len(set(filter(None, heartbeat_values))) >= 2
    elapsed_increased = len(elapsed_values) >= 2 and (elapsed_values[-1] or 0) > (elapsed_values[0] or 0)
    phase_running = all(str(v or "").upper() == "RUNNING" for v in phases)
    return {
        "pass": intervals_ok and heartbeat_changed and elapsed_increased and phase_running,
        "intervals_ok": intervals_ok,
        "intervals_seconds": intervals,
        "heartbeat_values": heartbeat_values,
        "elapsed_values": elapsed_values,
        "phases": phases,
        "request_count": len(timestamps),
        "still_polling_logic": should_poll(payloads[-1].get("state")),
    }


def test2_completed_stops(root: Path) -> dict:
    mark_completed(root)
    terminal_fetch = _get(f"/sessions/{SESSION_RUNNING}/runtime/status")
    time.sleep(POLL_INTERVAL + 1.0)
    # Hook would not schedule another fetch; verify no automatic server-side push needed.
    # Perform one manual fetch after wait — browser should NOT auto-fire without hook.
    after_wait = _get(f"/sessions/{SESSION_RUNNING}/runtime/status")
    stale = bool((after_wait.get("heartbeat") or {}).get("stale") or (after_wait.get("job") or {}).get("stale"))
    return {
        "pass": (
            str(terminal_fetch.get("state")).upper() == "COMPLETED"
            and not should_poll(terminal_fetch.get("state"))
            and not stale
            and str(after_wait.get("state")).upper() == "COMPLETED"
        ),
        "terminal_state": terminal_fetch.get("state"),
        "still_polling_logic": should_poll(terminal_fetch.get("state")),
        "stale_after_complete": stale,
        "operations_phase": after_wait.get("operations_phase"),
    }


def test3_legacy_session() -> dict:
    detail = _get(f"/sessions/{SESSION_LEGACY}")
    status = _get(f"/sessions/{SESSION_LEGACY}/runtime/status")
    panel = detail.get("provider_runtime_panel") or {}
    panel_data = panel.get("data") or {}
    required_nullable = [
        status.get("provider_execution_mode"),
        status.get("operations_phase"),
        status.get("preflight"),
        status.get("cost_telemetry"),
        panel_data.get("runtime_state"),
    ]
    return {
        "pass": detail.get("session_id") == SESSION_LEGACY and status.get("session_id") == SESSION_LEGACY,
        "detail_status": detail.get("status"),
        "runtime_panel_status": panel.get("status"),
        "runtime_state": status.get("runtime_state"),
        "nullable_fields_present": required_nullable,
    }


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    results = {
        "test1": test1_running_polling(root),
        "test2": test2_completed_stops(root),
        "test3": test3_legacy_session(),
    }
    print(json.dumps(results, indent=2, ensure_ascii=False))
    all_pass = all(item.get("pass") for item in results.values())
    print("ALL PASS" if all_pass else "SOME FAIL")


if __name__ == "__main__":
    main()
