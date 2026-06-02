# Phase 11E-b — Runway API Mode Hardening

**Status:** Complete  
**Date:** 2026-05-28  
**Validation:** `validate_11e_b_runway_api_hardening` **24/24 PASS** (includes 11E-a, 11A–11D, 10K regression)

---

## Summary

Phase 11E-b hardens the **Runway API provider** (`RunwayVideoProvider`) using unified config (11E-a), bounded polling, cooperative cancel checkpoints, error classifier integration, and download size validation. **Browser mode, router, dispatch, UI, and active default (`runway_browser`) are unchanged.**

---

## Files Created

| File | Purpose |
|------|---------|
| `providers/runway_api_errors.py` | `RunwayProviderError`, `RunwayCancelledError`, taxonomy-integrated errors |
| `project_brain/validate_11e_b_runway_api_hardening.py` | Mock-only validation (24 tests + regressions) |
| `project_brain/PHASE_11E-b_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `providers/runway_video_provider.py` | Full API hardening (config, polling, cancel, classifier, download validation) |
| `content_brain/execution/failure_taxonomy.py` | Added `OPERATIONS_CANCELLED` |

**Unchanged:** `runway_browser_provider.py`, `runway_browser_orchestrator.py`, `VideoProviderRouter`, `ProviderRuntimeEngine`, UI.

---

## Config Wiring Behavior

`RunwayVideoProvider` uses `RunwayConfigResolver` / injectable `RunwayConfigSnapshot`:

| Setting | Source |
|---------|--------|
| `base_url` | `RUNWAY_API_BASE_URL` → catalog `default_endpoint` |
| `api_key` | `RUNWAY_API_KEY` (env name from catalog) |
| Registry guard | Blocks when `runway` `enabled=false` → `PROVIDER_DISABLED` |
| Active default | Logged only; **not changed** (`runway_browser`) |
| Download dir | Mode catalog `browser_config.download_dir` |

Init guards (unless `skip_config_guards=True` for tests):

1. API enabled in registry  
2. API key present  
3. Base URL valid  

---

## Polling Behavior

| Control | Env var | Default |
|---------|---------|---------|
| Poll interval | `RUNWAY_POLL_INTERVAL` | 10s |
| Max attempts | `RUNWAY_MAX_ATTEMPTS` | 60 |
| Max wall time | `RUNWAY_MAX_POLL_SECONDS` | interval × attempts |

- Dual bound: **attempt count AND wall-clock deadline** — no infinite wait  
- Task status mapping:
  - `SUCCEEDED` → download
  - `FAILED` / `CANCELLED` → `PROVIDER_TASK_FAILED`
  - `PENDING` / `QUEUED` / `RUNNING` / etc. → continue poll
  - Unknown terminal → `PROVIDER_TASK_FAILED`
- Timeout → `RunwayProviderError` code `PROVIDER_TIMEOUT`

---

## Cancel Checkpoint Behavior

Cancel via optional `cancel_check: Callable[[], bool]` (constructor or `generate_clips`):

| Phase | Checkpoint |
|-------|------------|
| Before API POST | `before_api_request` |
| After task created | `after_task_creation` |
| Each poll iteration | `polling` |
| Before download | `before_download` |
| During download stream | `download_stream` |
| After download | `after_download` |
| Between clips | `between_clips` |

On cancel: raises `RunwayCancelledError` (`OPERATIONS_CANCELLED`, `cancelled=True`) with `partial_paths` preserved. **Not classified as FAILED.**

Runtime/router do not pass `cancel_check` yet — provider API ready for future wiring.

---

## Error Classifier Behavior

All API errors raised as `RunwayProviderError` with taxonomy code via `classify_runway_error()`:

| Condition | Code |
|-----------|------|
| Missing key | `CREDENTIALS_MISSING` |
| 401/403 | `CREDENTIALS_INVALID` |
| 402/429 | `API_QUOTA_EXCEEDED` |
| Poll timeout | `PROVIDER_TIMEOUT` |
| Task failed/cancelled | `PROVIDER_TASK_FAILED` |
| Download failure | `DOWNLOAD_FAILED` |
| File &lt; 100KB | `ARTIFACT_TOO_SMALL` |
| I2V / unsupported capability | `CAPABILITY_RUNTIME_UNSUPPORTED` |
| API disabled | `PROVIDER_DISABLED` |
| Invalid JSON/response | `PROVIDER_RUNTIME_ERROR` |

`RunwayProviderError.to_dict()` includes full taxonomy metadata.

---

## Download / Artifact Behavior

- Min size **100_000 bytes** (`MIN_ARTIFACT_BYTES`) — aligned with 10J-e  
- Undersized files deleted before raise  
- `clip_results[]` metadata per clip:

```json
{
  "file_path": "...",
  "task_id": "...",
  "video_url": "...",
  "size_bytes": 100500,
  "task_status": "SUCCEEDED",
  "provider": "runway",
  "mode": "api",
  "provider_version": "11e_b_v1",
  "poll_attempts": 1
}
```

- `generate_clips()` returns path list (backward compatible with router)

---

## Validation Results

```
py -3.11 -m project_brain.validate_11e_b_runway_api_hardening
```

**24/24 PASS** — all HTTP via mocks; no real Runway API calls.

Key tests: unified config, disabled/missing key guards, bounded polling, timeout classification, cancel during polling, classifier mappings, download metadata, small file rejection, I2V blocked, browser unchanged, no dispatch/router, regressions.

---

## Scope Compliance

| Rule | Status |
|------|--------|
| No real Runway API calls | ✅ Mocks only |
| Active default `runway_browser` | ✅ Verified |
| No browser mode changes | ✅ |
| No I2V implementation | ✅ Blocked at API entry |
| No failover execution | ✅ |
| No UI changes | ✅ |
| No router/dispatch structure changes | ✅ |
| `retry_generation` not auto-run | ✅ Still no-op |

---

## Known Limitations

1. **Cancel not wired from runtime** — `ProviderRuntimeEngine` does not pass `cancel_check` to router/provider yet (11E-c or worker slice).  
2. **Lazy `requests` import** — first real HTTP call requires `requests` installed.  
3. **API still disabled in registry** — production API path requires operator enable + key.  
4. **`RunwayCancelledError` through router** — uncaught by runtime today would still surface as generic error until worker wiring.  
5. **No copy-integrity check** — deferred to 11E-d.

---

## Next Slice Recommendation

**Phase 11E-c — Browser Mode Hardening**

- Remove orchestrator infinite sleep on error  
- Cancel checkpoints in browser wait loop  
- Browser cleanup on success/failure  
- Wire runtime `cancel_check` into both API and browser paths via optional router kwargs (ADR)

---

## Regression Commands

```bash
py -3.11 -m project_brain.validate_11e_b_runway_api_hardening
py -3.11 -m project_brain.validate_11e_a_runway_preflight
py -3.11 -m project_brain.validate_11a_capability_registry
py -3.11 -m project_brain.validate_11b_cost_catalog
py -3.11 -m project_brain.validate_11c_failover_policy
py -3.11 -m project_brain.validate_11d_provider_selection
py -3.11 -m project_brain.validate_10k_matrix
```
