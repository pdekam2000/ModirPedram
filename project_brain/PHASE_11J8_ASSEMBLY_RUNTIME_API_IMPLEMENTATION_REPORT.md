# PHASE 11J-8 — Assembly Runtime API Implementation (Dry-Run Only)

## Summary

Implemented the public assembly execution endpoint
`POST /sessions/{session_id}/assembly/run` on top of the existing
`AssemblyPlanBuilder` and `AssemblyFFmpegExecutor` (dry-run path only). The
endpoint plans the final-video assembly, updates **only** the
`assembly_generation` slot, and is **fail-closed**: any request with
`dry_run=false` is rejected with `ASSEMBLY_REAL_EXECUTION_DISABLED` before any
executor work is performed.

No FFmpeg is imported or invoked, no `FINAL_PUBLISH_READY.mp4` is produced, and
the Video / Voice / Subtitle runtime slots are never mutated.

## Files Created

| File | Responsibility |
| --- | --- |
| `content_brain/execution/assembly_run_action_policy.py` | Pure eligibility policy: session exists, not archived, not cancelled, assembly slot present, no active run, plan READY, and fail-closed `dry_run=false` block. Returns a structured `AssemblyRunPolicyResult`. |
| `content_brain/execution/assembly_runtime_engine.py` | Orchestrates the dry-run lifecycle: builds the `AssemblyPlan`, applies the policy, calls `AssemblyFFmpegExecutor(dry_run=True)`, writes the `assembly_generation` slot, and computes upstream-mutation flags. |
| `ui/api/assembly_run_service.py` | Thin service wrapper: invokes the engine and returns a response payload (`api_version` stamped). |
| `ui/api/schemas/assembly_run.py` | `AssemblyRunRequest` / `AssemblyRunResponse` Pydantic models with hard safety invariants. |
| `project_brain/validate_11j8_assembly_runtime_api.py` | 21-test validation matrix (18 functional + 4 regression; one functional check is an extra `no_final_video_created` guard). |
| `project_brain/PHASE_11J8_ASSEMBLY_RUNTIME_API_IMPLEMENTATION_REPORT.md` | This report. |

## Files Modified

| File | Change |
| --- | --- |
| `content_brain/execution/failure_taxonomy.py` | Registered `ASSEMBLY_SLOT_MISSING`, `ASSEMBLY_RUN_ACTIVE`, and `ASSEMBLY_SESSION_ARCHIVED` failure codes (additive only). |
| `ui/api/dependencies.py` | Added `get_assembly_run_service()` (lazy import, mirrors subtitle/voice wiring). |
| `ui/api/main.py` | Imported the new schemas/service/dependency; added `_assembly_run_response()` helper and the `POST /sessions/{session_id}/assembly/run` route. |

## Endpoint Added

```
POST /sessions/{session_id}/assembly/run
```

Request body (`AssemblyRunRequest`):

| Field | Default |
| --- | --- |
| `dry_run` | `true` |
| `overwrite` | `false` |
| `timeout_seconds` | `120` |
| `triggered_by` | `"operator"` |

Response body (`AssemblyRunResponse`) includes `session_id`, `status`,
`assembly_slot`, `validation_status`, `planned_steps`, `expected_output`,
`output_created`, `real_assembly_executed`, `warnings`, `errors`,
`video_mutated`, `voice_mutated`, `subtitle_mutated`. Hard invariants for this
phase: `output_created=false`, `real_assembly_executed=false`,
`video_mutated=false`, `voice_mutated=false`, `subtitle_mutated=false`.

Non-success results return HTTP `409` with the same DTO shape (consistent with
the subtitle run endpoint).

## Dry-Run Lifecycle Behavior

1. **Load** the session via `ExecutionSessionStore` and normalize the
   multi-category shell (idempotent — upstream slots unchanged).
2. **Snapshot** the video / voice / subtitle slots for mutation detection.
3. **Build** the `AssemblyPlan` (read-only) via `AssemblyPlanBuilder`.
4. **Policy** — `evaluate_assembly_run_request`:
   - session exists / not archived / not cancelled,
   - `assembly_generation` slot exists,
   - no active assembly run (`running`/`in_progress`/`started`),
   - **fail-closed**: `dry_run=false` → `ASSEMBLY_REAL_EXECUTION_DISABLED`,
   - `AssemblyPlan.validation_status == READY`.
   On rejection, the slot is marked `failed`/`cancelled`, the session is saved,
   and the executor is never called.
5. **Run** — the `assembly_generation` slot is set to `running` and persisted,
   then `AssemblyFFmpegExecutor(dry_run=True).execute(plan, ...)` is invoked with
   a cooperative `cancel_check`.
6. **Finalize** — the slot is updated with `validation_status`, `assembly_mode`,
   `subtitle_mode`, `planned_steps`, `expected_output`, `input_summary`,
   `output_summary`, `warnings`, `errors`, and the hard flags
   `executed=false`, `dry_run=true`, `real_assembly_executed=false`,
   `output_created=false`. Status becomes `completed` on a successful dry-run.

Only the `assembly_generation` slot (and its `assembly` alias) plus the
`operations.assembly_execution` summary are written; the upstream slots are
re-written verbatim from their pre-run values.

## Validation Results

Command:

```
python -m project_brain.validate_11j8_assembly_runtime_api
```

Full run (functional + regressions): **22 / 22 PASS** (exit code 0,
elapsed ≈ 68 min — the nested regression chain re-runs prior validators).
Functional subset (regressions excluded): **18 / 18 PASS**.

| # | Test | Result |
| --- | --- | --- |
| 1 | `dry_run_succeeds` | PASS |
| 2 | `assembly_plan_built` | PASS |
| 3 | `executor_dry_run_invoked` | PASS |
| 4 | `planned_steps_returned` | PASS |
| 5 | `expected_output_returned` | PASS |
| 6 | `output_created_false` | PASS |
| 7 | `real_assembly_executed_false` | PASS |
| 8 | `assembly_slot_updated` | PASS |
| 9 | `dry_run_false_blocked` | PASS |
| 10 | `video_mutated_false` | PASS |
| 11 | `voice_mutated_false` | PASS |
| 12 | `subtitle_mutated_false` | PASS |
| 13 | `video_slot_unchanged` | PASS |
| 14 | `voice_slot_unchanged` | PASS |
| 15 | `subtitle_slot_unchanged` | PASS |
| 16 | `no_ffmpeg_import_or_call` | PASS |
| 17 | `no_full_video_pipeline_import` | PASS |
| (extra) | `no_final_video_created` | PASS |

Regression validators (full run, `python -m ...`):

| Validator | Result |
| --- | --- |
| `validate_11j6_assembly_ffmpeg_executor_dry_run` | PASS |
| `validate_11j4_assembly_plan_builder` | PASS |
| `validate_11i8_subtitle_runtime_execution_api` | PASS |
| `validate_11h2d_live_engine_wiring_no_real_execution` | PASS |

> The full regression chain re-runs deeply nested prior validators and is slow
> (≈68 min end-to-end); the run completed with `22/22 PASS` and exit code 0.

## Safety Confirmations

- **No FFmpeg**: none of the new modules import the `ffmpeg` library or
  `subprocess`, and none contain ffmpeg/ffprobe command literals. The engine
  imports the internal `assembly_ffmpeg_executor` dry-run module, which itself
  never invokes FFmpeg (verified by the 11J-6 validator). Confirmed via AST scan
  (test `no_ffmpeg_import_or_call`).
- **No `FINAL_PUBLISH_READY.mp4`**: the dry-run path creates no output file;
  the validator asserts the expected output path does not exist
  (`no_final_video_created`).
- **Upstream slots unchanged**: video / voice / subtitle slots are deep-compared
  before/after on disk and via the response `*_mutated` flags — all `false`.
- **No legacy pipeline**: no module imports `full_video_pipeline`
  (test `no_full_video_pipeline_import`).
- **Fail-closed**: `dry_run=false` returns `ASSEMBLY_REAL_EXECUTION_DISABLED`
  with `real_assembly_executed=false` and `output_created=false`, and no
  executor/FFmpeg work is performed.

## Next Recommended Phase

**PHASE 11J-9 — Assembly Runtime UI Observability Design** (surface the
`assembly_generation` slot, planned steps, validation status, and dry-run state
in the Runtime Studio, read-only).
