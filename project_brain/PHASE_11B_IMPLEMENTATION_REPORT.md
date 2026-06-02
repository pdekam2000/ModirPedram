# Phase 11B — Provider Cost Catalog + Estimator

**Status:** Complete  
**Date:** 2026-05-30  
**Validation:** `validate_11b_cost_catalog` **15/15 PASS** · `validate_11a_capability_registry` **24/24 PASS** · `validate_10k_matrix` **89/89 PASS**

---

## Summary

Phase 11B adds a **standalone provider cost catalog** and **pre-dispatch cost estimator** that answers *"What might this provider usage cost?"* using metadata only. It integrates with the Phase 11A Capability Registry for support checks. No provider APIs, runtime dispatch, UI, router behavior, budget enforcement, or ledger.

All numeric values are **internal placeholder estimates** — clearly marked, not official provider pricing.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/providers/provider_cost_catalog.py` | Cost catalog, schema, default entries, estimator APIs |
| `project_brain/validate_11b_cost_catalog.py` | Validation (15 tests) |
| `project_brain/PHASE_11B_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/providers/__init__.py` | Export cost catalog + estimator types |

**Unchanged:** `ProviderRuntimeEngine`, `VideoProviderRouter`, `cost_telemetry.py` (10J storage), UI, worker, operations control.

---

## Cost Model Schema

### Cost models (`ALL_COST_MODELS`)

| Model | Typical use |
|-------|-------------|
| `per_clip` | Browser/subscription video clips |
| `per_second` | API video duration billing |
| `per_minute` | Voice/music duration |
| `per_character` | TTS/narration |
| `per_request` | Flat per generation job |
| `free` | Subscription opportunity cost only |
| `unknown` | Pricing not verified |

### Cost catalog entry (`CostCatalogEntry`)

| Field | Description |
|-------|-------------|
| `provider_id` | Canonical provider ID (aliases normalized) |
| `capability` | Capability ID from 11A registry |
| `cost_model` | One of `ALL_COST_MODELS` |
| `unit_cost` | Cost per unit (`null` when unknown) |
| `currency` | `USD`, `CREDITS`, etc. |
| `unit` | `clip`, `second`, `character`, `request`, … |
| `min_billable_units` | Minimum billable quantity (default 1) |
| `notes` | Human-readable; includes placeholder disclaimer |
| `updated_at` | Timestamp |
| `confidence` | `high` / `medium` / `low` / `unknown` |

Optional override: `config/provider_cost_catalog.json` with `entries` array.

### Estimate result (`CostEstimateResult`)

| Field | Description |
|-------|-------------|
| `estimated_cost` | Computed cost or `null` when unknown/blocked |
| `billable_units` | Quantity after `min_billable_units` |
| `is_estimate` | Always `true` for successful estimates |
| `blocked` | `true` when capability unsupported or entry missing |
| `block_reason` | `CAPABILITY_UNSUPPORTED` / `COST_ENTRY_MISSING` |

---

## Estimator API

```python
from content_brain.providers import ProviderCostEstimator

estimator = ProviderCostEstimator.load(".")

# Generic
estimator.estimate("runway", "text_to_video", quantity=10, unit="second")

# Convenience
estimator.estimate_video("hailuo_browser", clips=3)
estimator.estimate_video("runway", seconds=10)
estimator.estimate_voice("elevenlabs", characters=1200)
estimator.estimate_music("suno", tracks=1)

# Compare (cheapest first; blocked/unknown sort last)
estimator.compare(["runway_browser", "runway", "hailuo_browser"], "text_to_video", 2)
```

**Capability check:** Uses `ProviderCapabilityRegistry.supports()` before estimating. Unsupported capabilities return blocked result — no exception, no crash.

---

## Default Provider Cost Coverage

All 11 Phase 11A default providers have at least one cost entry:

| Provider | Primary capability | Cost model | Confidence |
|----------|-------------------|------------|------------|
| `hailuo_browser` | text_to_video | per_clip (CREDITS) | low |
| `hailuo_api` | text_to_video | unknown | unknown |
| `runway_browser` | text_to_video | free | medium |
| `runway` | text_to_video | per_second (USD) | low |
| `minimax_api` | text_to_video | unknown | unknown |
| `luma` | text_to_video | per_request | unknown |
| `kling` | text_to_video | per_clip | unknown |
| `elevenlabs` | narration + voice_clone | per_character / per_request | low/unknown |
| `openai_tts` | narration | per_character | medium |
| `suno` | music_generation | per_request | unknown |
| `generic_image` | text_to_image + image_generation | per_request | low |

Every entry note includes: *"Internal placeholder estimate — not official provider pricing."* when confidence is low/unknown.

---

## Validation Results

```
py -3.11 -m project_brain.validate_11b_cost_catalog     → 15/15 PASS
py -3.11 -m project_brain.validate_11a_capability_registry → 24/24 PASS
py -3.11 -m project_brain.validate_10k_matrix           → 89/89 PASS
```

| Test area | Result |
|-----------|--------|
| Catalog load + 11A provider coverage | PASS |
| Supported capability estimate | PASS |
| Free / unknown pricing handling | PASS |
| Unsupported capability block | PASS |
| Voice + music estimators | PASS |
| Multi-provider compare | PASS |
| No runtime/router dispatch | PASS |

---

## Limitations

1. **Placeholder pricing only** — not synced to live provider billing APIs.
2. **No budget enforcement** — estimates are informational; guardrails deferred to Phase 11K.
3. **No usage ledger** — no append-only actuals tracking yet.
4. **Not wired to runtime** — `SimulationReportBuilder` and preflight unchanged in 11B.
5. **Single capability per estimate** — composite session costs require summing multiple calls.

---

## Compatibility Notes

| System | Impact |
|--------|--------|
| Phase 11A Capability Registry | Read-only consumer |
| Phase 10J `cost_telemetry` | Unchanged |
| Phase 10K Operations | Unchanged |
| Provider runtime / router | Unchanged |

---

## Next Recommended Slice

**Phase 11C — Failover Policy Layer**

- Config-driven provider failover chains (`config/provider_failover_chains.json`)
- Use capability registry + cost estimator for candidate ranking metadata
- Still no new provider integrations; policy engine only

---

## Quick validation

```bash
py -3.11 -m project_brain.validate_11b_cost_catalog
```
