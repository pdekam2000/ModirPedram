# Phase 11J-14 — Assembly Approval Write APIs Implementation Report

**Status:** Complete — metadata-only write APIs; no FFmpeg, no UI buttons, no real execution flags  
**Date:** 2026-06-01  
**Prerequisite:** 11J-13 design, 11J-12 read-only guard, 11J-8 dry-run API  
**Next phase:** **PHASE 11J-15 — Assembly Approval UI Controls Design**

---

## Summary

Implemented backend-only Assembly Approval Write APIs that mutate **only** `assembly_generation.approval` and append `operations.assembly_approval_audit[]`. All four endpoints return `real_assembly_executed=false`. Upstream video/voice/subtitle slots are preserved.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/assembly_approval_action_policy.py` | Approve/reject/expire/reset precondition checks |
| `content_brain/execution/assembly_approval_operations_engine.py` | Mutations, guard recalc, audit append |
| `ui/api/assembly_approval_service.py` | Thin API service wrapper |
| `ui/api/schemas/assembly_approval.py` | Request/response Pydantic models |
| `project_brain/validate_11j14_assembly_approval_write_apis.py` | 17-test validator |
| `project_brain/PHASE_11J14_ASSEMBLY_APPROVAL_WRITE_APIS_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `ui/api/main.py` | Four POST routes + `_assembly_approval_response()` helper |
| `ui/api/dependencies.py` | `get_assembly_approval_service()` |
| `content_brain/execution/failure_taxonomy.py` | Added `ASSEMBLY_DRY_RUN_NOT_COMPLETED`, `ASSEMBLY_APPROVAL_INVALID_STATE`, `ASSEMBLY_APPROVAL_PRECONDITION_FAILED` |

---

## Endpoint List

| Method | Path | Action |
|--------|------|--------|
| `POST` | `/sessions/{session_id}/assembly/approve` | `approve_assembly` |
| `POST` | `/sessions/{session_id}/assembly/reject` | `reject_assembly` |
| `POST` | `/sessions/{session_id}/assembly/expire` | `expire_assembly` |
| `POST` | `/sessions/{session_id}/assembly/reset-approval` | `reset_assembly_approval` |

- **200** on successful metadata mutation  
- **409** on precondition failure (policy block)  
- **404** if session missing  

---

## State Transition Behavior

### Approve (success)

- Requires: READY plan, dry-run completed, `request_real_assembly=true`, session not archived/cancelled
- Sets `approval_state=approved`, grant fields, `real_assembly_requested=true`
- Re-runs `evaluate_assembly_approval_gate()` + `can_run_real_assembly()`
- `assembly_eligible` may remain `false` if env flags off (correct)

### Reject

- Sets `approval_state=rejected`, `assembly_eligible=false`
- `assembly_blocked_reasons` includes `ASSEMBLY_APPROVAL_REJECTED`
- Clears grant fields

### Expire

- Sets `approval_state=expired`, `assembly_eligible=false`
- `assembly_blocked_reasons` includes `ASSEMBLY_APPROVAL_EXPIRED`

### Reset

- Clears `approved_by`, `approved_at`, `approval_reason`, `approval_expires_at`
- Re-evaluates gate → `required` or `not_required` based on `real_assembly_requested` + plan

---

## Audit Event Examples

```json
{
  "event_id": "asm_appr_evt_20260601_073500_a1b2c3",
  "event_type": "assembly_approval_approved",
  "session_id": "exec_11j14_approve_ok",
  "category": "assembly_generation",
  "actor": "validator",
  "reason": "Validator approval",
  "timestamp": "2026-06-01T07:35:00Z",
  "previous_state": "required",
  "new_state": "approved",
  "blocked_reasons": ["ASSEMBLY_REAL_EXECUTION_DISABLED"],
  "assembly_eligible": false,
  "real_assembly_executed": false,
  "allowed": true
}
```

Blocked approve attempt still appends audit with `allowed=false` and unchanged `new_state`.

Audit location: `execution_runtime.operations.assembly_approval_audit[]` (FIFO trim at 50 events).

---

## Validation Results

| Command | Result |
|---------|--------|
| `python -m project_brain.validate_11j14_assembly_approval_write_apis` | **17/17 PASS** |
| `python -m project_brain.validate_11j12_assembly_approval_guard` | **PASS** (core + npm build when run as module) |
| `python -m project_brain.validate_11j8_assembly_runtime_api` | **PASS** |
| `python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution` | **17/17 PASS** |

### 11J-14 test coverage

1. Approve without READY plan blocks  
2. Approve without dry-run completed blocks  
3. Approve without `request_real_assembly` blocks  
4. Approve with READY plan succeeds  
5. Reject sets rejected state  
6. Expire sets expired state  
7. Reset clears grant fields  
8. Audit trail appended  
9–11. Video/voice/subtitle slots unchanged  
12. Response always `real_assembly_executed=false`  
13. No FFmpeg import/call in new modules  
14. No `FINAL_PUBLISH_READY.mp4` created  
15–17. 11J-12 / 11J-8 / 11H-2d regressions  

---

## Safety Confirmations

| Constraint | Status |
|------------|--------|
| No FFmpeg import/call in policy/engine/service | Confirmed (AST scan) |
| No `FINAL_PUBLISH_READY.mp4` created | Confirmed |
| No env flag mutation | Confirmed |
| Upstream slots unchanged | Confirmed (deep-copy compare) |
| `real_assembly_executed=false` always | Confirmed |
| No UI buttons added | Confirmed |
| No `full_video_pipeline.py` import | Confirmed |

---

## Next Recommended Phase

**PHASE 11J-15 — Assembly Approval UI Controls Design**

Design approve/reject/expire/reset controls in `AssemblyRuntimeObservabilityPanel` wired to these endpoints. Still metadata-only — no FFmpeg, no Run Assembly button for real execution until a later gated phase (11J-17+).
