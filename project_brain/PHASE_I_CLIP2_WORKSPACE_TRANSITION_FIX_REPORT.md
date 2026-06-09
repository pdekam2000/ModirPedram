# Phase I — Clip 2 Workspace Transition Fix

**Date:** 2026-06-03  
**Status:** Implemented and validated (structural + simulate rehearsal)

## Problem

Phase I live run completed Clip 1 (starter image → video, prompt fill, generate, download, Use Frame) but failed at `020_video_prompt_clip_2` when filling `div[aria-label="Prompt"]`. The video prompt editor was not ready/clickable immediately after Download MP4 (clip 1) and Use Frame (clip 2). Stale `video_transition_verified` from the starter Use-to-Video step could satisfy the old gate while the prompt control was still blocked by overlays or a remounting composer.

## Root cause

1. Reused `video_transition_verified` from step 011 for clip ≥ 2 prompt fill.
2. No settle after download (browser save/download UI).
3. No settle after Use Frame (frame apply + composer remount).
4. `fill_prompt_control` assumed mapped prompt selector was immediately interactable.

## Changes (scope-limited)

| Module | Change |
|--------|--------|
| `runway_ui_navigator.py` | `clear_stale_video_transition_for_clip`, `settle_after_download_clip`, `settle_after_use_frame_clip`, `wait_for_prompt_editor_ready`, `_try_focus_prompt_selector`, extended `collect_phase_i_failure_diagnostics` |
| `runway_continuity_semi_auto.py` | Handlers for settle steps; clip prompt uses readiness check (no stale transition gate) |
| `runway_continuity_dry_run.py` | Logical settle steps after download (non-final) and after use-frame |
| `runway_live_smoke_test.py` | Report fields `clip_2/3_prompt_ready_*`; broader failure diagnostics |

**Not modified:** StoryBrief Builder, Prompt Builder content, Provider Router, Assembly/Voice/Subtitle, approval semantics (still **7** gates).

## New dry-run step order (3-clip excerpt)

After each non-final download:

- `download_mp4_clip_N` → `settle_after_download_clip_N`

After each use-frame (clips 2–3):

- `use_frame_for_clip_N` → `settle_after_use_frame_clip_N` → `video_prompt_clip_N`

Dry-run records these steps only; no real browser waits in dry-run.

## Prompt readiness (`wait_for_prompt_editor_ready`)

Before every `video_prompt_clip_*` (especially clip ≥ 2):

- Clear stale transition marker when `clip_index >= 2`
- Poll until a prompt candidate is visible, enabled, non-zero bbox, not modal-covered
- Trial click / composer focus fallback
- Use winning selector for `fill_prompt_control(..., selector_override=...)`
- On failure: `project_brain/runway_phase_i_last_failure_diagnostics.json` includes clip number, URL, dialogs, prompt candidates, control visibility, last 10 action log entries, screenshot path when captured

## Report fields (live smoke)

| Field | Meaning |
|-------|---------|
| `clip_2_prompt_ready_checked` | Clip 2 video prompt step completed readiness path |
| `clip_2_prompt_ready_result` | `ready` / `not_ready` / `unknown` |
| `clip_3_prompt_ready_checked` | Same for clip 3 |
| `clip_3_prompt_ready_result` | Same for clip 3 |

## Validation

```bash
python project_brain/validate_phase_i_clip2_workspace_transition_fix.py
python project_brain/validate_runway_phase_i_3clip_live_continuity.py
python project_brain/validate_phase_i5_download_and_progression.py
```

| Validator | Result |
|-----------|--------|
| `validate_phase_i_clip2_workspace_transition_fix.py` | All checks PASS |
| `validate_runway_phase_i_3clip_live_continuity.py` | All structural checks PASS (35 checks; step IDs shifted by +4 settle steps) |
| `validate_phase_i5_download_and_progression.py` | 32/32 PASS |

## Operator re-run (live)

1. **Execution Center → Runway Live Smoke → 3-Clip Continuity (Phase I) → Start 3-Clip Live (CDP)** (not UAT Runtime).
2. After run, attach:
   - `project_brain/runway_phase_i_3clip_last_report.json`
   - `project_brain/runway_phase_i_last_failure_diagnostics.json` (if any failure)
   - Failure screenshots under the smoke artifact dir if present.

Expected improvement: after clip 1 download and Use Frame for clip 2, settle + readiness should complete before `video_prompt_clip_2` fill.
