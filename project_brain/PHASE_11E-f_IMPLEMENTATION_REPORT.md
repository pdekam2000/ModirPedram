# Phase 11E-f — Runway Failover Readiness Advisory

**Status:** Complete  
**Date:** 2026-05-28  
**Validation:** `validate_11e_f_runway_failover_advisory` **26/26 PASS** (includes 11E-e, 10K regression)

---

## Summary

Phase 11E-f adds **advisory-only** failover readiness metadata for Runway session outcomes. When Runway API/browser execution ends in FAILED, CANCELLED, or artifact validation reject, the runtime attaches `operations.failover_advisory` using 11C failover planning and 11D provider selection — **without executing failover, re-dispatch, retry, or requeue**.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/runway_failover_advisory.py` | Advisory builder + operations attachment helper |
| `project_brain/validate_11e_f_runway_failover_advisory.py` | Mock-only validation (26 tests + regressions) |
| `project_brain/PHASE_11E-f_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/provider_runtime_engine.py` | Attach advisory on `_mark_failed`, `_mark_cooperative_cancelled`, `_mark_artifact_validation_failed` |

**Unchanged:** UI, router dispatch, failover execution, retry/requeue engines, active default, Runway providers.

---

## Advisory Schema

Stored at `execution_runtime.operations.failover_advisory`:

| Field | Type | Description |
|-------|------|-------------|
| `advisory_version` | str | `"11e_f_v1"` |
| `advisory_only` | bool | Always `true` |
| `evaluated_at` | str | Timestamp |
| `outcome` | str | `FAILED` \| `CANCELLED` |
| `failure_code` | str \| null | Runtime failure code |
| `current_provider` | str | Runway provider id |
| `capability` | str | e.g. `text_to_video` |
| `failover_recommended` | bool | Whether fallback is suggested |
| `failover_allowed` | bool | Recommended + capability match |
| `reason` | str | Classified reason (see below) |
| `blocked_reason` | str \| null | Why failover blocked |
| `candidate_chain` | list[str] | Unblocked 11C chain candidates |
| `preferred_next_provider` | str \| null | Next provider after current |
| `partial_artifacts_present` | bool | Partial clips exist |
| `partial_artifacts_safe_to_reuse` | bool | Default `false` |
| `partial_artifact_count` | int | Count of partial paths |
| `partial_paths` | list[str] | Preserved paths (not deleted) |
| `cost_warning` | str \| null | Unknown/low-confidence cost note |
| `capability_match` | bool | Next provider supports capability |
| `failover_plan` | dict | 11C policy/chain summary |
| `provider_selection` | dict | 11D ranking summary |

---

## Integration with 11C / 11D

| Layer | Usage |
|-------|--------|
| **11C** `ProviderFailoverPlanner.plan_failover` | Builds candidate chain; excludes current provider |
| **11D** `ProviderSelectionEngine.rank_providers` | Ranks alternatives; warnings merged into advisory |
| **11A** `ProviderCapabilityRegistry` | `capability_match` for next provider |
| **11B** `ProviderCostEstimator` | `cost_warning` when estimate unknown |

No provider is dispatched. Planning metadata only.

---

## Failure / Cancel Behavior

| Outcome | `failover_recommended` | `reason` |
|---------|------------------------|----------|
| Operator cancel (`CANCELLED`, `OPERATIONS_CANCELLED`) | `false` | `operator_cancelled` |
| Provider timeout / runtime error | `true` (if candidate exists) | `provider_failure` / `provider_timeout` |
| Artifact validation reject | `true` (if candidate exists) | `artifact_validation_reject` |
| Download / too-small artifact | `true` (if candidate exists) | `download_failed` |
| `CAPABILITY_RUNTIME_UNSUPPORTED` | `false` | `capability_unsupported` |
| `PROVIDER_DISABLED` | `false` | `provider_disabled` |

Cancel path always sets `failover_allowed=false` and `blocked_reason=operator_cancelled`.

---

## Partial Artifact Behavior

- Paths read from `operations.cancellation.partial_paths`, partial `clip_results`, and `provider_clip_results`
- Files are **never deleted** by advisory logic
- `partial_artifacts_safe_to_reuse=false` by default (conservative)
- Count and paths included in advisory for future chaining review

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11e_f_runway_failover_advisory   # 26/26 PASS
```

| Test | Result |
|------|--------|
| Failed Runway session gets advisory | PASS |
| Failover recommended on provider failure | PASS |
| Cancelled session blocks failover | PASS |
| Partial artifacts marked, not deleted | PASS |
| 11C candidate chain in advisory | PASS |
| 11D selection metadata in advisory | PASS |
| Unsupported capability blocks failover | PASS |
| Unknown cost warning | PASS |
| No second provider dispatch | PASS |
| No retry/requeue triggered | PASS |
| 11E-e regression | PASS |
| 10K matrix | PASS |

---

## Scope Compliance

| Requirement | Status |
|-------------|--------|
| Advisory only | ✅ `advisory_only: true` |
| No failover execution | ✅ |
| No API / browser automation in validation | ✅ |
| No auto-retry / requeue | ✅ |
| No UI changes | ✅ |
| 11C/11D integration | ✅ |
| Partial artifact rules | ✅ |
| Cancel blocks recommendation | ✅ |
| Preserve 10J/10K/11A–11E-e | ✅ |

---

## Known Limitations

1. **Advisory is Runway-specific** — non-Runway providers do not receive `failover_advisory` (by design for 11E-f scope).
2. **Partial reuse always false** — safe reuse requires future cross-provider artifact compatibility analysis.
3. **Capability default** — video sessions default to `text_to_video`; explicit non-video capabilities need bundle metadata.
4. **Not wired to UI** — metadata is session/operations only until a future ops panel slice consumes it.

---

## Next Recommended Slice

**11E-g — Runway hardening closure / handoff update:** consolidate 11E-a–f reports, update `FULL_PROJECT_HANDOFF.md` and `current_state.md`, optional UI read-only display of `failover_advisory` in operations drawer (only if product requests).

Alternative: **11F** — extend advisory pattern to Hailuo/MiniMax providers using same 11C/11D layers.

---

## Quick Reference

```python
from content_brain.execution.runway_failover_advisory import build_runway_failover_advisory

advisory = build_runway_failover_advisory(
    session=session,
    execution_runtime=runtime,
    outcome="FAILED",
    failure_code="PROVIDER_TIMEOUT",
    project_root=".",
)
# advisory["failover_recommended"], advisory["preferred_next_provider"]
```

Advisory is attached automatically by `ProviderRuntimeEngine` on terminal Runway FAILED/CANCELLED paths.
