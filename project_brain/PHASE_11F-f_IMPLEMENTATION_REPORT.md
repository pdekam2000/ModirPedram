# Phase 11F-f — Failover Advisory UI Visibility

**Status:** Complete  
**Date:** 2026-05-30  
**Prerequisites:** Phase 11F-e Hailuo failover advisory metadata · Runway 11E-f advisory baseline

---

## Summary

The Execution Center **Provider Runtime** observability panel now displays **read-only failover advisory** metadata from `execution_runtime.operations.failover_advisory` when present. Applies to Hailuo and Runway sessions that received advisory metadata in 11E-f / 11F-e. **No failover execution**, retry, requeue, dispatch, or provider/API/browser calls were added.

---

## Files Created

| File | Purpose |
|------|---------|
| `ui/web/src/utils/failoverAdvisory.ts` | Legacy-safe resolver + display helpers |
| `ui/web/src/components/FailoverAdvisoryPanel.tsx` | Read-only advisory section component |
| `project_brain/validate_11f_f_failover_advisory_ui.py` | Static + API fixture validation (26 core + 3 nested) |
| `project_brain/PHASE_11F-f_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `ui/web/src/components/RuntimeObservability.tsx` | Conditionally renders `FailoverAdvisoryPanel` when advisory exists |
| `ui/web/src/App.css` | Styles for `.runtime-failover-advisory` section |

**Unchanged:** `content_brain/execution/*` (11F-e advisory logic), `ui/api/*` backend, router, providers, orchestrators, action handlers.

---

## UI Behavior

### When advisory exists

A **Failover Advisory** section appears in `RuntimeObservabilityPanel` (Session Drawer → Provider Runtime, and Active Runtime Jobs compact view):

| Field | Source |
|-------|--------|
| Recommended | `failover_recommended` |
| Reason | `reason` |
| Current provider | `current_provider` |
| Next provider | `preferred_next_provider` or 11D `selected_provider` |
| Failover allowed | `failover_allowed` |
| Blocked reason | `blocked_reason` (when present) |
| Capability match | `capability_match` |
| Cost warning | `cost_warning` |
| Partial artifacts | `partial_artifact_count` when `partial_artifacts_present` |
| Partial reusable | `partial_artifacts_safe_to_reuse` |
| Provider selection (11D) | Expandable: ranked candidates + warnings |
| Failover chain (11C) | Expandable: policy chain + warnings |

Banner text: **"Advisory only — no automatic failover"**

### When advisory missing (legacy sessions)

- Section is **not rendered**
- Existing fields continue to show `—` as before
- No errors or crashes

### Data path

```
session.execution_runtime.operations.failover_advisory
  → GET /sessions/{id}/runtime/status (execution_runtime passthrough)
  → resolveFailoverAdvisory(status)
  → FailoverAdvisoryPanel (display only)
```

---

## Safety Constraints

| Constraint | Status |
|------------|--------|
| UI display only | ✅ No action buttons added |
| No failover execution | ✅ No dispatch/failover planner calls in UI |
| No retry / requeue | ✅ No `postSessionAction` / action hooks |
| No provider/API/browser calls | ✅ Static forbidden-token scan passes |
| 11F-e behavior preserved | ✅ Backend advisory attachment unchanged |
| Partial artifacts preserved | ✅ Display-only; no deletion logic |
| Legacy sessions safe | ✅ Missing advisory → section hidden |

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11f_f_failover_advisory_ui  # 29/29 PASS
cd ui/web && npm run build                                    # PASS (tsc + vite)
```

| Test area | Result |
|-----------|--------|
| Advisory section renders when data exists | PASS |
| Missing advisory does not crash | PASS |
| Cancelled advisory: `failover_recommended=false`, `operator_cancelled` | PASS |
| Failed advisory: next provider + 11C/11D metadata | PASS |
| Partial artifacts: count + `safe_to_reuse=false` | PASS |
| No execution/retry/requeue/provider calls in UI bundle | PASS |
| Nested `validate_11f_e` | PASS |
| Nested `validate_11f_d` | PASS |
| Nested `validate_10k_matrix` | PASS |

---

## Scope Compliance

| Rule | Status |
|------|--------|
| UI visibility only | ✅ |
| No automatic failover / retry / requeue | ✅ |
| Preserve 11F-e advisory metadata | ✅ |
| Preserve partial artifact handling | ✅ |
| Legacy session safety | ✅ |
| No production runtime changes | ✅ |

---

## Known Limitations

1. Advisory section is observability-only — operator must manually choose next steps (requeue/retry) via existing Actions tab.
2. Compact Active Runtime Jobs view shows core advisory fields but collapses 11C/11D detail blocks.
3. No dedicated table-column chip for failover advisory (drawer + active jobs panel only).
4. Streamlit `ui/app.py` unchanged — advisory visible in Execution Center web UI only.

---

## Next Recommended Slice

**11F-g — Final Hailuo Hardening Matrix + Handoff**

- Consolidated 11F-a through 11F-f validation matrix
- Update project brain handoff docs
- Optional unified advisory display tests across Runway + Hailuo demo fixtures
