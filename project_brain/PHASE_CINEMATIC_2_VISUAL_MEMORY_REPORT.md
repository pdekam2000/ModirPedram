# PHASE CINEMATIC-2 — Visual Memory + Character Consistency Engine

**Status:** Complete  
**Date:** 2026-06-03  
**Scope:** Content Brain, Director Layer, Continuity Layer, Prompt Builder, Visual Memory, Results/Settings UI  
**Explicitly untouched:** Runway browser automation, Runway selectors, approval gates, provider router, upload system, Automation Center, branding runtime, music runtime

---

## Summary

PHASE CINEMATIC-2 adds persistent visual memory across multi-clip generation. Subject identity (lion, scorpion, cat, GPU, etc.) is extracted once, stored to disk, injected into every clip prompt, chained through upgraded seamless continuity, scored for consistency, and surfaced in Settings and Results.

**Success criteria met:** A lion in clip 1 prompts as the same lion in clips 2–3; scorpion and GPU subjects receive locked appearance profiles with cross-clip injection.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/director/visual_memory_store.py` | `VisualSubjectMemory` model + `VisualMemoryStore` persistence to `project_brain/visual_memory/run_<run_id>.json` |
| `content_brain/director/subject_memory_extractor.py` | Extract structured memory from story brief, director bundle, visual subject lock (lion/scorpion/cat/GPU profiles) |
| `content_brain/director/visual_memory_injector.py` | `VISUAL MEMORY LOCK` injection for clip 1 (establish) and clip 2+ (maintain) |
| `content_brain/director/scene_recall_engine.py` | Last-frame recall packages stored in `project_brain/runtime_state/scene_recall/` |
| `content_brain/director/consistency_score_engine.py` | 0–100 `visual_consistency_score` with five metric dimensions |
| `content_brain/director/visual_memory_pipeline.py` | Orchestrator: extract → continuity → inject → recall → score → persist |
| `project_brain/validate_visual_memory_v1.py` | 14-test validator |

---

## Files Modified

| File | Changes |
|------|---------|
| `content_brain/execution/seamless_continuity_engine.py` | v2: `CONTINUE EXACTLY FROM PREVIOUS FRAME`, visual memory-aware states, no jump cut / no subject replacement language |
| `content_brain/execution/runway_prompt_builder.py` | Wires `apply_visual_memory_pipeline()`; preserves continuity markers after cinematic expansion; adds `visual_memory_report` to bundle |
| `content_brain/platform/results_run_loader.py` | Loads `visual_memory_report` for Results panel; defensive empty history fix |
| `ui/api/schemas/product_studio.py` | `visual_memory` / `visual_memory_report` response fields |
| `ui/web/src/api/productClient.ts` | TypeScript types for visual memory panel |
| `ui/web/src/pages/ResultsPage.tsx` | Visual Memory panel: Subject, Memory PASS/FAIL, Consistency score, Continuity status |
| `ui/web/src/pages/SettingsPage.tsx` | Visual Memory Engine summary from latest run |
| `project_brain/validate_cinematic_runtime_v1.py` | Added `EXACT_FRAME_MARKER` continuity test |

---

## Memory Architecture

```
Story Brief + Director Layer + Visual Subject Lock
        │
        ▼
subject_memory_extractor.extract_subject_memory()
  • lion → dark mane, golden fur, scar above eye
  • scorpion → black exoskeleton, curved tail, pincers
  • cat → orange fur, green eyes
  • GPU → RTX-style, triple fan, black housing
        │
        ▼
VisualMemoryStore.save()
  → project_brain/visual_memory/run_<run_id>.json
        │
        ▼
seamless_continuity_engine v2 (with visual_memory context)
        │
        ▼
visual_memory_injector (VISUAL MEMORY LOCK per clip)
        │
        ▼
scene_recall_engine (per-clip recall packages)
  → project_brain/runtime_state/scene_recall/<run_id>/
        │
        ▼
consistency_score_engine → results panel payload
  → project_brain/runtime_state/visual_memory_report_<run_id>.json
        │
        ▼
cinematic_prompt_expander (markers preserved at prompt front)
```

### VisualSubjectMemory fields

**Identity:** `run_id`, `subject_name`, `subject_type`  
**Appearance:** `face_shape`, `eye_shape`, `eye_color`, `skin_color`, `fur_color`, `scale_color`, `markings`, `body_shape`, `clothing`, `accessories`  
**Environment:** `location`, `weather`, `lighting`, `color_palette`  
**Camera:** `camera_style`, `lens`, `framing`

---

## Continuity Architecture

**Engine version:** `seamless_continuity_engine_v2`

| Marker | Role |
|--------|------|
| `CONTINUE FROM PREVIOUS CLIP` | Cross-clip narrative continuity |
| `CONTINUE EXACTLY FROM PREVIOUS FRAME` | Frame-accurate pose/blocking continuation |
| `VISUAL MEMORY LOCK` | Subject identity freeze (colors, markings, proportions) |

**Maintained across clips:** subject identity, body position, camera direction, lighting, weather, scene composition  
**Forbidden:** jump cuts, subject replacement, environment reset, wardrobe swap

Scene recall packages add last-frame context: `subject_position`, `motion_direction`, `camera_angle`, `environment_state`, `lighting_state`, `emotional_state`.

---

## Consistency Scoring Architecture

**Version:** `consistency_score_engine_v1`  
**Pass threshold:** 70/100

| Metric | Weight |
|--------|--------|
| Subject consistency | 30% |
| Environment consistency | 20% |
| Color consistency | 15% |
| Camera consistency | 15% |
| Continuity consistency | 20% |

Output field: `visual_consistency_score` (0–100) plus per-metric breakdown and `pass` boolean.

**Sample scores from validation:**
- Multi-clip scorpion pipeline: **~78/100**
- Full prompt builder (3 clips): markers preserved, score attached to `visual_memory_report`

---

## Results / Settings Integration

**Results page panel displays:**
- Subject name + type
- Visual Memory: **PASS / FAIL**
- Consistency: **95/100** (example; actual score from pipeline)
- Continuity Status: **PASS / FAIL**
- Director-4 Vision Verifier readiness note

**Settings page:** Visual Memory Engine card with latest-run subject, memory status, consistency, and continuity from `fetchLatestResults()`.

---

## Future Vision Ready (Director-4)

Memory store includes:
- `vision_verifier_ready: true`
- `frame_analysis_hooks` with slots for `openai_vision_frame_analysis`, `character_recognition`, `director_4_vision_verifier`

Existing `content_brain/vision/visual_continuity_pipeline.py` remains the post-render frame verification path — memory architecture is designed to receive vision scores without schema changes.

---

## Validation Results

Command: `python project_brain/validate_visual_memory_v1.py`

| # | Test | Result |
|---|------|--------|
| 1 | Memory profile created | PASS |
| 2 | Memory stored to disk | PASS |
| 3 | Memory loaded correctly | PASS |
| 4 | Clip 2 receives memory injection | PASS |
| 5 | Clip 3 receives memory injection | PASS |
| 6 | Scene recall generated | PASS |
| 7 | Continuity upgrade active (v2 + EXACT FRAME) | PASS |
| 8 | Consistency score generated | PASS |
| 9 | Results panel receives score | PASS |
| 10 | Prompt builder integration | PASS |
| 11 | Results loader exposes memory | PASS |
| 12 | Runway automation untouched | PASS |
| 13 | Upload pipeline untouched | PASS |
| 14 | Branding/music pipeline untouched | PASS |

**Overall:** All visual memory v1 validations passed.

Cinematic v1 validator also passes with updated continuity marker tests.

---

## Next Recommended Phase

### PHASE CINEMATIC-3 — AI Director V2

Recommended focus:
- Shot planning graph with camera language nodes
- Cinematic shot types (establishing, insert, POV, rack focus)
- Beat-to-shot mapping with visual memory anchors
- Director-4 Vision Verifier integration using stored recall packages + frame analysis
