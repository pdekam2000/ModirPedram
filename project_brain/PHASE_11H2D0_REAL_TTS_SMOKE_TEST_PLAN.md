# Phase 11H-2d-0 — Real ElevenLabs TTS Smoke Test Plan

**Status:** Plan only — no implementation, no live TTS, no ElevenLabs API calls  
**Date:** 2026-05-31  
**Prerequisites:** Phase 11H-2c complete (adapter + mocked HTTP tests PASS)  
**Goal:** Controlled operator checklist for the first supervised real ElevenLabs TTS smoke test

---

## Executive summary

This document defines **how** the first real ElevenLabs TTS smoke test should be executed **after** a separate explicit 11H-2d approval. It does **not** enable live execution, change code flags, or authorize paid API usage today.

Current production safety state (unchanged by this plan):

| Control | Current value |
|---|---|
| `/voice/run` execution path | Mock only |
| `provider_mode=live_elevenlabs` | Returns `LIVE_TTS_DISABLED` |
| `LIVE_RUNTIME_EXECUTION_APPROVED` | `False` (hardcoded in policy) |
| `MODIR_VOICE_LIVE_TTS_ENABLED` | Default `false` |

---

## Approval boundary

> **This plan does NOT approve live ElevenLabs execution.**
>
> Phase 11H-2d-0 is documentation only. To proceed to **Phase 11H-2d** (supervised real smoke test), a **separate explicit architect/operator approval** is required.
>
> 11H-2d implementation must:
> 1. Wire `LiveVoiceTtsEngine` to `ElevenLabsRuntimeAdapter` for live mode
> 2. Temporarily enable gates **only** in a dedicated test branch or controlled config slice
> 3. Revert all enablement flags immediately after the smoke test
>
> **Do not implement 11H-2d or enable live TTS based on this document alone.**

---

## 1. Smoke test limits (first live run only)

These limits are **stricter than production caps** (`voice_live_tts_safety_caps.py`) and apply only to the first supervised smoke test.

| Limit | Smoke test value | Production cap (reference) |
|---|---|---|
| Sessions | **1** test session only | N/A |
| Narration segments | **1** segment only | 20 |
| Character count | **≤ 300** characters | 5000 |
| Estimated cost ceiling | **≤ $0.10 USD** | $5.00 |
| Retry attempts (adapter) | **≤ 1** retry (2 total attempts max) | 3 |
| Timeout per HTTP call | **60 seconds** | 120 |
| Operator confirmation | **Required** — manual sign-off before POST | Required via `confirm_live_tts=true` |
| Auto-re-run | **Forbidden** — no `force_retry` on first live test | Allowed on failure later |
| Concurrent runs | **Forbidden** — no parallel voice runs | One active run per session |

### Recommended test narration

Use a single short beat with known character count (example, ~120 chars):

```
This is a supervised ModirAgentOS live voice smoke test. One segment only. No video changes expected.
```

Verify character count in approval metadata before run.

---

## 2. Preconditions (operator checklist)

Complete **all** items before any live POST. If any item fails, **abort** — do not enable live mode.

### Environment

- [ ] **P1** — `ELEVENLABS_API_KEY` is set in `.env` (or configured env var from registry)
- [ ] **P2** — Key is valid (preflight / `has_api_key=true` on voice slot after dry-run refresh)
- [ ] **P3** — `MODIR_VOICE_LIVE_TTS_ENABLED=true` set **only** for smoke test window (shell/session env — not committed)
- [ ] **P4** — `LIVE_RUNTIME_EXECUTION_APPROVED=True` enabled **only** in approved 11H-2d test branch/slice (revert after test)
- [ ] **P5** — API server restarted after env/flag changes (if required by deployment)
- [ ] **P6** — Operator confirms this is the **only** live test in progress (no other sessions queued)

### Session state

- [ ] **P7** — Dedicated test session created (recommend ID prefix: `exec_11h2d_smoke_`)
- [ ] **P8** — Session is **not** archived
- [ ] **P9** — Session `operations_control.cancel_requested` is **false**
- [ ] **P10** — `brief_snapshot` contains **exactly one** narration segment (≤ 300 chars)
- [ ] **P11** — Voice preflight dry-run refreshed: `voice_preflight.ready == true`
- [ ] **P12** — `voice_generation.approval.approval_state == approved` (not expired/rejected)
- [ ] **P13** — `live_tts_requested == true`
- [ ] **P14** — `can_run_live_voice_tts().allowed == true` (verify via API panel excerpt or session JSON)
- [ ] **P15** — Estimated characters ≤ 300; estimated cost ≤ $0.10
- [ ] **P16** — Video slot snapshot recorded **before** run (`state`, `provider`, `started_at`, `completed_at`)

### Artifact / backup

- [ ] **P17** — Project backup created (e.g. `project_brain/PROJECT_BACKUP_*` or git tag on test branch)
- [ ] **P18** — Artifact directory empty or test-specific:
  `storage/content_brain/execution/artifacts/{session_id}/voice_generation/`
- [ ] **P19** — No prior `voice_manifest.json` in test artifact dir (or use fresh session ID)

### Operator sign-off

- [ ] **P20** — Operator reads smoke limits aloud / confirms in run log
- [ ] **P21** — Explicit written approval recorded: *"Approved for 11H-2d supervised smoke test — [date] — [operator]"*

---

## 3. Exact test flow

### Step 1 — Create or select test session

1. Create execution session with single-beat `brief_snapshot`:

```json
{
  "run_context": {
    "story_intelligence": {
      "story_architecture": {
        "beat_plans": [
          {
            "beat_id": "SMOKE_01",
            "narration": "This is a supervised ModirAgentOS live voice smoke test. One segment only. No video changes expected."
          }
        ]
      }
    }
  }
}
```

2. Note `session_id` (e.g. `exec_11h2d_smoke_001`).
3. Record video slot snapshot to run log.

### Step 2 — Refresh preflight (if not auto-run on open)

Ensure voice slot shows preflight ready and credentials present. No live TTS yet.

### Step 3 — Approve voice (metadata only)

```http
POST /sessions/{session_id}/voice/approve
Content-Type: application/json

{
  "request_live_tts": true,
  "reason": "11H-2d supervised smoke test approval",
  "approved_by": "operator_smoke_test",
  "ttl_minutes": 30
}
```

**Verify approve response:**

| Field | Expected |
|---|---|
| `success` | `true` |
| `tts_executed` | `false` |
| `voice_slot.approval.approval_state` | `approved` |
| No artifacts created | Confirm artifact dir empty |

### Step 4 — Operator manual confirm (mandatory pause)

Before live run, operator confirms:

- Session ID correct
- Narration text correct and ≤ 300 chars
- Cost estimate acceptable
- Env flags enabled intentionally
- Rollback plan understood

**Do not proceed without this pause.**

### Step 5 — Live voice run (11H-2d implementation only)

```http
POST /sessions/{session_id}/voice/run
Content-Type: application/json

{
  "triggered_by": "operator_smoke_test",
  "reason": "11H-2d supervised first live ElevenLabs smoke test",
  "force_retry": false,
  "provider_mode": "live_elevenlabs",
  "confirm_live_tts": true
}
```

**Today (pre-11H-2d):** this request returns `409` with `LIVE_TTS_DISABLED`. That is expected and correct.

### Step 6 — Verify API response (success criteria)

| Field | Expected (live success) |
|---|---|
| HTTP status | `200` |
| `success` | `true` |
| `status` | `completed` |
| `provider_mode` | `live_elevenlabs` |
| `tts_executed` | `true` |
| `real_provider_called` | `true` |
| `video_mutated` | `false` |
| `manifest_path` | Non-null path to `voice_manifest.json` |
| `artifacts` | Length `1` |
| `voice_slot.status` | `completed` |
| `voice_slot.executed` | `true` |
| `voice_slot.live_tts_executed` | `true` |
| `voice_slot.live_tts_progress.progress_percent` | `100` |

Example success response shape:

```json
{
  "success": true,
  "session_id": "exec_11h2d_smoke_001",
  "status": "completed",
  "provider_mode": "live_elevenlabs",
  "tts_executed": true,
  "real_provider_called": true,
  "video_mutated": false,
  "manifest_path": "storage/content_brain/execution/artifacts/exec_11h2d_smoke_001/voice_generation/voice_manifest.json",
  "artifacts": [
    {
      "file_name": "narration_001.mp3",
      "segment_index": 1,
      "size_bytes": 12345,
      "validation_status": "valid"
    }
  ]
}
```

### Step 7 — Verify artifacts on disk

Path:

```
storage/content_brain/execution/artifacts/{session_id}/voice_generation/
├── narration_001.mp3
└── voice_manifest.json
```

| Check | Expected |
|---|---|
| `narration_001.mp3` exists | Yes |
| File size | `> 0` bytes (typically >> 1 KB for real MP3) |
| `voice_manifest.json` exists | Yes |
| Manifest `provider` | `elevenlabs` |
| Manifest `provider_mode` | `live_elevenlabs` |
| Manifest `real_provider_called` | `true` |
| Manifest `tts_executed` | `true` |
| Manifest `validation_status` | `valid` |
| Manifest `segment_count` | `1` |
| Manifest `character_count` | ≤ 300 |
| No `narration_002.mp3` | Confirms single-segment limit |

Optional: play `narration_001.mp3` locally to confirm audible speech.

### Step 8 — Verify session slot state

| `voice_generation` field | Expected |
|---|---|
| `status` / `state` | `completed` |
| `executed` | `true` |
| `live_tts` | `true` |
| `live_tts_executed` | `true` |
| `dry_run` | `false` |
| `provider` | `elevenlabs` |
| `error` | `null` |

### Step 9 — Verify video slot unchanged

Compare before/after snapshot:

| Field | Must match pre-run snapshot |
|---|---|
| `video_generation.state` | Yes |
| `video_generation.provider` | Yes |
| `video_generation.started_at` | Yes |
| `video_generation.completed_at` | Yes |

### Step 10 — Audit trail

Confirm append to:

- `operations.voice_tts_audit[]` — event with `provider_mode=live_elevenlabs`, `real_provider_called=true`, `tts_executed=true`
- Optional: global operations audit if wired

---

## 4. Rollback / shutdown checklist

Execute **immediately** after smoke test completes (success or failure).

- [ ] **R1** — Set `MODIR_VOICE_LIVE_TTS_ENABLED=false` (or unset env var)
- [ ] **R2** — Set `LIVE_RUNTIME_EXECUTION_APPROVED=False` in code/config (revert 11H-2d test branch)
- [ ] **R3** — Restart API server if env flags require restart
- [ ] **R4** — Verify `/voice/run` with `live_elevenlabs` returns `LIVE_TTS_DISABLED` again
- [ ] **R5** — Verify mock `/voice/run` still works on a separate session
- [ ] **R6** — **Do not delete** smoke test artifacts — retain for inspection
- [ ] **R7** — Copy artifact path + manifest to run log
- [ ] **R8** — Document actual character count and estimated/actual cost
- [ ] **R9** — Write smoke test completion note to `project_brain/` (11H-2d report)
- [ ] **R10** — Expire voice approval on test session if no further testing planned:

```http
POST /sessions/{session_id}/voice/expire
{ "reason": "Smoke test complete — approval expired", "expired_by": "operator_smoke_test" }
```

---

## 5. Failure handling checklist

If live run fails, **do not** immediately retry in live mode.

### Expected failure response shape

```json
{
  "success": false,
  "status": "failed",
  "provider_mode": "live_elevenlabs",
  "tts_executed": false,
  "real_provider_called": true,
  "video_mutated": false,
  "code": "ELEVENLABS_RATE_LIMIT",
  "reject_reasons": ["..."]
}
```

### Failure checklist

- [ ] **F1** — Confirm `voice_generation.status` is `failed` (or `cancelled` if cooperatively cancelled)
- [ ] **F2** — Confirm `executed=false`, `live_tts_executed=false`
- [ ] **F3** — Confirm `tts_executed=false` in API response
- [ ] **F4** — Record `error.code` from voice slot (mapped taxonomy code)
- [ ] **F5** — Confirm **no retry loop explosion** — adapter retry count ≤ smoke limit (1 retry)
- [ ] **F6** — Confirm **video slot unchanged** (same snapshot comparison)
- [ ] **F7** — Document partial artifacts if any (cancel mid-run):
  - Partial MP3 files kept on disk
  - Manifest `partial: true` if written
  - `validation_status: partial` or absent
- [ ] **F8** — Execute rollback checklist (Section 4) before any investigation retry
- [ ] **F9** — If retry needed, use **mock mode first** to validate engine path, then schedule second supervised live attempt with fresh approval

### Failure code reference

| Code | Meaning | Operator action |
|---|---|---|
| `LIVE_TTS_DISABLED` | Gates not enabled | Expected pre-11H-2d; enable only with approval |
| `LIVE_TTS_NOT_CONFIRMED` | Missing `confirm_live_tts` | Fix request body |
| `APPROVAL_REQUIRED` | Voice not approved | Run approve first |
| `APPROVAL_EXPIRED` | TTL elapsed | Re-approve with short TTL |
| `ELEVENLABS_KEY_MISSING` | No API key | Fix `.env`, restart |
| `ELEVENLABS_RATE_LIMIT` | HTTP 429 | Wait, rollback, retry later |
| `ELEVENLABS_TIMEOUT` | Request timeout | Check network, reduce text, retry later |
| `ELEVENLABS_HTTP_ERROR` | Other HTTP error | Check ElevenLabs status, logs (no key in logs) |
| `ELEVENLABS_EMPTY_AUDIO` | Zero-byte response | Do not mark success; investigate |
| `ELEVENLABS_CANCELLED` | Cooperative cancel | Expected if cancel flag set |
| `ARTIFACT_VALIDATION_FAILED` | MP3 validation fail | Inspect file on disk |

---

## 6. Operator quick-reference checklist

Print and tick during supervised test:

```
□ Backup created
□ Test session ID: ____________________
□ ELEVENLABS_API_KEY present (not printed)
□ MODIR_VOICE_LIVE_TTS_ENABLED=true (temporary)
□ LIVE_RUNTIME_EXECUTION_APPROVED=True (temporary, 11H-2d branch)
□ Single segment ≤ 300 chars confirmed
□ Voice approved (tts_executed=false on approve response)
□ can_run_live_voice_tts allowed confirmed
□ Video snapshot recorded BEFORE
□ Operator manual confirm PAUSE taken
□ POST /voice/run live_elevenlabs + confirm_live_tts=true
□ Response: real_provider_called=true, tts_executed=true
□ narration_001.mp3 exists, size > 0
□ voice_manifest.json valid
□ video_generation unchanged
□ Rollback: env flags OFF
□ Rollback: LIVE_RUNTIME_EXECUTION_APPROVED=False
□ Artifacts retained, cost/characters logged
□ Smoke report written
```

---

## 7. What 11H-2d implementation must deliver (future)

This plan assumes 11H-2d implementation (not started) will:

1. Set `LIVE_RUNTIME_EXECUTION_APPROVED = True` only in controlled test configuration
2. Wire `LiveVoiceTtsEngine` to use `build_elevenlabs_runtime_adapter()` when live mode passes all gates
3. Apply smoke-test overrides: 1 segment cap, 300 chars, 60s timeout, 1 max retry (config or smoke profile)
4. Write live manifest via `build_live_manifest_extras()`
5. Set `real_provider_called=true` only on successful live adapter path
6. Add `validate_11h2d_live_smoke_test.py` (optional — may use manual checklist only for first run)

**None of the above is implemented in 11H-2d-0.**

---

## Phase gate

| Phase | Status |
|---|---|
| 11H-2c Adapter + mocked HTTP | ✅ Complete |
| **11H-2d-0 Smoke test plan (this document)** | ✅ **Complete** |
| 11H-2d Supervised live smoke test | 🔒 **Not approved — requires separate explicit approval** |
| 11H-2e Production live enablement | 🔒 Not in scope |

---

## Final approval note

> **Implementation of real ElevenLabs live TTS is NOT included in Phase 11H-2d-0.**
>
> This document is an operator runbook only. To proceed to **Phase 11H-2d** (first supervised real API call), the architect must explicitly approve:
>
> 1. Temporary enablement of `LIVE_RUNTIME_EXECUTION_APPROVED` and `MODIR_VOICE_LIVE_TTS_ENABLED`
> 2. 11H-2d code implementation wiring live adapter to `/voice/run`
> 3. Execution of this checklist by a named operator in a controlled environment
>
> Until that approval is given, **do not enable live TTS, do not call ElevenLabs, and do not generate paid audio.**

---

*Plan only. Current codebase remains mock-only. No changes to `/voice/run` behavior in this phase.*
