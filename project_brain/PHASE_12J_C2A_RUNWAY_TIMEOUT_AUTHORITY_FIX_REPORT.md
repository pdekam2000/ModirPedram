# PHASE 12J-C2a — Runway Timeout Authority Fix Report

**Date:** 2026-06-02  
**Status:** Implemented  
**Design input:** `PHASE_12J_C_STEP2_RUNWAY_WAIT_DOWNLOAD_HARDENING_DESIGN.md` §1 (timeout policy)  
**Scope:** Timeout authority only — no multi-signal wait, debug bundle, download fallbacks, or UI substate

---

## Problem

`VideoProviderRouter` instantiated `RunwayBrowserOrchestrator(wait_seconds=180)`, overriding the authoritative `browser_max_wait_seconds()` default (**900s**). UAT sessions failed with `PROVIDER_RUNTIME_ERROR` after ~180s of generation wait while Runway was still generating (`exec_uat_20260602_080026`, `exec_uat_20260602_055459`).

---

## Solution

1. Removed hardcoded **180** from `core/video_provider_router.py`.
2. Added `resolve_runway_browser_max_wait_seconds()` in `providers/runway_browser_support.py` with precedence, clamp, and logging.
3. Router calls `log_runway_wait_config()` before orchestrator construction.

---

## Changes

### `providers/runway_browser_support.py`

| Addition | Purpose |
|----------|---------|
| `DEFAULT_BROWSER_MAX_WAIT_SECONDS = 900` | Frozen default |
| `BROWSER_MAX_WAIT_FLOOR_SECONDS = 60` | Minimum wait |
| `BROWSER_MAX_WAIT_CEILING_SECONDS = 1800` | Maximum wait |
| `clamp_browser_max_wait_seconds()` | Apply floor/ceiling |
| `resolve_runway_browser_max_wait_seconds(session?)` | Authoritative resolution |
| `log_runway_wait_config(session?)` | Prints `[RUNWAY_WAIT_CONFIG] wait_seconds=… source=…` |
| `browser_max_wait_seconds(session?)` | Delegates to resolver (backward compatible) |

**Precedence:**

1. `RUNWAY_BROWSER_MAX_WAIT_SECONDS` env → `env:RUNWAY_BROWSER_MAX_WAIT_SECONDS`
2. `session.operations.runway_browser_max_wait_seconds` (or `execution_runtime.operations`) → `session:operations.runway_browser_max_wait_seconds`
3. `provider_mode_catalog` entry `runway.browser_generation_max_wait_seconds` (optional, when present) → `catalog:…`
4. Default **900** → `default:900`

**Clamp:** all paths → `[60, 1800]` seconds.

### `core/video_provider_router.py`

```python
wait_seconds, _source = log_runway_wait_config()
orchestrator = RunwayBrowserOrchestrator(wait_seconds=wait_seconds)
```

---

## Unchanged (per scope)

- `RunwayBrowserOrchestrator` wait loop logic
- `wait_for_generated_video_url()` detection (still `<video>` src only)
- `RunwayBrowserProvider` / Generate / fill_prompt
- `RunwayPromptComposer` / Content Brain
- Voice, subtitle, assembly, browser launcher
- Hailuo router path (`HailuoMultiClipOrchestrator()` — no wait override)

---

## Validation

**Script:** `project_brain/validate_12j_c2a_runway_timeout_authority.py`

**Result:** **16/16 PASS**

| Test | Result |
|------|--------|
| No `wait_seconds=180` in router | PASS |
| Default resolves to 900 | PASS |
| Env override (600) | PASS |
| Floor 60 / ceiling 1800 | PASS |
| Session override (240) when env unset | PASS |
| Router passes `wait_seconds=900` to orchestrator (mocked) | PASS |
| Composer module untouched | PASS |
| 12J-C composer validator (regression) | 22/22 PASS |

**Sample log:**

```text
[RUNWAY_WAIT_CONFIG] wait_seconds=900 source=default:900
```

---

## Expected Manual UAT Behavior

| Before (12J-C2a) | After (12J-C2a) |
|------------------|-----------------|
| Wait budget **180s** per clip | Wait budget **900s** default per clip |
| Failure ~3–4 min after dispatch | May wait up to **15 min** while Runway generates |
| `[Runway Browser] Waiting for generated video URL (max 180s)...` | `(max 900s)...` |

**Note:** This fix addresses **early timeout only**. If Runway completes but DOM never exposes a detectable `<video>` URL, failure can still occur at 900s until **12J-C2b** (multi-signal detection) and **12J-C2c** (debug bundle).

**Operator override:**

```powershell
$env:RUNWAY_BROWSER_MAX_WAIT_SECONDS = "600"
```

---

## Files Touched

| File | Action |
|------|--------|
| `providers/runway_browser_support.py` | Extended |
| `core/video_provider_router.py` | Fixed |
| `project_brain/validate_12j_c2a_runway_timeout_authority.py` | New |
| `project_brain/PHASE_12J_C2A_RUNWAY_TIMEOUT_AUTHORITY_FIX_REPORT.md` | New |

---

## Next Steps (Not in 12J-C2a)

- **12J-C2b** — Multi-signal completion detection
- **12J-C2c** — Timeout debug artifact bundle
- **12J-C2d** — Download fallbacks A→D
- **12J-C2e** — UI `runway_wait` substate panel
- Optional: add `browser_generation_max_wait_seconds` to `config/provider_mode_catalog.json` for catalog-tier override

---

## References

- `PHASE_12J_C_STEP1_RUNWAY_DOWNLOAD_TRACE.md`
- `PHASE_12J_C_STEP2_RUNWAY_WAIT_DOWNLOAD_HARDENING_DESIGN.md`
- Session: `exec_uat_20260602_080026`
