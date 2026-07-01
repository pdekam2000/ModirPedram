# Storage Cleanup Plan

Generated: 2026-06-13T09:26:07.267022+00:00

> **DO NOT DELETE YET.** This plan is advisory only.

## Current project size

**344.98 GB** (370,415,519,079 bytes)

## Estimated reclaimable

**14.08 GB** total heuristic reclaimable

- SAFE_TO_DELETE: 41.49 MB
- LIKELY_SAFE: 14.04 GB
- REVIEW_REQUIRED (manual): 53.64 MB

## Largest consumers

1. `storage/backups` — 319.23 GB
2. `chrome_mapper_profile` — 4.53 GB
3. `outputs/runs` — 386.26 MB
4. `debug` — 38.46 MB
5. `downloads/runway` — 480.88 KB
6. `project_brain/runtime_state` — 218.23 KB
7. `project_brain/archive` — 50.68 KB

## Potential safe cleanup (phased)

1. Remove Python caches and bytecode — est. 41.49 MB
2. Archive or relocate `chrome_mapper_profile/` browser automation cache — est. 4.53 GB (**LIKELY_SAFE**, confirm not needed for active sessions)
3. Prune old `debug/` forensic frames after review — est. 77.33 MB
4. Deduplicate exact SHA256 copies (keep registry + latest run copies) — est. 9.51 GB

## Branded video supersession

- Folder `c:\users\kaman\desktop\modiragentos\archive\legacy_outputs\20260611_235927_308_dc20bc1f\final`
  - Keep newest: `archive/legacy_outputs/20260611_235927_308_dc20bc1f/final/FINAL_BRANDED_VIDEO_v3.mp4`
  - Review for archive: archive/legacy_outputs/20260611_235927_308_dc20bc1f/final/FINAL_BRANDED_VIDEO.mp4, archive/legacy_outputs/20260611_235927_308_dc20bc1f/final/FINAL_BRANDED_VIDEO_v2.mp4
- Folder `c:\users\kaman\desktop\modiragentos\archive\legacy_outputs\20260611_235927_308_dc20bc1f\publish`
  - Keep newest: `archive/legacy_outputs/20260611_235927_308_dc20bc1f/publish/FINAL_BRANDED_VIDEO_v3.mp4`
  - Review for archive: archive/legacy_outputs/20260611_235927_308_dc20bc1f/publish/FINAL_BRANDED_VIDEO.mp4, archive/legacy_outputs/20260611_235927_308_dc20bc1f/publish/FINAL_BRANDED_VIDEO_v2.mp4

## DO NOT DELETE without explicit approval

- `project_brain/runtime_state/final_delivery_registry.json` targets
- Latest approved run: `outputs/runs/20260613_091042_148bc322/`
- `content_brain/`, `ui/`, active manifests in `project_brain/runtime_state/`
- Only copy of a unique SHA256 artifact

## Next phase (not executed here)

1. Human review of REVIEW_REQUIRED buckets
2. Move (not delete) superseded branded videos to `archive/legacy_outputs/`
3. Relocate `chrome_mapper_profile` outside repo if automation allows
4. Re-run this scanner and compare reclaim estimates
