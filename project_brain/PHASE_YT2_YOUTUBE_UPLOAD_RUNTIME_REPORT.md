# PHASE YT-2 — YouTube OAuth + Upload Runtime Report

**Phase:** `YT-2`  
**Date:** 2026-06-27  
**Scope:** OAuth authentication, resumable YouTube upload, metadata mapping, optional thumbnail, visibility/scheduling, results surfacing. No changes to generation pipeline modules.

---

## Goal

Upload completed branded publish videos to YouTube automatically with zero manual metadata entry, using artifacts from the publish pipeline:

- `publish/FINAL_BRANDED_PUBLISH_READY.mp4` (fallback: `FINAL_PUBLISH_READY.mp4`)
- `publish/youtube_metadata.json`
- `publish/publish_package.json`

---

## Delivered

### New / extended modules

| Module | Role |
|--------|------|
| `content_brain/upload/youtube_auth.py` (v2) | OAuth client resolution, token storage, refresh, channel info (`youtube_account_id`, `channel_id`, `channel_name`) |
| `content_brain/upload/youtube_uploader.py` (v2) | Resumable upload, metadata body, `publishAt` scheduling, thumbnail upload |
| `content_brain/upload/youtube_category_map.py` | Category name → YouTube `categoryId` |
| `content_brain/upload/youtube_upload_runtime.py` | Publish-package orchestrator; writes `youtube_upload_result.json` |
| `ui/api/upload_service.py` | `submit_publish_package_upload()`, `get_publish_upload_result()` |
| `ui/api/main.py` | `POST /upload/youtube/publish-package`, `GET /upload/youtube/result` |
| `ui/web/src/pages/ResultsPage.tsx` | YouTube Upload panel (status, URL, video id, visibility, schedule time) |

### OAuth storage

```
project_brain/upload/
  youtube_oauth_token.json    ← access + refresh tokens
  youtube_account.json        ← youtube_account_id, channel_id, channel_name
```

Supports reconnect via existing auth start/exchange endpoints and automatic token refresh via `refresh_access_token()`.

### Upload runtime flow

1. Resolve branded video from publish folder (branded → unbranded fallback).
2. Load `youtube_metadata.json` and map title, description, tags, category, language, hashtags.
3. Verify OAuth + channel profile settings (confirmation gate when configured).
4. Upload video via YouTube Data API (resumable).
5. Optionally upload thumbnail from `publish/thumbnail.{jpg,png,webp}` — skipped safely when missing.
6. Write `publish/youtube_upload_result.json`.

### Visibility & scheduling

| Mode | Behavior |
|------|----------|
| `private` / `unlisted` / `public` | Applied via `status.privacyStatus` |
| `publish_now` | Immediate publish (subject to privacy) |
| `publish_at` / `publish_at_datetime` | Sets `status.publishAt` (RFC3339 UTC); upload status `scheduled` |

### Upload result schema

`publish/youtube_upload_result.json`:

```json
{
  "uploaded": true,
  "upload_status": "uploaded",
  "youtube_video_id": "abc123xyz",
  "youtube_url": "https://www.youtube.com/watch?v=abc123xyz",
  "visibility": "private",
  "publish_time": "2026-07-01T18:00:00.000Z",
  "upload_time": "2026-06-27T11:00:00.000Z"
}
```

On failure: `uploaded: false`, `upload_status: "upload_failed"` — publish package, branded video, and metadata are preserved unchanged.

### API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /upload/youtube/auth/status` | OAuth + channel connection status |
| `POST /upload/youtube/auth/start` | Begin OAuth flow |
| `POST /upload/youtube/auth/exchange` | Exchange auth code; store channel info |
| `POST /upload/youtube/publish-package` | Upload from publish folder |
| `GET /upload/youtube/result?run_id=...` | Read upload result |

Example publish-package request:

```json
{
  "run_id": "pwmap_agent_runs_...",
  "publish_package_path": "outputs/pwmap_agent_runs/<run_id>/publish",
  "confirmed": true,
  "visibility": "private",
  "publish_now": false,
  "publish_at": "2026-07-01T18:00:00.000Z"
}
```

### Results integration

`pwmap_finalization.build_pwmap_results_payload()` and `product_studio_service._merge_pwmap_results()` load `youtube_upload_result.json` and expose:

- `youtube_upload_status`
- `youtube_video_id`
- `youtube_url`
- `youtube_visibility`
- `youtube_publish_time`
- `youtube_upload_time`

---

## Not modified (by design)

- Product Studio orchestration (no auto-upload on generation)
- pwmap generation / Use Frame / browser mappings
- Assembly bridge
- Subtitle / branding runtime
- YouTube metadata generator (`content_brain/publish/youtube_metadata_generator.py`)

Upload is on-demand via Upload Center API — decoupled from the generation pipeline.

---

## Validation

**Script:** `project_brain/validate_youtube_upload_runtime.py`

| Test | Result |
|------|--------|
| OAuth login works | PASS |
| Token refresh works | PASS |
| Upload works | PASS |
| Metadata mapping works | PASS |
| Thumbnail upload optional | PASS |
| Scheduling works | PASS |
| Upload failure handled safely | PASS |
| Results page shows upload status | PASS |
| No generation pipeline modified | PASS |

**Total: 15/15 PASS**

Run:

```bash
python project_brain/validate_youtube_upload_runtime.py
```

---

## Publish folder layout (full pipeline)

```
outputs/pwmap_agent_runs/<run_id>/publish/
  FINAL_PUBLISH_READY.mp4
  FINAL_BRANDED_PUBLISH_READY.mp4
  assembly_manifest.json
  publish_metadata.json
  branding_manifest.json
  publish_package.json
  youtube_metadata.json
  youtube_upload_result.json   ← YT-2 output
```

---

## Next recommended phase

**PHASE ANALYTICS-FEEDBACK-LOOP**

- Views, CTR, retention, watch time
- Likes, comments, subscriber conversion
- Prompt optimization feedback loop
