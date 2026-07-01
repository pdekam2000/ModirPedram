# KLING SINGLE CLIP MP4 RECOVERY WAIT REPORT

Generated: 2026-06-21

## Problem

Run `kling_sc_20260621T064818_2926d3e3` generated successfully but final MP4 was missing:

- Focus probe OK (`visibility=visible`, `hasFocus=True`) — not a stuck-click issue
- Error: `Could not download real MP4`
- Artifact card / timing: MP4 not yet on card when first extract ran

## Solution

Extended `kling_real_mp4_download_extractor_v2` with **MP4 recovery polling** and **scoped artifact card selection**.

### 1. Recovery polling (no immediate fail)

After generation completes, download/recovery uses `poll_extract_real_kling_mp4()`:

| Parameter | Value |
|-----------|-------|
| Poll interval | 10 seconds |
| Max wait | 5 minutes |
| Early stop | Valid MP4 found |
| Generate clicks | **None** — recovery never clicks Generate |

Each poll cycle re-runs all extractor methods:

1. `artifact_card_cdp_urls` (scoped card)
2. `scoped_card_browser_download`
3. `page_video_sources`
4. `global_ui_download`

### 2. Scoped newest artifact card

`resolve_scoped_video_card_for_extraction()` for each attempt:

- Captures total artifact card count
- Filters placeholder / empty-state cards (`studio-empty-state`, `empty-state`, etc.)
- Requires visible video preview (`blob:` / real URL, not placeholder)
- Prefers **newest** card (`cardBottom` + `selected` bonus)
- Falls back to tracker assign only if no eligible card

### 3. Poll reporting

Written to:

`outputs/kling_frame_to_video/<run_id>/clips/c1/mp4_recovery_poll_report.json`

Each attempt logs:

- attempt number
- timestamp
- card count / video card count
- selected card info
- methods tried
- rejected files (quarantined)
- valid MP4 found yes/no

Single-clip report (`KLING_SINGLE_CLIP_15S_REPORT.md`) includes poll summary when recovery runs.

### 4. Success criteria (unchanged)

Real MP4 must pass:

- size > 1 MB
- ffprobe OK
- duration >= 5 s
- MP4 container (`ftyp`)

### 5. Wired paths

| Component | Change |
|-----------|--------|
| `kling_multishot_live_engine._download_output` | Uses `poll_extract_real_kling_mp4` |
| `kling_frame_to_video_live_engine` step 13 | Fails only after polling exhausted |
| `recover_kling_frame_output` | Polls instead of single-shot; no hard fail on `output_detect` |
| `run_kling_single_clip_15s._resolve_mp4` | Reads poll report into recovery audit |

## Validation

```bash
python project_brain/validate_kling_single_clip_mp4_recovery_wait.py
```

Checks:

- Poll waits/retries instead of immediate fail
- No Generate click during recovery
- Placeholder cards rejected
- Newest artifact card preferred
- Valid MP4 accepted
- Poll report includes attempts

## Files changed

- `content_brain/execution/kling_real_mp4_download_extractor.py` — v2 polling + card selection
- `content_brain/execution/kling_multishot_live_engine.py` — poll on download
- `content_brain/execution/kling_frame_to_video_live_engine.py` — recovery poll + messaging
- `project_brain/run_kling_single_clip_15s.py` — poll report in output
- `project_brain/validate_kling_single_clip_mp4_recovery_wait.py` — new
- `project_brain/validate_kling_real_mp4_download_extractor.py` — v2 version check

## Recovering failed run

If Chrome CDP still has the session for `kling_sc_20260621T064818_2926d3e3`:

```bash
python -c "from content_brain.execution.kling_frame_to_video_live_engine import recover_kling_frame_output; r=recover_kling_frame_output(run_id='kling_sc_20260621T064818_2926d3e3'); print(r.status, r.clip_output_path)"
```

Or re-run single clip runner (will generate new credits unless using recovery-only path).
