# PHASE PRODUCT-VISUAL-DIVERSITY-GUARD Report

**Phase:** `PRODUCT-VISUAL-DIVERSITY-GUARD`  
**Date:** 2026-06-27  
**Scope:** Clip prompt diversity enforcement, pre-generation repetition gate, post-download visual similarity check, Results UI, upload blocking.

---

## Problem

Multi-clip generation, Use Frame, assembly, and YouTube upload all work — but clips can look too similar, making final videos feel repetitive.

---

## Solution

### New module

`content_brain/execution/product_visual_diversity_guard.py`

| Capability | Description |
|------------|-------------|
| Clip diversity specs | Per-clip camera distance, action beat, pose, environment, emotion, composition |
| Use Frame balance | Preserve identity/palette/world; force new action, angle, spatial position |
| Pre-generation gate | Compare clip prompts; block run when `repetition_risk = high` |
| Post-generation check | Compare first-frame signatures; fail with `visual_repetition_failed` |
| Report artifact | `visual_diversity_report.json` in run folder |

### Prompt builder integration

`content_brain/execution/runway_prompt_builder.py`

- Appends visual diversity directives to every clip prompt
- Extended narrative roles through clip 4 (establishing → pursuit → close-up → resolution)
- Use Frame variation rules on clips 2+

### Orchestrator integration

`content_brain/execution/product_multiclip_orchestrator.py`

- **Before generation:** blocks if prompt repetition risk is high (no credits spent)
- **After download:** runs frame-signature similarity check
- On `visual_repetition_failed`: skips assembly/branding, sets `publish_ready=false`, `youtube_upload_allowed=false`

### Upload gate

`ui/api/upload_service.py` — blocks publish-package upload when visual diversity report disallows upload (without modifying `youtube_upload_runtime.py`).

### Results integration

- `pwmap_finalization.build_pwmap_results_payload()`
- `product_studio_service._merge_pwmap_results()`
- `ResultsPage.tsx` — Visual Diversity panel

---

## Clip progression template

| Clip | Camera | Action |
|------|--------|--------|
| 1 | Wide establishing | Discovery / orientation |
| 2 | Medium pursuit | Escalation / movement |
| 3 | Close-up | Discovery / conflict |
| 4 | Medium-wide hero | Resolution / reveal |

---

## Failure modes

| Status | When | Effect |
|--------|------|--------|
| `prompt_repetition_blocked` | Pre-gen prompt similarity high | Generation never starts |
| `visual_repetition_failed` | Post-gen frame similarity ≥ 0.90 | No publish package, upload blocked |

---

## Not modified

- pwmap browser mappings (`pwmap_runway_agent_adapter.py` job/browser logic)
- Use Frame implementation
- YouTube upload runtime
- OAuth
- Assembly bridge

---

## Validation

**Script:** `project_brain/validate_product_visual_diversity_guard.py`

| Test | Result |
|------|--------|
| Near-identical prompts blocked | PASS |
| Diverse prompts pass | PASS |
| Use Frame continuity allowed | PASS |
| Upload blocked when visual_repetition_failed | PASS |
| Post-generation visual repetition detected | PASS |
| Repetitive video skips publish pipeline | PASS |
| Results displays visual diversity warnings | PASS |
| publish_ready cleared on repetition | PASS |
| Protected modules unmodified | PASS |
| Results UI panel | PASS |

**Total: 12/12 PASS**

```bash
python project_brain/validate_product_visual_diversity_guard.py
```

---

## Artifacts

```
outputs/pwmap_agent_runs/<run_id>/
  visual_diversity_report.json
  clip_1.mp4 … clip_N.mp4
```

Example report fields:

```json
{
  "visual_diversity_score": 82,
  "repetition_risk": "low",
  "status": "prompt_diversity_passed",
  "similar_clip_pairs": [],
  "publish_ready": true,
  "youtube_upload_allowed": true
}
```
