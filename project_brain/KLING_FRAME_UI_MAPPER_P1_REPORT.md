# Kling Frame-to-Video UI Mapper P1 Closeout Report

**Phase:** `KLING-FRAME-TO-VIDEO-UI-MAPPER-P1-CLOSEOUT`  
**Date:** 2026-06-17  
**Status:** Static map + locator stack **PASS** · Live CDP dry-run **PASS** (Frames panel session) · Screenshot package **partial** (re-run with Frames tab visible for `duration_after_15s`)

---

## Summary

Frame-to-Video UI mapping is finalized for automation. Duration is confirmed as a **slider** (not a dropdown). All 11 required labels are in `runway_ui_map.json` with role/class locator strategies. Dry-run shadow runner resolves controls from live CDP, moves the slider to max (15s), and never clicks Generate.

| Gate | Result |
|------|--------|
| All required labels in map | PASS |
| Slider labels (`duration_slider_*`, `duration_display_value`) | PASS |
| Role/text locators resolve from CDP | PASS (Frames session) |
| Slider read + move to 15s | PASS |
| Generate not clicked | PASS |
| Credits spent | PASS (none) |
| Static validation script | PASS |
| Screenshot package (5 files) | PARTIAL — see below |

---

## Required Controls (11 labels)

| Label | Map | CDP locator strategy | Notes |
|-------|-----|----------------------|-------|
| `kling_frame_to_video_mode` | ✓ | `text_frames_exact` | Operator + role fallback |
| `frame_prompt_box` | ✓ | `contenteditable_first` | |
| `first_frame_upload` | ✓ | `role_button_upload_first` | |
| `end_frame_upload` | ✓ | `role_button_upload_nth1` | |
| `duration_slider_handle` | ✓ | `role_slider` | Opens after Duration button |
| `duration_slider_track` | ✓ | `slider_root_class` | `[class*="Slider__Root"]` |
| `duration_display_value` | ✓ | `role_button_duration` | `button[aria-label="Duration"]` |
| `audio_toggle_on` | ✓ | `role_button_audio_settings` | |
| `generate_button` | ✓ | `role_button_generate` | Visible only — approval gated |
| `download_button` | ✓ | `aria_download` | Alias of `download_mp4_button` |
| `use_frame_button` | ✓ | `text_use_frame` | Optional until output exists |

---

## Duration Slider Validation (dry-run)

Confirmed on live CDP with Frames mode selected:

1. Open Duration panel (`button[aria-label="Duration"]` or `getByRole('button', { name: 'Duration' })`)
2. Read current value from Duration button text (e.g. `15s`)
3. Click track left → **3s**
4. Click track right → **15s**
5. **Generate never clicked**

Target max: **15 seconds** (`KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS`).

---

## Deliverables

| Artifact | Path |
|----------|------|
| UI map (slider + download alias) | `project_brain/runway_ui_mapping/runway_ui_map.json` |
| Config / required labels | `content_brain/execution/kling_frame_to_video_config.py` |
| Map loader | `content_brain/execution/kling_frame_to_video_map_loader.py` |
| Playwright locators | `content_brain/execution/kling_frame_to_video_locator.py` |
| Shadow dry-run runner | `tools/kling_frame_to_video_shadow_runner.py` |
| Validation | `project_brain/validate_kling_frame_ui_mapper_p1.py` |
| Shadow summary (latest) | `project_brain/kling_frame_to_video_shadow_summary.json` |
| Screenshots | `project_brain/runway_ui_mapping/screenshots/kling_frame_to_video_p1/` |

---

## Screenshot Package

Canonical names (no timestamp):

| File | Status |
|------|--------|
| `frame_mode_selected.png` | Captured (CDP) — re-capture when Frames tab visible for full panel |
| `duration_before.png` | ✓ (469 KB, live session) |
| `duration_after_15s.png` | **Pending** — run shadow runner with Frames tab open |
| `audio_on.png` | ✓ (410 KB, live session) |
| `generate_visible.png` | Captured (CDP) — re-capture when Generate bar visible |

**Re-run screenshots:**

```powershell
# Prerequisite: Chrome CDP on 127.0.0.1:9222, Runway Video Tools → Kling 3.0 Pro → Frames tab
.\venv\Scripts\python.exe tools\kling_frame_to_video_shadow_runner.py
```

---

## Validation Commands

```powershell
# Static (map, safety, dry-run guards) — always PASS
.\venv\Scripts\python.exe project_brain\validate_kling_frame_ui_mapper_p1.py

# Live CDP + slider + screenshots (requires Frames panel visible)
.\venv\Scripts\python.exe project_brain\validate_kling_frame_ui_mapper_p1.py --live
```

Static validation output: **All Kling Frame-to-Video UI mapper P1 checks passed.**

Live CDP session (2026-06-17, Frames mode): all locators resolved, slider max **15s**, `generate_clicked: false`, `credits_spent: false`.

---

## Safety

- `generate_button` in `safety.requires_approval`
- `generate_never_auto_clicked: true`
- `BLOCKED_KLING_FRAME_CLICK_LABELS` includes `generate_button`
- Shadow runner supports only `dry_run=True`

---

## Architecture Notes

- Weak operator CSS (`label`, `span`, `body`) tolerated when `operator_confirmed` — **role/text locators are primary**
- Slider controls require Duration panel open before resolve
- `download_button` canonical alias points at existing download map entries
- Multishot path unchanged (fallback)

---

## Next Phase

**P2** planner exists. Next execution work: **P3 Preflight API**, **P4 Live dry-run engine**, **P5 Approval-gated generation**, **P6 Frame continuity chain**.

Frame-to-Video UI map is **automation-ready** for P3–P4 wiring once operator re-runs `--live` with Frames tab visible to complete the screenshot set.
