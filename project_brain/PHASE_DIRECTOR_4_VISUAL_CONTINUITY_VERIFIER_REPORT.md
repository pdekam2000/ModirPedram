# Phase DIRECTOR-4 — Visual Continuity Verifier Report

## Goal

Verify **actual generated Runway output**, not just prompts. Director-3 locks visual subject in prompts; Director-4 analyzes downloaded clip frames to detect visual drift (e.g. scorpion → spider).

## Architecture

```
Downloaded clip MP4
    ↓
frame_extractor.py (ffmpeg: first / middle / last frame)
    ↓
openai_vision_reviewer.py (OpenAI vision JSON review)
    ↓
visual_continuity_verifier.py (score + issues)
    ↓
visual_continuity_pipeline.py (per-clip + report JSON)
    ↓
runway_live_post_processor.py (after download checkpoint, before assembly)
    ↓
Results UI + runtime_state/visual_continuity_report.json
```

V1 behavior: **verify and report only** — no auto-regenerate, no Runway selector changes.

## Files created

| File | Purpose |
|------|---------|
| `content_brain/vision/__init__.py` | Package export |
| `content_brain/vision/frame_extractor.py` | Extract first/middle/last analysis frames |
| `content_brain/vision/openai_vision_reviewer.py` | OpenAI vision frame review |
| `content_brain/vision/visual_continuity_verifier.py` | Pass/fail scoring + issues |
| `content_brain/vision/visual_continuity_pipeline.py` | Batch verification + report writer |
| `project_brain/validate_visual_continuity_verifier.py` | Validation suite |
| `project_brain/PHASE_DIRECTOR_4_VISUAL_CONTINUITY_VERIFIER_REPORT.md` | This report |

## Files updated (integration only)

| File | Change |
|------|--------|
| `content_brain/execution/runway_live_post_processor.py` | Runs verification after downloads, adds warnings |
| `ui/api/product_studio_service.py` | Loads visual continuity report for Results API |
| `ui/api/schemas/product_studio.py` | `visual_continuity` on latest results DTO |
| `ui/web/src/api/productClient.ts` | Typed visual continuity fields |
| `ui/web/src/pages/ResultsPage.tsx` | Visual Continuity section |

**Not touched:** `runway_ui_navigator.py`, Runway selectors, generate/download automation logic.

## Example — scorpion → spider detection

Expected visual subject: **black scorpion**  
Vision detects: **spider**

Verifier output:

```json
{
  "clip_index": 2,
  "pass": false,
  "score": 34,
  "expected_subject": "black scorpion",
  "detected_subject": "spider",
  "issues": ["forbidden_confusion", "subject_mismatch"],
  "warnings": ["forbidden confusion detected: spider"]
}
```

Results UI:

```
Clip 1: PASS 92
Clip 2: FAIL 34 — Detected: spider; Expected: black scorpion
```

## Report artifact

`project_brain/runtime_state/visual_continuity_report.json`

Per clip fields: `detected_subject`, `expected_subject`, `similarity_score`, `pass`, `score`, `notes`, `frame_paths`, `vision_review`.

## Validation results

```bash
python project_brain/validate_visual_continuity_verifier.py
python project_brain/validate_visual_subject_lock.py
```

Expected:

1. Subject match pass — PASS  
2. Forbidden confusion fail (spider) — PASS  
3. Visual report generated — PASS  
4. OpenAI vision dry-run integration — PASS  
5. Director-3 validator regression — PASS  
6. Runway automation untouched — PASS  

## Operational notes

- Requires **ffmpeg/ffprobe** for frame extraction (same stack as assembly).
- OpenAI vision requires `OPENAI_API_KEY`; dry-run path available for tests.
- Failed clips add `visual_continuity_failed` to post-processing warnings but do **not** block assembly/publish in V1.
