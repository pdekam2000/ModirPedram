# Phase 11J-17 — Pre-Real Assembly Final Safety Review

**Status:** Review only — no FFmpeg, no real assembly execution, no code changes  
**Date:** 2026-06-01  
**Scope:** Assembly Runtime stack 11J-2 through 11J-16  
**Recommendation:** **Proceed to PHASE 11J-18 — Real FFmpeg Smoke Test Design** (design only; no implementation)

---

## Executive Summary

The Assembly Runtime stack is **correctly fail-closed** for real FFmpeg execution. All approval and UI paths are metadata-only. Dry-run planning, observability, guard, write APIs, and UI controls are complete and validated. **No blocking issues** were found that would prevent moving to a **smoke-test design** phase.

Real FFmpeg execution remains **not implemented** and **must not be enabled** until a future gated phase after 11J-18 design review.

**Readiness score: 82 / 100** (metadata + safety layer ready; real executor layer intentionally absent)

---

## Checklist Results

### 1. Real assembly isolation

| Check | Result | Evidence |
|-------|--------|----------|
| No UI control runs real assembly | **PASS** | `assemblyApprovalClient.ts` calls only `/assembly/approve\|reject\|expire\|reset-approval`. No `/assembly/run` client in UI. Validator 11J-16: no `dry_run: false`. |
| Approval endpoints do not run FFmpeg | **PASS** | `assembly_approval_operations_engine.py` docstring + AST scan (11J-14): no FFmpeg/subprocess. Mutates `assembly_generation.approval` only. |
| `/assembly/run` with `dry_run=false` blocked | **PASS** | `assembly_run_action_policy.py` fail-closed → `ASSEMBLY_REAL_EXECUTION_DISABLED`. 11J-8 test `dry_run_false_blocked`. |
| `AssemblyFFmpegExecutor` default dry-run | **PASS** | `__init__(..., dry_run=True)`; `assembly_runtime_engine.py` uses `AssemblyFFmpegExecutor(dry_run=True)` and passes `dry_run=True` to execute. |
| Real execution requires future flags | **PASS** | `can_run_real_assembly()` requires `MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED=true` AND `ASSEMBLY_RUNTIME_EXECUTION_APPROVED=true` (both default off). Plus category approval + plan READY. |

### 2. Approval safety

| Check | Result | Evidence |
|-------|--------|----------|
| Category-scoped assembly approval | **PASS** | `assembly_generation.approval` + `operations.assembly_approval_audit[]` |
| Session approval ≠ assembly approval | **PASS** | Session `approval_decision` untouched by 11J-14 engine; no cross-writes |
| Voice approval ≠ assembly approval | **PASS** | Separate slots, APIs, UI panels; 11J-14 upstream immutability tests |
| Subtitle status ≠ assembly approval | **PASS** | Approve policy does not read subtitle `approval_state` |
| Expired/rejected/reset blocks execution | **PASS** | `can_run_real_assembly()` adds `ASSEMBLY_APPROVAL_EXPIRED` / `ASSEMBLY_APPROVAL_REJECTED`; guard tests in 11J-12 |
| Audit trail for all actions | **PASS** | 11J-14 test `audit_trail_appended_for_every_action`; event types `assembly_approval_*` |
| UI asserts `real_assembly_executed === false` | **PASS** | `assertAssemblyApprovalSafety()` in client; pre-check before success path |

### 3. FFmpeg safety

| Check | Result | Evidence |
|-------|--------|----------|
| No FFmpeg outside future executor | **PASS** | `assembly_ffmpeg_executor.py`: real branch returns `ASSEMBLY_REAL_EXECUTION_DISABLED` without subprocess |
| No FFmpeg in UI/API approval paths | **PASS** | 11J-14 AST scan; 11J-16 `no_ffmpeg_control_labels` |
| No `full_video_pipeline.py` import | **PASS** | 11J-2, 11J-6, 11J-8 validators grep clean |
| No `FINAL_PUBLISH_READY.mp4` from runtime path | **PASS** | Executor sets `output_created=False`, `output_file=None` on dry-run; 11J-8/11J-14 temp-dir checks |

### 4. Upstream immutability

| Check | Result | Evidence |
|-------|--------|----------|
| `video_generation` unchanged by approval | **PASS** | 11J-14 test + engine `_upstream_slots_preserved` |
| `voice_generation` unchanged | **PASS** | 11J-14 test |
| `subtitle_generation` unchanged | **PASS** | 11J-14 test |
| `assembly_generation` owns its state | **PASS** | Engine persists only assembly slot + operations mirror |

### 5. UI safety

| Check | Result | Evidence |
|-------|--------|----------|
| Forbidden labels absent on buttons | **PASS** | 11J-16 grep: no Run Assembly / Generate Final Video / Export / Run FFmpeg / Create MP4 / Build Final |
| Exact approve warning present | **PASS** | `ASSEMBLY_APPROVE_SAFETY_WARNING` in `assemblyApprovalLabels.ts` + modal |
| Dry-run safety copy in panel | **PASS** | `ASSEMBLY_SAFETY_COPY` in observability panel |
| Expected output labeled preview-only | **PASS** | `ASSEMBLY_EXPECTED_OUTPUT_LABEL = "Expected Output Only"` |

### 6. Data readiness

| Check | Result | Evidence |
|-------|--------|----------|
| AssemblyPlan READY path | **PASS** | 11J-4 validator 16/16; 11J-8 dry-run succeeds with READY plan |
| Dry-run completed path | **PASS** | 11J-8 slot `status=completed`, `dry_run=true`, `planned_steps≥5` |
| `expected_output` preview only | **PASS** | Panel section "Expected output (not generated)"; `isGeneratedOutput` false |
| Planned steps visible | **PASS** | 11J-10 observability tests |
| Input summaries visible | **PASS** | KV grid `input_summary` in panel |
| No false "complete" generated output | **PASS** | `output_created=false`, `real_assembly_executed=false` enforced in API responses |

### 7. Pre-real execution gaps (assessment)

| Gap | Status | Notes |
|-----|--------|-------|
| Real FFmpeg executor implementation | **Missing** | `dry_run=False` path fail-closed by design |
| FFmpeg binary availability check | **Missing** | `ffmpeg_path` stored but unused in 11J-6 |
| Real output validation (size, duration, probe) | **Missing** | No ffprobe integration |
| Temporary file cleanup policy | **Missing** | Not defined for real concat/burn-in |
| Timeout handling during FFmpeg | **Missing** | No subprocess timeout wiring |
| Cancellation during FFmpeg | **Missing** | Operations cancel not wired to executor |
| Codec/concat fallback strategy | **Missing** | Planned steps only; no runtime fallback |
| First smoke test plan | **Missing** | Target of 11J-18 design |

---

## Validator Results

Executed during this review (2026-06-01):

| Validator | Result | Notes |
|-----------|--------|-------|
| `validate_11j16_assembly_approval_ui_controls` | **17/17 PASS** | Includes npm build + regressions |
| `validate_11j14_assembly_approval_write_apis` | **17/17 PASS** | |
| `validate_11j12_assembly_approval_guard` | **14/14 PASS** | `include_regressions=False` (core matrix) |
| `validate_11j10_assembly_ui_observability` | **20/20 PASS** | `include_regressions=False` |
| `validate_11j8_assembly_runtime_api` | **18/18 PASS** | `include_regressions=False` |
| `validate_11j6_assembly_ffmpeg_executor_dry_run` | **13/13 PASS** | `include_regressions=False` |
| `validate_11j4_assembly_plan_builder` | **16/16 PASS** | `include_regressions=False` |
| `validate_11j2_assembly_runtime_foundation` | **16/16 PASS** | Full module (~12 min nested regressions) |
| `validate_11i8_subtitle_runtime_execution_api` | **19/19 PASS** | Full module on re-run (first run 18/19 flaky nested 11I-2) |
| `validate_11h2d_live_engine_wiring_no_real_execution` | **17/17 PASS** | |
| `npm run build` | **PASS** | TypeScript + Vite production build |

**Note:** Full-module runs of 11J-12 (includes `npm run build` in guard validator) and nested regression chains can exceed 10 minutes. Core assembly tests all pass independently.

---

## Blocking Issues

**None** for proceeding to **11J-18 Real FFmpeg Smoke Test Design**.

No code changes required before design phase. Real execution must remain disabled.

---

## Non-Blocking Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Operator confuses approve with “video is ready” | Medium | UI warning + `assembly_eligible` may still be false when env flags off — document in 11J-18 runbook |
| Nested validator flakiness (11I-8 → 11I-2) | Low | Re-run; unrelated to assembly isolation |
| Approval TTL expiry not re-evaluated client-side until refresh | Low | Refresh after actions already wired |
| `can_run_real_assembly()` not yet wired into `/assembly/run` for `dry_run=false` | Medium | Required before any real run enablement (11J-19+ implementation) |
| No FFmpeg binary preflight | High for real phase | Must be in 11J-18+ design |
| Plan fingerprint stale after upstream artifact change post-approve | Medium | Future `assembly_approval_stale` invalidation (design polish) |

---

## Confirmations

| Statement | Confirmed |
|-----------|-----------|
| No FFmpeg execution exists in current assembly path | **Yes** |
| No `FINAL_PUBLISH_READY.mp4` generated by Runtime assembly | **Yes** |
| Env flags default off | **Yes** (`MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED`, `ASSEMBLY_RUNTIME_EXECUTION_APPROVED`) |
| Video/Voice/Subtitle runtimes unchanged | **Yes** |
| Runway/Hailuo untouched | **Yes** |

---

## Readiness Score: **82 / 100**

| Layer | Score contribution |
|-------|-------------------|
| Foundation + plan builder (11J-2–4) | 15/15 |
| Dry-run executor + API (11J-6–8) | 15/15 |
| UI observability (11J-10) | 10/10 |
| Approval guard (11J-12) | 12/12 |
| Approval write APIs (11J-14) | 12/12 |
| Approval UI controls (11J-16) | 10/10 |
| Real FFmpeg execution layer | **0/20** (intentionally absent) |
| Operational hardening (timeout, cancel, cleanup, probe) | **8/16** (partial via dry-run + policy only) |

The score reflects **readiness for smoke-test design**, not readiness for production real assembly.

---

## Recommendation

### Proceed to **PHASE 11J-18 — Real FFmpeg Smoke Test Design**

**Do not** start real FFmpeg implementation in 11J-18. The next phase should produce:

1. Minimal smoke test scope (single session, 2 clips, 2 narration, 1 subtitle)
2. Explicit env flag + approval + guard gate sequence
3. FFmpeg binary discovery and version policy
4. Output validation criteria (file exists, non-zero size, optional ffprobe)
5. Temp workspace + cleanup rules
6. Timeout and cancel behavior spec
7. Rollback / fail-closed defaults
8. Validator plan for first real execution (isolated, operator-triggered, capped)

**Do not fix blockers first** — there are no assembly-safety blockers. Address operational gaps in 11J-18 design before any 11J-19+ implementation.

---

## Architecture Snapshot (Current)

```
Upstream (video / voice / subtitle) — read-only inputs
        ↓
AssemblyPlanBuilder → READY plan
        ↓
POST /assembly/run (dry_run=true only) → AssemblyFFmpegExecutor (dry-run)
        ↓
Assembly approval UI → POST /assembly/approve|reject|expire|reset (metadata only)
        ↓
can_run_real_assembly() — read-only guard (env flags OFF by default)
        ↓
[FUTURE 11J-19+] Real FFmpeg — NOT IMPLEMENTED
```

---

## Files Reviewed (Representative)

| Area | Files |
|------|-------|
| Guard | `assembly_approval_guard.py` |
| Policy | `assembly_approval_action_policy.py`, `assembly_run_action_policy.py` |
| Engine | `assembly_approval_operations_engine.py`, `assembly_runtime_engine.py`, `assembly_ffmpeg_executor.py` |
| API | `ui/api/main.py` (assembly routes), `ui/api/schemas/assembly_approval.py` |
| UI | `AssemblyApprovalControlsPanel.tsx`, `assemblyApprovalClient.ts`, `AssemblyRuntimeObservabilityPanel.tsx` |
| Validators | `validate_11j2` through `validate_11j16` |

**No files modified in this review phase.**
