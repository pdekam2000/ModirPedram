# Phase 11E-c — Runway Browser Mode Hardening

**Status:** Complete  
**Date:** 2026-05-28  
**Validation:** `validate_11e_c_runway_browser_hardening` **18/18 PASS** (includes 11E-a, 11E-b, 11A–11D, 10K regression)

---

## Summary

Phase 11E-c hardens the **Runway browser path** by removing infinite worker blocking, adding bounded waits, cooperative cancel checkpoints, taxonomy-integrated errors, cleanup on failure, and validation-compatible download metadata. **API provider (11E-b), router, dispatch, UI, and active default (`runway_browser`) are unchanged.**

---

## Files Created

| File | Purpose |
|------|---------|
| `providers/runway_browser_support.py` | Browser config env helpers, cancel checks, error wrapping |
| `project_brain/validate_11e_c_runway_browser_hardening.py` | Mock-only validation (18 tests + regressions) |
| `project_brain/PHASE_11E-c_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `orchestrators/runway_browser_orchestrator.py` | Removed infinite sleep; bounded wait; cancel; errors; cleanup; clip metadata |
| `providers/runway_browser_provider.py` | Cancel checkpoints; bounded settle waits; structured errors on launch/click failures |
| `providers/runway_download_provider.py` | Taxonomy errors; cancel during download; metadata dict return; min size gate |
| `project_brain/validate_11e_b_runway_api_hardening.py` | Updated browser regression check (no `999999`) |

**Unchanged:** `runway_video_provider.py`, `VideoProviderRouter`, `ProviderRuntimeEngine`, UI.

---

## Removed Blocking Behavior

| Before | After |
|--------|-------|
| `time.sleep(999999)` on any exception | **Removed** — `finally` cleanup + re-raise structured error |
| Unbounded error trap leaving worker stuck | Bounded generation wait with `PROVIDER_TIMEOUT` |
| `return None` on URL timeout + generic `RuntimeError` | Raises `RunwayProviderError` code `PROVIDER_TIMEOUT` |

---

## Browser Wait Timeout Behavior

Configurable via environment:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RUNWAY_BROWSER_MAX_WAIT_SECONDS` | 900 | Max wait per clip for video URL |
| `RUNWAY_BROWSER_POLL_INTERVAL` | 10 | Poll interval during generation wait |
| `RUNWAY_BROWSER_PAGE_SETTLE_SECONDS` | 8 | Post-navigation UI settle (capped 30s) |
| `RUNWAY_BROWSER_GENERATE_CLICK_WAIT` | 5 | Post-generate click wait (capped 30s) |
| `RUNWAY_BROWSER_PREPARE_STEP_TIMEOUT_MS` | 15000 | Playwright click/load timeouts |

Orchestrator `wait_seconds` constructor arg overrides max wait when set (router still passes 180).

Generation wait uses **monotonic deadline** + poll interval cap — never infinite.

Page state detection adds: `LOGIN_REQUIRED`, `SESSION_EXPIRED`, `GENERATION_ERROR`.

---

## Cancel Checkpoint Behavior

Optional `cancel_check: Callable[[], bool]]` on orchestrator and providers.

| Phase | Location |
|-------|----------|
| `before_browser_launch` | Orchestrator |
| `between_clips` | Orchestrator |
| `before_prompt_submit` | Orchestrator |
| `before_generation_wait` | Orchestrator |
| `generation_wait` | Each poll iteration |
| `before_download` / `after_download` | Orchestrator + download provider |
| `download_stream` | During HTTP stream |
| Browser UI steps | `fill_prompt`, `click_generate`, `prepare_gen45_page`, etc. |

On cancel: `RunwayCancelledError` (`OPERATIONS_CANCELLED`) with `partial_paths` — **not FAILED**.

Runtime/router do not pass `cancel_check` yet (same as 11E-b API path).

---

## Error Mapping Behavior

Uses `wrap_browser_error()` + `classify_runway_error()` / `RunwayProviderError`:

| Condition | Code |
|-----------|------|
| CDP/launch failure | `BROWSER_UNAVAILABLE` |
| Login/sign-in page | `BROWSER_SESSION_INVALID` |
| UI automation failure | `BROWSER_AUTOMATION_NOT_READY` |
| Generation page error | `PROVIDER_TASK_FAILED` |
| URL wait timeout | `PROVIDER_TIMEOUT` |
| Download HTTP failure | `DOWNLOAD_FAILED` |
| File &lt; 100KB | `ARTIFACT_TOO_SMALL` |
| Cancel requested | `OPERATIONS_CANCELLED` |

Cleanup errors in `finally` are logged as warnings — **do not mask primary error**.

---

## Artifact Behavior

`RunwayDownloadProvider.download_video_url()` returns metadata dict:

```json
{
  "file_path": "...",
  "video_url": "...",
  "size_bytes": 100100,
  "clip_index": 1,
  "provider": "runway_browser",
  "mode": "browser",
  "provider_version": "11e_c_v1"
}
```

- Min size **100_000 bytes** (10J-e aligned)  
- Undersized files deleted before raise  
- `RunwayBrowserOrchestrator.clip_results[]` populated per clip  
- `generate_clips` router contract unchanged — still returns `list[str]` paths via orchestrator `run()`

---

## Validation Results

```
py -3.11 -m project_brain.validate_11e_c_runway_browser_hardening
```

**18/18 PASS** — mocks only, no Playwright, no Runway API.

Regressions: 11E-a, 11E-b, 11A–11D, 10K matrix all pass.

---

## Scope Compliance

| Rule | Status |
|------|--------|
| No browser automation in validation | ✅ |
| No Runway API calls | ✅ |
| Active default `runway_browser` | ✅ |
| No I2V | ✅ |
| No UI/router/dispatch changes | ✅ |
| API provider unchanged | ✅ |

---

## Known Limitations

1. **Cancel not wired from runtime worker** — provider API ready; `_execute_clips` does not pass `cancel_check` yet.  
2. **Playwright still required at runtime** for real browser execution (lazy import in browser provider only).  
3. **Debug “leave browser open” behavior removed** — failures now cleanup disconnect; operator loses post-mortem open browser (by design for worker safety).  
4. **I2V UI flow not implemented** — unchanged from audit.  
5. **Shared download helper with API** deferred to 11E-d.

---

## Next Recommended Slice

**Phase 11E-d — Download & Artifact Continuity**

- Unified `runway_asset_downloader` for API + browser HTTP download  
- Copy integrity in `ProviderRuntimeEngine._execute_clips`  
- Wire runtime `cancel_check` into router optional kwargs (ADR)

---

## Regression Commands

```bash
py -3.11 -m project_brain.validate_11e_c_runway_browser_hardening
py -3.11 -m project_brain.validate_11e_b_runway_api_hardening
py -3.11 -m project_brain.validate_11e_a_runway_preflight
py -3.11 -m project_brain.validate_10k_matrix
```
