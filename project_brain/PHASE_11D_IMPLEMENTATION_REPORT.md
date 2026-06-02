# Phase 11D — Provider Selection Engine

**Status:** Complete  
**Date:** 2026-05-28  
**Validation:** `validate_11d_provider_selection` **17/17 PASS** (includes 11A, 11B, 11C, 10K regression)

---

## Summary

Phase 11D adds a **standalone provider selection engine** that ranks providers for a requested capability using capability registry (11A), cost estimates (11B), and failover metadata (11C). The engine is **metadata-only**: it does not dispatch providers, execute failover, enforce budgets, or mutate runtime/router/UI behavior.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/providers/provider_selection_engine.py` | Selection preferences, scoring model, ranking APIs |
| `project_brain/validate_11d_provider_selection.py` | Validation (17 tests + regressions) |
| `project_brain/PHASE_11D_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/providers/__init__.py` | Export selection engine types (`ProviderSelectionEngine`, `SelectionPreferences`, `SelectionResult`, optimize constants) |

**Unchanged:** `ProviderRuntimeEngine`, `VideoProviderRouter`, worker, UI, operations control, 11A/11B/11C modules (behavior preserved).

---

## Selection Schema

### `SelectionPreferences`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `preferred_provider` | `str \| None` | `None` | Soft-prefer a provider (boosts failover position score) |
| `mode_preference` | `str` | `any` | `api` / `browser` / `any` — blocks non-matching modes when strict |
| `max_cost` | `float \| None` | `None` | Block candidates above estimated cost |
| `allow_unknown_cost` | `bool` | `True` | Allow unknown-cost candidates; when `False`, blocks unknown cost |
| `excluded_providers` | `tuple[str, ...]` | `()` | Hard-exclude provider IDs |
| `require_async_jobs` | `bool` | `False` | Require `supports_async_jobs` from registry |
| `require_cost_estimation` | `bool` | `False` | Require `supports_cost_estimation` from registry |
| `optimize_for` | `str` | `balanced` | Scoring weight profile: `cost` / `quality` / `speed` / `reliability` / `balanced` |
| `estimate_quantity` | `float` | `1.0` | Quantity passed to cost estimator |

Construct from dict via `SelectionPreferences.from_dict(data)`. Converts to `FailoverConstraints` via `to_failover_constraints()` for 11C integration.

### `SelectionResult`

| Field | Description |
|-------|-------------|
| `capability` | Requested capability |
| `selected_provider` | Top-ranked non-blocked provider (or `None`) |
| `ranked_candidates[]` | Active candidates sorted by total score |
| `blocked_candidates[]` | Blocked candidates with reasons |
| `warnings[]` | Selection warnings (failover + preference conflicts) |
| `scoring_breakdown` | Top candidate dimension scores + weights |
| `estimated_cost` | Top candidate estimated cost |
| `failover_plan` | Full 11C failover plan dict (if available) |
| `is_executable_later` | Whether failover plan indicates future executability |
| `optimize_for` | Weight profile used |

### `RankedCandidate`

Per-candidate: `provider_id`, `rank`, `total_score`, `blocked`, `block_reason`, `estimated_cost`, `currency`, `cost_model`, `cost_confidence`, `scoring` (`ScoringBreakdown`), `warning`.

---

## Scoring Model

Eight scoring dimensions (each 0.0–1.0), combined via weighted sum:

| Dimension | Source |
|-----------|--------|
| `capability_support` | 11A registry — 1.0 if supports capability, else 0.0 |
| `cost_score` | 11B estimate — normalized inverse cost; free=1.0, unknown=0.35 |
| `confidence_score` | 11B cost confidence — high=1.0, medium=0.75, low=0.5, unknown=0.25 |
| `speed_score` | Internal placeholder profile (not official benchmark) |
| `quality_score` | Internal placeholder profile (not official benchmark) |
| `availability_score` | Internal placeholder profile + small registry bonuses |
| `mode_match_score` | 1.0 if mode matches preference, 0.0 if blocked mode |
| `failover_position_score` | 11C chain order — earlier position = higher score |

### Weight profiles (`optimize_for`)

| Mode | Emphasis |
|------|----------|
| `cost` | cost_score 45% |
| `quality` | quality_score 45% |
| `speed` | speed_score 45% |
| `reliability` | availability_score 30%, failover_position 20%, confidence 15% |
| `balanced` | Equal 12.5% across all dimensions |

All results include `benchmark_note`: *"Internal placeholder benchmark score — not an official provider benchmark."*

### Blocking rules (before scoring)

1. Failover plan marks provider blocked → `FAILOVER_PLAN_BLOCKED`
2. Capability unsupported → `CAPABILITY_UNSUPPORTED`
3. In `excluded_providers` → `EXCLUDED_BY_PREFERENCE`
4. Not in registry → `PROVIDER_NOT_IN_REGISTRY`
5. Cost estimator blocks → `COST_ESTIMATE_BLOCKED`
6. `require_async_jobs` / `require_cost_estimation` unmet
7. `mode_preference` api/browser mismatch
8. Unknown cost with `allow_unknown_cost=False` → `COST_UNKNOWN_BLOCKED`
9. `max_cost` exceeded → `MAX_COST_EXCEEDED`
10. `max_cost` set + unknown cost + `allow_unknown_cost=False` → `MAX_COST_UNKNOWN_BLOCKED`

---

## Engine APIs

```python
from content_brain.providers import (
    ProviderSelectionEngine,
    SelectionPreferences,
    OPTIMIZE_COST,
    OPTIMIZE_QUALITY,
)

engine = ProviderSelectionEngine.load(".")

# Rank all eligible providers
result = engine.rank_providers("text_to_video")

# Same as rank_providers (alias)
best = engine.select_best("text_to_video", SelectionPreferences(optimize_for=OPTIMIZE_COST))

# Compare subset
compare = engine.compare_candidates("text_to_video", ["runway", "hailuo_browser"])

# Human-readable explanation
lines = engine.explain_selection(result)
```

---

## Integration Notes

| Layer | Usage |
|-------|-------|
| **11A — ProviderCapabilityRegistry** | Candidate universe, capability support checks, mode/async/cost-estimation flags |
| **11B — ProviderCostEstimator** | Per-candidate cost estimates, confidence, blocking for max_cost |
| **11C — ProviderFailoverPlanner** | Failover chain ordering, position scoring, blocked steps, `is_executable_later`, warnings |

Candidate universe = failover chain order + registry providers for capability + preferred provider prepended.

Cost normalization uses max observed cost across active candidates in the same ranking pass.

Preferences map directly to `FailoverConstraints` so 11C and 11D share constraint semantics.

**No integration with:** `ProviderRuntimeEngine.dispatch`, `VideoProviderRouter.generate_clips`, UI panels, budget enforcement, or failover execution.

---

## Validation Results

```
py -3.11 -m project_brain.validate_11d_provider_selection
```

| Test | Result |
|------|--------|
| providers_ranked_text_to_video | PASS |
| select_best_supported | PASS |
| unsupported_capability_blocked | PASS |
| excluded_provider_removed | PASS |
| mode_preference_api | PASS |
| mode_preference_browser | PASS |
| max_cost_blocks_expensive | PASS |
| optimize_for_cost_changes_ranking | PASS |
| optimize_for_quality_changes_ranking | PASS |
| explanation_generated | PASS |
| compare_candidates | PASS |
| no_runtime_dispatch | PASS |
| no_router_dispatch | PASS |
| validate_11a_still_passes | PASS (24/24) |
| validate_11b_still_passes | PASS (15/15) |
| validate_11c_still_passes | PASS (18/18) |
| validate_10k_matrix_still_passes | PASS (89/89) |

**Summary: 17/17 PASS**

Example `text_to_video` ranking (balanced): `runway, runway_browser, hailuo_api, hailuo_browser, luma`

---

## Limitations

1. **Placeholder benchmarks** — speed/quality/availability scores are internal placeholders, not measured provider performance.
2. **No dispatch** — selection output is advisory; runtime still uses existing router/dispatch paths.
3. **No budget enforcement** — `max_cost` blocks in ranking only; no spend tracking or caps.
4. **No failover execution** — failover plan is attached for documentation; 11C execution wiring is future work.
5. **Static profiles** — provider speed/quality/availability not loaded from external config yet.
6. **Single capability per call** — no multi-capability bundle selection.
7. **Cost catalog placeholders** — inherits 11B placeholder pricing limitations.

---

## Next Recommended Slice

**Phase 11E — Runway Hardening** (per `PHASE_11_PROVIDER_EXPANSION_PLAN.md`):

- Wire selection engine into pre-dispatch advisory path (read-only hook)
- Harden Runway API + browser provider adapters
- Optional: expose selection explanation in Operations Console (read-only panel)

Alternatively, continue metadata layers:

- **11F — Provider Health Signals** (live availability, rate-limit awareness)
- **11G — Selection → Failover Execution Bridge** (connect 11D output to 11C execution when approved)

---

## Regression Commands

```bash
py -3.11 -m project_brain.validate_11d_provider_selection
py -3.11 -m project_brain.validate_11a_capability_registry
py -3.11 -m project_brain.validate_11b_cost_catalog
py -3.11 -m project_brain.validate_11c_failover_policy
py -3.11 -m project_brain.validate_10k_matrix
```
