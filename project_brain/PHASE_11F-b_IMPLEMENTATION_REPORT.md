# Phase 11F-b — Hailuo Browser Mode Hardening

**Status:** Complete  
**Date:** 2026-05-30  
**Prerequisites:** Phase 11F-a approved · Runway 11E-c pattern baseline

---

## Summary

Hailuo browser execution is hardened to match Runway 11E-c safety standards: **single browser session per orchestrator run**, **bounded polling** (no fixed 150s sleep), **cooperative cancel checkpoints**, **structured errors** via `hailuo_error_classifier`, and **`clip_results[]` artifact metadata** compatible with 10J-e / 11E-d.

No API implementation, UI changes, runtime dispatch structure changes, failover execution, or default provider switch.

---

## Files Created

| File | Purpose |
|------|---------|
| `providers/hailuo_api_errors.py` | `HailuoProviderError`, `HailuoCancelledError` |
| `providers/hailuo_browser_support.py` | Env config, `check_cancel`, `wrap_browser_error` |
| `providers/hailuo_artifact_utils.py` | Normalized clip records, min-size gate, partial bundles |
| `project_brain/validate_11f_b_hailuo_browser_hardening.py` | Mock-only validation (23 tests) |
| `project_brain/PHASE_11F-b_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `orchestrators/hailuo_multi_clip_orchestrator.py` | Full rewrite: session reuse, polling, cancel, clip_results |
| `providers/hailuo_browser_provider.py` | Cancel checkpoints, capped settles, structured errors |
| `providers/hailuo_download_provider.py` | Shared browser, artifact finalize, no silent None |
| `providers/hailuo_error_classifier.py` | Added `selector not found` pattern |
| `core/video_provider_router.py` | Removed hardcoded `wait_seconds=150` (orchestrator uses env default) |

---

## Session Reuse Findings

**Before (11F design audit):** Two CDP sessions per clip — `HailuoBrowserProvider.start/close` for generate, then separate `HailuoDownloadProvider.start/close` for download.

**After (11F-b):** **Safe to reuse** within one `run()` call.

| Aspect | Decision |
|--------|----------|
| Mode | `SESSION_REUSE_MODE = "single_session_per_run"` |
| Mechanism | One `BrowserManager.launch()`; downloader receives `generator.browser` + `generator.page` |
| Cleanup | Single `generator.close()` in `finally` — avoids double CDP disconnect |
| Per-clip navigation | Still navigates home → generate → `/mine` on **same** session (required by Hailuo UI flow) |
| Cross-run reuse | **Not** implemented — each orchestrator invocation owns its session |

**Why safe:** Same authenticated Chrome profile and CDP context; download does not require a separate browser instance. Runway 11E-c uses the same pattern.

---

## Wait / Polling Behavior

| Before | After |
|--------|-------|
| Fixed `sleep(150)` after Create | Bounded poll loop with monotonic deadline |
| Router hardcoded `wait_seconds=150` | Env-driven `HAILUO_BROWSER_MAX_WAIT_SECONDS` (default 900) |

**Env vars:**

- `HAILUO_BROWSER_MAX_WAIT_SECONDS` — max generation wait (default 900)
- `HAILUO_BROWSER_POLL_INTERVAL` — poll interval (default 10s)
- `HAILUO_BROWSER_PAGE_SETTLE_SECONDS` — capped page settle (max 30s, default 8)
- `HAILUO_BROWSER_ASSETS_SETTLE_SECONDS` — assets page settle (max 30s, default 10)
- `HAILUO_BROWSER_STEP_TIMEOUT_MS` — DOM step timeout (default 20000)

Poll loop checks page state (`GENERATING`, `LOGIN_REQUIRED`, new video sources) and raises `PROVIDER_TIMEOUT` at deadline.

---

## Cancel Behavior

Uses existing **10K-d / 11E-e** pattern — `cancel_check: Callable[[], bool]` on orchestrator `run()`.

Checkpoints:

| Phase | Location |
|-------|----------|
| `before_browser_launch` | Orchestrator |
| `between_clips` | Orchestrator loop |
| `before_prompt_submit` | Browser provider + orchestrator |
| `before_create_click` | Browser provider |
| `generation_wait` | Poll loop (each iteration) |
| `before_download` / `before_download_navigate` / `download_stream` / `after_download` | Download path |

Cancel raises `HailuoCancelledError` (`OPERATIONS_CANCELLED`) with `partial_paths` and `clip_results` preserved.

**Note:** `provider_cancel_wiring.RUNWAY_CANCEL_AWARE_PROVIDERS` unchanged — Hailuo runtime cancel wiring is **11F-d** scope. Router already forwards `cancel_check` via `call_with_optional_cancel_check` when orchestrator accepts it.

---

## Error Mapping

Structured via `HailuoProviderError` + `hailuo_error_classifier`:

| Condition | Code |
|-----------|------|
| CDP attach failed | `BROWSER_UNAVAILABLE` |
| Login / session expired | `BROWSER_SESSION_INVALID` |
| Generation timeout | `PROVIDER_TIMEOUT` |
| Generation page error | `PROVIDER_TASK_FAILED` |
| Create/selector failure | `BROWSER_AUTOMATION_NOT_READY` |
| Download/extract failure | `DOWNLOAD_FAILED` |
| File too small | `ARTIFACT_TOO_SMALL` |
| Cooperative cancel | `OPERATIONS_CANCELLED` |

No silent `None` returns — failures raise typed errors.

---

## Artifact Behavior

- `clip_results[]` on orchestrator with fields: `file_path`, `provider_id`, `mode`, `clip_index`, `size_bytes`, `sha256`, `validation_status`, `partial`
- Min size gate: 100KB (`MIN_ARTIFACT_BYTES`)
- `partial_artifact_bundle()` attached to error details on failure/cancel
- Return value: list of `file_path` strings only (no `None` entries)

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11f_b_hailuo_browser_hardening
# 23/23 PASS

py -3.11 -m project_brain.validate_11f_a_hailuo_preflight
# 24/24 PASS (nested regression)

# Nested regressions from 11F-b matrix:
# validate_11e_matrix — PASS
# validate_10k_matrix — PASS
```

**Mock-only** — no browser automation or API calls in validators.

---

## Scope Compliance

| Rule | Status |
|------|--------|
| Hailuo browser path only | ✅ |
| No API implementation | ✅ |
| No UI changes | ✅ |
| No runtime dispatch structure changes | ✅ |
| No failover execution | ✅ |
| Active default `runway_browser` unchanged | ✅ |
| 11F-a behavior preserved | ✅ |
| No real browser automation in CI | ✅ |

**Minimal router change:** Removed `wait_seconds=150` only — dispatch keys, `cancel_check` forwarding, and provider routing unchanged.

---

## Known Limitations

1. Download still selects `video.nth(0)` on assets page — clip index matching deferred to 11F-c.
2. Generation-complete detection uses page text + video source diff (best-effort DOM heuristics).
3. Hailuo runtime cancel not in `RUNWAY_CANCEL_AWARE_PROVIDERS` until 11F-d.
4. `hailuo_browser` registry `enabled=false` — preflight still blocks real dispatch (11F-a by design).
5. I2V UI detected but not implemented.

---

## Next Recommended Slice

**11F-c — Download & Artifact Continuity**

- Clip-index-aware download selection
- Session artifact root copy integration
- Extend runtime partial artifact handling for `HailuoCancelledError`
- `validate_11f_c_hailuo_artifacts` matrix

---

## Production Code Changed?

**Yes** — Hailuo browser orchestrator, providers, and minimal router wait default only. No changes to `provider_runtime_engine`, UI, preflight, or failover execution.
