# Phase 11E-e — Runtime Cancel Wiring for Runway Providers

**Status:** Complete  
**Date:** 2026-05-28  
**Validation:** `validate_11e_e_runtime_cancel_wiring` **26/26 PASS** (includes 11E-b/c/d, 10K regression)

---

## Summary

Phase 11E-e wires **live runtime `cancel_check`** from `ProviderRuntimeEngine` through `VideoProviderRouter` into Runway API and browser providers. Cooperative cancellation during provider execution now ends in **CANCELLED** (not FAILED), maps to **`OPERATIONS_CANCELLED`** in runtime failure metadata, and preserves partial artifacts via 11E-d bundles.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/provider_cancel_wiring.py` | Cancel helper: feature detection, session cancel_check builder, partial artifact extraction |
| `project_brain/validate_11e_e_runtime_cancel_wiring.py` | Mock-only validation (26 tests + regressions) |
| `project_brain/PHASE_11E-e_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/provider_runtime_engine.py` | Builds `cancel_check` from session; passes to router; catches `RunwayCancelledError` → CANCELLED; partial artifact propagation; same-file canonicalize guard |
| `core/video_provider_router.py` | Accepts optional `cancel_check`; forwards to Runway API/browser via `call_with_optional_cancel_check` |

**Unchanged:** Runway provider checkpoint logic (11E-b/c), UI, active default (`runway_browser`), failover, I2V.

---

## Runtime / Provider Boundary

```
ProviderRuntimeEngine.dispatch()
  └─ _execute_clips(session_id=...)
       ├─ cancel_check = build_runtime_cancel_check(store, session_id)
       └─ VideoProviderRouter.generate_clips(..., cancel_check=cancel_check)
            ├─ runway / runway_api → RunwayVideoProvider.generate_clips(cancel_check=...)
            ├─ runway_browser → RunwayBrowserOrchestrator.run(cancel_check=...)
            └─ hailuo / minimax → unchanged (cancel_check omitted via signature detection)
```

`cancel_check` reads `operations_control.cancel_requested` from the live session store (10K-d cooperative cancel path).

---

## cancel_check Wiring Behavior

| Component | Behavior |
|-----------|----------|
| `build_runtime_cancel_check` | Reloads session; returns True when `cancel_requested` set |
| `supports_cancel_check` | `inspect.signature` — only passes kwarg when parameter exists |
| `call_with_optional_cancel_check` | Kwargs-safe invoke; no breakage for Hailuo/MiniMax |
| `provider_accepts_runtime_cancel` | Documents Runway API/browser keys |

Backward compatible: providers without `cancel_check` parameter receive no extra kwargs.

---

## Partial Artifact Behavior

On `RunwayCancelledError` during `_execute_clips`:

1. `_execute_clips` canonicalizes `partial_paths` into session artifact root (11E-d records preserved)
2. Re-raises with updated paths + `clip_results` in `details`
3. `dispatch()` catches → `_mark_cooperative_cancelled()` with:
   - `failure.code = OPERATIONS_CANCELLED`
   - `reject_code = OPERATOR_CANCELLED` (worker 10K-d compatibility)
   - `operations.cancellation.partial_paths` + `clip_results`
   - `provider_clip_results` on runtime when present
   - Artifacts **not deleted**

Pre-execution cancel (flag set before `_execute_clips`) still uses existing early-exit path with empty partials.

---

## Error Taxonomy

| Scenario | Session state | `failure.code` | `DispatchResult.reject_code` |
|----------|---------------|----------------|------------------------------|
| Cooperative cancel during Runway execution | `CANCELLED` | `OPERATIONS_CANCELLED` | `OPERATOR_CANCELLED` |
| Generic provider exception | `FAILED` | `PROVIDER_RUNTIME_ERROR` | `PROVIDER_RUNTIME_ERROR` |
| Pre-run cancel flag | `CANCELLED` | `OPERATOR_CANCELLED` | `OPERATOR_CANCELLED` |

Provider-raised cancel uses `RunwayCancelledError` (`OPERATIONS_CANCELLED` from 11E-b).

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11e_e_runtime_cancel_wiring   # 26/26 PASS
```

| Area | Result |
|------|--------|
| Router → Runway API cancel_check | PASS |
| Router → Runway browser cancel_check | PASS |
| RuntimeEngine → router cancel_check | PASS |
| Legacy providers ignore cancel_check | PASS |
| Live cancel → CANCELLED not FAILED | PASS |
| OPERATIONS_CANCELLED failure code | PASS |
| Partial paths preserved | PASS |
| No artifact deletion | PASS |
| 11E-b / 11E-c / 11E-d regressions | PASS |
| 10K matrix | PASS |

Mock/fake only — no Runway API, no browser automation.

---

## Scope Compliance

| Requirement | Status |
|-------------|--------|
| Runtime-to-provider cancel wiring | ✅ |
| Backward compatible for non-Runway providers | ✅ |
| Runway API/browser consume live cancel_check | ✅ |
| Partial artifacts on cancel | ✅ |
| CANCELLED not FAILED / not COMPLETED | ✅ |
| OPERATIONS_CANCELLED taxonomy | ✅ |
| No UI / default / I2V / failover changes | ✅ |

---

## Known Limitations

1. **Hailuo/MiniMax** do not receive runtime cancel mid-generation — only Runway paths are cancel-aware today.
2. **Pre-dispatch cancel** still short-circuits before provider call; partials only when provider started.
3. **Worker heartbeat cancel** relies on session store reload per checkpoint — very fast cancels may race before first checkpoint (existing 10K-d behavior).

---

## Next Recommended Slice

**11E-f — Failover readiness advisory:** surface Runway cancel/partial state to provider selection / failover policy without automatic failover execution.

Alternative: extend `cancel_check` to Hailuo orchestrator in a future browser-hardening slice (parallel to 11E-c pattern).

---

## Quick Reference

```python
from content_brain.execution.provider_cancel_wiring import build_runtime_cancel_check

cancel_check = build_runtime_cancel_check(store, session_id)
router.generate_clips(prompts, provider_override="runway_browser", cancel_check=cancel_check)
```
