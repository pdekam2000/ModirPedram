# PHASE QUALITY-FIX-3 — Real Visibility & Audibility Report

**Run:** `cb_e2e_20260611_225308_dc20bc1f`  
**Run folder:** `outputs/runs/20260611_235927_308_dc20bc1f/`  
**Date:** 2026-06-12

## Root cause

1. **Subtitles invisible (v2):** Burn used `force_style` with `FontSize=14` on 720×1280 video, and ASS inline tags used invalid `\c` overrides (libass skipped dialogue). Windows absolute paths in the `subtitles=` filter also broke path parsing, so burns could complete with no visible text. Full-frame PSNR ≈ 45.5 dB confirmed negligible change.

2. **Music inaudible (v2):** `project_brain/music/default_background.mp3` was an ~8 KB silent placeholder (`mean_volume ≈ -91 dB`). Validators only checked file existence, ffmpeg exit, and output audio stream presence — not source loudness or human audibility.

3. **False PASS:** Validators did not inspect burned MP4 subtitle pixels or music source loudness before mix.

## Files changed

| Area | Files |
|------|-------|
| Subtitle burn/style | `content_brain/branding/subtitle_format_engine.py`, `content_brain/branding/subtitle_burn_engine.py`, `content_brain/branding/branding_ffmpeg.py`, `content_brain/audio/subtitle_timing_engine.py` |
| Music | `content_brain/audio/music_runtime.py`, `content_brain/audio/local_audio_assets.py` |
| Recovery / branding | `content_brain/execution/post_processing_recovery.py`, `content_brain/branding/branding_runtime.py`, `project_brain/recover_cartoon_run_quality.py` |
| Results / assets | `content_brain/platform/results_run_loader.py`, `content_brain/platform/asset_library.py`, `content_brain/execution/runway_live_post_processor.py`, `content_brain/audio/audio_post_processing.py`, `ui/web/src/pages/ResultsPage.tsx`, `ui/web/src/api/productClient.ts` |
| Validators | `project_brain/validate_subtitle_real_visibility.py`, `project_brain/validate_music_real_audibility.py`, updates to `validate_subtitle_color_style_v1.py`, `validate_music_audibility_v1.py` |

## Subtitle font size

| | Value |
|--|-------|
| **Old burn font size** | 14 px (`force_style` + ASS style) |
| **New burn font size** | 58 px (`round(1280 × 0.045)`, min 44) |
| **MarginV** | 155–179 (lower-third band) |
| **Highlight tags** | Fixed to ASS `\1c&H…&` (orange / yellow / cyan preserved) |
| **Burn path fix** | Stage ASS beside input video; relative `subtitles=burn_subtitles.ass` with ffmpeg `cwd` |

## Music loudness

| | Value |
|--|-------|
| **Old source** | `project_brain/music/default_background.mp3` — ~8,261 bytes, **-91 dB** |
| **New source** | `assets/audio/music/whimsical_adventure.mp3` — 120,401 bytes, 30 s procedural bed, **-27.1 dB** |
| **Mix settings** | volume 0.30, ducking 0.18, source must be > -45 dB or mix is skipped/failed |
| **Mixed output (v3)** | input ENV **-35.4 dB** → output **-40.4 dB**, audibility PASS |

## Real MP4 validation results (v3)

| Check | Result |
|-------|--------|
| Subtitle lower-third PSNR (pre-burn vs subtitled @ 1s) | **39.14 dB** (≤ 42 → visible) |
| Subtitle burn engine PSNR | **41.15 dB**, `burn_visible_enough: true` |
| Music source loudness | **-27.1 dB** (> -45 dB) |
| Music audibility | **PASS — audible music mixed** |
| Subtitle status | **PASS — visible lower-third subtitles burned** |

## Outputs

| Asset | Path |
|-------|------|
| **v3 branded video** | `outputs/runs/20260611_235927_308_dc20bc1f/publish/FINAL_BRANDED_VIDEO_v3.mp4` |
| **v2 preserved** | `outputs/runs/20260611_235927_308_dc20bc1f/publish/FINAL_BRANDED_VIDEO_v2.mp4` |
| **v1 preserved** | `outputs/runs/20260611_235927_308_dc20bc1f/publish/FINAL_BRANDED_VIDEO.mp4` |
| **Asset vault** | `assets/videos/cartoon/20260612_171056_cute_orange_cartoon_cat_explorer.mp4` |
| **Asset index** | `assets/asset_index.json` (checksum `f25e29c3…`) |

## Validator commands (all PASS after fix)

```bash
python project_brain/validate_subtitle_real_visibility.py
python project_brain/validate_music_real_audibility.py
python project_brain/validate_subtitle_color_style_v1.py
python project_brain/validate_music_audibility_v1.py
python project_brain/validate_quality_fix_2_recovery_v1.py
```

## Runway automation

**Confirmed untouched:** Runway automation, selectors, browser automation, provider router, Visual Memory, AI Director, Upload, Automation — no changes in this phase.

## Honest Results status (v3)

- **Subtitle:** PASS — visible lower-third subtitles burned  
- **Music:** PASS — audible music mixed  
- **Ambience:** PASS — 3 layer(s)  
- **SFX:** PASS — 4 cue(s)
