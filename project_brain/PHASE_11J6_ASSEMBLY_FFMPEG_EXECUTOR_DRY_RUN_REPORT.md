# Phase 11J-6 — Assembly FFmpeg Executor Foundation / Dry-Run Implementation Report

**Status:** Implemented — **dry-run only** (no FFmpeg, no `FINAL_PUBLISH_READY.mp4`, real execution fail-closed)
**Date:** 2026-05-31
**Prerequisites:** 11J-2 (foundation), 11J-4 (plan builder), 11J-5 (executor design)
**Next phase:** **11J-7 — Assembly Runtime API Design / Dry-Run Execution**

---

## Executive Summary

Phase 11J-6 implements the **`AssemblyFFmpegExecutor` foundation in dry-run mode**.
It consumes a validated `AssemblyPlan`, validates the execution contract, previews
the FFmpeg step plan, applies the failure taxonomy, exposes a cooperative
cancellation hook, and plans the output path — **without invoking FFmpeg and without
creating any media**.

Real execution (`dry_run=False`) is intentionally **fail-closed** with
`ASSEMBLY_REAL_EXECUTION_DISABLED`; actual FFmpeg is deferred to 11J-7.

The executor never reads the session and never touches upstream slots — it only sees
the plan, so `video_generation` / `voice_generation` / `subtitle_generation` are
structurally untouched.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/assembly_ffmpeg_executor.py` | `AssemblyExecutionResult` + `AssemblyFFmpegExecutor.execute(...)` (dry-run) |
| `project_brain/validate_11j6_assembly_ffmpeg_executor_dry_run.py` | 17-test validator (13 dry-run + 4 regressions) |
| `project_brain/PHASE_11J6_ASSEMBLY_FFMPEG_EXECUTOR_DRY_RUN_REPORT.md` | This report |

## Files Modified

| File | Change (additive only) |
|------|------------------------|
| `content_brain/execution/failure_taxonomy.py` | Registered 10 assembly failure codes (see below) |

---

## Executor Contract

```python
class AssemblyFFmpegExecutor:
    def __init__(self, ffmpeg_path: str | None = None, *, dry_run: bool = True) -> None: ...

    def execute(
        self,
        plan: AssemblyPlan,
        *,
        cancel_check: Callable[[], bool] | None = None,
        overwrite: bool = False,
        timeout_seconds: int = 120,
        dry_run: bool = True,
    ) -> AssemblyExecutionResult: ...
```

Execution order:

1. **Contract validation** — require an `AssemblyPlan` with `validation_status == READY`, else `ASSEMBLY_PLAN_INVALID`.
2. **Cooperative cancellation** — if `cancel_check()` is truthy before any work → `ASSEMBLY_CANCELLED`.
3. **Input re-check** — video clips / narration must exist on disk (`ASSEMBLY_VIDEO_MISSING` / `ASSEMBLY_AUDIO_MISSING`); VTT-only burn-in rejected (`ASSEMBLY_SUBTITLE_INVALID`).
4. **Step preview** — build planned FFmpeg steps (validate → concat → audio merge → subtitle → export → output validation).
5. **Branch** — `dry_run=True` → structured preview result; `dry_run=False` → `ASSEMBLY_REAL_EXECUTION_DISABLED` (fail closed).

`ffmpeg_path` is stored for future real execution but **never used** in 11J-6.

### `AssemblyExecutionResult` fields

`session_id`, `status` (`dry_run` / `failed` / `cancelled`), `expected_output`,
`output_file`, `output_created`, `output_size`, `duration_seconds`,
`execution_time_seconds`, `validation_status`, `input_counts`, `planned_steps`,
`real_assembly_executed`, `warnings`, `errors`, `executor_version`, `generated_at`
(+ `to_dict()`).

---

## Dry-Run Behavior

- Requires a READY plan; returns `status="dry_run"`.
- Returns `planned_steps` (6 steps): `validate_inputs`, `video_concat`,
  `audio_merge`, `subtitle_handling`, `export`, `output_validation`.
- `input_counts` = `{video, voice, subtitle}` counts.
- `expected_output = FINAL_PUBLISH_READY.mp4`; output path planned under
  `storage/content_brain/execution/artifacts/{session_id}/assembly_generation/`.
- **No file created**, `real_assembly_executed=false`, `output_created=false`.
- Reserved-but-unsupported V1 features (music layer, non-primary `output_variant`)
  surface as warnings and are ignored.
- `dry_run=False` → fail closed with `ASSEMBLY_REAL_EXECUTION_DISABLED`; still no
  FFmpeg, no output.

---

## Failure Codes Added (`failure_taxonomy.py`)

| Code | Category | Retriable |
|------|----------|-----------|
| `ASSEMBLY_PLAN_INVALID` | PREFLIGHT_REJECT | false |
| `ASSEMBLY_VIDEO_MISSING` | ARTIFACT_REJECT | false |
| `ASSEMBLY_AUDIO_MISSING` | ARTIFACT_REJECT | false |
| `ASSEMBLY_SUBTITLE_INVALID` | ARTIFACT_REJECT | false |
| `ASSEMBLY_FFMPEG_FAILED` | RUNTIME_ERROR | true |
| `ASSEMBLY_OUTPUT_INVALID` | ARTIFACT_REJECT | true |
| `ASSEMBLY_OUTPUT_MISSING` | ARTIFACT_REJECT | true |
| `ASSEMBLY_CANCELLED` | OPERATIONS | false |
| `ASSEMBLY_TIMEOUT` | RUNTIME_ERROR | true |
| `ASSEMBLY_REAL_EXECUTION_DISABLED` | DISPATCH_REJECT | false |

---

## Validation Results

Command:

```
python -m project_brain.validate_11j6_assembly_ffmpeg_executor_dry_run
```

| # | Test | Result |
|---|------|--------|
| 1 | Dry-run accepts READY plan | PASS |
| 2 | Dry-run returns planned steps | PASS |
| 3 | Dry-run does not create `FINAL_PUBLISH_READY.mp4` | PASS |
| 4 | `real_assembly_executed=false` | PASS |
| 5 | `output_created=false` | PASS |
| 6 | `dry_run=False` → `ASSEMBLY_REAL_EXECUTION_DISABLED` | PASS |
| 7 | Invalid plan → `ASSEMBLY_PLAN_INVALID` | PASS |
| 8 | Missing video fails/blocks safely | PASS |
| 9 | Cancellation before execution → `ASSEMBLY_CANCELLED` | PASS |
| 10 | Expected output under `assembly_generation` artifact dir | PASS |
| 11 | No FFmpeg/subprocess import or call | PASS |
| 12 | No `full_video_pipeline` import | PASS |
| 13 | Upstream slots not mutated | PASS |
| 14 | Existing 11J-4 validator still passes | PASS |
| 15 | Existing 11J-2 validator still passes | PASS |
| 16 | Existing 11I-8 validator still passes | PASS |
| 17 | Existing 11H-2d validator still passes | PASS |

Dry-run tests (1–13) verified directly: **13/13 PASS**.

Regression commands (all PASS):

```
python -m project_brain.validate_11j4_assembly_plan_builder
python -m project_brain.validate_11j2_assembly_runtime_foundation
python -m project_brain.validate_11i8_subtitle_runtime_execution_api
python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution
```

> Note: the nested regression chain (11J-6 → 11J-4 → 11J-2 → 11I-8 → …) spawns
> deeply nested validator subprocesses, so the full `validate_11j6` run takes many
> minutes. This is pre-existing behavior, unchanged by this phase.

---

## Safety Confirmations

- **No FFmpeg.** The executor imports no ffmpeg module and no `subprocess`; AST +
  literal scan enforced by test 11. `ffmpeg_path` is stored but never invoked.
- **No `FINAL_PUBLISH_READY.mp4`.** Dry-run and the fail-closed real branch both
  create nothing; test 3 confirms the planned output path does not exist.
- **No subtitle burning / media processing.** Only `Path.is_file()` existence checks.
- **Upstream slots unchanged.** The executor receives only the plan (never the
  session); deep-copy comparison confirms video/voice/subtitle slots are untouched
  (test 13).
- **No legacy pipeline.** `full_video_pipeline` not imported (test 12); no legacy
  orchestrator called.
- **Real execution disabled.** `dry_run=False` returns
  `ASSEMBLY_REAL_EXECUTION_DISABLED` — FFmpeg remains entirely deferred to 11J-7.
- **No Runway/Hailuo changes.**

---

## Next Phase

**PHASE 11J-7 — Assembly Runtime API Design / Dry-Run Execution**

Design the `AssemblyRuntimeEngine` orchestration + `assembly_run_action_policy`
guard + `POST /assembly/run` API that drives the dry-run executor and persists the
`assembly_generation` slot lifecycle (still no real FFmpeg until explicitly enabled).
