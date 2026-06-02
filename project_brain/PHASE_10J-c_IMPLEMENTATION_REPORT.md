# Phase 10J-c — Implementation Report

Generated: 2026-05-30  
Status: **Complete**  
Scope: Worker & job registry (no async API, no UI changes)

---

## Summary

Phase 10J-c adds **background job execution** with a full lifecycle, **preflight gate before router call**, **30s heartbeat**, **cost telemetry init/finalize**, and **active_jobs.json** registry. Dry-run remains **synchronous** via unchanged `ProviderRuntimeEngine.dispatch()` unless `force_worker=True`.

**Unchanged:** `VideoProviderRouter`, `providers/*`, `BrowserManager`, orchestrators, `full_video_pipeline.py`, `ui/app.py`, `ui/api/*`.

**Minimal extension:** `ProviderRuntimeEngine` preserves `operations` block and accepts optional `dispatch_id`.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/runtime_job_registry.py` | `active_jobs.json`, job snapshots, browser concurrency count, stale warning |
| `content_brain/execution/runtime_worker_engine.py` | Daemon thread worker, lifecycle, preflight gate, heartbeat, cost telemetry |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/session_store.py` | `active_jobs_path`, `jobs_dir`, `logs_dir`, `load/save_active_jobs`, `atomic_write_json`, `file_mutex` |
| `content_brain/execution/provider_runtime_engine.py` | Optional `dispatch_id`; preserve `execution_runtime.operations` across dispatch |
| `content_brain/execution/__init__.py` | Lazy exports: `RuntimeWorkerEngine`, `RuntimeJobRegistry`, `WorkerSubmitResult`, `JobRecord` |

### Storage (runtime)

```
storage/content_brain/execution/runtime/
  active_jobs.json          # in-flight index
  jobs/{dispatch_id}.json   # heartbeat + terminal snapshots
  logs/{dispatch_id}.log    # reserved (10J-c path helper only)
  locks/*.lock              # mutex files
```

---

## Job Lifecycle

```
JOB_ACCEPTED
    ↓
PREFLIGHT_RUNNING
    ↓
PREFLIGHT_PASSED ──→ RUNNING ──→ COMPLETED
    │
    └── PREFLIGHT_FAILED (terminal, no router call)

RUNNING ──→ FAILED (router/runtime error)
```

| Phase | Session `state` | Router called? |
|-------|-----------------|----------------|
| JOB_ACCEPTED | DEQUEUED | No |
| PREFLIGHT_* | DEQUEUED / FAILED | No |
| RUNNING | DISPATCHED → RUNNING | Yes (after PREFLIGHT_PASSED) |
| COMPLETED / FAILED | COMPLETED / FAILED | — |

---

## Job Lifecycle Example (dry-run worker)

```python
from content_brain.execution.operations_policy import OperationsPolicy
from content_brain.execution.runtime_worker_engine import RuntimeWorkerEngine
from content_brain.execution.session_store import ExecutionSessionStore

store = ExecutionSessionStore(".")
worker = RuntimeWorkerEngine(store)

result = worker.submit(
    "exec_10i_dequeued_demo",
    policy=OperationsPolicy(skip_provider_execution=True),
    force_worker=True,
    skip_browser_probes=True,
    actor="operator",
)
# result.accepted=True, result.async_mode=True, result.dispatch_id="disp_..."

# Poll session until terminal:
# operations.worker.phase: JOB_ACCEPTED → PREFLIGHT_RUNNING → PREFLIGHT_PASSED → RUNNING → COMPLETED
# operations.cost_telemetry.outcome: COMPLETED
```

---

## Heartbeat Example

While `RUNNING`, worker updates every **30 seconds** (configurable via `OperationsPolicy.heartbeat_interval_seconds`):

**`runtime/jobs/disp_20260530_120000_ab12cd.json`**

```json
{
  "job_id": "disp_20260530_120000_ab12cd",
  "session_id": "exec_10i_dequeued_demo",
  "phase": "RUNNING",
  "provider_execution_mode": "browser",
  "provider_family": "hailuo",
  "heartbeat_at": "2026-05-30 12:04:30",
  "elapsed_seconds": 270,
  "clip_target": 2,
  "clip_observed": null,
  "thread_alive": true,
  "stale": false
}
```

**Stale behavior:** If `now - heartbeat_at > stale_after_seconds` (default 120), registry sets `stale: true`, `stale_reason: "HEARTBEAT_TIMEOUT"`. **Warning only — no auto-fail.**

Mirrored on session: `execution_runtime.operations.worker.heartbeat_at`, `.stale`, `.elapsed_seconds`.

---

## Preflight Pass / Fail Examples

### Pass (browser, probes skipped for CI)

```json
{
  "preflight": {
    "passed": true,
    "provider_execution_mode": "browser",
    "provider_resolved": "hailuo_browser",
    "checks": [
      {"id": "PROVIDER_FAMILY_RESOLVED", "passed": true},
      {"id": "PROMPT_BUNDLE", "passed": true},
      {"id": "BROWSER_CONCURRENCY", "passed": true}
    ]
  },
  "worker": {"phase": "PREFLIGHT_PASSED"}
}
```

Audit: `PREFLIGHT_PASSED` → then `ProviderRuntimeEngine.dispatch()` runs.

### Fail (Hailuo API — not implemented)

```json
{
  "preflight": {
    "passed": false,
    "reject_code": "PROVIDER_NOT_IMPLEMENTED",
    "checks": [
      {"id": "ROUTER_IMPLEMENTED", "passed": false, "message": "API mode implementation status: planned"}
    ]
  },
  "worker": {"phase": "PREFLIGHT_FAILED"},
  "failure": {"code": "PROVIDER_NOT_IMPLEMENTED", "category": "PREFLIGHT_REJECT"}
}
```

**No router call.** Job removed from `active_jobs.json`. Terminal snapshot written.

---

## Cost Telemetry Example

**Init at JOB_ACCEPTED:**

```json
{
  "telemetry_version": "10j_v1",
  "provider_name": "hailuo",
  "provider_execution_mode": "browser",
  "learning_key": "hailuo_browser",
  "router_key": "hailuo_browser",
  "dispatch_id": "disp_20260530_120000_ab12cd",
  "start_time": "2026-05-30 12:00:00",
  "end_time": null,
  "duration_seconds": null,
  "estimated_credits": null,
  "outcome": null
}
```

**Finalize on COMPLETED:**

```json
{
  "end_time": "2026-05-30 12:00:02",
  "duration_seconds": 2,
  "outcome": "COMPLETED"
}
```

**Finalize on PREFLIGHT_FAILED:**

```json
{
  "end_time": "2026-05-30 12:00:01",
  "duration_seconds": 1,
  "outcome": "PREFLIGHT_FAILED"
}
```

Audit event: `COST_TELEMETRY_RECORDED` with full block in `details`.

---

## Concurrency & Guards

| Rule | Implementation |
|------|----------------|
| One active job per session | `RuntimeJobRegistry.get_active_for_session()` + `JOB_ALREADY_ACTIVE` |
| Browser concurrency cap = 1 | Preflight `BROWSER_CONCURRENCY` uses registry count |
| Dry-run sync preserved | `submit()` → direct `ProviderRuntimeEngine` when `skip_provider_execution=True` |
| Preflight before router | Worker runs `ProviderPreflightValidator` before `dispatch_by_id()` |

---

## Audit Events (10J-c additions)

| Event | When |
|-------|------|
| `JOB_ACCEPTED` | Worker thread starts |
| `MODE_RESOLVED` | Family + mode + router_key |
| `PREFLIGHT_PASSED` / `PREFLIGHT_FAILED` | After preflight |
| `HEARTBEAT` | Sampled every 4th tick (~2 min) |
| `COST_TELEMETRY_RECORDED` | Terminal state |
| `JOB_FINALIZED` | Worker exit |

Existing 10I events (`DISPATCHED`, `RUNNING`, `COMPLETED`, `FAILED`) still emitted by `ProviderRuntimeEngine` during execution phase.

---

## Regression Results

| Test | Result |
|------|--------|
| `seed_runtime_demo_sessions` (10I sync) | **PASS** |
| Sync dry-run `ProviderRuntimeEngine.dispatch_by_id` | **PASS** |
| Worker dry-run `force_worker=True` → COMPLETED | **PASS** |
| Preflight passed before dispatch | **PASS** |
| Cost telemetry COMPLETED + end_time | **PASS** |
| `active_jobs.json` cleaned on terminal | **PASS** |
| Job snapshot terminal phase | **PASS** |
| Hailuo API preflight → PREFLIGHT_FAILED | **PASS** |
| Cost telemetry PREFLIGHT_FAILED outcome | **PASS** |
| Double submit → JOB_ALREADY_ACTIVE | **PASS** |
| Linter on new/modified files | **PASS** |

---

## Backward Compatibility

| Area | Status |
|------|--------|
| 10I `ProviderRuntimeEngine.dispatch()` direct calls | **Unchanged behavior** |
| API v0.4.0 `RuntimeService` | **Unchanged** — still sync engine |
| Sessions without `operations` block | **OK** — block added only via worker |
| 10J-b preflight module | **Consumed** by worker |
| 10J-a cost_telemetry | **Consumed** init/finalize |

Worker path is **opt-in** via `RuntimeWorkerEngine.submit()`. API async wiring deferred to **10J-d**.

---

## Next Recommended Slice: **10J-d — Async API & Status Polling**

| Deliverable | Builds on 10J-c |
|-------------|-----------------|
| `runtime_service.dispatch_async()` | `RuntimeWorkerEngine.submit()` |
| HTTP 202 for real execution | Worker accept response |
| HTTP 200 sync for dry-run | Existing engine path |
| Enriched `GET /runtime/status` | job phase, heartbeat, stale, cost_telemetry |
| API version **0.5.0** | — |

**Exit gate:** POST dispatch with `skip_provider_execution=false` returns 202; status poll shows job heartbeat and cost telemetry start fields.

**Do not start:** 10J-f UI until 10J-d status API is stable.

---

*End of Phase 10J-c Implementation Report*
