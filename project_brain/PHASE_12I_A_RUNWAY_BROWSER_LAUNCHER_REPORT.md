# Phase 12I-A — Runway Browser Launcher Restoration Report

**Date:** 2026-06-01  
**Status:** Implemented  
**Goal:** Restore Tk-era controlled Chrome + CDP operator workflow in Execution Center / UAT

---

## Problem

- Legacy launcher lived only in `ui/app.py` (**OPEN AI BROWSER**).
- React Execution Center and UAT had no launcher; runtime attached to whatever owned CDP `:9222` (often Edge / logged-out context).
- UAT video could still mock-fallback on `NOT_DEQUEUED` (separate issue; not changed in this phase per scope).

---

## Solution

### 1. Shared launcher — `automation/browser_launcher.py`

| Function | Purpose |
|----------|---------|
| `resolve_chrome_executable()` | Chrome only via `MODIR_CHROME_PATH` or standard paths; **rejects Edge** |
| `resolve_runway_browser_config()` | Reads `provider_mode_catalog` → `storage/real_chrome_profile`, CDP URL |
| `launch_controlled_chrome()` | `chrome.exe --remote-debugging-port=9222 --user-data-dir={profile}` |
| `get_browser_operator_status()` | Status card fields + probes |
| `probe_runway_login_detected()` | Heuristic tab inspection (no credentials / no auto-login) |

State file: `storage/browser_launcher_state.json` (last launch metadata).

### 2. API — `ui/api/browser_operations_service.py`

| Endpoint | Method | Response |
|----------|--------|----------|
| `/operations/browser/launch` | POST | `BrowserLaunchResponse` |
| `/operations/browser/status` | GET | `BrowserStatusResponse` |

Reuses `browser_connectivity_probe` for socket + Playwright attach + profile path checks.

### 3. UI — `RunwayBrowserPanel`

- Button: **Open Runway Browser**
- Status tiles: Browser Running, CDP Connected, Profile Loaded, Runway Login Detected
- Polls status every 5s
- Shown on Execution Center (Sessions + UAT tabs)

### 4. Tk app

`ui/app.py` `open_ai_browser()` now calls `launch_controlled_chrome(PROJECT_ROOT)`.

---

## Operator workflow (restored)

1. Click **Open Runway Browser** (Execution Center).
2. Chrome opens with `storage/real_chrome_profile`.
3. Sign in to Runway manually in that window.
4. Leave Chrome open.
5. Status card shows CDP connected + Runway login detected.
6. Run dequeued session or UAT (browser attach uses same CDP + profile).

---

## Files

| File | Change |
|------|--------|
| `automation/browser_launcher.py` | New launcher + status |
| `ui/api/browser_operations_service.py` | API service |
| `ui/api/schemas/browser_operations.py` | DTOs |
| `ui/api/main.py` | Routes |
| `ui/api/dependencies.py` | DI |
| `ui/web/src/api/browserOperationsClient.ts` | Client |
| `ui/web/src/components/RunwayBrowserPanel.tsx` | UI panel |
| `ui/web/src/pages/ExecutionCenterPage.tsx` | Wired panel |
| `ui/app.py` | Delegates to launcher |
| `ui/web/src/App.css` | Panel styles |
| `project_brain/validate_12i_a_runway_browser_launcher.py` | Validator |

---

## Out of scope (unchanged)

- Provider runtime / `BrowserManager` attach logic
- UAT `NOT_DEQUEUED` mock video fallback
- Auto-login or credential storage

---

## Validation

Run:

```powershell
$env:PYTHONPATH="C:\Users\kaman\Desktop\ModirAgentOS"
python project_brain/validate_12i_a_runway_browser_launcher.py --core-only
cd ui/web; npm run build
```

Manual checklist:

1. **Open Runway Browser** → Chrome starts (not Edge).
2. Profile path = `storage/real_chrome_profile`.
3. Manual Runway login persists after restart (same profile).
4. Status → CDP Connected = Yes.
5. UAT / dispatch attach to same logged-in session when CDP is up.

---

## Follow-up (Phase 12I-B suggested)

- UAT real video: dequeue or UAT-only dispatch policy (fix placeholder clips).
- `BrowserManager`: read `cdp_url` from catalog; avoid `new_context()` when empty.
