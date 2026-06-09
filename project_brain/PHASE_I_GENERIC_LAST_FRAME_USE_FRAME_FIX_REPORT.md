# Phase I — Generic Last-Frame Use Frame Fix

**Date:** 2026-06-04  
**Status:** Implemented and validated (structural + simulate)

## Problem

Use Frame used the **visible/current** preview frame on the prior clip card. For Clip 1 that is often still the **starter / first frame**, so Clip 2 restarted from the same image instead of the end of Clip 1.

## Rule (generic)

For every target clip `N` where `N > 1`:

- Continuity source = **last safe frame** of clip `N - 1`
- Never starter image
- Never first frame unless seek fails **and** operator explicitly allows fallback (default: fail with diagnostics)

## Implementation

**Module:** `content_brain/execution/runway_phase_i_last_frame_use_frame.py`

`prepare_last_frame_use_frame_for_clip(navigator, target_clip_index)`:

1. Verify previous clip strictly complete (`evaluate_strict_clip_completion`)
2. Select tracked video card for `previous_clip`
3. Seek preview: `duration - 0.7s` (10s → ~9.0–9.3s, 5s → ~4.3–4.6s); fallback timeline ~90–95%
4. Pause video
5. Verify preview not still at first frame (`currentTime` / duration checks)
6. Scoped **Use Frame** on same card
7. Diagnostics: `project_brain/runway_phase_i_last_frame_use_frame_diagnostics.json`

**Integration:**

- `runway_ui_navigator.py` — `prepare_last_frame_use_frame_for_clip()`
- `runway_continuity_semi_auto.py` — all `use_frame_for_clip_*` steps (no hardcoded clip 2/3)
- `runway_live_smoke_test.py` — `use_frame_last_frame_by_clip` + flattened `clip_N_*` report keys

## Report fields (per target clip N ≥ 2)

| Field | Meaning |
|-------|---------|
| `clip_N_use_frame_source_clip` | N - 1 |
| `clip_N_use_frame_source` | `last_safe_frame` |
| `clip_N_previous_clip_seeked_to_last_frame` | seek succeeded |
| `clip_N_seek_time_used` | seconds |
| `clip_N_seek_strategy` | e.g. `duration_minus_0.7s`, `timeline_90_95_percent` |

Also: `use_frame_last_frame_by_clip` map for arbitrary `clip_count`.

## Validation

```bash
python project_brain/validate_phase_i_last_frame_use_frame.py
```

Covers: clip_count 3 and 5 plans, approval gates `1 + 2*clip_count`, clip 2–5 chain, starter not reused, no hardcoded clip 2/3-only logic.

**Unchanged:** StoryBrief, Prompt Builder, Provider Router; approval gate **formula** unchanged (7 gates for 3 clips, 11 for 5 clips).

## Operator note

Clip 1 still uses **starter image → Use to Video** only. Continuity Use Frame runs only for `use_frame_for_clip_2` … `use_frame_for_clip_{clip_count}` with last-frame seek on the prior clip card.
