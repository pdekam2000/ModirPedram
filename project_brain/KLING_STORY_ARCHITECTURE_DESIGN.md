# Kling Story Architecture — Design

**Phase:** KLING STORY ARCHITECTURE DESIGN (update)  
**Status:** Multishot = fallback/legacy; **Frame-to-Video = preferred** (see [`KLING_FRAME_TO_VIDEO_ARCHITECTURE.md`](KLING_FRAME_TO_VIDEO_ARCHITECTURE.md))  
**Date:** 2026-06-17 (Frame-to-Video switch) / 2026-06-16 (original multishot design)  
**Supersedes:** Multishot as **default** story mode — multishot remains supported as fallback  

---

## 0. Preferred mode update (2026-06-17)

**Decision:** Kling **Frame-to-Video Native Audio** is now preferred for cinematic story generation.

| Mode | Prompt | Role |
|------|--------|------|
| **Frame-to-Video** | ~2500 chars / clip | **Preferred** — rich story, dialogue, camera, audio cues |
| **Multishot 12+3** | ~512 chars × 2 shots | **Fallback / legacy** — when frame UI unavailable or explicit operator choice |

Multishot sections below remain valid for fallback execution and existing continuity chain runs.

**Primary architecture doc:** [`KLING_FRAME_TO_VIDEO_ARCHITECTURE.md`](KLING_FRAME_TO_VIDEO_ARCHITECTURE.md)

---

## 1. Executive Summary (Multishot fallback mode)

Kling Multishot production uses a **2-shot continuity mode** per generated clip:

| Shot | Duration | Role |
|------|----------|------|
| **Shot 1** | **12 s** | Main story action for this clip |
| **Shot 2** | **3 s** | Transition bridge / next-scene setup |
| **Clip total** | **15 s** | One Kling Multishot generation unit |

This replaces the earlier **5-shot full story** default (5 × 3 s). Reason: **12 + 3** yields smoother cinematic motion inside each clip while preserving **cross-clip continuity** via a dedicated 3 s bridge shot.

**Continuity rule:** The **final frame / transition moment from Shot 2 of Clip N** becomes the **first frame / reference image** for Clip N+1.

Content Brain must emit a structured **Kling clip plan** per clip. Runway UI automation maps each plan to Multishot fields (`shot_1_duration=12`, `shot_2_duration=3`, prompts, first-frame upload).

---

## 2. Design Decision: Why 2-Shot Continuity (12 + 3)

### Compared to 5 × 3 s (deprecated default)

| Aspect | 5 × 3 s (Strategy B) | **2 × (12 + 3) continuity (new default)** |
|--------|----------------------|---------------------------------------------|
| Motion quality | Frequent hard cuts every 3 s | **12 s** allows continuous action in Shot 1 |
| Beat control | Five micro-beats inside one clip | Two beats: **action + bridge** |
| Cross-clip link | Weak | **Explicit 3 s bridge** + frame handoff |
| UI complexity | Add shot × 3, five prompt fields | **Default 2 shots** — matches Runway default layout |
| Map readiness | Shots 3–5 inferred | **P0 map complete** (`shot_1/2` + duration menus) |

### Compared to single 15 s shot

| Aspect | One 15 s shot | **12 + 3** |
|--------|---------------|------------|
| Transition to next clip | Abrupt end frame | **Designed bridge** in Shot 2 |
| Prompt structure | Monolithic | **Action vs bridge** separation |

**Approved default for Kling Multishot fallback story content** unless operator explicitly selects Frame-to-Video or another mode.

> **Note (2026-06-17):** For new cinematic / dialogue-heavy stories, prefer **Frame-to-Video** (`kling_frame_to_video_native_audio`). Use this 2-shot multishot model only as fallback.

---

## 3. Clip Unit Definition

### 3.1 One Kling clip = 15 seconds

```
┌─────────────────────────────────────────────────────────────┐
│  KLING CLIP N  (15 s total)                                 │
├──────────────────────────────┬──────────────────────────────┤
│  SHOT 1 — 12 s               │  SHOT 2 — 3 s                │
│  Main story action           │  Transition bridge           │
│  (primary visual beat)       │  (setup for Clip N+1)        │
└──────────────────────────────┴──────────────────────────────┘
         │                                    │
         │                                    └── continuity_anchor
         │                                        (final frame → Clip N+1 first frame)
         └── may use Clip N-1 Shot 2 final frame as first frame input
```

### 3.2 Runway Multishot UI mapping

| Plan field | Runway control | Value |
|------------|----------------|-------|
| `shot_1_duration` | Shot 1 duration menu | **12 s** (`shot_1_duration_12s`) |
| `shot_1_prompt` | Shot 1 prompt textbox | `shot_1_prompt` |
| `shot_2_duration` | Shot 2 duration menu | **3 s** (default / `shot_2_duration_3s`) |
| `shot_2_prompt` | Shot 2 prompt textbox | `shot_2_prompt` |
| First frame (Clip 1) | `first_frame_upload` | User/asset reference |
| First frame (Clip N>1) | `first_frame_upload` | Extracted from **Clip N−1 Shot 2** final frame |

**No Add shot clicks** required for standard 15 s clip (Runway default = 2 shots).

---

## 4. Continuity Rule

### 4.1 Between clips

```
Clip 1                          Clip 2                          Clip 3
[12s action][3s bridge]  ──►   [12s action][3s bridge]  ──►   ...
     │              │
     │              └── continuity_anchor (final frame)
     │                        │
     └────────────────────────┴──► first_frame for Clip 2
```

| Step | Action |
|------|--------|
| 1 | Generate Clip N with Shot 1 (12 s) + Shot 2 (3 s bridge) |
| 2 | On completion, capture **final frame** of Shot 2 (or last frame of full 15 s clip) |
| 3 | Upload / attach that frame as **First Video Frame** for Clip N+1 |
| 4 | Shot 1 prompt of Clip N+1 should **continue** from `next_clip_reference_hint` of Clip N |

### 4.2 Continuity fields (Content Brain)

| Field | Purpose |
|-------|---------|
| `continuity_anchor` | Describe the **visual state at end of Shot 2** (character pose, lighting, prop position) — used for frame extraction validation |
| `next_clip_reference_hint` | Textual bridge: what Clip N+1 Shot 1 should **pick up from** (fed to prompt + frame QA) |

### 4.3 Alignment with existing ModirAgentOS continuity

Reuse patterns from Runway continuity / use-frame pipeline where applicable:

- `use_frame_button` / download final frame from prior generation  
- Do **not** break existing 4 × ~10 s Runway clip assembly path — Kling path is a **parallel provider architecture** for Kling Native Audio workflows  

---

## 5. Content Brain Output Schema

### 5.1 Package level

```json
{
  "version": "kling_story_plan_v1",
  "provider": "kling_multishot",
  "multishot_strategy": "two_shot_continuity",
  "requested_duration_seconds": 60,
  "kling_clip_count": 4,
  "total_kling_seconds": 60,
  "duration_policy": "exact_match",
  "clips": [ "…KlingClipPlan…" ]
}
```

### 5.2 Per-clip plan (required fields)

Each entry in `clips[]`:

```json
{
  "clip_index": 1,
  "clip_duration": 15,
  "shot_1_duration": 12,
  "shot_1_prompt": "Main action: boy discovers glowing dragon egg beneath forest leaves, slow push-in, golden light filtering through trees.",
  "shot_2_duration": 3,
  "shot_2_prompt": "Transition bridge: boy wraps the egg and glances toward distant footsteps, camera settles on his guarded expression, hold final frame.",
  "continuity_anchor": "Boy cradling wrapped egg, forest path behind, wary eyes toward camera-left, warm rim light.",
  "next_clip_reference_hint": "Same boy, same wrapped egg, footsteps audible, he turns to hide behind a fallen log.",
  "first_frame_source": "user_upload | prior_clip_shot2_final_frame",
  "prior_clip_index": null,
  "story_beat_ids": ["discovery"],
  "metadata": {
    "emotion": "wonder",
    "camera": "slow push-in → static hold"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `clip_index` | int | Yes | 1-based clip number |
| `clip_duration` | int | Yes | Always **15** for Kling unit |
| `shot_1_duration` | int | Yes | Always **12** |
| `shot_1_prompt` | string | Yes | Main action (visual + motion) |
| `shot_2_duration` | int | Yes | Always **3** |
| `shot_2_prompt` | string | Yes | Bridge / next-scene setup; ends on holdable frame |
| `continuity_anchor` | string | Yes | End-state description for frame extraction QA |
| `next_clip_reference_hint` | string | Yes | Handoff to Clip N+1 Shot 1 (empty on last clip) |
| `first_frame_source` | enum | Yes | `user_upload` (clip 1) or `prior_clip_shot2_final_frame` |
| `prior_clip_index` | int \| null | Clip 1: null; else N−1 | |

### 5.3 Story beat distribution

Content Brain maps narrative arc → Kling clips:

| Total clips | Beat allocation (example) |
|-------------|---------------------------|
| 1 (15 s) | Setup + mini-bridge |
| 2 (30 s) | Setup → escalation |
| 3 (45 s) | Setup → conflict → discovery |
| 4 (60 s) | Hook/setup → conflict → discovery → resolution/CTA bridge |

**Rule:** Shot 1 carries the **primary beat**; Shot 2 always **bridges forward** (even on final clip — bridge can tee CTA visually without new locations).

---

## 6. Duration Mapping

### 6.1 Supported Kling Native Audio durations

| Requested duration | Kling clips | Total seconds | Notes |
|--------------------|-------------|---------------|-------|
| **15 s** | 1 | 15 | Single clip |
| **30 s** | 2 | 30 | |
| **45 s** | 3 | 45 | |
| **60 s** | 4 | 60 | Max standard pack |

**Formula:**

```
kling_clip_count = requested_duration_seconds / 15
```

Must be integer; only **15, 30, 45, 60** allowed without policy override.

### 6.2 Unsupported durations

| Request | Policy |
|---------|--------|
| Not divisible by 15 | **Round up** to nearest 15 s (e.g. 20 → 30) **or** reject at UI |
| Between tiers (e.g. 25) | Prefer **UI restriction** to 15/30/45/60 only |
| > 60 | Out of scope v1 — cap at 60 or require multi-segment project |

**UI recommendation:** Kling Native Audio duration picker exposes **only 15 / 30 / 45 / 60** when `provider = kling_multishot`.

**Content Brain recommendation:** If rounded up, set `duration_policy: "rounded_up"` and emit `requested_duration_seconds` vs `total_kling_seconds` for operator visibility.

### 6.3 Mapping from legacy Runway 4-clip (~40 s) model

Existing E2E runs use **4 × ~10 s Runway clips ≈ 40 s**. Kling continuity model:

| Legacy | Kling equivalent |
|--------|------------------|
| 4 clips × 10 s | **Not 1:1** — prefer **3 × 15 s = 45 s** or **2 × 15 s = 30 s** re-storyboard |
| Per-clip beat | Maps to **Shot 1**; inter-clip link via **Shot 2 bridge** |

Migration: Content Brain **re-plans beats** into 12+3 units rather than stretching 10 s beats.

---

## 7. Pipeline Architecture (design)

```
┌──────────────────┐
│  Topic + duration│
│  + channel profile│
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Duration gate   │  15/30/45/60 only (or round-up policy)
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Story Architect │  Arc → N clips × (12+3) beat split
│  + Kling planner │  Emits kling_story_plan_v1
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Per-clip bundle │  shot_1_prompt, shot_2_prompt, continuity fields
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Runway UI map   │  Multishot 2-shot, 12s+3s, first frame upload
│  (shadow-mode+)  │  NO Generate without approval
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Frame handoff   │  Clip N Shot 2 final → Clip N+1 first frame
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Assembly        │  Concat N × 15 s → deliverable
└──────────────────┘
```

---

## 8. Integration Points (existing systems)

| System | Role | Change (future) |
|--------|------|-----------------|
| `story_architect.py` | Narrative arc | Add Kling clip slicing mode |
| `story_package` / `clip_beats` | Beat list | Map beats → `shot_1` / bridge `shot_2` |
| `dialogue_timeline` | Audio timing | Separate path — Kling Native Audio may embed audio in video |
| `runway_ui_map.json` | UI selectors | **Ready** — Strategy A / 2-shot P0 labels |
| `AUDIO_STRATEGY_ROUTER` | Audio class | Kling Native may be `music_only` or provider-native audio |
| Assembly / post | Final video | New `kling_clip_count × 15 s` duration gate |

**No duplicate story engines.** Extend Story Architect + new `kling_story_planner` module (future).

---

## 9. Example: 60 s / 4 clips (dragon egg)

| clip_index | Shot 1 (12 s) — main action | Shot 2 (3 s) — bridge |
|------------|----------------------------|------------------------|
| 1 | Boy discovers glowing egg in forest | Boy wraps egg, hears distant footsteps — **hold frame** |
| 2 | Boy hides behind log as travelers pass | Boy emerges, egg warmer — **hold frame** |
| 3 | Egg cracks, warm light leaks | Baby dragon stirs — **hold frame** |
| 4 | Boy bonds with hatchling | Boy runs deeper into trees clutching secret — **final hold** |

`next_clip_reference_hint` on clip 1 → feeds clip 2 Shot 1 prompt + first frame QA.

---

## 10. Validation Rules (future)

| Rule | Check |
|------|-------|
| Durations | `shot_1_duration == 12`, `shot_2_duration == 3`, `clip_duration == 15` |
| Prompts | Both non-empty; Shot 2 mentions bridge/hold language |
| Continuity | Clip N+1 has `prior_clip_index == N` when N > 1 |
| Last clip | `next_clip_reference_hint` may be empty or CTA-only |
| Count | `len(clips) == requested_duration / 15` |
| UI map | All labels resolve without generic selector warnings |

---

## 11. Deprecated / Superseded

| Item | Status |
|------|--------|
| Multishot Strategy B (5 × 3 s default) | **Deprecated** for story architecture |
| `shot_3_prompt`, `shot_4_prompt`, `shot_5_prompt` | Optional / legacy; not used in 2-shot continuity |
| `add_shot_button` automation for standard flow | **Not required** for 15 s clip |
| Prior validation doc default (Strategy B for fantasy) | **Replaced** by this document |

UI map labels for shots 3–5 remain for edge cases; standard pipeline uses **2 shots only**.

---

## 12. Implementation Roadmap (not started)

> **Superseded by:** [`KLING_FRAME_TO_VIDEO_ARCHITECTURE.md`](KLING_FRAME_TO_VIDEO_ARCHITECTURE.md) §9 for preferred path. Multishot items below = fallback track.

1. **Schema** — Add `kling_story_plan_v1` JSON schema under `project_brain/schemas/`.
2. **Planner** — `content_brain/story/kling_story_planner.py` (beats → clip plans).
3. **Validator** — `project_brain/validate_kling_story_plan.py`.
4. **UI binder** — Map plan fields → `runway_ui_map.json` labels (shadow-mode).
5. **Frame handoff** — Continuity module: extract final frame → upload first frame.
6. **Product Studio** — Restrict Kling duration to 15/30/45/60.

---

## 13. Open Questions

1. Should Shot 2 bridge always **freeze/hold** language for reliable frame extraction?
2. Is Kling Native Audio burned into the 15 s clip (no separate ElevenLabs path)?
3. Round-up vs hard reject for 20/25 s requests — channel profile default?

---

**Design complete. No code changes in this phase.**

**Related docs:**

- [`KLING_FRAME_TO_VIDEO_ARCHITECTURE.md`](KLING_FRAME_TO_VIDEO_ARCHITECTURE.md) — **preferred Frame-to-Video path**
- [`KLING_MULTISHOT_RELABEL_REPORT.md`](KLING_MULTISHOT_RELABEL_REPORT.md) — UI selectors (2-shot / 12+3 aligned)
- [`KLING_MULTISHOT_UI_MAP_VALIDATION_REPORT.md`](KLING_MULTISHOT_UI_MAP_VALIDATION_REPORT.md) — pre-relabel analysis (Strategy B sections superseded)
- [`PHASE_AUDIO_STRATEGY_ROUTER_DESIGN_REPORT.md`](PHASE_AUDIO_STRATEGY_ROUTER_DESIGN_REPORT.md) — audio routing (orthogonal)
