# Phase Director Layer v2 — Prompt Critic Report

**Phase:** DIRECTOR-2 — OpenAI Prompt Critic + Auto Rewrite  
**Status:** PASS  
**Date:** 2026-06-09

## Summary

Added an OpenAI-first **Prompt Critic** and **Auto Rewrite** layer that operates **only on prompts** before Runway execution. Runway automation, selectors, provider router, assembly, publish package, and FULL_AUTO runtime were not modified.

**Extended pipeline:**

```
Topic → Story Brief → Storyboard → Scene Breakdown → Continuity Planner → Prompt Builder → Prompt Critic → [Rewriter] → Runway
```

Critic/rewriter is **opt-in** via `auto_prompt_critic=True`. Default behavior unchanged.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/director/prompt_critic.py` | Phase 2A/2B — scoring, issue detection, OpenAI critic |
| `content_brain/director/prompt_rewriter.py` | Phase 2C — deterministic + OpenAI rewrite |
| `content_brain/director/prompt_review_pipeline.py` | Critic → rewrite → re-score (max 2 cycles) |
| `project_brain/validate_director_layer_v1.py` | Restored V1 regression validator |
| `project_brain/validate_director_layer_v2_prompt_critic.py` | V2 validation suite |
| `project_brain/PHASE_DIRECTOR_LAYER_V2_PROMPT_CRITIC_REPORT.md` | This report |

**Also restored (V1 lost during disk cleanup):**

- `content_brain/director/` full V1 package (models, pipeline, storyboard, scene, continuity, OpenAI client, topic authority)

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/director/director_models.py` | Added `PromptCriticReport`, `PromptReviewMetadata`, `PromptReviewResult`, thresholds |
| `content_brain/execution/runway_prompt_builder.py` | Director V1 + V2 integration (`auto_director`, `auto_prompt_critic`, API-ready `prompt_review` metadata) |

**Not modified:** Runway UI navigator, live smoke execution, browser provider, assembly, publish package.

---

## Scoring Model (Phase 2D)

Default thresholds (`PromptQualityThresholds`):

| Metric | Threshold |
|--------|-----------|
| `overall_score` | ≥ 80 |
| `topic_authority_score` | ≥ 90 |
| `continuity_score` | ≥ 80 |
| `hook_score` | ≥ 75 |
| `ending_score` | ≥ 75 |
| `repetition_score` | ≥ 70 (higher = less repetition) |

**Weighted overall:**

- Topic authority 25%
- Visual impact 15%
- Continuity 20%
- Hook 15%
- Ending 10%
- Repetition 15%

**Decisions:**

| Decision | When |
|----------|------|
| `PASS` | All thresholds met, no `topic_drift` |
| `IMPROVE` | Below threshold but recoverable |
| `REWRITE_REQUIRED` | `topic_drift` or overall < 60 |

---

## Rewrite Flow (Phase 2C)

```
Prompt V1 → Critic → decision?
  PASS → ship prompts
  IMPROVE / REWRITE_REQUIRED → Rewriter → Prompt V2 → Critic → (repeat, max 2 cycles)
```

Never loops infinitely — `DEFAULT_MAX_REWRITE_CYCLES = 2`.

---

## OpenAI Integration

| Stage | Module | Model cascade |
|-------|--------|---------------|
| Critic | `prompt_critic.py` | `gpt-5` → `gpt-4.1` → env / `gpt-4.1-mini` |
| Rewriter | `prompt_rewriter.py` | Same cascade |

Structured JSON via `openai_json_completion()`. Offline fallback when `dry_run=True` or no API key.

---

## Before / After Example (topic: `ants`)

**Before (intentionally bad prompts):**

```
Starter: Generic scene about technology and gaming GPU benchmark in a tech lab.
Clip 1: Clip about gaming GPU benchmark in tech lab...
Overall score: 36.3 | Issues: topic_drift, weak_visuals, continuity_risk, weak_hook, weak_ending, repetition_risk
```

**After (2 rewrite cycles, dry-run):**

```
Overall score: 82.44 | rewrite_count: 2
Gaming/GPU drift removed; topic anchor injected; hook/continuity/visual language strengthened
```

---

## API-Ready Metadata (Phase 2E)

`RunwayContinuityPromptBundle.prompt_review` exposes:

```json
{
  "version": "director_prompt_critic_v2",
  "topic": "ants",
  "score": 82.44,
  "decision": "PASS",
  "issues": [],
  "rewrite_count": 2,
  "thresholds": { "overall_min": 80, "topic_authority_min": 90, ... },
  "reports": [ { "cycle": 0, "phase": "initial", ... }, { "cycle": 2, "phase": "rescore", ... } ],
  "final_report": { ... }
}
```

No UI implemented — structure ready for future API/UI surfaces.

---

## Usage

```python
from content_brain.execution.runway_prompt_builder import build_continuity_prompts

bundle = build_continuity_prompts(
    "ants",
    clip_count=3,
    auto_story_brief=True,
    auto_director=True,
    auto_prompt_critic=True,
    director_dry_run=True,
    prompt_critic_dry_run=True,
)
review = bundle.prompt_review  # PromptReviewMetadata
```

---

## Validation Results

```bash
python project_brain/validate_director_layer_v2_prompt_critic.py
```

| Check | Result |
|-------|--------|
| Critic report generated | PASS |
| Scores generated | PASS |
| Topic drift detected | PASS |
| Repetition detected | PASS |
| Weak hook detected | PASS |
| Rewrite improves score | PASS (36.3 → 82.44) |
| Max rewrite count enforced | PASS (≤ 2) |
| Structured JSON output | PASS |
| Director V1 regression | PASS |
| Runway prompt builder | PASS |
| Runway runtime files untouched | PASS |

---

## Runway Unchanged — Confirmation

Director-2 only reads/writes **prompt text** upstream. No changes to browser automation, Generate/Download, provider router, or FULL_AUTO execution path. Operators opt in at prompt build time to avoid spending credits on weak prompts.
