# Kling Multishot UI Map — P0 Relabel Report

**Phase:** KLING-MULTISHOT-RELABEL-P0  
**Map file:** `project_brain/runway_ui_mapping/runway_ui_map.json`  
**Apply script:** `project_brain/apply_kling_multishot_relabel_p0.py`  
**Summary JSON:** `project_brain/kling_multishot_relabel_p0_summary.json`  
**Date:** 2026-06-16  
**Browser automation:** None  
**Generate clicked:** No  
**Credits spent:** No  

---

## Executive Summary

All **P0 selector issues** from the validation report were corrected using **scan ground-truth elements** (`elements` inventory from 2026-06-16 scan). **17 labels** were patched or added. **Static selector validation: 17/17 PASS (100%)** — zero generic-selector warnings, zero blocking errors.

Kling automation may proceed to **shadow-mode** (read-only / non-generate flows).

| Metric | Result |
|--------|--------|
| Labels patched | 17 |
| Validation pass rate | **100%** |
| Generic selector warnings | **0** |
| Generate clicked | **No** |
| Credits spent | **No** |

---

## P0 Fixes Applied

### 1. `provider_kling_3_pro`

| | Before | After |
|---|--------|-------|
| Target | Kling 3.0 **tab** | **Kling 3.0 Pro** bottom-bar button |
| Element | `el_001` tab | **`btn_030`** |
| CSS | `#…-tab-kling-3` | `#react-aria3046197000-\:r1s0\:` |
| Playwright | — | `getByRole('button', { name: /Kling 3\.0 Pro/i })` |
| Text | `Kling 3.0` | `Kling 3.0 Pro` |
| aria-label | — | `Video models` |

### 2. `audio_toggle_on`

| | Before | After |
|---|--------|-------|
| Target | SVG `path` (2×7 px) | **Audio settings** button |
| Element | `path` | **`btn_024`** |
| CSS | `path` | `#react-aria3046197000-\:r1r1\:` |
| Playwright | — | `getByRole('button', { name: /Audio settings/i })` |
| ON detection | Unreliable | Button text **`· On`** |

### 3. `shot_1_prompt`

| | Before | After |
|---|--------|-------|
| Tag | empty `<p>` | **`div[contenteditable]` textbox** |
| Element | `p` | **`input_006`** |
| CSS | `p` | `div[aria-label="Shot 1 prompt"][contenteditable="true"]` |
| Playwright | — | `getByRole('textbox', { name: 'Shot 1 prompt' })` |

### 4. `shot_2_prompt`

| | Before | After |
|---|--------|-------|
| Tag | empty `<p>` | **`div[contenteditable]` textbox** |
| Element | `p` | **`input_007`** |
| CSS | `p` | `div[aria-label="Shot 2 prompt"][contenteditable="true"]` |
| Playwright | — | `getByRole('textbox', { name: 'Shot 2 prompt' })` |

### 5. `multishot_tab`

| | Before | After |
|---|--------|-------|
| CSS | `label` (generic) | `input[name="react-aria3046197000-:r1ps:"][type="radio"]` |
| Element | generic label | **`input_005`** (Multishot radio) |
| Playwright | — | `getByText('Multishot', { exact: true })` |

### 6. `first_frame_upload`

| | Before | After |
|---|--------|-------|
| CSS | `span` (generic) | `#react-aria3046197000-\:r1q3\:` |
| Element | Upload span | **`btn_017`** (Upload button in first-frame zone) |
| Playwright | — | `getByRole('button', { name: /First Video Frame Upload/i })` |

**Note:** Drop-zone container remains **`btn_010`** (`First Video Frame Upload`); relabel targets the actionable **Upload** control inside it.

### 7. `shot_1_duration_menu`

| | Before | After |
|---|--------|-------|
| CSS | `svg` | `button[aria-label="Shot duration"]:nth-of-type(1)` |
| Element | svg icon | **`btn_020`** (shows `3s`) |
| Playwright | — | `getByRole('button', { name: 'Shot duration' }).first()` |

**Canonical label added:** `shot_1_duration_menu` (legacy alias `shot 1 duration menu` retained).

### 8. `shot_1_duration_12s`

| | Before | After |
|---|--------|-------|
| CSS | `span` | `[role="listbox"] [role="option"]:last-child` |
| Playwright | — | `getByRole('option', { name: '12 seconds' })` |
| Use | — | Open shot 1 duration menu first |

**Canonical label added:** `shot_1_duration_12s` (legacy alias `shot 1 duration 12 s` retained).

---

## Additional Labels Captured

| Label | Source | CSS (primary) | Status |
|-------|--------|---------------|--------|
| `shot_2_duration_menu` | `btn_022` | `button[aria-label="Shot duration"]:nth-of-type(2)` | PASS |
| `shot_2_duration_3s` | `btn_022` context | `[role="listbox"] [role="option"]:first-child` | PASS |
| `add_shot_button` | `btn_023` | `button[aria-label="Add shot"]` | PASS |
| `shot_3_prompt` | Pattern from shot 1/2 | `div[aria-label="Shot 3 prompt"][contenteditable="true"]` | PASS (inferred) |
| `shot_4_prompt` | Pattern from shot 1/2 | `div[aria-label="Shot 4 prompt"][contenteditable="true"]` | PASS (inferred) |
| `shot_5_prompt` | Pattern from shot 1/2 | `div[aria-label="Shot 5 prompt"][contenteditable="true"]` | PASS (inferred) |

**Legacy alias:** `+Add shot` → canonical `add_shot_button`.

### Shots 3–5 inference note

Shots 3–5 prompts are **not visible in the default 2-shot scan**. Selectors follow the Runway `aria-label="Shot N prompt"` pattern observed on shots 1–2. **Operator re-confirm** after 1–3 Add shot clicks is recommended before production automation; shadow-mode should verify element presence before fill.

---

## Validation Results

Command:

```powershell
python project_brain/apply_kling_multishot_relabel_p0.py
```

| Label | Generic warning | Errors | Pass |
|-------|-----------------|--------|------|
| `provider_kling_3_pro` | No | 0 | Yes |
| `audio_toggle_on` | No | 0 | Yes |
| `shot_1_prompt` | No | 0 | Yes |
| `shot_2_prompt` | No | 0 | Yes |
| `multishot_tab` | No | 0 | Yes |
| `first_frame_upload` | No | 0 | Yes |
| `shot_1_duration_menu` | No | 0 | Yes |
| `shot_1_duration_12s` | No | 0 | Yes |
| `shot_2_duration_menu` | No | 0 | Yes |
| `shot_2_duration_3s` | No | 0 | Yes |
| `add_shot_button` | No | 0 | Yes |
| `shot_3_prompt` | No | 0 | Yes |
| `shot_4_prompt` | No | 0 | Yes |
| `shot_5_prompt` | No | 0 | Yes |
| Legacy aliases (3) | No | 0 | Yes |

**Overall: 17/17 PASS — 100%**

---

## Safety Confirmation

Unchanged from prior map:

```json
{
  "generate_never_auto_clicked": true,
  "requires_approval": ["generate_button"],
  "auto_click_blocklist": ["generate", "create", "submit", "upgrade", "purchase", "buy", "subscribe", "delete"]
}
```

| Check | Status |
|-------|--------|
| Generate clicked during relabel | **No** |
| Credits spent | **No** |
| `generate_button` still approval-gated | **Yes** |
| Relabel phase automated Generate | **No** |

---

## Fifteen-Second Multishot Strategies (unchanged)

| Strategy | Config | Default for |
|----------|--------|-------------|
| **B — five_shot_story** | 5 × 3 s = 15 s | Story / fantasy / cinematic |
| **A — two_shot_compact** | 12 s + 3 s = 15 s | Simple scenes |

**Default UI state:** 2 shots × 3 s = **6 s total** (`btn_026` Duration).

**Strategy B map readiness:** `add_shot_button` + `shot_3/4/5_prompt` selectors ready; runtime must verify DOM after each Add shot.

**Strategy A map readiness:** `shot_1_duration_menu` + `shot_1_duration_12s` + `shot_2_duration_3s` ready.

---

## Remaining Non-P0 Items

| Item | Status | Action |
|------|--------|--------|
| Legacy label `Multishot` (duplicate) | Still generic `label` | Deprecate in favor of `multishot_tab` |
| `kling 3.0` tab label | Stable tab ID (OK) | Keep separate from `provider_kling_3_pro` |
| Shots 3–5 operator confirm | Inferred | Re-label after Add shot in live session |
| React aria ID drift | Session-scoped `#react-aria…` | Prefer Playwright role/text locators at runtime |

---

## Next Step: Shadow-Mode

Approved entry criteria met:

- [x] 100% P0 selector validation pass  
- [x] No generic selector warnings on patched labels  
- [x] No Generate click  
- [x] No credit consumption  

**Shadow-mode may:**

- Load map and resolve locators  
- Detect default 2-shot / 3 s state  
- Verify audio ON, multishot tab, provider chip  
- **Must not** click Generate without explicit approval gate  

---

## Files Changed

| File | Change |
|------|--------|
| `project_brain/runway_ui_mapping/runway_ui_map.json` | 17 labels patched (`updated_at` refreshed) |
| `project_brain/apply_kling_multishot_relabel_p0.py` | P0 relabel + validation runner (new) |
| `project_brain/kling_multishot_relabel_p0_summary.json` | Machine-readable validation summary (new) |

No Runway automation code was enabled in this phase.
