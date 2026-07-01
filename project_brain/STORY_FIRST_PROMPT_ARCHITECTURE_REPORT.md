# Story-First Prompt Architecture — Report

**Phase:** STORY-FIRST-PROMPT-ARCHITECTURE  
**Status:** IMPLEMENTED — validation PASS  
**Date:** 2026-06-03

---

## Problem

Kling Frame-to-Video prompts were metadata-heavy (`Character continuity:`, `Environment continuity:`, etc.) with thin story content, using ~1300–1800 chars of the 2500-char capacity.

---

## Solution

New engine: `content_brain/story/story_first_prompt_engine.py`

Story-first composition:
1. **Story body (≥80% target)** — narrative paragraphs covering scene, behavior, emotion, dialogue, environment, conflict, progression, context, sensory detail
2. **Technical footer (≤20%)** — appended after `--- Technical execution ---` with visual style, audio style, camera style, continuity anchor only

Planner v2 (`kling_frame_to_video_planner_v2_story_first`) delegates all frame prompts to `compose_story_first_frame_prompt()`.

---

## Rules Enforced

| Rule | Value |
|------|-------|
| Hard minimum | 2000 chars — **fail validation** |
| Recommended minimum | 2300 chars |
| Target range | 2400–2500 chars |
| Story ratio target | ≥ 80% |
| Technical ratio target | ≤ 20% |
| Generation fail floor | story_percent < 70% |

---

## Prompt Audit Output

`audit_story_first_prompt()` / `story_first_audit` on clip previews:

| Field | Description |
|-------|-------------|
| `story_percent` | Story body character share |
| `technical_percent` | Technical footer share |
| `character_count` | Total prompt length |
| `dialogue_density` | Quoted dialogue words / total words |
| `emotion_density` | Emotion token hits / total words |
| `prompt_length` | Same as character_count |
| `ok` | Passes hard min + 70% story floor |

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/story/story_first_prompt_engine.py` | **New** — compose, audit, validate |
| `content_brain/execution/kling_frame_to_video_planner.py` | Story-first compose + validation |
| `content_brain/execution/kling_frame_to_video_models.py` | Target constants → 2400–2500 |
| `content_brain/execution/kling_product_run.py` | Fail generate if story-first validation fails |
| `project_brain/validate_story_first_prompt_architecture.py` | Validation suite |
| `project_brain/validate_kling_frame_architecture_switch.py` | Updated length expectations (2400–2500) |
| `project_brain/validate_story_progression_engine_p5.py` | Story-first continuity assertions |

---

## Validation Results

```bash
python project_brain/validate_story_first_prompt_architecture.py
python project_brain/validate_kling_frame_architecture_switch.py
python project_brain/validate_story_progression_engine_p5.py
python project_brain/validate_product_studio_default_kling_ux.py
```

All four suites **PASS**.

Sample audit (30s robot dog topic, clip 1):

| Metric | Value |
|--------|-------|
| `prompt_length` | 2495 |
| `story_percent` | 83.61% |
| `technical_percent` | 15.23% |
| `dialogue_density` | computed from quoted lines |
| `emotion_density` | computed from emotion tokens |
| generation validation | PASS |

Clip 2 handoff language includes `continuing immediately from` plus `resumes without reset` for frame continuity.

---

## Generation Gate

`run_kling_product_studio_generate()` validates frame plan via `validate_kling_frame_content_plan()` before starter frame / live runtime. Returns `status: failed` with `story_first_audits` if story_percent < 70% or prompt < 2000 chars.

---

## Architecture Notes

- Multishot prompts unchanged (512 char shot limit)
- Story progression engine still supplies chapter metadata fed into narrative paragraphs
- Technical metadata labels removed from story body; continuity preserved in prose + technical footer anchor
