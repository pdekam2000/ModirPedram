# Scheduler Audit — Pre-Implementation (2026-07-03)

## Verdict: **Did NOT fully meet requirements** (gaps fixed in this phase)

---

## What existed before

| Component | File | Status |
|-----------|------|--------|
| Schedule planner | `content_brain/scheduling/schedule_planner.py` | Planning only — hardcoded 4/3/3 split |
| Automation runner | `content_brain/automation/automation_job_runner.py` | Manual `start-next` only |
| Automation queue | `content_brain/automation/automation_queue.py` | Global daily cap **5** |
| Automation center | `content_brain/platform/automation_center_store.py` | `enabled=false`, `paused=true` by default |
| Upload Center UI | `ui/web/src/pages/UploadCenterPage.tsx` | Manual metadata/upload workflow |
| Channel topics | `channel_profile_store.py` + Settings | YouTube/TikTok/Instagram topic fields (partial) |

---

## Gaps found (audit)

1. **No per-platform ON/OFF, videos/day, or interval settings** — only hardcoded `DEFAULT_DAILY_PLATFORM_PLANS` (YouTube 4/day, others 3/day).
2. **No upload interval spacing** — all jobs shared one `run_time` (`09:00`).
3. **No auto-start on app launch** — scheduler only ran when operator clicked "Start next job".
4. **Global daily cap blocked multi-platform** — `max_jobs_per_day = 5` prevented 10 videos/day.
5. **`next_planned_job` ignored scheduled time** — jobs ran immediately, not at 8:00 / 12:00 / 16:00.
6. **Upload Center had no per-platform automation UI** — only manual YouTube upload tools.
7. **No persisted upload history per platform** with success/fail from API.

---

## What was implemented

| Requirement | Implementation |
|-------------|----------------|
| Independent platforms | `platform_daily_scheduler_store.py` — per-platform config |
| ON/OFF + videos/day + interval | Upload Center UI + persisted JSON |
| Topic per platform | Synced with Settings (`channel_topic`, `tiktok_channel_topic`, `instagram_channel_topic`) |
| 30s default duration | `duration_seconds: 30` default |
| Interval uploads (e.g. 8/12/16) | `compute_upload_times()` + due-time queue filter |
| Auto-start on launch | `background_scheduler.py` wired in `ui/api/main.py` startup |
| Dynamic daily cap | Sum of enabled platforms' `videos_per_day` |
| Upload history | `upload_history_store.py` + UI per platform |
| Existing upload logic untouched | Manual tools moved to collapsible section; `submit_publish_package_upload` only adds history record |

---

## Files added

- `content_brain/automation/platform_daily_scheduler_store.py`
- `content_brain/automation/platform_daily_scheduler.py`
- `content_brain/automation/upload_history_store.py`
- `content_brain/automation/background_scheduler.py`

## Files modified

- `content_brain/automation/automation_queue.py`
- `content_brain/automation/automation_job_runner.py`
- `content_brain/automation/automation_service.py`
- `ui/api/upload_service.py` (additive history hook only)
- `ui/api/main.py`
- `ui/api/schemas/platform.py`
- `ui/web/src/pages/UploadCenterPage.tsx`
- `ui/web/src/pages/SettingsPage.tsx`
- `ui/web/src/api/platformClient.ts`
- `ui/web/src/App.css`
- `content_brain/scheduling/schedule_planner.py` (YouTube topic resolution)

---

## How to enable

1. Open **Upload Center**
2. Enable a platform (ON toggle), set topic, videos/day, interval
3. Ensure **Automation** is ON (enabling any platform auto-enables automation center)
4. Restart API or rely on startup hook — background scheduler polls every 30s

Manual upload workflow remains under **"Show manual upload tools"** — unchanged.
