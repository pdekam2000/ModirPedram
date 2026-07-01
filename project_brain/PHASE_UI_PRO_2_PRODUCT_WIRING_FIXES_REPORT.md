# Phase UI-PRO-2 FIX — Product UI Wiring Fixes Report

## Summary

Fixed three User Mode product wiring bugs by connecting the Product UI to existing backend/runtime paths. No Runway automation, selectors, provider router, or Phase I engine internals were modified.

---

## Bug 1 — Create Video Generate did nothing

### Root cause

The Create Video page only called `POST /product/create-video/preflight`, which performs topic/duration planning only. It never invoked the existing Phase I FULL_AUTO runner, so the Runway browser never started.

The button was labeled **Generate Plan** and hardcoded `provider: "runway"` without starting execution.

### Fix

- Added `POST /product/create-video/generate` in `ui/api/main.py`.
- `ProductStudioService.create_video_generate()` runs preflight, then delegates to the existing `RunwayLiveSmokeRuntimeService.start_run()` (same path as `POST /runway-live-smoke/start`).
- Uses `project_id=phase_i_live`, `execution_mode=FULL_AUTO`, and clip count from the duration planner.
- Returns `run_id`, `session_id`, and initial snapshot.
- Non-Runway providers return: **"Provider execution not wired yet."** (no execution attempted).

### Frontend

- `CreateVideoPage.tsx` now has separate **Preflight Plan** and **Generate Video** buttons.
- Generate calls `/product/create-video/generate`.
- Polls `/runway-live-smoke/status` for running/completed/failed states and latest step.
- Loads saved `default_provider` from channel profile.

---

## Bug 2 — Settings not persisted

### Root cause

Settings were saved via `ChannelIdentityStore` only. When no active channel file existed, `get_channel_profile()` fell back to in-memory defaults on reload, so values appeared to revert after navigation.

### Fix

- Added durable JSON store: `project_brain/product_settings/channel_profile.json`
- Module: `content_brain/product_settings/channel_profile_store.py`
- `GET /product/channel-profile` reads from JSON file first.
- `POST /product/channel-profile` writes to disk (PUT kept for compatibility).
- Dual-writes to `ChannelIdentityStore` for downstream Content Brain compatibility.
- Fields persisted include `default_provider`, `channel_topic`, `upload_platforms`, and `updated_at`.

### Frontend

- `saveChannelProfile()` now uses POST.
- Settings page loads saved profile on mount and shows confirmation after save.
- Create Video Channel Topic mode uses saved `channel_topic` / `main_niche`.

---

## Bug 3 — Upgrade Center patch upload missing

### Fix

- Added `POST /upgrades/upload` (multipart file upload).
- Service: `content_brain/upgrades/patch_upload_service.py`
- Stores packages under `project_brain/upgrades/uploaded/{upgrade_id}/`
- Allowed: `.zip`, `.json`, `.patch`
- Blocked: `.exe`, `.bat`, `.ps1`, and other dangerous extensions
- Zip extraction blocks path traversal; optional `manifest.json` validation
- **Upload does not auto-apply** (`auto_applied: false`)
- Upgrade Center list API merges future patches + uploaded patches
- Frontend upload section: choose file, upload, status, refresh list

Existing preview/backup/apply safety flow remains unchanged (upload-only storage).

---

## Files changed

| Area | Files |
|------|-------|
| Settings persistence | `content_brain/product_settings/channel_profile_store.py`, `content_brain/product_settings/__init__.py` |
| Product API | `ui/api/product_studio_service.py`, `ui/api/schemas/product_studio.py`, `ui/api/main.py` |
| Upgrade upload | `content_brain/upgrades/patch_upload_service.py`, `content_brain/upgrades/__init__.py` |
| Frontend | `ui/web/src/api/productClient.ts`, `ui/web/src/pages/CreateVideoPage.tsx`, `ui/web/src/pages/UpgradeCenterPage.tsx` |
| Validation | `project_brain/validate_ui_pro_2_product_wiring_fixes.py`, `project_brain/validate_upgrade_center_foundation.py` |

---

## Validation results

```text
python project_brain/validate_ui_pro_2_product_wiring_fixes.py          PASS
python project_brain/validate_ui_pro_2_create_video_scheduling.py     PASS
python project_brain/validate_upgrade_center_foundation.py            PASS
python project_brain/validate_director_layer_v1.py                    PASS
python project_brain/validate_director_layer_v2_prompt_critic.py     PASS
python project_brain/validate_runway_phase_i_hardening.py             SKIP (script not in workspace)
python project_brain/validate_runway_phase_i_final_assembly.py        SKIP (script not in workspace)
python project_brain/validate_runway_phase_i_publish_package.py       SKIP (script not in workspace)
```

Key wiring checks (all PASS):

1. Generate endpoint exists and frontend calls it
2. Generate returns run/session id via existing runner
3. Generate uses `runway_service.start_run`, not a duplicate engine
4. Settings POST persists to disk and GET reloads
5. Create Video uses saved channel topic
6. `default_provider` persists
7. Upgrade upload accepts safe zip, rejects `.exe`
8. Uploaded patch appears in list; upload does not auto-apply

---

## Runway automation unchanged

Confirmed:

- `content_brain/execution/runway_ui_navigator.py` — not modified
- `providers/runway_browser_provider.py` — not modified
- `content_brain/execution/runway_live_smoke_test.py` — not modified
- Provider router — not modified
- Phase I FULL_AUTO engine behavior — not modified (only UI wiring to existing `RunwayLiveSmokeRuntimeService.start_run()`)

---

## Operator notes

1. Restart the API server to pick up new routes if it was already running.
2. Generate Video with Runway selected will start the same Phase I browser flow as Developer Console → Runway Live Smoke.
3. Settings save now survives page navigation via `project_brain/product_settings/channel_profile.json`.
4. Upgrade uploads are stored only; apply still requires the existing preview → backup → confirm workflow when implemented.
