# PHASE N-CLIP POST-PROCESSING RECOVERY REPORT

## Root cause

Live post-processing eligibility in `evaluate_post_processing_eligibility()` trusted `total_downloads_completed` before validating on-disk downloads.

For run `cb_e2e_20260610_201403_811da26d` (60s / 6 clips):

- `clip_count`: 6
- `downloaded_file_paths`: 6 existing non-empty files
- `total_downloads_completed`: 3 (stale counter)
- Eligibility returned `downloads_mismatch:3!=6`
- Post-processing was skipped, so assembly/publish/visual continuity never ran
- Results API continued to surface stale cat-run manifests (`cb_e2e_20260610_173213_22433f51`)

Fix: use valid on-disk paths as source of truth when `len(valid_downloads) == clip_count`, and sync `total_downloads_completed` to match.

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/runway_live_post_processor.py` | Added `collect_valid_download_paths()`; eligibility uses valid path count; syncs stale counter |
| `project_brain/recover_latest_run_post_processing.py` | New recovery command (post-processing only) |
| `ui/api/product_studio_service.py` | Stale manifest guard + visual continuity run_id guard/backfill |
| `ui/api/schemas/product_studio.py` | New Results fields for post-processing/stale state |
| `ui/web/src/api/productClient.ts` | Typed Results fields |
| `ui/web/src/pages/ResultsPage.tsx` | Shows post-processing + stale manifest + continuity unavailable states |
| `project_brain/validate_n_clip_post_processing_recovery.py` | New validator (9 tests) |

**Not changed:** Runway automation, selectors, prompt builder, Director/Critic, ElevenLabs generation internals.

## Recovery command

```bash
python -m project_brain.recover_latest_run_post_processing
```

Behavior:

- Loads latest runway report from `project_brain/runway_phase_i_3clip_last_report.json` (fallback: `runway_live_smoke_last_report.json`)
- Verifies `downloaded_file_paths` on disk
- Runs checkpoint → visual continuity → assembly → publish only
- Persists updated report fields
- No Runway browser, no generation, no credits

## Latest 60s run recovery result

Run: `cb_e2e_20260610_201403_811da26d`

Recovery output:

- `eligible_before_run`: true
- `post_processing_status`: completed
- `assembly_status`: ASSEMBLED
- `publish_package_status`: PUBLISHED_PACKAGE_CREATED
- `total_downloads_completed` synced to 6 in saved report

Warnings (non-blocking):

- Visual continuity FAIL for all 6 clips (vision review)
- Audio post-processing failed (`narration_audio_missing` — ElevenLabs path unchanged by design)

## Output paths

| Artifact | Path |
|----------|------|
| Final video (versioned run) | `outputs/runs/20260611_122643_403_811da26d/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` |
| Publish package (versioned run) | `outputs/runs/20260611_122643_403_811da26d/publish` |
| Legacy final symlink/copy target | `outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` |
| Legacy publish folder | `outputs/publish/runway_phase_i` |
| Checkpoint | `project_brain/runtime_state/runway_phase_i_checkpoint.json` (run_id now matches grafig run) |

## Validation results

```bash
python project_brain/validate_n_clip_post_processing_recovery.py
python project_brain/validate_live_post_processing_hook.py
```

Both pass.

Coverage:

1. 6 downloaded files + `total_downloads_completed=3` still eligible
2. Missing file blocks post-processing
3. Recovery command runs post-processing without Runway
4. Assembly handles 6 clips
5. Publish package created for 6 clips
6. Results ignores stale cat manifest for different run_id
7. Results ignores stale visual continuity for different run_id
8. Existing 2-clip post-processing still passes
9. No Runway automation changed

## Results API after recovery

- `latest_run_id`: `cb_e2e_20260610_201403_811da26d`
- `stored_manifest_run_id`: `cb_e2e_20260610_201403_811da26d`
- `stale_manifest_ignored`: false
- `post_processing_status`: completed
- `assembly_status`: ASSEMBLED
- `publish_status`: PUBLISHED_PACKAGE_CREATED
- `downloaded_clip_count`: 6

## Confirmation

Runway automation files (`runway_ui_navigator.py`, smoke test selectors/prompt builder hooks) were not modified. Changes are limited to post-processing eligibility, Results guards, recovery tooling, and validators.
