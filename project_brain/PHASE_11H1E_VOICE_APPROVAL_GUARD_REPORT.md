# Phase 11H-1e — Voice Approval Gate Read-Only Guard Report

**Status:** Complete  
**Date:** 2026-05-28  
**Prerequisites:** 11G, 11H-1a, 11H-1b, 11H-1c, 11H-1d design  
**Scope:** Read-only approval metadata + guard helper — no live TTS, no write actions

---

## Summary

Implemented category-scoped voice approval gate metadata on `voice_generation`. The slot now exposes whether live TTS would be blocked or eligible in a future phase, without executing ElevenLabs or adding approve/reject UI controls.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/voice_approval_guard.py` | Approval evaluation, `can_run_live_voice_tts()` guard helper |
| `project_brain/validate_11h1e_voice_approval_guard.py` | Phase validator (18 tests) |
| `project_brain/PHASE_11H1E_VOICE_APPROVAL_GUARD_REPORT.md` | This report |

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/execution/voice_preflight_runtime_slot.py` | Calls `evaluate_voice_approval_gate()` after preflight; writes `operations.voice_approval_gate` |
| `content_brain/execution/category_runtime_compat.py` | Preserves `approval` and `live_tts_requested` in slot normalization |
| `ui/api/services/panel_extractor.py` | Exposes `voice_approval_gate` in provider runtime panel |
| `ui/web/src/utils/categoryRuntimeShell.ts` | `VoiceApprovalBlock` type + approval fields in observability resolver |
| `ui/web/src/components/VoiceRuntimeObservabilityPanel.tsx` | Read-only approval gate section |
| `ui/web/src/App.css` | Styles for `.voice-approval-gate-section` |

---

## Approval Schema Added

Nested under `execution_runtime.category_runtime.voice_generation.approval`:

```json
{
  "gate_version": "11h1e_v1",
  "approval_required": false,
  "approval_state": "not_required",
  "approved_by": null,
  "approved_at": null,
  "approval_reason": null,
  "estimated_voice_cost": 0.0042,
  "estimated_voice_cost_currency": "USD",
  "estimated_voice_cost_confidence": "low",
  "estimated_character_count": 42,
  "estimated_segment_count": 1,
  "approval_expires_at": null,
  "live_tts_eligible": false,
  "live_tts_blocked_reasons": ["LIVE_TTS_NOT_REQUESTED"]
}
```

Operations mirror: `execution_runtime.operations.voice_approval_gate`

---

## Guard Behavior Matrix

| Scenario | `approval_required` | `approval_state` | `live_tts_eligible` | Block code |
|----------|---------------------|------------------|---------------------|------------|
| Dry-run only (preflight ready, no request) | `false` | `not_required` | `false` | `LIVE_TTS_NOT_REQUESTED` |
| No narration | `false` | `not_required` | `false` | `NO_NARRATION` |
| Missing credentials | `false` | `not_required` | `false` | `CREDENTIALS_MISSING` |
| Preflight ready + `live_tts_requested=false` | `false` | `not_required` | `false` | `LIVE_TTS_NOT_REQUESTED` |
| Preflight ready + `live_tts_requested=true` | `true` | `required` | `false` | `VOICE_APPROVAL_REQUIRED` |
| Existing approved + expired | `true` | `expired` | `false` | `APPROVAL_EXPIRED` |
| Existing approved + valid + within limits | `true` | `approved` | `true` | (none — metadata only) |

`can_run_live_voice_tts(slot, session)` returns structured `VoiceLiveTtsGuardResult` with full checklist (preflight, approval, expiration, character/cost limits, budget, cancel). Not invoked by video dispatch.

---

## Validation Results

| Validator | Result |
|-----------|--------|
| `validate_11h1e_voice_approval_guard` | **18/18 PASS** |
| `validate_11h1b_voice_preflight_runtime_slot` | **10/10 PASS** |
| `validate_11h1c_voice_ui_observability` | **17/17 PASS** |
| `validate_11g_multi_category_runtime_shell` | **20/20 PASS** |
| `npm run build` | **PASS** |

---

## Confirmations

| Requirement | Status |
|-------------|--------|
| No live TTS / no `ElevenLabsVoiceProvider` import | Confirmed — static grep in validator |
| No approve/reject buttons | Confirmed — UI read-only only |
| Video runtime unchanged | Confirmed — video slot preserved on preflight |
| Legacy pipeline untouched | Confirmed — no TimelineEngine / full_video_pipeline imports |
| Legacy sessions without approval block | Safe — UI shows `—` |

---

## Next Recommended Slice

**Phase 11H-1f — Voice Approval Write APIs Design**

- Design approve/reject/expire/request-live-TTS endpoints
- Extend `operations_action_policy` eligibility
- Audit trail in `operations_control.voice_approval_history`
- Still no live TTS until explicit 11H-2 approval

**Do not start Phase 11H-2.** Live ElevenLabs TTS requires explicit user approval in a separate phase.
