# Video Quality Judge P0 — Implementation Report

**Phase:** `VIDEO-QUALITY-JUDGE-P0`  
**Status:** Implemented — rules-only, no LLM/provider calls  
**Date:** 2026-06-16  

---

## 1. Files Created

| File | Purpose |
|------|---------|
| `content_brain/quality/video_quality_judge.py` | Rules-only judge: probes + existing reports → structured scores |
| `content_brain/quality/video_learning_loop.py` | P0 learning stub: proposed weight deltas only (no live mutation) |
| `project_brain/validate_video_quality_judge_p0.py` | 10 validation tests + persistence checks |
| `project_brain/VIDEO_QUALITY_JUDGE_P0_REPORT.md` | This report |

**Updated:**

| File | Change |
|------|--------|
| `content_brain/quality/__init__.py` | Exports `judge_video_quality`, `judge_and_persist`, `run_video_learning_loop` |

---

## 2. Scoring Rules

### Overall (weighted)

| Dimension | Weight |
|-----------|--------|
| Story | 25% |
| Audio | 20% |
| Visual | 20% |
| Continuity | 20% |
| Viral | 15% |

### Audio (0–100)

- Base score with audio stream present (+25)
- Mean volume via `ffmpeg volumedetect`:
  - ≥ −35 dB → strong (+25)
  - ≥ −45 dB → audible (+15)
  - below −45 dB → quiet penalty
- Missing audio stream → cap at 25
- Music penalty only when `music_provider` enabled and audio report shows skip/failure
- `kling_native_audio` strategy: bonus when native in-video audio is audible

### Visual (0–100)

- File exists and non-empty
- Video stream present (`ffprobe`)
- Duration > 0
- Resolution present; ≥720 on both axes preferred
- Truncation penalty when assembly manifest duration loss ratio > 5%

### Continuity (0–100)

- Uses `visual_continuity_report.overall_score` when present
- Multi-clip runs (`clip_count ≥ 2`) without continuity metadata → 35
- Single-clip runs without report → 60 (optional metadata)

### Story (0–100)

- Uses `story_audio_audit.story_score` or `story_visual_quality` composite when present
- Missing story package → cap at 40
- Duration/story mismatch when delivered vs planned duration delta > 25%
- Topic present in runtime metadata → small boost

### Viral (0–100)

- Uses existing `viral_score` or brief `viral_scorecard.composite_score` when present
- Otherwise heuristic:
  - Short-form duration (6–60s)
  - Topic/title present
  - Story hook present in story package
  - Publish metadata present

### Improvement actions

Generated when sub-scores fall below 60 (or reinforcement when environment audio is strong):

- `boost_dialogue_emphasis`
- `increase_environment_weight`
- `improve_visual_continuity`
- `strengthen_hook`
- `improve_pacing`
- `increase_cinematic_language`

---

## 3. Persistence

| Output | Path |
|--------|------|
| Run-scoped judge result | `{run_dir}/quality/video_quality_judge.json` |
| Latest copy | `project_brain/quality_judge/latest_video_quality_judge.json` |
| Proposed learning updates | `project_brain/quality_learning/proposed_updates/{run_id}.json` |

Run directory resolution:

1. Explicit `run_dir` in context
2. Infer from `outputs/kling_multishot_live/{run_id}/`
3. Infer from `outputs/runs/{run_id}/`
4. Fallback: `outputs/quality_judge/{run_id}/`

---

## 4. Learning Loop (P0 Stub)

`run_video_learning_loop()`:

1. Reads judge output
2. If `overall_score < threshold` (default 70) → **corrective** mode from `improvement_actions`
3. If `overall_score ≥ 85` → **reinforcement** mode from strengths
4. Writes proposed deltas to `project_brain/quality_learning/proposed_updates/{run_id}.json`
5. Sets `"applied": false` — **does not mutate** `project_brain/runtime_state/channel_quality_learning.json`

---

## 5. Validation Results

Command:

```bash
python project_brain/validate_video_quality_judge_p0.py
```

Result: **all checks passed**

| # | Test | Result |
|---|------|--------|
| 1 | Valid MP4 with metadata gets score | PASS (overall 92) |
| 2 | Missing audio lowers audio score | PASS (25 < 90) |
| 3 | Truncated duration lowers visual/story | PASS (75/72 < 100/87) |
| 4 | Missing story package lowers story | PASS (45 < 87) |
| 5 | Continuity report improves continuity | PASS (90 > 35) |
| 6 | Improvement actions for weak areas | PASS |
| 7 | Learning loop produces proposed update file | PASS |
| 8 | Does not call LLM | PASS |
| 9 | Does not call provider | PASS |
| 10 | Does not mutate live weights | PASS |

Additional: persistence paths for run + latest JSON — PASS

---

## 6. Sample Output

```json
{
  "version": "video_quality_judge_p0",
  "run_id": "sample_run_p0",
  "video_path": ".../final.mp4",
  "overall_score": 92,
  "story_score": 87,
  "audio_score": 90,
  "visual_score": 100,
  "continuity_score": 88,
  "viral_score": 100,
  "strengths": [
    "Video stream present",
    "Resolution present (1080x1920)",
    "Duration preserved vs assembly",
    "Audio level healthy (-28.0 dB)",
    "Visual continuity report passed"
  ],
  "weaknesses": [],
  "improvement_actions": [],
  "used_sources": [
    "ffprobe_video_stream",
    "ffmpeg_mean_volume",
    "visual_continuity_report",
    "story_audio_audit"
  ],
  "created_at": "2026-06-16T21:09:06.930878+00:00"
}
```

---

## 7. Usage

```python
from content_brain.quality.video_quality_judge import judge_and_persist
from content_brain.quality.video_learning_loop import run_video_learning_loop

result = judge_and_persist(
    video_path="outputs/kling_multishot_live/{run_id}/final.mp4",
    run_id="{run_id}",
    context={"run_dir": "outputs/kling_multishot_live/{run_id}", ...},
    project_root=".",
    run_dir="outputs/kling_multishot_live/{run_id}",
)

proposed = run_video_learning_loop(result, project_root=".")
```

---

## 8. Constraints Honored

- No LLM calls
- No vision model
- No provider/generate/credits usage
- Uses existing `media_probe` + inline/file-loaded reports only
- Learning loop proposes updates only — live weights unchanged

---

## 9. Next Recommended Phase

**VIDEO-QUALITY-JUDGE-P1 — optional LLM-assisted semantic review**

Suggested scope:

1. Wire judge into post-processor (`runway_live_post_processor`, `kling_product_run`) after delivery gate
2. Surface scores on Results page (`ResultsPage.tsx` + `results_run_loader`)
3. Optional LLM semantic pass for narrative/hook quality (behind feature flag, credit-gated)
4. Apply learning loop deltas to channel quality profile with approval gate
5. Soft publish warning when `overall_score < 60`

P0 delivers the measurable foundation; P1 adds semantic depth and product integration.
