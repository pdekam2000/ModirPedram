# Phase 11C — Provider Failover Policy Layer

**Status:** Complete  
**Date:** 2026-05-30  
**Validation:** `validate_11c_failover_policy` **18/18 PASS** (includes 11A, 11B, 10K regression)

---

## Summary

Phase 11C adds a **standalone failover policy layer** that plans provider fallback chains before dispatch. It integrates with Phase 11A (capability support) and Phase 11B (cost estimates) but **does not execute failover**, dispatch providers, or modify runtime/router/UI behavior.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/providers/provider_failover_policy.py` | Policy schema, default policies, planner APIs |
| `project_brain/validate_11c_failover_policy.py` | Validation (18 tests + regressions) |
| `project_brain/PHASE_11C_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/providers/__init__.py` | Export failover policy types |

**Unchanged:** `ProviderRuntimeEngine`, `VideoProviderRouter`, worker, UI, operations control, 11A/11B modules.

---

## Policy Schema

### `FailoverPolicy`

| Field | Description |
|-------|-------------|
| `policy_id` | Unique policy identifier |
| `capability` | Target capability (e.g. `text_to_video`) |
| `preferred_provider` | First-choice provider |
| `fallback_providers[]` | Ordered fallback candidates |
| `max_attempts` | Max non-blocked chain length |
| `allow_browser_fallback` | Permit browser-mode providers |
| `allow_api_fallback` | Permit API-mode providers |
| `allow_cross_vendor_fallback` | Permit fallback across vendor families |
| `preserve_partial_artifacts` | Design flag for future execution |
| `stop_on_cost_unknown` | Block candidates with unknown cost |
| `stop_on_low_confidence_cost` | Block low/unknown confidence estimates |
| `notes` | Human-readable policy notes |

Optional override: `config/provider_failover_policies.json`

### `FailoverConstraints` (planner input)

| Field | Description |
|-------|-------------|
| `max_cost` | Block candidates above estimated cost |
| `mode_preference` | `api` / `browser` / `any` |
| `allow_unknown_cost` | Allow unknown-cost candidates when policy permits |
| `preferred_provider` | Override policy preferred provider |
| `excluded_providers` | Hard-exclude provider IDs |
| `require_async_jobs` | Require `supports_async_jobs` |
| `require_cost_estimation` | Require `supports_cost_estimation` |
| `estimate_quantity` | Quantity passed to cost estimator |

---

## Planner API

```python
from content_brain.providers import ProviderFailoverPlanner, FailoverConstraints

planner = ProviderFailoverPlanner.load(".")

planner.get_policy("text_to_video")
planner.providers_for_failover("text_to_video")

plan = planner.plan_failover(
    "text_to_video",
    preferred_provider="runway",
    constraints=FailoverConstraints(
        mode_preference="api",
        excluded_providers=("minimax_api",),
        max_cost=1.0,
    ),
)

planner.explain_plan(plan)  # human-readable lines
```

### `FailoverPlan` result

| Field | Description |
|-------|-------------|
| `chain[]` | Ordered steps with support/cost/block status |
| `blocked_providers[]` | Providers removed from active chain |
| `reasons[]` | Block explanations |
| `warnings[]` | Non-fatal issues (e.g. unknown cost) |
| `estimated_costs[]` | Cost snapshots from 11B for active steps |
| `capability_support` | Provider → supported map from 11A |
| `is_executable_later` | `True` if at least one viable candidate exists |

---

## Default Policies

| Policy ID | Capability | Preferred | Fallback chain (ordered) |
|-----------|------------|-----------|--------------------------|
| `video_text_to_video_default` | `text_to_video` | `runway` | runway_browser → hailuo_browser → hailuo_api → minimax_api → luma → kling |
| `video_image_to_video_default` | `image_to_video` | `runway` | runway_browser → hailuo_browser → hailuo_api → kling |
| `voice_narration_default` | `narration` | `elevenlabs` | openai_tts |
| `music_generation_default` | `music_generation` | `suno` | *(none)* |
| `image_generation_default` | `image_generation` | `generic_image` | *(none)* |

Example default `text_to_video` chain (max_attempts=4):

```
runway → runway_browser → hailuo_browser → hailuo_api
```

---

## Validation Results

```
py -3.11 -m project_brain.validate_11c_failover_policy → 18/18 PASS
  (includes validate_11a, validate_11b, validate_10k_matrix)
```

| Area | Result |
|------|--------|
| Policy load + chain planning | PASS |
| Unsupported / excluded providers | PASS |
| Mode preference api/browser | PASS |
| Unknown cost warning vs block | PASS |
| Capability support from 11A | PASS |
| Plan explanation | PASS |
| No runtime/router dispatch | PASS |
| 11A / 11B / 10K regression | PASS |

---

## Limitations

1. **Planning only** — no automatic failover execution at runtime.
2. **No partial artifact replay** — `preserve_partial_artifacts` is metadata for future phases.
3. **Vendor family heuristic** — simple ID-prefix mapping for cross-vendor rules.
4. **No live availability probes** — browser/API readiness not checked (preflight remains 10J).
5. **Not wired to operations** — Retry/Requeue unchanged; no auto-failover on FAILED.

---

## Compatibility Notes

| Layer | Relationship |
|-------|--------------|
| 11A Capability Registry | Required support check before chain inclusion |
| 11B Cost Estimator | Optional cost/warning/block per policy + constraints |
| 10J Runtime / Router | Unchanged — planner never calls dispatch |
| 10K Operations | Unchanged |

---

## Next Recommended Slice

**Phase 11D — Provider Selection Engine**

- Rank providers using capability registry + cost catalog + failover plan metadata
- Strategies: `balanced`, `cost_optimized`, `quality_optimized`, `speed_optimized`, `manual`
- Still planning/metadata only until explicitly wired to session `provider_selection`

---

## Quick validation

```bash
py -3.11 -m project_brain.validate_11c_failover_policy
```
