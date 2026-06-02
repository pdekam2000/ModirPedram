# PHASE 12J-C2A-OBS — Runway Browser Execution Observability

**Date:** 2026-05-31  
**Scope:** Observability only — no Runway generate, wait, download, prompt composer, Content Brain, voice/subtitle/assembly, or `browser_launcher` changes.

---

## Problem

UAT dispatch and Video Runtime reach `RUNNING`, but the operator may watch a different Chrome tab than Playwright controls (`context.pages[0]`). Without persisted step + tab metadata, stalls before prompt typing look like a hung “Video Runtime” with no actionable detail.

---

## Solution

### 1. Session persistence (`runway_browser_observability.py`)

- New module: `content_brain/execution/runway_browser_observability.py`
- Writes to:
  - `execution_runtime.operations.runway_browser_obs`
  - `execution_runtime.category_runtime.video_generation.runway_browser_obs` (mirror)

**Steps persisted:**

| Step | When set |
|------|----------|
| `browser_connecting` | Before `RunwayBrowserProvider.start()` |
| `browser_connected` | After CDP attach |
| `page_selected` | After controlled page snapshot |
| `preparing_gen45_page` | Before `prepare_gen45_page()` |
| `filling_prompt` | Before `fill_prompt()` per clip |
| `generate_clicked` | After `click_generate()` |
| `waiting_for_generation` | Start of `wait_for_generated_video_url()` |
| `video_url_detected` | After URL resolved |
| `download_started` | Before download call |
| `download_completed` | After download succeeds |
| `failed` | On cancel/provider/generic failure |

**Page metadata (safe):**

- `controlled_page`: `page_index`, `page_url` (query/fragment stripped), `page_title`, `is_runway_url`
- `open_pages`: up to 24 tabs — index, safe URL, title, Runway flag, `controlled` marker

**Not stored:** credentials, cookies, localStorage, account emails, or raw query strings.

### 2. Stdout logs

| Tag | Trigger |
|-----|---------|
| `[RUNWAY_STEP]` | Every `set_step()` / `mark_failed()` |
| `[RUNWAY_PAGE_SELECTED]` | `record_controlled_page()` |
| `[RUNWAY_PROMPT_TYPING_START]` | Start of `fill_prompt()` |
| `[RUNWAY_GENERATE_CLICKED]` | Start of `click_generate()` |
| `[RUNWAY_WAIT_STARTED]` | Start of generation wait (includes max wait) |

### 3. Wiring (observability hooks only)

| File | Change |
|------|--------|
| `provider_runtime_engine.py` | Builds `RunwayBrowserObservability` for `runway_browser` + passes to router |
| `core/video_provider_router.py` | `runway_obs` → `RunwayBrowserOrchestrator` |
| `orchestrators/runway_browser_orchestrator.py` | Step transitions around existing flow |
| `providers/runway_browser_provider.py` | Optional `runway_obs`; typing/generate log tags only |

**Unchanged:** `automation/browser_launcher.py`, download provider logic, wait heuristics, prompt composer, Content Brain engines.

### 4. UAT API + UI

- `build_uat_status_payload()` adds `runway_browser_obs` and `video_runtime` summary.
- `UatRunResponse` schema extended (`ui/api/schemas/uat_runtime.py`).
- UAT Runtime page: under **Video Runtime** step, shows:
  - Video Runtime: `ACTIVE` when state is `RUNNING`
  - Runway step
  - Controlled tab URL
  - Page title
  - Expandable open tabs when more than one

---

## Validation

```bash
python project_brain/validate_12j_c2a_runway_browser_observability.py
```

**Manual UAT checklist:**

1. Start supervised UAT with `runway_browser` + real video confirm.
2. Poll `/uat/status/{session_id}` or watch UAT UI during video stage.
3. Confirm step advances: `browser_connecting` → … → `filling_prompt` → `waiting_for_generation`.
4. Compare **Controlled tab** URL/title with the tab Playwright uses (first context page).
5. If stuck before typing, UI shows last step (e.g. `preparing_gen45_page`) without changing automation behavior.

---

## Operator notes

- Observability runs in the UAT daemon thread; `[RUNWAY_*]` tags appear in that process stdout (not always in uvicorn API logs).
- Tab mismatch diagnosis: if `Controlled tab` is not the tab you are watching, the operator is on the wrong Chrome tab — not a generation failure.
- Failed step includes a short `failure_message` (no secrets).

---

## Files touched

| Path | Role |
|------|------|
| `content_brain/execution/runway_browser_observability.py` | New persistence + safe URL helpers |
| `content_brain/execution/provider_runtime_engine.py` | Factory + router pass-through |
| `core/video_provider_router.py` | `runway_obs` parameter |
| `orchestrators/runway_browser_orchestrator.py` | Step hooks |
| `providers/runway_browser_provider.py` | Log tags only |
| `content_brain/execution/uat_runtime_engine.py` | Status payload |
| `ui/api/schemas/uat_runtime.py` | Response models |
| `ui/web/src/api/uatRuntimeClient.ts` | TS types |
| `ui/web/src/pages/UatRuntimePage.tsx` | Video Runtime observability panel |
| `ui/web/src/styles/uat-runtime.css` | Panel styles |
| `project_brain/validate_12j_c2a_runway_browser_observability.py` | Automated checks |

---

## Next (out of scope)

- 12J-C2b multi-signal wait / tab selection policy (behavior change)
- Execution Center runtime panel (can read same `runway_browser_obs` without new backend work)
