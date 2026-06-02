# Phase 11H-1f — Voice Approval Write APIs Design

**Status:** Design only — no implementation, no live TTS, no UI buttons  
**Date:** 2026-05-28  
**Prerequisites:** Phase 11G, 11H-1a–1e complete  
**Goal:** Define safe write APIs for category-scoped voice approval before any live ElevenLabs TTS can run

---

## Executive Summary

Voice live TTS approval is **category-scoped** on `execution_runtime.category_runtime.voice_generation.approval`. It is separate from session-level `approval_decision` (Phase 10F), which governs video queue/dispatch.

Phase 11H-1f designs four write endpoints that mutate **only** the voice slot approval block and audit metadata. They never call `ElevenLabsVoiceProvider`, never trigger HTTP to ElevenLabs, and never modify `video_generation` or Runway/Hailuo fields.

Implementation follows the existing **Operations Control** pattern (`OperationsControlEngine` → service → FastAPI route → session store persist → panel DTO return).

**Do not start Phase 11H-2.** Live ElevenLabs TTS requires explicit user approval in a separate phase.

---

## Current Architecture Summary

### Existing voice stack (11H-1a–1e)

| Component | Role |
|-----------|------|
| `SessionNarrationAdapter` | Narration from `beat_plans` |
| `apply_voice_preflight_dry_run()` | Dry-run preflight on video dispatch |
| `voice_approval_guard.evaluate_voice_approval_gate()` | Read-only approval metadata |
| `voice_approval_guard.can_run_live_voice_tts()` | Future live TTS guard (metadata only today) |
| `VoiceRuntimeObservabilityPanel` | Read-only UI (no action buttons) |

### Existing operator action pattern (10K-b)

```
POST /sessions/{id}/actions/{retry|cancel|archive|requeue}
  → OperationsControlService
  → OperationsControlEngine
  → eligibility check (operations_action_policy)
  → session mutation + operations_audit_log
  → OperationsActionResponse { ok, audit_event_id, ... }
```

Voice approval write APIs mirror this structure but target **voice slot approval only** and use a dedicated audit bucket: `execution_runtime.operations.voice_approval_audit`.

### Session approval vs voice approval

| Gate | Location | Question |
|------|----------|----------|
| Session `approval_decision` | Session root | May this session enter queue / dispatch **video**? |
| Session `budget_decision` | Session root | Is total run within budget cap? |
| Voice `approval` block | `voice_generation` slot | May this session spend ElevenLabs credits on **live TTS**? |

Write APIs in 11H-1g must **never** set `approval_decision.status = APPROVED_FOR_EXECUTION` as a side effect.

---

## Endpoint Design

Base path: `/sessions/{session_id}/voice`

All endpoints:

- Require session to exist (404 if missing)
- Return structured success/reject payload (200 / 409)
- Persist session via `ExecutionSessionStore.save_session(overwrite=True)`
- Include updated voice approval snapshot + guard result in response
- Optionally include `provider_runtime_panel` excerpt for Execution Center refresh

### Endpoint summary

| Method | Path | Action | Idempotent |
|--------|------|--------|------------|
| `POST` | `/sessions/{session_id}/voice/approve` | Grant voice TTS approval | No |
| `POST` | `/sessions/{session_id}/voice/reject` | Reject voice TTS approval | No |
| `POST` | `/sessions/{session_id}/voice/expire` | Force-expire current approval | Yes-ish* |
| `POST` | `/sessions/{session_id}/voice/reset-approval` | Clear approval fields; re-evaluate gate | No |

\*Expire is idempotent when already `expired`.

### Optional read endpoint (11H-1g+, not required for write slice)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sessions/{session_id}/voice/approval` | Read gate + eligibility without mutation |

---

## Request / Response Shapes

### Shared request body — `VoiceApprovalActionRequest`

```json
{
  "reason": "Operator reviewed narration estimate and approved TTS spend.",
  "actor": "operator",
  "request_live_tts": false
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `reason` | string | Approve: recommended; Reject/Expire: required (min 3 chars) | Never log credentials |
| `actor` | string | Optional | Default `operator`; may be `api`, `system`, `local_user` |
| `request_live_tts` | bool | Optional | **Approve only** — if `true`, sets `voice_generation.live_tts_requested=true` before gate evaluate |

### Approve-only fields — `VoiceApproveRequest` extends base

```json
{
  "reason": "Approved for narration generation after cost review.",
  "actor": "operator",
  "request_live_tts": true,
  "ttl_hours": 4
}
```

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `ttl_hours` | float | `4` | Clamped to `[0.25, 24]`; sets `approval_expires_at` |

### Success response — `VoiceApprovalActionResponse`

```json
{
  "ok": true,
  "action": "approve_voice",
  "session_id": "exec_abc123",
  "api_version": "0.6.0",
  "audit_event_id": "voice_appr_evt_20260528_120000_a1b2c3",
  "message": "Voice generation approved for live TTS (metadata only — no TTS executed).",
  "voice_generation": {
    "status": "pending",
    "provider": "elevenlabs",
    "live_tts_requested": true,
    "executed": false,
    "dry_run": true,
    "live_tts": false,
    "approval": {
      "gate_version": "11h1e_v1",
      "approval_required": true,
      "approval_state": "approved",
      "approved_by": "operator",
      "approved_at": "2026-05-28 12:00:00",
      "approval_reason": "Approved for narration generation after cost review.",
      "approval_expires_at": "2026-05-28 16:00:00",
      "estimated_character_count": 420,
      "estimated_segment_count": 3,
      "estimated_voice_cost": 0.042,
      "live_tts_eligible": true,
      "live_tts_blocked_reasons": []
    }
  },
  "guard": {
    "allowed": true,
    "blocked": false,
    "block_codes": [],
    "approval_state": "approved",
    "live_tts_eligible": true
  },
  "panel": {
    "voice_generation_status": "pending",
    "voice_generation_executed": false,
    "voice_approval_gate": { "...": "operations mirror" }
  }
}
```

### Reject response (success)

Same envelope; `approval_state: "rejected"`, `live_tts_eligible: false`, `guard.block_codes: ["VOICE_APPROVAL_REJECTED"]`.

### Error response — `VoiceApprovalActionErrorResponse`

```json
{
  "ok": false,
  "action": "approve_voice",
  "session_id": "exec_abc123",
  "code": "VOICE_APPROVAL_PRECONDITION_FAILED",
  "reason": "Voice preflight is not ready.",
  "reject_reasons": ["PREFLIGHT_NOT_READY"],
  "current_approval_state": "not_required",
  "detail": {
    "voice_status": "failed",
    "preflight_ready": false
  },
  "api_version": "0.6.0"
}
```

### HTTP status mapping

| Condition | Status |
|-----------|--------|
| Session not found | `404` |
| Precondition failed (no narration, missing key, etc.) | `409` |
| Reason too short (reject/expire) | `400` |
| Success | `200` |

---

## Operation Specifications

### 1. Approve voice generation

**Route:** `POST /sessions/{session_id}/voice/approve`

**Purpose:** Mark `voice_generation` as approved for **future** live TTS. Does not execute TTS.

#### Preconditions (all must pass)

| # | Check | Block code |
|---|-------|------------|
| 1 | Session exists | — (404) |
| 2 | `execution_runtime.category_runtime.voice_generation` exists or can be normalized | `VOICE_SLOT_MISSING` |
| 3 | Narration exists (`segment_count > 0`, not skipped) | `NO_NARRATION` |
| 4 | ElevenLabs preflight ready (`voice_preflight.ready === true`) | `PREFLIGHT_NOT_READY` |
| 5 | Provider is `elevenlabs` | `PROVIDER_NOT_SUPPORTED` |
| 6 | Credentials present (preflight not `CREDENTIALS_MISSING`) | `CREDENTIALS_MISSING` |
| 7 | `live_tts_requested === true` **OR** body `request_live_tts === true` | `LIVE_TTS_NOT_REQUESTED` |
| 8 | `estimated_character_count > 0` | `ESTIMATE_MISSING` |
| 9 | `estimated_segment_count > 0` | `ESTIMATE_MISSING` |
| 10 | Cost estimate present **or** nullable placeholder accepted (`estimated_voice_cost` may be `null` with `confidence: low`) | — |
| 11 | Session not archived | `SESSION_ARCHIVED` |
| 12 | Session cancel not requested | `OPERATIONS_CANCELLED` |
| 13 | Character count ≤ policy max (5000) | `VOICE_CHARACTER_LIMIT_EXCEEDED` |
| 14 | Cost estimate ≤ policy max ($5 placeholder) | `VOICE_COST_LIMIT_EXCEEDED` |
| 15 | Current state allows approve (`required`, `expired`, or re-approve after `rejected`) | `VOICE_APPROVAL_INVALID_STATE` |

**Not allowed:** approve when already `approved` and not expired (return 409 with `ALREADY_APPROVED` unless `force: true` in future — out of scope for 11H-1g v1).

#### State change

```python
approval_required = True
approval_state = "approved"
approved_by = actor  # from request or "operator"
approved_at = now()
approval_reason = reason or "Voice generation approved for live TTS."
approval_expires_at = now + ttl_hours
# Preserve estimates from gate evaluate
live_tts_eligible = can_run_live_voice_tts(...).allowed  # metadata only
live_tts_blocked_reasons = [] if eligible else guard.block_codes
```

If `request_live_tts: true`:

```python
voice_slot["live_tts_requested"] = True
```

Slot fields **unchanged:** `executed`, `live_tts`, `dry_run` (remain false/true/false until 11H-2).

#### Post-write

1. Re-run `evaluate_voice_approval_gate()` to sync mirror fields
2. Update `operations.voice_approval_gate` mirror
3. Append audit event
4. Save session

---

### 2. Reject voice generation

**Route:** `POST /sessions/{session_id}/voice/reject`

**Purpose:** Explicitly block live TTS until operator re-requests and re-approves.

#### Preconditions

| Check | Block code |
|-------|------------|
| Session exists | 404 |
| Voice slot exists | `VOICE_SLOT_MISSING` |
| Narration + preflight context evaluable | `NO_NARRATION` / `PREFLIGHT_NOT_READY` |
| `reason` length ≥ 3 | `REASON_REQUIRED` |
| Not archived | `SESSION_ARCHIVED` |

Allowed from: `required`, `approved`, `expired` (operator override).

#### State change

```python
approval_required = True  # if live_tts_requested
approval_state = "rejected"
approval_reason = reason
approved_by = None
approved_at = None
approval_expires_at = None
live_tts_eligible = False
live_tts_blocked_reasons = ["VOICE_APPROVAL_REJECTED"]
```

Does **not** clear `live_tts_requested` (operator must reset or explicitly clear in future).

---

### 3. Expire voice approval

**Route:** `POST /sessions/{session_id}/voice/expire`

**Purpose:** Operator-initiated revocation before TTL (or confirm natural expiry).

#### Preconditions

| Check | Block code |
|-------|------------|
| Session exists | 404 |
| Voice slot exists | `VOICE_SLOT_MISSING` |
| Current `approval_state === "approved"` OR force expire from `required` | `VOICE_APPROVAL_INVALID_STATE` |
| `reason` length ≥ 3 | `REASON_REQUIRED` |

#### State change

```python
approval_state = "expired"
approval_expires_at = now()  # mark immediate expiry
live_tts_eligible = False
live_tts_blocked_reasons = ["APPROVAL_EXPIRED"]
# Preserve approved_by/approved_at for audit history
```

---

### 4. Reset / clear voice approval

**Route:** `POST /sessions/{session_id}/voice/reset-approval`

**Purpose:** Clear grant fields and recompute gate from current slot + preflight state.

#### Preconditions

| Check | Block code |
|-------|------------|
| Session exists | 404 |
| Voice slot exists | `VOICE_SLOT_MISSING` |
| Not archived | `SESSION_ARCHIVED` |

#### State change

```python
approved_by = None
approved_at = None
approval_reason = None
approval_expires_at = None
# Do NOT blindly clear live_tts_requested — optional body flag:
# clear_live_tts_request: false (default)
```

Then call `evaluate_voice_approval_gate(voice_slot, session, live_tts_requested=...)` which sets:

| Condition | Resulting `approval_state` |
|-----------|---------------------------|
| No narration / missing creds / preflight fail | `not_required` |
| Preflight ready + `live_tts_requested=false` | `not_required` |
| Preflight ready + `live_tts_requested=true` | `required` |

`live_tts_eligible` recalculated via guard.

---

## Approval State Transitions

```mermaid
stateDiagram-v2
    [*] --> not_required: preflight dry-run / no request
    not_required --> required: live_tts_requested + preflight ready
    required --> approved: POST /voice/approve
    required --> rejected: POST /voice/reject
    approved --> expired: TTL OR POST /voice/expire
    approved --> rejected: POST /voice/reject
    rejected --> required: POST /voice/reset-approval + live_tts_requested
    expired --> required: POST /voice/reset-approval + live_tts_requested
    expired --> approved: POST /voice/approve
    approved --> required: POST /voice/reset-approval
    required --> not_required: reset + live_tts_requested=false
```

### Transition table (write engine)

| From | Action | To | Writer |
|------|--------|-----|--------|
| `not_required` | approve (with `request_live_tts`) | `approved`* | Only if preflight ready + request set |
| `required` | approve | `approved` | `VoiceApprovalOperationsEngine.approve()` |
| `required` | reject | `rejected` | `.reject()` |
| `approved` | expire | `expired` | `.expire()` |
| `approved` | reject | `rejected` | `.reject()` |
| `*` | reset | `required` or `not_required` | `.reset_approval()` → gate evaluate |
| `rejected` | reset | `required` | if `live_tts_requested` |
| `expired` | approve | `approved` | re-approve |

\*Approve from `not_required` requires setting `live_tts_requested` in same request.

---

## Audit Trail Design

### Location

Append-only list at:

```
execution_runtime.operations.voice_approval_audit[]
```

**Not** mixed with session `operations_audit_log` (10K operator actions) — voice spend is category-scoped and easier to filter separately. Optional cross-reference via shared `session_id` + timestamp.

### Event schema

```json
{
  "event_id": "voice_appr_evt_20260528_120000_a1b2c3",
  "timestamp": "2026-05-28 12:00:00",
  "session_id": "exec_abc123",
  "action": "approve_voice",
  "actor": "operator",
  "previous_approval_state": "required",
  "next_approval_state": "approved",
  "reason": "Approved after cost review.",
  "allowed": true,
  "blocked_reason": null,
  "metadata": {
    "gate_version": "11h1e_v1",
    "provider": "elevenlabs",
    "estimated_character_count": 420,
    "estimated_segment_count": 3,
    "estimated_voice_cost": 0.042,
    "approval_expires_at": "2026-05-28 16:00:00",
    "live_tts_requested": true,
    "live_tts_eligible_after": true,
    "guard_block_codes": []
  }
}
```

### Event ID generator

```python
def generate_voice_approval_audit_event_id() -> str:
    return f"voice_appr_evt_{stamp}_{uuid.hex[:6]}"
```

Mirror pattern from `generate_operations_audit_event_id()`.

### Failed attempts

Rejected preconditions still append audit with `allowed: false`, `blocked_reason`, no slot mutation (except optional diagnostic timestamp on `operations.voice_approval_gate.last_reject_at`).

### Retention

Cap list at 50 events per session (drop oldest) — same discipline as `attempt_history`.

---

## Safety Rules

### Hard prohibitions (engine + validator enforced)

| Rule | Enforcement |
|------|-------------|
| No live TTS execution | Engine must not import `ElevenLabsVoiceProvider`, `VoiceProviderRouter.generate_*` live path, or `generate_voice` |
| No video slot mutation | Only read `video_generation` for equality checks in tests |
| No credential exposure | Never return `ELEVENLABS_API_KEY`, env values, or preflight secret fields |
| No session approval conflation | Never write `approval_decision`, `approval_state` at session root |
| Approval TTL required on approve | `approval_expires_at` always set on approve |
| Approval revocable | reject + expire + reset |
| Category-scoped only | All writes under `category_runtime.voice_generation.approval` |
| Persist before respond | `save_session(overwrite=True)` then return DTO from reloaded session |

### Cooperative guards (read paths + 11H-2 future)

After every write, re-run:

```python
approval = evaluate_voice_approval_gate(voice_slot, session, live_tts_requested=...)
guard = can_run_live_voice_tts({**voice_slot, "approval": approval}, session)
```

`live_tts_eligible` in response reflects guard output — **still no TTS call**.

### Narration drift (future hardening)

On approve, snapshot `narration_adapter.total_text_length` + optional `text_hash` in audit metadata. If narration changes after approve, next dispatch preflight should invalidate approval → `required` (11H-1g may stub hash field; full invalidation in 11H-2).

---

## Engine Architecture (11H-1g implementation target)

### New module — `VoiceApprovalOperationsEngine`

**Path:** `content_brain/execution/voice_approval_operations_engine.py`

```python
@dataclass
class VoiceApprovalActionResult:
    ok: bool
    session_id: str
    action: str
    audit_event_id: str | None
    message: str
    code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    voice_slot: dict[str, Any] | None = None
    guard: dict[str, Any] | None = None

class VoiceApprovalOperationsEngine:
    def __init__(self, store: ExecutionSessionStore): ...

    def eligibility(self, session_id: str) -> dict[str, Any]: ...
    def approve(self, session_id: str, *, reason: str, actor: str, request_live_tts: bool, ttl_hours: float) -> VoiceApprovalActionResult: ...
    def reject(self, session_id: str, *, reason: str, actor: str) -> VoiceApprovalActionResult: ...
    def expire(self, session_id: str, *, reason: str, actor: str) -> VoiceApprovalActionResult: ...
    def reset_approval(self, session_id: str, *, reason: str, actor: str, clear_live_tts_request: bool) -> VoiceApprovalActionResult: ...
```

### Policy module — `voice_approval_action_policy.py`

Pure eligibility (no I/O):

```python
def evaluate_voice_approval_eligibility(session: dict, voice_slot: dict, action: str) -> ActionEligibility: ...
```

Extend `GET /sessions/{id}/actions/eligibility` **optionally** with nested `voice_actions` block (11H-1h UI slice) — do not overload session retry/cancel eligibility.

### API layer

| File | Role |
|------|------|
| `ui/api/schemas/voice_approval.py` | Pydantic request/response models |
| `ui/api/services/voice_approval_service.py` | Thin wrapper over engine |
| `ui/api/main.py` | Four POST routes |
| `ui/api/dependencies.py` | `get_voice_approval_service()` |

### Reuse from 11H-1e

- `evaluate_voice_approval_gate()`
- `can_run_live_voice_tts()`
- `build_voice_approval_operations_mirror()`
- Block code constants

### Preflight refresh before approve

If voice slot stale (no `voice_preflight` or old `preflight_evaluated_at`), engine calls `apply_voice_preflight_dry_run(session, execution_runtime)` **without** video dispatch — dry-run only, no TTS.

---

## UI Future Plan (Design Only — Not 11H-1f/g)

### Button visibility rules

Show action buttons in `VoiceRuntimeObservabilityPanel` **only when**:

| Condition | Required |
|-----------|----------|
| Narration exists | Yes |
| Preflight ready | Yes |
| Provider = `elevenlabs` | Yes |
| `live_tts` not running / voice not `running` | Yes |
| Session not archived | Yes |

### Button mapping (future 11H-1h)

| Button | Enabled when | API |
|--------|--------------|-----|
| Request live TTS | preflight ready, not requested | Sets `live_tts_requested` via approve prelude or dedicated flag |
| Approve voice | `approval_state=required` | `POST .../voice/approve` |
| Reject voice | `approval_state in (required, approved)` | `POST .../voice/reject` |
| Expire approval | `approval_state=approved` | `POST .../voice/expire` |
| Reset approval | any voice slot with approval block | `POST .../voice/reset-approval` |

**Never show:** Generate Voice / Run TTS until explicit 11H-2 approval phase.

### Copy

```
Voice approval actions affect ElevenLabs credit spend authorization only.
They do not generate audio in this phase.
```

---

## Validation Plan (11H-1g implementation)

**Validator:** `project_brain/validate_11h1g_voice_approval_write_apis.py`

| # | Test | Expected |
|---|------|----------|
| 1 | Approve without narration | 409, `NO_NARRATION`, no slot mutation |
| 2 | Approve with missing credentials | 409, `CREDENTIALS_MISSING` |
| 3 | Approve with ready preflight + `request_live_tts=true` | 200, `approval_state=approved`, `live_tts_eligible=true` (guard metadata) |
| 4 | Reject | `approval_state=rejected`, `VOICE_APPROVAL_REJECTED` in blocked reasons |
| 5 | Expire from approved | `approval_state=expired`, `APPROVAL_EXPIRED` |
| 6 | Reset after approve | `required` or `not_required` per `live_tts_requested` |
| 7 | Audit trail appended | `operations.voice_approval_audit[-1].action` matches |
| 8 | Video slot unchanged | byte-level equality on video slot before/after |
| 9 | No TTS import/call | Static grep engine + service + routes |
| 10 | Legacy session without approval block | 409 or safe normalize, no crash |
| 11 | Nested 11H-1e validator | Still passes |
| 12 | No credentials in API response | Response JSON grep |

---

## Files Likely to Change (11H-1g)

### Create

| File | Purpose |
|------|---------|
| `content_brain/execution/voice_approval_operations_engine.py` | Write engine |
| `content_brain/execution/voice_approval_action_policy.py` | Eligibility rules |
| `ui/api/schemas/voice_approval.py` | API models |
| `ui/api/services/voice_approval_service.py` | Service layer |
| `project_brain/validate_11h1g_voice_approval_write_apis.py` | Validator |
| `project_brain/PHASE_11H1G_VOICE_APPROVAL_WRITE_APIS_REPORT.md` | Implementation report |

### Modify

| File | Change |
|------|--------|
| `ui/api/main.py` | Register four voice approval routes |
| `ui/api/dependencies.py` | DI for voice approval service |
| `content_brain/execution/voice_approval_guard.py` | Optional: export precondition helpers shared by engine |
| `ui/api/services/panel_extractor.py` | Ensure audit list exposed in panel if needed |

### Must NOT modify (11H-1g)

| File | Reason |
|------|--------|
| `content_brain/execution/provider_runtime_engine.py` video path | Video unchanged |
| `VoiceProviderRouter` live path | No TTS until 11H-2 |
| `ui/web/.../VoiceRuntimeObservabilityPanel.tsx` | No UI buttons until 11H-1h |
| Runway/Hailuo providers | Out of scope |
| Legacy `full_video_pipeline`, `NarrationEngine`, `TimelineEngine` | Out of scope |

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Accidental TTS on approve | **Critical** | Engine import boundary + validator grep; approve docstring |
| Session vs voice approval confusion | **High** | Separate audit bucket + UI labels |
| Stale preflight at approve time | **Medium** | Re-run dry-run preflight before approve |
| Double approve race | **Low** | 409 on already-approved-not-expired |
| Audit log growth | **Low** | Cap at 50 events |
| `live_tts_eligible=true` mistaken for execution | **High** | Response message: "metadata only — no TTS executed" |

---

## Implementation Slices

### Phase 11H-1g — Implement Voice Approval Write APIs Backend Only (next)

1. `VoiceApprovalOperationsEngine` + policy
2. API routes + schemas + service
3. Audit append to `operations.voice_approval_audit`
4. Validator matrix (12 tests)
5. **No UI buttons, no live TTS**

### Phase 11H-1h — Voice Approval UI Actions (future)

1. Wire buttons to APIs with eligibility gating
2. Extend `GET /actions/eligibility` or voice-specific eligibility
3. Confirm still no Generate Voice until 11H-2

### Phase 11H-2 — Live TTS Execution (explicit user approval required)

1. `can_run_live_voice_tts()` assert before first ElevenLabs HTTP
2. Requires `approval_state=approved` + not expired
3. Mock-only validator for HTTP

**Do not start Phase 11H-2 without explicit user approval.**

---

## Confirmation Checklist (Design Phase)

| Requirement | Design status |
|-------------|---------------|
| Four write operations defined | Yes — approve, reject, expire, reset |
| Endpoint paths specified | Yes — `/sessions/{id}/voice/{approve\|reject\|expire\|reset-approval}` |
| Request/response shapes | Yes |
| Preconditions documented | Yes — per operation tables |
| State transitions | Yes — diagram + table |
| Audit trail `operations.voice_approval_audit` | Yes |
| Safety rules (no TTS, no video, no secrets) | Yes |
| UI future plan (no buttons this phase) | Yes |
| Validator plan for 11H-1g | Yes — 12 tests |
| Files likely to change | Yes |
| No live TTS in this phase | Yes — design only |

---

## Next Recommended Slice

**Phase 11H-1g — Implement Voice Approval Write APIs Backend Only**

- Backend engine + FastAPI routes
- Audit trail persistence
- Full validator matrix
- Still no UI buttons, no ElevenLabs HTTP, no video changes

**Do not start Phase 11H-2.** Live ElevenLabs TTS requires explicit user approval in a separate phase.

---

## Files Analyzed

| File | Relevance |
|------|-----------|
| `content_brain/execution/voice_approval_guard.py` | Gate evaluate + `can_run_live_voice_tts()` |
| `content_brain/execution/voice_preflight_runtime_slot.py` | Preflight refresh hook |
| `content_brain/execution/operations_control_engine.py` | Operator action + audit pattern |
| `content_brain/execution/operations_action_policy.py` | Eligibility pattern |
| `ui/api/main.py` | Existing route conventions |
| `ui/api/schemas/operations.py` | Response envelope pattern |
| `ui/api/services/panel_extractor.py` | Panel DTO return shape |
| `project_brain/PHASE_11H1D_VOICE_APPROVAL_GATE_DESIGN.md` | Prior write-action sketch |
| `project_brain/PHASE_11H1E_VOICE_APPROVAL_GUARD_REPORT.md` | Current approval schema |
