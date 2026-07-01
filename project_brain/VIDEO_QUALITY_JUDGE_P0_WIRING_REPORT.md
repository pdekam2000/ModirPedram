# Video Quality Judge P0 Wiring — Report

**Phase:** `VIDEO-QUALITY-JUDGE-P0-WIRING`  
**Status:** Implemented  
**Date:** 2026-06-16  

---

## 1. Files Modified

| File | Change |
|------|--------|
| `content_brain/quality/video_quality_judge.py` | Added `build_judge_context_from_run_dir`, `run_post_processing_quality_pipeline` |
| `content_brain/quality/__init__.py` | Export wiring helper |
| `content_brain/execution/runway_live_post_processor.py` | Run judge + learning after delivery gate |
| `content_brain/execution/kling_product_run.py` | Run judge + learning after successful Kling generation; expose in results loader |
| `content_brain/platform/results_run_loader.py` | Load `quality/video_quality_judge.json` + learning proposed flag |
| `ui/api/product_studio_service.py` | Merge Kling judge payload into results API |
| `ui/api/schemas/product_studio.py` | `video_quality_judge`, `video_quality_learning_proposed` fields |
| `ui/web/src/api/productClient.ts` | Results types for judge + fixed `cinematic_audio` type block |
| `ui/web/src/pages/ResultsPage.tsx` | Video Quality Judge section |

## Files Created

| File | Purpose |
|------|---------|
| `project_brain/validate_video_quality_judge_p0_wiring.py` | Wiring validation (10 tests) |
| `project_brain/VIDEO_QUALITY_JUDGE_P0_WIRING_REPORT.md` | This report |

---

## 2. Wiring Points

### Runway final publish package

After `evaluate_delivery_quality()` in `run_live_post_processing()`:

1. Resolve canonical deliverable (`delivery gate → branded video → assembly output`)
2. Call `run_post_processing_quality_pipeline()`
3. Persist:
   - `{run_dir}/quality/video_quality_judge.json`
   - `project_brain/quality_judge/latest_video_quality_judge.json`
   - `project_brain/quality_learning/proposed_updates/{run_id}.json`
4. Attach judge payload to post-processing result dict (no live weight mutation)

### Kling Native Audio output package

After successful clip execution in `_execute_kling_clips()`:

1. Copy final `video.mp4` to run root
2. Call `run_post_processing_quality_pipeline()` with `kling_native_audio` strategy context
3. Same persistence paths as Runway
4. Expose judge fields on generate response + `load_kling_product_run_results()`

### Results aggregation

`load_run_results()` reads run-scoped judge JSON and proposed-learning flag.  
Kling-only runs use `_merge_kling_results()` with the same fields.

---

## 3. Results UI Changes

New **Video Quality Judge** card on Results page:

- Overall / Story / Audio / Visual / Continuity / Viral scores
- Strengths, weaknesses, improvement actions
- Learning proposed: yes/no
- Missing state: **"Quality Judge not run yet"** (old runs unaffected)

Uses existing `.cb-test-score-grid` layout for score chips.

---

## 4. Validation Results

```bash
python project_brain/validate_video_quality_judge_p0_wiring.py
python project_brain/validate_video_quality_judge_p0.py
```

**All checks passed**

| # | Test | Result |
|---|------|--------|
| 1 | Kling output triggers judge | PASS |
| 2 | Runway output triggers judge | PASS |
| 3 | Judge result saved in run_dir | PASS |
| 4 | Latest judge result updated | PASS |
| 5 | Learning proposed file created | PASS |
| 6 | Learning not applied automatically | PASS |
| 7 | Results page displays scores | PASS |
| 8 | Results page handles missing judge | PASS |
| 9 | No LLM call | PASS |
| 10 | No provider call (judge path) | PASS |

---

## 5. Sample Displayed Score

Example payload surfaced on Results page:

```json
{
  "overall_score": 92,
  "story_score": 87,
  "audio_score": 90,
  "visual_score": 100,
  "continuity_score": 88,
  "viral_score": 100,
  "strengths": ["Video stream present", "Audio level healthy (-28.0 dB)"],
  "weaknesses": [],
  "improvement_actions": [],
  "video_quality_learning_proposed": false
}
```

When sub-scores are weak, improvement actions populate and `video_quality_learning_proposed` becomes `true` (proposed file only — weights unchanged).

---

## 6. Constraints Honored

- No LLM
- No provider/generate/credits in judge wiring path
- No learning weight mutation (`applied: false`, live weights file untouched)
- Old results without judge JSON show graceful empty state

---

## 7. Next Recommended Phase

**VIDEO-QUALITY-JUDGE-P1 — optional LLM-assisted semantic review**

1. Feature-flagged semantic pass on hook/narrative quality
2. Operator approval before applying proposed learning deltas
3. Quality trend sparkline on Results (last N runs)
4. Soft publish warning when `overall_score < 60`

P0 wiring completes the post-run measurable loop; P1 adds semantic depth and controlled learning application.
