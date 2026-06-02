# Phase 11E-a — Runway Preflight, Config Unification & Error Taxonomy

**Status:** Complete  
**Date:** 2026-05-28  
**Validation:** `validate_11e_a_runway_preflight` **25/25 PASS** (includes 11A–11D, 10K regression)

---

## Summary

Phase 11E-a adds **read-only Runway config resolution**, **structured Runway preflight**, and **Runway-specific error → taxonomy mapping** without changing provider execution, dispatch structure, router behavior, or UI. Browser remains the active/default authority (`runway_browser`); API mode is hardened in preflight but stays disabled in registry.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/runway_config.py` | Unified config resolver (registry + mode catalog + env + active provider) |
| `content_brain/execution/runway_preflight.py` | Structured Runway preflight engine |
| `providers/runway_error_classifier.py` | Runway error → failure taxonomy code mapping |
| `project_brain/validate_11e_a_runway_preflight.py` | Validation (25 tests + regressions) |
| `project_brain/PHASE_11E-a_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/failure_taxonomy.py` | Extended codes: `CREDENTIALS_INVALID`, `PROVIDER_DISABLED`, `CAPABILITY_RUNTIME_UNSUPPORTED`, `DOWNLOAD_FAILED` |
| `content_brain/execution/provider_preflight_validator.py` | Runway family hook; `runway_preflight` block on `PreflightResult`; check ID → code mappings |

**Unchanged:** `ProviderRuntimeEngine.dispatch()`, `VideoProviderRouter`, `runway_video_provider.py`, `runway_browser_provider.py`, `runway_browser_orchestrator.py`, `BrowserManager`, UI.

---

## Config Behavior

`RunwayConfigResolver` reads:

| Source | Fields used |
|--------|-------------|
| `config/active_providers.json` | `video` → active provider (unchanged: `runway_browser`) |
| `config/provider_registry.json` | `runway` / `runway_browser` `enabled` flags |
| `ProviderModeCatalog` (+ `config/provider_mode_catalog.json` override) | `preferred_mode`, router keys, `api_config`, `browser_config` |
| Environment | `RUNWAY_API_KEY`, `RUNWAY_API_BASE_URL` |

Provider ID normalization:

| Input | Canonical |
|-------|-----------|
| `runway`, `runway_api` | `runway` |
| `runway_browser` | `runway_browser` |

API base URL resolution order: `RUNWAY_API_BASE_URL` env → catalog `default_endpoint`. Format validated locally (`http`/`https` + host) — **no API calls**.

---

## Preflight Behavior

### `RunwayPreflightEngine.evaluate()` result

| Field | Description |
|-------|-------------|
| `ready` | `True` when no blocking issues |
| `mode` | `browser` or `api` |
| `provider_id` | Resolved router key |
| `blocking_issues[]` | `{code, message, check_id}` |
| `warnings[]` | Non-blocking advisories |
| `capability_supported` | 11A registry declares capability |
| `runtime_supported` | Runtime actually implements capability |
| `requested_capability` | Inferred from session or explicit |
| `i2v_drift_detected` | Registry declares I2V but runtime does not |

### Mode-specific checks

**API mode blockers:**

- API disabled in registry → `PROVIDER_DISABLED`
- Missing `RUNWAY_API_KEY` → `CREDENTIALS_MISSING`
- Missing/invalid base URL → `API_ENDPOINT_NOT_CONFIGURED`

**Browser mode:**

- Reuses existing `run_browser_probes` when probes not skipped
- Default validation uses `skip_browser_probes=True` (no automation)

**Capability:**

- Unsupported capability → `CAPABILITY_RUNTIME_UNSUPPORTED`
- **I2V drift:** blocker when `image_to_video` requested; **warning** when only declared in 11A (text-to-video sessions)

### Integration

When `ProviderPreflightValidator` resolves `provider_family == "runway"`, it attaches `runway_preflight` to `PreflightResult` and merges blocking checks into the standard check list.

---

## Error Taxonomy Additions

Extended (not replaced) `failure_taxonomy.py`:

| Code | Category | Use |
|------|----------|-----|
| `CREDENTIALS_INVALID` | PREFLIGHT_REJECT | 401/403, invalid API key patterns |
| `PROVIDER_DISABLED` | PREFLIGHT_REJECT | Registry `enabled=false` |
| `CAPABILITY_RUNTIME_UNSUPPORTED` | PREFLIGHT_REJECT | I2V drift, unsupported capabilities |
| `DOWNLOAD_FAILED` | RUNTIME_ERROR | Download failure patterns |

`providers/runway_error_classifier.py`:

- `classify_runway_error(error, http_status=..., context=...)` → taxonomy code
- `classify_runway_failure(...)` → full metadata via `classify_failure()`

Maps: missing credential, invalid credential, rate limit, timeout, download failed, artifact invalid, unsupported capability, provider disabled, browser session unavailable.

---

## Capability Drift (I2V)

11A declares `image_to_video` for Runway; runtime supports only:

- `text_to_video`
- `asset_download`

Preflight exposes drift via `i2v_drift_detected` + `i2v_drift_note`. Requesting I2V is blocked; text-to-video sessions receive a warning only. **11A registry unchanged; no I2V implementation.**

---

## Validation Results

```
py -3.11 -m project_brain.validate_11e_a_runway_preflight
```

| Test | Result |
|------|--------|
| browser_default_unchanged | PASS |
| preferred_mode_browser | PASS |
| api_disabled_in_registry | PASS |
| api_mode_disabled_blocker | PASS |
| missing_api_key_blocker | PASS |
| invalid_base_url_blocker | PASS |
| unsupported_capability_blocker | PASS |
| i2v_drift_blocker_when_requested | PASS |
| i2v_drift_warning_when_not_requested | PASS |
| taxonomy (8 mappings) | PASS |
| integrated_runway_preflight_block | PASS |
| no_runtime_dispatch | PASS |
| no_router_execution | PASS |
| validate_11a_still_passes | PASS |
| validate_11b_still_passes | PASS |
| validate_11c_still_passes | PASS |
| validate_11d_still_passes | PASS |
| validate_10k_matrix_still_passes | PASS |

**Summary: 25/25 PASS**

---

## Scope Compliance

| Rule | Status |
|------|--------|
| No Runway API calls | ✅ URL format validation only |
| No browser automation in validation | ✅ `skip_browser_probes=True` default |
| Active default stays `runway_browser` | ✅ Verified |
| API not made default | ✅ Registry `enabled=false` respected |
| No I2V implementation | ✅ Drift warning/blocker only |
| No dispatch structure changes | ✅ |
| No router changes | ✅ |
| No UI changes | ✅ |
| No `retry_generation` | ✅ Not touched |

---

## Known Limitations

1. **API provider still hardcodes base URL** at execution time — config unification is preflight/metadata only until 11E-b.
2. **Browser login/session validity** not deeply probed (CDP attach success used as proxy when probes enabled).
3. **I2V remains metadata-only** — registry/cost/failover still declare capability.
4. **Error classifier is pattern-based** — not yet wired into live provider exception paths (11E-b/c).
5. **Default endpoint warning** emitted when using catalog URL without env override (informational).

---

## Next Slice Recommendation

**Phase 11E-b — API Mode Hardening**

- Wire `RUNWAY_API_BASE_URL` into `RunwayVideoProvider` (read from config resolver)
- Cancel checkpoints in poll loop
- Download min-size parity
- Wire `classify_runway_error()` into API provider exception paths
- Remove or document `retry_generation` stub (no auto-retry per operator decision)

---

## Regression Commands

```bash
py -3.11 -m project_brain.validate_11e_a_runway_preflight
py -3.11 -m project_brain.validate_11a_capability_registry
py -3.11 -m project_brain.validate_11b_cost_catalog
py -3.11 -m project_brain.validate_11c_failover_policy
py -3.11 -m project_brain.validate_11d_provider_selection
py -3.11 -m project_brain.validate_10k_matrix
```
