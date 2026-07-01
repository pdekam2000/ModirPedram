# Kling Frame Live Dry-Run P2 Report

**Phase:** `KLING-FRAME-LIVE-DRY-RUN-P2`  
**Version:** `kling_frame_live_dry_run_p2_v2`  
**Date:** 2026-06-17  
**Status:** **PASS** — duration popover dismiss + stability verified on live CDP

---

## Goal

Validate Frame-to-Video UI prepare on live CDP — **no Generate, no credits, no download**.

---

## P2 Checks (8)

| Check | Validates |
|-------|-----------|
| `frame_mode` | Frames tab selected |
| `prompt` | Prompt box visible |
| `first_frame_upload` | First frame upload visible |
| `duration_reaches_15s` | `duration_display_value` reads **15s** after slider drag |
| `duration_popover_closed` | Duration slider popover closed after outside click |
| `duration_stable_after_dismiss` | `duration_display_value` still **15s** after dismiss |
| `audio_on` | Audio toggle ON (runs only after duration sequence passes) |
| `generate_visible` | Generate visible only — never clicked |

Legacy aggregate in summary JSON: `duration_slider_15s` = all three duration sub-checks pass.

---

## Duration Sequence (v2 fix)

Operator reported: after dragging to 15s, the duration popover stays open; accidental contact can reset to 7s.

**Automation flow:**

1. Drag slider track to max
2. Read `duration_display_value` → confirm **15s**
3. Click safe neutral area (prompt box, then Frames label, then left-panel header)
4. Confirm popover closed (slider not visible)
5. Re-read `duration_display_value` → confirm still **15s**
6. **Only then** run Audio ON + Generate visible checks

---

## Safety

- `generate_clicked: false`
- `download_clicked: false`
- `credits_spent: false`
- No file upload, no Generate click

---

## Commands

```powershell
# Static validation
.\venv\Scripts\python.exe project_brain\validate_kling_frame_live_dry_run_p2.py

# Live CDP (requires Generate page + Frames mode)
.\venv\Scripts\python.exe tools\kling_frame_to_video_live_dry_run.py

# Live validation
.\venv\Scripts\python.exe project_brain\validate_kling_frame_live_dry_run_p2.py --live
```

**Prerequisite:** Chrome CDP `127.0.0.1:9222`, tab on `ai-tools/generate?mode=tools`, Frames mode.

---

## Summary JSON Fields

| Field | Meaning |
|-------|---------|
| `duration_before_dismiss` | Display text after slider drag |
| `duration_after_dismiss` | Display text after outside click |
| `popover_open_before_dismiss` | Slider visible before dismiss |
| `popover_open_after_dismiss` | Should be `false` |
| `duration_slider_15s` | Aggregate pass for all duration sub-checks |

Output: `project_brain/kling_frame_live_dry_run_p2_summary.json`

### Latest live run (2026-06-17)

| Field | Value |
|-------|-------|
| `ok` | `true` |
| `duration_before_dismiss` | `15s` |
| `duration_after_dismiss` | `15s` |
| `popover_open_before_dismiss` | `true` |
| `popover_open_after_dismiss` | `false` |
| `generate_clicked` | `false` |
| All 8 checks | PASS |

---

## Files

| Artifact | Path |
|----------|------|
| Config | `content_brain/execution/kling_frame_to_video_config.py` |
| Engine | `content_brain/execution/kling_frame_to_video_live_dry_run.py` |
| CLI | `tools/kling_frame_to_video_live_dry_run.py` |
| Validation | `project_brain/validate_kling_frame_live_dry_run_p2.py` |
