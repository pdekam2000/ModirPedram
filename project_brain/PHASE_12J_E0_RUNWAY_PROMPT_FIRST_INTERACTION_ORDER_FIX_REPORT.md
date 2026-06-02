# PHASE 12J-E0 — Runway Prompt-First Interaction Order Fix Report

**Date:** 2026-06-02  
**Problem:** Real 40s UAT showed truncated prompts (e.g. `evidence — specific t`) when ratio/duration controls were applied **before** prompt entry, causing focus loss and editor re-render.  
**Scope:** Runway browser prompt insertion order and verification only — no Content Brain, Story Intelligence, Prompt Composer, Voice, Subtitle, Assembly, or download/wait changes.

---

## Summary

| Requirement | Status |
|-------------|--------|
| Prompt before ratio/duration | **Done** |
| Reliable fill/paste (not slow typing) | **Done** — `locator.fill()` + contenteditable fallback |
| Full prompt verification + retry | **Done** |
| `PROMPT_INJECTION_INCOMPLETE` on failure | **Done** |
| Generate only after verified prompt | **Done** |
| Observability fields | **Done** — persisted on session |
| Download / `wait_for_generated_video_url` | **Unchanged** |

---

## Required sequence (implemented)

```
Try it now
  → wait for editor ready
  → insert FULL prompt
  → verify FULL prompt
  → set 16:9 → verify
  → set 10s → verify
  → [RUNWAY_READY_TO_GENERATE]
  → click Generate (re-verify prompt)
```

### Once per run: `prepare_gen45_page`

- Open Runway → Video mode → Gen-4.5  
- **Try it now** → **generate editor ready**  
- **Does not** set ratio or duration (12J-E0)

### Per clip: `prepare_clip_for_generate(prompt)`

1. `[RUNWAY_PROMPT_SET_START]`  
2. Paste/fill prompt (`fill()` preferred)  
3. `[RUNWAY_PROMPT_VERIFY]` — length, first/last 50 chars, placeholder check  
4. On fail: clear + retry once  
5. `[RUNWAY_PROMPT_SET_DONE]`  
6. `[RUNWAY_RATIO_SET]` — 16:9 strict  
7. `[RUNWAY_DURATION_SET]` — 10s strict  
8. `[RUNWAY_READY_TO_GENERATE]`  

### `click_generate`

- Re-runs full prompt verification  
- **Does not click** if prompt incomplete or `PROMPT_INJECTION_INCOMPLETE`

---

## Prompt verification rules

| Check | Rule |
|-------|------|
| Length | `actual >= max(32, expected × 0.90)` |
| Prefix | First 50 characters must match |
| Suffix | Last 50 characters must match |
| Placeholder | Reject if editor placeholder text remains and field is shorter than expected |
| Retry | One clear + paste retry |
| Fail code | `PROMPT_INJECTION_INCOMPLETE` |

Removed behaviors that caused truncation:

- `keyboard.type(prompt, delay=5)`  
- `mouse.click(1200, 700)` after typing (focus steal)

---

## Observability fields (session)

Persisted via `RunwayBrowserObservability.record_clip_prep()` → `execution_runtime.operations.runway_browser_obs`:

| Field | When set |
|-------|----------|
| `prompt_expected_length` | After verify attempt |
| `prompt_actual_length` | After verify attempt |
| `prompt_verified` | `true` on success; `false` on failed attempt |
| `ratio_verified` | After 16:9 selection |
| `duration_verified` | After 10s selection |
| `clip_index` | Per-clip observability instance |
| `clip_prep_updated_at` | ISO timestamp |

**Note:** Prompt **text** is not stored in observability (session-safe).

---

## Log tags

| Tag | Meaning |
|-----|---------|
| `[RUNWAY_PROMPT_SET_START]` | Starting paste/fill |
| `[RUNWAY_PROMPT_SET_DONE]` | Verify passed |
| `[RUNWAY_PROMPT_VERIFY]` | `expected_len`, `actual_len`, `ok=` |
| `[RUNWAY_RATIO_SET]` | `selected=`, `clicked=` |
| `[RUNWAY_DURATION_SET]` | `target=`, `verified=` |
| `[RUNWAY_READY_TO_GENERATE]` | Clip prep complete |

---

## Files changed

| File | Role |
|------|------|
| `providers/runway_browser_provider.py` | Order, verify, logs, `_record_clip_prep_obs` |
| `providers/runway_browser_support.py` | `PROMPT_INJECTION_INCOMPLETE`, ratio constants |
| `orchestrators/runway_browser_orchestrator.py` | `prepare_clip_for_generate` per clip |
| `content_brain/execution/runway_browser_observability.py` | `record_clip_prep()` |
| `project_brain/validate_12j_e0_runway_interaction_order.py` | Static + obs persist test |
| `project_brain/validate_12j_d_b_step1_runway_prep_generate_duration.py` | Updated prep order checks |

**Not modified:** `wait_for_generated_video_url`, `RunwayDownloadProvider`, Content Brain, composers, voice/subtitle/assembly.

---

## Validation

```powershell
python project_brain/validate_12j_e0_runway_interaction_order.py
python project_brain/validate_12j_d_b_step1_runway_prep_generate_duration.py
```

| # | Requirement | Result |
|---|-------------|--------|
| 1 | Full prompt before ratio/duration | **PASS** |
| 2 | Partial prompt rejected | **PASS** — verify + `PROMPT_INJECTION_INCOMPLETE` |
| 3 | Generate never clicked if incomplete | **PASS** — `click_generate` re-verify |
| 4 | 16:9 after prompt verify | **PASS** |
| 5 | 10s after prompt verify | **PASS** |
| 6 | Generate locator compatible | **PASS** — unchanged `_resolve_generate_button` |
| 7 | No download/wait changes | **PASS** — orchestrator wait path intact |

Observability persist test: **PASS** (session `validate_12j_e0_obs_session`).

---

## Operator verification

Re-run supervised Runway UAT. In terminal you should see:

1. `[RUNWAY_PROMPT_SET_START]` → `[RUNWAY_PROMPT_VERIFY] ok=True` → `[RUNWAY_PROMPT_SET_DONE]`  
2. Then `[RUNWAY_RATIO_SET]` and `[RUNWAY_DURATION_SET]`  
3. Then `[RUNWAY_READY_TO_GENERATE]` before `[RUNWAY_GENERATE_CLICKED]`

In Runtime Studio / session JSON, check `runway_browser_obs.prompt_verified === true` before `ratio_verified` / `duration_verified`.

---

## Related

- `PHASE_12J_E_RUNWAY_REAL_OUTPUT_DETECTION_AUDIT.md` — empty-state URL fallback (out of scope for 12J-E0)  
- `PHASE_12J_E0_RUNWAY_INTERACTION_ORDER_FIX_REPORT.md` — earlier report (superseded by this deliverable name)
