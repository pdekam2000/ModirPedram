# Kling Frame-to-Video Native Audio — Architecture

**Phase:** `KLING-FRAME-TO-VIDEO-ARCHITECTURE-SWITCH`  
**Status:** Design + P0 schema / P2 planner foundation  
**Date:** 2026-06-17  
**Authority:** Preferred cinematic path for Kling Native Audio story generation

---

## 1. Executive decision

**Kling Frame-to-Video Native Audio** is now the **preferred** mode for cinematic story generation.

**Kling Multishot (2-shot 12+3)** remains supported as **fallback / legacy**.

| Mode | Prompt budget | Frame control | Use when |
|------|---------------|---------------|----------|
| **Frame-to-Video** (preferred) | **~2500 chars** | first + optional end frame | cinematic, dialogue, fantasy, emotional, animal scenes |
| Multishot (fallback) | ~512 chars × 2 shots | first frame only | frame mode unavailable, legacy runs, simple beats |

---

## 2. Why Frame-to-Video is preferred

Multishot splits story into two ~512-char prompts (Shot 1 + Shot 2). That is too small for:

- detailed character description  
- exact story action + dialogue  
- emotional tone + environment sound + movement sound  
- camera direction + continuity instruction  
- ending frame target + cinematic audio cues  

Frame-to-Video uses **one rich prompt per 15s clip** (target 1200–1800 chars, max 2500) plus:

- **first_frame upload** (continuity from prior clip)  
- **end_frame upload** when available (optional target frame)  
- **native audio on**  
- **~15s output** per clip  

---

## 3. Architecture comparison

### Current (Multishot — fallback)

```
Story
  ↓
Kling 2-shot multishot planner
  ↓
shot_1_prompt (~512)
shot_2_prompt (~512)
  ↓
Runway Multishot UI (12s + 3s)
```

### Preferred (Frame-to-Video)

```
Story
  ↓
Kling Frame Story Planner
  ↓
clip_prompt_2500
  ↓
first_frame (+ optional end_frame)
  ↓
Kling Frame-to-Video UI
  ↓
~15s native-audio MP4
```

---

## 4. Per-clip unit (Frame-to-Video)

| Field | Value |
|-------|-------|
| Duration | **15s** |
| Prompt max | **2500 chars** |
| Prompt target | **1200–1800 chars** |
| First frame | user upload (clip 1) or prior clip last frame |
| End frame | optional generated/selected target |
| Audio | Kling native in-video |

---

## 5. Continuity rule (unchanged intent, new mode)

```
Clip 1: starter / generated first frame
   ↓ generate ~15s
   ↓ extract last frame → continuity/frame_c1.png
Clip 2: first_frame = frame_c1.png
        optional end_frame target
        prompt = next story beat (rich)
   ↓ repeat for 30/45/60s
```

| Clip | first_frame_source | end_frame_source |
|------|-------------------|------------------|
| 1 | `user_upload` | `generated_target_frame` or `none` (last clip) |
| N>1 | `prior_clip_final_frame` | optional target / `none` on final clip |

Reuse existing:

- `kling_last_frame_extractor.py`  
- `kling_continuity_runtime.py` (adapt for frame mode in P6)

---

## 6. Provider modes

| Mode ID | Role |
|---------|------|
| `kling_frame_to_video_native_audio` | **Preferred** cinematic path |
| `kling_multishot_native_audio` | **Fallback** — existing multishot live engine |

Base provider remains `kling_3_0_pro_native_audio`. Mode selects **UI surface + planner**, not a different Runway subscription product.

### Auto selection (design)

For cinematic story / dialogue / fantasy / animal / emotional scenes → **frame mode**.

If frame UI labels unavailable → **multishot fallback**.

Implementation: `select_kling_generation_mode()` in `kling_frame_to_video_models.py`.

---

## 7. Content Brain schema (P0)

**Module:** `content_brain/execution/kling_frame_to_video_models.py`

**Planner:** `content_brain/execution/kling_frame_to_video_planner.py`

### Per-clip plan

```json
{
  "clip_index": 1,
  "duration_seconds": 15,
  "first_frame_source": "user_upload",
  "end_frame_source": "generated_target_frame",
  "prompt": "… up to 2500 chars …",
  "character_continuity": "…",
  "environment_continuity": "…",
  "dialogue": "…",
  "native_audio_directives": { "dialogue_lines": [], "ambience": [], "foley": [] },
  "camera_direction": "…",
  "continuity_anchor": "…",
  "next_clip_reference_hint": "…"
}
```

### Package level

```json
{
  "version": "kling_frame_to_video_plan_v1",
  "provider_mode": "kling_frame_to_video_native_audio",
  "fallback_mode": "kling_multishot_native_audio",
  "clip_count": 2,
  "prompt_max_chars": 2500,
  "clips": []
}
```

---

## 8. UI impact (future — design only this phase)

Product Studio will eventually expose:

**Kling Mode:** Auto | Frame-to-Video (recommended) | Multishot

Not wired in this phase unless safe. Existing Multishot Product Studio path unchanged.

---

## 9. Implementation roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **P0 Schema** | `kling_frame_to_video_models.py`, mode constants, validation | **Done (this phase)** |
| **P1 UI Mapper labels** | `first_frame_upload`, `end_frame_upload`, `frame_prompt`, duration 15s, audio on | Not started |
| **P2 Frame planner** | `kling_frame_to_video_planner.py` | **Done (this phase)** |
| **P3 Preflight API** | Expose `kling_frame_to_video_plan` in Product Studio preflight | Not started |
| **P4 Live dry-run** | Prepare UI without Generate | Not started |
| **P5 Approval-gated live generation** | Frame mode live engine + CDP download | Not started |
| **P6 Continuity chain** | Extend continuity runtime for frame mode + end frame | Not started |

**Hard rule until P5:** No Generate, no credits in validation phases.

---

## 10. Parallel paths (no removal)

| System | Status |
|--------|--------|
| `kling_native_audio_planner.py` | **Retained** — multishot fallback |
| `kling_multishot_live_engine.py` | **Retained** — legacy/fallback execution |
| `kling_continuity_runtime.py` | **Retained** — adapt in P6 |
| Runway Phase I | **Unchanged** |

---

## 11. Related documents

| Document | Update |
|----------|--------|
| [`KLING_STORY_ARCHITECTURE_DESIGN.md`](KLING_STORY_ARCHITECTURE_DESIGN.md) | Multishot marked fallback |
| [`KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md`](KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md) | Frame mode selector noted |
| [`KLING_CONTINUITY_CHAIN_V1_REPORT.md`](KLING_CONTINUITY_CHAIN_V1_REPORT.md) | Continuity mechanics reused |

---

## 12. Validation

```bash
python project_brain/validate_kling_frame_architecture_switch.py
python project_brain/validate_kling_native_audio_schema_p0.py
python project_brain/validate_kling_native_audio_content_planner_p3.py
```

No Generate. No credits.
