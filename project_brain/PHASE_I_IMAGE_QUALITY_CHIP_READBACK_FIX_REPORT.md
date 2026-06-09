# Phase I — Image Quality Chip Readback Fix

**Date:** 2026-06-04  
**Status:** Implemented and validated (structural + simulate)

## Problem

Live Phase I failed at `005_select_image_quality` with:

```text
expected image_quality_2k (2K), detected '4K'
```

Operator confirmed **2K was selected visibly**. Root cause: toolbar chip readback scanned the whole lower page and picked the **smallest-area** quality-like text (often a stale **4K** node outside the image composer toolbar), not the **active** chip in the image settings row.

## Fix summary

| Area | Change |
|------|--------|
| Scoped readback | `_image_toolbar_chip_readback_eval_script()` finds the image composer toolbar (prompt anchor → parent row with count+aspect+quality) |
| Active chip | Prefer `aria-pressed` / `aria-selected` / `data-state=active` / selected classes; then button-like chips; then **largest** area in-toolbar (not smallest globally) |
| Settle | `CHIP_READBACK_SETTLE_MS` wait before verification after select |
| Retry | Up to `CHIP_VERIFY_MAX_RETRIES` with delay; reopen quality menu on mismatch before final fail |
| Click scope | Image toolbar chip open uses `_image_toolbar_chip_click_eval_script()` on image generation page |
| Diagnostics | `project_brain/runway_phase_i_image_quality_chip_diagnostics.json` on quality mismatch |

**Not modified:** StoryBrief Builder, Prompt Builder content, continuity/download/clip-2 transition logic.

## Diagnostics file fields

On quality verification failure:

- `all_quality_chip_candidates` (text, bbox, active, in_toolbar)
- `active_chip_candidate`
- `toolbar_container_selector`
- `expected_texts` / `detected`
- `screenshot_path`
- `retry_attempts`
- `last_action_log_entries` (last 10)

## Validation

```bash
python project_brain/validate_phase_i_image_quality_chip_readback.py
```

All checks PASS, including:

- 2K simulate readback and starter settings
- Parsed payload: active 2K wins over stale 4K candidate
- Retry before fail; diagnostics JSON written
- Phase I 3-clip simulate rehearsal still completes with `detected_image_quality=2K`

## Operator re-run

Re-run Phase I live from **Runway Live Smoke → 3-Clip Continuity**. If quality still fails, attach:

- `project_brain/runway_phase_i_image_quality_chip_diagnostics.json`
- `project_brain/runway_phase_i_3clip_last_report.json`
- Chip diagnostic screenshots from the smoke artifact dir
