# Phase I — Strict Completion Gate + Approval UI Safety

**Date:** 2026-06-04  
**Status:** Implemented and validated (structural + simulate)

## Problem

Clip 1 could still be generating (~6%) while the runtime exposed `018_download_mp4_clip_1`. Root cause: `wait_for_completion_signal()` treated any global `download_mp4_button` visibility as completion.

## Part 1 — Strict generation completion

**Module:** `content_brain/execution/runway_phase_i_strict_completion_gate.py`

A clip is complete only when:

- Generation not in progress (no spinner, stop/cancel, progress &lt; 100%, no loading output)
- A new **video** artifact card exists (excludes starter + prior clip fingerprints)
- Playable `video` element in that card
- **Download** control inside that card (global download buttons ignored)

**Navigator:** `wait_for_strict_clip_completion()` replaces loose polling; `wait_for_completion_signal()` delegates to it.

**Semi-auto:** completion wait uses strict poll; download step re-checks strict completion before executing.

**Removed:** logic that cleared `in_progress` when a global download button was visible.

## Part 2 — Approval UI safety

**Runtime:** `runway_live_smoke_approval_runtime.py` (v2 gate safety)

Snapshot fields:

- `gate_ready`, `gate_enabled`, `gate_reason`, `expected_step_id`
- `early_approval_rejections_count`, `approval_gate_safety_enabled`

**Runner:** polls strict completion before opening download approval; sets gate readiness on runtime.

**UI:** `RunwayLiveSmokeApprovalPanel.tsx` — Approve disabled unless `waiting && gate_enabled`.

**Early approve:** `submit_approve()` rejects when `gate_enabled=false`, logs `rejected_early_approval`.

## Diagnostics

`project_brain/runway_phase_i_completion_gate_diagnostics.json` — progress, spinner, cards, download candidates, screenshot path, last 20 actions.

## Report fields (`runway_phase_i_3clip_last_report.json`)

- `clip_N_completion_verified`, `clip_N_completion_reason`
- `clip_N_download_gate_released_after_completion`
- `early_approval_rejections_count`, `approval_gate_safety_enabled`

## Validation

```bash
python project_brain/validate_phase_i_strict_completion_gate.py
python project_brain/validate_phase_i_artifact_tracking_and_cdp_download.py
python project_brain/validate_phase_i_use_frame_handoff_verification.py
python project_brain/validate_phase_i_false_fail_while_generating.py
python project_brain/validate_runway_phase_i_3clip_live_continuity.py
```

**Unchanged:** StoryBrief, Prompt Builder content, Provider Router, **7** approval gates, duration chip work deferred.

## Operator note

Download Approve stays disabled until strict completion passes. If generation is still running, gate reason explains why (e.g. `progress_not_complete`, `generation_in_progress`).
