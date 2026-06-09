# Phase RUNWAY-STARTER-TO-VIDEO-H.5 — UI Approval Runtime Report

**Phase:** `runway_live_smoke_h5_ui_v1`  
**Goal:** Move Phase H approval gates from terminal input to Runtime Studio UI  
**Result:** PASS (structural + bridge validation)

---

## Summary

Phase H.5 adds a **view + approval surface** between `RunwayLiveSmokeRunner` callbacks and Runtime Studio UI. The semi-auto engine, approval guard, and Generate/Download safety gates are unchanged.

| Before | After |
|--------|-------|
| Terminal `APPROVE` / `READY` | Runtime Studio buttons: **Approve**, **Image Ready**, **Cancel Run** |
| No live gate visibility | UI shows step, control, status, approval history, runtime logs |
| CLI-only operator loop | Web Execution Center tab + optional CLI `--ui-approval` bridge |

Terminal input remains supported as **fallback** when UI is not connected within ~1.5s.

---

## Architecture

```
RunwayLiveSmokeRunner (unchanged)
  └─ approval_callback / manual_ack_callback
        └─ RunwayLiveSmokeApprovalRuntime (NEW bridge)
              ├─ Runtime Studio Web UI (poll + POST)
              ├─ Runtime Studio Tk panel (optional)
              └─ Terminal fallback (default_interactive_*)
```

**Source of truth:** `RunwayLiveSmokeRunner` + `RunwayContinuitySemiAutoEngine` + `runway_continuity_approval_guard.py`

**UI role:** display gate state; submit operator decisions to the bridge only.

---

## New Files

| Path | Purpose |
|------|---------|
| `content_brain/execution/runway_live_smoke_approval_runtime.py` | Thread-safe approval bridge |
| `ui/api/runway_live_smoke_service.py` | API service (start run + gate actions) |
| `ui/api/schemas/runway_live_smoke.py` | Request/response schemas |
| `ui/web/src/api/runwayLiveSmokeClient.ts` | Web API client |
| `ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx` | Web approval panel |
| `ui/web/src/pages/RunwayLiveSmokePage.tsx` | Execution Center tab page |
| `ui/components/runway_live_smoke_approval_panel.py` | Tkinter approval panel |

---

## API Endpoints (Phase H.5)

| Method | Path | Action |
|--------|------|--------|
| `POST` | `/runway-live-smoke/start` | Start live/sim smoke run (background thread) |
| `GET` | `/runway-live-smoke/status` | Poll gate snapshot + report |
| `POST` | `/runway-live-smoke/connect-ui` | Mark UI connected |
| `POST` | `/runway-live-smoke/approve` | Approve current dangerous gate |
| `POST` | `/runway-live-smoke/image-ready` | Acknowledge image-ready manual hold |
| `POST` | `/runway-live-smoke/cancel` | Cancel run / deny gate |

---

## UI Gate Examples

### Waiting: `image_generate_button`

- Status: `waiting_approval`
- Buttons: **[Approve]** **[Cancel Run]**

### Waiting: image ready

- Status: `waiting_image_ready`
- Buttons: **[Image Ready]** **[Cancel Run]**

### Waiting: `download_mp4_button`

- Status: `waiting_approval`
- Buttons: **[Approve]** **[Cancel Run]**

---

## Operator Workflows

### A — Web Runtime Studio (recommended)

1. Start API server: `python -m ui.api.main`
2. Open Execution Center → **Runway Live Smoke** tab
3. Enter story → **Start Live Smoke (CDP)**
4. Use **Approve** / **Image Ready** / **Cancel Run** at each gate

### B — CLI with UI bridge + terminal fallback

```bash
python project_brain/run_runway_live_smoke_test.py --ui-approval --story "..."
```

- Connect web UI (or Tk panel) to the same bridge process, **or**
- Type `APPROVE` / `READY` at terminal if UI not connected

### C — Terminal only (unchanged)

```bash
python project_brain/run_runway_live_smoke_test.py --story "..."
```

---

## Safety Confirmation

| Constraint | Status |
|------------|--------|
| Approval guard unchanged | ✅ |
| Semi-auto engine unchanged | ✅ |
| RunwayBrowserProvider unchanged | ✅ |
| Generate/Download still approval-gated | ✅ |
| No autonomous Generate/Download | ✅ |
| Phase H validator passes | ✅ |

---

## Validation

```bash
python project_brain/validate_runway_live_smoke_test.py
```

New checks include:

- UI bridge module + API + web panel exist
- UI `Approve` / `Image Ready` unblock runtime callbacks
- Terminal fallback still works when UI not connected

---

## Not Changed

- `content_brain/execution/runway_continuity_approval_guard.py`
- `content_brain/execution/runway_continuity_semi_auto.py` (core logic)
- `providers/runway_browser_provider.py`
- `RunwayLiveSmokeRunner` gate handling (callbacks only swapped at CLI/API boundary)

---

**Report generated:** Phase H.5 UI Approval Runtime implementation
