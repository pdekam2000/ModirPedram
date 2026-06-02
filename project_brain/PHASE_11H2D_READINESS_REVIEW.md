# Phase 11H-2d-R — Architecture Readiness Review Before First Live TTS

**Date:** 2026-05-31  
**Type:** Review only — no implementation, no flag changes, no API calls, no TTS  
**Prerequisites reviewed:** 11G, 11H-1a→1j, 11H-2a, 11H-2b, 11H-2c, 11H-2d-0

---

## Executive verdict

| Question | Answer |
|---|---|
| **Ready for first paid/live ElevenLabs call today?** | **NOT READY** |
| **Ready to begin Phase 11H-2d implementation (supervised smoke wiring)?** | **YES — with bounded gaps** |
| **Confidence score** | **79 / 100** |

**Final recommendation:** **Complete 11H-2d implementation first**, then execute the supervised smoke test per `PHASE_11H2D0_REAL_TTS_SMOKE_TEST_PLAN.md`. Do **not** enable live TTS or call ElevenLabs until that implementation slice lands and passes validation.

The architecture is **sound and fail-closed**. Remaining work is **implementation wiring and a small set of lifecycle/telemetry fixes** — not a redesign.

---

## Current safety state (confirmed)

| Control | State |
|---|---|
| `/voice/run` execution | Mock only (`MockVoiceTtsProvider`) |
| `provider_mode=live_elevenlabs` | Blocked → `LIVE_TTS_DISABLED` |
| `LIVE_RUNTIME_EXECUTION_APPROVED` | `False` (hardcoded) |
| `MODIR_VOICE_LIVE_TTS_ENABLED` | Default `false` |
| Real ElevenLabs HTTP | Adapter exists; `allow_real_http=False` without injected client |
| Legacy `ElevenLabsVoiceProvider` in Content Brain runtime | Not imported |
| Video dispatch | Unchanged; voice hook is additive preflight only |

**Validator baseline (last known):** 11H-2c 26/26, 11H-2a 20/20, 11H-1i 16/16, 11G 20/20, 11H-1j 107/107 + build PASS.

---

## Review by area

### 1. Runtime architecture

| Aspect | Status | Notes |
|---|---|---|
| Multi-category shell (11G) | ✅ Complete | Video/voice slots isolated |
| Mock execution path | ✅ Complete | Policy → engine → mock provider → validator → manifest |
| Live adapter module | ✅ Complete | `elevenlabs_runtime_adapter.py` + factory + mocked HTTP tests |
| Live engine wiring | ❌ **Gap** | `LiveVoiceTtsEngine.run()` always uses `MockVoiceTtsProvider`; factory not invoked |
| Provider dispatch from `/voice/run` | ❌ **Gap** | Service forces mock after mode policy |
| Video dispatch isolation | ✅ Verified | No voice TTS on `ProviderRuntimeEngine.dispatch` |
| Execution lock / concurrent run guard | ✅ Partial | Policy blocks `JOB_ALREADY_ACTIVE` when status=`running` |
| Preflight coexistence | ⚠️ **Risk** | `apply_voice_preflight_dry_run()` always sets `executed=False`, `live_tts=False` — would clobber a completed live run on next video dispatch |

**Assessment:** Architecture is correct; live path is **designed but not connected**.

---

### 2. Approval architecture

| Aspect | Status | Notes |
|---|---|---|
| Category-scoped voice approval | ✅ Complete | Separate from session `approval_decision` |
| Read-only guard (11H-1e) | ✅ Complete | `can_run_live_voice_tts()` metadata |
| Write APIs (11H-1g) | ✅ Complete | Approve/reject/expire/reset |
| UI controls (11H-1i) | ✅ Complete | Approve modal safety text; no Run TTS |
| Approve does not auto-run | ✅ Verified | Separate `/voice/run` trigger |
| Live mode double confirm | ✅ Designed | `confirm_live_tts` + server flags (11H-2c policy) |
| TTL / expiration | ✅ Complete | Guard + write APIs |
| Audit on approval writes | ✅ Complete | `operations.voice_approval_audit[]` |

**Assessment:** **Ready** for live execution gating. No approval architecture blockers.

---

### 3. Failure taxonomy

| Aspect | Status | Notes |
|---|---|---|
| Core dispatch/preflight/artifact codes | ✅ Complete | `failure_taxonomy.py` |
| ElevenLabs live codes (11H-2c) | ✅ Registered | `ELEVENLABS_*`, `LIVE_TTS_DISABLED`, etc. |
| Engine maps adapter codes on live path | ❌ **Gap** | Mock engine uses `CANCELLED` / `PROVIDER_ERROR`; live wiring must propagate adapter `reject_code` |
| UI displays voice error codes | ✅ Partial | `errorCode` + blocked reasons in observability panel |

**Assessment:** Taxonomy is **ready**; live engine must map adapter results consistently (11H-2d task).

---

### 4. Manifest structure

| Aspect | Status | Notes |
|---|---|---|
| Mock manifest (11H-2a) | ✅ Complete | `voice_manifest.json` with required fields |
| Live manifest design (11H-2b) | ✅ Documented | `provider`, `voice_id`, `model_id`, `real_provider_called`, etc. |
| `build_live_manifest_extras()` | ✅ Exists | Not merged into engine `_build_manifest()` yet |
| Per-segment `request_id`, `retry_count`, `latency_ms` | ⚠️ **Gap** | Adapter returns them; engine manifest writer does not include live fields |
| Smoke caps snapshot in manifest | ✅ Prepared | Via `build_live_manifest_extras()` |

**Assessment:** **Not ready for live** until engine writes live manifest schema (11H-2d task). Non-blocking for smoke if implemented in same slice.

---

### 5. Artifact validation

| Aspect | Status | Notes |
|---|---|---|
| `AudioArtifactValidator` | ✅ Complete | Path, extension, min size |
| Wired post-generation (mock) | ✅ Complete | Before `tts_executed=true` |
| MP3 header / duration check | ⏸ Deferred | Acceptable for smoke test |
| Manifest consistency check | ⚠️ Partial | Implicit via segment count; no dedicated manifest-vs-disk validator |
| Empty audio rejection (live) | ✅ Adapter | `ELEVENLABS_EMPTY_AUDIO` |

**Assessment:** **Adequate for first smoke test.** Duration validation can follow post-smoke.

---

### 6. Cost visibility

| Aspect | Status | Notes |
|---|---|---|
| Pre-run estimate (approval block) | ✅ Complete | `estimated_voice_cost` via cost catalog |
| Live caps on estimate | ✅ Complete | Policy `evaluate_voice_live_tts_live_caps()` |
| Post-execution actual cost | ❌ **Gap** | No `operations.voice_cost_events[]` or manifest `actual_cost` |
| ElevenLabs usage API integration | ❌ Not built | Optional for smoke; log manual estimate acceptable |
| UI cost display | ✅ Partial | Estimated cost in approval observability only |

**Assessment:** **Non-blocking for smoke** if operator logs estimate manually per 11H-2d-0. **Recommended** post-smoke telemetry slice.

---

### 7. Cancellation path

| Aspect | Status | Notes |
|---|---|---|
| Session `operations_control.cancel_requested` | ✅ Complete | Shared with video |
| Policy blocks cancel before run | ✅ Complete | |
| Engine checks between segments | ✅ Complete | Mock path |
| Adapter cancel between attempts | ✅ Complete | Mocked HTTP tests PASS |
| Voice-specific cancel endpoint | ⏸ Not built | Session cancel sufficient for smoke |
| Cancelled status on voice slot | ✅ Complete | `cancelled` state + partial manifest |

**Assessment:** **Ready** for supervised smoke test.

---

### 8. Progress tracking

| Aspect | Status | Notes |
|---|---|---|
| `live_tts_progress` block on voice slot | ✅ Complete | segment, percent, retry, timestamps |
| Persisted during run | ✅ Complete | Checkpoint saves in engine loop |
| Panel DTO / API exposes progress | ⚠️ **Gap** | `panel_extractor` does not surface `live_tts_progress` |
| UI progress display | ❌ **Gap** | No progress bar / segment counter in Execution Center |
| `voiceTtsRunning` heuristic | ✅ Partial | Status `running` or `live_tts` in `categoryRuntimeShell.ts` |

**Assessment:** **Backend sufficient for smoke** (inspect session JSON). **UI gap is non-blocking** for first supervised test via API/curl.

---

### 9. UI observability

| Aspect | Status | Notes |
|---|---|---|
| Voice runtime observability panel | ✅ Complete | Preflight, approval gate, blocked reasons |
| Approval controls | ✅ Complete | Approve/reject/expire/reset |
| Forbidden Run TTS labels | ✅ Verified | Static grep clean |
| `tts_executed` assert on approval APIs | ✅ Complete | |
| Live run button / `/voice/run` client | ❌ Intentionally absent | Smoke test via API acceptable |
| `real_provider_called` / `provider_mode` in UI | ❌ **Gap** | Not in observability DTO |
| Post-run manifest link | ❌ **Gap** | Not displayed |

**Assessment:** **Adequate for approval-phase operations.** Live smoke can be operator-driven via HTTP without UI (per 11H-2d-0).

---

### 10. Audit trail completeness

| Aspect | Status | Notes |
|---|---|---|
| `voice_approval_audit[]` | ✅ Complete | Unique event IDs, all write actions |
| `voice_tts_audit[]` | ✅ Complete | Run events with `provider_mode`, `tts_executed` |
| `voice_tts_execution` operations mirror | ✅ Complete | Last run metadata |
| Global `operations_audit.jsonl` for voice TTS | ⚠️ Unknown / partial | Engine appends session-local audit; global ops audit not verified for voice runs |
| Post-live cost in audit | ❌ **Gap** | Not recorded |
| Actor + reason on run | ✅ Complete | Request body fields |

**Assessment:** **Session-level audit sufficient for smoke.** Global audit alignment is a minor follow-up.

---

### 11. Session persistence

| Aspect | Status | Notes |
|---|---|---|
| `ExecutionSessionStore` load/save | ✅ Complete | |
| Video slot preservation check | ✅ Complete | Raises on mutation |
| Incremental persist during run | ✅ Complete | Per-segment checkpoint |
| Session schema version | ✅ Stable | |
| Artifact paths on disk | ✅ Complete | `artifacts/{session_id}/voice_generation/` |

**Assessment:** **Ready.**

---

### 12. Rollback strategy

| Aspect | Status | Notes |
|---|---|---|
| Operator rollback checklist (11H-2d-0) | ✅ Complete | Env flags, approval expire, artifact retention |
| Code auto-disable on failure | ❌ Not built | Manual rollback only (acceptable for smoke) |
| Artifact auto-delete | ✅ None | Partial artifacts retained by design |
| Revert `LIVE_RUNTIME_EXECUTION_APPROVED` | ✅ Documented | Manual in test branch |
| Mock path regression after rollback | ✅ Validators | 11H-2a/2c regression tests exist |

**Assessment:** **Adequate for supervised smoke** with operator discipline.

---

### 13. Smoke test plan completeness

| Aspect | Status | Notes |
|---|---|---|
| `PHASE_11H2D0_REAL_TTS_SMOKE_TEST_PLAN.md` | ✅ Complete | Limits, preconditions, flow, rollback, failure |
| Stricter limits vs production caps | ✅ Defined | 1 segment, 300 chars, $0.10, 1 retry, 60s timeout |
| Explicit non-approval of live execution | ✅ Clear | |
| 11H-2d implementation prerequisites listed | ✅ Complete | Engine wiring, temporary flags |

**Assessment:** **Ready** as operator runbook once 11H-2d code lands.

---

## Remaining blockers (must fix in 11H-2d before first live call)

These are **implementation blockers**, not architectural flaws:

| # | Blocker | Severity | Owner slice |
|---|---|---|---|
| B1 | Wire `LiveVoiceTtsEngine` to `build_elevenlabs_runtime_adapter()` when live mode passes all gates | **Critical** | 11H-2d |
| B2 | `VoiceRunService` must pass resolved `provider_mode` to engine (not force mock after policy allows live) | **Critical** | 11H-2d |
| B3 | Temporary enablement: `LIVE_RUNTIME_EXECUTION_APPROVED` + env flag (test branch only) | **Critical** | 11H-2d |
| B4 | Merge `build_live_manifest_extras()` into live manifest; include per-segment `request_id` / `retry_count` | **High** | 11H-2d |
| B5 | Map adapter `reject_code` to voice slot `error.code` on live failure | **High** | 11H-2d |
| B6 | Preflight coexistence: do not reset `executed`/`live_tts` on completed voice runs during video dispatch hook | **High** | 11H-2d (or pre-smoke patch) |
| B7 | Smoke profile caps enforced in code (1 segment, 300 chars, reduced retry/timeout) | **High** | 11H-2d |
| B8 | `validate_11h2d` or extend smoke validation; manual checklist from 11H-2d-0 | **Medium** | 11H-2d |

**No blockers require redesign.** All are bounded implementation tasks already specified in 11H-2b and 11H-2d-0.

---

## Remaining risks (non-blocking or post-smoke)

| Risk | Severity | Mitigation |
|---|---|---|
| Preflight clobbers completed voice state on video dispatch | **High** | Fix B6 before or during 11H-2d |
| No post-execution cost telemetry | Medium | Manual log for smoke; add `voice_cost_events` post-smoke |
| No UI for live progress / run trigger | Low | API-driven smoke per 11H-2d-0 |
| MP3 not validated for playability (header/duration) | Low | Operator listens to file during smoke |
| `allow_real_http=True` misuse | Medium | Keep false in main; smoke branch only with review |
| Retry/cost explosion on provider outage | Medium | Smoke caps + operator abort; adapter max retry |
| Multi-segment brief accidentally used in smoke | Medium | 11H-2d-0 checklist + code smoke profile |
| Global ops audit not voice-aware | Low | Session audit sufficient for first test |

---

## Recommended fixes (ordered for 11H-2d implementation)

1. **Engine live branch** — Select provider via `build_voice_tts_provider()`; propagate `provider_mode`, `real_provider_called` through result, audit, manifest.
2. **Service pass-through** — Remove mock override when live policy allows; keep hard block when `LIVE_RUNTIME_EXECUTION_APPROVED=False`.
3. **Preflight guard** — Skip execution-flag reset when `voice_slot.status == completed` and `live_tts_executed == true`.
4. **Live manifest writer** — Call `build_live_manifest_extras()`; add per-file adapter metadata.
5. **Smoke profile** — Config or constants for 11H-2d smoke: 1 segment max, 300 chars, 60s timeout, 1 retry.
6. **Optional before smoke** — Extend `panel_extractor` with `live_tts_progress`, `voice_tts_execution`, `real_provider_called` for operator visibility without UI button.

**Do not implement in this review phase.**

---

## Confidence score breakdown

| Area | Weight | Score | Weighted |
|---|---|---|---|
| Safety gates & fail-closed design | 25 | 95 | 23.8 |
| Approval & audit architecture | 20 | 92 | 18.4 |
| Mock execution proof (11H-2a) | 15 | 90 | 13.5 |
| Live adapter (mocked HTTP, 11H-2c) | 15 | 88 | 13.2 |
| Live wiring & manifest (not done) | 15 | 35 | 5.3 |
| Observability / telemetry / UX | 10 | 55 | 5.5 |
| **Total** | **100** | — | **79.7 → 79** |

---

## Architecture diagram (current vs 11H-2d target)

```
TODAY (11H-2c)                         11H-2d TARGET (after implementation)
────────────────                       ────────────────────────────────────
POST /voice/run                        POST /voice/run
  → mode policy                          → mode policy (live allowed if flags on)
  → LIVE_TTS_DISABLED if live            → engine provider_mode=live_elevenlabs
  → engine (mock only)                   → ElevenLabsRuntimeAdapter (real HTTP)
  → MockVoiceTtsProvider                 → AudioArtifactValidator
  → manifest (mock)                      → manifest (live + extras)
```

---

## Final recommendation

### Do NOT proceed directly to a live ElevenLabs API call

The system is correctly **fail-closed**. A live call today would either fail at policy (`LIVE_TTS_DISABLED`) or would require unsafe manual bypass — both unacceptable.

### DO proceed to Phase 11H-2d **implementation**

Implement blockers **B1–B8** in a controlled test branch, run regression validators (11H-2a, 11H-2c, 11H-1i, 11G), then execute the supervised smoke test exactly per `PHASE_11H2D0_REAL_TTS_SMOKE_TEST_PLAN.md` with:

- One session, one segment, ≤300 characters
- Temporary flags enabled only for the test window
- Immediate rollback after test
- Named operator sign-off

### Post-smoke (11H-2e+, not in scope now)

- Post-execution cost telemetry
- UI progress and optional Run Voice control (separate UX approval)
- MP3 duration validation
- Production cap tuning

---

## Sign-off matrix

| Criterion | Met? |
|---|---|
| No accidental live path exists today | ✅ Yes |
| Approval architecture production-ready | ✅ Yes |
| Adapter tested with mocked HTTP only | ✅ Yes |
| Live engine wiring complete | ❌ No — 11H-2d |
| Smoke operator plan complete | ✅ Yes |
| Safe to call ElevenLabs now | ❌ **No** |
| Safe to start 11H-2d implementation | ✅ **Yes** |

---

## Phase gate

| Phase | Status |
|---|---|
| 11H-2d-0 Smoke test plan | ✅ Complete |
| **11H-2d-R Readiness review (this document)** | ✅ **Complete** |
| 11H-2d Implementation + supervised smoke | 🔒 Next — requires explicit approval to implement and execute |
| First paid/live ElevenLabs call | 🔒 Blocked until 11H-2d completes successfully |

---

*Review only. No code changes. No flags enabled. No ElevenLabs API calls. Video/Runway/Hailuo/legacy pipeline unchanged.*
