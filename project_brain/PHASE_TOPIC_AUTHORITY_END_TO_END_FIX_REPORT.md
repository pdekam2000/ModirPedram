# Phase Topic Authority End-to-End Fix Report

## Critical bug

**Observed:** Runway prompt showed `Topic: Zander Fishing Method` while the user selected a different topic. Prompt also generated **3 clips** when the user requested **2 clips**.

**Impact:** Wrong topic and clip count waste Runway credits and produce incorrect videos.

---

## Root cause

The generate flow did **not** run Content Brain for the user's topic. Instead it reused stale cached handoff data:

1. `POST /product/create-video/generate` passed `story_idea` to `RunwayLiveSmokeRuntimeService.start_run()` only.
2. `resolve_live_smoke_prompts()` loaded prompts in this priority order:
   - registered E2E result
   - `project_brain/content_brain_test_results/latest.runway_prompts.txt`
   - `project_brain/content_brain_test_results/latest.json`
3. The cached `latest.json` contained a prior Content Brain Test Studio run for **`zander fishing method`** (3 clips).
4. On topic mismatch, handoff **still returned the stale payload** (warning only).
5. `_bundle_from_cleaned_payload()` preferred `payload.content_brain_topic` over `story_idea`, replacing the user topic with the cached fishing topic.
6. Clip count came from cached 3-clip export when duration preset implied 3 clips, or explicit user clip count was not forwarded.

---

## Fix summary

### 1. Strict topic authority in handoff (`content_brain_live_smoke_handoff.py`)

- Reject E2E / registered / `latest.json` / `latest.runway_prompts.txt` when `story_idea` does not match cached topic.
- `strict_topic_authority=True` blocks all cache fallbacks for Product generate.
- `_bundle_from_cleaned_payload()` now prefers **`story_idea`** over cached `content_brain_topic`.
- Fallback scaffold supports `auto_director` / `auto_prompt_critic`.

### 2. Product generate runs Content Brain first (`product_studio_service.py`)

Generate now:

1. Resolves authoritative topic from UI (custom vs channel mode).
2. Resolves explicit `clip_count` (UI override) or duration plan.
3. Clears stale registered E2E result.
4. Runs `run_content_brain_e2e_micro_test()` with the **exact user topic**.
5. Validates topic + clip count before Runway starts.
6. Builds prompt handoff with `strict_topic_authority=True`.
7. Registers fresh E2E result and starts Phase I with matching `e2e_result`.

### 3. Runway runtime wiring

- `RunwayLiveSmokeRuntimeService.start_run()` accepts `e2e_result`, `strict_topic_authority`, director/critic flags.
- Passes them through to `run_live_smoke_test()` → `resolve_live_smoke_prompts()`.

### 4. Topic authority trace logging

- New module: `content_brain/product/topic_authority_trace.py`
- Logs topic + clip_count at: UI request → generate endpoint → Content Brain E2E → Prompt Builder → Runway start.
- Written to: `project_brain/runtime_state/topic_authority_trace.json`
- Returned in generate API response as `topic_authority_trace`.

### 5. UI clip count override

- Create Video page sends explicit `clip_count` in generate payload.
- User can override planned clip count (e.g. force 2 clips).

---

## Pipeline audit (after fix)

| Stage | Topic source | Clip count source |
|-------|--------------|-------------------|
| Create Video UI | custom topic or saved channel topic | clip count override / duration plan |
| `/product/create-video/generate` | preflight authoritative topic | explicit `clip_count` or duration plan |
| Content Brain E2E | exact user topic argument | `duration_seconds = clip_count * 10` when explicit |
| Prompt Builder handoff | validated `story_idea` | requested `clip_count` (truncated/padded) |
| Runway runtime | same topic + registered fresh E2E | same `clip_count` |

No substitution from cached fishing demo data when topics differ.

---

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/content_brain_live_smoke_handoff.py` | Strict topic matching, story_idea priority |
| `content_brain/product/topic_authority_trace.py` | Trace logging |
| `ui/api/product_studio_service.py` | Content Brain before Runway, validation |
| `ui/api/runway_live_smoke_service.py` | Pass e2e_result + strict flags |
| `content_brain/execution/runway_live_smoke_test.py` | Strict handoff flags on runner |
| `ui/api/schemas/product_studio.py` | `clip_count`, trace fields |
| `ui/web/src/pages/CreateVideoPage.tsx` | Clip count override + payload |
| `project_brain/validate_topic_authority_end_to_end.py` | New validator |

---

## Validation

```text
python project_brain/validate_topic_authority_end_to_end.py
```

Checks:

1. Custom topic survives pipeline (stale fishing cache rejected)
2. Channel topic used only in channel mode
3. No stale `latest.json` reuse on mismatch
4. Requested clip count preserved in handoff
5. 2 clips remain 2 clips
6. Topic mismatch fails generate before Runway starts
7. Director V1/V2 + live smoke handoff regressions

---

## Runway automation unchanged

- No changes to Runway selectors, browser automation, provider router, or Phase I FULL_AUTO engine internals.
- Only handoff authority rules and Product generate wiring were fixed.

---

## Operator notes

1. Restart API server to load changes.
2. After Generate, inspect `project_brain/runtime_state/topic_authority_trace.json` if topic issues recur.
3. Use **Clip count override** on Create Video when you need an exact clip count (e.g. 2) independent of duration preset rounding.
