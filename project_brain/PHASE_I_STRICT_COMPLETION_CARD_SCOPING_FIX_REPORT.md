# Phase I Strict Completion Card Scoping Fix Report

**Date:** 2026-06-03  
**Scope:** Strict clip completion gate + artifact card detection only  
**Out of scope (unchanged):** Content Brain, prompt handoff, Use Frame, download logic

---

## Problem

Live Phase I run (`phase_i_live`, 2026-06-07) stopped at step `017_wait_until_completion_signal_clip_1` after 25 minutes:

- Error: `strict clip completion not detected within 25 minutes for clip 1 (last_reason=generation_in_progress)`
- Operator confirmed Clip 1 was visually complete in Runway
- Diagnostics showed `generation_in_progress=true`, `artifact_cards=[]`, empty assignment fingerprint
- Action log repeatedly assigned stale offscreen card: `488|-247|608|439|video|…an old man…quiet beach…` (negative document Y from prior session)

## Root Cause

1. **Global early return** — `evaluate_strict_clip_completion` returned `generation_in_progress` before running card-scoped DOM evaluation, so `artifact_cards` stayed empty while global UI noise blocked release.
2. **Notification banner false positive** — `progress_text` matched Runway’s “Get notifications when your generations are complete…” banner and was treated as active generation progress.
3. **Stale card assignment** — `_pick_latest_video_card_raw` selected highest `cardBottom` without rejecting negative-Y / prior-session cards.
4. **Incomplete card signals** — Strict eval lacked `looseMedia` fallback and in-card `Apps` menu detection used by Runway for scoped download.

## Fix Summary

### `content_brain/execution/runway_phase_i_strict_completion_gate.py`

| Change | Purpose |
|--------|---------|
| Card-first evaluation | Always run DOM eval; global generation state is diagnostic only |
| Notification banner filter | `progress_blocks_completion()` ignores notification CTA text |
| Stale rejection helpers | Reject negative Y, offscreen, stale topic markers, prompt mismatch |
| Bottom-most visible candidate | Prefer lowest visible complete video card |
| Card-scoped completion | Requires playable video, no card spinner/progress/loading, Download or Apps or Use Frame in card |
| Global override | Card complete releases gate even if `stop_cancel_visible` or global `generation_in_progress` |
| Assignment persistence | Refresh stale assignment and persist `latest_video_card` each poll |
| Enhanced diagnostics | `candidate_cards`, `rejected_cards`, `card_scoped_state`, `global_generation_state`, `persisted_assignment_fingerprint` |

### `content_brain/execution/runway_phase_i_artifact_tracker.py`

| Change | Purpose |
|--------|---------|
| `_fingerprint_document_top` / `_raw_card_is_stale` | Reject cards with negative document Y in fingerprint |
| `_pick_latest_video_card_raw` | Skip stale offscreen cards when picking latest video |
| `assign_latest_video_card_for_clip` | Drop and refresh stale clip assignment |

## Expected Flow After Fix

```
016 video_generate_manual_required_clip_1
017 wait_until_completion_signal_clip_1   ← card-scoped complete releases here
018 download_mp4_clip_1
019 settle_after_download_clip_1
020 use_frame_for_clip_2
```

## Validation

Run:

```bash
python project_brain/validate_phase_i_strict_completion_gate.py
python project_brain/validate_phase_i_strict_completion_card_scoping.py
```

New validator checks:

- Notification banner does not block completion
- Stale negative-Y / old-topic cards rejected
- Visible bottom-most complete card selected
- Card complete overrides global generation indicators
- `latest_video_card` assignment persists in simulate path
- Diagnostics include card-scoped vs global state

## Files Touched

- `content_brain/execution/runway_phase_i_strict_completion_gate.py` (primary fix)
- `content_brain/execution/runway_phase_i_artifact_tracker.py` (stale card rejection)
- `project_brain/validate_phase_i_strict_completion_card_scoping.py` (new)
- `project_brain/PHASE_I_STRICT_COMPLETION_CARD_SCOPING_FIX_REPORT.md` (this report)

## Not Modified

- Content Brain modules
- Prompt handoff (`content_brain_live_smoke_handoff.py`)
- Use Frame (`runway_phase_i_last_frame_use_frame.py`)
- Download logic (`runway_phase_i_cdp_download.py`)
