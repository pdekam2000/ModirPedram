# Phase I — False Fail While Generating Fix

**Date:** 2026-06-04  
**Status:** Implemented and validated (structural + simulate)

## Problem

Live run failed at `022_video_prompt_clip_2`:

```text
prompt editor not ready for clip 2: timeout_after_25.0s
```

Operator confirmed **Video Clip 2 was already generating** in Runway. The runtime treated prompt-editor timeout as fatal even though the UI had advanced to generation state (prompt hidden/disabled, spinner/progress active).

## Fix

### Generation-state detection (`runway_ui_navigator.py`)

New `detect_video_generation_in_progress()` probes:

- Spinner / `aria-busy` / loading classes
- Stop/cancel generation controls
- Progress text (generating, processing, %)
- Output cards / loading skeletons
- Generate button disabled with output slot present

### Prompt readiness reclassification (clip ≥ 2)

On timeout or during poll in `wait_for_prompt_editor_ready()`:

- If generation detected → `ready_result = skipped_because_generation_started` (non-fatal)
- Else → `ready_result = not_ready_fatal`

### Semi-auto (`runway_continuity_semi_auto.py`)

`video_prompt_clip_*`:

- **ready** → fill prompt as before
- **skipped_because_generation_started** → skip fill, continue plan → `wait_until_completion_signal` for that clip
- **not_ready_fatal** → raise only when no generation signals

### Report fields (`runway_live_smoke_test.py`)

| Field | Values |
|-------|--------|
| `clip_2_prompt_ready_result` | `ready`, `not_ready_fatal`, `skipped_because_generation_started` |
| `clip_3_prompt_ready_result` | same |
| `clip_2_generation_detected_after_prompt_timeout` | bool |
| `clip_3_generation_detected_after_prompt_timeout` | bool |

Fatal diagnostics include `generation_state_candidates` (spinner, stop/cancel, output cards, generate disabled, progress text).

**Unchanged:** StoryBrief, Prompt Builder, Provider Router, approval gates (7), Download Tracker, image quality readback, starter routing.

## Validation

```bash
python project_brain/validate_phase_i_false_fail_while_generating.py
python project_brain/validate_phase_i_clip2_workspace_transition_fix.py
python project_brain/validate_runway_phase_i_3clip_live_continuity.py
python project_brain/validate_phase_i5_download_and_progression.py
```

## Operator re-run

Re-run Phase I live. If clip 2 prompt step is skipped, report should show:

- `clip_2_prompt_ready_result`: `skipped_because_generation_started`
- `clip_2_generation_detected_after_prompt_timeout`: `true`

Run should continue to completion wait for clip 2 instead of stopping at prompt fill.
