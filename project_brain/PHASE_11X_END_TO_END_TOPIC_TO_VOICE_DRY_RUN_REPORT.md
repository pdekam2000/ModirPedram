# Phase 11X — End-to-End Topic → Voice Slot Dry Run Report

**Date:** 2026-05-31 14:00:29
**Status:** PASS

## Test Topic

`cat in the streets of Los Angeles`

## Session

- **Session ID:** `exec_20260531_140029_80ea59`
- **Brief ID:** `brief_20260531_140029_a97eb4fc`
- **Niche:** `general`

## User Topic Authority

- **user_topic_authoritative:** `True`
- **user_topic (run_context):** `cat in the streets of Los Angeles`
- **pipeline topic:** `cat in the streets of Los Angeles`
- **trend signal topic:** `cat in the streets of Los Angeles`
- **trend signal source:** `user_topic`

User topic was preserved as authoritative (no trend override).

## Content Brief

- **Decision:** PROCEED
- **Production ready:** True
- **Clip count:** 5

## Story Beats / Narration

- **Beat count:** 6
- **Beats with narration:** 6
- **Narration segment count (adapter):** 6
- **Narration source:** `story_blueprint.beats`
- **Schema director shots:** 5

### Narration segments (adapter)

```json
[
  {
    "segment_index": 1,
    "beat_id": "HOOK_BEAT",
    "text_preview": "Watch one concrete general short-form content detail closely — the last second of cat in the streets...",
    "character_count": 125
  },
  {
    "segment_index": 2,
    "beat_id": "CONTEXT_BEAT",
    "text_preview": "Set up the General Short-Form Content situation behind the hook: cat in the streets of Los Angeles",
    "character_count": 98
  },
  {
    "segment_index": 3,
    "beat_id": "ESCALATION_BEAT",
    "text_preview": "Raise the stakes in General Short-Form Content with one new detail that changes how the viewer reads...",
    "character_count": 134
  },
  {
    "segment_index": 4,
    "beat_id": "PATTERN_BREAK",
    "text_preview": "Shift perspective: the obvious read on cat in the streets of Los Angeles is incomplete",
    "character_count": 86
  },
  {
    "segment_index": 5,
    "beat_id": "PAYOFF_BEAT",
    "text_preview": "Deliver the payoff for General Short-Form Content without fake certainty: show what changes after ca...",
    "character_count": 131
  },
  {
    "segment_index": 6,
    "beat_id": "LOOP_SEED",
    "text_preview": "Leave one unanswered detail about cat in the streets of Los Angeles so General Short-Form Content vi...",
    "character_count": 134
  }
]
```

### Beat summary

```json
[
  {
    "beat_id": "HOOK_BEAT",
    "narration_preview": "Watch one concrete general short-form content detail closely — the last second of cat in the streets of Los Angeles does...",
    "narration_length": 125,
    "has_narration": true
  },
  {
    "beat_id": "CONTEXT_BEAT",
    "narration_preview": "Set up the General Short-Form Content situation behind the hook: cat in the streets of Los Angeles",
    "narration_length": 98,
    "has_narration": true
  },
  {
    "beat_id": "ESCALATION_BEAT",
    "narration_preview": "Raise the stakes in General Short-Form Content with one new detail that changes how the viewer reads cat in the streets ...",
    "narration_length": 134,
    "has_narration": true
  },
  {
    "beat_id": "PATTERN_BREAK",
    "narration_preview": "Shift perspective: the obvious read on cat in the streets of Los Angeles is incomplete",
    "narration_length": 86,
    "has_narration": true
  },
  {
    "beat_id": "PAYOFF_BEAT",
    "narration_preview": "Deliver the payoff for General Short-Form Content without fake certainty: show what changes after cat in the streets of ...",
    "narration_length": 131,
    "has_narration": true
  },
  {
    "beat_id": "LOOP_SEED",
    "narration_preview": "Leave one unanswered detail about cat in the streets of Los Angeles so General Short-Form Content viewers comment or wai...",
    "narration_length": 134,
    "has_narration": true
  }
]
```

- **Total narration characters:** 708

## Governance & Dispatch

- **Governance state:** `COMPLETED`
- **Readiness:** `READY_WITH_WARNINGS`
- **Video dispatch success:** `True`
- **Dispatch reject code:** `None`
- **Runtime state:** `COMPLETED`
- **skip_provider_execution:** `True` (no Runway/Hailuo paid execution)

## Video Runtime

```json
{
  "status": "pending",
  "state": "COMPLETED",
  "provider": "hailuo_browser",
  "executed": false
}
```

- **Video artifacts (dry-run):** 5

## Voice Generation Slot

```json
{
  "status": "pending",
  "state": "pending",
  "provider": "elevenlabs",
  "executed": false,
  "dry_run": true,
  "live_tts": false,
  "segment_count": 6,
  "preflight_ready": true,
  "preflight_code": null
}
```

- **ElevenLabs API key present:** `True`
- **Preflight ready (if key exists):** `True`

## Voice Approval Gate

```json
{
  "approval_state": "not_required",
  "approval_required": false,
  "live_tts_eligible": false,
  "live_tts_blocked_reasons": [
    "LIVE_TTS_NOT_REQUESTED"
  ],
  "estimated_segment_count": 6,
  "estimated_character_count": 708
}
```

## Live TTS Blocked (Expected)

```json
{
  "mode_request": {
    "allowed": false,
    "action": "run_voice_tts",
    "reject_reasons": [
      "LIVE_TTS_DISABLED"
    ],
    "message": "Live ElevenLabs runtime execution is not approved (11H-2c).",
    "code": "LIVE_TTS_DISABLED"
  },
  "run_policy": {
    "allowed": false,
    "action": "run_voice_tts",
    "reject_reasons": [
      "VOICE_APPROVAL_REQUIRED"
    ],
    "message": "Voice approval is required before live TTS run.",
    "code": "APPROVAL_REQUIRED"
  },
  "voice_service": {
    "success": false,
    "code": "LIVE_TTS_DISABLED"
  }
}
```

- **Guard allowed:** `False`

## Safety Confirmations

| Check | Result |
|-------|--------|
| No real ElevenLabs TTS executed | `True` |
| No paid video provider execution | `True` |
| Live mode blocked at service layer | `True` |
| Video slot critical fields preserved | `True` |

## Preflight Operations Mirror

```json
{
  "slot_version": "11h1b_v1",
  "evaluated_at": "2026-05-31 14:00:29",
  "status": "pending",
  "executed": false,
  "dry_run": true,
  "live_tts": false,
  "provider": "elevenlabs",
  "segment_count": 6,
  "narration_skipped": false,
  "preflight_ready": true,
  "reject_code": null,
  "completed_run_preserved": false
}
```
