# Phase 10I — Provider Runtime Implementation Report

Generated: 2026-05-30

## Summary

Phase 10I adds **ProviderRuntimeEngine** — dispatch of **DEQUEUED** sessions to existing video provider infrastructure (`VideoProviderRouter` + Hailuo/Runway orchestrators). Scope is **video_generation only**; voice/music/image/publishing categories are registered as future slots.

API version bumped to **0.4.0**.

## New Modules

| Module | Responsibility |
|--------|----------------|
| `content_brain/execution/provider_categories.py` | Category constants, aliases, default runtime slots |
| `content_brain/execution/queue_integrity_validator.py` | DEQUEUED state + queue fingerprint + readiness checks |
| `content_brain/execution/session_prompt_adapter.py` | `brief_snapshot` → `prompts[]` via `schema_director_shots` |
| `content_brain/execution/provider_runtime_engine.py` | Dispatch lifecycle: DISPATCHED → RUNNING → COMPLETED \| FAILED |
| `content_brain/execution/seed_runtime_demo_sessions.py` | Dry-run demo seeds (skip provider execution) |
| `ui/api/services/runtime_service.py` | API wrapper for dispatch + status |
| `ui/api/schemas/runtime.py` | Dispatch/status DTOs |

## Extended Modules

| Module | Change |
|--------|--------|
| `content_brain/execution/session_store.py` | `artifact_dir()`, `append_global_provider_audit()`, provider timeline events |
| `core/video_provider_router.py` | `provider_override` param on `generate_clips()` |
| `ui/api/main.py` | `POST /sessions/{id}/runtime/dispatch`, `GET /sessions/{id}/runtime/status` |
| `ui/api/services/panel_extractor.py` | `extract_provider_runtime()` |
| `ui/api/schemas/panels.py` | `ProviderRuntimePanel`, overview runtime counts |
| `ui/web` | Provider Runtime drawer panel, status filters (DISPATCHED/RUNNING/COMPLETED) |

## Lifecycle

```
DEQUEUED → DISPATCHED → RUNNING → COMPLETED | FAILED
```

Reject codes: `NOT_DEQUEUED`, `STALE_QUEUE_FINGERPRINT`, `READINESS_DRIFT`, `INVALID_PROVIDER`, `PROVIDER_UNSUPPORTED`, `PROMPT_ADAPTER_FAILED`, `CLIP_COUNT_MISMATCH`, `PROVIDER_RUNTIME_ERROR`.

## Dry-Run Policy

`RuntimePolicy(skip_provider_execution=True)` writes mock clip artifacts under:

`storage/content_brain/execution/artifacts/{session_id}/video_generation/`

Global audit: `storage/content_brain/execution/runtime/audit.jsonl`

## Demo Seeds

```powershell
python -m content_brain.execution.seed_runtime_demo_sessions
```

| Session ID | Expected |
|------------|----------|
| `exec_10i_completed_demo` | COMPLETED (2 mock clips) |
| `exec_10i_failed_demo` | FAILED (NOT_DEQUEUED) |
| `exec_10i_dequeued_demo` | DEQUEUED (ready for manual dispatch) |

## Validation Results

| Test | Result |
|------|--------|
| Dry-run dispatch DEQUEUED → COMPLETED | PASS |
| Stale queue fingerprint reject | PASS |
| NOT_DEQUEUED reject | PASS |
| Legacy session (`exec_test_001`) loads with empty runtime panel | PASS |
| Provider runtime panel extraction | PASS |
| Runtime status service | PASS |
| API routes registered (v0.4.0) | PASS |

## Run

```powershell
$env:MODIR_API_PORT='8770'
python -m ui.api.main

cd ui/web
npm run dev
# ui/web/.env: VITE_API_BASE_URL=http://127.0.0.1:8770
```

Dispatch (dry-run):

```powershell
curl -X POST http://127.0.0.1:8770/sessions/exec_10i_dequeued_demo/runtime/dispatch -H "Content-Type: application/json" -d "{\"skip_provider_execution\": true}"
```

## Not In Scope (10I)

- Suno / ElevenLabs execution
- Narration, assembly, publishing
- Changes to `ui/app.py`, `pipelines/full_video_pipeline.py`, provider orchestrator internals

## Next Phase Candidates

- 10J: Real provider execution toggle + retry/requeue policy
- Voice/music category slots (Suno, ElevenLabs)
- Assembly pipeline after clip artifacts
