# Phase 11H-2a — Mock Live Voice TTS Engine Report

**Date:** 2026-05-31  
**Status:** ✅ Complete  
**Mode:** Mock only — no real ElevenLabs API calls

---

## Summary

Implemented the full mock live voice TTS execution path: policy gate, engine, mock provider, API route, and validator. All tests pass. Video runtime unchanged. Real ElevenLabs HTTP is not imported or called.

---

## Files created

| File | Purpose |
|---|---|
| `content_brain/execution/voice_live_tts_action_policy.py` | `/voice/run` eligibility policy |
| `content_brain/execution/mock_voice_tts_provider.py` | Deterministic fake MP3 writer (no network) |
| `content_brain/execution/live_voice_tts_engine.py` | Mock execution orchestrator + manifest |
| `ui/api/voice_run_service.py` | Service wrapper (forces mock mode) |
| `ui/api/schemas/voice_run.py` | Request/response Pydantic models |
| `project_brain/validate_11h2a_mock_live_voice_tts_engine.py` | 20-test validator |

---

## Files modified

| File | Change |
|---|---|
| `ui/api/main.py` | Added `POST /sessions/{session_id}/voice/run` |
| `ui/api/dependencies.py` | Added `get_voice_run_service()` |

---

## Route added

```
POST /sessions/{session_id}/voice/run
```

- **11H-2a:** Always runs in mock mode via `VoiceRunService` → `LiveVoiceTtsEngine`
- No request body field can switch to real ElevenLabs
- Returns `409` on policy/guard block; `200` on successful mock completion

### Response fields (success)

```json
{
  "success": true,
  "session_id": "exec_11h2a_mock_ok",
  "status": "completed",
  "provider_mode": "mock",
  "tts_executed": true,
  "real_provider_called": false,
  "video_mutated": false,
  "manifest_path": ".../voice_generation/voice_manifest.json",
  "artifacts": [ "... narration_001.mp3", "... narration_002.mp3" ]
}
```

---

## Artifact path

```
storage/content_brain/execution/artifacts/{session_id}/voice_generation/
├── narration_001.mp3
├── narration_002.mp3
└── voice_manifest.json
```

Resolved via `ExecutionSessionStore.artifact_dir(session_id, "voice_generation")`.

---

## Manifest example

From validator run session `exec_11h2a_mock_ok`:

```json
{
  "manifest_version": "11h2a_v1",
  "session_id": "exec_11h2a_mock_ok",
  "category": "voice_generation",
  "provider": "mock_elevenlabs",
  "provider_mode": "mock",
  "segment_count": 2,
  "character_count": 87,
  "files": [
    {
      "segment_index": 1,
      "file_name": "narration_001.mp3",
      "validation_status": "valid"
    },
    {
      "segment_index": 2,
      "file_name": "narration_002.mp3",
      "validation_status": "valid"
    }
  ],
  "validation_status": "valid",
  "execution_status": "completed",
  "tts_executed": true,
  "real_provider_called": false
}
```

---

## Validation results

| Validator | Result |
|---|---|
| `python -m project_brain.validate_11h2a_mock_live_voice_tts_engine` | **20/20 PASS** |
| `python -m project_brain.validate_11h1i_voice_approval_ui_controls` | **16/16 PASS** |
| `python -m project_brain.validate_11g_multi_category_runtime_shell` | **20/20 PASS** |

### 11H-2a test coverage

| # | Test | Result |
|---|---|---|
| 1 | Run blocks without approval | PASS |
| 2 | Run blocks expired approval | PASS |
| 3 | Run blocks missing credentials | PASS |
| 4 | Run succeeds with approved mock session | PASS |
| 5 | Mock MP3 files created and non-empty | PASS |
| 6 | voice_manifest.json created | PASS |
| 7 | AudioArtifactValidator passes | PASS |
| 8 | Voice slot lifecycle → completed | PASS |
| 9 | Progress reaches 100% | PASS |
| 10 | executed=true only after mock run | PASS |
| 11 | real_provider_called=false | PASS |
| 12 | video_generation snapshot unchanged | PASS |
| 13 | Cancel-before-run blocked | PASS |
| 14 | Provider failure marks failed | PASS |
| 15 | No ElevenLabs real HTTP import/call | PASS |
| 16 | Approve does not auto-run | PASS |
| 17 | validate_11h1i still passes | PASS |
| 18 | validate_11g still passes | PASS |
| 19 | API response provider_mode=mock | PASS |
| 20 | Manifest required fields present | PASS |

---

## Confirmations

| Statement | Confirmed |
|---|---|
| No real ElevenLabs API call | ✅ Yes — mock provider only |
| `provider_mode=mock` only in 11H-2a | ✅ Yes — hardcoded in service/engine |
| `real_provider_called=false` always | ✅ Yes |
| Video runtime unchanged | ✅ Yes — snapshot preserved; no video dispatch changes |
| Approve does not trigger TTS | ✅ Yes — separate `/voice/run` trigger |
| No `ElevenLabsVoiceProvider` import | ✅ Yes — static grep clean |

---

## Lifecycle (mock run)

```
pending → running → completed
                 ↘ failed (provider/validation error)
                 ↘ cancelled (cooperative cancel)
                 ↘ rejected (pre-run policy block)
```

Voice slot after success:

- `executed=true`, `live_tts=true`, `live_tts_executed=true`, `dry_run=false`
- `provider=mock_elevenlabs`
- `live_tts_progress.progress_percent=100`

---

## Next recommended slice

**Phase 11H-2b — Real ElevenLabs Runtime Adapter Design/Approval**

Before any real execution:

1. Design `elevenlabs_runtime_adapter.py` (injected config, retry, timeout, structured errors)
2. Explicit user approval gate for swapping mock → live provider
3. Environment flag or server-side config (never client-controlled) to enable live mode
4. Preflight coexistence: do not clobber completed voice runs on video dispatch
5. UI progress display (read-only) — optional 11H-2c

**Do not start real ElevenLabs execution until explicit user approval.**

---

*Mock implementation only. No paid TTS. No video/Runway/Hailuo/legacy pipeline changes.*
