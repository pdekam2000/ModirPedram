# PHASE CINEMATIC-1 — Story Quality + Seamless Continuity + Music Foundation

**Status:** Complete  
**Date:** 2026-06-03  
**Scope:** Content Brain, Prompt Builder, Continuity Engine, Branding Runtime, Audio Layer only  
**Explicitly untouched:** Runway browser automation, Runway selectors, approval gates, provider router, upload system, Automation Center

---

## Summary

PHASE CINEMATIC-1 upgrades the content pipeline from short clip prompts to cinematic story-driven generation with cross-clip continuity, professional shorts subtitles, local background music, and improved channel branding CTAs. All 12 validation checks pass via `project_brain/validate_cinematic_runtime_v1.py`.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/cinematic_prompt_expander.py` | Expands each clip prompt to 2000–4000 chars with sections A–J (subject, environment, lighting, camera, motion, atmosphere, visual detail, continuity, style, negative) |
| `content_brain/execution/seamless_continuity_engine.py` | Per-clip `ContinuityState`, `CONTINUE FROM PREVIOUS CLIP` chaining, seamless prompt injection |
| `content_brain/audio/music_runtime.py` | Local MP3 background music merge with volume ducking, fade in/out (Phase 1 — no Suno) |
| `content_brain/audio/subtitle_format_engine.py` | Shorts-style 2–4 words/line, platform safe margins, keyword highlight |
| `project_brain/validate_cinematic_runtime_v1.py` | 12-test cinematic runtime validator |

---

## Files Modified

| File | Changes |
|------|---------|
| `content_brain/execution/runway_story_brief_builder.py` | `runway_story_brief_v3`: extended `RunwayStoryBrief` with title, logline, subject, main_character, environment, conflict, stakes, emotional_arc, visual_hook, opening_hook, escalation, payoff, continuity_anchors, clip_beats, scene_progression |
| `content_brain/execution/runway_prompt_builder.py` | `runway_starter_to_video_f_v6`: wires seamless continuity → cinematic expansion after base clip build |
| `content_brain/branding/subtitle_burn_engine.py` | v2: smaller fonts, higher lower-third margins (140–160px), safe-zone aware burn |
| `content_brain/audio/subtitle_timing_engine.py` | Routes SRT generation through `format_srt_content()` with platform param |
| `content_brain/audio/audio_post_processing.py` | Passes platform to subtitles; invokes `run_music_runtime()` after narration merge |
| `content_brain/branding/cta_engine.py` | v2: `CTA_PRESETS`, `resolve_cta_text()` for Follow/Subscribe/Like & Follow/custom slogan |
| `content_brain/branding/branding_runtime.py` | Uses `resolve_cta_text()`; supports `cta_preset`, `cta_custom_slogan` |
| `content_brain/branding/intro_outro_engine.py` | Intro/outro text cards clamped to 1–2 seconds |
| `content_brain/product_settings/channel_profile_store.py` | Added `music_track_path`, `music_background_volume`, `music_fade_in/out_seconds`, `cta_preset`, `cta_custom_slogan` |

---

## Average Prompt Length

| Source | Average chars | Target |
|--------|---------------|--------|
| Standalone expander (3 clips) | **3827** | 2000–4000 |
| Full `RunwayPromptBuilder` integration (3 clips) | **3999** | 2000–4000 |

Each expanded prompt includes labeled blocks A–J plus a negative prompt section. The expander pads to `TARGET_MIN_CHARS` (2000) and caps at `TARGET_MAX_CHARS` (4000).

---

## Continuity Architecture

```
RunwayStoryBrief (conflict, stakes, anchors, clip_beats)
        │
        ▼
RunwayPromptBuilder — base clip prompts
        │
        ▼
seamless_continuity_engine.apply_seamless_continuity()
  • build_continuity_states() per clip
  • inject "CONTINUE FROM PREVIOUS CLIP" into clip N+1
  • maintain: subject, environment, lighting, camera, motion, composition
        │
        ▼
cinematic_prompt_expander.expand_clip_prompt()
  • continuity_block from prior state
  • 2000–4000 char cinematic sections
        │
        ▼
Runway clip generation (unchanged automation)
```

**ContinuityState fields:** `subject_state`, `environment_state`, `lighting_state`, `camera_state`, `motion_vector`, `scene_composition`, `emotional_state`

**Goal:** Clip1 → Clip2 → Clip3 reads as one continuous shot sequence, not separate videos.

---

## Subtitle Improvements

| Feature | Implementation |
|---------|----------------|
| Max words per line | 2–4 (`MAX_WORDS_PER_LINE = 4`) |
| Dynamic line breaking | `break_cue_into_short_lines()` with char limits per platform |
| Lower-third placement | `MarginV` 140–160 in burn engine + format engine safe margins |
| Platform modes | `tiktok`, `youtube_shorts`, `instagram_reels` |
| Keyword highlight | Highlight tags for follow/subscribe/secret/how/best/etc. |
| Safe zone | Horizontal margins 40–48px; max 18–20 chars/line per platform |
| Channel profile | Platform stored via channel profile / post-processing platform param |

Subtitles no longer dominate the frame — they sit in the lower third with short, punchy lines.

---

## Music Runtime Architecture

**Version:** `music_runtime_v1`  
**Phase 1 scope:** Local MP3/WAV/M4A only — no Suno integration.

```
Assembly
  → Narration (audio_post_processing)
  → Music (run_music_runtime)
  → Branding
  → Publish
```

**Capabilities:**

- `resolve_music_track_path()` — channel profile path, then `project_brain/music/default_background.mp3`, then storage/assets fallbacks
- `run_music_runtime()` — FFmpeg merge with narration + background bed
- Auto volume ducking under narration (`music_background_volume`, default 0.18)
- Fade in / fade out (configurable via channel profile)
- Graceful skip when provider disabled, track missing, or FFmpeg unavailable (`plan_only`)

**Channel profile keys:** `music_provider`, `music_track_path`, `music_background_volume`, `music_fade_in_seconds`, `music_fade_out_seconds`

---

## Branding CTA Improvements

| Preset | Text |
|--------|------|
| `follow_for_more` | Follow for more (optionally `@handle`) |
| `subscribe` | Subscribe |
| `like_and_follow` | Like & Follow |
| `custom` | User-defined `cta_custom_slogan` |

Intro/outro text cards: **1–2 seconds** duration — visible but non-blocking.

---

## Validation Results

Command: `python project_brain/validate_cinematic_runtime_v1.py`

| # | Test | Result |
|---|------|--------|
| 1 | Story brief contains conflict/stakes/payoff | PASS |
| 2 | Expanded prompts generated | PASS |
| 3 | Prompt length > 2000 chars (avg 3827) | PASS |
| 4 | Continuity state generated | PASS |
| 5 | Continuity passed to next clip (`CONTINUE FROM PREVIOUS CLIP`) | PASS |
| 6 | Subtitle line limits respected (≤4 words/line) | PASS |
| 7 | Subtitle safe zone respected (margin_v ≥ 140) | PASS |
| 8 | Music runtime loads local MP3 | PASS |
| 9 | Music fade in/out configured | PASS |
| 10 | Branding CTA still works | PASS |
| 11 | Runway automation unchanged | PASS |
| 12 | Provider router unchanged | PASS |

**Overall:** All cinematic runtime v1 validations passed.

---

## Integration Notes

1. **Prompt pipeline order:** base prompts → seamless continuity → cinematic expansion → (optional) prompt critic
2. **Music runs inside** `run_audio_post_processing()` after narration merge — no changes to Runway post-processor entry points beyond existing audio hook
3. **Channel profile** must set `music_provider: "local"` and `music_track_path` for music to merge; otherwise runtime skips cleanly
4. **Subtitle platform** flows from post-processing context into `format_srt_content()`

---

## Next Recommended Phase

### PHASE CINEMATIC-2 — Visual Memory + Scene Recall + Character Consistency Engine

Recommended focus:

- Persistent visual memory across runs (character face, wardrobe, palette embeddings)
- Scene recall from prior clips for stronger subject lock
- Character consistency scoring before clip approval
- Optional reference-frame injection into prompt continuity blocks
- Suno / licensed music provider hook (when ready)
