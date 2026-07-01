# UPLOAD FORENSIC LIVE REPORT

**Phase:** UPLOAD-FORENSIC-LIVE  
**Mode:** Read-only forensic (no code changes, no regeneration, no upload)  
**Generated:** 2026-06-27  
**Investigator scope:** Latest Web UI **Create Video** run → YouTube upload outcome

---

## Executive Summary

The latest Web UI Create Video run **completed clip generation, Use Frame chaining, download verification, and FFmpeg merge**, but **never reached assembly, subtitle/branding publish, YouTube metadata generation, or YouTube upload**. No `publish/` folder exists for this run. YouTube upload was **never triggered** — there is no upload attempt artifact and Create Video does not auto-chain upload.

**Verdict:**

```
LATEST_RUN_STOPPED_AT: download_verification
UPLOAD_STATUS: not_triggered
ROOT_CAUSE: upload_blocked_publish_failed + upload_not_triggered + auto_upload_disabled
NEXT_ACTION: Restart API to load full post-merge pipeline → run assembly/branding/metadata for this run → manually POST /upload/youtube/publish-package (or enable auto_upload)
```

---

## 1. Latest Web UI Create Video Run

| Field | Value |
|-------|-------|
| **run_id** | `pwmap_20260627T153920_b27a7273` |
| **topic** | Short, unsettling stories blending analog horror aesthetics with dark fantasy elements |
| **creation time** | Run ID timestamp **2026-06-27T15:39:20 UTC** (`job.json` written at local 17:39:20) |
| **finish time** | **2026-06-27T16:06:04.702924+00:00** (`agent_result.json`, `execution_report.json`) |
| **duration target** | **30 seconds** (`requested_duration_seconds: 30`, `final_video_duration_seconds: 30.13`) |
| **provider used** | **kling_3_0_pro_native_audio** via **pwmap_agent** runtime (`execution_mode: use_frame_chain`) |
| **clip count planned** | **2** (`multiclip_execution_plan.clip_count: 2`) |
| **clip count completed** | **2** (`agent_result.json` — both clips valid) |

### Identification method

- Newest folder under `outputs/pwmap_agent_runs/` by mtime: `pwmap_20260627T153920_b27a7273` (2026-06-27 18:06:04 local).
- Confirmed by `project_brain/runtime_state/latest_run_attempt.json` pointing to the same `run_id`.
- API terminal log shows `POST /product/create-video/generate` → FFmpeg stitch for this run folder.

### Run folder

`C:/Users/kaman/Desktop/ModirAgentOS/outputs/pwmap_agent_runs/pwmap_20260627T153920_b27a7273/`

**Present artifacts:** `clip_1.mp4`, `clip_2.mp4`, `video.mp4`, `video_merged.mp4`, `job.json`, `agent_result.json`, `execution_report.json`, `normalized_result.json`, `product_multiclip_runtime.json`, `last_result.json`, `subprocess_stdout.log`

**Absent artifacts:** `publish/` directory, `visual_diversity_report.json`, assembly/branding fields in persisted JSON

### Data inconsistency note

`latest_run_attempt.json` reports `clips_completed: 3` and lists `video.mp4` as a third downloaded clip path. On-disk evidence shows **2 clip files** plus a merged `video.mp4` (stitched output, not a third generated clip). Authoritative clip count: **2** from `agent_result.json` and `product_multiclip_runtime.json`.

---

## 2. Stage Progression — Last Successful Stage

| Stage | Status | Evidence |
|-------|--------|----------|
| **story_planning** | ✅ Completed | `normalized_result.json` → `preflight_snapshot`, `story_progression`, 2 Kling story-first prompts in `job.json` / `multiclip_execution_plan` |
| **clip_generation** | ✅ Completed | `clip_1.mp4`, `clip_2.mp4` (20,099,478 bytes each); `finalization_stages.clips_generated.status: completed` |
| **use_frame_chain** | ✅ Completed | Clip 2 `used_frame_from_previous: true`; `execution_mode: use_frame_chain` |
| **download_verification** | ✅ Completed | `finalization_stages.downloads_verified.status: completed`, `valid_clip_count: 2`, `missing_paths: []` |
| **assembly_bridge** | ❌ Not reached | No `publish/` folder; no `assembly_status` / `assembly_manifest.json`; `normalized_result.json` has no assembly fields |
| **subtitle_branding_publish** | ❌ Not reached | No `FINAL_BRANDED_PUBLISH_READY.mp4`; no `publish_package.json` |
| **youtube_metadata_generation** | ❌ Not reached | No `publish/youtube_metadata.json` |
| **youtube_upload_runtime** | ❌ Not reached | No `publish/youtube_upload_result.json`; no API upload call logged |

### Additional sub-stage (not in enum)

**FFmpeg merge (`merge_complete`):** ✅ Completed — `video_merged.mp4` and `product_multiclip_runtime.json` → `generation_state: merge_complete`. This occurs in the orchestrator **after** download verification and **before** assembly_bridge.

### Last successful stage (from required enum)

**`download_verification`**

(`merge_complete` succeeded but is outside the requested stage list.)

### Finalization pointer

`agent_result.json` → `finalization_stage: browser_closed` (pwmap agent finalization only; does not include post-merge Product Studio assembly).

---

## 3. Publish Artifact Verification

Run directory: `outputs/pwmap_agent_runs/pwmap_20260627T153920_b27a7273/`

| Artifact | Expected path | Exists |
|----------|---------------|--------|
| `FINAL_PUBLISH_READY.mp4` | `publish/FINAL_PUBLISH_READY.mp4` | **NO** — `publish/` directory missing |
| `FINAL_BRANDED_PUBLISH_READY.mp4` | `publish/FINAL_BRANDED_PUBLISH_READY.mp4` | **NO** |
| `youtube_metadata.json` | `publish/youtube_metadata.json` | **NO** |
| `publish_package.json` | `publish/publish_package.json` | **NO** |
| `youtube_upload_result.json` | `publish/youtube_upload_result.json` | **NO** |

**All five publish artifacts are missing.**

---

## 4. Why Upload Did Not Happen

### Classification

| Reason code | Applies | Detail |
|-------------|---------|--------|
| **upload_not_triggered** | ✅ Primary | No `POST /upload/youtube/publish-package` call logged for this run after generation |
| **upload_blocked_publish_failed** | ✅ Primary | Publish package never built — upload runtime requires `publish/` with branded video + metadata |
| **auto_upload_disabled** | ✅ Contributing | `feature_flags.auto_upload` defaults to `false`; no `project_brain/platform/automation_center.json` on disk |
| **metadata_missing** | ✅ Consequence | No `youtube_metadata.json` because metadata step never ran |
| upload_disabled | ❌ | `youtube_upload_enabled: true` in channel profile |
| oauth_not_available | ❌ | OAuth authorized (`youtube_auth_result.json`, channel **Lost Signal HD**) |
| upload_blocked_visual_diversity | ❌ | No visual diversity failure; no `visual_diversity_report.json` (guard may not have run — see §8) |
| upload_blocked_missing_clips | ❌ | Both clips present and verified |
| youtube_runtime_exception | ❌ | Upload runtime never invoked for this run |

### Causal chain

1. Create Video completed pwmap generation + merge.
2. Post-merge pipeline (assembly → branding → metadata) **did not produce artifacts** for this run.
3. Create Video endpoint **does not** call YouTube upload on success (`create_video_generate` returns pwmap result only).
4. `auto_upload` is **disabled** in automation defaults.
5. Therefore upload was **never attempted** and **could not succeed** without a publish package.

---

## 5. Upload Configuration

Sources: `project_brain/product_settings/channel_profile.json`, `content_brain/platform/automation_center_store.py` (defaults — no persisted `automation_center.json` file)

| Setting | Value | Source |
|---------|-------|--------|
| **auto_upload_enabled** | **false** | `DEFAULT_STATE.feature_flags.auto_upload: false`; file `project_brain/platform/automation_center.json` **not found** |
| **require_manual_approval** | **true** | `youtube_require_confirmation: true` (channel profile) |
| **default_visibility** | **private** | `youtube_privacy: private` |
| **publish_now** | **not set for this run** | Would default to `true` if upload API invoked (`run_youtube_upload_from_publish_package` default) |
| **scheduled_publish** | **not set** | No `youtube_publish_at` in profile; no schedule payload for this run |

### YouTube readiness (not blocking — for context)

| Setting | Value |
|---------|-------|
| `youtube_upload_enabled` | true |
| `youtube_upload_confirmed` | true |
| `youtube_credentials_configured` | true |
| OAuth authorized | true (`project_brain/upload/youtube_auth_result.json`, `token_refresh_verified: true`) |
| Channel | Lost Signal HD (`UCtBjz0YpU_3LG6pci6C-VXg`) |

Upload credentials and profile flags are **ready**; the blocker is missing publish package + no upload trigger.

---

## 6. Upload Runtime Logs (Latest Run)

| Metric | Value |
|--------|-------|
| **Upload attempt count** | **0** |
| **Last upload timestamp** | **N/A** (no artifact for this run) |
| **Last upload error** | **N/A** (runtime never invoked) |

### API access log

Terminal `1.txt` (API server `python -m ui.api.main`):

- `POST /product/create-video/generate` → FFmpeg stitch → `202 Accepted`
- **No** `POST /upload/youtube/publish-package` entries for `pwmap_20260627T153920_b27a7273`

### Prior run reference (not latest)

Run `pwmap_20260627T104052_f462d50b` (earlier same day) has a complete `publish/` folder and `youtube_upload_result.json` with `upload_status: uploaded`, `youtube_video_id: Oa9XDEPHT4s` — from a **manual** upload smoke test, not from Create Video auto-upload.

---

## 7. Final Verdict

```
LATEST_RUN_STOPPED_AT:
  download_verification
  (merge_complete also succeeded; assembly_bridge never started)

UPLOAD_STATUS:
  not_triggered

ROOT_CAUSE:
  upload_blocked_publish_failed
  + upload_not_triggered
  + auto_upload_disabled

NEXT_ACTION:
  1. Restart API server (python -m ui.api.main) so post-merge orchestrator
     (assembly → subtitle/branding → metadata) loads current code.
  2. Run assembly + branding + metadata for run pwmap_20260627T153920_b27a7273
     (or re-trigger post-processing if a repair endpoint exists).
  3. Manually trigger upload:
     POST /upload/youtube/publish-package
     { "run_id": "pwmap_20260627T153920_b27a7273", "confirmed": true, "publish_now": true }
  4. Optional: enable auto_upload in Automation Center if post-generation
     upload should happen without manual API calls.
```

---

## 8. Supporting Forensic Observations

### Post-merge pipeline gap

Current source (`content_brain/execution/product_multiclip_orchestrator.py`) calls `run_product_assembly_bridge` **after** merge and register. For this run:

- `product_multiclip_runtime.json` stops at merge fields only.
- `normalized_result.json` was updated with merge info but **not** with `assembly_status`, `publish_package_path`, or branding fields (second update block never persisted).
- API returned `202 Accepted` immediately after FFmpeg stitch log lines — no assembly/branding log output.

**Likely explanation:** API server process was running **stale orchestrator code** (pre-assembly wiring) or terminated between merge persistence and assembly invocation. Restarting the API before the next Create Video run is recommended.

### Visual diversity guard

No `visual_diversity_report.json` in the run folder. Current orchestrator saves this **before** merge. Absence supports stale-server hypothesis; this did **not** block upload for this run because upload was never attempted.

### Generation performance

- Wall time: **1604.53 seconds** (~26.7 minutes) per `product_multiclip_runtime.json`
- Provider: Kling 3.0 Pro native audio, 9:16, 2×15s clips with Use Frame on clip 2

---

## Appendix — Key File References

| File | Role |
|------|------|
| `outputs/pwmap_agent_runs/pwmap_20260627T153920_b27a7273/agent_result.json` | pwmap finalization stages |
| `outputs/pwmap_agent_runs/pwmap_20260627T153920_b27a7273/product_multiclip_runtime.json` | merge + plan snapshot |
| `project_brain/runtime_state/latest_run_attempt.json` | runtime registry pointer |
| `project_brain/product_settings/channel_profile.json` | upload + privacy settings |
| `project_brain/upload/youtube_auth_result.json` | OAuth state |
| `ui/api/main.py` | Create Video + upload endpoints (upload is separate POST) |

---

*End of report — read-only forensic; no system state modified.*
