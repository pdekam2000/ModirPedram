# Kling Native Audio — GUI & Content Brain Integration Design

**Phase:** KLING-NATIVE-AUDIO-GUI-INTEGRATION-DESIGN  
**Status:** Design only — no implementation  
**Date:** 2026-06-16  
**Authority:** Extends `KLING_STORY_ARCHITECTURE_DESIGN.md`, `PHASE_AUDIO_STRATEGY_ROUTER_DESIGN_REPORT.md`, and live benchmark from `KLING_MULTISHOT_LIVE_APPROVAL_GATED_REPORT.md`

---

## 1. Executive Summary

Kling 3.0 Pro with **Native Audio** (Multishot, 12s + 3s continuity) is promoted from an automation experiment to a **first-class video provider** in the Product UI and Content Brain.

**Benchmark evidence:** First live test produced character voices, environment audio, breathing, emotional acting, and dialogue in-video — quality that exceeds the current **narrator-only post pipeline** for cinematic, dialogue-heavy stories.

This design specifies:

1. **GUI** — Create Video + Results surfaces for audio strategy, provider selection, Kling duration rules  
2. **Content Brain** — Planning chain: Story → **Kling Frame Story Planner (preferred)** or Kling Multishot Planner (fallback)  
3. **Router** — Auto mode maps content class → audio strategy → provider bundle → **frame vs multishot mode**  
4. **Continuity** — Frame handoff metadata across 15s Kling clips  
5. **Schema** — Run-level and clip-level JSON artifacts  
6. **Migration** — Path off narrator-first cinematic pipeline  
7. **Implementation order** — Phased rollout without breaking Runway Phase I

**Mode preference (2026-06-17):** `kling_frame_to_video_native_audio` preferred; `kling_multishot_native_audio` fallback. See [`KLING_FRAME_TO_VIDEO_ARCHITECTURE.md`](KLING_FRAME_TO_VIDEO_ARCHITECTURE.md).

**Future GUI control (design):** Kling Mode — Auto | Frame-to-Video (recommended) | Multishot

**Hard rule (design):** When `audio_strategy = kling_native_audio`, **skip ElevenLabs narration overlay** for speech; native audio is authoritative in the generated MP4.

---

## 2. Current State vs Target State

### 2.1 Product UI (today)

| Surface | Today | Gap |
|---------|-------|-----|
| Create Video | Provider: Runway / Hailuo only | No Kling, no audio strategy |
| Duration | Presets 6–40s, custom | No Kling 15/30/45/60 model |
| Preflight | `duration_planner` → clip count | Assumes 10s Runway clips |
| Generate | Phase I FULL_AUTO Runway only | No Kling live path |
| Results | Narrator / cinematic / music status | No Kling native audio block |

**Reference:** `ui/web/src/pages/CreateVideoPage.tsx`, `content_brain/scheduling/duration_planner.py`

### 2.2 Content Brain (today)

```
Topic → Strategy → Story Package → Clip Planner → Prompt Builder → Runway clip_prompts[]
                                      ↓
                            Post: narrator / cinematic / music_only
```

**Gap:** No shot-level planning; no Kling 12+3 structure; post-processing assumes external VO.

### 2.3 Target Content Brain (Kling mode)

```
Topic
  ↓
Story Architect (narrative arc, beats, cast)
  ↓
Kling Story Planner        ← NEW: arc → N × 15s clips, beat allocation
  ↓
Kling Clip Planner         ← NEW: per-clip story beat, continuity fields
  ↓
Kling Shot Planner         ← NEW: shot_1 (12s) + shot_2 (3s) prompts + audio cues
  ↓
Execution bundle           → kling_multishot_live_runner (approval-gated)
  ↓
Assembly                   → concat N × 15s (minimal audio post — optional music bed only)
```

When **not** in Kling mode, existing pipeline remains unchanged.

---

## 3. GUI Changes — Create Video Page

### 3.1 New control: Video Audio Strategy

**Location:** Create Video → new card **“Video Audio Strategy”** (above or beside Provider).

| Option | ID | Description |
|--------|-----|-------------|
| **Auto (recommended)** | `auto` | Router decides (default) |
| Music Only | `music_only` | Class A — no speech, music + optional captions |
| Narrator | `narrator` | Class B — ElevenLabs narrator post-mix |
| **Kling Native Audio** | `kling_native_audio` | Class C-Kling — in-video native audio via Kling 3.0 Pro |

**Default:** `auto`

**Payload fields (API):**

```json
{
  "audio_strategy": "auto",
  "audio_strategy_override": null
}
```

When user picks a non-auto value, set `audio_strategy_override` to that ID (matches Audio Strategy Router hard-override pattern).

**UX copy (Auto selected):**

> Auto picks the best audio path from your topic, style, and platform. Cinematic dialogue-heavy stories may route to **Kling Native Audio**.

### 3.2 New control: Video Provider

**Location:** Replace single Runway/Hailuo select with expanded provider matrix.

| Option | ID | Notes |
|--------|-----|-------|
| **Auto** | `auto` | Router + audio strategy decide |
| Runway Gen-4 | `runway_gen4` | Maps to existing Gen-4 browser path |
| Runway Gen-5 | `runway_gen5` | Future Gen-5 path (placeholder in v1 UI) |
| **Kling 3.0 Pro Native Audio** | `kling_3_pro_native` | Multishot 2-shot, native audio ON |

**Default:** `auto`

**Coupling rules (UI validation):**

| User selection | Allowed audio strategies |
|----------------|-------------------------|
| `kling_3_pro_native` | Force `kling_native_audio` (disable other audio options or show read-only) |
| `kling_native_audio` (audio) | Provider must be `kling_3_pro_native` or `auto` |
| Runway / Hailuo | Cannot use `kling_native_audio` unless user confirms override |

**Warning banner:** Selecting Kling shows estimated credit use and approval-gated Generate (link to existing live runner behavior).

### 3.3 Duration rules (Kling mode)

When provider resolves to Kling **or** audio strategy is `kling_native_audio`:

| UI behavior | Detail |
|-------------|--------|
| Duration presets | **Replace** chip row with **15 / 30 / 45 / 60** only |
| Custom duration | **Disabled** (or hidden) for Kling |
| Clip count | **Read-only**, derived — not overridable |
| Helper text | Show mapping table inline |

**Mapping table (visible in UI):**

| Total duration | Kling clips | Structure |
|----------------|-------------|-----------|
| **15s** | 1 clip | 1 × (12s action + 3s bridge) |
| **30s** | 2 clips | 2 × 15s with frame continuity |
| **45s** | 3 clips | 3 × 15s |
| **60s** | 4 clips | 4 × 15s (max standard pack) |

**Formula:** `kling_clip_count = duration_seconds / 15`

**Preflight panel addition:**

```
Kling plan: 3 clips × 15s (45s total)
Shot mode: 12s main action + 3s continuity bridge per clip
Audio: Native (in-video) — no narrator overlay planned
```

**Non-Kling mode:** Keep existing presets (6, 8, 10, 20, 30, 40, custom) and current clip override.

### 3.4 Preflight & Generate (Kling)

| Step | Behavior |
|------|----------|
| Preflight Plan | Calls backend with `audio_strategy` + `video_provider`; returns `kling_story_plan` preview if Kling path |
| Generate Video | Routes to **Kling live engine** (prepare → approval checklist → optional Generate) — **not** Phase I FULL_AUTO |
| Runway browser panel | Show when Runway selected; show **Kling status panel** when Kling selected (CDP connection, approval state) |

### 3.5 Create Video — wireframe (logical)

```
┌─────────────────────────────────────────────────────────────┐
│ Create Video                                                 │
├─────────────────────────────────────────────────────────────┤
│ Topic Source          │ Duration                             │
│                       │ [15][30][45][60]  ← Kling mode     │
│                       │ 1 clip = 15s · 12s+3s per clip     │
├───────────────────────┼─────────────────────────────────────┤
│ Video Audio Strategy  │ Video Provider                       │
│ (•) Auto              │ (•) Auto                             │
│ ( ) Music Only        │ ( ) Runway Gen-4                     │
│ ( ) Narrator          │ ( ) Runway Gen-5                     │
│ ( ) Kling Native Audio│ ( ) Kling 3.0 Pro Native Audio       │
├───────────────────────┴─────────────────────────────────────┤
│ [Preflight Plan]  [Generate Video]                          │
│ ⚠ Kling: Generate requires explicit approval (credits)      │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. GUI Changes — Results Page

Add a **“Video & Audio Provenance”** section (always visible when run used Kling; collapsed optional for legacy runs).

| Field | Source | Example |
|-------|--------|---------|
| **Provider Used** | `run.execution.video_provider_resolved` | Kling 3.0 Pro |
| **Audio Strategy** | `run.audio_strategy.resolved` | Native Audio |
| **Shot Mode** | `run.kling.multishot_strategy` | 12s + 3s |
| **Clip Count** | `run.kling.kling_clip_count` | 3 |
| **Total Duration** | `run.kling.total_kling_seconds` | 45s |
| **Native Audio Status** | `run.kling.native_audio_status` | See enum below |
| **Per-clip table** | `run.kling.clips[]` | Shot prompts, continuity, frame handoff status |

**Native Audio Status enum:**

| Status | Meaning |
|--------|---------|
| `not_applicable` | Runway/Hailuo narrator or music path |
| `planned` | Kling selected, not yet generated |
| `generated_in_video` | Clip MP4 contains Kling native audio |
| `verified` | ffprobe / manual QA confirmed audio streams |
| `failed_qa` | Video ok, audio missing or corrupt |

**Hide or de-emphasize for Kling runs:**

- Narrator coverage / ElevenLabs timeline (show “Skipped — Kling Native Audio”)
- Cinematic multi-voice mixer status (show “Not used — native audio authoritative”)

**Show retained:**

- Assembly status, publish package, branding, subtitles (optional — dialogue may be burned from native speech or skipped)

**Reference extension point:** `ui/web/src/pages/ResultsPage.tsx` — add `kling_provenance` block alongside existing `cinematic_audio` / `story_audio_director` sections.

---

## 5. Content Brain Changes

### 5.1 Pipeline insertion point

Insert **after** `_step_story_generation` and **before** `_step_clip_planner` in E2E micro studio — **only when** resolved route is Kling.

**Reference:** `content_brain/execution/content_brain_e2e_micro_test_studio.py`

```
Existing:  step3 story → step5 clip_planner → step6 prompt_generation
Kling:     step3 story → step3k kling_story_planner → step3k2 kling_clip_planner
           → step3k3 kling_shot_planner → step5k execution_bundle (skip legacy clip_prompts)
```

Legacy `clip_planner` + monolithic `clip_prompts[]` **bypassed** for Kling — replaced by structured shot plans.

### 5.2 Module responsibilities

| Module (future) | Responsibility |
|-----------------|----------------|
| `content_brain/story/kling_story_planner.py` | Map story arc → N clips (15/30/45/60), beat allocation, `kling_story_plan_v1` |
| `content_brain/story/kling_clip_planner.py` | Per clip: beat assignment, `continuity_anchor`, `next_clip_reference_hint`, `first_frame_source` |
| `content_brain/story/kling_shot_planner.py` | Expand clip beat → `shot_1_prompt` (12s) + `shot_2_prompt` (3s) with native audio directives |
| `content_brain/story/kling_plan_validator.py` | Schema + duration + prompt length guards |

**No duplicate story engines** — extend Story Architect output; planners consume `story_brief` + `duration_plan`.

### 5.3 Per-clip output (required)

Each clip in `kling_story_plan_v1.clips[]`:

```json
{
  "clip_index": 1,
  "clip_duration": 15,
  "shot_1_duration": 12,
  "shot_1_prompt": "…main action with dialogue, breathing, forest ambience, native audio…",
  "shot_2_duration": 3,
  "shot_2_prompt": "…bridge hold frame, wind, trust beat, native cinematic audio…",
  "continuity_anchor": "Boy cradling wrapped egg, forest path, wary eyes camera-left, warm rim light.",
  "next_clip_reference_hint": "Same boy, same egg, footsteps — hides behind fallen log.",
  "first_frame_source": "user_upload",
  "prior_clip_index": null,
  "native_audio_directives": {
    "dialogue_lines": ["Don't worry... I won't hurt you."],
    "ambience": ["forest", "wind", "distant thunder"],
    "foley": ["breathing", "soft growl"],
    "voice_acting": "emotional, whispered reassurance"
  }
}
```

Clip 1: `first_frame_source: user_upload` (optional starter image from asset library).  
Clip N>1: `first_frame_source: prior_clip_shot2_final_frame`, `prior_clip_index: N-1`.

### 5.4 Prompt authoring rules (Shot Planner)

| Shot | Duration | Content |
|------|----------|---------|
| **Shot 1** | 12s | Primary beat — action, dialogue, character emotion, camera motion, **native audio cues** (voices, ambience, SFX) |
| **Shot 2** | 3s | Transition bridge — holdable final frame, wind/breath tail, **explicit “hold final frame”** language for continuity extraction |

**Suffix convention (machine-readable):** Append `Native audio.` or structured `native_audio_directives` block — planner merges into prompt text for Runway/Kling UI.

**Do not** embed ElevenLabs narrator script in Kling prompts when `audio_strategy = kling_native_audio`.

### 5.5 Post-processing branch (Kling)

When Kling native audio is authoritative:

```
Kling clips (N × 15s MP4, audio embedded)
  ↓
Concat assembly (no narration merge)
  ↓
Optional light music bed (user/channel setting, heavily ducked or off)
  ↓
Optional subtitles (from dialogue_lines metadata, not narrator timeline)
  ↓
Branding + Publish
```

**Skip:** `timeline_aware_narration_engine`, `dialogue_to_speech_engine`, cinematic mixer for speech tracks.

---

## 6. Content Router (Auto Mode)

### 6.1 Two-stage routing

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 1 — Audio Strategy Router (existing design)            │
│ Inputs: topic, niche, style, platform, characters, dialogue  │
│ Output: music_only | narrator | cinematic | kling_native_audio│
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 2 — Video Provider Router (extended)                   │
│ Inputs: audio_strategy, user provider pref, channel defaults │
│ Output: runway_gen4 | runway_gen5 | kling_3_pro_native       │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Auto mapping — Audio Strategy

| Class | Strategy ID | Typical niches / signals |
|-------|-------------|--------------------------|
| **A** | `music_only` | Motivation, luxury, travel, lifestyle, nature, aesthetic reels |
| **B** | `narrator` | Mystery, educational, documentary, explainer, horror (VO-led) |
| **C** | `kling_native_audio` | Fantasy, animals, children, horror (scene audio), mini movies, dialogue-heavy, emotional cinematic |

**Upgrade from prior Class C (`cinematic`):**

| Prior `cinematic` | New resolution |
|-------------------|----------------|
| Multi-voice ElevenLabs post | **`kling_native_audio`** when provider Kling available + dialogue ≥ 2 + fantasy/character signals |
| Fallback | `cinematic` (legacy ElevenLabs) if Kling unavailable or user/channel blocks Kling |

**New scoring feature (Audio Strategy Router v2 design):**

| Feature | kling_native_audio boost |
|---------|--------------------------|
| `story_type` ∈ {fantasy, animals, children, mini_movie} | +35 |
| `dialogue_count` ≥ 2 | +25 |
| `character_count` ≥ 2 | +20 |
| User wants “character speaks in video” | +30 |
| Platform YouTube Shorts cinematic | +10 |
| Duration ∈ {30, 45, 60} | +15 (Kling sweet spot) |

**Hard route to Kling (Auto):**

```
IF scores.kling_native_audio ≥ 60
   AND dialogue_count ≥ 1
   AND NOT channel.block_kling_native
THEN audio_strategy = kling_native_audio
```

### 6.3 Auto mapping — Video Provider

| Resolved audio_strategy | Default provider |
|-------------------------|------------------|
| `music_only` | Runway Gen-4 (silent-ish gen + music post) |
| `narrator` | Runway Gen-4 |
| `kling_native_audio` | **Kling 3.0 Pro Native Audio** |
| `cinematic` (legacy) | Runway Gen-4 + ElevenLabs post |

User **Video Provider = Auto** accepts router output. Explicit user selections override Auto (with validation coupling in §3.2).

### 6.4 Duration planner extension (design)

New provider key in `duration_planner`:

```python
PROVIDER_CLIP_LIMIT_SECONDS = {
    "runway": 10,
    "hailuo": 8,
    "kling_3_pro_native": 15,  # Kling unit = 15s clip
}
```

For Kling: `clip_count = duration_seconds // 15`, only allow durations {15, 30, 45, 60}.

---

## 7. Continuity Architecture

### 7.1 Visual continuity chain

```
Clip N                          Clip N+1
┌─────────────────────┐         ┌─────────────────────┐
│ Shot 1 (12s action) │         │ Shot 1 (12s action) │
│ Shot 2 (3s bridge)  │──frame──► first_frame_upload   │
│   └─ final frame    │         │ Shot 2 (3s bridge)  │
└─────────────────────┘         └─────────────────────┘
```

### 7.2 Metadata representation

**Run-level:** `kling_continuity_chain_v1`

```json
{
  "version": "kling_continuity_chain_v1",
  "multishot_strategy": "two_shot_continuity",
  "clips": [
    {
      "clip_index": 1,
      "first_frame": {
        "source": "user_upload",
        "asset_path": "outputs/assets/starter_frame.png",
        "upload_status": "pending | uploaded | verified"
      },
      "generation": {
        "output_mp4": "outputs/kling_multishot_live/{run_id}/clip_01.mp4",
        "status": "pending | generated | downloaded"
      },
      "continuity_extract": {
        "shot_2_final_frame_path": "outputs/kling_multishot_live/{run_id}/clip_01_shot2_final.png",
        "extract_method": "ffmpeg_last_frame | manual",
        "extract_status": "pending | ok | failed",
        "continuity_anchor_match_score": 0.0
      },
      "handoff_to_next": {
        "next_clip_index": 2,
        "next_clip_first_frame_path": "…/clip_02_first_frame.png",
        "handoff_status": "pending | linked | verified"
      }
    }
  ]
}
```

**Per-clip cross-reference fields (already in story plan):**

| Field | Role |
|-------|------|
| `continuity_anchor` | Text QA — does extracted frame match described end state? |
| `next_clip_reference_hint` | Feeds Clip N+1 Shot 1 prompt continuity |
| `prior_clip_index` | Links to upstream clip for frame path resolution |
| `first_frame_source` | `user_upload` \| `prior_clip_shot2_final_frame` |

### 7.3 Execution handoff (live runner integration)

Extend `kling_multishot_live_engine` (future) to:

1. After clip N download → extract last frame (Shot 2 region or final 0.5s frame)  
2. Write `clip_N_shot2_final.png` to run folder  
3. Clip N+1 prepare step → pass as `--first-frame-path`  
4. Update `kling_continuity_chain_v1` statuses  

**Alignment:** Reuse frame extraction patterns from Runway `use_frame_button` pipeline conceptually — **separate output root** `outputs/kling_multishot_live/` (no Phase I folder mixing).

### 7.4 Assembly

```
clip_01.mp4 (15s) + clip_02.mp4 (15s) + … → kling_assembled_{run_id}.mp4
```

Assembly metadata records per-clip native audio preserved (no re-encode unless branding requires).

---

## 8. Metadata Schema Summary

### 8.1 Run record extensions

Path: `outputs/runs/{run_id}/run_metadata.json` (or existing session store)

```json
{
  "audio_strategy": {
    "requested": "auto",
    "resolved": "kling_native_audio",
    "router_version": "audio_strategy_router_v2",
    "confidence": 0.91,
    "reasons": ["topic:fantasy", "dialogue_count:3", "character_count:2"]
  },
  "video_provider": {
    "requested": "auto",
    "resolved": "kling_3_pro_native",
    "execution_engine": "kling_multishot_live_v1"
  },
  "kling": {
    "multishot_strategy": "two_shot_continuity",
    "shot_mode_label": "12s + 3s",
    "requested_duration_seconds": 45,
    "kling_clip_count": 3,
    "total_kling_seconds": 45,
    "native_audio_status": "generated_in_video",
    "story_plan_path": "outputs/runs/{run_id}/kling_story_plan_v1.json",
    "continuity_chain_path": "outputs/runs/{run_id}/kling_continuity_chain_v1.json",
    "generate_approval": {
      "approved_by": "operator",
      "approved_at": "ISO-8601",
      "generate_clicked": true
    }
  }
}
```

### 8.2 API — Create Video preflight response (extension)

```json
{
  "authoritative_topic": "…",
  "duration_plan": {
    "duration_seconds": 45,
    "clip_count": 3,
    "provider": "kling_3_pro_native",
    "clip_limit_seconds": 15,
    "kling_duration_mode": true
  },
  "audio_strategy": {
    "resolved": "kling_native_audio",
    "display_label": "Kling Native Audio"
  },
  "kling_story_plan_preview": {
    "clip_count": 3,
    "clips": [
      { "clip_index": 1, "shot_1_preview": "…", "shot_2_preview": "…" }
    ]
  },
  "warnings": []
}
```

### 8.3 Results API — extension

Add to `fetchLatestResults` payload:

```json
{
  "kling_provenance": {
    "provider_used": "Kling 3.0 Pro",
    "audio_strategy_label": "Native Audio",
    "shot_mode": "12s + 3s",
    "clip_count": 3,
    "native_audio_status": "verified",
    "assembled_output_path": "outputs/kling_multishot_live/…/kling_assembled_….mp4"
  }
}
```

---

## 9. Migration Plan — Narrator Pipeline → Kling Native Audio

### 9.1 What changes for operators

| Scenario | Before | After (Kling route) |
|----------|--------|---------------------|
| Dragon / fantasy story | Runway 4×10s + narrator timeline | Kling 3×15s native dialogue in video |
| Post-processing time | Narration synthesis + mix | Mostly assembly + optional subtitles |
| ElevenLabs credits | Per-segment narrator | **Zero** for speech (optional narrator only if fallback) |
| Continuity | Use-frame between Runway clips | Shot 2 bridge frame → next first frame |

### 9.2 Parallel operation (required)

| Path | Status |
|------|--------|
| Runway Phase I FULL_AUTO | **Keep** — default for non-Kling |
| Narrator / cinematic post | **Keep** — Class A/B and legacy Class C |
| Kling Multishot live | **Add** — Class C-Kling, separate output folder |

**No breaking changes** to existing runs; Kling is opt-in via router or explicit UI selection.

### 9.3 Content migration steps

1. **Re-storyboard** — Do not map 4×10s beats 1:1 to Kling; re-plan into 12+3 beats (`KLING_STORY_ARCHITECTURE_DESIGN.md` §6.3).  
2. **Prompt rewrite** — Move dialogue from `dialogue_timeline` narrator segments into `shot_1_prompt` / native_audio_directives.  
3. **Disable narrator post** — Set `skip_narration: true` on run when `kling_native_audio`.  
4. **Subtitle strategy** — Generate from `dialogue_lines` metadata or ASR optional pass; not from narrator MP3 alignment.  
5. **Channel profile** — Add `prefer_kling_native_audio: bool`, `block_kling_native: bool` for operator control.

### 9.4 Fallback matrix

| Failure | Fallback |
|---------|----------|
| Kling Generate fails | Offer retry or downgrade to Runway + narrator (explicit approval) |
| Native audio QA fails | Flag in Results; optional narrator overlay (user opt-in) |
| Frame handoff extract fails | Manual first-frame upload gate before clip N+1 |
| CDP / browser unavailable | Block Kling route in preflight with clear error |

---

## 10. Recommended Implementation Order

| Phase | Scope | Depends on |
|-------|-------|------------|
| **P0** | JSON schemas: `kling_story_plan_v1`, `kling_continuity_chain_v1`, run metadata extensions | Design approval |
| **P1** | `duration_planner` + `product_studio_service` Kling duration/provider validation | P0 |
| **P2** | Audio Strategy Router v2 — add `kling_native_audio` class + scoring | P0 |
| **P3** | Content Brain: `kling_story_planner` → `kling_clip_planner` → `kling_shot_planner` + validator | P0, P2 |
| **P4** | Create Video UI — audio strategy + provider + Kling duration chips + preflight preview | P1, P2 |
| **P5** | Wire Generate → `kling_multishot_live_runner` multi-clip loop + continuity chain | Live runner (done), P3 |
| **P6** | Results page — Kling provenance block + native audio status | P5 |
| **P7** | Assembly concat + skip narrator post branch in `audio_post_processing` | P5 |
| **P8** | Channel profile settings + Auto router tuning from benchmark feedback | P2, P4 |
| **P9** | Migration tooling — re-plan legacy runs (optional CLI) | P3 |

**Do not implement P5 Generate automation without approval gate** — preserve existing `grant_continuity_approval` pattern.

---

## 11. Architecture Safety Checklist

| Rule | Compliance |
|------|------------|
| Extend, don’t duplicate | Planners extend Story Architect; reuse `kling_multishot_locator` / live engine |
| No Phase I folder mixing | `outputs/kling_multishot_live/` only |
| Approval-gated Generate | Required — already in live runner |
| JSON-safe artifacts | All plans versioned (`*_v1`) |
| Backward compatible | Runway + narrator paths unchanged when not Kling |

---

## 12. References

| Document / module | Role |
|-------------------|------|
| `project_brain/KLING_STORY_ARCHITECTURE_DESIGN.md` | 12+3 clip model, schema draft |
| `project_brain/PHASE_AUDIO_STRATEGY_ROUTER_DESIGN_REPORT.md` | Class A/B/C router |
| `project_brain/KLING_MULTISHOT_LIVE_APPROVAL_GATED_REPORT.md` | Live benchmark, approval flow |
| `tools/kling_multishot_live_runner.py` | Execution target |
| `ui/web/src/pages/CreateVideoPage.tsx` | GUI integration point |
| `ui/web/src/pages/ResultsPage.tsx` | Results integration point |
| `content_brain/scheduling/duration_planner.py` | Duration/clip authority |

---

**End of design — no code changes in this phase.**
