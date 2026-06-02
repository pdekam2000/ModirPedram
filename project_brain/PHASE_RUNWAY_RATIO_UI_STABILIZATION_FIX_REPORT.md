# Runway 16:9 UI Stabilization Fix

**Date:** 2026-05-31  
**Observation:** During Runway prep, 16:9 is selected briefly then disappears after UI re-render (often triggered by duration menu interaction).

**Scope:** `RunwayBrowserProvider` prep only. No changes to Content Brain, voice, subtitle, assembly, or download/wait logic.

---

## Root cause

Ratio and duration were set sequentially with a short fixed sleep (`0.75s`). Runway’s React UI can re-render after duration selection and **reset** the aspect ratio chip before Generate. Prep proceeded if 16:9 was visible only at click time, not after stabilization.

---

## Fix

### Flow (`prepare_clip_for_generate`)

1. Prompt → verify (unchanged)  
2. Set 16:9 (strict)  
3. Set 10s (strict)  
4. **`_stabilize_and_verify_before_generate()`** — new gate before `[RUNWAY_READY_TO_GENERATE]`

### Stabilization (`_wait_for_ratio_duration_ui_stable`)

- Post-settle sleep (default **1.25s**)  
- Poll body text every **0.4s** until **16:9** and **10s** both present for **2 consecutive** polls (configurable)  
- Max wait **8s** (configurable)  
- Logs `[RUNWAY_UI_STABILIZE]` including reset detection

### Ratio retry (once)

If 16:9 not stable after wait:

1. `[RUNWAY_RATIO_RETRY]` — `set_ratio_16_9(strict=True)` again  
2. Re-verify prompt; re-apply with `set_prompt_verified` if incomplete  
3. Re-apply `set_duration_10s(strict=True)`  
4. Re-run stabilization wait  
5. Fail prep if ratio, duration, or prompt still invalid (Generate not clicked)

---

## Observability (`record_clip_prep`)

| Field | Meaning |
|-------|---------|
| `ratio_selected_before_generate` | 16:9 visible in UI at gate |
| `duration_selected_before_generate` | 10s visible at gate |
| `prompt_still_verified_before_generate` | Prompt verify passed at gate |
| `ui_stabilized_after_ratio` | Consecutive stable polls succeeded |

Also refreshes `ratio_verified`, `duration_verified`, `prompt_verified` at gate time.

---

## Config (env)

| Variable | Default |
|----------|---------|
| `RUNWAY_BROWSER_RATIO_DURATION_POST_SETTLE_SECONDS` | 1.25 |
| `RUNWAY_BROWSER_RATIO_DURATION_STABLE_POLL_SECONDS` | 0.4 |
| `RUNWAY_BROWSER_RATIO_DURATION_STABLE_POLLS` | 2 |
| `RUNWAY_BROWSER_RATIO_DURATION_STABILIZE_TIMEOUT_SECONDS` | 8 |

---

## Files

| File | Change |
|------|--------|
| `providers/runway_browser_provider.py` | Stabilize wait, retry, pre-generate gate |
| `providers/runway_browser_support.py` | Stabilization timing helpers |
| `content_brain/execution/runway_browser_observability.py` | Four new prep fields |
| `project_brain/validate_runway_ratio_ui_stabilization.py` | Validator |

---

## Validation

```bash
python project_brain/validate_runway_ratio_ui_stabilization.py
```

---

## UAT signals

Stdout before Generate:

```text
[RUNWAY_UI_STABILIZE] stable ratio+duration (2/2 polls)
[RUNWAY_PREP_BEFORE_GENERATE] ratio=True duration=True prompt=True ui_stabilized=True
[RUNWAY_READY_TO_GENERATE]
```

Session JSON: `runway_browser_obs.ratio_selected_before_generate === true` and `ui_stabilized_after_ratio === true`.

If ratio resets: `[RUNWAY_UI_STABILIZE] reset detected` then optional `[RUNWAY_RATIO_RETRY]`.
