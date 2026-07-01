# Story Progression Engine P5 — Report

**Phase:** `STORY-PROGRESSION-ENGINE-P5`  
**Status:** IMPLEMENTED — validation PASS  
**Date:** 2026-06-03

---

## 1. Goal

Guarantee true story arc progression across Frame-to-Video clip chapters. Continuity preserves characters and environment; each clip must advance action, emotion, and stakes — never repeat the previous clip.

---

## 2. Chapter System

| Duration | Chapters |
|----------|----------|
| 15s | Hook |
| 30s | Hook → Payoff |
| 45s | Hook → Escalation → Resolution |
| 60s | Hook → Escalation → Conflict → Resolution |
| 75s | Hook → Escalation → Conflict → Twist → Resolution |
| 90s | Hook → Escalation → Conflict → Twist → Climax → Resolution |

---

## 3. Component Delivered

`content_brain/story/story_progression_engine.py`

| Function | Purpose |
|----------|---------|
| `build_story_progression_plan()` | Build full chapter arc for a story duration |
| `chapter_roles_for_clip_count()` | Map clip count → role sequence |
| `validate_story_progression_plan()` | Verify roles, conflict rise, resolution last |
| `story_chapter_for_clip()` | Display label helper (used by Use Frame runtime) |

Per-clip output schema:

```json
{
  "clip_index": 1,
  "chapter_role": "hook",
  "chapter_label": "Hook",
  "story_objective": "...",
  "emotion": "curiosity and intrigue",
  "conflict_level": 1,
  "camera_style": "...",
  "dialogue_goal": "...",
  "next_chapter_hint": "...",
  "visual_progression": "..."
}
```

---

## 4. Prompt Integration

`kling_frame_to_video_planner.py` now:

1. Calls `build_story_progression_plan()` before clip planning
2. Injects chapter role, story objective, emotional state, conflict level, visual progression, and next chapter hint into every Frame-to-Video prompt
3. Stores `chapter_progression` on each clip and `story_progression` on the plan
4. Clip 2+ prompts include explicit **"Do not repeat the previous clip's action"** language

Character continuity rules enforced in prompts:

- **Preserved:** identity, appearance, core environment
- **May change:** emotion, location depth, camera, action, stakes

---

## 5. Wiring

| System | Integration |
|--------|-------------|
| `kling_use_frame_runtime.py` | Delegates `story_chapter_for_clip` to progression engine |
| `kling_native_audio_planner.py` | Preflight includes `story_progression` + validation status |
| `kling_product_run.py` | Results loader exposes `story_progression` |
| `product_studio_service.py` | Results API passes progression to UI |
| `ResultsPage.tsx` | Shows per-clip chapters + PASS/FAIL status |

---

## 6. Validation

`project_brain/validate_story_progression_engine_p5.py` — **all checks PASS**:

1. 15s → 1 chapter  
2. 30s → 2 chapters  
3. 45s → 3 chapters  
4. 60s → 4 chapters  
5. 75s → 5 chapters  
6. 90s → 6 chapters  
7. Chapter roles never duplicate incorrectly  
8. Conflict increases before resolution  
9. Resolution (or Payoff for 30s) appears last  
10. Frame planner consumes progression data in prompts  
11. Character/environment continuity preserved  
12. Multishot pipeline unaffected  

Run:

```bash
python project_brain/validate_story_progression_engine_p5.py
```

---

## 7. Relationship to Existing Systems

`visual_story_progression_engine.py` remains for Runway visual orchestration (discovery/escalation/reward). The new `story_progression_engine.py` is the **Kling Frame-to-Video chapter arc** system with duration-specific roles (hook through resolution). No duplicate runtime path created.

---

## 8. Success Criteria

| Criterion | Status |
|-----------|--------|
| 60s story has distinct Hook/Escalation/Conflict/Resolution chapters | **PASS** (validated) |
| Prompts include chapter progression fields | **PASS** |
| Clips instructed not to repeat prior action | **PASS** |
| Results page shows chapter breakdown | **Implemented** |
| Multishot unchanged | **Verified** |

A 60-second Frame-to-Video story now plans four advancing chapters with rising conflict, not four connected repeats of the same beat.
