# PHASE 12J-D-B STEP 1 — Runway Prep + Generate Locator + UAT 10s Default

**Date:** 2026-05-31  
**Status:** Implemented  
**Scope:** Runway browser prep, Generate locator, provider-aware UAT duration only

---

## Summary

UAT no longer defaults to 45s/20s for all providers. **Runway Browser** defaults to **10s**; **Hailuo Browser** defaults to **8s** (smoke safe cap for Hailuo live voice remains **6s**). Runway automation now runs an explicit **prep sequence** (Video mode → Gen-4.5 → 10s duration → prompt ready) before typing, uses **robust Generate button resolution**, and **fails loud** with `prep_debug` when prep or click preconditions fail.

**Not modified:** Content Brain, topic grammar, prompt composer, voice/subtitle/assembly, browser launcher, download/wait logic, Hailuo browser generation steps.

---

## Part A — Provider-aware UAT duration

| Provider | UI/API default | Smoke safe (live voice, unchanged) |
|----------|----------------|-------------------------------------|
| `runway_browser` | 10s | 10s |
| `hailuo_browser` | 8s | 6s |
| `mock` | 10s | 10s |

**Files:**
- `content_brain/execution/uat_runtime_profile.py` — `UAT_DEFAULT_DURATION_BY_VIDEO_PROVIDER`, `uat_default_duration_seconds()`
- `ui/api/schemas/uat_runtime.py` — `model_validator` applies provider default when `duration_seconds` omitted
- `ui/web/src/utils/uatRuntimeEligibility.ts` — `uatDefaultDurationSeconds()`
- `ui/web/src/pages/UatRuntimePage.tsx` — initial form `10s`; switching video provider resets duration
- `project_brain/run_12b_uat_supervised_pipeline.py` — CLI omits duration → provider default

Max duration remains **90s**. Explicit `10` / `8` pass schema validation.

---

## Part B — Runway page prep

**File:** `providers/runway_browser_provider.py`

`prepare_gen45_page()` sequence:

1. `open_runway()` — Runway app URL
2. `select_video_mode()` — Video tab / Generate / Generate Video (multi-selector)
3. `select_gen45()` — Gen-4.5 tab (fail if not visible)
4. `enter_generate_editor()` — **Try it now** on `mode=apps` landing → wait for editor (no Generate / no credits)
5. `set_ratio_16_9()` — best effort
6. `set_duration_10s(strict=True)` — only after editor has prompt box

**Try it now fix (operator):** Gen-4.5 card page showed `mode=apps` with CTA **Try it now** but prep skipped it and failed with `textarea_count=0`. Prep now clicks **Try it now** first, polls until `prompt_box_count > 0`, then sets duration.

**Observability steps** (`content_brain/execution/runway_browser_observability.py`):

- `selecting_video_mode`
- `selecting_gen45_model`
- `clicking_try_it_now`
- `try_it_now_clicked`
- `waiting_for_generate_editor`
- `generate_editor_ready`
- `setting_duration_10s`
- `prompt_box_ready`
- `ready_for_generate`

On failure: `_fail_prep()` → `prep_debug` via `capture_runway_prep_debug()` (no Generate click, no placeholder video).

**Orchestrator:** `apply_default_settings()` removed from clip loop; settings applied during prep only.

---

## Part C — Generate button locator

`click_generate()` prechecks:

- Prompt has text (`_prompt_has_text`)
- Not already generating (`_is_already_generating`)

Locator order (`_resolve_generate_button`):

1. `role=button` name `/Generate/i`
2. text `Generate` (exact)
3. text `Generate Video` (non-exact)
4. `button` filter `/Generate/i`
5. `button[aria-label*='Generate']`

Then: visible, enabled, click → `[RUNWAY_GENERATE_CLICKED]` + queue wait.

Explicit error: `Generate button not found. Tried role=button /Generate/i, ...`

Removed reliance on **only** `get_by_text("Generate Video", exact=True)`.

---

## Part D — Validation

```bash
python project_brain/validate_12j_d_b_step1_runway_prep_generate_duration.py
python project_brain/validate_12j_c2a_runway_browser_observability.py
python project_brain/validate_11e_c_runway_browser_hardening.py
```

**Step 1 validator** covers: provider defaults (10/8), schema, UI switch, prep OBS steps, Generate locator strategy, prep-before-prompt ordering, orchestrator wiring, C2A regression.

---

## Operator success criteria (next UAT)

- Duration field shows **10s** with Runway Browser selected
- OBS progresses through video mode → Gen-4.5 → duration → prompt ready → filling → generate clicked
- No manual Generate click required when prep succeeds
- Failures show explicit step + `prep_debug` in session `runway_browser_obs`

---

## Files touched

| File | Change |
|------|--------|
| `providers/runway_browser_provider.py` | Prep hardening, Generate locator |
| `providers/runway_browser_support.py` | `capture_runway_prep_debug`, `RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS` |
| `content_brain/execution/runway_browser_observability.py` | Prep step keys |
| `orchestrators/runway_browser_orchestrator.py` | Settings only in prep |
| `content_brain/execution/uat_runtime_profile.py` | Provider defaults |
| `ui/api/schemas/uat_runtime.py` | Provider default duration |
| `ui/web/src/pages/UatRuntimePage.tsx` | 10s default + provider switch |
| `ui/web/src/utils/uatRuntimeEligibility.ts` | `uatDefaultDurationSeconds` |
| `project_brain/run_12b_uat_supervised_pipeline.py` | CLI provider default |
| `project_brain/validate_12j_d_b_step1_runway_prep_generate_duration.py` | New |
| `project_brain/validate_11e_c_runway_browser_hardening.py` | Fake provider accepts `runway_obs` |

---

*End of STEP 1 report.*
