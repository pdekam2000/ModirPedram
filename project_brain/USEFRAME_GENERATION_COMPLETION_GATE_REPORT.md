# USEFRAME GENERATION COMPLETION GATE REPORT

Generated: 2026-06-23T19:38:00+00:00

## Root cause

Live run `kling_uf_20260623T192725_d8a9e3f3` clicked Clip 2 Generate while Runway still showed *"Please wait for your last generation to complete"*. Recovery immediately downloaded Clip 1's artifact card again (identical SHA256).

## Fix summary

Added **generation completion gate** between Generate and recovery/download for Use Frame clip 2+ chains.

### New module

`content_brain/execution/kling_useframe_generation_completion_gate.py`

- `wait_for_generation_completion_gate()` — post-Generate wait until queue warning gone, generation inactive, and new non-duplicate artifact exists
- `recovery_blocked_by_gate()` — recovery lock while queue/generation active or new artifact unconfirmed
- `is_duplicate_artifact()` — reject same fingerprint, URL, or file hash as prior clip
- `find_new_artifact_candidate()` — select newest card that is not Clip 1
- `build_prior_artifact_signatures_from_clip()` — baseline from clip 1 extract report + video hash

### Wired into

| Component | Change |
|-----------|--------|
| `kling_frame_to_video_live_engine.py` | Capture baseline before Generate; gate wait after Generate for clip 2+; pass `gate_context` to download |
| `kling_real_mp4_download_extractor.py` | Recovery lock in poll/extract; duplicate rejection in `_accept_candidate`; scoped card resolver excludes prior artifacts |
| `kling_multishot_live_engine.py` | `_download_output()` accepts `gate_context` |
| `kling_frame_continuity_runtime.py` | Builds prior signatures from clip N-1; sets `require_new_artifact=True` for clip 2+ |

### Required flow (now enforced)

```
Clip1 Complete → Use Frame → Generate Clip2
  → WAIT (queue cleared, warning gone, generation inactive)
  → WAIT (new artifact card confirmed, not duplicate of Clip1)
  → Download Clip2
```

Recovery never runs while:

- generation still active
- queue warning visible
- new artifact not confirmed

## Validation

Script: `project_brain/validate_useframe_generation_completion_gate.py`

Result: **ALL PASS** (25 checks)

Covers:

- Clip 2 waits for generation completion gate (live engine wiring)
- Queue warning blocks recovery
- Old / duplicate artifact rejected
- Recovery starts only after new artifact exists
- Clip 1 artifact cannot be reused as clip 2 (scoped resolver + hash check)

## Live re-test

Run 2 (`kling_uf_20260623T194151_eed4c82a`): **SUCCESS**

- Gate waited **334.9s** for new artifact before download
- Clip 1 SHA256: `731d9261…`
- Clip 2 SHA256: `d0ada935…` (distinct)
- Merged 30.13s / 60,392,457 bytes
- Fix applied: `_write_outputs()` now writes to `clips/c{clip_index}/` (was always `c1/`)

Report: `project_brain/KLING_2CLIP_USEFRAME_LIVE_TEST_REPORT.md`
