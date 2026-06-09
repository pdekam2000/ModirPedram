# Content Brain V8.3 → Runway Live Smoke Handoff Report

**Phase:** CONTENT-BRAIN-HANDOFF-1  
**Date:** 2026-06-03  
**Handoff module:** `content_brain/execution/content_brain_live_smoke_handoff.py`

## Goal

Connect Content Brain V8.3 cleaned prompts to **Runway Live Smoke only**, without changing Provider Runtime, browser automation, Use Frame logic, or download logic.

## Problem (before)

Content Brain V8.3 exported cleaned prompts via `prompt_cleanup`, but Live Smoke still called `build_continuity_prompts(story_idea)` directly. V8.3 outputs stopped at export.

## Solution

A dedicated handoff layer resolves prompts in priority order:

1. Current E2E run result (in-memory / registered after Test Studio run)
2. `project_brain/content_brain_test_results/latest.runway_prompts.txt`
3. `project_brain/content_brain_test_results/latest.json` (`prompt_cleanup` step)
4. Fallback: existing `build_continuity_prompts()`

Live Smoke now calls `resolve_live_smoke_prompts()` before dry-run and semi-auto execution. Continuity anchors and story brief scaffolding still come from the legacy builder when needed; **starter + clip prompts** come from `prompt_cleanup`.

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/content_brain_live_smoke_handoff.py` | **New** handoff resolver |
| `content_brain/execution/runway_live_smoke_test.py` | Integrate handoff; report fields |
| `ui/api/content_brain_test_studio_service.py` | Register E2E result after studio run |
| `ui/api/runway_live_smoke_service.py` | Pass registered E2E + handoff preview API |
| `ui/api/main.py` | `GET /runway-live-smoke/handoff-preview` |
| `ui/api/schemas/runway_live_smoke.py` | `handoff_preview` response field |
| `ui/web/src/api/runwayLiveSmokeClient.ts` | Handoff preview client |
| `ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx` | Prompt Handoff UI panel |
| `project_brain/validate_content_brain_live_smoke_handoff.py` | **New** validator |

## Report fields (Live Smoke)

| Field | Values / meaning |
|-------|------------------|
| `prompt_source` | `CONTENT_BRAIN_V83` or `FALLBACK_CONTINUITY_BUILDER` |
| `content_brain_run_id` | E2E run id when handoff used |
| `prompt_cleanup_used` | Whether cleanup pass prompts were loaded |
| `prompt_noise_score` | From cleanup / quality audit |
| `prompt_efficiency_score` | From cleanup / quality audit |
| `handoff_loaded_from` | `e2e_result`, `latest.runway_prompts.txt`, `latest.json`, or fallback |
| `content_brain_topic` | Original Content Brain input topic |
| `topic_label` | Human-readable label (e.g. Perfume Bestseller Prediction) |
| `seo_title` | SEO title from Content Brain export |
| `story_summary` | Logline / clip-beat summary from story generation |
| `starter_prompt_preview` | Truncated cleaned starter image prompt |

## UI (Runway Live Smoke)

The approval panel shows **Prompt Handoff**:

- Prompt Source
- Run ID
- Prompt cleanup used
- Noise score
- Efficiency score

When `CONTENT_BRAIN_V83` is active, the panel also shows **Using Content Brain V8.3 prompts** with topic label, SEO title, story summary, and starter prompt preview. The manual story textbox is disabled and marked as ignored unless fallback mode is active.

## Pipeline (after handoff)

```
Content Brain V8.3
  → Prompt Cleanup
  → Starter Image prompt
  → Clip 1 prompt
  → Clip 2 prompt
  → Clip 3 prompt
  → Existing Runway Live Smoke runtime (unchanged browser / Use Frame / download)
```

## Out of scope (unchanged)

- Provider Runtime
- Runway browser automation (`runway_ui_navigator`)
- Use Frame logic
- Download logic

## Validation

Run:

```powershell
python project_brain/validate_content_brain_live_smoke_handoff.py
```

Checks:

1. E2E export exists (`latest.json`, `latest.runway_prompts.txt`)
2. Starter image loaded from cleanup
3. Clips 1–3 loaded from cleanup
4. Cleanup metrics preserved
5. Handoff reaches Live Smoke runner report
6. Fallback path still works when no export is available

## Success criteria

- [x] Dedicated handoff module
- [x] Live Smoke uses cleaned prompts when export/register available
- [x] Fallback to `build_continuity_prompts()` when handoff unavailable
- [x] Report + UI expose prompt source and cleanup metrics
- [x] No changes to browser automation, Use Frame, or download paths
