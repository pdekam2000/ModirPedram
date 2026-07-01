# KLING DOWNLOAD GATE REPAIR REPORT

Generated: 2026-06-20

## Problem

Live run `kling_ft_20260619T211503_a5970bcb` proved clip 1 UI/generation succeeded (Kling 3.0 Pro, 9:16, 15s, audio ON, Generate once) but the 2-clip chain stopped because download/recovery returned **"Recovered file is not a real MP4"**. Clip 2 never started.

## Root cause

Two separate failures in `content_brain/execution/kling_frame_continuity_runtime.py` (v1):

1. **Download gate treated as generation gate** — chain stopped when `final_video` / local MP4 was missing, even though `generation_wait` passed and browser output was visible.
2. **`story_chapter` KeyError** — `_ensure_frame_mp4()` merged recovery payload without preserving `story_chapter`, breaking Use Frame handoff metadata.

Blocking code (v1 pattern):

```python
if not final_video:
    stop_reason = f"clip {clip_index} download/recovery failed"
    break
```

Clip 2 also required `prior_frame` file path; Use Frame without local MP4 had no path, triggering `prior_clip_frame_required`.

## Fix (v2)

**File:** `content_brain/execution/kling_frame_continuity_runtime.py` (`RUNTIME_VERSION = kling_frame_continuity_runtime_v2`)

### Separated states

| State | Meaning |
|-------|---------|
| `generation_success` | Step 12 / `generation_completed` passed |
| `download_success` | Real MP4 verified via `verify_recovered_mp4()` |
| `continuity_source_available` | `download_success` **OR** (`generation_success` + browser output ready) |

Chain stops on **generation failure** or **no continuity source** — not on download alone.

### Download failure handling

When clip 1 generates but download fails:

- `clip_generation_status = completed`
- `download_status = failed`
- `recovery_needed = true`
- `recovery_available = true` (after fake recovery quarantine)
- Fake/non-MP4 files moved to `clips/cN/quarantine/` — never registered as output
- Use Frame handoff proceeds with empty `video_path` when browser output is ready

### Clip 2 start condition

- Clip 2 may start when clip 1 `generation_success` + `continuity_source_available`
- After Use Frame handoff without local file: `continuity_frame_in_ui = True`
- **Minimal live-engine continuity flag** in `kling_frame_to_video_live_engine.py`: skips first-frame file upload when frame already in UI (does not change Generate/prompt/aspect/duration/audio steps)

```python
continuity_frame_in_ui: bool = False  # new kwarg
```

### MP4 validation

- `_quarantine_invalid_mp4()` deletes/quarantines invalid files
- `_ensure_frame_mp4()` merges recovery payload with `_merge_live_payload()` preserving `story_chapter` and steps
- Invalid recovery never sets `clip_output_path`

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/kling_frame_continuity_runtime.py` | v2 gate helpers, quarantine, chain loop, Use Frame continuity without MP4 |
| `content_brain/execution/kling_frame_to_video_live_engine.py` | `continuity_frame_in_ui` skip upload for clip 2+ after Use Frame |
| `project_brain/validate_kling_download_gate_repair.py` | Offline validation (no credits, no live browser for gate tests) |
| `project_brain/KLING_REAL_2CLIP_15S_LIVE_TEST_REPORT.md` | Forensic update with blocking file references |

## Validation

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS
python project_brain/validate_kling_download_gate_repair.py
```

Tests cover:

- generation success + download fail still allows chain planning
- fake MP4 quarantined, not accepted
- clip 2 blocked only when no browser continuity source
- download failure reported separately from generation failure
- no automatic re-Generate in recovery/ensure path
- no credit-spending in gate helpers
- mocked 2-clip chain reaches clip 2 with `continuity_frame_in_ui=True`

## Expected live behavior after repair

For runs like `kling_ft_20260619T211503_a5970bcb`:

1. Clip 1 Generate + generation wait — unchanged
2. Download may still fail with clear error + quarantine
3. Use Frame activates from visible browser output
4. Clip 2 Generate starts without local MP4
5. Final `download_report.status` may remain `failed` until real MP4 recovery succeeds

## Re-run live test

```powershell
python project_brain/run_kling_real_2clip_15s_live_test.py
```

Requires visible Chrome CDP `:9222`, Runway generate tab, API on port **8765**.
