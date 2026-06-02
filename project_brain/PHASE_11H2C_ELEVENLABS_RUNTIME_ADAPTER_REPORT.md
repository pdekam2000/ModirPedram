# Phase 11H-2c — ElevenLabs Runtime Adapter Report

**Date:** 2026-05-31  
**Status:** ✅ Complete  
**Mode:** Adapter + mocked HTTP tests only — **no real ElevenLabs execution**

---

## Summary

Implemented `ElevenLabsRuntimeAdapter` with injectable HTTP client, live mode policy gates, safety caps, provider factory, and a 26-test validator suite. All tests use **mocked HTTP only**. `/voice/run` remains **mock-only** at runtime (`LIVE_RUNTIME_EXECUTION_APPROVED = False`).

---

## Files created

| File | Purpose |
|---|---|
| `content_brain/execution/elevenlabs_runtime_adapter.py` | Single Content Brain ElevenLabs HTTP site (injection required) |
| `content_brain/execution/voice_live_tts_safety_caps.py` | Hard caps constants |
| `content_brain/execution/voice_provider_factory.py` | DI factory for mock/live adapters |
| `project_brain/validate_11h2c_elevenlabs_runtime_adapter.py` | 26-test validator (mocked HTTP) |

---

## Files modified

| File | Change |
|---|---|
| `content_brain/execution/voice_live_tts_action_policy.py` | Live mode gating, caps, `LIVE_RUNTIME_EXECUTION_APPROVED=False` |
| `content_brain/execution/failure_taxonomy.py` | ElevenLabs + live gate codes |
| `content_brain/execution/live_voice_tts_engine.py` | Docstring update (execution still mock-only) |
| `ui/api/schemas/voice_run.py` | `provider_mode`, `confirm_live_tts` fields |
| `ui/api/voice_run_service.py` | Mode policy gate; execution remains mock |
| `ui/api/main.py` | Pass mode fields to service |

---

## Adapter architecture

```
ElevenLabsRuntimeAdapter
  ├── config: ElevenLabsConfigSnapshot (from ElevenLabsConfigResolver)
  ├── api_key: injected (never in to_dict / manifest / API)
  ├── http_client: required in 11H-2c (no allow_real_http without 11H-2d)
  ├── cancel_check: cooperative cancel hook
  ├── retry: 429/5xx with exponential backoff (max 3)
  ├── timeout: 120s default
  └── synthesize_segment() → ElevenLabsSegmentResult
```

**Real HTTP guard:**

```python
if http_client is None and not allow_real_http:
    raise RuntimeError("Real ElevenLabs HTTP is disabled — inject http_client for tests")
```

No import of legacy `providers.elevenlabs_voice_provider`.

---

## Live mode gating (prepared, not enabled)

| Gate | Status |
|---|---|
| `LIVE_RUNTIME_EXECUTION_APPROVED = False` | ✅ Hardcoded — blocks live `/voice/run` |
| `MODIR_VOICE_LIVE_TTS_ENABLED` env | Read but insufficient alone |
| `provider_mode=live_elevenlabs` + `confirm_live_tts=true` | Required in future; returns `LIVE_TTS_DISABLED` today |
| Approval + `can_run_live_voice_tts()` | Policy extended for future live path |
| Live caps (segments/chars/cost) | `evaluate_voice_live_tts_live_caps()` |

---

## Safety caps

| Cap | Value |
|---|---|
| `max_segments_per_run` | 20 |
| `max_characters_per_run` | 5000 |
| `max_retry_attempts` | 3 |
| `timeout_seconds` | 120 |
| `max_estimated_cost_usd` | 5.00 |

---

## Validation results

| Validator | Result |
|---|---|
| `python -m project_brain.validate_11h2c_elevenlabs_runtime_adapter` | **26/26 PASS** |
| `validate_11h2a` (regression) | **20/20 PASS** |
| `validate_11h1i` (regression) | **16/16 PASS** |
| `validate_11g` (regression) | **20/20 PASS** |

All adapter HTTP tests use `SequentialMockHttp` / injected clients — **zero real network calls**.

---

## Confirmations

| Statement | Confirmed |
|---|---|
| No real ElevenLabs HTTP execution | ✅ `allow_real_http=False` default; no client = RuntimeError |
| `/voice/run` mock-only | ✅ Service always runs mock engine |
| `provider_mode=live_elevenlabs` blocked | ✅ Returns `LIVE_TTS_DISABLED` |
| `real_provider_called=false` on `/voice/run` | ✅ Always |
| `real_provider_called=true` on adapter success (unit tests) | ✅ Adapter metadata only |
| API key not in normalized results | ✅ Static test PASS |
| Video runtime unchanged | ✅ No video dispatch changes |
| Legacy provider not imported | ✅ Grep clean |

---

## Manifest integration prep

`build_live_manifest_extras()` returns live manifest fields:

- `provider=elevenlabs`, `provider_mode=live_elevenlabs`
- `voice_id`, `model_id`, `output_format`
- `real_provider_called=true`, `retry_count`, `safety_caps`

Not wired to `/voice/run` until 11H-2d.

---

## Phase gate

| Phase | Status |
|---|---|
| 11H-2c Adapter + mocked HTTP tests | ✅ **Complete** |
| 11H-2d Real live ElevenLabs execution | 🔒 **Not approved — requires explicit architect approval** |

---

## Next step (requires approval)

**Pre-live architecture review** then **Phase 11H-2d** — enable live execution under:

1. `LIVE_RUNTIME_EXECUTION_APPROVED = True` (code gate)
2. `MODIR_VOICE_LIVE_TTS_ENABLED=true` (env gate)
3. Wire `LiveVoiceTtsEngine` to `build_elevenlabs_runtime_adapter()` for live mode
4. Manual supervised smoke test with real API key (outside CI)

**Do not enable live ElevenLabs execution without explicit 11H-2d approval.**

---

*Implemented per architect approval boundaries. No paid API usage. No live audio generation.*
