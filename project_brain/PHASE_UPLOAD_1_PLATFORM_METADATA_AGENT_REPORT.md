# PHASE UPLOAD-1 — Platform Upload Agent + Metadata Agent Report

## Summary

PHASE UPLOAD-1 adds a real upload preparation workflow for YouTube Shorts, TikTok, and Instagram Reels. The system now generates platform-specific metadata, builds per-platform upload packages under versioned run folders, exposes an Upload Center UI, and supports gated YouTube OAuth upload (private by default, confirmation required). TikTok and Instagram remain manual-upload only in V1.

Runway automation, Director/Critic, Assembly, Branding, and Visual verifier were not modified.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/upload/platform_metadata_agent.py` | OpenAI-primary metadata generation with rule-based fallback |
| `content_brain/upload/upload_package_builder.py` | Per-platform upload folders under `outputs/runs/<run_id>/upload/` |
| `content_brain/upload/youtube_auth.py` | OAuth client resolution, token storage, auth status |
| `content_brain/upload/youtube_uploader.py` | YouTube Data API resumable upload (private default) |
| `ui/api/upload_service.py` | Upload Center API service |
| `ui/web/src/pages/UploadCenterPage.tsx` | Upload Center UI page |
| `project_brain/validate_upload_agent_v1.py` | Upload agent validation suite |

## Files Updated

| File | Change |
|------|--------|
| `content_brain/upload/upload_manager.py` | Orchestrates metadata + package builder + YouTube submit v2 |
| `content_brain/comments/comment_agent.py` | `draft_pinned_comments_from_metadata()` |
| `content_brain/automation/automation_job_runner.py` | Calls `prepare_full_upload_workflow()` after publish |
| `content_brain/product_settings/channel_profile_store.py` | YouTube OAuth / kids / confirmation settings |
| `ui/api/automation_service.py` | Uses full upload workflow on `/upload/prepare` |
| `ui/api/main.py` | Upload Center routes |
| `ui/api/schemas/platform.py` | Upload Center request/response schemas |
| `ui/api/schemas/product_studio.py` | Extended channel profile fields |
| `ui/api/product_studio_service.py` | Persist new YouTube settings |
| `ui/api/dependencies.py` | `get_upload_service()` |
| `ui/web/src/App.tsx` | Upload Center nav entry |
| `ui/web/src/product/constants.ts` | `upload` nav item |
| `ui/web/src/api/platformClient.ts` | Upload Center API client |
| `ui/web/src/pages/SettingsPage.tsx` | YouTube OAuth path / kids / confirmation UI |
| `content_brain/upload/__init__.py` | Export new upload modules |

---

## Platform Metadata Examples (rule-based fallback)

### YouTube Shorts

```json
{
  "title": "gpu review topic",
  "description": "gpu review topic\n\nFollow My Channel for more selfcare.",
  "hashtags": ["#shorts", "#viral"],
  "tags": ["gpu", "review", "shorts", "shortvideo", "topic"],
  "category": "Science & Technology",
  "privacy": "private",
  "thumbnail_text": "gpu review topic",
  "pinned_comment": "Thanks for watching! What should we cover next about gpu review topic?"
}
```

### TikTok

```json
{
  "caption": "Skincare routine — follow for more beauty.",
  "hashtags": ["#fyp", "#foryou", "#viral", "#skincare", "#routine"],
  "cover_text": "Skincare routine",
  "hook_text": "POV: Skincare routine",
  "pinned_comment": "What part of Skincare routine should we explain next?"
}
```

### Instagram Reels

```json
{
  "caption": "Morning routine\n\nFollow for more",
  "hashtags": ["#reels", "#explore", "#morning", "#routine"],
  "alt_text": "Short video about Morning routine from Glow.",
  "cover_text": "Morning routine",
  "pinned_comment": "Save this reel if Morning routine is useful — what should we post next?"
}
```

---

## Upload Package Structure

```
outputs/runs/<run_id>/upload/
├── upload_manifest.json
├── metadata/platform_metadata.json
├── youtube_pinned_comment.txt
├── tiktok_pinned_comment.txt
├── instagram_pinned_comment.txt
├── youtube/
│   ├── video.mp4
│   ├── metadata.json
│   ├── caption.txt
│   ├── hashtags.txt
│   ├── youtube_pinned_comment.txt
│   └── upload_readme.md
├── tiktok/
│   └── (same file set)
└── instagram/
    └── (same file set)
```

Legacy compatibility packages remain at `outputs/upload_packages/<run_slug>/upload_package.json`.

---

## YouTube Upload Status (V1)

| Setting | Default |
|---------|---------|
| Enabled | Off (`youtube_upload_enabled: false`) |
| Privacy | `private` |
| Made for kids | `false` |
| Confirmation required | `true` |
| Auto-upload | Off |

Behavior:

- If YouTube upload is disabled → blocked
- If confirmation not given → `confirmation_required`
- If OAuth client/token missing → `youtube_connect_required` / `youtube_credentials_missing`
- If authenticated + confirmed → resumable upload via YouTube Data API v3
- OAuth token stored at `project_brain/upload/youtube_oauth_token.json`
- OAuth client path configurable via Settings (`youtube_oauth_client_path`)

---

## TikTok / Instagram V1 Behavior

- Upload packages are prepared automatically after publish
- Status: `manual_upload_ready`
- `auto_upload: false`
- No browser or unofficial automation
- Upload Center provides **Copy TikTok Caption** / **Copy Instagram Caption** actions

---

## Automation Integration

After a successful automation job (publish package ready):

```
Publish Package → Metadata Agent → Upload Package Builder → Upload Center ready
```

Hook: `AutomationJobRunner._execute_job()` → `UploadManager.prepare_full_upload_workflow()`

Auto-upload remains **OFF** by default (`feature_flags.auto_upload: false`).

---

## Upload Center UI

New nav item: **Upload Center**

Shows:

- Latest publish package / run ID
- Platform targets and metadata previews
- Upload package status per platform
- YouTube auth status
- Actions: Generate Metadata, Prepare Upload Packages, Upload to YouTube Private, Copy captions, Open Package Folder

---

## Comment Agent Extension

Pinned comment drafts are generated from metadata agent output:

- `youtube_pinned_comment.txt`
- `tiktok_pinned_comment.txt`
- `instagram_pinned_comment.txt`

No auto-posting. Approval remains required.

---

## Validation Results

```text
python project_brain/validate_upload_agent_v1.py
→ All 10 upload agent v1 validations passed.

python project_brain/validate_automation_v1.py
→ All 12 automation v1 validations passed.
```

Upload validator checks:

1. YouTube metadata generated
2. TikTok metadata generated
3. Instagram metadata generated
4. Upload package folders created
5. Captions and hashtags saved
6. YouTube upload defaults private
7. YouTube upload requires confirmation
8. TikTok/Instagram do not auto-upload
9. Automation creates upload packages after publish
10. No Runway automation changed

---

## Runway / Protected Systems — Not Changed

Confirmed unchanged:

- `content_brain/execution/runway_live_smoke_test.py`
- `content_brain/execution/runway_ui_navigator.py`
- Assembly pipeline
- Branding runtime (`content_brain/branding/branding_runtime.py` — no upload imports)
- Visual verifier / continuity pipeline

Only post-publish automation hook was extended to call the upload workflow.
