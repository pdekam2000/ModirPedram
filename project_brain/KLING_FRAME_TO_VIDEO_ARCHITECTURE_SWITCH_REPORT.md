# Kling Frame-to-Video Architecture Switch — Report

**Phase:** `KLING-FRAME-TO-VIDEO-ARCHITECTURE-SWITCH`  
**Status:** COMPLETE (design + P0 schema + P2 planner foundation)  
**Date:** 2026-06-17  
**No Generate. No credits.**

---

## 1. Decision

Kling **Frame-to-Video Native Audio** is now the **preferred** cinematic story mode.

Kling **Multishot (12+3)** remains as **fallback / legacy**.

---

## 2. Why

| Limitation (Multishot) | Frame-to-Video advantage |
|------------------------|--------------------------|
| ~512 chars × 2 prompts | **~2500 chars** single rich prompt |
| Split shot_1 / shot_2 | Unified story + camera + audio cues |
| Limited dialogue detail | Full dialogue, ambience, foley, movement sound |
| Bridge-only continuity text | first + optional **end frame** upload |

---

## 3. Deliverables

| # | Deliverable | Path | Status |
|---|-------------|------|--------|
| 1 | Architecture doc | `project_brain/KLING_FRAME_TO_VIDEO_ARCHITECTURE.md` | Done |
| 2 | Story design updated | `project_brain/KLING_STORY_ARCHITECTURE_DESIGN.md` | Done |
| 3 | GUI design updated | `project_brain/KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md` | Done |
| 4 | Schema models (P0) | `content_brain/execution/kling_frame_to_video_models.py` | Done |
| 5 | Frame planner (P2) | `content_brain/execution/kling_frame_to_video_planner.py` | Done |
| 6 | Validation | `project_brain/validate_kling_frame_architecture_switch.py` | Done |

---

## 4. Provider modes

| Mode | ID |
|------|-----|
| Preferred | `kling_frame_to_video_native_audio` |
| Fallback | `kling_multishot_native_audio` |

Auto selection via `select_kling_generation_mode()` — cinematic / dialogue / fantasy / emotional content → frame mode; unavailable UI → multishot.

---

## 5. Per-clip schema (planner output)

Each clip includes:

- `duration_seconds: 15`
- `first_frame_source`, `end_frame_source`
- `prompt` (max **2500**, target **1200–1800**)
- `character_continuity`, `environment_continuity`
- `dialogue`, `native_audio_directives`
- `camera_direction`, `continuity_anchor`, `next_clip_reference_hint`

---

## 6. Continuity rule (design)

```
Clip N → generate 15s → extract last frame
Clip N+1 → first_frame = prior last frame → rich prompt → optional end_frame
```

Reuses existing `kling_last_frame_extractor.py` and `kling_continuity_runtime.py` (P6 adaptation).

---

## 7. Implementation roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| P0 | Schema + mode constants | **Done** |
| P1 | UI mapper labels (first/end frame, frame prompt) | Pending |
| P2 | Frame planner | **Done** |
| P3 | Preflight API | Pending |
| P4 | Live dry-run | Pending |
| P5 | Approval-gated live generation | Pending |
| P6 | Continuity chain for frame mode | Pending |

---

## 8. Validation

```bash
python project_brain/validate_kling_frame_architecture_switch.py
```

**All checks passed**, including:

- Frame mode documented as preferred  
- Multishot remains fallback  
- Provider mode names defined  
- Planner schema complete  
- Continuity rule documented  
- Prompt max 2500 documented  
- No Generate / credits in new modules  
- Existing multishot schema + validation scripts unchanged  

---

## 9. Not changed (by design)

- `kling_multishot_live_engine.py` — still fallback execution  
- `kling_native_audio_planner.py` — still multishot planner  
- Product Studio generate path — still multishot until P3–P5  
- Runway Phase I — unchanged  

---

## 10. Next phase

**P1 UI Mapper labels** — map Frame-to-Video controls (`first_frame_upload`, `end_frame_upload`, rich prompt field, 15s duration, audio on) without clicking Generate.
