# PHASE BRANDING-1 — Channel Identity & Visual Branding Runtime

## Architecture

Branding is a post-audio, pre-publish layer in the live post-processing pipeline:

```text
Runway → Assembly → Narration/Audio Merge → Branding Runtime → Publish Package
```

`content_brain/branding/branding_runtime.py` orchestrates:

1. Subtitle burn (`subtitle_burn_engine.py`)
2. Logo overlay (`logo_overlay_engine.py`)
3. CTA overlay (`cta_engine.py`)
4. Intro/outro cards (`intro_outro_engine.py`)
5. Final output: `FINAL_BRANDED_VIDEO.mp4`

Channel settings live in `project_brain/product_settings/channel_profile.json`. Logo PNG is stored at `project_brain/channel_assets/logo.png`.

## Files created

| File | Purpose |
|------|---------|
| `content_brain/branding/__init__.py` | Package exports |
| `content_brain/branding/branding_ffmpeg.py` | Shared FFmpeg helpers |
| `content_brain/branding/channel_assets_store.py` | Logo storage |
| `content_brain/branding/subtitle_burn_engine.py` | Burn SRT into video |
| `content_brain/branding/logo_overlay_engine.py` | PNG logo overlay |
| `content_brain/branding/cta_engine.py` | CTA suggestions + timed overlay |
| `content_brain/branding/intro_outro_engine.py` | Intro/outro cards + concat |
| `content_brain/branding/branding_runtime.py` | Pipeline orchestrator |
| `project_brain/validate_branding_runtime_v1.py` | Validator |

## Files updated

| File | Change |
|------|--------|
| `content_brain/product_settings/channel_profile_store.py` | Branding profile defaults |
| `content_brain/execution/runway_live_post_processor.py` | Branding hook + publish branded video |
| `ui/api/product_studio_service.py` | Profile fields, logo upload, Results branding status |
| `ui/api/schemas/product_studio.py` | DTOs for branding + logo |
| `ui/api/main.py` | Logo upload/status routes |
| `ui/web/src/api/productClient.ts` | Branding types + logo upload client |
| `ui/web/src/pages/SettingsPage.tsx` | Channel Branding settings UI |
| `ui/web/src/pages/ResultsPage.tsx` | Branding Status card |

## Branding flow

1. Load channel profile branding settings.
2. Choose source video: narrated video if present, else assembled video.
3. Optionally burn subtitles (TikTok / Instagram Reels / YouTube Shorts styles).
4. Optionally overlay channel logo (corner + scale).
5. Optionally overlay CTA text (beginning / middle / end timing).
6. Optionally prepend intro card and append outro card.
7. Write `FINAL_BRANDED_VIDEO.mp4` and manifest `project_brain/runtime_state/runway_phase_i_branding_manifest.json`.

## Settings additions

Profile fields:

- `branding_enabled`, `logo_enabled`, `logo_position`, `logo_scale`
- `subtitle_enabled`, `subtitle_style`, `subtitle_position`
- `cta_enabled`, `cta_text`, `cta_position`, `cta_frequency`
- `intro_enabled`, `intro_text`, `intro_duration`
- `outro_enabled`, `outro_text`, `outro_duration`

API:

- `GET /product/channel-assets/logo`
- `POST /product/channel-assets/logo` (PNG upload)

## Publish package additions

Publish folder now includes:

- `FINAL_BRANDED_VIDEO.mp4` (when branding runtime succeeds)

`metadata.json` includes:

- `branded_video_path`
- `branding_enabled`, `subtitle_enabled`, `logo_enabled`, `cta_enabled`, `intro_enabled`, `outro_enabled`
- `branding_status`, `branding_steps`

## Validation results

Run:

```bash
python project_brain/validate_branding_runtime_v1.py
python project_brain/validate_elevenlabs_runtime_v1.py
python project_brain/validate_visual_continuity_verifier.py
```

Branding validator covers:

1. Subtitle burn
2. Logo overlay
3. CTA overlay
4. Intro generation
5. Outro generation
6. Branding pipeline final video
7. Publish package branded video
8. Results branding status
9. Assembly pipeline unchanged
10. Audio pipeline unchanged
11. Runway automation unchanged

## Confirmation

Runway automation (`runway_ui_navigator.py`, smoke test selectors/prompt builder) was not modified. Director, Prompt Critic, Visual Continuity, and Provider Router were not touched. Branding runs only after assembly/audio in `runway_live_post_processor.py`.
