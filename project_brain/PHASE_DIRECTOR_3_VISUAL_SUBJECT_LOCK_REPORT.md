# Phase DIRECTOR-3 — Visual Subject Lock Report

## Root cause

The scorpion run (`cb_e2e_20260610_060527`) locked the **human presenter** (`Arachnologist`) as `Subject identity` instead of the **topic visual subject** (`black scorpion specimen`).

Continuity anchors covered human character, location, lighting, camera, and palette — but not:

- animal/object subject identity
- species/shape constraints
- required visible anatomy
- forbidden similar species (spider, crab, beetle)

Runway therefore received prompts where the authoritative on-screen subject was ambiguous, allowing spider-like drift while topic text remained scorpion-correct.

## Files changed

| File | Change |
|------|--------|
| `content_brain/director/visual_subject_lock.py` | **New** — `VisualSubjectLock` extraction + topic catalogs (scorpion, snake, ant, zander, spider) |
| `content_brain/director/director_models.py` | `DirectorLayerOutput.visual_subject_lock`, `PromptCriticReport.visual_subject_consistency_score`, `CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT` |
| `content_brain/director/director_pipeline.py` | Extract and store visual subject lock in director bundle |
| `content_brain/director/prompt_critic.py` | Score/reject visual subject drift; forbidden confusion checks |
| `content_brain/director/prompt_review_pipeline.py` | Pass visual subject lock into critic rescoring |
| `content_brain/execution/runway_prompt_builder.py` | Starter/clip prompt structure, continuity lock, strict negatives (`BUILDER_VERSION` → `runway_starter_to_video_f_v5`) |
| `project_brain/validate_visual_subject_lock.py` | **New** — 12-check validation suite |
| `project_brain/PHASE_DIRECTOR_3_VISUAL_SUBJECT_LOCK_REPORT.md` | **New** — this report |

**Not touched:** Runway automation, selectors, provider router, post-processing, ElevenLabs, assembly, publish package.

## Before / after — scorpion prompts

### Starter image

**Before (bad):**
```
Subject: Arachnologist
```

**After (good):**
```
Subject: a black scorpion in the foreground as the primary visual subject,
with Arachnologist observer / presenter only as an optional background observer.
Visual subject lock: The same black scorpion specimen remains the main on-screen subject
in every clip, always showing curved segmented tail, raised stinger, pincers, segmented exoskeleton, eight legs.
Forbidden confusions: no spider, no crab, no lobster, no generic insect, no beetle.
```

### Clip prompts

**Before (bad):**
```
Subject identity: Arachnologist
Continuity lock: same character (Arachnologist), same location ...
Strict negatives: no text, no subtitles ... no unrelated new characters entering frame.
```

**After (good):**
```
Subject identity: same black scorpion specimen with curved segmented tail, raised stinger, pincers, segmented exoskeleton.
Human role: Arachnologist observer / presenter. Do not make human the primary visual subject unless the user topic is a person.
Visual subject lock: The same black scorpion specimen remains the main on-screen subject in every clip ...
Continuity lock: same primary visual subject (black scorpion with curved segmented tail, raised stinger, pincers),
same species or object identity, same key anatomy and silhouette, same scale ...
Strict negatives: ... no spider, no crab, no lobster, no generic insect, no beetle.
```

## Validation results

```bash
python project_brain/validate_visual_subject_lock.py          # PASS
python project_brain/validate_topic_authority_end_to_end.py   # PASS
python project_brain/validate_director_layer_v2_prompt_critic.py  # PASS
```

Key checks:

1. Scorpion lock targets scorpion, not Arachnologist
2. Starter foregrounds scorpion
3. Clip `Subject identity` uses scorpion specimen language
4. Human presenter is secondary when present
5. Strict negatives include spider
6. All clips carry the same visual subject lock
7. Snake forbids lizard/worm/eel
8. Ant forbids termite/beetle/spider
9. Prompt Critic rejects missing visual subject lock (`visual_subject_drift`)
10. Topic authority validator still passes
11. Director V2 validator still passes
12. Runway automation files unchanged

## Runway automation confirmation

No changes to:

- `content_brain/execution/runway_ui_navigator.py`
- `content_brain/execution/runway_live_smoke_test.py`
- `content_brain/execution/runway_live_post_processor.py`
- `providers/runway_browser_provider.py`

Only Content Brain / Director / Prompt Builder prompt structure was modified.
