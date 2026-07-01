# PHASE ASSET-LIBRARY-1 — Final Video Asset Vault

**Status:** Complete  
**Date:** 2026-06-03  
**Scope:** Permanent vault for publish-ready `FINAL_BRANDED_VIDEO.mp4` files without altering `outputs/runs/` layout.

---

## Goal

Every upload-ready final branded video is automatically copied into a dedicated Asset Library under `assets/videos/{category}/`, indexed in `assets/asset_index.json`, and never overwritten.

---

## Vault Structure

```
assets/
├── asset_index.json
├── videos/
│   ├── cartoon/
│   ├── wildlife/
│   ├── technology/
│   ├── history/
│   └── other/
├── youtube_shorts/
├── tiktok/
├── instagram/
├── cartoon/
├── wildlife/
├── technology/
├── history/
└── archive/
```

Platform and top-level category folders are created up front. Canonical video storage is `assets/videos/{category}/`.

---

## Registration Trigger

Registration runs from `finalize_versioned_run_layout()` when:

- `publish_status == PUBLISHED_PACKAGE_CREATED`
- `FINAL_BRANDED_VIDEO.mp4` exists (publish or final folder)
- `asset_vault_enabled` is true in channel profile

**Module:** `content_brain/platform/asset_library.py`  
**Hook:** `content_brain/platform/run_output_versioning.py`

---

## Copy Behavior

| Setting | Behavior |
|---------|----------|
| `asset_copy_mode: copy` (default) | `shutil.copy2` into vault; run folder unchanged |
| `asset_copy_mode: move` | Same copy into vault; run folder still preserved |

Run folders under `outputs/runs/` are never modified or removed.

---

## Naming

Pattern: `{YYYYMMDD_HHMMSS}_{topic_slug}.mp4`  
Collision handling: `_v2`, `_v3`, … — never overwrite.

---

## Deduplication

SHA256 checksum of source video is stored on each asset record. Re-registration (recovery reruns, duplicate finalize calls) returns `duplicate_skipped` and does not add a second index row.

---

## Asset Index Fields

Each record in `assets/asset_index.json` includes:

- `asset_id`, `run_id`, `topic`, `category`, `creation_time`
- `source_run_folder`, `final_video_path`, `checksum_sha256`
- `duration`, `duration_seconds`, `clip_count`
- `branding_enabled`, `narration_enabled`, `music_enabled`

Category auto-classification uses topic + channel profile keywords (`cartoon`, `wildlife`, `technology`, `history`, `other`).

---

## UI

| Surface | Change |
|---------|--------|
| **Results** | Asset Library card — Open Asset Library (copies vault path), Latest Assets list |
| **Settings** | Asset Library accordion — Enable Asset Vault, Asset copy mode |
| **API** | `GET /product/assets/library` |

---

## Validation

```bash
python project_brain/validate_asset_library_v1.py
```

Tests cover folder creation, copy, no-overwrite suffixes, index updates, checksum dedup, recovery idempotency, category assignment, results/API wiring, run folder preservation, and metadata shape.

---

## Success Criteria

| Criterion | Result |
|-----------|--------|
| Finished upload-ready videos saved to `assets/videos/` | Yes — auto on publish finalize |
| Older videos never overwritten | Yes — unique names + checksum dedup |
| `outputs/runs/` structure intact | Yes — copy-only from source |
| Settings toggle + copy mode | Yes |
| Results shows latest assets | Yes |
| Recovery does not duplicate assets | Yes — SHA256 guard |

---

## Files Touched

- `content_brain/platform/asset_library.py` (new)
- `content_brain/platform/run_output_versioning.py`
- `content_brain/platform/results_run_loader.py`
- `content_brain/product_settings/channel_profile_store.py`
- `ui/api/product_studio_service.py`
- `ui/api/schemas/product_studio.py`
- `ui/api/main.py`
- `ui/web/src/api/productClient.ts`
- `ui/web/src/pages/ResultsPage.tsx`
- `ui/web/src/pages/SettingsPage.tsx`
- `ui/web/src/App.css`
- `project_brain/validate_asset_library_v1.py`
- `project_brain/PHASE_ASSET_LIBRARY_1_REPORT.md`

---

## Not Changed

Runway automation, selectors, browser automation, provider router, Visual Memory, AI Director V2, Upload Center, Automation Center.
