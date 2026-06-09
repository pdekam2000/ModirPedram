# Phase I — Post Use Frame Composer Handoff Verification

**Date:** 2026-06-04  
**Status:** Implemented and validated (structural + simulate)

## Problem

Phase I only proved the **Use Frame click** succeeded. It did not prove:

- Frame/reference applied to the **next-clip composer**
- Prompt editor remounted and is usable
- Next clip is ready for prompt + generate

Live evidence showed card-only selection / generation-in-progress while the runtime advanced blindly.

## Solution

New step after each `use_frame_for_clip_N` + settle:

`verify_use_frame_handoff_clip_N` → `verify_use_frame_composer_handoff(clip_number)`

### Valid paths (non-fatal)

| Path | Result | Criteria |
|------|--------|----------|
| **A — Composer ready** | `composer_ready` | Prompt interactable; generate or reference thumbnail visible; no blocking modal |
| **B — Generation started** | `generation_already_started` | Spinner/progress/stop/cancel/disabled generate + output slot |

### Invalid path (retry then fail)

| Path | Result | Criteria |
|------|--------|----------|
| **Card-only** | `invalid_card_only` / `timeout` | Output card selected; no prompt; no reference; no generation |

### Retry budget (3)

1. Wait and re-check  
2. Safe focus on composer/prompt area  
3. Optional single Use Frame re-click (per clip, idempotent guard)

## Dry-run step order (clip ≥ 2)

```
use_frame_for_clip_N
settle_after_use_frame_clip_N
verify_use_frame_handoff_clip_N   ← NEW
video_prompt_clip_N
...
```

## Report fields

- `clip_2/3_use_frame_handoff_checked`
- `clip_2/3_use_frame_handoff_result`: `composer_ready` | `generation_already_started` | `invalid_card_only` | `timeout`
- `clip_2/3_reference_thumbnail_detected`
- `clip_2/3_prompt_interactable_after_use_frame`

## Diagnostics (fatal)

`project_brain/runway_phase_i_last_failure_diagnostics.json` adds:

- `output_card_candidates`, `reference_thumbnail_candidates`
- `use_frame_handoff_state`, `generate_button_state`
- `generation_state_candidates`
- Last **15** action log entries (handoff failures)

**Unchanged:** StoryBrief, Prompt Builder content, Provider Router, 7 approval gates, Download Tracker, image quality readback.

## Validation

```bash
python project_brain/validate_phase_i_use_frame_handoff_verification.py
python project_brain/validate_phase_i_false_fail_while_generating.py
python project_brain/validate_phase_i_clip2_workspace_transition_fix.py
python project_brain/validate_runway_phase_i_3clip_live_continuity.py
python project_brain/validate_phase_i5_download_and_progression.py
```

## Operator re-run

After Use Frame, report should show `clip_2_use_frame_handoff_result` before prompt fill. If `invalid_card_only` or `timeout`, check diagnostics JSON and handoff screenshot artifacts.
