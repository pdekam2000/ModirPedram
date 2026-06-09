# Content Brain End-to-End Micro Test Studio

**Phase:** Content Brain intelligence validation (permanent tool)  
**Status:** Implemented  
**Runway / Hailuo / media generation:** Not used

---

## Purpose

Validate the full Content Brain intelligence pipeline **before** spending Runway credits:

```
User Topic → Trend Discovery → Story → Duration → Clips → Prompts → SEO → Quality Audit → Export
```

---

## Operator entry point

**Execution Center → Content Brain Test Studio**

Web API:

- `POST /content-brain-test-studio/run`
- `GET /content-brain-test-studio/status`

---

## Modules

| Module | Role |
|--------|------|
| `content_brain/execution/content_brain_topic_authority.py` | Topic facet extraction + preservation scoring |
| `content_brain/execution/content_brain_e2e_micro_test_studio.py` | 9-step pipeline orchestrator + export |
| `ui/api/content_brain_test_studio_service.py` | API service |
| `ui/web/src/pages/ContentBrainTestStudioPage.tsx` | Operator UI |
| `project_brain/validate_content_brain_end_to_end_micro_test.py` | Validator |

---

## Pipeline steps

1. **User Topic Authority** — subject / environment / action + preservation flags  
2. **Live Trend Discovery** — `TrendDiscoveryEngine` with provider layer (DataForSEO, SerpAPI, enricher when configured)  
3. **Story Generation** — `RunwayStoryBriefBuilder` (rule-based, no credits)  
4. **Duration Planner** — `VideoFormatPlanner` (e.g. 30s → 3×10s)  
5. **Clip Planner** — hook / escalation / payoff per clip  
6. **Prompt Generation** — `runway_prompt_builder` only (no browser)  
7. **SEO Generation** — profile SEO rules + optional `ContentBriefOrchestrator` title packaging  
8. **Quality Audit** — composite scores  
9. **Export** — JSON + Markdown → `project_brain/content_brain_test_results/`

---

## Export paths

- Per run: `project_brain/content_brain_test_results/cb_e2e_<timestamp>_<id>.json|.md`
- Latest: `project_brain/content_brain_test_results/latest.json|.md`

---

## Validation

```bash
python project_brain/validate_content_brain_end_to_end_micro_test.py
```

Checks: topic preservation, all nine steps, prompt generation without Runway, export files, API route, UI tab.

---

## Example input

| Field | Example |
|-------|---------|
| Topic | old man walking on a beach |
| Duration | 30 |
| Platform | youtube_shorts |
| Mood | emotional |

---

## Constraints preserved

- No Runway browser automation  
- No Hailuo  
- No image/video generation  
- Story Brief Builder / Prompt Builder content paths reused (not rewritten)  
- Provider Router unchanged for media execution

---

## Recommended workflow

Run **Content Brain Test Studio** and review scores + exported JSON **before** any Runway Live Smoke or production clip generation.
