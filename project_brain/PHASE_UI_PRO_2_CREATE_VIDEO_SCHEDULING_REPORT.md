# Phase UI-PRO-2 — Create Video + Scheduling Report

**Phase:** UI-PRO-2 — Final Product Create Video + Scheduling Features  
**Status:** PASS  
**Date:** 2026-06-09

## Summary

Upgraded the web UI from a debug-first Execution Center shell into a **professional User Mode product** with Create Video, Schedule Planner, Results, Settings, and Upgrade Center. Developer/debug tools remain hidden unless **Developer Mode** is enabled.

**No runtime automation changed** — Runway execution, provider router, assembly, and publish package runtimes were not modified.

---

## UI Pages Added / Modified

| Page | Path | Purpose |
|------|------|---------|
| Dashboard | `ui/web/src/pages/ProductDashboardPage.tsx` | Product home |
| Create Video | `ui/web/src/pages/CreateVideoPage.tsx` | Duration, topic source, AI options, preflight |
| Schedule Planner | `ui/web/src/pages/SchedulePlannerPage.tsx` | Daily/weekly/monthly planning |
| Results | `ui/web/src/pages/ResultsPage.tsx` | Latest video + publish package |
| Settings | `ui/web/src/pages/SettingsPage.tsx` | Channel profile / niche setup |
| Upgrade Center | `ui/web/src/pages/UpgradeCenterPage.tsx` | Patch-ready future features |
| Developer Console | `ui/web/src/pages/DeveloperConsolePage.tsx` | Wraps Execution Center (dev only) |
| App shell | `ui/web/src/App.tsx` | User Mode navigation + dev toggle |
| App mode | `ui/web/src/context/AppModeContext.tsx` | Developer Mode persistence |

**Modified:** `ui/web/src/App.css` (product layout, chips, dev banner)

---

## Backend Added

| Module | Purpose |
|--------|---------|
| `content_brain/scheduling/duration_planner.py` | Duration validation + clip count by provider |
| `content_brain/scheduling/schedule_models.py` | `VideoSchedulePlan`, `ScheduledVideoJob` |
| `content_brain/scheduling/schedule_planner.py` | Daily/weekly/monthly job generation (planning only) |
| `content_brain/scheduling/schedule_store.py` | JSON persistence |
| `ui/api/product_studio_service.py` | Channel profile, preflight, schedules, results |
| `ui/api/schemas/product_studio.py` | API DTOs |
| `content_brain/upgrades/__init__.py` | Patch-ready future patch list stub |

**API routes (planning only):**

- `GET/PUT /product/channel-profile`
- `POST /product/create-video/preflight`
- `GET/POST /product/schedules`, `POST /product/schedules/preview`
- `POST /product/schedules/{id}/generate-jobs`, `POST /product/schedules/{id}/disable`
- `GET /product/results/latest`
- `GET /product/upgrade-center/patches`

---

## Duration Selector Behavior

Presets: **6 / 8 / 10 / 20 / 30 / 40 / Custom**

| Duration | Runway clips (10s limit) | Hailuo clips (8s limit) |
|----------|--------------------------|-------------------------|
| 6–10s | 1 | 1 |
| 20s | 2 | 3 |
| 30s | 3 | 4 |
| 40s | 4 | 5 |
| Custom | `ceil(duration / provider_limit)` | same |

Validation:

- Minimum **6 seconds**
- Soft warning above **120 seconds**
- Hard reject above **600 seconds**

---

## Topic Source Behavior

| Mode | Behavior |
|------|----------|
| **Channel Topic** | Uses saved `channel_topic` (fallback: sub niche / main niche) |
| **Custom Topic** | User text is **authoritative for that video only** |

Saved channel niche is never overwritten when custom topic is used.

---

## Channel Profile Behavior

Settings page + API manage:

- Channel name, main niche, sub niche, channel topic
- Target audience, language, tone/style
- Default platform, duration, provider
- Upload platforms: TikTok, Instagram Reels, YouTube Shorts

Stored via existing `ChannelIdentityStore` (`storage/content_brain/channel_identities/`).

---

## Schedule Planner Behavior

Modes: **daily**, **weekly** (Mon–Fri), **monthly**, **custom** range

- Creates **planned jobs only** (`status: planned`)
- No background auto-generation or auto-upload
- Preview / Save / Generate Today's Jobs / Disable Schedule

Example daily plan: 1 video/day × 7 days → **7 planned jobs** (validated).

---

## Platform Targets

Supported platform IDs:

- `tiktok`
- `instagram_reels`
- `youtube_shorts`

Multi-platform selection supported in Create Video and Schedule Planner.

---

## Patch-Ready Future Upgrades

Listed in Upgrade Center (install via future patch packages):

- Auto Upload Patch
- Real ElevenLabs Voice Patch
- Burned Subtitle Patch
- TikTok / YouTube / Instagram Upload Patches
- Advanced Calendar Automation Patch
- Multi-channel Management Patch
- Music/SFX Patch
- Suno Music Patch

Note shown in UI: *"Advanced features can be installed through Upgrade Center patches."*

---

## Developer Mode

- Default: **User Mode** product navigation
- Toggle in sidebar footer enables Developer Mode
- Developer Console exposes legacy Execution Center (UAT, smoke tests, etc.)
- Debug tools hidden from default user navigation

---

## Validation Results

```bash
python project_brain/validate_ui_pro_2_create_video_scheduling.py
python project_brain/validate_ui_professional_mode.py
python project_brain/validate_upgrade_center_foundation.py
python project_brain/validate_director_layer_v1.py
python project_brain/validate_director_layer_v2_prompt_critic.py
python project_brain/validate_runway_starter_to_video_prompt_builder.py
```

| Check | Result |
|-------|--------|
| Duration presets + custom validation | PASS |
| Clip count by provider | PASS |
| Channel / custom topic modes | PASS |
| Channel profile fields | PASS |
| Schedule daily/weekly/monthly jobs | PASS |
| Platform targets | PASS |
| Upgrade Center visible | PASS |
| Developer tools hidden by default | PASS |
| Director V1/V2 regressions | PASS |
| Runway prompt builder regression | PASS |
| Runway automation files untouched | PASS |

Phase I hardening/assembly/publish validators skipped (files not present in current workspace snapshot).

---

## Runtime Unchanged — Confirmation

- No edits to Runway UI navigator automation logic
- No edits to provider router
- No edits to assembly or publish package runtime modules
- Create Video **Generate Plan** runs preflight/planning only — no browser execution

---

## Usage

1. Start API: `python -m ui.api.main`
2. Start UI: `cd ui/web && npm run dev`
3. Use **Create Video** for preflight planning
4. Use **Schedule Planner** to save/preview/generate planned jobs
5. Enable **Developer Mode** only when debugging Execution Center
