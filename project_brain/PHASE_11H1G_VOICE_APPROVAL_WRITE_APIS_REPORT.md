# Phase 11H-1g — Voice Approval Write APIs Backend Report

**Status:** Complete  
**Date:** 2026-05-28  
**Prerequisites:** 11G, 11H-1a–1f  
**Scope:** Backend-only voice approval write APIs — no live TTS, no UI buttons

---

## Summary

Implemented four POST endpoints and supporting engine/policy/service layers that mutate **only** `voice_generation.approval` metadata and `operations.voice_approval_audit`. All writes recalculate `can_run_live_voice_tts()` guard metadata without executing ElevenLabs TTS.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/voice_approval_action_policy.py` | Precondition checks for approve/reject/expire/reset |
| `content_brain/execution/voice_approval_operations_engine.py` | Write mutations, audit append, session persist |
| `ui/api/voice_approval_service.py` | API service wrapper |
| `ui/api/schemas/voice_approval.py` | Pydantic request/response models |
| `project_brain/validate_11h1g_voice_approval_write_apis.py` | Phase validator (16 tests) |
| `project_brain/PHASE_11H1G_VOICE_APPROVAL_WRITE_APIS_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `ui/api/main.py` | Four voice approval POST routes |
| `ui/api/dependencies.py` | `get_voice_approval_service()` DI |

**Not modified:** Execution Center UI, `ProviderRuntimeEngine` video path, Runway/Hailuo, legacy pipeline.

---

## Endpoint List

| Method | Path | Action |
|--------|------|--------|
| `POST` | `/sessions/{session_id}/voice/approve` | Grant voice TTS approval (metadata only) |
| `POST` | `/sessions/{session_id}/voice/reject` | Reject voice TTS approval |
| `POST` | `/sessions/{session_id}/voice/expire` | Force-expire approval |
| `POST` | `/sessions/{session_id}/voice/reset-approval` | Clear approval grant; re-evaluate gate |

All responses include `tts_executed: false`.

---

## Validation Results

| Validator | Result |
|-----------|--------|
| `validate_11h1g_voice_approval_write_apis` | **16/16 PASS** |
| `validate_11h1e_voice_approval_guard` | **18/18 PASS** |
| `validate_11g_multi_category_runtime_shell` | **20/20 PASS** |

### Test matrix (11H-1g)

| # | Test | Result |
|---|------|--------|
| 1 | Approve without narration blocks | PASS |
| 2 | Approve missing credentials blocks | PASS |
| 3 | Approve without `request_live_tts` blocks | PASS |
| 4 | Approve with ready preflight succeeds | PASS |
| 5 | Reject sets rejected state | PASS |
| 6 | Expire sets expired state | PASS |
| 7 | Reset returns correct state | PASS |
| 8 | Audit trail appended | PASS |
| 9 | No video_generation mutation | PASS |
| 10 | No ElevenLabsVoiceProvider import | PASS |
| 11 | Legacy session safe | PASS |
| 12 | API response `tts_executed=false` | PASS |
| 13 | No UI approve buttons | PASS |
| 14 | Legacy pipeline untouched | PASS |
| 15 | 11H-1e regression | PASS |
| 16 | 11G regression | PASS |

---

## Audit Event Example

```json
{
  "event_id": "voice_appr_evt_20260528_120000_a1b2c3",
  "event_type": "approve_voice",
  "session_id": "exec_11h1g_approve_ok_v2",
  "category": "voice_generation",
  "actor": "validator",
  "reason": "Test approval",
  "timestamp": "2026-05-28T12:00:00Z",
  "previous_state": "not_required",
  "new_state": "approved",
  "blocked_reasons": [],
  "live_tts_eligible": true,
  "tts_executed": false,
  "allowed": true,
  "metadata": {
    "engine_version": "11h1g_v1",
    "gate_version": "11h1e_v1",
    "provider": "elevenlabs",
    "estimated_character_count": 45,
    "estimated_segment_count": 1,
    "live_tts_requested": true
  }
}
```

Stored at: `execution_runtime.operations.voice_approval_audit[]` (cap 50 events).

---

## Confirmations

| Requirement | Status |
|-------------|--------|
| No live TTS / no `ElevenLabsVoiceProvider` | Confirmed |
| No UI approve/reject buttons | Confirmed |
| Video runtime unchanged (critical fields) | Confirmed |
| Legacy pipeline untouched | Confirmed |
| Category-scoped approval only | Confirmed |
| Audit trail on every write attempt | Confirmed |

---

## Next Recommended Slice

**Phase 11H-1h — Voice Approval UI Controls Design**

- Button visibility rules wired to eligibility
- Approve/reject/expire/reset UI actions calling these endpoints
- Still no Generate Voice / live TTS until explicit 11H-2 approval

**Do not start Phase 11H-2.** Live ElevenLabs TTS requires explicit user approval in a separate phase.
