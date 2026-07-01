# Video Learning Loop — Design

**Phase:** `VIDEO-QUALITY-JUDGE-AI` (companion to Video Judge)  
**Status:** Design only — no implementation  
**Date:** 2026-06-16  

---

## 1. Purpose

Close the loop:

```text
Generate Video → Judge scores deliverable → Feedback → Content Brain adjusts → Next run improves
```

Without manual review every time, the system learns:

- **What works** → reinforce (gold references)
- **What fails** → suppress (anti-pattern references)
- **What generates higher quality** → channel-specific weight tuning

---

## 2. Current State vs Target

| Capability | Today | After learning loop |
|------------|-------|---------------------|
| Pre-run quality | `QualityAuditV2`, viral scoring | Unchanged — plans still audited pre-run |
| Post-run quality | Delivery gate only | **Video Judge** holistic score |
| Feedback storage | Scattered warnings in manifests | **`video_quality_judge.json` + learning state** |
| Next-run adjustment | Manual prompt edits | **Automatic weight deltas** from `improvement_actions` |
| Channel memory | Topic memory, voice registry | **+ quality preference profile** |

---

## 3. Learning Loop Architecture

```text
┌─────────────────┐
│ Video Judge     │
│ (post-run)      │
└────────┬────────┘
         │ VideoQualityJudgeResult
         ▼
┌─────────────────┐
│ Learning        │
│ Interpreter     │  maps weaknesses → action_ids → deltas
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Channel Quality │  persisted per channel / niche
│ Profile Store   │  project_brain/runtime_state/channel_quality_learning.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Content Brain   │  reads weights on next preflight/generate
│ Weight Applier  │
└────────┬────────┘
         │
         ▼
   Next generation with adjusted emphasis
```

---

## 4. Trigger Conditions

### 4.1 When learning applies

| Condition | Action |
|-----------|--------|
| `overall_score < threshold` (default 70) | Apply **corrective** deltas from `improvement_actions` |
| `overall_score ≥ 85` | Apply **reinforcement** deltas from strengths |
| `50 ≤ score < 70` | Mild corrective + log for review |
| Judge failed / no video | Skip learning; log `learning_skipped:no_deliverable` |

### 4.2 Cooldown & safety

- **Max delta per run:** ±0.15 per weight dimension (prevent oscillation)
- **Cooldown:** same `action_id` not applied more than once per 3 runs
- **Rollback:** channel profile stores `learning_history[]` with undo pointer
- **Manual override:** Settings → “Reset quality learning” clears store

---

## 5. Improvement Action → Content Brain Mapping

Each `improvement_action` from the judge targets an existing Content Brain subsystem:

| action_id | Trigger phrase (examples) | Target module | Weight key |
|-----------|---------------------------|---------------|------------|
| `boost_dialogue_emphasis` | dialogue too weak, flat narration | `dialogue_engine`, `dialogue_naturalization_engine` | `dialogue_weight` |
| `increase_environment_weight` | environment audio excellent | `environment_designer`, `environment_presence_engine` | `ambience_weight` |
| `strengthen_hook` | weak opening, slow start | `hook_engineering_engine`, story blueprint hook | `hook_weight` |
| `improve_pacing` | dragging middle, abrupt ending | `story_architect`, `duration_planner` | `pacing_tightness` |
| `boost_emotional_arc` | flat emotions | `emotion_engine`, `story_emotion_engine` | `emotion_weight` |
| `improve_visual_continuity` | character drift, inconsistent subject | `visual_continuity_pipeline`, shot planner | `continuity_strictness` |
| `increase_cinematic_language` | generic visuals | `ai_director_v2`, prompt cleanup | `cinematic_prompt_weight` |
| `boost_native_audio_cues` | weak Kling native audio | `kling_native_audio_planner` | `native_audio_cue_density` |
| `reduce_generic_story_beats` | repetitive structure | `story_strategy_library`, uniqueness engine | `uniqueness_weight` |
| `increase_viral_retention` | low retention/shareability | `viral_scoring_engine`, retention map | `retention_weight` |

### 5.1 Example flows (from user requirements)

**Weak dialogue:**

```text
Judge weakness: "dialogue too weak"
  → action: boost_dialogue_emphasis (+0.15 dialogue_weight)
  → next run: dialogue_engine produces longer, more emotional lines
  → narrator timeline gets denser speech cues
```

**Strong environment:**

```text
Judge strength: "environment audio excellent"
  → action: increase_environment_weight (+0.10 ambience_weight)
  → next run: environment_designer adds layers; prompts include ambience keywords
```

---

## 6. Channel Quality Profile Store

**Path (future):** `project_brain/runtime_state/channel_quality_learning.json`

```json
{
  "version": "channel_quality_learning_v1",
  "channel_id": "default",
  "updated_at": "2026-06-16T22:55:00Z",
  "threshold": 70,
  "weights": {
    "dialogue_weight": 1.15,
    "ambience_weight": 1.10,
    "hook_weight": 1.0,
    "emotion_weight": 1.0,
    "continuity_strictness": 1.05,
    "cinematic_prompt_weight": 1.0,
    "native_audio_cue_density": 1.0,
    "uniqueness_weight": 1.0,
    "retention_weight": 1.0
  },
  "baseline_weights": { "...": 1.0 },
  "learning_history": [
    {
      "run_id": "cb_e2e_20260616_225212",
      "overall_score": 68,
      "actions_applied": ["boost_dialogue_emphasis"],
      "deltas": { "dialogue_weight": +0.15 },
      "applied_at": "2026-06-16T22:56:00Z"
    }
  ],
  "gold_reference_run_ids": ["run_abc123"],
  "anti_pattern_run_ids": ["run_xyz789"],
  "stats": {
    "judged_run_count": 12,
    "average_overall_score": 71.4,
    "last_5_average": 74.2
  }
}
```

All weights default to **1.0**; applied as multipliers in Content Brain modules.

---

## 7. Weight Applier Integration Points

Read `channel_quality_learning.weights` at:

| Stage | Module | Effect |
|-------|--------|--------|
| Story planning | `build_story_blueprint` | hook/conflict emphasis |
| Dialogue | `build_dialogue_plan` | line count, emotional intensity |
| Environment | `build_environment_plan` | layer count, ambience tokens |
| Prompt build | `content_brain_prompt_cleanup` | cinematic / ambience token density |
| Kling planner | `kling_native_audio_planner` | native audio cue phrases in shot prompts |
| Audio router | `audio_strategy_router` | soft bias only if repeated anti-patterns (v2) |
| Director | `ai_director_v2` | shot diversity vs continuity strictness |

**Rule:** Learning adjusts **emphasis**, never bypasses safety gates (topic authority, delivery gate, approval gate).

---

## 8. Reference Library (Gold & Anti-Pattern)

### 8.1 Promotion rules

| Library | Entry condition | Used for |
|---------|-----------------|----------|
| **Gold** | `overall_score ≥ 85` AND delivery PASS | Few-shot “do this” examples in judge + planner prompts |
| **Anti-pattern** | `overall_score < 50` OR same weakness in 3 consecutive runs | Few-shot “avoid this” examples |

### 8.2 Storage layout

```text
project_brain/video_reference_library/
  gold/
    {run_id}/
      judge.json
      keyframes/
      story_package_snapshot.json
      prompt_snapshot.json
  anti/
    {run_id}/
      judge.json
      keyframes/
      failure_summary.txt
```

### 8.3 Retrieval (future)

`ReferenceLibrarySelector` picks top-k gold + anti entries by:

- niche match
- provider match (`runway` vs `kling_native_audio`)
- audio_strategy match

Injected into Content Brain as **compact context blocks** (not full video upload every run).

---

## 9. Results Page — Learning Visibility

Extend Results (see Video Judge design) with:

| Field | Source |
|-------|--------|
| Video Judge Score | `overall_score` |
| Overall Rating | GREAT / GOOD / NEEDS WORK / POOR |
| Improvement Suggestions | `improvement_actions` |
| **Learning Applied** | last `learning_history[-1]` |
| **Quality Trend** | sparkline from last 5 `overall_score` |

Optional badge: “Content Brain will emphasize dialogue +15% next run” when corrective action applied.

---

## 10. API Surface (Future)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/product/results/latest` | GET | includes `video_quality_judge` block |
| `/product/runs/{run_id}/judge` | POST | re-run judge |
| `/product/channel-quality-learning` | GET/DELETE | view / reset learning state |

---

## 11. Observability

Log events to run metadata:

| Event | Payload |
|-------|---------|
| `video_judge_completed` | scores, confidence |
| `learning_actions_applied` | deltas, action_ids |
| `learning_skipped` | reason |
| `reference_promoted` | gold or anti, run_id |

Runtime Dashboard (existing) can add read-only panel via `panel_extractor` extension — **no new dashboard page**.

---

## 12. Compatibility

| System | Impact |
|--------|--------|
| Runway pipeline | Hook after post-processor; no change to Generate |
| Kling pipeline | Hook in `kling_product_run` after clip completion |
| ElevenLabs | Learning may boost dialogue; does not disable provider |
| Delivery gate | Independent — learning never bypasses integrity FAIL |
| Manual operator edits | Learning deltas composable with manual channel profile |

---

## 13. Validation Plan (Future)

**Script:** `project_brain/validate_video_quality_judge.py`

| Test | Assert |
|------|--------|
| Judge output schema | all score fields 0–100 |
| Weak dialogue → action | `boost_dialogue_emphasis` present |
| Strong environment → action | `increase_environment_weight` present |
| Score below threshold | learning interpreter produces deltas |
| Score above 85 | gold reference candidate flagged |
| Weight cap | delta ≤ 0.15 per dimension |
| Runway narrator run | unchanged generate path |
| Results loader | judge block present when JSON exists |

**Script:** `project_brain/validate_video_learning_loop.py`

| Test | Assert |
|------|--------|
| Apply learning | weights updated in store |
| Cooldown | duplicate action blocked within 3 runs |
| Reset | baseline restored |
| Content Brain read | dialogue_weight affects dialogue plan length proxy |

---

## 14. Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| **LEARN-P0** | `channel_quality_learning.json` schema + interpreter (no UI) |
| **LEARN-P1** | Weight applier in dialogue + environment modules |
| **LEARN-P2** | Results page learning visibility |
| **LEARN-P3** | Gold/anti reference library + retrieval |
| **LEARN-P4** | Trend analytics + optional hard gate linkage |

Depends on: **JUDGE-P0** (schema + rules judge) minimum.

---

## 15. Success Metrics

| Metric | Target (90 days post-launch) |
|--------|------------------------------|
| Average `overall_score` trend | +5 pts vs first 10 runs |
| Repeated weakness rate | −30% for top-3 weakness tags |
| Manual re-edit rate | −20% (operator prompt tweaks) |
| Gold library size | ≥5 runs per active channel |

---

## 16. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Oscillating weights (dialogue up → visuals down) | per-dimension caps + cooldown |
| LLM judge hallucination | hybrid mode + deterministic caps |
| Overfitting to one viral outlier | require ≥2 gold runs before strong reinforcement |
| Kling vs Runway metric mismatch | provider-aware judge rubric |

---

**Primary doc:** [`VIDEO_QUALITY_JUDGE_DESIGN.md`](VIDEO_QUALITY_JUDGE_DESIGN.md)

**Next recommended implementation phase:** `VIDEO-QUALITY-JUDGE-P0` (rules-only judge + schema + persistence)
