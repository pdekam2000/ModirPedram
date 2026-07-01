# CLIP COUNT AUTHORITY REPORT

**Phase:** CLIP-COUNT-AUTHORITY-REPAIR  
**Topic:** A boy finds a dragon egg in the forest and hides it from everyone  
**Date:** 2026-06-14  

---

## Summary

The UI requested **4 clips** for a **40-second** Runway short. Content Brain produced **5 clips**, and the topic authority guard correctly blocked execution (`5 != 4`). Root cause was a split authority between the UI duration preflight and the Content Brain `video_format_planner`, compounded by missing propagation of `requested_clip_count` into the E2E pipeline and trace metrics reading prompt list length instead of the authoritative plan.

**Fix:** Single authority module + propagation of `requested_clip_count` through duration plan → story package → prompt builder → prompt cleanup → Runway handoff. Duration snap table updated so 40s no longer snaps to 45s.

---

## Requested vs Generated (before fix)

| Stage | clip_count | Source |
|-------|------------|--------|
| UI request / preflight | **4** | `duration_planner.plan_duration(40)` → `40 ÷ 10 = 4` |
| Content Brain E2E duration step | **5** | `video_format_planner.plan(user_duration_seconds=40)` |
| Content Brain E2E trace | **5** | `_extract_e2e_prompt_metrics()` → `len(prompt_cleanup.clip_prompts)` |
| Guard | **blocked** | `topic_authority_trace.validate_clip_count` → `5 != 4` |

**Trace artifact:** `project_brain/runtime_state/topic_authority_trace.json`  
**E2E run:** `cb_e2e_20260614_191849_19cf2f75`

---

## Clip count flow (traced)

```
Create Video UI
  └─ clip_count=4, duration_seconds=40 (override)
       │
Product Studio preflight
  └─ duration_planner.calculate_clip_count(40, runway) → 4
       │
create_video_generate()
  └─ [BEFORE FIX] called E2E with duration_seconds=40 only — no requested_clip_count
       │
Content Brain E2E — _step_duration_plan()
  └─ video_format_planner.plan(40)
       └─ [BEFORE FIX] _snap_duration(40) → 45 (40 not in SUPPORTED_SHORT_DURATIONS)
       └─ ceil(45/10) → clip_count=5
       │
Story Package (_step_story_generation)
  └─ clip_count from duration_plan → 5
       │
Prompt Builder (build_continuity_prompts_from_brief)
  └─ story_brief.clip_count → 5 prompts
       │
Prompt Cleanup
  └─ 5 clip_prompts → trace recorded clip_count=5
       │
Runway Planner (resolve_live_smoke_prompts)
  └─ never reached — guard blocked at content_brain_e2e
```

---

## Root cause — exact files

### 1. Duration snap invented 5 clips

**File:** `content_brain/engines/video_format_planner.py`

- `SUPPORTED_SHORT_DURATIONS` was `[15, 30, 45, 60]` — **40 was missing**.
- `_snap_duration(40)` snapped to **45** (nearest supported value).
- `_resolve_clip_structure`: `ceil(45 / 10) = 5` clips.

### 2. UI clip count not propagated into E2E

**File:** `ui/api/product_studio_service.py`

- `create_video_generate()` resolved `clip_count=4` from payload.
- Called `run_content_brain_e2e_micro_test(duration_seconds=40)` **without** `requested_clip_count`.
- E2E used format planner output (5) instead of UI authority (4).

### 3. Trace compared wrong metric

**File:** `ui/api/product_studio_service.py` — `_extract_e2e_prompt_metrics()`

- Used `len(prompt_cleanup.clip_prompts)` as `clip_count`.
- Reported **5** even when UI requested **4**, triggering the guard.

### 4. E2E had no authority field

**File:** `content_brain/execution/content_brain_e2e_micro_test_studio.py`

- `ContentBrainE2ETestInput` lacked `requested_clip_count`.
- Duration plan from format planner was never overridden.

---

## Rule: 40 seconds = how many clips?

**Authority:** `content_brain/scheduling/duration_planner.py`

```python
calculate_clip_count(duration_seconds=40, provider="runway")
# Runway clip limit = 10s
# 40 ÷ 10 = 4 clips
```

| Duration | Runway clip limit | clip_count |
|----------|-------------------|------------|
| 40s | 10s | **4** |
| 30s | 10s | 3 |
| 45s | 10s | 5 (aligned to 50s target) |

UI override: when `clip_count` is set explicitly, `duration_seconds = clip_count × 10` (40s for 4 clips).

---

## Fix implemented

### New module

**`content_brain/platform/clip_count_authority.py`**

- `build_clip_count_authority()` — canonical requested count + duration
- `apply_authoritative_clip_count()` — force duration plan payload
- `assert_clip_count_authority()` — fail closed on stage mismatch
- `expected_clip_count_for_duration()` / `infer_format_planner_clip_count()` — audit helpers

### Wiring

| File | Change |
|------|--------|
| `content_brain/execution/content_brain_e2e_micro_test_studio.py` | `requested_clip_count` on input; override duration plan; assert at duration, story, prompt_builder, prompt_cleanup |
| `ui/api/product_studio_service.py` | Pass `requested_clip_count` to E2E; metrics read duration_planner / requested count |
| `content_brain/engines/video_format_planner.py` | Added **20** and **40** to `SUPPORTED_SHORT_DURATIONS` |

### Propagation contract

When UI sets `clip_count=4`:

1. **Duration plan** → `clip_count=4`, `requested_clip_count=4`
2. **Story package** → `story_brief.clip_count=4`
3. **Prompt builder** → 4 continuity prompts
4. **Prompt cleanup** → `clip_count=4` (authoritative field, not list length)
5. **Runway handoff** → `resolve_live_smoke_prompts(..., clip_count=4)` (unchanged call site, now receives matching E2E output)

If any stage produces a different count while `requested_clip_count` is set, `ClipCountAuthorityError` is raised **before** Runway planning.

---

## Verification (post-fix)

```
requested_clip_count=4, duration_seconds=40
duration_planner clip_count: 4
story clip_count: 4
prompt_cleanup clip_count: 4, prompts: 4
```

Both planners now agree on 40s → 4:

```
duration_planner: 4
format_planner:   4
```

---

## Scope boundaries (honored)

- Did **not** start Runway
- Did **not** generate video
- Did **not** modify prompt text
- Fixed clip-count authority only

---

## Related artifacts

- `project_brain/runtime_state/topic_authority_trace.json` — pre-fix mismatch record
- `project_brain/content_brain_test_results/cb_e2e_20260614_191849_19cf2f75.json` — pre-fix E2E with `clip_count: 5`
