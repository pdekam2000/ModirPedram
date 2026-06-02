# Phase 10K-c — Operations Control UI Report

Generated: 2026-05-30  
Status: **Complete**  
Scope: Frontend UI only (no backend changes)

Prerequisites: Phase 10K-b backend (30/30 validation), API v0.6.0

---

## Summary

Phase 10K-c adds **operator action UI** to the Execution Center Session Drawer:

- Eligibility-driven Retry / Cancel / Archive / Requeue buttons
- Actions tab with eligibility cards, last result, and audit history
- Confirmation dialogs with required reasons (cancel/archive/requeue)
- Toast feedback and post-action refetch (session, list, runtime poll, eligibility)

**No provider dispatch.** Buttons call only `POST /sessions/{id}/actions/*`.

---

## Files Created

| File | Purpose |
|------|---------|
| `ui/web/src/hooks/useSessionActions.ts` | Eligibility fetch + action execution + last result |
| `ui/web/src/utils/sessionActions.ts` | Action metadata, labels, error parsing |
| `ui/web/src/components/ConfirmActionDialog.tsx` | Confirmation modal with reason input |
| `ui/web/src/components/ToastProvider.tsx` | Success/error toast stack |
| `ui/web/src/components/SessionActionBar.tsx` | Compact header action buttons |
| `ui/web/src/components/SessionActionsPanel.tsx` | Actions tab: eligibility, history, last result |

---

## Files Modified

| File | Change |
|------|--------|
| `ui/web/src/api/client.ts` | `fetchSessionActionEligibility`, `postSessionAction`, types |
| `ui/web/src/components/SessionDrawer.tsx` | Actions tab, header bar, dialog wiring |
| `ui/web/src/pages/ExecutionCenterPage.tsx` | `refreshAfterAction`, runtime refresh key, Phase 10K header |
| `ui/web/src/hooks/useRuntimeStatusPoll.ts` | Optional `refreshKey` to refetch after actions |
| `ui/web/src/App.tsx` | Wrap app in `ToastProvider` |
| `ui/web/src/App.css` | Action bar, eligibility cards, modal, toast styles |

### Unchanged (by design)

| Path |
|------|
| `content_brain/execution/*` (backend) |
| `ui/api/*` |
| `ui/app.py`, providers, orchestrators, `full_video_pipeline.py` |

---

## UI Behavior

### Session Drawer header

- Four compact buttons: **Retry**, **Cancel**, **Archive**, **Requeue**
- Disabled when eligibility `allowed: false`
- Block reason shown as hint text under disabled buttons (title tooltip on wrap)
- **Cancel** — danger styling (`action-btn-danger`)
- **Archive** — neutral styling (`action-btn-neutral`)

### Actions tab

1. **Current state** — session state + eligibility load status  
2. **Eligibility cards** — one per action with allowed/blocked pill, reason, safety note, action button  
3. **Last action result** — transition, audit ID, message (after any action attempt)  
4. **Action history** — last 20 entries from `session.operations_audit_log` (newest first)

### Legacy sessions (`exec_test_001`)

- Info banner when no schema/runtime metadata  
- Eligibility fetch still runs; blocked reasons render as `—` or policy text  
- No crash on missing `operations_audit_log`

---

## Endpoint Usage

| Client function | HTTP |
|-----------------|------|
| `fetchSessionActionEligibility(id)` | GET `/sessions/{id}/actions/eligibility` |
| `postSessionAction(id, 'retry', { reason, actor })` | POST `/sessions/{id}/actions/retry` |
| `postSessionAction(id, 'cancel', …)` | POST `/sessions/{id}/actions/cancel` |
| `postSessionAction(id, 'archive', …)` | POST `/sessions/{id}/actions/archive` |
| `postSessionAction(id, 'requeue', …)` | POST `/sessions/{id}/actions/requeue` |

**Not called by this UI:** `POST /runtime/dispatch` (no auto-dispatch after retry/requeue).

---

## Confirmation Dialog Behavior

| Action | Reason | Notes in dialog |
|--------|--------|-----------------|
| Retry | Optional | DEQUEUED prep only; no provider execution |
| Cancel | Required (≥3 chars) | Worker cooperative cancel not implemented (10K-d) |
| Archive | Required | Soft flag; data preserved |
| Requeue | Required | QUEUED only; not dispatched |

Dialog shows: action name, current state, consequence summary, safety note, reason field.

---

## Post-Action Refetch

On successful action (`onAfterAction`):

1. `fetchSessionSummary()` + `fetchSessions()` — refresh overview + table  
2. `fetchSession(session_id)` — refresh drawer detail (includes updated audit log)  
3. `runtimeRefreshKey++` — triggers immediate runtime status poll refresh  
4. `useSessionActions` reloads eligibility internally after `postSessionAction`

Toasts:

- **Success** — green, `result.message`  
- **Error** — red, parsed `reason` / `code` from API JSON

---

## Action Eligibility Display (expected)

| Session state | Retry | Cancel | Archive | Requeue |
|---------------|-------|--------|---------|---------|
| FAILED | Allowed | Blocked | Allowed | Allowed |
| RUNNING + active job | Blocked | Allowed | Blocked | Blocked |
| COMPLETED | Blocked | Blocked | Allowed | Blocked |
| CANCELLED | Blocked | Blocked | Allowed | Allowed |
| SIMULATED (legacy) | Blocked | Blocked | Blocked | Blocked |

---

## Build Verification

```bash
cd ui/web
npm run build
```

**Result:** `tsc && vite build` — PASS (46 modules)

Backend validation unchanged:

```bash
py -3.11 -m project_brain.validate_10k_b_operations_backend
```

---

## Manual Validation Checklist

| # | Check | Expected |
|---|-------|----------|
| 1 | Open FAILED session (`exec_10j_ops_preflight_fail`) | Retry + Requeue allowed in Actions tab |
| 2 | Open RUNNING session with active job | Cancel allowed; Retry/Archive blocked |
| 3 | Open COMPLETED session | Archive allowed; Retry/Requeue/Cancel blocked |
| 4 | Open `exec_test_001` legacy | Actions tab loads; all blocked with reasons; no crash |
| 5 | Confirm Retry on FAILED | Toast success; state → DEQUEUED; table refreshes |
| 6 | Confirm Archive on COMPLETED | Toast success; archived flag in raw JSON |
| 7 | Cancel without reason | Dialog blocks submit; API 400 if bypassed |
| 8 | Retry on RUNNING | Button disabled; 409 if forced via API |
| 9 | Action history | Shows timestamp, action, actor, states, reason |
| 10 | No dispatch triggered | Network tab shows no `/runtime/dispatch` from action buttons |

---

## Scope Compliance

| Rule | Status |
|------|--------|
| Frontend UI only | ✅ |
| No backend changes | ✅ |
| No provider/browser/orchestrator changes | ✅ |
| No worker cancel implementation | ✅ (UI shows limitation note) |
| No auto-dispatch | ✅ |
| Operations endpoints only | ✅ |
| Preserve 10J polling + 10K-b API | ✅ |

---

## Known Limitations

1. Cancel dialog notes registry-only cancel until 10K-d worker hook  
2. Archived sessions still visible in default list (filter in 10K-e)  
3. Action bar block hints may truncate on narrow drawer width  
4. Toast auto-dismiss after 5s (no manual dismiss)

---

## Next Slice Recommendation

**Phase 10K-d — Worker cooperative cancel**

- Worker checks `operations_control.cancel_requested`  
- Finalize CANCELLED only after worker ack  
- Update UI cancel messaging when cooperative path ships  

Followed by **10K-e** archived session filter in Execution Center list.

---

## Exit Gate

| Criterion | Status |
|-----------|--------|
| API client helpers | ✅ |
| Actions tab + header bar | ✅ |
| Confirmation dialogs | ✅ |
| Toast + refetch | ✅ |
| Action history panel | ✅ |
| Legacy safety | ✅ |
| Build passes | ✅ |
| No backend changes | ✅ |

**Phase 10K-c is complete.**
