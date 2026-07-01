# Audio Strategy Router — Design Report

**Phase:** AUDIO-STRATEGY-ROUTER-DESIGN  
**Status:** Design only — no implementation, no runtime changes  
**Date:** 2026-06-15  
**Canonical short name:** `AUDIO_STRATEGY_ROUTER_DESIGN.md` (same content)

---

## 1. Executive Summary

ModirAgentOS currently routes most runs through a **single heavy audio path** (story package → narration or cinematic pipeline → ambience → music → subtitles), regardless of whether the content needs character dialogue, environment simulation, or any speech at all.

This design introduces an **Audio Strategy Router**: a decision layer that runs **before video generation** and **before post-processing**, classifying each run into one of three audio strategies and selecting the minimum viable pipeline.

| Strategy ID | Class | Typical content |
|-------------|-------|-----------------|
| `music_only` | **A — Music Driven** | Motivational, luxury, aesthetic, travel, lifestyle, nature, visual reels |
| `narrator` | **B — Narrator Driven** | Mystery, horror, educational, storytelling, documentary |
| `cinematic` | **C — Cinematic Audio** | Multi-character, fantasy, dialogue-heavy, comedy skits, mini movies |

**Output artifact (future):** `audio_strategy` JSON on the run record, consumed by story generation, Runway phase planning, and `audio_post_processing`.

---

## 2. Problem Statement

### Current behavior

Today the system tends to:

1. Always build a full **story package** (dialogue plan, voice cast, environment plan, music plan, `dialogue_timeline`).
2. Attempt **cinematic multi-voice** when story audit passes and `run_dir` exists.
3. Fall back to **monolithic or timeline-aware narrator** synthesis.
4. Always run **environment mix + music + subtitles + branding**.

This works for narrative/fantasy content (e.g. dragon-egg E2E) but is **overkill** for music-first reels and **under-specified** when platform norms favor text-on-screen over VO.

### Cost and quality impact

| Issue | Effect |
|-------|--------|
| Unnecessary ElevenLabs calls | Credits spent on content that should be music-only |
| Full cinematic stack on simple reels | Longer post-processing, more failure surfaces |
| One-size-fits-all story package | Dialogue timelines generated even when no speech is planned |
| No pre-Runway signal | Video prompts not optimized for silent vs VO-driven pacing |

### Design goal

**Right-size audio before generation.** The router answers: *“What audio does this video actually need?”* and locks that decision early enough to influence prompts, providers, and post-processing branches.

---

## 3. Three Audio Classes

### CLASS A — Music Driven (`music_only`)

**Intent:** Visual and music carry the story; subtitles provide context. No VO required.

**Examples:** motivational, luxury, aesthetic, travel, lifestyle, nature, visual reels, product B-roll, timelapse, ASMR-adjacent visuals.

**Pipeline:**

```
Video (Runway)
  ↓
Music (local / licensed bed)
  ↓
Subtitle (optional text hooks / captions)
  ↓
Branding + Publish
```

**Explicitly skipped:**

- Narrator / ElevenLabs
- Character voices
- Environment simulation beyond optional light bed
- Cinematic audio mixer
- `dialogue_timeline` speech tracks

**Existing modules to reuse (future):**

- `runway_live_post_processor` → assembly
- `music_runtime.run_music_runtime`
- `branding_runtime` + subtitle burn (text from hook/caption, not narration script)
- `delivery_quality_gate` (duration, burn, music audibility)

---

### CLASS B — Narrator Driven (`narrator`)

**Intent:** Single warm narrator guides the viewer; music supports but does not dominate. No character dialogue simulation.

**Examples:** mystery, horror, educational, storytelling, documentary, explainer, “voiceover facts” shorts.

**Pipeline:**

```
Video (Runway)
  ↓
Timeline-aware Narrator (ElevenLabs, per-segment or monolithic)
  ↓
Light ambience (optional, low mix)
  ↓
Music (ducked under narration)
  ↓
Subtitle (aligned to narration timeline)
  ↓
Branding + Publish
```

**Explicitly skipped:**

- Multi-character `dialogue_to_speech_engine` per line
- Boy/companion character VO (unless user override)
- Full cinematic mixer (dialogue + env + music composite)

**Existing modules to reuse (future):**

- `timeline_aware_narration_engine` (preferred when `dialogue_timeline` narrator clips exist)
- `audio_merge_engine.merge_narration_into_video`
- `audio_mix_engine` (light ambience only)
- `music_runtime` with ducking
- `subtitle_timing_engine.generate_timeline_subtitles`

---

### CLASS C — Cinematic Audio (`cinematic`)

**Intent:** Multi-voice story world — characters speak, narrator may interleave, environment and music are directed.

**Examples:** multiple characters, animals, fantasy, dragon stories, dialogue-heavy scenes, comedy skits, mini movies.

**Pipeline:**

```
Video (Runway)
  ↓
Character Director (story package / performance plan)
  ↓
Voice Engine (ElevenLabs multi-voice, per dialogue line)
  ↓
Environment Audio (ambience + SFX timeline)
  ↓
Music (cinematic bed, ducked under dialogue)
  ↓
Subtitle (per-line or narrator cues from runtime timeline)
  ↓
Branding + Publish
```

**Existing modules to reuse (future):**

- `story_package` full build
- `run_cinematic_audio_pipeline`
- `cinematic_audio_mixer` + `cinematic_video_audio_builder`
- `delivery_reality_auditor`

**Note:** Dragon-egg E2E is **Class B or C** depending on scoring — current production used **Class B** (narrator timeline only) successfully; full Class C adds Boy dialogue lines at clip boundaries.

---

## 4. Decision Engine

### 4.1 Router placement

```
┌─────────────────────────────────────────────────────────────┐
│  PRE-GENERATION (before Runway)                             │
│  Topic + Channel Profile + Brief → AudioStrategyRouter      │
│  → audio_strategy.json on run                               │
│  → influences: clip beats, prompt pacing, story depth       │
└─────────────────────────────────────────────────────────────┘
                          ↓
                   Runway clip generation
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  POST-PROCESSING (after assembly)                           │
│  Read audio_strategy → branch audio_post_processing         │
│  → music_only | narrator | cinematic handlers               │
└─────────────────────────────────────────────────────────────┘
```

**Hard rule:** Strategy is decided **once** pre-generation. Post-processing may **downgrade** (e.g. cinematic → narrator on provider failure) but must **not upgrade** without explicit user/channel override.

### 4.2 Inputs

| Input | Source | Role in scoring |
|-------|--------|-----------------|
| `topic` | Content brain / user | Keyword genre detection |
| `niche` | `channel_profile.main_niche`, `sub_niche` | Baseline strategy bias |
| `platform` | `default_platform`, upload target | Platform table modifier |
| `style` | `tone_style`, `visual_style`, `narration_style` | Cinematic vs minimal |
| `character_count` | Story brief / character director | ≥2 pushes cinematic |
| `dialogue_count` | Dialogue plan lines (planned or estimated) | ≥3 pushes cinematic |
| `story_type` | Genre tags: educational, fantasy, aesthetic, etc. | Primary classifier |
| `target_duration` | `default_duration_seconds`, clip_count × clip_len | Short reels favor music_only |

### 4.3 Scoring model

Each strategy receives a **weighted score** 0–100. Highest score wins unless a **hard override** applies.

#### Feature weights (default)

| Feature | music_only | narrator | cinematic |
|---------|------------|----------|-----------|
| Topic keywords (aesthetic, travel, luxury, nature, motivational) | +30 | +5 | +0 |
| Topic keywords (mystery, horror, educational, documentary, explain) | +0 | +35 | +10 |
| Topic keywords (fantasy, dragon, dialogue, comedy skit, characters talk) | +0 | +15 | +40 |
| `character_count` ≥ 2 | −20 | +5 | +25 |
| `dialogue_count` ≥ 3 | −25 | +10 | +30 |
| `character_voice_mode` = multi_voice (profile) | −15 | +0 | +20 |
| Platform = Instagram Reels (visual niche) | +15 | +5 | −5 |
| Platform = TikTok (story/educational) | +5 | +20 | +10 |
| Platform = YouTube Shorts (explainer) | +0 | +25 | +15 |
| Duration ≤ 15 s | +20 | +5 | −10 |
| Duration ≥ 30 s with story beats | −10 | +15 | +20 |
| User `cta_only` / no speech flag (future) | +40 | −20 | −30 |

#### Hard overrides (priority order)

1. **User/channel explicit** `audio_strategy_override`: `music_only` | `narrator` | `cinematic` — wins unconditionally.
2. **`narration_provider` = disabled** → force `music_only`.
3. **`character_count` ≥ 3 AND `dialogue_count` ≥ 5** → minimum `cinematic` (cannot score to music_only).
4. **`story_type` in {aesthetic_reel, product_showcase, timelapse}** → maximum `narrator` (cannot score to cinematic without override).
5. **Confidence gap < 8 points** between top two → default **`narrator`** (safe middle path).

#### Output schema (future)

```json
{
  "version": "audio_strategy_router_v1",
  "audio_strategy": "narrator",
  "confidence": 0.82,
  "scores": {
    "music_only": 22,
    "narrator": 78,
    "cinematic": 41
  },
  "reasons": [
    "topic:educational_storytelling",
    "character_count:2",
    "platform:youtube_shorts",
    "dialogue_timeline:narrator_only"
  ],
  "pipeline_id": "class_b_narrator_timeline",
  "provider_bundle_id": "runway_elevenlabs_music_local",
  "decided_at": "ISO-8601",
  "override_applied": false
}
```

---

## 5. Strategy Matrix

| Dimension | music_only (A) | narrator (B) | cinematic (C) |
|-----------|----------------|--------------|---------------|
| **Speech** | None | Single narrator | Multi-voice + optional narrator |
| **Story package depth** | Minimal (hook, captions) | Blueprint + narrator timeline | Full package + performance plan |
| **ElevenLabs usage** | None | 1 voice, N segments | N voices, M lines |
| **Ambience / SFX** | Skip or music-only | Light optional | Full environment timeline |
| **Music** | Primary | Background, ducked | Cinematic bed |
| **Subtitles** | Hook / on-screen text | Narration-aligned | Dialogue or narrator cues |
| **Post-processing time** | Low | Medium | High |
| **Failure modes** | Music inaudible | Coverage / timing | Multi-voice sync, mix complexity |
| **Best for** | Visual-first reels | Explainers, story VO | Character-driven fiction |

### Content type → default strategy

| Content type | Default | Platform tweak |
|--------------|---------|----------------|
| Motivational quote reel | music_only | TikTok: music_only; YT Shorts: narrator optional |
| Luxury / fashion aesthetic | music_only | Instagram: music_only |
| Travel montage | music_only | All platforms: music_only |
| Nature / timelapse | music_only | YouTube: music_only |
| Skincare / how-to (visual steps) | music_only or narrator | TikTok: music_only + text; YT: narrator |
| Educational explainer | narrator | All: narrator |
| Mystery / horror story | narrator | TikTok: narrator (pacing); IG: narrator |
| Documentary fact | narrator | YouTube Shorts: narrator |
| Fantasy / dragon / animals talking | cinematic or narrator | Short 4-clip: narrator; 30s+ multi-char: cinematic |
| Comedy skit (2+ speakers) | cinematic | TikTok: cinematic |
| Mini movie | cinematic | YouTube Shorts: cinematic |

---

## 6. Routing Rules

### Rule set (deterministic layer after scoring)

| ID | Condition | Route |
|----|-----------|-------|
| R1 | `scores.music_only` ≥ 60 AND no override blocking | `music_only` |
| R2 | `scores.cinematic` ≥ 65 AND `character_count` ≥ 2 AND `dialogue_count` ≥ 2 | `cinematic` |
| R3 | `scores.narrator` ≥ 50 | `narrator` |
| R4 | Tie between music_only and narrator, duration ≤ 20 s, visual_style contains “aesthetic” | `music_only` |
| R5 | Tie between narrator and cinematic, `character_voice_mode` = narrator_only | `narrator` |
| R6 | Default fallback | `narrator` |

### Pre-generation consequences

| Strategy | Story generation | Runway prompts | Clip beat plan |
|----------|------------------|----------------|----------------|
| music_only | Hook + caption lines only; **no** dialogue plan | Visual pacing, no “speaking character” | Visual beats, no VO slots |
| narrator | Blueprint + **narrator-only** `dialogue_timeline` | Scene clarity for VO sync | 1 narrator line per clip |
| cinematic | Full dialogue + cast + env + music plans | Character blocking, reaction beats | Dialogue + narrator offsets |

### Post-processing branch map (future)

| Strategy | Handler | Skip list |
|----------|---------|-----------|
| music_only | `handle_music_only_post()` | narration_engine, cinematic_runtime, env_mix (heavy), dialogue_speech |
| narrator | `handle_narrator_post()` | cinematic_runtime, multi_voice_casting |
| cinematic | `handle_cinematic_post()` | monolithic narration concat |

**Integration point (existing):** `content_brain/audio/audio_post_processing.py` — add strategy dispatch at top; preserve current paths as `narrator` / `cinematic` implementations.

---

## 7. Platform Optimization

Platform modifiers adjust scores; they do **not** override hard safety rules.

### Instagram Reels

| Content | Recommended strategy | Rationale |
|---------|---------------------|-----------|
| Aesthetic / lifestyle / travel | **music_only** | Visual-first; text overlays common |
| Product / luxury | **music_only** | Brand feel; minimal VO |
| Story / educational | **narrator** | VO acceptable when hook is strong in first 1 s |
| Character comedy | **cinematic** | Rare; only when dialogue is the hook |

**Defaults:** bias +15 toward `music_only` for `visual_style` ∈ {aesthetic, cinematic, luxury}.

### TikTok

| Content | Recommended strategy | Rationale |
|---------|---------------------|-----------|
| Trend / visual reel | **music_only** | Sound-on music culture |
| Storytime / facts | **narrator** | Strong VO retention format |
| Skit / multi-character | **cinematic** | Dialogue-native format |

**Defaults:** bias +20 toward `narrator` when `story_type` ∈ {storytelling, educational, mystery}.

### YouTube Shorts

| Content | Recommended strategy | Rationale |
|---------|---------------------|-----------|
| Explainer / documentary | **narrator** | VO + subtitles expected |
| High-production story | **narrator** or **cinematic** | Depends on character count |
| B-roll / montage Shorts | **music_only** | Lower production cost |

**Defaults:** bias +25 toward `narrator` for `main_niche` ∈ {educational, documentary, science}.

### Cross-platform summary

| Platform | Primary bias | Secondary | Avoid by default |
|----------|--------------|-----------|------------------|
| Instagram Reels | music_only | narrator | cinematic (unless comedy) |
| TikTok | narrator | music_only | cinematic unless skit |
| YouTube Shorts | narrator | cinematic | music_only unless montage |

---

## 8. Provider Mapping

Design-only mapping from strategy → provider bundle. No new providers required in v1.

### CLASS A — `music_only`

| Stage | Provider / module | Notes |
|-------|-------------------|-------|
| Video | **Runway** (`default_provider`) | Visual-only clips |
| Music | **Local music engine** (`music_runtime`, `assets/audio/music/`) | Primary audio layer |
| Ambience | Optional local bed | Same track or secondary loop; no SFX timeline |
| Narration | **None** | `narration_provider: disabled` for this run |
| Subtitles | **Local** (`subtitle_format_engine`) | Hook text from story hook, not TTS |
| Publish | Existing publish package | No narration artifacts |

### CLASS B — `narrator`

| Stage | Provider / module | Notes |
|-------|-------------------|-------|
| Video | **Runway** | Clip-aligned visual beats |
| Narrator | **ElevenLabs** (`default_narration_provider`) | Prefer `timeline_aware_narration_engine` |
| Music | **Local** (`music_runtime`) | Duck under speech |
| Ambience | **Local** (`environment_sound_engine`, low gain) | Optional |
| Subtitles | **Local**, timeline from `dialogue_timeline` | `generate_timeline_subtitles` |
| Publish | Full narration plan + segments | |

### CLASS C — `cinematic`

| Stage | Provider / module | Notes |
|-------|-------------------|-------|
| Video | **Runway** | Multi-character scenes |
| Character director | **Story package** (`character_director`, `dialogue_engine`) | Pre-gen |
| Voice | **ElevenLabs multi-voice** (`dialogue_to_speech_engine`, `multi_voice_casting_engine`) | Per-line assets |
| Environment | **Local** ambience + SFX timelines | `cinematic_audio_mixer` |
| Music | **Local** + cinematic mix | `music_timeline_builder` |
| Subtitles | **Local**, runtime dialogue timeline | |
| Audit | **delivery_reality_auditor** | Multi-speaker verification |

### Provider fallback chain

| Failure | Downgrade |
|---------|-----------|
| ElevenLabs unavailable (B) | music_only + subtitle-only **or** block publish (channel setting) |
| ElevenLabs partial (C) | narrator-only (narrator track only, drop character lines) |
| Music missing (A/B/C) | Warning; publish with narration/video only |
| Cinematic mix fail | Retry narrator path if narrator timeline exists |

---

## 9. Relationship to Current Architecture

| Existing component | Role after router |
|--------------------|-------------------|
| `audio_design_engine` | Strategy-aware plan depth (full vs music-only) |
| `story_package.build_story_package` | Skip dialogue/cast for music_only |
| `audio_post_processing` v7 | Dispatch by `audio_strategy` |
| `timeline_aware_narration_engine` | Default handler for `narrator` |
| `cinematic_audio_runtime` | Handler for `cinematic` only |
| `music_runtime` | All strategies; primary for music_only |
| `delivery_quality_gate` | Strategy-specific checks (e.g. skip speech level for music_only) |
| `channel_profile_store` | Source for niche, platform, overrides |

**No duplicate pipelines.** Router selects branches; it does not replace existing engines.

---

## 10. Implementation Roadmap

### Phase 1 — Router core (no pipeline split)

- Add `content_brain/audio/audio_strategy_router.py` (pure function + tests).
- Persist `audio_strategy.json` under `run_dir/metadata/`.
- Log decision in `run_summary.json`.
- **No change** to post-processing yet; shadow mode compares router vs actual path.

### Phase 2 — Pre-generation wiring

- Content brain / story generation reads strategy:
  - `music_only` → skip dialogue plan depth.
  - `narrator` → narrator-only timeline.
  - `cinematic` → full story package.
- Product Studio: optional `audio_strategy_override` in channel profile.

### Phase 3 — Post-processing dispatch

- Refactor `audio_post_processing` into three handlers.
- Add `validate_audio_strategy_router.py` + strategy-specific validators.
- Update `delivery_quality_gate` with per-strategy check profiles.

### Phase 4 — Platform presets

- Platform packs: `{instagram_reels: {bias…}, tiktok: …}`.
- UI exposure in Product Studio (“Audio mode: Auto / Music / Narrator / Cinematic”).

### Phase 5 — Observability and tuning

- Results API: store `audio_strategy`, scores, provider costs.
- A/B metrics: retention proxy by strategy × platform (manual at first).
- Tune weights from production runs.

---

## 11. Validation and Guardrails

| Check | music_only | narrator | cinematic |
|-------|------------|----------|-----------|
| Duration preserved | ✓ | ✓ | ✓ |
| Speech level | N/A | −12 to −20 dB | per-speaker audit |
| Music audibility | Required | Required, below speech | Required, ducked |
| Subtitle burn | Hook visible | Narration aligned | Dialogue aligned |
| Beat coverage | N/A | ≥ 90% beats | ≥ 90% lines |
| Runway started | Only for video | Only for video | Only for video |

**Guardrails:**

- Never invoke ElevenLabs when `audio_strategy = music_only`.
- Never run cinematic mixer when `audio_strategy = narrator` unless user upgrades.
- Preserve backward compatibility: missing `audio_strategy.json` → current behavior (`narrator` with timeline if available).

---

## 12. Example Decisions

### Example 1 — Luxury travel reel (Instagram)

- Inputs: topic “Sunset yacht aesthetic”, niche lifestyle, platform instagram_reels, 15 s, 0 characters.
- Scores: music_only **72**, narrator 28, cinematic 8.
- **Route:** `music_only`.

### Example 2 — Dragon egg story (YouTube Shorts, 4 clips)

- Inputs: educational storytelling, 2 characters in brief, narrator timeline, 40 s.
- Scores: music_only 18, narrator **74**, cinematic 52.
- **Route:** `narrator` (matches current TIMELINE_FIXED production).

### Example 3 — Cat and owl comedy skit (TikTok)

- Inputs: 3 characters, 8 dialogue lines, comedy.
- Scores: music_only 5, narrator 35, cinematic **81**.
- **Route:** `cinematic`.

---

## 13. Open Questions (for approval before Phase 1)

1. Should `music_only` runs still generate a minimal story package for Runway prompts, or a separate “visual brief” schema?
2. On ElevenLabs failure for Class B, is silent publish acceptable or hard-fail?
3. Should channel profile `character_voice_mode: multi_voice` force minimum Class C, or only add score weight?
4. Where should override live: channel profile only, per-run UI, or both?

---

## 14. Deliverables Checklist (this document)

- [x] Three audio classes (A / B / C) with pipelines
- [x] Decision engine with scoring inputs and output schema
- [x] Strategy matrix
- [x] Routing rules (pre-gen + post-processing)
- [x] Platform recommendations (Instagram Reels, TikTok, YouTube Shorts)
- [x] Provider mapping per strategy
- [x] Implementation roadmap
- [x] Integration with existing ModirAgentOS modules
- [x] No implementation performed

---

**Next step when approved:** Phase 1 shadow-mode router + `validate_audio_strategy_router.py` (design complete; implementation not started).
