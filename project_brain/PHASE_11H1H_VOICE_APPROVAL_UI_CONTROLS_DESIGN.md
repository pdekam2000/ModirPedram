# Phase 11H-1h — Voice Approval UI Controls Design

**Status:** Design only — no implementation, no working buttons, no live TTS  
**Date:** 2026-05-28  
**Prerequisites:** Phase 11G, 11H-1a–1g complete  
**Goal:** Design safe Voice Approval UI controls for Execution Center that call 11H-1g backend APIs without ever triggering live TTS

---

## Executive Summary

Execution Center already shows **read-only** voice observability in `VoiceRuntimeObservabilityPanel` (11H-1c/1e): preflight status, approval gate fields, and blocked reasons. Phase 11H-1g added **backend-only** write APIs that mutate approval metadata and append audit events — always returning `tts_executed: false`.

Phase 11H-1h designs operator controls that mirror the existing **Session Actions** pattern (`SessionActionsPanel` + `ConfirmActionDialog` + eligibility gating) but scoped to **category voice approval**, not session-level retry/cancel/archive.

**Key principle:** Approve Voice authorizes **future** ElevenLabs spend metadata only. It does **not** generate audio. No control may trigger live TTS until explicit Phase 11H-2 approval.

**Do not start Phase 11H-2.**

---

## Current UI Architecture

### Placement today

```
SessionDrawer / ExecutionCenterPage
  └── RuntimeObservabilityPanel
        ├── Video runtime (clip artifacts, validation, failover)
        ├── CategoryRuntimeSlotsPanel
        └── VoiceRuntimeObservabilityPanel   ← read-only voice + approval gate
              ├── voice_generation status
              └── voice-approval-gate-section (KV fields)
```

Session-level operator actions live on a separate **Actions** tab via `SessionActionsPanel` (retry, cancel, archive, requeue).

### Data sources

| Source | Fields used |
|--------|-------------|
| `RuntimeStatusResponse.category_runtime_slots[]` | Voice slot status, preflight, approval |
| `legacyPanel` / `provider_runtime_panel.data` | Fallback for older sessions |
| `resolveVoiceRuntimeObservability()` | Normalized display + approval block |
| `SessionDetail.session.operations_control` | Archived, cancel_requested |
| `SessionDetail.status` | Session state |

### Backend APIs (11H-1g — implemented)

| Endpoint | Purpose |
|----------|---------|
| `POST /sessions/{id}/voice/approve` | Grant approval + set `live_tts_requested` |
| `POST /sessions/{id}/voice/reject` | Reject approval |
| `POST /sessions/{id}/voice/expire` | Force expire |
| `POST /sessions/{id}/voice/reset-approval` | Clear grant; re-evaluate gate |

All return `VoiceApprovalActionResponse` with `tts_executed: false`.

---

## UI Placement Plan

### Recommended layout (11H-1i)

Add a **Voice approval actions** subsection **inside** `VoiceRuntimeObservabilityPanel`, directly below the existing read-only approval gate KV grid:

```
Voice runtime
  [status badge]
  [preflight KV grid]

Voice approval gate          ← existing read-only (11H-1e)
  [approval KV grid]
  [blocked reasons — always visible]

Voice approval actions       ← NEW (11H-1i)
  [safety banner — metadata only]
  [eligibility cards OR compact button row]
  [last action result]
  [voice_approval_audit excerpt]
```

### Why nested under voice panel (not Actions tab)

| Reason | Detail |
|--------|--------|
| Category scope | Voice approval ≠ session retry/cancel |
| Context | Operator sees estimates/blocks adjacent to action |
| Video safety | Actions tab stays session-level; video observability unchanged |
| Discoverability | Approval is tied to `voice_generation` slot state |

### Compact mode

When `compact={true}` (Execution Center list embed):

- Show read-only blocked reasons only
- Hide action buttons (or show disabled row with tooltip: "Open session for voice approval actions")

---

## Control Specifications

### 1. Approve Voice

**Label:** `Approve voice`  
**Variant:** Primary (non-danger)  
**Never label:** Generate Voice, Run TTS, Generate Narration

#### Visibility (all must pass)

| # | Condition | Source |
|---|-----------|--------|
| 1 | Provider = `elevenlabs` | `voice.provider` |
| 2 | Narration exists | `status !== skipped`, `segment_count > 0` |
| 3 | Preflight ready | `voice_preflight.ready === true` |
| 4 | Approval actionable | `approval_state ∈ { required, not_required }` **and** approve path available |
| 5 | Not already approved (valid) | `approval_state !== approved` OR expired |
| 6 | No voice TTS running | `voice.status !== running`, `live_tts !== true`, `executed !== true` with live flag |
| 7 | Session not archived | `operations_control.archived !== true` |
| 8 | Session not cancelled | `operations_control.cancel_requested !== true` |
| 9 | Credentials present | `error.code !== CREDENTIALS_MISSING` |

**Note on `not_required`:** Approve is visible when preflight is ready and approval is `not_required` because operator has not yet requested live TTS — clicking Approve sends `request_live_tts: true` and grants approval in one step (matches 11H-1g engine behavior).

#### Disabled (visible but disabled) when

- Estimates missing (`estimated_character_count === 0`)
- Character/cost limits exceeded (show block reason)
- Session archived / cancelled (show banner)

#### Confirmation modal

**Title:** `Approve voice generation?`

**Body copy:**

```
This approves future ElevenLabs voice generation for this session only.
It does not generate audio in this phase.

Estimated characters: {estimatedCharacters}
Estimated segments:   {estimatedSegments}
Estimated voice cost: {estimatedVoiceCost} (placeholder — not billing)
Approval TTL:         {ttlMinutes} minutes (default 240)
```

**Warning (prominent):**

> This only approves future voice generation. It does not generate audio yet.

**Fields:**

| Field | Required | Default |
|-------|----------|---------|
| Reason | Optional | empty |
| TTL (minutes) | Optional | 240 (hidden advanced: 15–1440) |

**Confirm sends:**

```json
POST /sessions/{session_id}/voice/approve
{
  "request_live_tts": true,
  "reason": "<operator note>",
  "ttl_minutes": 240,
  "approved_by": "operator"
}
```

**Post-success:** Assert `response.tts_executed === false`; show success toast with message from API.

---

### 2. Reject Voice

**Label:** `Reject voice`  
**Variant:** Danger

#### Visibility

| Condition | Required |
|-----------|----------|
| Voice slot exists | Yes |
| `approval_state ∈ { required, approved }` | Yes |
| No voice TTS running | Yes |
| Session not archived | Yes |

#### Modal

**Title:** `Reject voice approval?`

**Copy:** Blocks live TTS until re-approved. Does not generate or delete audio.

**Reason:** Optional (recommended, min 3 chars if provided — backend accepts empty).

**Request:**

```json
POST /sessions/{session_id}/voice/reject
{
  "reason": "...",
  "rejected_by": "operator"
}
```

---

### 3. Expire Approval

**Label:** `Expire approval`  
**Variant:** Neutral

#### Visibility

| Condition | Required |
|-----------|----------|
| `approval_state === approved` (not expired by TTL) | Yes |
| No voice TTS running | Yes |

#### Modal

**Title:** `Expire voice approval?`

**Copy:** Immediately revokes approval. Live TTS will remain blocked until re-approved.

**Request:**

```json
POST /sessions/{session_id}/voice/expire
{
  "reason": "...",
  "expired_by": "operator"
}
```

---

### 4. Reset Approval

**Label:** `Reset approval`  
**Variant:** Neutral

#### Visibility

| Condition | Required |
|-----------|----------|
| `approval_state ∈ { rejected, expired, approved }` | Yes |
| Voice slot exists | Yes |

#### Modal

**Title:** `Reset voice approval?`

**Copy:** Clears approval grant fields and recalculates gate state. Does not execute TTS.

**Optional checkbox:** `Clear live TTS request` → `clear_live_tts_request: true`

**Request:**

```json
POST /sessions/{session_id}/voice/reset-approval
{
  "reason": "...",
  "reset_by": "operator",
  "clear_live_tts_request": false
}
```

---

### 5. Read-only blocked reasons (always on)

Existing fields remain **always visible** above action controls:

| Display | Source |
|---------|--------|
| Blocked because | `approval.live_tts_blocked_reasons[]` |
| Approval state | `approval.approval_state` |
| Live TTS eligible | `approval.live_tts_eligible` |
| Error code / preflight code | credentials, preflight |

#### Human-readable block messages (priority order)

| Code | User message |
|------|--------------|
| `NO_NARRATION` | No narration text available — voice approval unavailable. |
| `CREDENTIALS_MISSING` | ElevenLabs API key missing — configure credentials before approval. |
| `PREFLIGHT_NOT_READY` | Voice preflight not ready. |
| `LIVE_TTS_NOT_REQUESTED` | Live TTS not requested — use Approve to authorize future generation. |
| `VOICE_APPROVAL_REQUIRED` | Operator approval required before live TTS can run. |
| `VOICE_APPROVAL_REJECTED` | Voice generation was rejected. |
| `APPROVAL_EXPIRED` | Approval expired — re-approval required. |
| `VOICE_CHARACTER_LIMIT_EXCEEDED` | Estimated character count exceeds limit. |
| `VOICE_COST_LIMIT_EXCEEDED` | Estimated cost exceeds budget cap. |
| `BUDGET_BLOCKED` | Session budget blocks voice spend. |
| `OPERATIONS_CANCELLED` | Session cancellation requested. |

When actions are unavailable, show inline **Why actions are hidden** derived from the same resolver (no silent empty section).

---

## Button Visibility Matrix

| Session / slot state | Approve | Reject | Expire | Reset |
|----------------------|---------|--------|--------|-------|
| No voice slot / legacy empty | — | — | — | — |
| No narration (`skipped`) | — | — | — | — |
| Credentials missing | — | — | — | — |
| Preflight not ready | — | — | — | — |
| Ready + `not_required` | ✓ | — | — | — |
| Ready + `required` | ✓ | ✓ | — | — |
| `approved` (valid) | — | ✓ | ✓ | ✓ |
| `approved` (TTL expired) | ✓ | — | — | ✓ |
| `rejected` | ✓* | — | — | ✓ |
| `expired` | ✓ | — | — | ✓ |
| Archived session | disabled all | disabled all | disabled all | disabled all |
| Cancel requested | disabled all | disabled all | disabled all | disabled all |
| Voice `running` / live TTS | — | — | — | — |

\*Approve from `rejected` after reset or direct approve if backend allows re-approve path (11H-1g: approve from `rejected`/`expired` allowed).

**Legend:** ✓ = enabled when clicked through eligibility; — = hidden; disabled all = visible greyed with reason banner.

---

## API Integration Plan

### Client module (11H-1i)

**File:** `ui/web/src/api/voiceApprovalClient.ts` (or extend `client.ts`)

```typescript
export type VoiceApprovalActionResponse = {
  success: boolean;
  session_id: string;
  action: string;
  message: string;
  code?: string | null;
  reject_reasons?: string[];
  voice_slot?: Record<string, unknown> | null;
  guard_result?: Record<string, unknown> | null;
  panel_excerpt?: Record<string, unknown> | null;
  audit_event?: Record<string, unknown> | null;
  tts_executed: boolean;  // MUST be false — UI asserts on every response
  api_version?: string;
};

export async function postVoiceApprove(sessionId: string, body: VoiceApproveRequest): Promise<VoiceApprovalActionResponse>;
export async function postVoiceReject(sessionId: string, body: VoiceRejectRequest): Promise<VoiceApprovalActionResponse>;
export async function postVoiceExpire(sessionId: string, body: VoiceExpireRequest): Promise<VoiceApprovalActionResponse>;
export async function postVoiceResetApproval(sessionId: string, body: VoiceResetApprovalRequest): Promise<VoiceApprovalActionResponse>;
```

### Request bodies (match 11H-1g schemas)

| Action | Body fields |
|--------|-------------|
| Approve | `request_live_tts: true`, `reason?`, `ttl_minutes?`, `approved_by?` |
| Reject | `reason?`, `rejected_by?` |
| Expire | `reason?`, `expired_by?` |
| Reset | `reason?`, `reset_by?`, `clear_live_tts_request?` |

### Response handling

```typescript
function assertNoTtsExecuted(response: VoiceApprovalActionResponse): void {
  if (response.tts_executed !== false) {
    throw new Error("Unexpected tts_executed flag — voice UI safety abort.");
  }
}
```

| HTTP | UI behavior |
|------|-------------|
| 200 + `success: true` | Close modal; refresh; show success |
| 409 + `success: false` | Keep modal open or show inline error; display `reject_reasons` |
| 404 | Session not found banner |
| Network error | Retry prompt; no optimistic UI |

### Optimistic updates

**Do not** optimistically mutate approval state. Always refresh from server after success.

---

## Eligibility Resolver (client-side, 11H-1i)

**File:** `ui/web/src/utils/voiceApprovalEligibility.ts`

Pure function — no API calls:

```typescript
export type VoiceApprovalAction = "approve" | "reject" | "expire" | "reset";

export type VoiceActionEligibility = {
  allowed: boolean;
  visible: boolean;
  reason: string;
};

export function evaluateVoiceApprovalEligibility(
  voice: VoiceRuntimeObservability,
  session: { archived?: boolean; cancelRequested?: boolean },
): Record<VoiceApprovalAction, VoiceActionEligibility>;
```

Mirrors `voice_approval_action_policy.py` rules using observability DTO fields. Optional future: `GET /sessions/{id}/voice/approval/eligibility` — not required for 11H-1i.

---

## Refresh Behavior

After any successful voice approval action:

| Refresh target | Method |
|----------------|--------|
| Runtime status | `fetchRuntimeStatus(sessionId)` — updates `category_runtime_slots` |
| Session detail | `fetchSession(sessionId)` — updates panels + audit |
| Local last-result | Store `VoiceApprovalActionResponse` in component state |

**Sequence:**

1. User confirms modal → POST voice action
2. Assert `tts_executed === false`
3. Parallel refresh: runtime status + session detail
4. Update `VoiceRuntimeObservabilityPanel` via new props/state
5. Append audit line from `response.audit_event` to local history list

If session drawer is on **Actions** tab, do not auto-switch tabs. Voice panel updates in **Overview/Runtime** view.

Video observability sections re-render from same `RuntimeStatusResponse` — no voice-specific changes to video KV grid.

---

## Error Display Plan

| Error type | Display location |
|------------|------------------|
| Precondition failed (409) | Modal inline alert + `reject_reasons` chips |
| Already approved | "Voice is already approved until {expiry}" |
| Missing credentials | Persistent banner in voice panel (no approve button) |
| Archived session | Grey banner: "Session archived — voice approval actions disabled." |
| API unreachable | `runtime-poll-error` style banner |
| Unexpected `tts_executed` | Hard error banner + log (safety) |

Parse backend `message` for operator-readable text; map `reject_reasons` codes via block message table.

---

## Safety Wording (required copy)

### Persistent banner (above action buttons)

```
Voice approval actions authorize future ElevenLabs spend metadata only.
No audio is generated in this phase. tts_executed is always false.
```

### Approve modal footer

```
Approving does not call ElevenLabs. Live TTS execution requires a separate future phase.
```

### Forbidden UI strings (validator grep)

- `Generate voice`
- `Generate narration`
- `Run TTS`
- `Dispatch voice`
- `ElevenLabs generate`

### Session vs voice disambiguation

Label session tab actions as **Session actions** (existing).  
Label new controls as **Voice approval actions** (category-scoped).

---

## Legacy Session Safety

| Condition | UI behavior |
|-----------|-------------|
| No `execution_runtime` | Hide action section; show "Legacy session — voice approval unavailable." |
| No `approval` block | Read-only gate shows `—`; actions hidden |
| No `category_runtime_slots` | Derive from `legacyPanel`; if empty, no controls |
| Missing preflight | All write actions hidden; blocked reason explains |

Never throw on missing fields — match `resolveVoiceRuntimeObservability()` dash fallbacks.

---

## Component Structure (11H-1i target)

| File | Role |
|------|------|
| `ui/web/src/utils/voiceApprovalEligibility.ts` | Client eligibility |
| `ui/web/src/utils/voiceApprovalLabels.ts` | Block code → human message |
| `ui/web/src/api/voiceApprovalClient.ts` | API wrappers |
| `ui/web/src/components/VoiceApprovalControlsPanel.tsx` | Action cards + audit excerpt |
| `ui/web/src/components/VoiceApprovalConfirmDialog.tsx` | Modal (mirror `ConfirmActionDialog`) |
| `ui/web/src/components/VoiceRuntimeObservabilityPanel.tsx` | Embed controls subsection |
| `ui/web/src/App.css` | `.voice-approval-actions`, `.voice-approval-modal` |

**Do not modify:** `VideoProviderRouter`, video artifact sections, Runway/Hailuo panels.

---

## Validation Plan (11H-1i implementation)

**Validator:** `project_brain/validate_11h1i_voice_approval_ui_controls.py`

| # | Test | Expected |
|---|------|----------|
| 1 | Eligibility: no narration → approve hidden | PASS |
| 2 | Eligibility: credentials missing → approve hidden | PASS |
| 3 | Eligibility: preflight ready + required → approve visible | PASS |
| 4 | Eligibility: approved → expire + reset visible | PASS |
| 5 | Static grep: no Generate Voice / Run TTS | PASS |
| 6 | Approve modal copy contains metadata-only warning | PASS |
| 7 | Client asserts `tts_executed === false` | PASS |
| 8 | Video observability sections unchanged (grep) | PASS |
| 9 | Legacy session: no crash, actions hidden | PASS |
| 10 | API client maps four endpoints correctly | PASS |
| 11 | `npm run build` | PASS |
| 12 | Nested 11H-1g + 11H-1c validators | PASS |

**Note:** 11H-1i slice name says "Metadata Only" — first implementation may wire buttons to API with integration tests using mock fetch; still no live TTS.

---

## Files Likely to Change (11H-1i)

### Create

- `ui/web/src/utils/voiceApprovalEligibility.ts`
- `ui/web/src/utils/voiceApprovalLabels.ts`
- `ui/web/src/api/voiceApprovalClient.ts`
- `ui/web/src/components/VoiceApprovalControlsPanel.tsx`
- `ui/web/src/components/VoiceApprovalConfirmDialog.tsx`
- `project_brain/validate_11h1i_voice_approval_ui_controls.py`
- `project_brain/PHASE_11H1I_VOICE_APPROVAL_UI_CONTROLS_REPORT.md`

### Modify

- `ui/web/src/components/VoiceRuntimeObservabilityPanel.tsx`
- `ui/web/src/utils/categoryRuntimeShell.ts` (optional: export raw `approval_state` for eligibility)
- `ui/web/src/App.css`
- `ui/web/src/components/SessionDrawer.tsx` (pass `sessionId` + refresh callbacks if needed)

### Must NOT modify (11H-1i)

- `content_brain/execution/provider_runtime_engine.py` (video path)
- `VoiceProviderRouter` / ElevenLabs execution
- `ui/api/main.py` voice routes (already complete in 11H-1g)
- Legacy pipeline modules

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Operator thinks Approve generates audio | **Critical** | Modal + persistent banner + `tts_executed` assert |
| Confusion with session Approve | **High** | Separate section title "Voice approval actions" |
| Stale UI after action | **Medium** | Mandatory dual refresh (runtime + session) |
| Client/server eligibility drift | **Medium** | Mirror policy rules; optional future eligibility GET |
| Accidental button in compact view | **Low** | Hide actions when `compact={true}` |

---

## Implementation Slices

### Phase 11H-1i — Implement Voice Approval UI Controls (next)

1. Eligibility resolver + label map
2. API client wrappers with `tts_executed` assert
3. `VoiceApprovalControlsPanel` + confirm dialog
4. Wire into `VoiceRuntimeObservabilityPanel`
5. Refresh hooks from `SessionDrawer`
6. Validator + report
7. **Still no live TTS, no Generate Voice button**

### Phase 11H-2 — Live TTS Execution (explicit user approval required)

- Guard + `ElevenLabsVoiceProvider` behind separate explicit phase gate
- New "Generate voice" control **not** part of 11H-1i

**Do not start Phase 11H-2 without explicit user approval.**

---

## Confirmation Checklist (Design Phase)

| Requirement | Design status |
|-------------|---------------|
| Four controls specified | Yes — approve, reject, expire, reset |
| Button visibility matrix | Yes |
| Modal/confirmation copy | Yes — including metadata-only warning |
| API mapping | Yes — request/response handling |
| Refresh behavior | Yes |
| Error display plan | Yes |
| Safety wording | Yes |
| Read-only blocked reasons | Yes — always visible |
| Legacy session safety | Yes |
| No working buttons in this phase | Yes — design only |
| No live TTS | Yes |

---

## Next Recommended Slice

**Phase 11H-1i — Implement Voice Approval UI Controls**

- Working buttons wired to 11H-1g APIs
- Confirmation modals with safety copy
- Eligibility gating + refresh
- Validator matrix
- Still no live TTS / no Generate Voice

**Do not start Phase 11H-2.** Live ElevenLabs TTS requires explicit user approval in a separate phase.

---

## Files Analyzed

| File | Relevance |
|------|-----------|
| `ui/web/src/components/VoiceRuntimeObservabilityPanel.tsx` | Current read-only voice UI |
| `ui/web/src/utils/categoryRuntimeShell.ts` | Approval observability resolver |
| `ui/web/src/components/RuntimeObservability.tsx` | Parent panel — video unchanged |
| `ui/web/src/components/SessionActionsPanel.tsx` | Operator action pattern reference |
| `ui/web/src/components/ConfirmActionDialog.tsx` | Modal pattern reference |
| `ui/web/src/api/client.ts` | Session action client pattern |
| `ui/api/schemas/voice_approval.py` | Request/response shapes |
| `project_brain/PHASE_11H1G_VOICE_APPROVAL_WRITE_APIS_REPORT.md` | Backend contract |
