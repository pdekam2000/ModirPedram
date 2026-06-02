# Phase 10K-b — Operations Control Backend + API Report

Generated: 2026-05-30  
Status: **Complete**  
Scope: Backend engine + API only (no UI, no worker cancel hook, no provider execution)

Design reference: `PHASE_10K-a_OPERATIONS_CONTROL_DESIGN_REPORT.md`

---

## Summary

Phase 10K-b implements **operator session control** as a state-preparation layer:

- **Retry** — FAILED → DEQUEUED (preserves failure in `attempt_history`)
- **Cancel** — DISPATCHED/RUNNING with active registry job → CANCELLED (registry cleanup; no worker hook)
- **Archive** — soft flag on COMPLETED/FAILED/CANCELLED (no deletion)
- **Requeue** — FAILED/CANCELLED → QUEUED via existing `ExecutionQueueEngine`

**No action triggers provider dispatch.** API version bumped to **0.6.0**.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/operations_action_policy.py` | Pure eligibility rules per action/state |
| `content_brain/execution/operations_control_engine.py` | Mutations, audit, queue/registry coordination |
| `ui/api/services/operations_control_service.py` | Thin API adapter |
| `ui/api/schemas/operations.py` | Request/response Pydantic models |
| `project_brain/validate_10k_b_operations_backend.py` | Automated backend validation (30 tests) |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/session_store.py` | `operations_audit_path`, `append_global_operations_audit`, timeline merge for `operations_audit_log` |
| `content_brain/execution/__init__.py` | Lazy export: `OperationsControlEngine` |
| `ui/api/dependencies.py` | `get_operations_control_service()` |
| `ui/api/main.py` | Action routes + eligibility GET; API `0.6.0` |
| `project_brain/validate_10j_matrix.py` | Health version check → `0.6.0` |

### Unchanged (by design)

| Path |
|------|
| `content_brain/execution/provider_runtime_engine.py` |
| `content_brain/execution/runtime_worker_engine.py` |
| `core/video_provider_router.py`, `providers/*`, orchestrators |
| `pipelines/full_video_pipeline.py`, `ui/app.py` |
| `ui/web/*` |

---

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/sessions/{session_id}/actions/eligibility` | Per-action allowed + reason |
| POST | `/sessions/{session_id}/actions/retry` | FAILED → DEQUEUED |
| POST | `/sessions/{session_id}/actions/cancel` | Active runtime job → CANCELLED |
| POST | `/sessions/{session_id}/actions/archive` | Soft archive terminal session |
| POST | `/sessions/{session_id}/actions/requeue` | FAILED/CANCELLED → QUEUED |

### Request body

```json
{
  "reason": "operator reason",
  "actor": "operator"
}
```

- **Required** (min 3 chars): cancel, archive, requeue  
- **Optional**: retry

### Success response (200)

```json
{
  "ok": true,
  "session_id": "exec_10j_ops_preflight_fail",
  "action": "retry",
  "previous_state": "FAILED",
  "next_state": "DEQUEUED",
  "audit_event_id": "ops_evt_20260530_143022_a1b2c3",
  "message": "Session prepared for re-dispatch (DEQUEUED). Provider dispatch not started.",
  "api_version": "0.6.0"
}
```

### Blocked response (409 / 400)

```json
{
  "ok": false,
  "code": "ACTION_NOT_ALLOWED",
  "action": "retry",
  "session_id": "exec_10k_val_running",
  "current_state": "RUNNING",
  "reason": "Retry allowed only from FAILED (current: RUNNING).",
  "reject_reasons": ["..."],
  "api_version": "0.6.0"
}
```

HTTP **400** for `REASON_REQUIRED`; **409** for blocked actions; **404** for missing session.

---

## Action State Rules

| Action | Allowed when | Target / effect |
|--------|--------------|-----------------|
| Retry | `FAILED`, no active job, not archived | `DEQUEUED`; failure snapshot in `operations_control.attempt_history` |
| Cancel | `DISPATCHED`/`RUNNING`/`EXECUTING` **and** active registry job | `CANCELLED`; registry `finalize`; `cancel_requested` flag |
| Archive | `COMPLETED`/`FAILED`/`CANCELLED`/`EXPIRED`, no active job | `operations_control.archived = true`; state unchanged |
| Requeue | `FAILED`/`CANCELLED`, not queued, not archived | `QUEUED` via `ExecutionQueueEngine.enqueue_by_id` |

**Global blocks:** archived sessions; active runtime job blocks retry/archive/requeue.

**QUEUED cancel:** use existing `POST /sessions/{id}/queue/cancel` — not operations cancel.

---

## Audit Behavior

**Session field:** `operations_audit_log[]`  
**Global file:** `storage/content_brain/execution/runtime/operations_audit.jsonl`

Event fields:

| Field | Description |
|-------|-------------|
| `event_id` | `ops_evt_{timestamp}_{hex}` |
| `timestamp` | `%Y-%m-%d %H:%M:%S` |
| `session_id` | Execution session ID |
| `action` | retry / cancel / archive / requeue |
| `actor` | From request (default `operator`) |
| `previous_state` | Before mutation |
| `next_state` | After mutation |
| `reason` | Operator reason |
| `allowed` | true / false |
| `blocked_reason` | Set when blocked |
| `metadata` | Action-specific extras |

Blocked attempts are also audited with `allowed: false`.

Timeline tab will include `OPERATIONS` events via extended `build_timeline_events()`.

---

## Session Extensions

```json
{
  "operations_control": {
    "schema_version": "10k_v1",
    "archived": false,
    "retry_count": 0,
    "requeue_count": 0,
    "attempt_history": [],
    "cancel_requested": false
  },
  "operations_audit_log": []
}
```

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_10k_b_operations_backend
```

**30/30 PASS**

| Category | Tests |
|----------|-------|
| Eligibility gates | retry/cancel/archive/requeue allowed/blocked |
| Actions | retry, cancel, archive, requeue mutations |
| Legacy | `exec_test_001` eligibility without crash |
| Audit | global JSONL + session log |
| Safety | no provider dispatch import/call |
| API | eligibility 200, archive 200, retry blocked 409, reason 400 |

---

## Scope Compliance

| Rule | Status |
|------|--------|
| No UI changes | ✅ |
| No provider execution | ✅ |
| No auto-dispatch after retry/requeue | ✅ |
| No worker cooperative cancel | ✅ (registry cleanup only) |
| No provider/browser/orchestrator changes | ✅ |
| Backend uses existing stores/services | ✅ |
| Audit trail on every action | ✅ |

---

## Known Limitations

1. **Cancel (10K-b):** Marks CANCELLED and removes registry entry; does **not** interrupt worker thread or browser orchestrator (10K-d).
2. **Cancel requires active registry job** for DISPATCHED/RUNNING — orphaned RUNNING without registry cannot cancel via this path.
3. **Requeue** uses `QueuePolicy(require_fingerprint_match=False)` for operator path; still subject to readiness/governance/budget gates.
4. **Archive** uses flag overlay; default session list still shows archived sessions until filter added (10K-e).
5. **COMPLETED retry** not implemented (deferred to 10K-c per design).

---

## Next Slice Recommendation

**Phase 10K-c — Operations Control UI**

- `SessionActionsPanel`, confirm dialogs, toasts
- `client.ts` POST/GET helpers
- Eligibility-driven disabled buttons
- Actions tab + post-action refresh

Followed by **10K-d** worker cooperative cancel hook.

---

## Exit Gate

| Criterion | Status |
|-----------|--------|
| OperationsControlEngine implemented | ✅ |
| Four action endpoints + eligibility | ✅ |
| Audit JSONL + session log | ✅ |
| Validation 30/30 | ✅ |
| No forbidden changes | ✅ |

**Phase 10K-b is complete.**
