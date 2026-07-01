# PHASE QUALITY-FIX-1 — Cartoon Output Quality Recovery

**Status:** Complete  
**Date:** 2026-06-12  
**Run recovered:** `cb_e2e_20260611_225308_dc20bc1f`  
**Run folder:** `outputs/runs/20260611_235927_308_dc20bc1f/`

---

## Root Cause

| Layer | Execution said | Actual problem |
|-------|----------------|----------------|
| **Subtitles** | PASS | `BorderStyle=3` + semi-opaque `BackColour` produced giant centered black boxes; cues were long single blocks |
| **Narration** | completed | Script pulled platform hooks + Runway report/prompt leakage (`"In the next few seconds…"`, `"knowledgeable presenter"`, `"vertical framing"`) |
| **Music** | skipped silently | `music_provider: none` and no default local track; no explicit Results status |
| **CTA** | PASS | Large static drawtext (28px, 4s) with no fade/accent styling |
| **Validators** | PASS on execution | No quality checks for placement, source text, or music visibility |

**Runway automation, Visual Memory, AI Director, browser automation, and provider router were not modified.**

---

## Before / After

| Area | Before | After |
|------|--------|-------|
| Subtitles | Large opaque box, center-weighted | Lower-third outline style (14px), max 2 lines × 4 words, ASS keyword highlights |
| Narration | Technical/system voiceover | Story brief `scene_progression` + clip beats only; source guard blocks prompt/runtime terms |
| Music | `skipped_provider_disabled` (silent) | Local MP3 + ducking; Results shows **Music: PASS** or explicit skip reason |
| CTA | Plain white 28px text | Orange accent, soft box, ~2.8s with fade in/out |
| Final video | Same cat clips, bad overlay stack | Same clips, re-processed publish deliverable |

**Updated deliverable:**

`C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260611_235927_308_dc20bc1f\publish\FINAL_BRANDED_VIDEO.mp4`

**Sample narration script (after):**

> Introduce the cute orange cat and its explorer personality. Showcase the cat navigating through various animated terrains. Highlight a key discovery or adventure climax. Follow for more adventures.

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/branding/subtitle_format_engine.py` | **New** — Shorts line breaks, safe margins, ASS highlights, layout quality checks |
| `content_brain/audio/subtitle_format_engine.py` | Re-export shim |
| `content_brain/branding/subtitle_burn_engine.py` | v3 — outline style, lower third, ASS burn support |
| `content_brain/audio/subtitle_timing_engine.py` | Writes formatted SRT + ASS |
| `content_brain/audio/narration_script_builder.py` | v2 — story-only sources from `story_generation` e2e step |
| `content_brain/audio/narration_source_guard.py` | **New** — forbidden term guard |
| `content_brain/audio/narration_engine.py` | Guard integration |
| `content_brain/audio/music_runtime.py` | v2 — ducking, explicit status labels |
| `content_brain/audio/audio_post_processing.py` | Music status fields |
| `content_brain/branding/cta_engine.py` | v3 — fade, glow box, accent color |
| `content_brain/branding/branding_runtime.py` | Default `lower_third` subtitle position |
| `content_brain/product_settings/channel_profile_store.py` | `music_provider: local`, volume/ducking defaults |
| `content_brain/execution/post_processing_recovery.py` | **New** — in-place recovery (no Runway) |
| `content_brain/platform/results_run_loader.py` | Exposes `music_status` |
| `content_brain/execution/runway_live_post_processor.py` | Publish metadata music status |
| `ui/web/src/pages/ResultsPage.tsx` | Audio & Music panel |
| `ui/api/schemas/product_studio.py` | `music_status` field |
| `project_brain/music/default_background.mp3` | Default ambient track (generated) |
| `project_brain/recover_cartoon_run_quality.py` | **New** — recovery runner for cartoon run |

## Validators Added

| Script | Purpose |
|--------|---------|
| `validate_subtitle_visual_quality.py` | Lower-third rules, line/word limits, no opaque boxes |
| `validate_narration_source_guard.py` | Blocks prompt/runtime narration leakage |
| `validate_music_runtime_local.py` | Local track, ducking, explicit skip labels |
| `validate_final_video_quality.py` | Orchestrates quality checks + cartoon run deliverable |

---

## Validation Results

```bash
python project_brain/validate_subtitle_visual_quality.py
python project_brain/validate_narration_source_guard.py
python project_brain/validate_music_runtime_local.py
python project_brain/validate_final_video_quality.py
python project_brain/recover_cartoon_run_quality.py
```

| Check | Result |
|-------|--------|
| Subtitle visual quality | **PASS** |
| Narration source guard | **PASS** |
| Music runtime local | **PASS** |
| Final video quality | **PASS** |
| In-place recovery | **PASS** — audio `completed`, music `PASS`, branding `completed` |

Recovery summary:

- `audio_status`: completed  
- `music_status`: PASS  
- `branding_status`: completed  
- `publish_status`: PUBLISHED_PACKAGE_CREATED  
- `final_branded_video_path`: `...\publish\FINAL_BRANDED_VIDEO.mp4`

---

## Security / Scope Confirmation

- No Runway selectors, browser automation, Visual Memory, AI Director V2, Upload Center, or Automation Center code changed  
- No new Runway generation or credits spent — recovery reused existing 3 clips  
- Narration guard prevents settings/runtime/prompt terms in TTS source  
- Subtitle burn uses masked ASS/SRT paths only; no full secrets in UI

---

## How to Re-run Recovery

```bash
python project_brain/recover_cartoon_run_quality.py
```

Uses existing run folder, re-runs audio → music → branding → publish only.
