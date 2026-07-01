# CONTINUITY DIRECTOR LIVE FIX 2 REPORT

Generated: 2026-06-20

## Problems addressed

| Run | Issue |
|-----|-------|
| `kling_ft_20260620T195250_dda55406` | `ValueError: starter_image_prompt does not match topic keywords` before execution |
| `kling_ft_20260620T201036_f84cdcd8` | Clip 1 generated; chain stopped at `mp4_missing_or_invalid` without full recovery |

## Fixes

### 1. Topic Guard alignment (smoke-only payload)

- Added `ensure_kling_frame_metadata_for_plan()` in `agents/continuity_director_agent.py`
- Builds `starter_image_prompt` via `build_kling_starter_image_prompt()` from plan topic/mood/environment
- Falls back to story topic text if keyword match fails
- Writes `outputs/kling_frame_to_video/<run_id>/starter_frame/starter_frame_prompt.json`
- Called automatically at `run_chain()` start and explicitly in smoke runner
- Topic Guard **not** disabled globally — clip 2 PNG upload now passes validation

### 2. Real MP4 resolution after Clip 1

- Added `resolve_real_clip_mp4()` — checks in order:
  1. Inline generation path / live payload paths
  2. `outputs/kling_frame_to_video/<run_id>/clips/cN/clip_N.mp4`
  3. `video.mp4` in live + agent clip dirs
  4. Existing `mp4_extract_report.json`
  5. `recover_kling_frame_output` / KlingRealMp4DownloadExtractor
  6. Post-recovery path re-check
- Uses `verify_extracted_kling_mp4` (>1MB, MP4 container, ffprobe, duration ≥ 5s)
- Stores `mp4_recovery_audit` on each clip result (methods, quarantine, failure reason)

### 3. Hook updates

- `build_frame_live_generate_hook(topic=...)` passes story topic to live engine
- `build_frame_live_recover_hook(project_root=...)` reuses existing `clip_N.mp4` before live recovery

### 4. Smoke report fields

- Topic Guard passed
- Extractor methods attempted per clip
- Quarantine paths
- Final MP4 path / failure reason

## Validation

```bash
python project_brain/validate_continuity_director_live_fix_2.py
```

Tests:
- starter_image_prompt matches topic keywords
- smoke payload passes Topic Guard
- existing recovered MP4 reused without recovery call
- recovery called when MP4 missing after generation
- fake MP4 rejected
- last frame extracted from valid MP4
- clip 2 starts after valid PNG
- recover hook does not click Generate

## Files changed

| File | Change |
|------|--------|
| `agents/continuity_director_agent.py` | metadata ensure, `resolve_real_clip_mp4`, audit fields, hook updates |
| `project_brain/run_continuity_director_v1_live_smoke.py` | topic metadata, topic in generate hook, enriched report |
| `project_brain/validate_continuity_director_live_fix_2.py` | **New** validation |

## Re-run live smoke

```bash
python project_brain/run_continuity_director_v1_live_smoke.py
```

Expected flow: Clip 1 generate → extractor recovery if needed → last-frame PNG → Clip 2 upload → Clip 2 generate.
