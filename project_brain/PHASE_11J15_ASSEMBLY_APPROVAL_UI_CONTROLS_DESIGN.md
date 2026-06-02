# Phase 11J-15 — Assembly Approval UI Controls Design

**Status:** Design only — no implementation, no working buttons, no FFmpeg, no real assembly execution  
**Date:** 2026-06-01  
**Prerequisites:** 11J-2 foundation, 11J-8 dry-run API, 11J-10 UI observability, 11J-12 read-only guard, 11J-14 approval write APIs  
**Next phase:** **PHASE 11J-16 — Assembly Approval UI Controls Implementation**

---

## Executive Summary

Execution Center already shows **read-only** assembly observability in `AssemblyRuntimeObservabilityPanel` (11J-10): dry-run safety copy, planned steps preview, expected output (not generated), and the **Assembly approval gate** subsection (11J-12). Phase 11J-14 added **backend-only** write APIs that mutate `assembly_generation.approval` metadata and append `operations.assembly_approval_audit[]` — always returning `real_assembly_executed: false`.

Phase 11J-15 designs operator controls that mirror the proven **Voice Approval UI** pattern (`VoiceApprovalControlsPanel` + `VoiceApprovalConfirmDialog` + eligibility gating from 11H-1i) but scoped to **category assembly approval**, not session-level actions and not assembly execution.

**Key principle:** Approve assembly authorizes **future** real FFmpeg assembly metadata only. It does **not** run FFmpeg, does **not** create `FINAL_PUBLISH_READY.mp4`, and does **not** call `POST /assembly/run` with `dry_run=false`.

**Do not start Phase 11J-16 until explicit user approval.**

---

## Current UI Architecture

### Placement today

```
SessionDrawer / ExecutionCenterPage
  └── RuntimeObservabilityPanel
        ├── CategoryRuntimeSlotsPanel
        ├── VoiceRuntimeObservabilityPanel
        │     └── Voice approval actions        ← 11H-1i (reference pattern)
        ├── SubtitleRuntimeObservabilityPanel
        └── AssemblyRuntimeObservabilityPanel   ← read-only (11J-10 + 11J-12 gate)
              ├── assembly_generation status KV
              ├── Assembly approval gate          ← read-only KV + blocked reasons
              ├── Planned steps (preview only)
              └── Expected output (not generated)
```

Assembly panel currently receives `status`, `legacyPanel`, and `compact` only — **no** `sessionId` or refresh callback (11J-16 will add these, mirroring voice wiring).

### Data sources

| Source | Fields used |
|--------|-------------|
| `RuntimeStatusResponse.category_runtime_slots[]` | Assembly slot status, validation, approval, planned_steps |
| `legacyPanel` / `provider_runtime_panel.data` | Fallback for older sessions |
| `resolveAssemblyRuntimeObservability()` | Normalized display + approval block |
| `SessionDetail.session.operations_control` | Archived, cancel_requested |
| `SessionDetail.status` | Session state |

### Backend APIs (11J-14 — implemented)

| Endpoint | Purpose |
|----------|---------|
| `POST /sessions/{id}/assembly/approve` | Grant approval + set `real_assembly_requested` |
| `POST /sessions/{id}/assembly/reject` | Reject approval |
| `POST /sessions/{id}/assembly/expire` | Force expire |
| `POST /sessions/{id}/assembly/reset-approval` | Clear grant; re-evaluate gate |

All return `AssemblyApprovalActionResponse` with `real_assembly_executed: false`.

---

## UI Placement Plan

### Recommended layout (11J-16)

Add an **Assembly approval actions** subsection **inside** `AssemblyRuntimeObservabilityPanel`, directly **below** the existing read-only **Assembly approval gate** KV grid and blocked-reasons list:

```
Assembly runtime
  [dry-run safety banner]
  [status badge + KV grid]

Assembly approval gate          ← existing read-only (11J-12)
  [approval KV grid]
  [blocked reasons — always visible]
  [globally disabled note if applicable]

Assembly approval actions       ← NEW (11J-16)
  [safety banner — metadata only]
  [eligibility note OR compact button row]
  [last action result]
  [assembly_approval_audit excerpt — optional first slice]

Planned steps (preview only)    ← unchanged; stays below actions
Expected output (not generated)   ← unchanged
```

### Why nested under assembly panel

| Reason | Detail |
|--------|--------|
| Category scope | Assembly approval ≠ session retry/cancel |
| Context | Operator sees estimates/blocks adjacent to approve action |
| Video/voice/subtitle safety | No changes to upstream runtime panels |
| Discoverability | Approval tied to `assembly_generation` slot + dry-run completion |
| Parity | Voice approval actions already live inside voice panel |

### Compact mode

When `compact={true}` (Execution Center list embed):

- Show read-only approval gate fields if space allows
- **Hide** action buttons (or show disabled row with tooltip: "Open session for assembly approval actions")

---

## Control Specifications

### Safe labels (required)

| Control | Label |
|---------|-------|
| Approve | **Approve assembly** |
| Reject | **Reject approval** |
| Expire | **Expire approval** |
| Reset | **Reset approval** |

### Forbidden labels (validator grep — must never appear on buttons or primary CTAs)

- `Run Assembly`
- `Generate Final Video`
- `Export Final Video`
- `Run FFmpeg`
- `Create MP4`
- `Build Final`

Secondary safety copy may mention FFmpeg in **disclaimer** context only (e.g. "does not run FFmpeg") — same pattern as existing `ASSEMBLY_SAFETY_COPY` in `assemblyRuntimeObservability.ts`.

---

### 1. Approve assembly

**Label:** `Approve assembly`  
**Variant:** Primary (non-danger)

#### Visibility (all must pass)

| # | Condition | Source |
|---|-----------|--------|
| 1 | `assembly_generation` slot exists | `findAssemblyRuntimeSlot()` |
| 2 | Dry-run completed successfully | `status === "completed"` AND `dry_run === true` AND `planned_steps.length >= 1` |
| 3 | Plan READY | `validation_status === "READY"` (slot or preflight) |
| 4 | Approval actionable | `approval_state ∈ { required, not_required, rejected, expired }` AND not valid active `approved` |
| 5 | Real assembly path available | Operator may request real assembly (`not_required` → approve sets `request_real_assembly: true`) |
| 6 | Session not archived | `operations_control.archived !== true` |
| 7 | Session not cancelled | `operations_control.cancel_requested !== true` |
| 8 | No active assembly run | `status !== "running"` |

**Note on `not_required`:** Approve is visible when dry-run completed and plan READY but operator has not yet requested real assembly — clicking Approve sends `request_real_assembly: true` and grants approval in one step (matches 11J-14 engine).

#### Disabled (visible but disabled) when

- Dry-run not completed (show inline reason: "Complete assembly dry-run first")
- Plan not READY (`validation_status !== READY`)
- Already approved and not expired
- Session archived / cancelled (banner)

#### Confirmation modal

**Title:** `Approve assembly?`

**Body copy:**

```
This approves future real assembly execution for this session only.
It does not run FFmpeg or generate the final video in this phase.

Expected output:        {expectedOutput}
Estimated runtime:      {estimatedRuntimeSeconds}
Estimated output size:  {estimatedOutputSize}
Estimated disk usage:   {estimatedDiskUsage}
Approval TTL:           {ttlMinutes} minutes (default 30)
```

**Blocked reasons (if any):** Render `assembly_blocked_reasons[]` as chips/list below estimates — operator sees env-flag blocks (e.g. `ASSEMBLY_REAL_EXECUTION_DISABLED`) **before** confirming. Approval may succeed while `assembly_eligible` remains false — show post-success note.

**Warning (prominent):**

> This only approves future real assembly execution. It does not run FFmpeg or generate the final video yet.

**Fields:**

| Field | Required | Default |
|-------|----------|---------|
| Reason | Optional | empty |
| TTL (minutes) | Optional | 30 (clamped 15–1440 in backend) |

**Confirm sends:**

```json
POST /sessions/{session_id}/assembly/approve
{
  "request_real_assembly": true,
  "reason": "<operator note>",
  "ttl_minutes": 30,
  "approved_by": "operator"
}
```

**Post-success:** Assert `response.real_assembly_executed === false`; show success message from API.

---

### 2. Reject approval

**Label:** `Reject approval`  
**Variant:** Danger

#### Visibility

| Condition | Required |
|-----------|----------|
| Assembly slot exists | Yes |
| `approval_state ∈ { required, approved }` | Yes |
| No assembly run active (`status !== "running"`) | Yes |
| Session not archived | Yes |

#### Modal

**Title:** `Reject assembly approval?`

**Copy:** Blocks real assembly until re-approved. Does not run FFmpeg or delete upstream artifacts.

**Reason:** Optional.

**Request:**

```json
POST /sessions/{session_id}/assembly/reject
{
  "reason": "...",
  "rejected_by": "operator"
}
```

---

### 3. Expire approval

**Label:** `Expire approval`  
**Variant:** Neutral

#### Visibility

| Condition | Required |
|-----------|----------|
| `approval_state === approved` (effective, not TTL-expired) | Yes |
| No assembly run active | Yes |

#### Modal

**Title:** `Expire assembly approval?`

**Copy:** Immediately revokes approval. Real assembly remains blocked until re-approved.

**Request:**

```json
POST /sessions/{session_id}/assembly/expire
{
  "reason": "...",
  "expired_by": "operator"
}
```

---

### 4. Reset approval

**Label:** `Reset approval`  
**Variant:** Neutral

#### Visibility

| Condition | Required |
|-----------|----------|
| `approval_state ∈ { rejected, expired, approved }` | Yes |
| Assembly slot exists | Yes |
| No assembly run active | Yes |

#### Modal

**Title:** `Reset assembly approval?`

**Copy:** Clears approval grant fields and recalculates gate state. Does not execute assembly.

**Note:** Unlike voice, assembly reset does **not** expose `clear_real_assembly_request` in 11J-14 backend — omit checkbox in 11J-16 unless a future API field is added.

**Request:**

```json
POST /sessions/{session_id}/assembly/reset-approval
{
  "reason": "...",
  "reset_by": "operator"
}
```

---

### Read-only blocked reasons (always on)

Existing **Assembly approval gate** subsection remains **always visible** above action controls:

| Display | Source |
|---------|--------|
| Approval required | `approval.approval_required` |
| Approval state | `approval.approval_state` |
| Assembly eligible | `approval.assembly_eligible` |
| Blocked reasons | `approval.assembly_blocked_reasons[]` |
| Estimates | `estimated_runtime_seconds`, `estimated_output_size`, `estimated_disk_usage` |

When actions are unavailable, show inline **Why actions are hidden** derived from eligibility resolver (no silent empty section).

---

## Button Visibility Matrix

| Session / slot state | Approve | Reject | Expire | Reset |
|----------------------|---------|--------|--------|-------|
| No assembly slot / legacy empty | — | — | — | — |
| Plan not READY | — | — | — | — |
| Dry-run not completed | — | — | — | — |
| Ready + dry-run done + `not_required` | ✓ | — | — | — |
| Ready + dry-run done + `required` | ✓ | ✓ | — | — |
| `approved` (valid TTL) | — | ✓ | ✓ | ✓ |
| `approved` (TTL expired) | ✓ | — | — | ✓ |
| `rejected` | ✓ | — | — | ✓ |
| `expired` | ✓ | — | — | ✓ |
| `running` assembly | — | — | — | — |
| Archived session | disabled all | disabled all | disabled all | disabled all |
| Cancel requested | disabled all | disabled all | disabled all | disabled all |

**Legend:** ✓ = enabled when eligibility passes; — = hidden; disabled all = greyed with reason banner.

---

## Human-Readable Block Messages

| Code | User message |
|------|--------------|
| `REAL_ASSEMBLY_NOT_REQUESTED` | Real assembly not requested — use Approve assembly to authorize future execution. |
| `ASSEMBLY_PLAN_NOT_READY` | Assembly plan is not READY — complete upstream artifacts and dry-run first. |
| `ASSEMBLY_DRY_RUN_NOT_COMPLETED` | Assembly dry-run has not completed — run dry-run before approving. |
| `ASSEMBLY_APPROVAL_REQUIRED` | Operator approval required before real assembly can run. |
| `ASSEMBLY_APPROVAL_REJECTED` | Assembly was rejected — reset or re-approve to continue. |
| `ASSEMBLY_APPROVAL_EXPIRED` | Approval expired — re-approval required. |
| `ASSEMBLY_REAL_EXECUTION_DISABLED` | Real assembly is globally disabled (environment flag). |
| `ASSEMBLY_RUNTIME_EXECUTION_DISABLED` | Runtime execution approval flag is off. |
| `ASSEMBLY_SESSION_ARCHIVED` | Session is archived — approval actions disabled. |
| `ASSEMBLY_CANCELLED` | Session cancellation requested — approval actions disabled. |
| `ASSEMBLY_RUN_ACTIVE` | Assembly run in progress — wait for completion. |

Map via `assemblyApprovalLabels.ts` (11J-16), mirroring `voiceApprovalLabels.ts`.

---

## API Integration Plan

### Client module (11J-16)

**File:** `ui/web/src/api/assemblyApprovalClient.ts`

```typescript
export type AssemblyApprovalActionResponse = {
  success: boolean;
  session_id: string;
  action: string;
  message: string;
  code?: string | null;
  reject_reasons?: string[];
  assembly_slot?: Record<string, unknown> | null;
  guard_result?: Record<string, unknown> | null;
  panel_excerpt?: Record<string, unknown> | null;
  audit_event?: Record<string, unknown> | null;
  real_assembly_executed: boolean;  // MUST be false — UI asserts on every response
  api_version?: string;
};

export class AssemblyApprovalSafetyError extends Error { /* ... */ }

export function assertAssemblyApprovalSafety(response: AssemblyApprovalActionResponse): void {
  if (response.real_assembly_executed !== false) {
    throw new AssemblyApprovalSafetyError(
      "Assembly approval safety check failed: real_assembly_executed was not false.",
    );
  }
}

export async function postAssemblyApprove(sessionId: string, body: AssemblyApproveRequest): Promise<AssemblyApprovalActionResponse>;
export async function postAssemblyReject(sessionId: string, body: AssemblyRejectRequest): Promise<AssemblyApprovalActionResponse>;
export async function postAssemblyExpire(sessionId: string, body: AssemblyExpireRequest): Promise<AssemblyApprovalActionResponse>;
export async function postAssemblyResetApproval(sessionId: string, body: AssemblyResetApprovalRequest): Promise<AssemblyApprovalActionResponse>;
```

### Request bodies (match 11J-14 schemas)

| Action | Body fields |
|--------|-------------|
| Approve | `request_real_assembly: true`, `reason?`, `ttl_minutes?`, `approved_by?` |
| Reject | `reason?`, `rejected_by?` |
| Expire | `reason?`, `expired_by?` |
| Reset | `reason?`, `reset_by?` |

### Response handling

| HTTP | UI behavior |
|------|-------------|
| 200 + `success: true` | Close modal; refresh; show success; assert `real_assembly_executed === false` |
| 409 + `success: false` | Keep modal open or inline error; display `reject_reasons` + `message` |
| 404 | Session not found banner |
| Network error | Retry prompt; **no optimistic UI** |
| Missing `real_assembly_executed` field | **Safety error** — do not update UI; show hard error banner |

### Forbidden client behavior

| Forbidden | Reason |
|-----------|--------|
| `POST /assembly/run` with `dry_run: false` | Real execution disabled |
| Any FFmpeg / subprocess invocation | Out of scope |
| Setting env flags client-side | Backend-only |
| Optimistic approval state mutation | Stale UI risk |

---

## Eligibility Resolver (client-side, 11J-16)

**File:** `ui/web/src/utils/assemblyApprovalEligibility.ts`

Pure function — no API calls:

```typescript
export type AssemblyApprovalAction = "approve" | "reject" | "expire" | "reset";

export type AssemblyActionEligibility = {
  allowed: boolean;
  visible: boolean;
  reason: string;
};

export type AssemblySessionContext = {
  archived?: boolean;
  cancelRequested?: boolean;
  isLegacy?: boolean;
};

export function evaluateAssemblyApprovalEligibility(
  assembly: AssemblyRuntimeObservability,
  rawSlot: CategoryRuntimeSlot | null,
  session: AssemblySessionContext,
): Record<AssemblyApprovalAction, AssemblyActionEligibility>;
```

**Dry-run completed helper:**

```typescript
export function isAssemblyDryRunCompleted(slot: CategoryRuntimeSlot): boolean {
  return (
    String(slot.status).toLowerCase() === "completed" &&
    slot.dry_run === true &&
    Array.isArray(slot.planned_steps) &&
    slot.planned_steps.length >= 1
  );
}
```

Mirrors `assembly_approval_action_policy.py` rules using observability + raw slot fields. Extend `AssemblyRuntimeObservability` type in 11J-16 with raw keys needed for eligibility (`dryRunCompleted`, `validationStatusKey`, `approvalStateKey`, `hasAssemblySlot`).

Optional future: `GET /sessions/{id}/assembly/approval/eligibility` — not required for 11J-16.

---

## Refresh Behavior

After any successful assembly approval action:

| Refresh target | Method |
|----------------|--------|
| Runtime status | `fetchRuntimeStatus(sessionId)` — updates `category_runtime_slots` |
| Session detail | `fetchSession(sessionId)` — updates drawer + audit |
| Local last-result | Store `AssemblyApprovalActionResponse` in component state |

**Sequence:**

1. User confirms modal → POST assembly approval action
2. Assert `real_assembly_executed === false`
3. Parallel refresh: runtime status + session detail (via `onAssemblyApprovalSuccess` callback)
4. Re-render `AssemblyRuntimeObservabilityPanel` from refreshed props
5. Optionally show `response.audit_event` in local history line

**No optimistic update** — wait for server refresh before showing new approval state.

### Wiring (11J-16)

Extend `RuntimeObservability.tsx` parallel to voice:

```typescript
<AssemblyRuntimeObservabilityPanel
  status={status}
  legacyPanel={legacyPanel}
  compact={compact}
  sessionId={sessionId}
  sessionContext={sessionContext}
  onAssemblyApprovalSuccess={onAssemblyApprovalSuccess}
/>
```

`SessionDrawer` passes shared refresh handler (same pattern as `onVoiceApprovalSuccess`).

Video, voice, and subtitle panels re-render from same `RuntimeStatusResponse` — no assembly-specific changes to their KV grids.

---

## Error Display Plan

| Error type | Display location |
|------------|------------------|
| Precondition failed (409) | Modal inline alert + `reject_reasons` chips |
| Already approved | "Assembly is already approved until {expiry}" |
| Dry-run not completed | Persistent note in actions section |
| Plan not READY | Persistent note with validation status |
| Archived session | Grey banner: "Session archived — assembly approval actions disabled." |
| API unreachable | Error banner (match voice approval style) |
| Unexpected `real_assembly_executed` | Hard safety error banner + log; **do not** update approval UI |
| Missing safety field on response | Treat as safety error (fail closed) |

Parse backend `message` for operator-readable text; map `reject_reasons` via block message table.

Show current **approval state** in modal header and error blocks.

---

## Safety Rules (UI)

Controls must **never**:

| Rule | Enforcement |
|------|-------------|
| Call `/assembly/run` with `dry_run=false` | No such client function; grep validator |
| Run FFmpeg | No client-side media code |
| Generate `FINAL_PUBLISH_READY.mp4` | No download/export actions |
| Enable real execution env flags | Read-only display of block codes |
| Mutate upstream slots | Backend enforced; UI only refreshes read-only views |

Every API response must satisfy:

```typescript
response.real_assembly_executed === false
```

If the field is missing or not `false`:

- Throw `AssemblyApprovalSafetyError`
- Show safety error banner
- **Do not** silently update approval KV fields

### Persistent banner (above action buttons)

```
Assembly approval actions authorize future real assembly execution metadata only.
No FFmpeg runs and no final video is generated in this phase. real_assembly_executed is always false.
```

### Approve modal footer

```
Approving does not invoke FFmpeg. Real assembly execution requires a separate future gated phase.
```

---

## Legacy Session Safety

| Condition | UI behavior |
|-----------|-------------|
| No `execution_runtime` | Hide action section; "Legacy session — assembly approval unavailable." |
| No `assembly_generation` slot | Hide actions; read-only panel shows dashes |
| No `approval` block | Gate shows `—`; actions hidden |
| No `category_runtime_slots` | Derive from `legacyPanel`; if empty, no controls |
| Dry-run never run | Approve hidden; blocked reason explains |
| Missing `planned_steps` | Treat as dry-run incomplete |

Never throw on missing fields — match `resolveAssemblyRuntimeObservability()` dash fallbacks.

---

## Component Structure (11J-16 target)

| File | Role |
|------|------|
| `ui/web/src/utils/assemblyApprovalEligibility.ts` | Client eligibility |
| `ui/web/src/utils/assemblyApprovalLabels.ts` | Block code → human message + banners |
| `ui/web/src/api/assemblyApprovalClient.ts` | API wrappers + safety assert |
| `ui/web/src/components/AssemblyApprovalControlsPanel.tsx` | Action buttons + audit excerpt |
| `ui/web/src/components/AssemblyApprovalConfirmDialog.tsx` | Modal (mirror `VoiceApprovalConfirmDialog`) |
| `ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx` | Embed controls subsection |
| `ui/web/src/utils/assemblyRuntimeObservability.ts` | Extend DTO with eligibility helpers |
| `ui/web/src/App.css` | `.assembly-approval-actions`, `.assembly-approval-modal` |

**Do not modify:** Video/voice/subtitle runtime engines, Runway/Hailuo panels, `AssemblyFFmpegExecutor` real branch, `full_video_pipeline.py`.

---

## Validation Plan (11J-16 implementation)

**Validator:** `project_brain/validate_11j16_assembly_approval_ui_controls.py`

| # | Test | Expected |
|---|------|----------|
| 1 | Eligibility: plan not READY → approve hidden | PASS |
| 2 | Eligibility: dry-run not completed → approve hidden | PASS |
| 3 | Eligibility: dry-run done + READY + required → approve visible | PASS |
| 4 | Eligibility: approved → expire + reset visible | PASS |
| 5 | Static grep: forbidden labels absent from button text | PASS |
| 6 | Approve modal contains metadata-only FFmpeg warning | PASS |
| 7 | Client asserts `real_assembly_executed === false` | PASS |
| 8 | Video/voice/subtitle observability unchanged (grep) | PASS |
| 9 | Legacy session: no crash, actions hidden | PASS |
| 10 | API client maps four assembly endpoints | PASS |
| 11 | No `/assembly/run` dry_run=false in new UI files | PASS |
| 12 | `npm run build` | PASS |
| 13 | Nested 11J-14 + 11J-12 + 11J-10 validators | PASS |

Extend existing `uiContainsAssemblyForbiddenActions()` or add panel-specific scan that excludes safety disclaimer copy (same pattern as 11J-10 validator).

---

## Files Likely to Change (11J-16)

### Create

| File | Purpose |
|------|---------|
| `ui/web/src/utils/assemblyApprovalEligibility.ts` | Visibility rules |
| `ui/web/src/utils/assemblyApprovalLabels.ts` | Copy + block messages |
| `ui/web/src/api/assemblyApprovalClient.ts` | Four POST wrappers |
| `ui/web/src/components/AssemblyApprovalControlsPanel.tsx` | Button row + errors |
| `ui/web/src/components/AssemblyApprovalConfirmDialog.tsx` | Confirm modals |
| `project_brain/validate_11j16_assembly_approval_ui_controls.py` | Validator |
| `project_brain/PHASE_11J16_ASSEMBLY_APPROVAL_UI_CONTROLS_REPORT.md` | Implementation report |

### Modify

| File | Change |
|------|--------|
| `ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx` | Embed controls subsection |
| `ui/web/src/components/RuntimeObservability.tsx` | Pass `sessionId`, `sessionContext`, `onAssemblyApprovalSuccess` |
| `ui/web/src/components/SessionDrawer.tsx` | Wire refresh callback (if not already shared) |
| `ui/web/src/utils/assemblyRuntimeObservability.ts` | Eligibility helper fields |
| `ui/web/src/App.css` | Assembly approval action styles |

### Must NOT modify (11J-16)

| Area | Reason |
|------|--------|
| `AssemblyFFmpegExecutor` real execution path | Future gated phase |
| `AssemblyRuntimeEngine` real branch | 11J-17+ |
| `ui/api/main.py` assembly approval routes | Complete in 11J-14 |
| Video / voice / subtitle run services | Isolation |
| Runway / Hailuo / `full_video_pipeline.py` | Constraints |
| Env flags `MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED` | Backend-only |

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Operator thinks Approve runs FFmpeg | **Critical** | Modal warning + persistent banner + `real_assembly_executed` assert |
| Confusion with dry-run "Run" elsewhere | **High** | Forbidden labels; no Run Assembly button |
| Stale UI after action | **Medium** | Mandatory dual refresh; no optimistic updates |
| Client/server eligibility drift | **Medium** | Mirror 11J-14 policy rules in eligibility util |
| Accidental buttons in compact view | **Low** | Hide actions when `compact={true}` |
| `FINAL_PUBLISH_READY.mp4` implied by expected output preview | **Medium** | Keep "Expected Output Only" badge; approve modal states "not generated yet" |

---

## Implementation Slices

| Phase | Scope | FFmpeg | Output file | UI buttons |
|-------|-------|--------|-------------|------------|
| **11J-15** | This design doc | No | No | No |
| **11J-16** | Approval UI controls wired to 11J-14 APIs | No | No | Yes (metadata only) |
| **11J-17+** | Wire guard into assembly run for `dry_run=false` | No until env gate | No | Still no Run Assembly |
| **11J-18+** | Real FFmpeg execution enablement | Separate phase | Only when executor succeeds | Run Assembly (future, explicit gate) |

---

## Confirmation Checklist (Design Phase)

| Requirement | Design status |
|-------------|---------------|
| UI placement in `AssemblyRuntimeObservabilityPanel` | Yes — below read-only gate |
| Four controls specified | Yes — approve, reject, expire, reset |
| Button visibility matrix | Yes |
| Modal copy + FFmpeg warning | Yes |
| API mapping to 11J-14 endpoints | Yes |
| `real_assembly_executed === false` assert | Yes |
| Forbidden labels listed | Yes |
| Refresh behavior (no optimistic) | Yes |
| Error display plan | Yes |
| Legacy session safety | Yes |
| No working buttons in this phase | Yes — design only |
| No Run Assembly / no FFmpeg | Yes |

---

## Next Recommended Phase

**PHASE 11J-16 — Assembly Approval UI Controls Implementation**

- Working buttons wired to 11J-14 APIs
- Confirmation modals with safety copy
- Eligibility gating + dual refresh
- Validator matrix + report
- Still no FFmpeg / no `FINAL_PUBLISH_READY.mp4` / no Run Assembly button

**Do not enable real assembly execution without explicit user approval in a separate future phase.**

---

## Files Analyzed

| File | Relevance |
|------|-----------|
| `ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx` | Current read-only assembly UI |
| `ui/web/src/utils/assemblyRuntimeObservability.ts` | Observability resolver + safety copy |
| `ui/web/src/components/VoiceApprovalControlsPanel.tsx` | Reference implementation pattern |
| `ui/web/src/components/VoiceApprovalConfirmDialog.tsx` | Modal pattern |
| `ui/web/src/api/voiceApprovalClient.ts` | Client + safety assert pattern |
| `ui/api/schemas/assembly_approval.py` | Request/response shapes |
| `content_brain/execution/assembly_approval_action_policy.py` | Server precondition rules |
| `project_brain/PHASE_11J14_ASSEMBLY_APPROVAL_WRITE_APIS_REPORT.md` | Backend contract |
| `project_brain/PHASE_11H1H_VOICE_APPROVAL_UI_CONTROLS_DESIGN.md` | Structural template |
