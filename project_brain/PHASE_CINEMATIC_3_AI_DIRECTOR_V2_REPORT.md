# PHASE CINEMATIC-3 — AI Director V2

**Status:** Complete  
**Date:** 2026-06-03  
**Scope:** Director Layer, Story Engine, Prompt Builder, Results UI  
**Explicitly untouched:** Runway browser automation, Runway selectors, provider router, upload center, automation center, branding runtime, music runtime

---

## Summary

PHASE CINEMATIC-3 upgrades multi-clip generation from repetitive visual clips to **directed cinematic sequences** with shot planning, camera language, a connected shot graph, visual rhythm scoring, and per-clip `DIRECTOR CAMERA PLAN` injection.

**Success criteria met:** A 3-clip video is planned as **establish world → build tension → reveal/payoff** (establishing_shot → tracking_shot → hero_shot) instead of three similar framings.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/director/shot_library.py` | 17 cinematic shot types with purpose, camera behavior, emotional effect, transitions |
| `content_brain/director/shot_planner.py` | Clip-count-aware shot sequences with topic category adjustments and anti-duplication |
| `content_brain/director/camera_language_engine.py` | Movement, lens, framing, composition by domain (wildlife/technology/history) |
| `content_brain/director/shot_graph_engine.py` | Connected visual graph → `shot_graph.json` in `project_brain/runtime_state/shot_graph/` |
| `content_brain/director/visual_rhythm_engine.py` | 0–100 `rhythm_score` penalizing repetitive framing/angles/movement |
| `content_brain/director/ai_director_v2_pipeline.py` | Orchestrator + `DIRECTOR CAMERA PLAN` prompt injection + results panel |
| `project_brain/validate_ai_director_v2.py` | 12-test validator |

---

## Files Modified

| File | Changes |
|------|---------|
| `content_brain/execution/runway_prompt_builder.py` | v7: wires `apply_ai_director_v2()` after visual memory; preserves camera plan markers after expansion; adds `ai_director_v2_report` |
| `content_brain/platform/results_run_loader.py` | Loads `ai_director_v2_report` for Results |
| `ui/api/schemas/product_studio.py` | Response fields for AI Director V2 |
| `ui/web/src/api/productClient.ts` | TypeScript types |
| `ui/web/src/pages/ResultsPage.tsx` | AI Director V2 panel: shot plan, rhythm score, shot graph status, camera language |

---

## Shot Library (17 types)

`establishing_shot`, `wide_shot`, `medium_shot`, `close_up`, `extreme_close_up`, `tracking_shot`, `dolly_in`, `dolly_out`, `orbit_shot`, `over_shoulder`, `reveal_shot`, `hero_shot`, `cinematic_pan`, `low_angle`, `high_angle`, `aerial_shot`, `macro_detail`

Each entry includes: **purpose**, **camera behavior**, **emotional effect**, **recommended transitions**.

---

## Shot Planning Architecture

**Default 3-clip arc:**

| Clip | Shot | Narrative role |
|------|------|----------------|
| 1 | `establishing_shot` | Establish world |
| 2 | `tracking_shot` | Build tension |
| 3 | `hero_shot` | Reveal / payoff |

**Topic-aware adjustments:**
- **Wildlife:** telephoto documentary tracking, hero/reveal finales
- **Technology:** wide product establish, macro detail mid-beat, reveal finale
- **History:** slow dramatic dolly push-in

**Anti-spam:** adjacent duplicate shot types are replaced automatically.

---

## Camera Language Engine

Generates per-clip:

- Camera movement
- Lens selection
- Framing
- Composition
- Visual objective

Injected into prompts as:

```
DIRECTOR CAMERA PLAN. Shot type: … Camera movement: … Lens: … Composition: … Framing: … Visual objective: …
```

---

## Shot Graph Architecture

```
ShotPlan + CameraLanguagePlan
        │
        ▼
build_shot_graph()
  • nodes: clip order, shot type, transition, emotion, pacing
  • edges: transition links between clips
  • pacing_curve: open → build → payoff
        │
        ▼
ShotGraphStore.save()
  → project_brain/runtime_state/shot_graph/<run_id>/shot_graph.json
```

---

## Visual Rhythm Scoring

**Version:** `visual_rhythm_engine_v1`  
**Pass threshold:** 65/100

| Component | Weight |
|-----------|--------|
| Framing variety | 30% |
| Angle variety | 20% |
| Movement variety | 30% |
| Pacing variety | 20% |

Penalties for adjacent duplicate shot types and movement patterns.

**Sample:** 3-clip wildlife plan scores **100/100** rhythm in validation.

---

## Prompt Pipeline Order

```
base clip prompts
  → visual memory pipeline (CINEMATIC-2)
  → AI Director V2 (shot plan + camera language injection)
  → cinematic prompt expansion (markers preserved)
  → optional prompt critic
```

Visual memory and continuity markers remain intact after Director V2.

---

## Results UI

**AI Director V2 panel displays:**
- Shot plan summary (clip → shot type → scene progression)
- Rhythm score (0–100)
- Shot graph status (PASS/FAIL)
- Camera language per clip (lens + movement)

---

## Validation Results

Command: `python project_brain/validate_ai_director_v2.py`

| # | Test | Result |
|---|------|--------|
| 1 | Shot library loads | PASS |
| 2 | Shot planner generates sequence | PASS |
| 3 | No duplicate shot spam | PASS |
| 4 | Camera language generated | PASS |
| 5 | Shot graph created | PASS |
| 6 | Rhythm score generated | PASS |
| 7 | Prompt builder receives camera plan | PASS |
| 8 | Results receives director data | PASS |
| 9 | Visual memory unaffected | PASS |
| 10 | Continuity unaffected | PASS |
| 11 | Runway automation untouched | PASS |
| 12 | Upload untouched | PASS |

Prior validators (`validate_visual_memory_v1`, `validate_cinematic_runtime_v1`) also pass.

---

## Next Recommended Phase

**PHASE CINEMATIC-4** — Director-4 Vision Verifier integration: frame analysis against shot graph + visual memory locks using stored recall packages and OpenAI Vision.
