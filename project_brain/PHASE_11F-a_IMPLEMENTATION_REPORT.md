# Phase 11F-a — Hailuo Preflight, Config & Error Taxonomy

**Status:** Complete  
**Date:** 2026-05-30  
**Scope:** Preflight, config resolver, error taxonomy, validator hook — no browser/API execution changes

---

## Summary

Phase 11F-a adds read-only Hailuo/MiniMax configuration resolution, structured preflight evaluation, and error taxonomy mapping mirroring the Phase 11E-a Runway pattern. Browser execution, router dispatch, runtime dispatch, and UI are unchanged.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/hailuo_config.py` | Config resolver (registry, mode catalog, active_providers, env) |
| `content_brain/execution/hailuo_preflight.py` | Structured preflight engine for Hailuo + MiniMax |
| `providers/hailuo_error_classifier.py` | Hailuo/MiniMax error → 10J taxonomy mapping |
| `project_brain/validate_11f_a_hailuo_preflight.py` | Mock-only validation matrix |
| `project_brain/PHASE_11F-a_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/provider_preflight_validator.py` | Hailuo/MiniMax preflight hook; `hailuo_preflight` block on `PreflightResult`; check ID → reject code map |

---

## Config Behavior

`HailuoConfigResolver` reads:

- `config/active_providers.json` — active video provider (unchanged: `runway_browser`)
- `config/provider_registry.json` — `hailuo_browser` enabled flag, `minimax_api` entry
- `ProviderModeCatalog` defaults — Hailuo/MiniMax API `implementation_status`
- Optional env: `HAILUO_API_KEY`, `MINIMAX_API_KEY`, `HAILUO_API_BASE_URL`, `MINIMAX_API_BASE_URL`

Key outputs:

| Field | Current value |
|-------|---------------|
| `active_video_provider` | `runway_browser` |
| `active_default_is_runway` | `true` |
| `hailuo_browser_enabled_in_registry` | `false` |
| `hailuo_api_implemented` | `false` (`planned`) |
| `minimax_api_implemented` | `false` (`stub`) |
| `hailuo_api_in_registry` | `false` |

Browser mode does **not** require API keys.

---

## Preflight Behavior

### Hailuo browser (`hailuo` / `hailuo_browser`)

- Returns structured block: `ready`, `provider_id`, `mode`, `blocking_issues`, `warnings`, `capability_supported`, `runtime_supported`, `api_implemented`, `browser_available`
- Blocks with `PROVIDER_DISABLED` when registry `enabled=false`
- Blocks unsupported capabilities and I2V when requested (runtime gap)
- I2V drift warning when T2V requested but I2V declared in 11A
- Browser probes skipped by default in tests (`browser_available=null`)

### Hailuo API (`hailuo_api`)

- Always blocks with `PROVIDER_NOT_IMPLEMENTED` (metadata-only)
- Additional `CREDENTIALS_MISSING` if API key absent (when API mode evaluated directly)
- Warning when `hailuo_api` missing from registry

### MiniMax API (`minimax_api`)

- Blocks with `PROVIDER_NOT_IMPLEMENTED` (`MINIMAX_API_STUB`)
- Blocks with `PROVIDER_DISABLED` when registry disabled
- Blocks with `CREDENTIALS_MISSING` when key absent

### Validator integration

When `provider_family` is `hailuo` or `minimax`, `ProviderPreflightValidator` attaches `operations`-level `hailuo_preflight` block (parallel to `runway_preflight`). Does not alter dispatch or router paths.

---

## Error Taxonomy

`classify_hailuo_error` / `classify_hailuo_failure` map to **existing** 10J codes:

| Condition | Code |
|-----------|------|
| Browser unavailable | `BROWSER_UNAVAILABLE` |
| Session expired / login required | `BROWSER_SESSION_INVALID` |
| Generation timeout | `PROVIDER_TIMEOUT` |
| Download failed | `DOWNLOAD_FAILED` |
| Artifact invalid / too small | `ARTIFACT_TOO_SMALL` / `ARTIFACT_VALIDATION_FAILED` |
| Unsupported capability | `CAPABILITY_RUNTIME_UNSUPPORTED` |
| Provider not implemented | `PROVIDER_NOT_IMPLEMENTED` |
| API credential missing | `CREDENTIALS_MISSING` |
| Provider disabled | `PROVIDER_DISABLED` |
| Cancel requested | `OPERATIONS_CANCELLED` |

No new taxonomy registry entries required.

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11f_a_hailuo_preflight
```

| Scope | Result |
|-------|--------|
| **11F-a core tests** | **22/22 PASS** |
| Nested `validate_11e_matrix` | FAIL (cascade from 10K-d) |
| Nested `validate_10k_matrix` | FAIL (pre-existing 10K-d validator bug) |

### 11F-a core coverage (all pass)

- Active default remains `runway_browser`
- Hailuo API metadata-only / not implemented
- MiniMax stub status detected
- Hailuo browser preflight structured output
- `hailuo_api` → `PROVIDER_NOT_IMPLEMENTED`
- MiniMax stub blocker
- Browser mode does not require API key
- Unsupported capability blocks
- I2V drift blocks when requested
- Error classifier mappings (browser, session, timeout, download, artifact, capability, not-implemented, credential, disabled, cancel)
- Integrated `hailuo_preflight` block attached
- No runtime dispatch / router execution during preflight

### Regression note

Nested regression checks invoke full `validate_10k_matrix`, which fails in `validate_10k_d_worker_cancel` with `AttributeError: 'dict' object has no attribute 'ok'` at line 113 — a pre-existing test harness issue unrelated to 11F-a changes. All 11E-a Runway core tests (20/20 excluding nested regressions) still pass after the Hailuo hook addition.

---

## Scope Compliance

| Rule | Status |
|------|--------|
| No Hailuo browser automation | ✅ |
| No Hailuo/MiniMax API calls | ✅ |
| No API provider implementation | ✅ |
| Active/default provider unchanged | ✅ |
| No router dispatch changes | ✅ |
| No UI changes | ✅ |
| No runtime dispatch changes | ✅ |
| Preserve 10J/10K/11A–11E behavior | ✅ (no execution path changes) |

---

## Known Limitations

1. `hailuo_browser` registry `enabled=false` — preflight blocks until operator enables (by design).
2. `hailuo_api` has no registry row — warning only; primary blocker is `PROVIDER_NOT_IMPLEMENTED`.
3. Browser availability probe runs only when `skip_browser_probes=False` (not used in CI validators).
4. I2V declared in 11A but not runtime-supported — blocked when requested (same pattern as Runway 11E-a).
5. MiniMax evaluated as separate family; no conflation with Hailuo API.

---

## Next Recommended Slice

**11F-b — Browser Mode Hardening**

- Single browser session per clip (generate + download)
- Bounded wait loop replacing fixed 150s sleep
- Cooperative cancel checkpoints
- Structured `HailuoProviderError` / `HailuoCancelledError`
- Login/session detection in browser provider

Do not start 11F-b until 11F-a validation core tests are accepted.
