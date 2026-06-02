# Phase 11F-d — Hailuo Runtime Cancel Wiring

**Status:** Complete  
**Date:** 2026-05-30  
**Prerequisites:** Phase 11F-c artifact continuity · Runway 11E-e cancel wiring baseline

---

## Summary

Live `cancel_check` from `ProviderRuntimeEngine` is now wired through `VideoProviderRouter` into the Hailuo browser path (orchestrator + download provider). Cooperative cancellation raises `HailuoCancelledError` with code `OPERATIONS_CANCELLED`, maps to session state `CANCELLED` (not `FAILED`), and preserves partial artifacts / `clip_results`.

Scope was runtime-to-Hailuo cancel wiring only — no API, UI, default provider switch, or failover execution.

---

## Files Created

| File | Purpose |
|------|---------|
| `project_brain/validate_11f_d_hailuo_runtime_cancel.py` | Mock-only cancel wiring matrix (22 core + 5 nested regression gates) |
| `project_brain/validate_registry_cleanup.py` | Shared active-job cleanup for validation suites (harness isolation fix) |
| `project_brain/PHASE_11F-d_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified — 11F-d Production Implementation

| File | Change |
|------|--------|
| `content_brain/execution/provider_cancel_wiring.py` | `HAILUO_CANCEL_AWARE_PROVIDERS`, `CANCEL_AWARE_PROVIDERS`; Hailuo in `provider_accepts_runtime_cancel()` and `is_provider_cooperative_cancel()` |
| `content_brain/execution/provider_runtime_engine.py` | Catch `HailuoCancelledError` alongside `RunwayCancelledError`; canonicalize partial paths; `_clip_result_metadata_key()` → `hailuo_clip_result` in cooperative cancel metadata |

**Unchanged but consumed:** `core/video_provider_router.py` (already passes `cancel_check` via `call_with_optional_cancel_check` to Hailuo orchestrator), `orchestrators/hailuo_multi_clip_orchestrator.py`, `providers/hailuo_browser_provider.py`, `providers/hailuo_download_provider.py` (11F-b cancel checkpoints receive live signal when `cancel_check` is supplied).

---

## Files Modified — Validator Isolation (Harness Only)

| File | Change |
|------|--------|
| `project_brain/validate_10k_b_operations_backend.py` | Entry/exit registry cleanup; `try/finally` on `disp_10k_val_cancel` registration |
| `project_brain/validate_10k_matrix.py` | Entry/exit registry cleanup |
| `project_brain/validate_11e_common.py` | Cleanup before/after each nested subprocess regression |
| `project_brain/validate_10j_matrix.py` | `try/finally` + cleanup in 10J-c job test |
| `project_brain/validate_10k_d_worker_cancel.py` | Entry/exit cleanup for cooperative cancel session |
| `project_brain/validate_11e_e_runtime_cancel_wiring.py` | Test renamed to `provider_accepts_hailuo_browser` (expects True after Hailuo opt-in) |

**No production runtime, provider, router, or UI files were changed by the isolation fix.**

---

## Runtime / Provider Boundary

```
ProviderRuntimeEngine._execute_clips
  → build_runtime_cancel_check(store, session_id)
  → VideoProviderRouter.generate_clips(..., cancel_check=...)
  → call_with_optional_cancel_check(orchestrator.run, ..., cancel_check=...)
  → HailuoMultiClipOrchestrator.run / HailuoDownloadProvider(cancel_check=...)
```

| Layer | Behavior |
|-------|----------|
| `provider_accepts_runtime_cancel("hailuo" \| "hailuo_browser")` | Returns `True` |
| `call_with_optional_cancel_check` | Injects `cancel_check` only when callee supports it |
| Runway / MiniMax / stub paths | Unchanged — no `cancel_check` injection when unsupported |
| `HailuoCancelledError` | Classified cooperative; code `OPERATIONS_CANCELLED` |

---

## cancel_check Wiring Behavior

- **Router:** Passes live `cancel_check` to `HailuoMultiClipOrchestrator.run` when provider is `hailuo` or `hailuo_browser`.
- **Runtime engine:** Builds session-backed cancel check from `operations_control.cancel_requested`; passes into router on clip execution.
- **Orchestrator / download:** 11F-b checkpoints call injected `cancel_check` during generation wait, download, and between clips.
- **Backward compatibility:** Providers without `cancel_check` parameter continue to work via optional injection.

---

## Partial Artifact Behavior

On cooperative Hailuo cancel during provider call:

| Outcome | Value |
|---------|-------|
| Session / runtime state | `CANCELLED` |
| Failure code | `OPERATIONS_CANCELLED` (not `PROVIDER_RUNTIME_ERROR`) |
| Reject code | Operator cancel reject code (`CANCEL_REJECT_CODE`) |
| Partial paths / clip_results | Preserved in cancellation metadata |
| Source files | Not deleted |
| Artifact metadata key | `hailuo_clip_result` on partial artifact entries |
| Dispatch success | `False` (expected — cancelled, not completed) |

---

## Validation Results

### Core 11F-d tests

**22/22 PASS** — all Phase 11F-d cancel-wiring assertions pass independently of nested regression gates:

- Router / runtime engine / orchestrator / download provider receive `cancel_check`
- Live cooperative cancel → `CANCELLED` + `OPERATIONS_CANCELLED`
- Partial artifacts preserved; not `FAILED` or `COMPLETED`

### Full matrix (`validate_11f_d_hailuo_runtime_cancel`)

| Run | Result | Notes |
|-----|--------|-------|
| Chained run (11F-b → 11F-c → 11F-d in one shell) | **26/27** | One transient nested-regression gate failure (`validate_11e_e_still_passes`) due to validator order / `active_jobs.json` pollution from prior nested suites — not a 11F-d core defect |
| After registry cleanup harness fix, **separate re-run** | **27/27 PASS** | `py -3.11 -m project_brain.validate_11f_d_hailuo_runtime_cancel` |
| Nested regressions (when matrix green) | PASS | `validate_11e_e`, `validate_11f_a`, `validate_11f_b`, `validate_11f_c`, `validate_10k_matrix` |

```bash
# Core slice (mock/fake only — no browser automation or API calls)
py -3.11 -m project_brain.validate_11f_d_hailuo_runtime_cancel  # 27/27 PASS (post-cleanup re-run)
```

---

## Validator Isolation Fix (Post-11F-d)

**Root cause:** `validate_10k_b_operations_backend` left `disp_10k_val_cancel` registered for session `exec_10k_val_running` when the cancel-with-active-job block exited without cleanup, causing `JobAlreadyActiveError` on subsequent nested runs.

**Cleanup strategy:**

1. Shared `cleanup_validation_registry()` removes validation-scoped jobs by known job IDs and session-ID prefixes.
2. Entry/exit cleanup in validators that register jobs.
3. `try/finally` around all test job registrations.
4. Pre/post cleanup in `append_regression_checks` between nested subprocess invocations.

**Production code unchanged by this fix** — only validation harness files listed above.

---

## Scope Compliance

| Rule | Status |
|------|--------|
| Runtime-to-Hailuo cancel wiring only | ✅ |
| No API / UI / default provider / failover | ✅ |
| Runway 11E-e cancel behavior preserved | ✅ |
| MiniMax / stub paths unchanged | ✅ |
| Mock-only validation (no real Hailuo browser/API) | ✅ |
| Phase 10J, 10K, 11A–11F-c behavior preserved | ✅ |

---

## Known Limitations

1. **Chained full-regression runner:** Running multiple heavy validators sequentially in one shell (e.g. 11F-b → 11F-c → 11F-d) may still surface transient nested-regression failures if disk state is polluted before cleanup runs. Prefer isolated re-runs or ensure cleanup helper is invoked. Future hardening of a dedicated chained-regression runner may be warranted.
2. Hailuo API path remains metadata-only — no live cancel wiring (deferred to 11F-g).
3. Failover advisory for Hailuo not implemented (11F-e scope).
4. Session artifact root copy still uses generic runtime canonicalization.

---

## Next Recommended Slice

**11F-e — Hailuo Failover Advisory**

- Extend failover policy hints for Hailuo browser failures
- Read-only advisory; no automatic failover execution

**11F-f — Final Hailuo matrix + handoff**

- Consolidated regression matrix and project brain handoff update
