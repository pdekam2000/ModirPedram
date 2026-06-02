# Phase 11F-e — Hailuo Failover Readiness Advisory

**Status:** Complete  
**Date:** 2026-05-30  
**Prerequisites:** Phase 11F-d runtime cancel wiring · Runway 11E-f advisory baseline · 11C failover policy · 11D provider selection

---

## Summary

Hailuo browser/API sessions that end in **FAILED**, **CANCELLED**, artifact rejection, timeout, download failure, or provider-disabled states now receive **advisory-only** failover metadata under `execution_runtime.operations.failover_advisory`. Planning uses `ProviderFailoverPlanner` (11C) and `ProviderSelectionEngine` (11D) — **no failover execution**, re-dispatch, retry, or requeue.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/hailuo_failover_advisory.py` | Hailuo advisory builder + operations attachment helper |
| `project_brain/validate_11f_e_hailuo_failover_advisory.py` | Mock-only advisory matrix (28 core + 2 nested regressions) |
| `project_brain/PHASE_11F-e_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/provider_runtime_engine.py` | Renamed `_attach_runway_failover_advisory` → `_attach_failover_advisory`; tries Runway then Hailuo builders on FAILED, CANCELLED, and artifact-validation paths |

**Unchanged:** UI, router dispatch logic, failover policy execution, provider APIs, browser automation.

---

## Advisory Schema (`11f_e_v1`)

| Field | Type | Description |
|-------|------|-------------|
| `advisory_only` | bool | Always `true` — metadata only |
| `advisory_version` | string | `11f_e_v1` |
| `evaluated_at` | string | Timestamp |
| `outcome` | string | `FAILED` \| `CANCELLED` |
| `failure_code` | string \| null | Taxonomy code |
| `failure_message` | string \| null | Human-readable detail |
| `current_provider` | string | e.g. `hailuo_browser` |
| `capability` | string | e.g. `text_to_video` |
| `failover_recommended` | bool | Whether a next provider is suggested |
| `failover_allowed` | bool | Recommended + capability match |
| `reason` | string | Classified advisory reason |
| `blocked_reason` | string \| null | Why failover blocked |
| `candidate_chain` | list[str] | Unblocked 11C chain providers |
| `preferred_next_provider` | string \| null | Next candidate after current |
| `partial_artifacts_present` | bool | Any partial paths detected |
| `partial_artifacts_safe_to_reuse` | bool | Default `false` |
| `partial_artifact_count` | int | Count of partial paths |
| `partial_paths` | list[str] | Preserved path references |
| `cost_warning` | string \| null | Unknown/low-confidence cost note |
| `capability_match` | bool | Next provider supports capability |
| `failover_plan` | object | 11C policy id, chain, warnings |
| `provider_selection` | object | 11D ranked candidates + warnings |

**Storage path:** `session.execution_runtime.operations.failover_advisory`

---

## Integration with 11C / 11D

| Component | Usage |
|-----------|--------|
| `ProviderFailoverPlanner.plan_failover()` | Builds candidate chain; excludes current Hailuo provider |
| `ProviderSelectionEngine.rank_providers()` | Ranked fallback candidates + selection warnings |
| `ProviderCapabilityRegistry.supports()` | Validates capability match for next provider |
| `ProviderCostEstimator.estimate()` | Surfaces `cost unknown` when model is `unknown` |

No provider is invoked after advisory attachment.

---

## Failure Behavior

| Failure type | Advisory behavior |
|--------------|-------------------|
| `PROVIDER_TIMEOUT` | May recommend next 11C chain provider |
| `DOWNLOAD_FAILED` / artifact reject codes | May recommend failover; partial paths preserved |
| `PROVIDER_RUNTIME_ERROR` | May recommend failover with cost warning |
| `CAPABILITY_RUNTIME_UNSUPPORTED` | `failover_allowed=false`, `blocked_reason=capability_unsupported` |
| `HAILUO_BROWSER_DISABLED` / `PROVIDER_DISABLED` | `failover_allowed=false`, `blocked_reason=provider_disabled` |

Always includes `current_provider` and `preferred_next_provider` when recommendation is made.

---

## Cancel Behavior

When outcome is `CANCELLED` or failure code is `OPERATIONS_CANCELLED`:

| Field | Value |
|-------|-------|
| `failover_recommended` | `false` |
| `failover_allowed` | `false` |
| `reason` | `operator_cancelled` |
| `blocked_reason` | `operator_cancelled` |

No fallback suggested after manual/cooperative cancel.

---

## Partial Artifact Behavior

- Partial paths extracted from `operations.cancellation`, `artifacts_by_category` (`hailuo_clip_result`), and `provider_clip_results`
- Files are **never deleted** by advisory logic
- `partial_artifacts_safe_to_reuse` defaults to **`false`**
- `partial_artifact_count` and `partial_paths` included in advisory

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11f_e_hailuo_failover_advisory  # 30/30 PASS
```

| Area | Tests |
|------|-------|
| Failed Hailuo advisory + failover recommendation | PASS |
| Cancelled session blocks recommendation | PASS |
| Partial artifacts preserved, not reusable by default | PASS |
| Candidate chain from 11C | PASS |
| Provider selection metadata from 11D | PASS |
| Unsupported capability / provider disabled blocks | PASS |
| Unknown cost warning | PASS |
| Runtime FAILED/CANCELLED attaches advisory | PASS |
| No second dispatch / retry / requeue | PASS |
| Nested `validate_11f_d` | PASS |
| Nested `validate_10k_matrix` | PASS |

**Mock/fake only** — no browser automation, no Hailuo/MiniMax API calls.

---

## Scope Compliance

| Rule | Status |
|------|--------|
| Advisory metadata only | ✅ |
| No automatic failover / re-dispatch / retry / requeue | ✅ |
| No UI changes | ✅ |
| No provider API calls | ✅ |
| Partial artifacts preserved, not deleted | ✅ |
| Runway 11E-f advisory preserved (Runway builder tried first) | ✅ |
| Phase 10J, 10K, 11A–11F-d preserved | ✅ |

---

## Known Limitations

1. Partial artifacts marked not reusable by default — cross-provider reuse rules deferred.
2. Hailuo API path advisory uses same planner chain as browser; API not implemented (11F-g).
3. Advisory does not persist operator acknowledgment or auto-create requeue items.
4. Chained full-regression runners may still be slow; prefer isolated validator re-runs when debugging.

---

## Next Recommended Slice

**11F-f — Final Hailuo Hardening Matrix + Handoff**

- Consolidated 11F-a through 11F-e regression matrix
- Update `FULL_PROJECT_HANDOFF.md` / `current_state.md` with Hailuo hardening closure
- Optional unified failover advisory facade (Runway + Hailuo) if duplication becomes maintenance burden
