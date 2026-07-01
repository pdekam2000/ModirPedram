# PHASE SUBTITLE-BRANDING-PUBLISH Report

**Phase:** `SUBTITLE-BRANDING-PUBLISH`  
**Date:** 2026-06-27  
**Goal:** Transform `publish/FINAL_PUBLISH_READY.mp4` into a branded, publish-ready package for downstream upload.

---

## Reused Legacy Components

| Component | Path | Role |
|-----------|------|------|
| Branding settings | `branding_runtime._branding_settings` | Channel profile → layer toggles |
| Subtitle burn | `branding/subtitle_burn_engine.burn_subtitles` | Optional burn-in |
| Logo overlay | `branding/logo_overlay_engine.apply_logo_overlay` | Logo / watermark corner overlay |
| CTA overlay | `branding/cta_engine.apply_cta_overlay` | CTA card + subscribe reminder text |
| Intro / outro | `branding/intro_outro_engine` | Optional intro/outro cards + merge |
| FFmpeg helpers | `branding/branding_ffmpeg` | Filter execution + loudnorm audio path |
| FFmpeg availability | `assembly_ffmpeg_availability.check_ffmpeg_availability` | Probe binary |
| MP4 validation | `pwmap_runway_agent_adapter.validate_mp4_path` | Output verification |
| Assembly output | `product_assembly_bridge.FINAL_PUBLISH_READY_NAME` | Required input (unchanged) |
| YT-1 metadata | existing `youtube_metadata.json` in publish folder | Read-only presence check |

**Not modified:** duration planner, pwmap generation, Use Frame, browser mappings, assembly bridge, YouTube metadata generator, upload runtime.

---

## Created Files

| File | Purpose |
|------|---------|
| `content_brain/execution/product_subtitle_branding_publish.py` | Subtitle, branding, audio, publish package orchestration |
| `project_brain/validate_subtitle_branding_publish.py` | Validation suite |
| `project_brain/PHASE_SUBTITLE_BRANDING_PUBLISH_REPORT.md` | This report |

---

## Modified Files

| File | Change |
|------|--------|
| `product_multiclip_orchestrator.py` | Invokes branding/publish runtime after successful assembly |
| `pwmap_finalization.py` | Exposes publish/branding fields in results payload |
| `product_studio_service.py` | Merges publish package state into Results API |
| `ResultsPage.tsx` | Publish ready, branded path, subtitle/branding/audio statuses |

---

## Pipeline Flow

```
publish/FINAL_PUBLISH_READY.mp4   (from assembly bridge)
        │
        ▼
Subtitle Runtime (optional)
  • none | generated | external | burn_in
  • writes publish/subtitles/generated.srt when generated
        │
        ▼
Branding Runtime (optional)
  • logo / watermark overlay
  • CTA card
  • intro / outro merge
        │
        ▼
Audio Runtime (optional)
  • loudnorm when normalization flags enabled
        │
        ▼
publish/FINAL_BRANDED_PUBLISH_READY.mp4
publish/branding_manifest.json
publish/publish_package.json
(existing youtube_metadata.json preserved)
```

---

## Publish Folder Layout

```
publish/
  FINAL_PUBLISH_READY.mp4           ← preserved original assembly output
  FINAL_BRANDED_PUBLISH_READY.mp4   ← branded deliverable
  assembly_manifest.json            ← from assembly bridge
  publish_metadata.json             ← from assembly bridge
  branding_manifest.json            ← NEW
  publish_package.json              ← NEW
  youtube_metadata.json             ← from YT-1
  subtitles/generated.srt           ← when generated mode used
  branding_staging/                 ← intermediate renders
```

---

## Failure Behavior

When any required branding step fails:

- `FINAL_PUBLISH_READY.mp4` is preserved (snapshot restored if touched)
- `branding_status = branding_failed`
- `publish_ready = false`
- `FINAL_BRANDED_PUBLISH_READY.mp4` is not left in a broken state (removed if partial)
- `branding_manifest.json` + `publish_package.json` still written with error detail

---

## Configuration (channel profile)

All layers optional via existing profile fields:

- `subtitle_enabled`, `subtitle_mode`, `subtitle_style`, `subtitle_position`
- `branding_enabled`, `logo_enabled`, `watermark_enabled`
- `cta_enabled`, `cta_text`, `intro_enabled`, `outro_enabled`
- `audio_normalization_enabled`, `loudness_normalization_enabled`, `target_lufs`

Overrides supported via `settings_overrides` in runtime call.

---

## Results UI

Product Multi-Clip Output panel shows:

- Publish ready yes/no
- Branded publish video path
- Subtitle status + cue count
- Branding status
- Logo / CTA / Intro / Outro status
- Audio normalization status (+ LUFS when applied)

---

## Validation Results

```powershell
python project_brain\validate_subtitle_branding_publish.py
```

| Test | Result |
|------|--------|
| Subtitles disabled | PASS |
| Subtitles enabled (generated) | PASS |
| Logo disabled / enabled | PASS |
| CTA enabled | PASS |
| Intro/outro enabled | PASS |
| `FINAL_BRANDED_PUBLISH_READY.mp4` created | PASS |
| `publish_package.json` created | PASS |
| Branding failure preserves source | PASS |
| Results API displays statuses | PASS |
| Assembly bridge + YT-1 untouched | PASS |

---

## Downstream Compatibility

`publish_package.json` marks downstream-ready paths for:

- Subtitle runtime (completed or skipped in this phase)
- Branding runtime (completed in this phase)
- YouTube metadata (existing file detected)
- YouTube upload (PHASE YT-2)
- TikTok / Instagram upload (future)

Primary upload input: `publish/FINAL_BRANDED_PUBLISH_READY.mp4`

---

## Next Phase: YT-2 — YouTube OAuth + Upload Runtime

- OAuth login
- Upload to channel
- Auto-apply title, description, tags, hashtags from `youtube_metadata.json`
- Thumbnail upload from `thumbnail_prompt` runtime
- Visibility + scheduling
- Store `youtube_video_id`
- Analytics collection
