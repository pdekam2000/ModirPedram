# Kling Multishot Live Dry-Run Stabilization Report

**Phase:** KLING-MULTISHOT-LIVE-DRY-RUN-STABILIZATION  
**Date:** 2026-06-16  
**Result:** Live CDP dry-run **PASSED** — all steps through Generate verification, no Generate click, no credits spent

---

## Summary

Live CDP automation for Kling Multishot 2-shot continuity is stabilized. The root cause (stale React aria IDs for `provider_kling_3_pro`) was fixed by:

1. A stable locator layer (`kling_multishot_locator.py`) that prefers role/text/aria strategies over React IDs
2. Live CDP selector refresh (`refresh_kling_multishot_selectors_from_cdp.py`) writing stable CSS into `runway_ui_map.json`
3. Shadow runner v2 using locators, overlay-safe clicks, and per-step screenshots

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/kling_multishot_locator.py` | Stable Playwright locator strategies (role/text/aria before React ID) |
| `project_brain/refresh_kling_multishot_selectors_from_cdp.py` | Refresh map selectors from live Runway CDP page |
| `project_brain/validate_kling_multishot_live_dry_run_stabilization.py` | Stabilization validation suite (all PASS) |
| `project_brain/KLING_MULTISHOT_LIVE_DRY_RUN_STABILIZATION_REPORT.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `tools/kling_multishot_shadow_runner.py` | v2 — stable locators, screenshots, overlay-safe clicks, multishot already-selected detection |
| `project_brain/runway_ui_mapping/runway_ui_map.json` | Refreshed stable CSS for 9 Kling controls (live CDP) |

---

## Refreshed Selectors

| Label | Old (stale) | New (stable) | Live strategy |
|-------|-------------|--------------|---------------|
| `provider_kling_3_pro` | `#react-aria3046197000-:r1s0:` | `button:has-text("Kling 3.0 Pro")` | `text_kling_3_pro` |
| `multishot_tab` | `input[name="react-aria..."]` | `label:has-text("Multishot")` | `text_multishot` |
| `audio_toggle_on` | `#react-aria3046197000-:r1r1:` | `button[aria-label="Audio settings"]` | `role_button_audio_settings` |
| `first_frame_upload` | `#react-aria3046197000-:r1q3:` | `button[aria-label="Upload"]` | `role_button_upload` |
| `shot_1_prompt` | (unchanged aria) | `div[aria-label="Shot 1 prompt"][contenteditable="true"]` | `role_textbox_shot_1` |
| `shot_2_prompt` | (unchanged aria) | `div[aria-label="Shot 2 prompt"][contenteditable="true"]` | `role_textbox_shot_2` |
| `shot_1_duration_menu` | nth-of-type (confirmed) | `button[aria-label="Shot duration"]:nth-of-type(1)` | `role_button_shot_duration_first` |
| `shot_2_duration_menu` | nth-of-type (confirmed) | `button[aria-label="Shot duration"]:nth-of-type(2)` | `role_button_shot_duration_nth1` |
| `generate_button` | `#react-aria3046197000-:r2cu:` | `button:has-text("Generate")` | `role_button_generate` |

Refresh summary: `project_brain/kling_multishot_selector_refresh_summary.json`

---

## Controls Successfully Reached (Live Dry-Run)

| Step | Control | Status | Locator strategy |
|------|---------|--------|------------------|
| 01 | `provider_kling_3_pro` | passed | `text_kling_3_pro` |
| 02 | `multishot_tab` | passed (already selected) | `text_multishot` |
| 03 | `audio_toggle_on` | passed (· On) | `role_button_audio_settings` |
| 04 | `first_frame_upload` | passed (detected) | `role_button_upload` |
| 05 | `shot_1_duration_12s` | passed (12s verified) | `role_option_12_seconds` |
| 06 | `shot_2_duration_3s` | passed (3s verified) | default confirmed |
| 07 | `shot_1_prompt` | passed (50 chars) | `role_textbox_shot_1` |
| 08 | `shot_2_prompt` | passed (54 chars) | `role_textbox_shot_2` |
| 09 | `generate_button` | **blocked** (visible, not clicked) | `role_button_generate` |

Full run log: `project_brain/kling_multishot_shadow_run_summary.json`

---

## Final Dry-Run Checklist

| Check | Result |
|-------|--------|
| CDP connected | Yes (`127.0.0.1:9222`) |
| Runway tab found | Yes |
| Provider Kling 3.0 Pro | Yes |
| Multishot mode | Yes (already active) |
| Audio ON | Yes |
| First frame upload detected | Yes |
| Shot 1 duration = 12s | Yes |
| Shot 2 duration = 3s | Yes |
| Shot 1 prompt filled | Yes |
| Shot 2 prompt filled | Yes |
| Generate visible + approval-gated | Yes |
| Generate clicked | **No** |
| Credits spent | **No** |
| Add Shot used | **No** |
| `dry_run=true` | Yes |
| `ok=true` | Yes |

---

## Screenshots / Logs

Per-step screenshots saved under:

`project_brain/runway_ui_mapping/screenshots/kling_multishot_live_dry_run/`

| Screenshot | Step |
|------------|------|
| `01_provider_kling_3_pro_20260616T185445.png` | Provider selected |
| `02_multishot_tab_20260616T185448.png` | Multishot mode |
| `03_audio_toggle_on_20260616T185451.png` | Audio ON |
| `04_first_frame_upload_20260616T185453.png` | Upload control |
| `06_shot_2_duration_3s_20260616T185539.png` | Durations set |
| `07_shot_1_prompt_20260616T185542.png` | Shot 1 prompt |
| `08_shot_2_prompt_20260616T185546.png` | Shot 2 prompt |
| `09_generate_button_20260616T185549.png` | Generate visible (not clicked) |

Note: Step 05 screenshot timed out (font load); step still passed with duration verified as `12s`.

---

## Safety Confirmations

- **Generate clicked:** `false`
- **Credits spent:** `false`
- **Add shot used:** `false`
- **Approval gate:** `generate_button` in `safety.requires_approval`
- **Unstable React ID fallback rejected** for Generate when only unstable selector resolves

---

## Validation

```text
python project_brain/validate_kling_multishot_live_dry_run_stabilization.py
→ All checks passed

python project_brain/validate_kling_multishot_shadow_runner.py
→ All checks passed (10/10)
```

---

## Stabilization Fixes Applied

1. **Provider:** `getByRole` / `button:has-text("Kling 3.0 Pro")` instead of React ID; skip click if already Kling 3.0 Pro
2. **Multishot:** Detect `data-selected=true` — skip click when already active (avoids body overlay intercept)
3. **Overlay clicks:** Escape + force click fallback for duration menus blocked by overlays
4. **Map refresh:** Live CDP writes stable CSS overrides into `runway_ui_map.json`

---

## Next Phase

**PHASE KLING-MULTISHOT-LIVE-APPROVAL-GATED** (after approval):

- Wire explicit operator approval before any Generate click
- Still no auto-Generate without human approval token
- Optional: first-frame upload path in live flow

---

## References

- `project_brain/KLING_STORY_ARCHITECTURE_DESIGN.md`
- `project_brain/KLING_MULTISHOT_SHADOW_AUTOMATION_REPORT.md`
- `tools/kling_multishot_shadow_runner.py`
- `content_brain/execution/kling_multishot_locator.py`
