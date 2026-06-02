# Phase 10J-d — Implementation Report

Generated: 2026-05-30  
Status: **Complete**  
Scope: Async API dispatch (202) + enriched status polling (no UI panel work)

---

## Summary

Phase 10J-d wires **`RuntimeWorkerEngine.submit()`** into **`RuntimeService`**. Real execution returns **HTTP 202 Accepted** with `dispatch_id`; dry-run remains **HTTP 200** synchronous. **`GET /runtime/status`** now exposes job phase, heartbeat, stale warning, preflight, mode fields, and cost telemetry.

**API version:** `0.5.0`

**Unchanged:** `VideoProviderRouter`, `providers/*`, `BrowserManager`, orchestrators, `full_video_pipeline.py`, `ui/app.py`.

---

## Files Changed

| File | Change |
|------|--------|
| `ui/api/services/runtime_service.py` | Sync vs async dispatch; enriched `status()` with job/heartbeat/telemetry |
| `ui/api/schemas/runtime.py` | Extended `RuntimeActionResponse`, `RuntimeStatusResponse`, nested job/heartbeat/progress models |
| `ui/api/main.py` | 202 for async accept; 200 sync dry-run; version `0.5.0` |
| `ui/web/src/api/client.ts` | Minimal TypeScript types + `dispatchRuntime()` / `fetchRuntimeStatus()` |

### Unchanged

| Path |
|------|
| `content_brain/execution/runtime_worker_engine.py` |
| `content_brain/execution/runtime_job_registry.py` |
| `ui/api/dependencies.py` (singleton wiring sufficient) |
| `ui/app.py` |

---

## API Behavior

### POST `/sessions/{id}/runtime/dispatch`

| `skip_provider_execution` | HTTP | Behavior |
|---------------------------|------|----------|
| `true` | **200** | Sync `ProviderRuntimeEngine.dispatch()` (10I path) |
| `false` | **202** | Async `RuntimeWorkerEngine.submit()` — preflight + worker |
| reject (not DEQUEUED, etc.) | **409** | Same as 10I |
| session missing | **404** | |

### GET `/sessions/{id}/runtime/status`

Returns all 10I fields **plus**:

| Field | Source |
|-------|--------|
| `provider_family` | `execution_runtime.operations` |
| `provider_execution_mode` | `execution_runtime.operations` |
| `learning_key` | `execution_runtime.operations` |
| `operations_phase` | `operations.worker.phase` |
| `preflight` | `operations.preflight` |
| `cost_telemetry` | `operations.cost_telemetry` |
| `job` | Registry + session operations |
| `heartbeat` | Worker heartbeat mirror |
| `progress` | clip_target / artifact counts |
| `api_version` | `"0.5.0"` |

Legacy sessions without `operations` block: fields return `null` / defaults — no errors.

---

## Async Dispatch Example

**Request:**

```http
POST /sessions/exec_10i_dequeued_demo/runtime/dispatch
Content-Type: application/json

{"skip_provider_execution": false}
```

**Response `202 Accepted`:**

```json
{
  "success": true,
  "accepted": true,
  "async_mode": true,
  "dispatch_mode": "async",
  "session_id": "exec_10i_dequeued_demo",
  "dispatch_id": "disp_20260530_005820_a1b2c3",
  "state": "DEQUEUED",
  "execution_runtime": null,
  "reject_code": null,
  "reject_reasons": [],
  "api_version": "0.5.0"
}
```

Worker continues in background: `JOB_ACCEPTED → PREFLIGHT_* → RUNNING → COMPLETED | FAILED`.

---

## Dry-Run Example (unchanged sync path)

**Request:**

```http
POST /sessions/exec_10i_dequeued_demo/runtime/dispatch
Content-Type: application/json

{"skip_provider_execution": true}
```

**Response `200 OK`:**

```json
{
  "success": true,
  "accepted": true,
  "async_mode": false,
  "dispatch_mode": "sync",
  "session_id": "exec_10i_dequeued_demo",
  "dispatch_id": "disp_20260530_010000_x9y8z7",
  "state": "COMPLETED",
  "execution_runtime": { "state": "COMPLETED", "...": "..." },
  "reject_code": null,
  "reject_reasons": [],
  "api_version": "0.5.0"
}
```

---

## Status Response Example

**Request:**

```http
GET /sessions/exec_10i_dequeued_demo/runtime/status
```

**Response `200 OK` (worker running or terminal):**

```json
{
  "session_id": "exec_10i_dequeued_demo",
  "state": "RUNNING",
  "runtime_state": "RUNNING",
  "provider_category": "video_generation",
  "provider_resolved": "hailuo_browser",
  "provider_family": "hailuo",
  "provider_execution_mode": "browser",
  "learning_key": "hailuo_browser",
  "operations_phase": "RUNNING",
  "dispatch_id": "disp_20260530_005820_a1b2c3",
  "preflight": {
    "passed": true,
    "provider_execution_mode": "browser",
    "checks": []
  },
  "cost_telemetry": {
    "telemetry_version": "10j_v1",
    "provider_name": "hailuo",
    "provider_execution_mode": "browser",
    "start_time": "2026-05-30 00:58:18",
    "end_time": null,
    "duration_seconds": null,
    "outcome": null
  },
  "job": {
    "active": true,
    "phase": "RUNNING",
    "dispatch_id": "disp_20260530_005820_a1b2c3",
    "accepted_at": "2026-05-30 00:58:18",
    "heartbeat_at": "2026-05-30 00:58:48",
    "elapsed_seconds": 30,
    "stale": false,
    "stale_reason": null,
    "stale_after_seconds": 120,
    "thread_alive": true,
    "provider_family": "hailuo",
    "provider_execution_mode": "browser"
  },
  "heartbeat": {
    "heartbeat_at": "2026-05-30 00:58:48",
    "elapsed_seconds": 30,
    "stale": false,
    "stale_reason": null,
    "stale_after_seconds": 120,
    "clip_target": 2,
    "clip_observed": null
  },
  "progress": {
    "clip_target": 2,
    "clip_artifact_count": 0,
    "clip_validated_count": 0
  },
  "api_version": "0.5.0"
}
```

**Stale warning representation** (when `now - heartbeat_at > 120s`):

```json
{
  "job": {
    "active": true,
    "stale": true,
    "stale_reason": "HEARTBEAT_TIMEOUT"
  },
  "heartbeat": {
    "stale": true,
    "stale_reason": "HEARTBEAT_TIMEOUT",
    "stale_after_seconds": 120
  }
}
```

Warning only — session state stays `RUNNING` (no auto-fail).

**Terminal (preflight fail without browser):**

```json
{
  "state": "FAILED",
  "operations_phase": "PREFLIGHT_FAILED",
  "job": { "active": false, "phase": "PREFLIGHT_FAILED" },
  "cost_telemetry": { "outcome": "PREFLIGHT_FAILED", "duration_seconds": 2 }
}
```

`active_jobs.json` cleared on terminal.

---

## Regression Results

| Test | Result |
|------|--------|
| `/health` version `0.5.0` | **PASS** |
| Dry-run dispatch → **200** sync | **PASS** |
| Dry-run `dispatch_mode: sync`, state COMPLETED | **PASS** |
| Real dispatch → **202** accepted | **PASS** |
| 202 returns `dispatch_id` | **PASS** |
| Status includes `job`, `heartbeat`, `cost_telemetry` | **PASS** |
| Status includes `operations_phase` | **PASS** |
| Terminal job `active: false` | **PASS** |
| `active_jobs.json` empty after terminal | **PASS** |
| Legacy session `exec_test_001` status **200** | **PASS** |
| `seed_runtime_demo_sessions` direct engine | **PASS** |
| Linter on modified API files | **PASS** |

**Note:** Real async dispatch without Chrome CDP correctly terminates as `PREFLIGHT_FAILED` / `BROWSER_UNAVAILABLE` — worker and registry cleanup verified.

---

## Backward Compatibility

| Area | Status |
|------|--------|
| 10I sync dry-run via API | **Unchanged** — still 200 + completed session |
| 10I seed scripts | **Unchanged** — call engine directly |
| Legacy sessions (no `operations`) | **OK** — status returns with null optional fields |
| Existing status fields | **Preserved** — all 10I fields still present |
| 10J-c worker | **Consumed** — no worker logic changes |

---

## Next Recommended Slice: **10J-e — Artifact Validation**

| Deliverable | Purpose |
|-------------|---------|
| `artifact_validation_engine.py` | Post-provider file checks |
| Wire into worker finalize | No COMPLETED without validated artifacts |
| Failure codes | `ARTIFACT_VALIDATION_FAILED`, etc. |

**Exit gate:** Invalid mock paths → FAILED; valid dry-run → COMPLETED with enriched artifact metadata.

**Then:** 10J-f UI observability (poll hook, stale banner, mode/duration display).

---

*End of Phase 10J-d Implementation Report*
