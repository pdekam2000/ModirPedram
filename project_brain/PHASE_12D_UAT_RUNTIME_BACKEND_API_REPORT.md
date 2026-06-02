# Phase 12D — UAT Runtime Backend API Implementation Report

**Status:** PASS — **18/18 core** (`validate_12d_uat_runtime_backend_api --core-only`)  
**Date:** 2026-06-01  
**Prerequisites:** Phase 12B CLI runner; Phase 12C UI wizard design  
**Next phase:** **PHASE 12E — UAT Runtime UI Wizard Implementation**

---

## Summary

Phase 12D extracts the supervised UAT pipeline into a shared **`UATRuntimeEngine`**, refactors the 12B CLI runner into a thin wrapper, and exposes three FastAPI endpoints for the Execution Center wizard (12E):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/uat/run` | Start one async UAT job (202 Accepted) |
| `GET` | `/uat/status/{session_id}` | Poll progress / terminal state |
| `POST` | `/uat/review/{session_id}` | Persist human review JSON (201 Created) |

All existing safety gates are preserved: one active run at a time, voice/assembly approval + scoped env flags, no batch mode, no auto-publish, no `full_video_pipeline` import.

---

## Files Created

| File | Role |
|------|------|
| `content_brain/execution/uat_runtime_engine.py` | Shared pipeline + `UATRuntimeEngine` (sync CLI + async API) |
| `ui/api/schemas/uat_runtime.py` | Pydantic request/response models |
| `ui/api/uat_runtime_service.py` | Service layer + error mapping |
| `project_brain/validate_12d_uat_runtime_backend_api.py` | Phase 12D validator (18 core tests) |

## Files Modified

| File | Change |
|------|--------|
| `project_brain/run_12b_uat_supervised_pipeline.py` | Thin CLI wrapper — delegates to `UATRuntimeEngine.run_sync()` |
| `ui/api/main.py` | Mount `/uat/*` routes |
| `ui/api/dependencies.py` | `get_uat_runtime_service()` |

---

## Architecture

```
CLI (12B)                    API (12D)
    │                            │
    └──────────┬─────────────────┘
               ▼
    UATRuntimeEngine
    ├── run_sync()     ← CLI + tests
    ├── start()        ← POST /uat/run (background thread)
    ├── get_status()   ← GET /uat/status/{id}
    └── submit_review()← POST /uat/review/{id}
               │
               ▼
    run_uat_pipeline()  (stage orchestration)
    ├── content_brain
    ├── video (mock when provider=mock)
    ├── voice (mock / gated live)
    ├── subtitle
    └── assembly (real gated / mock fallback for dry_run_only)
```

### Progress persistence

Run state is written to `execution_runtime.operations.uat_run`:

- `status`, `current_stage`, `stages`, `progress_log[]`
- `artifact_folder`, `final_video_path`, `report_path`, `review_template_path`
- `warnings[]`, `errors[]`

### One-active-run lock

Class-level lock on `UATRuntimeEngine._active_session_id`. Second start returns **409** (`UAT_RUN_ALREADY_ACTIVE`).

### Dry-run assembly (UI `dry_run_only`)

When `confirm_real_assembly=false`, the engine uses `allow_mock_assembly_fallback=True` (API path) to produce a stub `FINAL_PUBLISH_READY.mp4` after assembly dry-run — matching 12C wizard mapping. Direct `_run_assembly_stage` calls without this flag still fail closed (12B validator preserved).

---

## Validation Results

### Primary sign-off — 12D

```
python -m project_brain.validate_12d_uat_runtime_backend_api --core-only
```

**18/18 PASS — ACCEPTED**

### Individual regressions (run separately, core-only)

| Validator | Result |
|-----------|--------|
| `validate_12b_uat_supervised_pipeline --core-only` | **13/13 PASS** |
| `validate_11j19_supervised_assembly_smoke_test --core-only` | **13/13 PASS** |
| `validate_11h2d_live_engine_wiring_no_real_execution --core-only` | **14/14 PASS** (per accepted baseline) |

Nested regression chains were **not** invoked inside 12D (validation policy).

---

## Safety Checklist

| Constraint | Status |
|------------|--------|
| One UAT run at a time | Enforced (`UatRunAlreadyActiveError` → HTTP 409) |
| Real voice requires `confirm_real_voice` + approval + env flag | Unchanged (12B gates) |
| Real assembly requires `confirm_real_assembly` + approval + env flag | Unchanged (12B gates) |
| Flags cleared in `finally` blocks | Unchanged |
| No batch mode | No loop / batch endpoints |
| No auto-publish | No publish/upload paths |
| No `full_video_pipeline` import | Verified by validator AST scan |

---

## API Examples

### Start run

```http
POST /uat/run
Content-Type: application/json

{
  "topic": "Cat in the streets of Los Angeles",
  "platform": "youtube_shorts",
  "duration_seconds": 45,
  "video_provider": "mock",
  "voice_provider": "mock",
  "confirm_real_voice": false,
  "confirm_real_assembly": false
}
```

→ **202** with `session_id`, `status: running`, `api_version: 12d_v1`

### Poll status

```http
GET /uat/status/exec_uat_20260601_192619
```

→ **200** with `stages`, `progress_log`, paths when complete

### Submit review

```http
POST /uat/review/{session_id}
```

→ **201** writes `project_brain/user_acceptance_reviews/{session_id}_review.json`  
Duplicate submit → **409** (`UAT_REVIEW_ALREADY_SUBMITTED`)

---

## Next Phase — 12E

Implement the Execution Center **UAT Runtime** wizard tab per [PHASE_12C_UAT_RUNTIME_UI_WIZARD_DESIGN.md](./PHASE_12C_UAT_RUNTIME_UI_WIZARD_DESIGN.md):

- 5-step wizard (Topic → Providers → Safety → Run & Monitor → Review)
- Poll `GET /uat/status/{session_id}` every 2–3 s
- Submit review via `POST /uat/review/{session_id}`
- Optional backlog: artifact video preview route, `/uat/active`, cooperative cancel
