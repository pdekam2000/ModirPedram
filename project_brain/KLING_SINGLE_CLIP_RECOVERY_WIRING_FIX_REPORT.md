# KLING SINGLE CLIP RECOVERY WIRING FIX REPORT

Generated: 2026-06-21

## Problem

Single clip runner could report recovery as only:

```text
Recovery attempted: ['live_result.clip_output_path']
```

When the live engine path was missing or invalid, the runner returned early or skipped the full extractor/recovery pipeline — no `recover_kling_frame_output`, no extractor methods, no poll report.

## Fix

Rewired `_resolve_mp4()` in `project_brain/run_kling_single_clip_15s.py` to run a **full download-only recovery chain**:

| Step | Action | Logged as |
|------|--------|-----------|
| A | Check `live_result.clip_output_path`, `output_path`, `download_path` | `live_result.*` |
| B | Check canonical `outputs/kling_frame_to_video/<run_id>/clips/c1/clip_1.mp4` and `video.mp4` | `canonical_live_engine.clips/c1/*` |
| C | Call `recover_kling_frame_output()` (includes 5m poll + extractor) | `recover_kling_frame_output` |
| D/E | Direct `poll_extract_real_kling_mp4` fallback if recover did not run extractors | `poll_extract_real_kling_mp4_direct` |

Every step is **always logged** in `recovery_audit.json` and the markdown report — even when a prior step fails validation.

### Extractor methods tracked

Report now includes `extractor methods` from:

- `recover_kling_frame_output` → `download_strategies`
- `mp4_recovery_poll_report.json` → per-attempt `methods_tried`

Expected methods when recovery runs:

- `artifact_card_cdp_urls`
- `scoped_card_browser_download`
- `page_video_sources`
- `global_ui_download`

### Output copy

Valid MP4 is copied to:

`outputs/kling_single_clip/<run_id>/clip_1.mp4`

### No Generate during recovery

Recovery path is download-only — `recover_kling_frame_output` and `poll_extract_real_kling_mp4` never click Generate.

## Success criteria (unchanged)

- MP4 exists at single-clip output path
- Size > 1 MB
- ffprobe OK
- Duration >= 5 s

## Validation

```bash
python project_brain/validate_kling_single_clip_recovery_wiring_fix.py
```

## Files changed

- `project_brain/run_kling_single_clip_15s.py` — full recovery wiring + audit/report
- `project_brain/validate_kling_single_clip_recovery_wiring_fix.py` — new
