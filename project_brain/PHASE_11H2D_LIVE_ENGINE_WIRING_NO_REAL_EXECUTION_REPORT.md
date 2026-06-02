# Phase 11H-2d — Live Engine Wiring (No Real Execution) Report

**Date:** 2026-05-28  
**Status:** PASS  
**Validator:** `project_brain.validate_11h2d_live_engine_wiring_no_real_execution` — **17/17 PASS**

---

## Summary

Phase 11H-2d wires the live ElevenLabs execution path through `LiveVoiceTtsEngine` and `VoiceRunService` while keeping real HTTP disabled by default. Live runs require all gates plus injected mock HTTP in tests. No supervised smoke test was run. No paid audio was generated.

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/execution/live_voice_tts_engine.py` | Provider selection via factory; `provider_mode` + `confirm_live_tts`; live manifest merge; smoke caps enforcement |
| `content_brain/execution/voice_live_tts_action_policy.py` | Live mode gates + smoke caps in `evaluate_voice_live_tts_run()` |
| `content_brain/execution/voice_live_tts_smoke_profile.py` | **New** — strict smoke caps profile |
| `content_brain/execution/voice_provider_factory.py` | Pass `timeout_seconds` / `max_retry_attempts` to adapter |
| `content_brain/execution/elevenlabs_runtime_adapter.py` | `build_live_manifest_extras()` smoke profile + `request_id` support |
| `content_brain/execution/voice_preflight_runtime_slot.py` | Preflight coexistence — preserve completed `executed=true` runs |
| `ui/api/voice_run_service.py` | Pass-through `provider_mode` / `confirm_live_tts`; no forced mock override |
| `project_brain/validate_11h2d_live_engine_wiring_no_real_execution.py` | **New** — 17-test validator |

**Not modified:** video dispatch, Runway/Hailuo, legacy pipeline, `LIVE_RUNTIME_EXECUTION_APPROVED` default (`False`), `MODIR_VOICE_LIVE_TTS_ENABLED` default (`false`).

---

## Safety Gates Implemented

Live execution requires **all** of:

| Gate | Enforced in |
|------|-------------|
| `provider_mode=live_elevenlabs` | `VoiceRunService`, `LiveVoiceTtsEngine` |
| `confirm_live_tts=true` | `evaluate_voice_run_mode_request()` |
| `MODIR_VOICE_LIVE_TTS_ENABLED=true` | `is_voice_live_tts_enabled()` |
| `LIVE_RUNTIME_EXECUTION_APPROVED=True` | `voice_live_tts_action_policy` (default **False**) |
| `approval_state=approved` | `evaluate_voice_live_tts_run()` |
| `can_run_live_voice_tts().allowed=true` | guard in `evaluate_voice_live_tts_run()` |
| Preflight ready | `_preflight_ready()` |
| Narration exists | `_narration_skipped()` |
| Smoke caps pass | `evaluate_voice_live_tts_smoke_caps()` (approval + actual narration) |
| Not archived / not cancelled | session checks |
| Injected `http_client` or explicit `allow_real_http` | `ElevenLabsRuntimeAdapter` (real HTTP still blocked without injection) |

---

## Smoke Caps Implemented

Profile: `voice_live_tts_smoke_profile.py` (`SMOKE_PROFILE_VERSION=11h2d_v1`)

| Cap | Value |
|-----|-------|
| `max_segments` | 1 |
| `max_characters` | 300 |
| `max_estimated_cost` | $0.10 |
| `max_retries` | 1 |
| `timeout_seconds` | 60 |

Applied when `provider_mode=live_elevenlabs`. Fail-closed on approval estimates and actual narration bundle counts.

---

## Manifest Behavior

### Mock (`provider_mode=mock`)

```json
{
  "provider": "mock_elevenlabs",
  "provider_mode": "mock",
  "real_provider_called": false
}
```

Unchanged from 11H-2a.

### Live (`provider_mode=live_elevenlabs`)

Merged via `build_live_manifest_extras()`:

```json
{
  "provider": "elevenlabs",
  "provider_mode": "live_elevenlabs",
  "real_provider_called": true,
  "voice_id": "...",
  "model_id": "...",
  "request_id": "...",
  "retry_count": 0,
  "safety_caps": { "...smoke profile..." }
}
```

Per-segment `request_id` and `retry_count` included in manifest `files[]`.

---

## Preflight Coexistence Fix

`apply_voice_preflight_dry_run()` detects completed voice runs (`status=completed`, `executed=true`) and **does not**:

- reset `executed=false`
- reset `dry_run=true`
- overwrite `artifacts`, `voice_manifest_path`, or `status`

Still refreshes: `narration_adapter`, `voice_preflight`, `approval` gate, `preflight_evaluated_at`. Operations mirror sets `completed_run_preserved=true`.

---

## Validation Results

| Validator | Result |
|-----------|--------|
| `validate_11h2d_live_engine_wiring_no_real_execution` | **17/17 PASS** |
| `validate_11h2c_elevenlabs_runtime_adapter` | **26/26 PASS** |
| `validate_11h2a_mock_live_voice_tts_engine` | **20/20 PASS** |
| `validate_11g_multi_category_runtime_shell` | **20/20 PASS** |

---

## Confirmations

| Item | Status |
|------|--------|
| No real ElevenLabs call in this phase | ✅ Confirmed — validator uses injected `SequentialMockHttp` only |
| Live disabled by default | ✅ `LIVE_RUNTIME_EXECUTION_APPROVED=False`, `MODIR_VOICE_LIVE_TTS_ENABLED` unset/false |
| Video runtime unchanged | ✅ Video slot fields preserved; validator confirms |
| Supervised smoke test run | ❌ **Not run** (per phase scope) |

---

## Remaining Steps Before First Real Smoke Test

1. **Operator approval** — set `LIVE_RUNTIME_EXECUTION_APPROVED=True` in code or via approved config mechanism (separate explicit sign-off).
2. **Environment** — set `MODIR_VOICE_LIVE_TTS_ENABLED=true` and valid `ELEVENLABS_API_KEY`.
3. **API request** — `POST /sessions/{id}/voice/run` with `provider_mode=live_elevenlabs`, `confirm_live_tts=true`.
4. **Session prep** — approved voice slot, preflight ready, single segment ≤300 chars, cost estimate ≤$0.10.
5. **Execute** — follow `PHASE_11H2D0_REAL_TTS_SMOKE_TEST_PLAN.md` under supervision.
6. **Post-smoke** — verify manifest, artifacts, audit log, rollback path.

First paid TTS call requires **separate explicit approval** after this phase passes.
