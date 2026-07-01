# Phase Live Post-Processing Hook Report

## Summary

Implemented a live post-processing hook that runs after successful non-simulate Runway smoke runs when all requested clips are downloaded. The hook writes a checkpoint, assembles clips with FFmpeg when available, and creates a publish package when assembly succeeds.

Runway automation, selectors, Prompt Builder, and Director/Critic were not modified.

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/runway_live_post_processor.py` | Checkpoint, assembly, publish package orchestration |
| `project_brain/validate_live_post_processing_hook.py` | Validation suite for the hook |
| `project_brain/PHASE_LIVE_POST_PROCESSING_HOOK_REPORT.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/runway_live_smoke_test.py` | Post-processing fields on report; hook call before `_persist_report()` |
| `ui/api/product_studio_service.py` | `latest_results()` reads assembly/publish manifests and runway report |
| `ui/api/schemas/product_studio.py` | Extended `LatestResultsResponse` |
| `ui/web/src/api/productClient.ts` | Extended results response type |
| `ui/web/src/pages/ResultsPage.tsx` | Pipeline status (Runway / Assembly / Publish) |

## Hook Location

`RunwayLiveSmokeRunner.run()` → `finally` block → after action log / page URL capture → **before** `_persist_report()`:

```python
if self.report.ok and not self.simulate:
    run_live_post_processing(self.report, project_root=ROOT)
```

Gates inside `run_live_post_processing()`:

- `simulate == false`
- `report.ok == true`
- `clips_downloaded == clip_count`
- all `downloaded_file_paths` exist with size > 0

## Assembly Behavior

- Input: `downloaded_file_paths` in report order (dynamic N clips)
- Output: `outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4`
- Manifest: `project_brain/runtime_state/runway_phase_i_assembly_manifest.json`
- FFmpeg via `check_ffmpeg_availability()`; concat demuxer for 2+ clips
- If FFmpeg missing: `status = PLAN_ONLY` (Runway run still succeeds; warning added)
- If FFmpeg fails: `status = FAILED` (Runway run still succeeds; warning added)

## Publish Behavior

- Runs when assembly `status == ASSEMBLED` and final video exists
- Package folder: `outputs/publish/runway_phase_i/`
- Includes final video copy, `metadata.json`, prompts (if available), subtitle placeholders, narration plan placeholder
- Manifest: `project_brain/runtime_state/runway_phase_i_publish_manifest.json`
- If assembly `PLAN_ONLY`: `status = SKIPPED_ASSEMBLY_PLAN_ONLY`

## Checkpoint Behavior

- Path: `project_brain/runtime_state/runway_phase_i_checkpoint.json`
- Overwrites stale simulate checkpoints on live runs
- Stages: `run_completed_post_processing_started` → `assembly_completed` → `publish_completed`
- Fields: `run_id`, `topic`, `clip_count`, `clips_generated`, `clips_downloaded`, `downloaded_file_paths`, `simulate`, timestamps

## Dynamic clip_count

No hardcoded 3-clip gate. Eligibility and assembly use `report.clip_count` and `report.downloaded_file_paths` length.

## New Report Fields

- `post_processing_enabled`
- `post_processing_status`
- `assembly_status`
- `final_video_path`
- `publish_package_status`
- `publish_package_folder`
- `post_processing_warnings`

## Validation Results

All validators passed:

```
python project_brain/validate_live_post_processing_hook.py   → ALL PASS (11 test groups)
python project_brain/validate_topic_authority_end_to_end.py  → PASS
python project_brain/validate_ui_pro_2_product_wiring_fixes.py → PASS
```

Hook validator covers: 1/2/3-clip assembly hook, missing file safety, simulate skip, FFmpeg PLAN_ONLY, publish gating, checkpoint overwrite, product results manifests, and Runway automation unchanged.

## Runway Automation Unchanged

- No edits to `runway_ui_navigator.py`, selector maps, Prompt Builder, Director/Critic, or Runway browser automation paths
- Only post-run hook added at end of `RunwayLiveSmokeRunner.run()`
