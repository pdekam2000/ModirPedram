# Phase 11J-16 — Assembly Approval UI Controls Implementation Report

**Status:** Complete — metadata-only approval controls; no FFmpeg, no real assembly execution  
**Date:** 2026-06-01  
**Prerequisites:** 11J-15 design, 11J-14 write APIs, 11J-12 guard, 11J-10 observability  
**Next phase:** **PHASE 11J-17 — Pre-Real Assembly Final Safety Review**

---

## Summary

Implemented Assembly Approval UI controls inside `AssemblyRuntimeObservabilityPanel`, mirroring the voice approval pattern (11H-1i). Four safe actions call 11J-14 backend endpoints only. Every response is fail-closed on `real_assembly_executed !== false`. No optimistic updates; session/runtime refresh after success.

---

## Files Created

| File | Purpose |
|------|---------|
| `ui/web/src/api/assemblyApprovalClient.ts` | Four POST wrappers + safety assert |
| `ui/web/src/utils/assemblyApprovalEligibility.ts` | Button visibility/enabled rules |
| `ui/web/src/utils/assemblyApprovalLabels.ts` | Safe labels, block messages, exact approve warning |
| `ui/web/src/components/AssemblyApprovalControlsPanel.tsx` | Action cards + API calls + refresh |
| `ui/web/src/components/AssemblyApprovalConfirmDialog.tsx` | Confirmation modal with estimates |
| `project_brain/validate_11j16_assembly_approval_ui_controls.py` | 17-test validator |
| `project_brain/PHASE_11J16_ASSEMBLY_APPROVAL_UI_CONTROLS_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx` | Embed `AssemblyApprovalControlsPanel` below approval gate |
| `ui/web/src/components/RuntimeObservability.tsx` | Pass `sessionId`, `sessionContext`, `onAssemblyApprovalSuccess` |
| `ui/web/src/components/SessionDrawer.tsx` | Wire `onAssemblyApprovalSuccess={onAfterAction}` |
| `ui/web/src/utils/assemblyRuntimeObservability.ts` | Eligibility helper fields + `hasAssemblyGenerationSlot` / `isAssemblyDryRunCompleted` |
| `ui/web/src/App.css` | Assembly approval action/modal styles |

**Backend:** unchanged (no bugs discovered).

---

## Controls Added

| Label | Endpoint | Body highlight |
|-------|----------|----------------|
| Approve assembly | `POST …/assembly/approve` | `request_real_assembly: true`, `ttl_minutes`, `approved_by: "operator"` |
| Reject approval | `POST …/assembly/reject` | `rejected_by: "operator"` |
| Expire approval | `POST …/assembly/expire` | `expired_by: "operator"` |
| Reset approval | `POST …/assembly/reset-approval` | `reset_by: "operator"` |

Placement: **Assembly approval actions** subsection below read-only **Assembly approval gate** (non-compact mode only).

---

## Safety Warning Confirmation

Approve modal displays exact copy:

> This only approves future real assembly execution. It does not run FFmpeg or generate the final video yet.

Client `assertAssemblyApprovalSafety()` and pre-success check reject any response where `real_assembly_executed !== false`.

Persistent banner:

> Assembly approval actions authorize future real assembly execution metadata only. No FFmpeg runs and no final video is generated in this phase.

---

## Forbidden Label Check

Validator confirms no button text contains:

- Run Assembly
- Generate Final Video
- Export Final Video
- Run FFmpeg
- Create MP4
- Build Final

No `dry_run: false` references in new UI files. No FFmpeg-labeled buttons.

---

## Validation Results

| Command | Result |
|---------|--------|
| `python -m project_brain.validate_11j16_assembly_approval_ui_controls` | **17/17 PASS** |
| `python -m project_brain.validate_11j14_assembly_approval_write_apis` | **PASS** (regression via 11J-16) |
| `python -m project_brain.validate_11j12_assembly_approval_guard` | **PASS** (regression via 11J-16) |
| `python -m project_brain.validate_11j10_assembly_ui_observability` | **PASS** (regression via 11J-16) |
| `python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution` | **PASS** (regression via 11J-16) |
| `npm run build` | **PASS** |

---

## Safety Confirmations

| Constraint | Status |
|------------|--------|
| No FFmpeg execution | Confirmed — UI calls approval APIs only |
| No `FINAL_PUBLISH_READY.mp4` generation | Confirmed |
| No `/assembly/run` with `dry_run=false` | Confirmed (grep) |
| No real execution env flags changed | Confirmed |
| Upstream video/voice/subtitle runtimes unchanged | Confirmed |
| No Runway/Hailuo changes | Confirmed |
| Refresh after success (no optimistic update) | Confirmed via `onAfterAction` |

---

## Next Recommended Phase

**PHASE 11J-17 — Pre-Real Assembly Final Safety Review**

Before any future real FFmpeg wiring: review guard + policy + UI + env flags end-to-end; confirm fail-closed defaults; document operator runbook for when real assembly becomes available in a later gated phase.
