# PHASE PLATFORM-1 — Product Platform Foundation Report

## Summary

ModirAgentOS now has a platform shell around the working pipeline: local API credential management, local login gate, black/orange product theme, versioned run outputs, browser health monitoring, Open Browser integration, and an Automation Center foundation page.

**Not modified:** Runway generation selectors, Runway automation logic, Director/Critic, visual verifier, ElevenLabs runtime logic.

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/platform/local_secret_codec.py` | Local key + masked secret helpers |
| `content_brain/platform/local_credentials_store.py` | Encrypted local credential storage |
| `content_brain/platform/local_user_store.py` | Local username/password hash store |
| `content_brain/platform/run_output_versioning.py` | Versioned `outputs/runs/...` folders + index |
| `content_brain/platform/browser_health_monitor.py` | CDP/Runway health + safe refresh |
| `content_brain/platform/automation_center_store.py` | Automation Center JSON state |
| `ui/api/platform_service.py` | Platform API service |
| `ui/api/schemas/platform.py` | Platform DTOs |
| `ui/web/src/api/platformClient.ts` | Frontend platform client |
| `ui/web/src/context/AuthContext.tsx` | Local auth session context |
| `ui/web/src/pages/LoginPage.tsx` | Login / create local user |
| `ui/web/src/pages/AutomationCenterPage.tsx` | Automation Center V1 |
| `ui/web/src/styles/platform-theme.css` | Black + orange + diamond white theme |
| `project_brain/validate_platform_foundation_v1.py` | Phase validator |
| `project_brain/PHASE_PLATFORM_1_FOUNDATION_REPORT.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `.gitignore` | Ignore `project_brain/local_credentials/`, `project_brain/local_user/` |
| `content_brain/execution/runway_live_post_processor.py` | Versioned run dirs + latest pointer copies |
| `ui/api/main.py` | Platform routes + startup credential env apply |
| `ui/api/dependencies.py` | `get_platform_service()` |
| `ui/api/product_studio_service.py` | `run_history` in latest results |
| `ui/api/schemas/product_studio.py` | `run_history` field |
| `ui/web/src/App.tsx` | Auth gate, logout, Automation nav, theme shell |
| `ui/web/src/pages/SettingsPage.tsx` | API Credentials section |
| `ui/web/src/pages/ResultsPage.tsx` | Run history list |
| `ui/web/src/components/RunwayBrowserPanel.tsx` | Health heartbeat, reconnect, safe refresh |
| `ui/web/src/product/constants.ts` | `automation` nav item |

## API Credential Storage

- Path: `project_brain/local_credentials/credentials.local.json`
- Key file: `project_brain/local_credentials/.local_key` (gitignored with folder)
- Values stored encoded locally; API returns **masked** values only (`sk-...abcd`)
- Full secrets are **never** returned to frontend after save
- Supported providers: OpenAI, ElevenLabs, DataForSEO login/password, SerpAPI, Hailuo/MiniMax, Runway, Veed, future slots
- Test connection: OpenAI + ElevenLabs (others save-only for now)
- On API startup + save: credentials applied to process env (no `.env` overwrite)

## Local Login

- Path: `project_brain/local_user/user.local.json`
- Password stored as PBKDF2 hash + salt (never plain text)
- First launch: **Create Local User** screen
- Later: login page + logout button + “Signed in as …” in sidebar
- Session token in memory (backend) + `localStorage` token (frontend)
- No cloud auth, no database

## Theme

- Background: deep black / charcoal
- Accent: orange (`#ff7a1a`)
- Text: diamond white (`#f8f8ff`)
- Cards: dark gray with subtle orange border glow
- Applied via `platform-theme.css` on product shell pages + login

## Output Versioning

Each successful post-processing run creates:

`outputs/runs/YYYYMMDD_HHMMSS_<short_run_id>/`

With subfolders:

- `final/`
- `publish/`
- `audio/` (reserved in layout)
- `prompts/` (via publish package copy)
- `metadata/`
- `vision/` (reserved in layout)
- `raw_downloads_manifest.json`

Latest pointers still updated:

- `outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4`
- `outputs/publish/runway_phase_i/`

Run index: `outputs/runs/index.json`  
Results page shows latest output + previous runs list with folder paths.

## Browser Health

Endpoints:

- `GET /platform/browser/health`
- `POST /platform/browser/open`
- `POST /platform/browser/reconnect`
- `POST /platform/browser/refresh-runway?force=false`

Behavior:

- CDP reachable check
- Runway tab detection
- Page responsiveness via existing browser probes
- Last heartbeat timestamp persisted in runtime state
- Refresh blocked while generation active (unless `force=true` / UI confirmation)
- Does not click Generate or spend credits

Dashboard + Create Video use enhanced `RunwayBrowserPanel` with Open Browser / Reconnect / Refresh.

## Automation Center Foundation

Page: **Automation Center** (nav)

State file: `project_brain/platform/automation_center.json`

V1 controls:

- Enable/disable automation
- Pause automation
- Queue upcoming jobs
- Manual start next job
- Run history + failed jobs list
- Future feature flags (Auto Generate/Voice/Publish/Upload/Suno/Analytics) — disabled placeholders

No auto-upload. No autonomous generation loop unless explicitly started later.

## Validation Results

```text
python project_brain/validate_platform_foundation_v1.py          PASS
python project_brain/validate_live_post_processing_hook.py         PASS
python project_brain/validate_visual_continuity_verifier.py          PASS
python project_brain/validate_elevenlabs_runtime_v1.py            PASS
```

## Runtime Safety Confirmation

- `runway_ui_navigator.py` selectors unchanged
- Runway smoke test generation flow unchanged
- Director/Critic/visual verifier/ElevenLabs runtime modules unchanged
- Changes are platform shell, storage, UI, post-processing output paths, and browser health wrappers only

## First Run Notes

1. Restart API: `python -m ui.api.main`
2. Open product UI → create local user once
3. Save API keys in Settings → API Credentials
4. Use **Open Browser** before Runway generation
5. After next completed run, check Results → Run History for versioned folder entry
