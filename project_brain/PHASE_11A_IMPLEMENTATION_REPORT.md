# Phase 11A — Provider Capability Registry

**Status:** Complete  
**Date:** 2026-05-30  
**Validation:** `validate_11a_capability_registry` **24/24 PASS**

---

## Summary

Phase 11A introduces a **declarative Provider Capability Registry** so the system can answer *"What can this provider do?"* without inspecting provider-specific code. The registry sits **beside** existing `ProviderModeCatalog`, `ProviderRegistryEngine`, and `ProviderRuntimeEngine` — none were replaced or modified.

No new provider integrations, runtime changes, UI changes, or router changes.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/providers/provider_capability_registry.py` | Capability constants, schema, default registry, lookup APIs |
| `content_brain/providers/__init__.py` | Package exports for registry |
| `project_brain/validate_11a_capability_registry.py` | Automated validation (24 tests) |
| `project_brain/PHASE_11A_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

None. Phase 11A is additive only.

**Explicitly unchanged:** `ProviderModeCatalog`, `ProviderRegistryEngine`, `ProviderRuntimeEngine`, `VideoProviderRouter`, runtime worker, UI, orchestrators, providers.

---

## Capability Schema

Each provider is a frozen `ProviderCapabilityRecord`:

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | `str` | Canonical ID (aliases normalized on lookup) |
| `provider_name` | `str` | Display name |
| `category` | `str` | Runtime category (`video_generation`, `voice_generation`, …) |
| `capabilities` | `tuple[str, …]` | Declared capability IDs |
| `supports_browser_mode` | `bool` | Browser execution supported |
| `supports_api_mode` | `bool` | API execution supported |
| `supports_async_jobs` | `bool` | Async/polling job model |
| `supports_webhooks` | `bool` | Webhook callbacks supported |
| `supports_cost_estimation` | `bool` | Cost estimation applicable |

### Capability IDs (`ALL_CAPABILITIES`)

| ID | Typical providers |
|----|-------------------|
| `text_to_video` | hailuo_browser, runway, luma, kling, … |
| `image_to_video` | hailuo_*, runway_* |
| `text_to_image` | generic_image |
| `image_generation` | generic_image |
| `narration` | elevenlabs, openai_tts |
| `voice_clone` | elevenlabs |
| `music_generation` | suno |
| `subtitle_generation` | *(none yet — valid empty set)* |
| `asset_download` | Most media providers |
| `asset_upload` | generic_image |

### Default providers registered (11)

`hailuo_browser`, `hailuo_api`, `runway_browser`, `runway`, `minimax_api`, `luma`, `kling`, `elevenlabs`, `openai_tts`, `suno`, `generic_image`

Optional override file (not required): `config/provider_capability_registry.json` with `providers` array merges/overrides by `provider_id`.

---

## Registry APIs

```python
from content_brain.providers import ProviderCapabilityRegistry

registry = ProviderCapabilityRegistry.load(".")

registry.get_provider("runway")           # ProviderCapabilityRecord | None
registry.get_provider("runway_api")       # alias → runway

registry.list_capabilities("elevenlabs")  # ["narration", "voice_clone", "asset_download"]

registry.providers_for_capability("text_to_video")
# ["hailuo_api", "hailuo_browser", "kling", "luma", "minimax_api", "runway", "runway_browser"]

registry.supports("runway", "text_to_video")       # True
registry.supports("elevenlabs", "text_to_video")  # False
registry.supports("runway", "unknown_cap")         # False

registry.list_provider_ids()
registry.capability_coverage()          # all caps → provider ids
registry.to_dict()                      # JSON-safe export
registry.legacy_registry_coverage()     # read-only cross-check vs legacy registry
```

Alias normalization: `hailuo` → `hailuo_browser`, `runway_api` → `runway` (shared with `provider_categories.normalize_provider_key`).

---

## Validation Results

```
py -3.11 -m project_brain.validate_11a_capability_registry → 24/24 PASS
```

| Area | Tests |
|------|-------|
| Provider lookup + aliases | 4 |
| Capability listing | 2 |
| Reverse capability lookup | 2 |
| `supports()` positive/negative/unknown | 4 |
| Registry completeness | 4 |
| Legacy + mode catalog compatibility | 4 |
| Runtime/router import safety | 2 |
| Serialization + normalize | 2 |

---

## Compatibility Notes

| System | Relationship |
|--------|--------------|
| `ProviderModeCatalog` | Unchanged; families runway/hailuo/minimax have matching capability entries |
| `ProviderRegistryEngine` | Unchanged; all video/music/voice registry names map to capability records |
| `ProviderRuntimeEngine` | Unchanged; not wired to capability registry in 11A |
| `VideoProviderRouter` | Unchanged |
| Phase 10J / 10K | No behavior impact |

The registry is **read-only metadata** until Phase 11B+ consumers (cost catalog, selection engine, preflight) opt in.

---

## Known Limitations

1. **Declarative only** — capabilities describe design intent; no runtime enforcement yet.
2. **No live probe** — does not check credentials, implementation status, or router branches.
3. **`subtitle_generation`** — intentionally unassigned (post-production engine planned separately).
4. **Trend/LLM providers** — excluded from capability registry scope (different subsystem).

---

## Next Recommended Slice

**Phase 11B — Provider Cost Catalog + Estimator**

- Read capability registry + mode catalog for unit types
- Config-driven `ProviderCostCatalog` (credits/USD per capability unit)
- Extend `SimulationReportBuilder` / `cost_telemetry` to consume estimates
- Still no new provider integrations

---

## Quick validation

```bash
py -3.11 -m project_brain.validate_11a_capability_registry
```
