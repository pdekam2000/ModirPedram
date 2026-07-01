# WEB CREATE VIDEO PUBLISH CHAIN REPAIR REPORT

**Phase:** WEB-CREATE-VIDEO-PUBLISH-CHAIN-REPAIR  
**Date:** 2026-06-27  
**Target run:** `pwmap_20260627T153920_b27a7273`

---

## Problem

Latest Web UI Create Video run completed clip generation, Use Frame continuity, and download verification, but stopped before assembly, branding, YouTube metadata, and upload. Root cause: the long-running API process (`python -m ui.api.main`) held stale orchestrator code in memory — merge/register ran, but the post-processing chain never executed.

---

## Fixes Implemented

### 1. Unified publish post-processing chain

**New module:** `content_brain/execution/product_publish_pipeline_trace.py`

- `run_publish_post_processing_chain()` — mandatory sequence after download verification:
  1. `product_assembly_bridge` (includes `youtube_metadata_generator` when `invoke_youtube_metadata=True`)
  2. `product_subtitle_branding_publish`
  3. YouTube upload marked **skipped** (`upload_not_auto_triggered`) — not auto-invoked from Create Video
- `repair_publish_chain_for_run()` — replays chain for existing runs
- Persists `pipeline_trace.json` per run with all 8 stages

**Updated:** `content_brain/execution/product_multiclip_orchestrator.py`

- Imports `ORCHESTRATOR_VERSION` (`product_multiclip_orchestrator_v2`)
- After merge + register, always calls `run_publish_post_processing_chain()`
- Writes pipeline trace + orchestrator version into `product_multiclip_runtime.json` and `normalized_result.json`

### 2. API startup diagnostics + version stamp

**New module:** `content_brain/platform/api_runtime_diagnostics.py`

- `api_build_id` — SHA256 fingerprint of key publish-chain source files (16 hex chars)
- `orchestrator_version`, `startup_time`
- Capability flags: `assembly_bridge_enabled`, `branding_publish_enabled`, `youtube_metadata_enabled`, `youtube_upload_enabled`
- Persisted to `project_brain/runtime_state/api_runtime_diagnostics.json`
- Logged on startup via `modiragent.api.diagnostics` logger

**Updated:** `ui/api/main.py`

- `@app.on_event("startup")` → `init_api_runtime_diagnostics()`
- `GET /health` — exposes build id, orchestrator version, capability flags, `api_process_stale`
- `GET /platform/runtime-diagnostics` — live vs expected build comparison

### 3. Results UI + API enrichment

**Updated:** `ui/api/product_studio_service.py`

- Fixed bug: `_merge_pwmap_results` was overwriting `assembly_status` with `"PWMAP_AGENT"`
- Merges `pipeline_trace`, `stop_stage`, `last_completed_stage`, `api_runtime_diagnostics`
- Surfaces stale-server detection (`api_process_stale`)

**Updated:** `ui/api/schemas/product_studio.py`, `ui/web/src/pages/ResultsPage.tsx`

- New **Publish Chain Trace** panel: API build id, orchestrator version, capability flags, per-stage status
- Stale API warning when `api_process_stale === true`

### 4. Repair tooling

| Script | Purpose |
|--------|---------|
| `project_brain/repair_publish_chain_for_run.py` | CLI repair for stuck runs |
| `project_brain/validate_web_create_video_publish_chain_repair.py` | 31-check validation suite |

---

## Validation — Run `pwmap_20260627T153920_b27a7273`

Repair executed:

```bash
python project_brain/repair_publish_chain_for_run.py --run-id pwmap_20260627T153920_b27a7273
```

**Result:** `31/31 PASS`

### Publish artifacts (now present)

| Artifact | Path | Status |
|----------|------|--------|
| `FINAL_PUBLISH_READY.mp4` | `publish/FINAL_PUBLISH_READY.mp4` | ✅ |
| `FINAL_BRANDED_PUBLISH_READY.mp4` | `publish/FINAL_BRANDED_PUBLISH_READY.mp4` | ✅ |
| `youtube_metadata.json` | `publish/youtube_metadata.json` | ✅ |
| `publish_package.json` | `publish/publish_package.json` | ✅ |
| `pipeline_trace.json` | run root | ✅ |

### Pipeline trace summary

| Stage | Status |
|-------|--------|
| story_planning | completed |
| clip_generation | completed |
| use_frame_chain | completed |
| download_verification | completed |
| assembly_bridge | completed |
| youtube_metadata_generation | completed |
| subtitle_branding_publish | completed |
| youtube_upload_runtime | **skipped** (upload_not_auto_triggered) |

- **last_completed_stage:** `subtitle_branding_publish`
- **stop_stage:** *(empty — publish chain complete)*
- **pipeline_complete:** `true`

### Upload policy (unchanged)

- **No auto-upload** from Create Video (`youtube_upload_result.json` absent — correct)
- Channel profile: `youtube_privacy: private`, `youtube_require_confirmation: true`
- Manual upload via `POST /upload/youtube/publish-package` with `confirmed: true` when ready

---

## Operator Actions

1. **Restart API server** so live process loads repaired orchestrator:
   ```bash
   python -m ui.api.main
   ```
2. Verify startup log lines include `api_build_id=... assembly_bridge_enabled=True ...`
3. Check `GET /health` — confirm `api_process_stale: false`
4. Future Create Video runs will auto-chain assembly → branding → metadata
5. For any run stuck before this fix: `python project_brain/repair_publish_chain_for_run.py --run-id <run_id>`

---

## Files Changed / Added

| File | Change |
|------|--------|
| `content_brain/execution/product_publish_pipeline_trace.py` | **NEW** — trace + chain + repair |
| `content_brain/platform/api_runtime_diagnostics.py` | **NEW** — startup diagnostics |
| `content_brain/execution/product_multiclip_orchestrator.py` | Wired publish chain + trace |
| `ui/api/main.py` | Startup diagnostics, `/health`, `/platform/runtime-diagnostics` |
| `ui/api/product_studio_service.py` | Pipeline trace in results; fixed assembly_status override |
| `ui/api/schemas/product_studio.py` | New response fields |
| `ui/web/src/pages/ResultsPage.tsx` | Publish Chain Trace panel |
| `project_brain/repair_publish_chain_for_run.py` | **NEW** — repair CLI |
| `project_brain/validate_web_create_video_publish_chain_repair.py` | **NEW** — validation |

---

*End of report.*
