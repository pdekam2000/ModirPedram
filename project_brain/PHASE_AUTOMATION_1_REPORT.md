# PHASE AUTOMATION-1 — Auto Generation + Upload + Comment Agent Foundation

## Goal

Turn Automation Center into a real one-job-at-a-time automation system that orchestrates the existing manual pipeline without modifying Runway browser automation internals.

## Architecture

```text
Automation Queue
  ↓
Automation Job Runner (safety preflight)
  ↓
ProductStudioService.create_video_generate
  → Content Brain / Director / Prompt handoff
  → RunwayLiveSmokeRuntimeService.start_run
  ↓ poll until complete
Post-processing (inside existing smoke test hook)
  → Assembly → Audio → Branding → Publish Package
  ↓
UploadManager.prepare_upload_package
```

No infinite loop. `start-next` runs exactly one job per call.

## Files created

| File | Purpose |
|------|---------|
| `content_brain/automation/automation_queue.py` | Persistent job queue with statuses |
| `content_brain/automation/automation_job_runner.py` | Preflight + pipeline orchestration |
| `content_brain/automation/__init__.py` | Package exports |
| `content_brain/upload/upload_models.py` | Upload target/package models |
| `content_brain/upload/upload_manager.py` | Upload package prep + gated YouTube submit |
| `content_brain/upload/__init__.py` | Package exports |
| `content_brain/comments/comment_agent.py` | Draft-only comment replies |
| `content_brain/comments/__init__.py` | Package exports |
| `ui/api/automation_service.py` | API service layer |
| `project_brain/validate_automation_v1.py` | Validator |

## Files updated

| File | Change |
|------|--------|
| `content_brain/product_settings/channel_profile_store.py` | YouTube upload settings defaults |
| `ui/api/product_studio_service.py` | YouTube profile fields in get/save |
| `ui/api/schemas/platform.py` | Automation/upload/comment DTOs |
| `ui/api/dependencies.py` | `get_automation_service()` |
| `ui/api/main.py` | `/automation/*`, `/upload/*`, `/comments/*` routes |
| `ui/web/src/api/platformClient.ts` | Automation client functions |
| `ui/web/src/pages/AutomationCenterPage.tsx` | Full automation UI |

## Automation flow

1. Operator creates job (`POST /automation/jobs`) or imports planned schedule jobs.
2. Operator enables automation and clicks **Start next job**.
3. Runner checks:
   - automation enabled / not paused
   - no job already running
   - daily cap (`max_jobs_per_day`, default 5)
   - browser connected
   - `OPENAI_API_KEY` present
4. Runner calls existing `create_video_generate` + waits for Runway service completion.
5. Runner resolves output paths from Runway report and prepares upload package.
6. Job status becomes `completed` or `failed` with error text.

## Upload foundation

- Platforms supported in V1 package prep: YouTube Shorts, TikTok, Instagram Reels
- TikTok / Instagram: placeholder prepared metadata only
- YouTube: gated submit foundation via `POST /upload/youtube/submit`
  - Requires `youtube_upload_enabled`
  - Default privacy: **private**
  - First submit requires confirmation unless `youtube_upload_confirmed=true`
  - No automatic public upload executed in V1

## Comment agent foundation

- `POST /comments/draft-reply` generates draft replies only
- `approve_required=true` always
- `auto_posted=false` always
- Approve/reject endpoints store draft state only — **no posting**

## Safety rules implemented

| Rule | Behavior |
|------|----------|
| No auto-upload by default | `youtube_upload_enabled=false`, `feature_flags.auto_upload=false` |
| No auto-comment posting | draft-only + approve stores status without posting |
| Upload privacy default private | `youtube_privacy=private` |
| Max jobs per day | queue cap default 5 |
| Pause always available | `/automation/pause` |
| Stop if browser disconnected | preflight + runtime poll |
| Stop if API key missing | OpenAI key required in preflight |
| Stop if Runway fails | failed job recorded from runway report |

## API endpoints

- `GET /automation/status`
- `GET /automation/jobs`
- `POST /automation/jobs`
- `POST /automation/start-next`
- `POST /automation/pause`
- `POST /automation/resume`
- `POST /automation/cancel/{job_id}`
- `POST /upload/prepare`
- `POST /upload/youtube/submit`
- `POST /comments/draft-reply`
- `POST /comments/draft-reply/approve`
- `POST /comments/draft-reply/reject`

Legacy `/platform/automation-center/*` routes remain; `start-next` now delegates to the real runner.

## Validation results

```bash
python project_brain/validate_automation_v1.py
```

All 12 tests pass:

1. Job creation
2. Start next calls existing generation pipeline
3. Job status updates
4. Pause/resume
5. Failed job error recording
6. Upload package creation
7. YouTube private default + confirmation gate
8. Comment draft only
9. No auto-comment posting
10. No auto-upload unless enabled
11. Manual generate preflight still works
12. Runway automation unchanged

## Confirmation

`runway_ui_navigator.py` and Runway smoke test selectors/generation logic were not modified. Director, Critic, Branding internals, and Visual verifier internals were not touched. Automation composes existing services only.
