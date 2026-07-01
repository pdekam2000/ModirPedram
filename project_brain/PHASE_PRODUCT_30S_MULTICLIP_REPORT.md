# PHASE PRODUCT-30S-MULTICIP — Report

**Date:** 2026-06-20  
**Scope:** Product Studio orchestration only — no pwmap, browser, Use Frame, or recovery pipeline changes.

## Goal

Extend Product Studio so duration selection automatically plans and executes the correct clip chain via existing validated pwmap adapter paths.

## Duration Mapping

| Requested Duration | Clip Count | Execution Mode |
|-------------------|------------|----------------|
| 15s | 1 | `single_clip` |
| 30s | 2 | `use_frame_chain` |
| 40s | 3 | `use_frame_chain` |
| 60s | 4 | `use_frame_chain` |
| Custom | `ceil(duration / 15)` | 1 clip → `single_clip`, 2+ → `use_frame_chain` |

Example planner output:

```json
{
  "duration_seconds": 30,
  "clip_count": 2,
  "execution_mode": "use_frame_chain"
}
```

## Execution Routing

| Clips | Route |
|-------|-------|
| 1 | pwmap agent **single clip** (`build_pwmap_job` with `prompt`) |
| 2+ | pwmap agent **multi-clip** (`prompts` + `use_frame_second`) |

Orchestration flow:

1. `create_video_preflight` → `plan_product_duration` → `MultiClipExecutionPlan`
2. Frame plan built with correct `clip_count` and prompts
3. `create_video_generate` → `run_product_multiclip_generate`
4. Delegates to unchanged `run_pwmap_product_studio_generate`
5. Post-run: optional FFmpeg stitch for 2+ clips → `video.mp4`
6. Runtime + results metadata written to `product_multiclip_runtime.json` and enriched `normalized_result.json`

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/product_multiclip_execution_plan.py` | Centralized duration planner, `MultiClipExecutionPlan`, runtime status builder |
| `content_brain/execution/product_multiclip_orchestrator.py` | Product Studio wrapper over pwmap adapter + FFmpeg merge finalize |
| `project_brain/validate_product_30s_multiclip.py` | Automated validation (19 checks) |
| `project_brain/PHASE_PRODUCT_30S_MULTICLIP_REPORT.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `ui/api/product_studio_service.py` | Preflight applies product duration plan; generate uses multiclip orchestrator; results merge includes clip metadata |
| `ui/web/src/product/constants.ts` | Kling presets 15/30/40/60 + clip hints |
| `ui/web/src/api/productClient.ts` | Types for `MultiClipExecutionPlan`, `GenerationRuntimeStatus` |
| `ui/web/src/pages/CreateVideoPage.tsx` | Custom duration for Kling, execution mode display, runtime clip status |
| `ui/web/src/pages/ResultsPage.tsx` | Final MP4, duration, clip count, provider, generation time, execution mode |

## Files Unchanged (Safety)

- `content_brain/execution/pwmap_runway_agent_adapter.py` — **not modified**
- pwmap `runway_agent.py` / browser mappings — **not modified**
- Use Frame implementation — **not modified**
- Recovery pipeline / generation completion gate — **not modified**
- Legacy 15s single-clip pwmap routing — **preserved** (`len(prompts) == 1` path)

## MultiClipExecutionPlan Fields

- `duration_seconds`
- `clip_count`
- `prompts`
- `provider`
- `aspect_ratio`
- `native_audio`
- `execution_mode` (`single_clip` | `use_frame_chain`)
- `use_frame_enabled`

## Runtime Visibility (Create Video)

Generation response includes `generation_runtime_status`:

- `planned_clip_count`
- `current_clip`
- `completed_clips`
- `generation_state` (`generating` | `completed` | `merge_complete` | `failed`)
- `clip_statuses[]` with labels like `Clip 1/2 Generating...`

## Results Page

Shows when pwmap/multiclip metadata is present:

- Final MP4 path
- Duration (probed or planned)
- Clip count
- Provider (`pwmap_agent`)
- Generation time (seconds)
- Execution mode

## Validation Results

```
python project_brain/validate_product_30s_multiclip.py
TOTAL: 19  PASS: 19  FAIL: 0
ALL PASS
```

Checks include:

- 15s → 1 clip, `single_clip`
- 30s → 2 clips, `use_frame_chain`
- 40s → 3 clips, `use_frame_chain`
- 60s → 4 clips, `use_frame_chain`
- Custom durations (22, 45, 75)
- Product Studio preflight creates valid execution plan
- pwmap adapter routing preserved
- Results merge receives clip count + execution mode metadata

## Confirmation

- No runtime redesign
- No browser changes
- No provider changes
- Only Product Studio orchestration over existing validated paths
