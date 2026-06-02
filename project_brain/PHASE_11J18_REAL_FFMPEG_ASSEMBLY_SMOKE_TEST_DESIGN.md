# Phase 11J-18 — Real FFmpeg Assembly Smoke Test Design

**Status:** Design only — no implementation, no FFmpeg invocation, no env flag changes  
**Date:** 2026-06-01  
**Prerequisites:** 11J-2 through 11J-17 complete; readiness **82/100**; no assembly blockers  
**Next phase:** **PHASE 11J-19 — Real FFmpeg Assembly Smoke Test Implementation** (requires separate explicit operator approval)

---

## Explicit Approval Boundary

> **This design document does NOT authorize real FFmpeg execution.**

Phase 11J-18 specifies *how* the first supervised smoke test *would* run in 11J-19. No FFmpeg binary may be invoked, no `FINAL_PUBLISH_READY.mp4` may be created, and no real execution env flags may be enabled until:

1. Operator explicitly approves **11J-19 implementation**, and  
2. Operator manually runs the supervised smoke runner **once** with flags set only for that session window.

Approval UI controls (11J-16) remain metadata-only. **No UI button** for real assembly in 11J-19 smoke scope — operator uses a **supervised CLI runner** or API with `confirm_real_assembly=true` (backend-only, not exposed in Execution Center UI initially).

---

## Smoke Test Purpose

The first real FFmpeg assembly smoke test validates end-to-end that:

1. All existing gates (plan READY, dry-run completed, category approval, dual env flags, explicit confirm) work together before subprocess invocation.
2. `AssemblyFFmpegExecutor` can produce **one** small `FINAL_PUBLISH_READY.mp4` from known-good upstream artifacts.
3. `assembly_manifest.json` is written with truthful metadata.
4. Only `assembly_generation` mutates; video/voice/subtitle slots remain unchanged.
5. Flags and approval are **disabled/expired after the test** — fail-closed by default restored.

This is **not** production assembly. It is a single-session, operator-supervised proof that the guarded real path is safe and observable.

**Reference pattern:** Phase 11H-2e supervised ElevenLabs voice smoke (`run_11h2e_supervised_smoke_test.py`) — isolated session, explicit approval, env flags scoped to test window, post-run report, flags disabled.

---

## Strict Smoke Limits

| Limit | Value |
|-------|-------|
| Sessions | **1** dedicated smoke session only |
| Video clips | **1–2** short clips (≤ ~8 s each recommended) |
| Voice | **1** MP3 narration segment only |
| Subtitle | **1** file, **ASS preferred** (SRT fallback only if ASS unavailable) |
| Max final duration | **15 seconds** |
| Max output size target | **≤ 5 MB** (soft cap; fail if wildly larger) |
| Request timeout | **120 seconds** (`timeout_seconds: 120`) |
| Music layer | **None** |
| Multi-language | **None** |
| Output variants | **Primary only** (`FINAL_PUBLISH_READY.mp4`) |
| Batch / parallel runs | **Forbidden** — one FFmpeg invocation |
| Overwrite existing output | **Forbidden** (`overwrite: false`) |
| Session reuse | **Forbidden** — new `exec_11j19_smoke_*` session per run |

### Smoke profile constants (11J-19)

Proposed module: `content_brain/execution/assembly_smoke_profile.py`

```python
SMOKE_MAX_VIDEO_CLIPS = 2
SMOKE_MAX_VOICE_SEGMENTS = 1
SMOKE_MAX_SUBTITLE_FILES = 1
SMOKE_MAX_DURATION_SECONDS = 15
SMOKE_MAX_OUTPUT_BYTES = 5_000_000
SMOKE_TIMEOUT_SECONDS = 120
SMOKE_SESSION_PREFIX = "exec_11j19_smoke_"
```

Policy and executor must **reject** real runs that exceed smoke caps when `triggered_by=operator_smoke_test` or when `assembly_smoke_mode=true` (11J-19 implementation detail).

---

## Architecture (Target 11J-19)

```
Operator (manual)
  → run_11j19_supervised_assembly_smoke_test.py   [NEW — CLI only]
      → set env flags (test window only)
      → seed tiny session + artifacts
      → POST dry-run /assembly/run (dry_run=true)
      → POST /assembly/approve (request_real_assembly=true)
      → POST /assembly/run (dry_run=false, confirm_real_assembly=true)
          → evaluate_assembly_run_request (real path)     [EXTEND 11J-19]
          → can_run_real_assembly()                       [EXISTING 11J-12]
          → assembly_ffmpeg_preflight (binary + version)  [NEW 11J-19]
          → AssemblyFFmpegExecutor.execute(dry_run=false) [EXTEND 11J-19]
          → assembly_runtime_engine persist slot + manifest
      → verify artifacts
      → expire/reset approval
      → unset env flags
      → write PHASE_11J19_* report
```

**Out of scope for smoke:** UI "Run Assembly" button, batch queue, `full_video_pipeline.py`, Runway/Hailuo mutation.

---

## Preconditions (Before 11J-19 Smoke)

All must pass before any real run attempt. Operator checklist — manual sign-off recommended.

| # | Precondition | Verification |
|---|--------------|--------------|
| 1 | FFmpeg binary on PATH or `FFMPEG_PATH` set | `assembly_ffmpeg_preflight.check_binary()` → version string logged |
| 2 | FFmpeg version check passes | Minimum version policy TBD in 11J-19 (e.g. major ≥ 4.x); fail with `ASSEMBLY_FFMPEG_FAILED` if missing |
| 3 | `AssemblyPlan.validation_status == READY` | Plan builder + artifact validator |
| 4 | Assembly dry-run completed | `status=completed`, `dry_run=true`, `planned_steps.length >= 1` |
| 5 | Category approval **approved** | `assembly_generation.approval.approval_state=approved`, not expired |
| 6 | `real_assembly_requested=true` on slot | Set by approve API |
| 7 | `MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED=true` | **Only during test window** — default `false` |
| 8 | `ASSEMBLY_RUNTIME_EXECUTION_APPROVED=true` | **Only during test window** — default `false` |
| 9 | Output directory empty or smoke-specific | `{artifact_root}/assembly_generation/` has no existing `FINAL_PUBLISH_READY.mp4` unless `overwrite=true` (smoke forbids overwrite) |
| 10 | Project backup / handoff snapshot | Operator confirms recent backup or git clean state |
| 11 | Upstream artifacts snapshot recorded | Deep-copy `video_generation`, `voice_generation`, `subtitle_generation` before run |
| 12 | Disk space sufficient | ≥ 100 MB free on artifact volume (conservative for smoke) |
| 13 | Operator manual confirm | CLI prompt: `Type SMOKE to proceed` or `--i-understand-real-ffmpeg` flag |
| 14 | No active assembly run | `assembly_generation.status != running` |
| 15 | Session not archived / not cancelled | Operations control |

### Explicit non-requirements (unchanged from 11J-14)

- Session-level `approval_decision` — **not** required  
- Voice `approval_state` — **not** required  
- Subtitle slot `completed` — **not** required (artifact existence only)

---

## Request Body (Future Real Run)

Extend `AssemblyRunRequest` in 11J-19 (schema change — design only here):

```json
POST /sessions/{session_id}/assembly/run
{
  "dry_run": false,
  "confirm_real_assembly": true,
  "triggered_by": "operator_smoke_test",
  "reason": "11J-19 supervised first real FFmpeg assembly smoke test",
  "overwrite": false,
  "timeout_seconds": 120
}
```

| Field | Required for real | Notes |
|-------|-------------------|-------|
| `dry_run` | `false` | Dry-run remains default `true` for all normal API calls |
| `confirm_real_assembly` | `true` | New explicit confirm gate (mirrors voice `confirm_live_tts`) |
| `triggered_by` | `operator_smoke_test` | Enables smoke profile caps |
| `reason` | recommended | Audit + `operations.assembly_execution` log |
| `overwrite` | `false` | Smoke forbids overwrite |
| `timeout_seconds` | `120` | Hard cap for subprocess |

### Policy gate order (11J-19 real path)

1. Session exists, not archived, not cancelled  
2. Assembly slot exists, not already running  
3. `dry_run=false` → enter real path (not immediate reject as today)  
4. `confirm_real_assembly=true` else → `ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED` (new code)  
5. Smoke caps (if smoke triggered_by)  
6. Plan READY  
7. Dry-run completed marker present  
8. `can_run_real_assembly()` — approval + env flags  
9. FFmpeg preflight binary/version  
10. Output path safe (no collision unless overwrite)  
11. Allow → engine invokes executor real branch once  

---

## Expected Success Behavior

When all gates pass and FFmpeg completes within timeout:

### Artifacts

| Artifact | Path | Requirement |
|----------|------|-------------|
| Final video | `{artifact_root}/assembly_generation/FINAL_PUBLISH_READY.mp4` | Exists, size > 0, duration ≤ 15 s (probe optional in smoke) |
| Manifest | `{artifact_root}/assembly_generation/assembly_manifest.json` | Valid JSON; `real_assembly_executed=true`; lists inputs/outputs |

### Session slot (`assembly_generation`)

| Field | Expected |
|-------|----------|
| `status` | `completed` |
| `dry_run` | `false` |
| `executed` | `true` |
| `real_assembly_executed` | `true` |
| `output_created` | `true` |
| `validation_status` | `READY` (or post-run validation state) |
| `planned_steps` | Preserved from dry-run + execution markers appended |
| `output_summary.output_file` | Path to MP4 |
| `output_summary.output_created` | `true` |

### API response (`AssemblyRunResponse`)

| Field | Expected |
|-------|----------|
| `success` | `true` |
| `status` | `completed` |
| `real_assembly_executed` | `true` (**only** for this successful real run) |
| `output_created` | `true` |
| `video_mutated` | `false` |
| `voice_mutated` | `false` |
| `subtitle_mutated` | `false` |

### Upstream slots

`video_generation`, `voice_generation`, `subtitle_generation` — **byte-identical critical fields** (state, provider, status, started_at, completed_at, manifest paths) before vs after.

### Operations log

Append to `execution_runtime.operations.assembly_execution`:

```json
{
  "last_status": "completed",
  "real_assembly_executed": true,
  "output_created": true,
  "triggered_by": "operator_smoke_test",
  "reason": "11J-19 supervised first real FFmpeg assembly smoke test",
  "ffmpeg_version": "6.x.x",
  "duration_seconds": 12.5,
  "output_size_bytes": 1234567
}
```

---

## Post-Test Shutdown Checklist

Execute **always**, success or failure:

| Step | Action |
|------|--------|
| 1 | Set `MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED=false` (unset env) |
| 2 | Set `ASSEMBLY_RUNTIME_EXECUTION_APPROVED=false` (unset env) |
| 3 | **Keep** smoke artifacts on disk for inspection (do not auto-delete MP4) |
| 4 | Expire or reset assembly approval | `POST …/assembly/expire` or `reset-approval` |
| 5 | Verify approval state no longer allows real run | `can_run_real_assembly()` → blocked |
| 6 | Write report | `project_brain/PHASE_11J19_FIRST_REAL_FFMPEG_ASSEMBLY_SMOKE_TEST_REPORT.md` |
| 7 | Record validator results | Run 11J-19 validator one command at a time |
| 8 | Do **not** re-run smoke without new operator approval |

---

## Rollback / Shutdown Checklist (Failure Mid-Run)

| Step | Action |
|------|--------|
| 1 | Do not auto-retry FFmpeg — single attempt only in smoke |
| 2 | Set `assembly_generation.status=failed` with mapped error code |
| 3 | Preserve partial outputs in output dir (`.part`, temp concat list) for forensics |
| 4 | Set `real_assembly_executed=false`, `output_created=false` unless MP4 fully validated |
| 5 | Unset env flags (same as success shutdown) |
| 6 | Expire/reset approval |
| 7 | Upstream slots — verify unchanged |
| 8 | Append failure audit to `operations.assembly_execution` |

---

## Failure Handling

| Condition | Slot status | Code | Retry | Flags after |
|-----------|-------------|------|-------|-------------|
| FFmpeg nonzero exit | `failed` | `ASSEMBLY_FFMPEG_FAILED` | No | Disabled |
| Output missing / zero bytes | `failed` | `ASSEMBLY_OUTPUT_INVALID` | No | Disabled |
| Subprocess timeout (120 s) | `failed` | `ASSEMBLY_TIMEOUT` | No | Disabled |
| Operator cancel during run | `failed` or `cancelled` | `ASSEMBLY_CANCELLED` | No | Disabled |
| Guard block (approval/env) | no run | existing block codes | No | Disabled |
| Confirm missing | no run | `ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED` | No | N/A |
| Smoke cap exceeded | no run | `ASSEMBLY_SMOKE_CAP_EXCEEDED` | No | N/A |

**No retry loop explosion:** smoke runner exits after one attempt. Validator must assert no more than one FFmpeg invocation per smoke session (mock or invocation counter in test).

---

## Artifact Checks (Post-Run Verification)

Automated checks in `run_11j19_supervised_assembly_smoke_test.py`:

1. `FINAL_PUBLISH_READY.mp4` exists under `storage/content_brain/execution/artifacts/{session_id}/assembly_generation/`  
2. File size > 0 and ≤ `SMOKE_MAX_OUTPUT_BYTES`  
3. Optional: ffprobe duration ≤ 15 s (if ffprobe available — separate from ffmpeg binary check)  
4. `assembly_manifest.json` exists and parses  
5. Manifest `real_assembly_executed === true`  
6. Manifest `output_artifacts` includes MP4 path  
7. Session slot matches manifest  
8. Upstream slot snapshots match pre-run  
9. No unexpected files in video/voice/subtitle artifact dirs  

---

## Seed Session Design (Smoke Fixture)

Dedicated session ID: `exec_11j19_smoke_{timestamp}`

Minimal artifact layout (operator or runner creates real tiny media files):

```
artifacts/exec_11j19_smoke_YYYYMMDD_HHMMSS/
  video_generation/
    clip_001.mp4          # 3–8 s silent or test pattern
    video_manifest.json
  voice_generation/
    narration_001.mp3       # single short narration
    voice_manifest.json
  subtitle_generation/
    subtitles.ass           # burn-in preferred
    subtitle_manifest.json
  assembly_generation/      # empty before run; output after
```

Runner flow:

1. Create session + artifacts (or copy from validated fixture template)  
2. `POST /assembly/run` with `dry_run=true`  
3. `POST /assembly/approve` with `request_real_assembly=true`, short TTL  
4. Enable env flags in process only (`patch.dict(os.environ, ...)`)  
5. `POST /assembly/run` with real body above  
6. Verify + shutdown  

**No Runway/Hailuo.** Video clips are **pre-seeded local files**, not newly generated.

---

## Validation Plan (11J-19 Implementation)

**Validator:** `project_brain/validate_11j19_real_ffmpeg_assembly_smoke_test.py`

Run validators **one at a time** (nested chains timeout on Windows/PowerShell).

| # | Test | Expected |
|---|------|----------|
| 1 | Real run blocked when env flags off | `ASSEMBLY_REAL_EXECUTION_DISABLED` |
| 2 | Real run blocked without `confirm_real_assembly` | `ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED` |
| 3 | Real run blocked without category approval | `ASSEMBLY_APPROVAL_REQUIRED` |
| 4 | Real run blocked if plan not READY | `ASSEMBLY_PLAN_NOT_READY` |
| 5 | FFmpeg availability check works | Preflight returns version or clean block |
| 6 | Smoke run creates `FINAL_PUBLISH_READY.mp4` | File exists (mock FFmpeg in unit tests; real FFmpeg only in supervised manual run) |
| 7 | Output file size > 0 | PASS |
| 8 | `assembly_manifest.json` written | PASS |
| 9 | `real_assembly_executed=true` only for real run | Dry-run remains `false` |
| 10 | `output_created=true` only for successful real run | Failed run → `false` |
| 11 | Upstream slots unchanged | Deep-copy compare |
| 12 | Flags disabled after smoke helper | Env restored |
| 13 | Failure path maps error safely | Inject mock FFmpeg failure |

### Test strategy split

| Layer | FFmpeg | Purpose |
|-------|--------|---------|
| Unit / validator | **Mock** subprocess | Policy, caps, slot updates, failure codes |
| Supervised manual smoke | **Real** FFmpeg once | Operator-only `run_11j19_supervised_assembly_smoke_test.py` |

Validator must **not** invoke real FFmpeg in CI/default `python -m` run.

---

## Files Likely to Change (11J-19 — Not This Phase)

| File | Change |
|------|--------|
| `content_brain/execution/assembly_smoke_profile.py` | Smoke caps constants |
| `content_brain/execution/assembly_ffmpeg_preflight.py` | Binary discovery + version |
| `content_brain/execution/assembly_ffmpeg_executor.py` | Real subprocess branch (guarded) |
| `content_brain/execution/assembly_run_action_policy.py` | Real path + confirm + smoke caps |
| `content_brain/execution/assembly_runtime_engine.py` | Real run orchestration, manifest write |
| `content_brain/execution/failure_taxonomy.py` | New codes if missing |
| `ui/api/schemas/assembly_run.py` | `confirm_real_assembly`, `reason` |
| `project_brain/run_11j19_supervised_assembly_smoke_test.py` | Supervised CLI runner |
| `project_brain/validate_11j19_real_ffmpeg_assembly_smoke_test.py` | Validator |
| `project_brain/PHASE_11J19_*_REPORT.md` | Post-smoke report |

### Must NOT change (11J-19 smoke scope)

| Area | Reason |
|------|--------|
| Video/Voice/Subtitle runtime engines | Isolation |
| Runway/Hailuo orchestrators | Constraint |
| `full_video_pipeline.py` | Legacy forbidden |
| Assembly approval UI (11J-16) | No real-run button in smoke |
| Global env flags in repo config | Flags only in operator shell for test |

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Accidental real run in dev | **Critical** | Dual env flags + confirm + smoke CLI only; default API still dry-run |
| FFmpeg hang | **High** | 120 s timeout; kill process group |
| Partial corrupt MP4 | **Medium** | Validate size + optional probe before `output_created=true` |
| Disk fill | **Low** | Smoke caps + preflight disk check |
| Stale approval after smoke | **Medium** | Mandatory expire/reset in shutdown checklist |
| Validator timeout when chained | **Low** | Run one validator module at a time (11J-17 lesson) |

---

## Confirmation Checklist (Design Phase)

| Requirement | Design status |
|-------------|---------------|
| Smoke purpose defined | Yes |
| Strict limits documented | Yes |
| Preconditions checklist | Yes |
| Request body specified | Yes |
| Expected success behavior | Yes |
| Failure handling | Yes |
| Rollback/shutdown checklist | Yes |
| Artifact checks | Yes |
| 11J-19 validation plan | Yes |
| Explicit approval boundary | Yes — **11J-18 does not authorize FFmpeg** |
| No implementation in 11J-18 | Yes |

---

## Next Recommended Phase

**PHASE 11J-19 — Real FFmpeg Assembly Smoke Test Implementation**

Requires **separate explicit operator approval** before any FFmpeg command runs.

Deliverables:

1. Extend policy + executor (real branch behind all gates)  
2. FFmpeg preflight module  
3. Supervised CLI runner (mirror 11H-2e)  
4. Mock-based validator (13 tests)  
5. Post-smoke report template  
6. **One** manual supervised smoke run with real FFmpeg — operator-initiated only  

**Do not enable real assembly in UI or global config in 11J-19.**

---

## Files Analyzed

| File | Relevance |
|------|-----------|
| `assembly_approval_guard.py` | `can_run_real_assembly()` env + approval gates |
| `assembly_run_action_policy.py` | Current fail-closed `dry_run=false` |
| `assembly_ffmpeg_executor.py` | Dry-run only; real branch stub |
| `assembly_runtime_engine.py` | Orchestration target |
| `assembly_models.py` | `EXPECTED_OUTPUT`, manifest skeleton |
| `ui/api/schemas/assembly_run.py` | Request/response extension point |
| `run_11h2e_supervised_smoke_test.py` | Supervised smoke pattern |
| `PHASE_11J17_PRE_REAL_ASSEMBLY_FINAL_SAFETY_REVIEW.md` | Readiness + gaps |

**No files modified in Phase 11J-18.**
