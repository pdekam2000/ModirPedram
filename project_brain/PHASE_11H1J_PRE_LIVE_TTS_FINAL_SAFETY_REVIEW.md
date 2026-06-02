# Phase 11H-1j — Pre-Live TTS Final Safety Review

**Date:** 2026-05-28  
**Phase:** 11H-1j (audit/review only — no implementation)  
**Status:** ✅ **PASS — safe to proceed to 11H-2 design/implementation only with explicit user approval**

---

## Executive summary

Phases 11G through 11H-1i have built a complete **voice preflight + approval metadata stack** with **zero live ElevenLabs TTS execution paths** in the Content Brain runtime, API, or Execution Center UI. All seven automated validator suites pass (107/107 tests). `npm run build` passes.

**No blocking safety issues were found.** Live TTS remains impossible until Phase 11H-2 explicitly wires an execution engine behind `can_run_live_voice_tts()` with user approval.

---

## Scope and constraints verified

| Constraint | Result |
|---|---|
| Do not start 11H-2 | ✅ No 11H-2 code added |
| Do not generate real ElevenLabs audio | ✅ Confirmed |
| Do not import/call `ElevenLabsVoiceProvider` in runtime/approval/UI | ✅ Confirmed |
| Do not modify video execution | ✅ Confirmed |
| Do not touch Runway/Hailuo or legacy pipeline | ✅ Confirmed |

---

## 1. Live TTS isolation

### Checklist

| Check | Result | Evidence |
|---|---|---|
| No code path executes live TTS | ✅ PASS | `content_brain/execution/` contains no `generate_voice`, no `text-to-speech` HTTP calls |
| No UI action triggers real TTS | ✅ PASS | UI only calls approval metadata POST endpoints; static grep finds no forbidden labels |
| No backend approval endpoint calls TTS | ✅ PASS | `VoiceApprovalOperationsEngine` docstring + implementation: metadata/audit only |
| No `ElevenLabsVoiceProvider` import in runtime/approval/UI stack | ✅ PASS | Provider exists only in legacy paths |

### Code path map (current)

```
ProviderRuntimeEngine.dispatch (video only)
  → ensure_multi_category_shell()
  → apply_voice_preflight_dry_run()   # dry-run metadata; live_tts=False, executed=False
  → _execute_clips()                  # video providers only — unchanged

Voice approval POST endpoints
  → VoiceApprovalOperationsEngine     # mutates voice_generation.approval + audit only
  → can_run_live_voice_tts()          # metadata guard — no provider call
```

### `ElevenLabsVoiceProvider` isolation

| Location | In runtime path? |
|---|---|
| `providers/elevenlabs_voice_provider.py` | Legacy provider module (not imported by Content Brain runtime) |
| `engines/narration_engine.py` | Legacy SelfCare pipeline |
| `test_*.py`, `full_selfcare_factory.py` | Standalone test/factory scripts |
| `content_brain/execution/*` | **Not present** |
| `ui/api/*`, `ui/web/src/*` | **Not present** |

### Voice slot invariants (preflight)

`voice_preflight_runtime_slot.py` always sets:

- `executed = False`
- `live_tts = False`
- `voice_provider_router.py`: `executed=False`, `dry_run=True` on all routes

**Verdict:** ✅ **No live TTS path exists** in the Content Brain execution stack.

---

## 2. Approval safety

### Checklist

| Check | Result | Evidence |
|---|---|---|
| Live TTS cannot be eligible without approval | ✅ PASS | `can_run_live_voice_tts()` requires `live_tts_requested=True` + effective `approval_state=approved` |
| Approval is category-scoped to `voice_generation` | ✅ PASS | Nested under `category_runtime.voice_generation.approval` |
| Session-level approval does not imply voice approval | ✅ PASS | `voice_approval_guard.py` has zero references to `approval_decision`; voice gate is independent |
| Expired/rejected approval blocks execution | ✅ PASS | `BLOCK_APPROVAL_EXPIRED`, `BLOCK_VOICE_APPROVAL_REJECTED` in guard |
| Reset clears grant fields correctly | ✅ PASS | `_mutate_reset()` clears `approved_by`, `approved_at`, `approval_reason`, `approval_expires_at`; re-evaluates gate |
| Audit trail records approve/reject/expire/reset | ✅ PASS | `_append_audit()` on both allowed and blocked actions |

### Approval gate logic (metadata-only today)

`can_run_live_voice_tts()` returns `allowed=True` only when **all** pass:

1. Narration not skipped  
2. Credentials present (`has_api_key`)  
3. Preflight ready  
4. `live_tts_requested=True`  
5. Effective approval state = `approved` (not expired/rejected)  
6. Character/cost limits  
7. Session budget not blocked  
8. No cooperative cancel  

When all checks pass, `allowed=True` is **eligibility metadata only** — no HTTP/TTS call follows in 11H-1.

### Write API safety

- Approve requires `request_live_tts=True` (blocks with `LIVE_TTS_NOT_REQUESTED` otherwise)
- Approve blocks on `NO_NARRATION`, `CREDENTIALS_MISSING`
- All responses include `tts_executed: false`
- Video slot preservation enforced: `_video_slot_preserved()` raises `RuntimeError` on mutation

**Verdict:** ✅ **Approval gate is correctly scoped and enforced at metadata layer.**

---

## 3. Credential safety

### Checklist

| Check | Result | Evidence |
|---|---|---|
| `ELEVENLABS_API_KEY` never printed | ✅ PASS | `ElevenLabsConfigResolver` reads env; `to_summary()` excludes key value |
| API key never returned to frontend | ✅ PASS | No `api_key` / `ELEVENLABS` fields in `ui/api/` responses |
| Config exposes only `has_api_key` boolean | ✅ PASS | `ElevenLabsConfigSnapshot.to_summary()` keys verified by 11H-1a validator |
| Missing key → `CREDENTIALS_MISSING` | ✅ PASS | Preflight + guard + approve policy all block |

**Verdict:** ✅ **Credentials safe — boolean probe only, no secret leakage.**

---

## 4. Runtime compatibility

### Checklist

| Check | Result | Evidence |
|---|---|---|
| `video_generation` behavior unchanged | ✅ PASS | `ProviderRuntimeEngine` dispatches `CATEGORY_VIDEO` only; voice hook is post-dispatch metadata |
| Voice metadata does not break video dispatch | ✅ PASS | Voice preflight preserves video slot; approval writes verify video snapshot |
| Legacy sessions open safely | ✅ PASS | `ensure_multi_category_shell()` normalizes missing slots; validators confirm `planned` fallback |
| `category_runtime_slots` backward compatible | ✅ PASS | 11G validator: legacy video state preserved, missing slots safe |

### Dispatch hook (unchanged video path)

```python
# provider_runtime_engine.py — voice hook is additive, after video shell
execution_runtime = ensure_multi_category_shell(execution_runtime)
execution_runtime = apply_voice_preflight_dry_run(session, execution_runtime, ...)
# video _execute_clips() proceeds unchanged
```

Non-video category dispatch remains rejected (`CATEGORY_NOT_SUPPORTED`).

**Verdict:** ✅ **Video runtime unchanged; voice is observability + metadata only.**

---

## 5. UI safety

### Checklist

| Check | Result | Evidence |
|---|---|---|
| No forbidden labels: Generate Voice / Run TTS / Start TTS | ✅ PASS | Static grep on `ui/web/src` — zero matches |
| Approve modal contains exact safety warning | ✅ PASS | `VOICE_APPROVE_SAFETY_WARNING` in `voiceApprovalLabels.ts` |
| UI requires `tts_executed === false` in API responses | ✅ PASS | `assertVoiceApprovalSafety()` in `voiceApprovalClient.ts` |
| Blocked reasons visible | ✅ PASS | `VoiceRuntimeObservabilityPanel` shows "Blocked because" + approval gate section |

### Approve modal safety text (exact match)

> This only approves future voice generation. It does not generate audio yet.

Additional UI copy reinforces: *"Read-only dry-run observability — no live TTS execution in this phase."*

**Verdict:** ✅ **UI cannot trigger or imply live TTS execution.**

---

## 6. Data integrity

### Checklist

| Check | Result | Evidence |
|---|---|---|
| Approval writes mutate only `voice_generation.approval` + `operations.voice_approval_audit` | ✅ PASS | `_persist_voice_slot()` replaces voice slot; video slot copied back unchanged |
| Video slot not mutated | ✅ PASS | Before/after snapshot check on critical keys (`state`, `provider`, `started_at`, `completed_at`) |
| Audit trail uses unique event IDs | ✅ PASS | `generate_voice_approval_audit_event_id()` → `voice_appr_evt_{stamp}_{uuid6}` |
| Runtime panel DTO still works | ✅ PASS | `_panel_excerpt()` + `resolveVoiceRuntimeObservability()` wired in UI |

### Audit event schema (sample fields)

- `event_id`, `event_type`, `actor`, `timestamp`
- `previous_state`, `new_state`, `allowed`, `blocked_reasons`
- `live_tts_eligible`, `tts_executed: false`
- Capped at 50 events (`AUDIT_MAX_EVENTS`)

**Verdict:** ✅ **Data integrity constraints hold.**

---

## 7. Pre-11H-2 readiness assessment

### Already in place (11H-1 foundation)

| Component | Status |
|---|---|
| Multi-category runtime shell (11G) | ✅ Complete |
| Voice foundation: router, config, narration adapter (11H-1a) | ✅ Complete |
| Voice preflight dry-run runtime slot (11H-1b) | ✅ Complete |
| Voice UI observability (11H-1c) | ✅ Complete |
| Voice approval read-only guard (11H-1e) | ✅ Complete |
| Voice approval write APIs (11H-1g) | ✅ Complete |
| Voice approval UI controls (11H-1i) | ✅ Complete |
| `can_run_live_voice_tts()` structured guard | ✅ Complete (metadata) |
| `AudioArtifactValidator` (MP3 validation primitive) | ✅ Exists (not wired to live path) |
| `ElevenLabsPreflight` (probe-only) | ✅ Complete |

### Still missing for live TTS (11H-2 scope)

| Component | Status | Notes |
|---|---|---|
| Live TTS execution engine | ❌ Not built | Must wrap `ElevenLabsVoiceProvider` behind guard + explicit phase gate |
| Artifact output folder convention | ❌ Not defined | Video uses `artifact_root`; voice needs `{session}/voice/` convention |
| MP3 validation wired to live output | ❌ Not wired | `AudioArtifactValidator` exists; needs post-generation hook |
| Retry/cancel support for voice | ❌ Not built | Video has cooperative cancel; voice slot needs parallel semantics |
| Cost telemetry (live execution) | ❌ Not built | Estimates exist in approval; no post-execution cost recording |
| Status transitions: running/completed/failed | ❌ Not built | Voice slot stays `pending`/`planned`; no execution lifecycle |
| UI live progress display | ❌ Not built | Current UI is read-only observability + approval controls |
| Rollback/cleanup policy | ❌ Not defined | Need failed-run artifact cleanup + session state recovery |

### 11H-2 readiness score

**68 / 100** — Strong approval + preflight + observability foundation; execution layer entirely absent by design.

| Area | Weight | Score | Rationale |
|---|---|---|---|
| Isolation & safety gates | 25 | 25/25 | Complete — no accidental live path |
| Approval & audit | 20 | 20/20 | Complete end-to-end |
| Preflight & narration | 15 | 14/15 | Minor: live segment batching strategy TBD |
| Execution engine | 20 | 0/20 | Not started (correct for 11H-1) |
| Artifacts & validation | 10 | 4/10 | Validator exists; path/convention unwired |
| UI & telemetry | 10 | 5/10 | Observability done; live progress missing |

---

## Validators run

All executed 2026-05-28 on workspace `C:\Users\kaman\Desktop\ModirAgentOS`.

| Validator | Result |
|---|---|
| `python -m project_brain.validate_11h1i_voice_approval_ui_controls` | **16/16 PASS** |
| `python -m project_brain.validate_11h1g_voice_approval_write_apis` | **16/16 PASS** |
| `python -m project_brain.validate_11h1e_voice_approval_guard` | **18/18 PASS** |
| `python -m project_brain.validate_11h1c_voice_ui_observability` | **17/17 PASS** |
| `python -m project_brain.validate_11h1b_voice_preflight_runtime_slot` | **10/10 PASS** |
| `python -m project_brain.validate_11h1a_voice_foundation` | **10/10 PASS** |
| `python -m project_brain.validate_11g_multi_category_runtime_shell` | **20/20 PASS** |
| `npm run build` (ui/web) | **PASS** (`tsc && vite build`) |

**Total automated checks:** 107/107 PASS + frontend build PASS

---

## Blocking issues

**None.**

No validator failures. No accidental live TTS wiring. No credential leakage. No video runtime regression detected.

---

## Non-blocking risks (monitor in 11H-2)

| Risk | Severity | Mitigation for 11H-2 |
|---|---|---|
| `can_run_live_voice_tts().allowed=True` could be misread as "safe to call provider" | Medium | 11H-2 engine must call guard immediately before first HTTP; add explicit `live_tts_executed` flip only after successful generation |
| Legacy `ElevenLabsVoiceProvider` still callable from old scripts | Low | Keep Content Brain path isolated; do not import legacy provider from `provider_runtime_engine` |
| Approve sets `live_tts_requested=True` — eligibility metadata becomes true when fully approved | Low | Expected; 11H-2 must add separate **execution trigger** (not auto-run on approve) |
| `ElevenLabsVoiceProvider` uses `load_dotenv()` and raises on missing key at construct time | Low | 11H-2 adapter should inject config from `ElevenLabsConfigResolver` rather than re-constructing legacy provider blindly |
| No voice-specific rollback/cleanup yet | Medium | Define artifact cleanup on failed/cancelled voice runs before first live execution |

---

## Confirmations

| Statement | Confirmed |
|---|---|
| No live TTS path exists in Content Brain runtime/API/UI | ✅ Yes |
| Video runtime behavior unchanged | ✅ Yes |
| Credentials safe (boolean probe only) | ✅ Yes |
| Phase 11H-2 not started | ✅ Yes |

---

## Recommended 11H-2 implementation boundaries

**Requires explicit user approval before any live ElevenLabs TTS work begins.**

### In scope (11H-2)

1. **`VoiceLiveTtsExecutionEngine`** (new module under `content_brain/execution/`)
   - Entry: explicit dispatch/trigger only (not on approve, not on video dispatch)
   - Must call `can_run_live_voice_tts()` immediately before any HTTP
   - Wrap legacy `ElevenLabsVoiceProvider` via thin adapter (inject config from `ElevenLabsConfigResolver`)

2. **Artifact convention**
   - `{session_artifact_root}/voice/{segment_id}.mp3`
   - Record paths in `voice_generation.artifacts[]`

3. **Lifecycle**
   - Voice slot states: `pending` → `running` → `completed` | `failed`
   - Set `live_tts=True`, `executed=True` only after validated MP3 write
   - Cooperative cancel parity with video

4. **Post-generation**
   - `AudioArtifactValidator` on each output
   - Cost telemetry append to `operations.voice_cost_events[]`
   - Failed-run cleanup policy

5. **UI (read-only progress first)**
   - Show running/completed/failed on voice observability panel
   - **Still no** "Generate Voice" / "Run TTS" until separate UX approval phase if desired

### Out of scope (11H-2)

- Video dispatch changes
- Runway/Hailuo modifications
- Legacy `NarrationEngine` / SelfCare pipeline refactor
- Music/subtitles/assembly categories
- Auto-run TTS on approval success

### Mandatory safety gates for 11H-2 PR

- [ ] Static grep: no `ElevenLabsVoiceProvider` import outside approved adapter module
- [ ] Validator: live path blocked when `can_run_live_voice_tts().allowed=False`
- [ ] All execution responses distinguish `tts_executed` from `live_tts_eligible`
- [ ] Video slot preservation test on voice execution writes
- [ ] Credential never in API response or logs

---

## Phase gate

| Phase | Status |
|---|---|
| 11H-1a – 11H-1i | ✅ Complete |
| **11H-1j (this review)** | ✅ **Complete — PASS** |
| 11H-2 Live TTS execution | 🔒 **Blocked — requires explicit user approval** |

---

*Audit performed by static code review + full validator suite. No live ElevenLabs API calls were made during this review.*
