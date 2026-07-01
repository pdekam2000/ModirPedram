# PHASE AUTO YOUTUBE UPLOAD AFTER PUBLISH — REPORT

**Phase:** AUTO-YOUTUBE-UPLOAD-AFTER-PUBLISH  
**Date:** 2026-06-27  
**Validation:** `project_brain/validate_auto_youtube_upload_after_publish.py` — **13/13 PASS**

---

## Goal

After Web UI Create Video completes the publish chain (`FINAL_BRANDED_PUBLISH_READY.mp4` + `publish_package.json` with `publish_ready: true`), automatically upload to YouTube as **private** with `publish_now: true` and `confirmed: true`.

Generation pipeline (clip gen → download → assembly → metadata → branding) is unchanged; upload is appended as the final pipeline stage.

---

## Configuration

**File:** `project_brain/automation_center.json`

```json
{
  "version": "automation_center_youtube_v1",
  "youtube": {
    "auto_upload_enabled": true,
    "default_visibility": "private",
    "publish_now": true,
    "allow_public_auto_upload": false,
    "require_manual_public_approval": true
  }
}
```

**Loader:** `content_brain/automation/youtube_auto_upload_config.py`

Safety defaults match spec: private auto-upload on; public auto-upload blocked unless `allow_public_auto_upload` is explicitly set true.

---

## Implementation

### Auto-upload runtime

**New:** `content_brain/automation/auto_youtube_upload_after_publish.py`

- `evaluate_auto_youtube_upload_eligibility()` — gate checks before upload
- `maybe_auto_youtube_upload_after_publish()` — calls `run_youtube_upload_from_publish_package()` with:
  ```json
  { "confirmed": true, "visibility": "private", "publish_now": true }
  ```
- Writes `publish/youtube_upload_result.json` on success **and** on blocked attempts (except when `auto_upload_disabled`)

### Block conditions (never auto-upload)

| Reason code | Trigger |
|-------------|---------|
| `auto_upload_disabled` | Config off |
| `upload_blocked_visual_diversity` | Visual repetition failed / upload not allowed |
| `upload_blocked_missing_clips` | `source_clip_count < expected_clip_count` |
| `upload_blocked_publish_failed` | Assembly or branding failed |
| `publish_not_ready` | `publish_ready != true` |
| `metadata_missing` | No `youtube_metadata.json` |
| `oauth_not_available` | OAuth not authenticated |
| `public_upload_requires_manual_approval` | Visibility public/unlisted without `allow_public_auto_upload` |
| `publish_video_missing` | No branded final MP4 |

### Pipeline integration

**Updated:** `content_brain/execution/product_publish_pipeline_trace.py`

- Replaced skip-upload default with `attempt_auto_youtube_upload=True`
- After branding completes with `publish_ready: true`, invokes `maybe_auto_youtube_upload_after_publish()`
- Records `youtube_upload_runtime` stage: `completed`, `blocked`, `failed`, or `skipped`

**Updated:** `content_brain/execution/product_multiclip_orchestrator.py`

- Passes `visual_diversity` report into publish chain
- Merges upload fields into run artifacts (`youtube_upload_status`, `auto_upload_enabled`, etc.)
- Orchestrator version bumped to `product_multiclip_orchestrator_v3`

### Results UI + API

**Updated:** `ui/api/product_studio_service.py`, `ui/api/schemas/product_studio.py`, `ui/web/src/pages/ResultsPage.tsx`

YouTube Upload panel now shows:

- Auto upload enabled
- Upload started
- Upload status
- YouTube video ID / URL
- Visibility
- Upload time
- Blocked reason (when skipped/blocked)

### Startup diagnostics

**Updated:** `content_brain/platform/api_runtime_diagnostics.py`

- Exposes `auto_upload_enabled` from `project_brain/automation_center.json` in `/health` and startup logs

---

## Upload inputs used

| Input | Path |
|-------|------|
| Video | `publish/FINAL_BRANDED_PUBLISH_READY.mp4` |
| Metadata | `publish/youtube_metadata.json` |
| Package manifest | `publish/publish_package.json` |
| Result | `publish/youtube_upload_result.json` |

Private uploads pass `confirmed: true`, bypassing first-upload confirmation gate in `youtube_upload_runtime` without changing the upload runtime module itself.

---

## Validation summary

| Test | Result |
|------|--------|
| Private auto upload triggers after publish ready | PASS |
| Public auto upload blocked unless explicitly allowed | PASS |
| Visual diversity failure blocks upload | PASS |
| Missing publish package blocks upload | PASS |
| Missing OAuth blocks upload | PASS |
| Upload result JSON written | PASS |
| Results UI shows upload status fields | PASS |
| Generation pipeline unchanged (pwmap path preserved) | PASS |

Run validation:

```bash
python project_brain/validate_auto_youtube_upload_after_publish.py
```

---

## Operator notes

1. **Restart API** after deploy: `python -m ui.api.main`
2. OAuth must remain authorized (`project_brain/upload/youtube_auth_result.json`)
3. Next Create Video run with successful publish chain will auto-upload **private**
4. To upload an existing publish package manually:
   ```bash
   POST /upload/youtube/publish-package
   { "run_id": "<run_id>", "confirmed": true, "publish_now": true, "visibility": "private" }
   ```
5. To disable auto-upload, set `youtube.auto_upload_enabled: false` in `project_brain/automation_center.json`

---

## Files added / changed

| File | Role |
|------|------|
| `project_brain/automation_center.json` | **NEW** — YouTube auto-upload config |
| `content_brain/automation/youtube_auto_upload_config.py` | **NEW** — Config loader |
| `content_brain/automation/auto_youtube_upload_after_publish.py` | **NEW** — Eligibility + upload trigger |
| `content_brain/execution/product_publish_pipeline_trace.py` | Auto-upload after branding |
| `content_brain/execution/product_multiclip_orchestrator.py` | Pass diversity + merge upload fields |
| `content_brain/platform/api_runtime_diagnostics.py` | `auto_upload_enabled` diagnostic |
| `ui/api/product_studio_service.py` | Results enrichment |
| `ui/api/schemas/product_studio.py` | Response schema fields |
| `ui/web/src/pages/ResultsPage.tsx` | Upload panel UI |
| `project_brain/validate_auto_youtube_upload_after_publish.py` | **NEW** — 13-check validation |

---

*End of report.*
