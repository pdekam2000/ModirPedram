# Phase 10J — Implementation Plan Report

Generated: 2026-05-30  
Updated: 2026-05-30 (Cost Telemetry)  
Status: **Implementation plan approved — no code started**  
Design reference: [`PHASE_10J_PROVIDER_OPERATIONS_DESIGN.md`](PHASE_10J_PROVIDER_OPERATIONS_DESIGN.md)  
Analysis reference: [`PHASE_10J_REAL_PROVIDER_EXECUTION_ANALYSIS.md`](PHASE_10J_REAL_PROVIDER_EXECUTION_ANALYSIS.md)

---

## Executive Summary

Phase 10J adds a **Provider Operations shell** around the existing 10I `ProviderRuntimeEngine` path. Implementation is split into **seven incremental slices (10J-a → 10J-g)** so each slice is testable without breaking 10A–10I behavior.

**API version target:** `0.5.0`  
**Session schema target:** `10j_v1`  
**Hard constraint:** Zero edits to `VideoProviderRouter`, orchestrators, browser providers, `BrowserManager`, `ui/app.py`, and `pipelines/full_video_pipeline.py`.

**Cost telemetry:** Storage-only `execution_runtime.operations.cost_telemetry` on every dispatch — no pricing calculations in 10J.

---

## 1. Files to Create

### 1.1 Core execution layer (`content_brain/execution/`)

| File | Slice | Purpose |
|------|-------|---------|
| `failure_taxonomy.py` | 10J-a | Failure codes, categories, retriability, HTTP hints |
| `operations_policy.py` | 10J-a | `OperationsPolicy` dataclass (extends 10I `RuntimePolicy` fields) |
| `cost_telemetry.py` | 10J-a | Schema helpers, init/finalize builders, estimate snapshot (read session only) |
| `provider_mode_catalog.py` | 10J-a | Runway/Hailuo families, `supported_modes`, `preferred_mode`, router/learning keys |
| `provider_mode_router.py` | 10J-b | Resolve `(family, provider_execution_mode)` → `router_key` |
| `execution_adapters.py` | 10J-b | `BrowserExecutionAdapter`, `ApiExecutionAdapter` → delegate to router |
| `browser_connectivity_probe.py` | 10J-b | CDP/session smoke without modifying `BrowserManager` |
| `api_connectivity_probe.py` | 10J-b | API key + endpoint probe (Runway only; Hailuo stub-aware) |
| `provider_preflight_validator.py` | 10J-b | Mode-aware preflight orchestration |
| `runtime_job_registry.py` | 10J-c | `active_jobs.json`, job snapshots, mutex |
| `runtime_worker_engine.py` | 10J-c | Daemon thread worker, heartbeat, finalize, **cost_telemetry init/finalize** |
| `artifact_validation_engine.py` | 10J-e | Post-run file validation |
| `provider_learning_writer.py` | 10J-g | Append `{learning_key}.jsonl` on terminal states (optional thin module) |
| `seed_operations_demo_sessions.py` | 10J-g | Demo: preflight fail, async dry-run, mode fields |

### 1.2 Configuration

| File | Slice | Purpose |
|------|-------|---------|
| `config/provider_mode_catalog.json` | 10J-a | Optional override of embedded catalog defaults |

### 1.3 API layer (`ui/api/`)

| File | Slice | Purpose |
|------|-------|---------|
| `services/runtime_operations_service.py` | 10J-d | Facade: async accept, status enrichment, jobs list (may extend `runtime_service.py` instead if kept thin) |
| `schemas/runtime_operations.py` | 10J-d | Extended status DTO, `202 Accepted` response, jobs list |

*Note:* If team prefers fewer files, `runtime_operations_service.py` can be merged into `runtime_service.py` in 10J-d — plan assumes extension of existing service unless split aids review.

### 1.4 Runtime storage (created at runtime, not in repo)

| Path | Slice |
|------|-------|
| `storage/content_brain/execution/runtime/active_jobs.json` | 10J-c |
| `storage/content_brain/execution/runtime/jobs/{dispatch_id}.json` | 10J-c |
| `storage/content_brain/execution/runtime/logs/{dispatch_id}.log` | 10J-c |
| `storage/content_brain/execution/provider_learning/{learning_key}.jsonl` | 10J-g |

### 1.5 Documentation (post-implementation)

| File | Slice |
|------|-------|
| `project_brain/PHASE_10J_IMPLEMENTATION_REPORT.md` | 10J-g |

### 1.6 UI (`ui/web/`)

| File | Slice | Purpose |
|------|-------|---------|
| `src/hooks/useRuntimeStatusPoll.ts` | 10J-f | Poll `GET /runtime/status` while active |
| `src/components/RuntimeOperationsPanel.tsx` | 10J-f | Mode, preflight, stale badge, elapsed (optional extract from SessionDrawer) |

*Optional:* CSS additions in existing stylesheet only — no new theme files required.

---

## 2. Files to Modify

### 2.1 Core execution

| File | Slice(s) | Changes |
|------|----------|---------|
| `content_brain/execution/provider_runtime_engine.py` | 10J-a, 10J-b, 10J-c, 10J-e | Split phases; mode router integration; artifact validation hook; heartbeat callback; persist `provider_execution`, `operations`, **`cost_telemetry`**; keep sync dry-run path |
| `content_brain/execution/session_store.py` | 10J-c | Job paths, `load/save_active_jobs`, file lock helper, learning log append |
| `content_brain/execution/__init__.py` | 10J-a–g | Lazy exports for new engines |
| `content_brain/execution/seed_runtime_demo_sessions.py` | 10J-g | Align with operations fields; optional async dry-run seed |

### 2.2 API

| File | Slice(s) | Changes |
|------|----------|---------|
| `ui/api/services/runtime_service.py` | 10J-c, 10J-d | Delegate to worker for real execution; sync for dry-run; enriched status |
| `ui/api/schemas/runtime.py` | 10J-d | `RuntimeDispatchAcceptedResponse`, extended `RuntimeStatusResponse` with **`cost_telemetry`**, optional `execution_mode` on dispatch body |
| `ui/api/main.py` | 10J-d | HTTP 202 on async dispatch; optional `GET /runtime/jobs`; version `0.5.0` |
| `ui/api/dependencies.py` | 10J-c | Wire worker/registry if singleton needed |
| `ui/api/services/panel_extractor.py` | 10J-f | `extract_provider_runtime()` — add mode, preflight, operations fields |
| `ui/api/schemas/panels.py` | 10J-f | Panel data completeness for new fields |
| `ui/api/schemas/sessions.py` | 10J-f | Pass-through if detail schema needs typed fields |
| `ui/api/services/session_service.py` | 10J-f | Overview `runtime_stale_count` |

### 2.3 UI

| File | Slice(s) | Changes |
|------|----------|---------|
| `ui/web/src/api/client.ts` | 10J-d, 10J-f | Types for extended status, poll helper, optional dispatch POST |
| `ui/web/src/components/SessionDrawer.tsx` | 10J-f | Provider + Mode display, preflight checklist, stale warning, **duration + optional est. credits** |
| `ui/web/src/components/SessionTable.tsx` | 10J-f | Optional Mode column; RUNNING/DISPATCHED filters unchanged |
| `ui/web/src/pages/ExecutionCenterPage.tsx` | 10J-f | Wire poll hook when drawer open on active session |
| `ui/web/src/components/OverviewCards.tsx` | 10J-f | `runtime_stale_count` card |

### 2.4 Explicitly NOT modified

| Path | Reason |
|------|--------|
| `core/video_provider_router.py` | Design lock |
| `orchestrators/*` | Design lock |
| `providers/*` | Design lock |
| `automation/browser_manager.py` | Design lock |
| `pipelines/full_video_pipeline.py` | Legacy path |
| `ui/app.py` | Separate Run Studio app |
| `engines/video_generation_engine.py` | Legacy wrapper |

---

## 3. Dependency Impact Analysis

### 3.1 Inbound dependencies (what 10J depends on)

```
ui/web
  └── ui/api (runtime routes, session routes)
        └── RuntimeOperationsService / RuntimeService
              └── RuntimeWorkerEngine
                    ├── RuntimeJobRegistry → ExecutionSessionStore
                    ├── ProviderPreflightValidator
                    │     ├── ProviderModeRouter → ProviderModeCatalog
                    │     ├── BrowserConnectivityProbe (playwright — optional import)
                    │     ├── ApiConnectivityProbe (requests)
                    │     └── ProviderRegistryEngine (read-only)
                    ├── ProviderRuntimeEngine (10I)
                    │     ├── QueueIntegrityValidator (10I)
                    │     ├── SessionPromptAdapter (10I)
                    │     ├── ProviderModeRouter + ExecutionAdapters
                    │     └── VideoProviderRouter (UNCHANGED)
                    └── ArtifactValidationEngine
```

### 3.2 Outbound impact (what depends on modified files)

| Consumer | Risk if 10J breaks |
|----------|-------------------|
| `seed_runtime_demo_sessions.py` | Demo seeds fail — low prod impact |
| `ui/api` session detail | Panel completeness regression |
| 10H queue → DEQUEUED → dispatch | Primary user path |
| Legacy `ui/app.py` | **None** — no shared code path |
| Content brief pipeline | **None** — stops at queue unless manually dispatched |

### 3.3 New runtime dependencies

| Package | Used by | Already in project? |
|---------|---------|---------------------|
| `playwright` | BrowserConnectivityProbe | Yes (browser stack) |
| `requests` | ApiConnectivityProbe | Yes (Runway API provider) |
| `threading` | RuntimeWorkerEngine | stdlib |

No new pip packages required.

### 3.4 Cross-phase coupling

| Phase | Coupling to 10J |
|-------|-----------------|
| 10G Readiness | Preflight re-checks readiness via existing integrity validator |
| 10H Queue | DEQUEUED prerequisite unchanged; requeue for retry |
| 10I Runtime | Extended, not replaced |
| 10C UI/API | Panel DTO pattern extended |

### 3.5 File system coupling

- Worker and API share `ExecutionSessionStore` — **requires file lock** on session save and `active_jobs.json` updates to prevent lost updates under concurrent poll + worker write.

---

## 4. Rollout Order

### 10J-a — Taxonomy & policy foundation

**Goal:** Shared vocabulary and mode catalog without behavior change.

| Task | Deliverable |
|------|-------------|
| Create `failure_taxonomy.py` | Codes, categories, `is_retriable()`, HTTP hint map |
| Create `operations_policy.py` | `OperationsPolicy` with defaults from design §9.3, §15 |
| Create `cost_telemetry.py` | `init_cost_telemetry()`, `finalize_cost_telemetry()`, estimate snapshot from session (no math) |
| Create `provider_mode_catalog.py` + optional JSON | Runway/Hailuo families, `preferred_mode: browser`, `cost_basis` per mode |
| Extend `RuntimePolicy` or compose `OperationsPolicy` | Document in `provider_runtime_engine` imports only |
| Unit smoke | Import catalog; resolve runway browser → `runway_browser`; build empty telemetry dict |

**Exit gate:** No API/session behavior change; all 10I tests still pass; telemetry helpers unit-testable in isolation.

---

### 10J-b — Preflight & dual mode routing

**Goal:** Mode resolution + preflight checks; still no async worker.

| Task | Deliverable |
|------|-------------|
| Create `provider_mode_router.py`, `execution_adapters.py` | Shim to router keys |
| Create `browser_connectivity_probe.py`, `api_connectivity_probe.py` | Probes only |
| Create `provider_preflight_validator.py` | Full check matrix §6.3–6.5 |
| Extend `provider_runtime_engine.resolve path` | Use mode router for `router_key` (dry-run path can call preflight optionally behind flag) |
| Persist `provider_execution_mode` on manual sync dispatch (optional flag) | Schema fields in session when dispatched |

**Exit gate:** CLI/script can run preflight on DEQUEUED session; browser-down → `BROWSER_UNAVAILABLE`; hailuo api → `PROVIDER_NOT_IMPLEMENTED`.

---

### 10J-c — Worker & job registry

**Goal:** Background execution infrastructure without changing API contract yet.

| Task | Deliverable |
|------|-------------|
| Create `runtime_job_registry.py` | active_jobs, snapshots, mutex |
| Create `runtime_worker_engine.py` | Thread spawn, heartbeat, call engine |
| Extend `session_store.py` | Job paths, locks |
| Extend `provider_runtime_engine.py` | Phase split + heartbeat callback |
| Wire `cost_telemetry` init on job start, finalize on terminal | `operations.cost_telemetry` persisted; audit `COST_TELEMETRY_RECORDED` |
| Internal test | Worker completes dry-run dispatch in thread; heartbeat files written; telemetry has start/end/duration |

**Exit gate:** Worker runs dry-run end-to-end in background; registry cleans up on terminal state; **cost_telemetry populated on COMPLETED/FAILED**.

---

### 10J-d — Async API & status polling

**Goal:** HTTP 202 + enriched status; Execution Center can poll.

| Task | Deliverable |
|------|-------------|
| Extend `runtime_service.py` | `dispatch_async()` vs `dispatch_sync()` |
| Extend `runtime.py` schemas | Accepted response, job block, mode fields, **`cost_telemetry` block** |
| Update `main.py` | 202 for real execution; 200 for dry-run; `GET /runtime/jobs` optional |
| Bump API version | `0.5.0` |
| Extend `client.ts` types | Status DTO (minimal in 10J-d; UI poll in 10J-f) |

**Exit gate:** `POST dispatch` with `skip_provider_execution=true` still 200 sync; with `false` returns 202; status shows job heartbeat **and cost_telemetry start fields**.

---

### 10J-e — Artifact validation

**Goal:** No COMPLETED without validated artifacts.

| Task | Deliverable |
|------|-------------|
| Create `artifact_validation_engine.py` | Rules §7.2 |
| Wire into worker finalize path | Before COMPLETED |
| Enrich artifact metadata | `source_path`, `size_bytes`, `provider_execution` |
| Failure cases | `ARTIFACT_VALIDATION_FAILED`, partial artifacts kept |

**Exit gate:** Inject invalid mock paths → FAILED with artifact code; valid dry-run → COMPLETED.

---

### 10J-f — UI observability

**Goal:** Execution Center displays mode, progress, stale state.

| Task | Deliverable |
|------|-------------|
| Extend `panel_extractor.extract_provider_runtime()` | Mode, preflight, operations |
| SessionDrawer / optional RuntimeOperationsPanel | Provider + Mode, checklist, stale banner |
| `useRuntimeStatusPoll` hook | 5s poll while active |
| OverviewCards | `runtime_stale_count` |
| SessionTable | Optional Mode column |

**Exit gate:** Open RUNNING session → elapsed updates; stale badge when heartbeat old.

---

### 10J-g — Validation & handoff

**Goal:** Automated regression + manual smoke checklist + report.

| Task | Deliverable |
|------|-------------|
| Create `seed_operations_demo_sessions.py` | Preflight fail, async dry-run completed, mode metadata |
| Run validation matrix | Design §13 + §17.9 + **§18.7 cost telemetry** |
| Manual smoke doc | Browser mode with Chrome CDP (operator) |
| Write `PHASE_10J_IMPLEMENTATION_REPORT.md` | Results, known limits |
| Update `project_brain/current_state.md`, `CHAT_HANDOFF.md` | Handoff only if repo convention requires |

**Exit gate:** All automated checks green; implementation report signed off.

---

### Rollout dependency graph

```
10J-a ──► 10J-b ──► 10J-c ──► 10J-d
                    │         │
                    └────► 10J-e ──► 10J-f ──► 10J-g
```

10J-e can start once 10J-c worker finalize path exists (parallel with 10J-d API wiring after 10J-c).

---

## 5. Risk Assessment

| ID | Risk | Severity | Likelihood | Mitigation |
|----|------|----------|------------|------------|
| R1 | Worker thread dies silently; session stuck RUNNING | High | Medium | Heartbeat stale UI warning; job registry `thread_alive`; manual recovery doc |
| R2 | Runway orchestrator `sleep(999999)` blocks worker forever | High | Medium | Document as known; do not auto-fail; global browser job limit = 1 |
| R3 | Session JSON corruption from concurrent API poll + worker save | High | Low | File lock on save; atomic write temp+rename |
| R4 | Preflight false positive (CDP up but not logged in) | Medium | Medium | Best-effort session probe; clear operator message |
| R5 | Preflight false negative (passes but orchestrator fails) | Medium | High | Expected — runtime errors caught as `PROVIDER_RUNTIME_ERROR` |
| R6 | Hailuo returns `None` paths without exception | Medium | High | Artifact validation `ARTIFACT_NULL_PATH` in 10J-e |
| R7 | API mode selected but operator expects browser cost | Low | Medium | UI shows Mode prominently; catalog `preferred_mode` |
| R8 | Two dispatches same session | Medium | Low | `JOB_ALREADY_ACTIVE` + registry mutex |
| R9 | FastAPI reload kills worker threads | Medium | Low | Document: `reload=False` (already default in `main.py`) |
| R10 | Playwright probe in API process conflicts with orchestrator CDP | Medium | Low | Short-lived probe connection; disconnect immediately |

| R11 | Cost telemetry estimates misleading vs actual | Low | Medium | Label as `estimated_*`; store `estimate_source`; no actual-cost claims in 10J UI |

---

## 6. Regression Risks

| Area | Regression | Detection |
|------|------------|-----------|
| 10I dry-run dispatch | Sync path broken or schema regression | Re-run `seed_runtime_demo_sessions.py` |
| 10H queue | DEQUEUED sessions fail dispatch eligibility | Queue demo seeds + dequeue → dispatch |
| 10G readiness fingerprint | Dispatch rejects valid DEQUEUED | Full pipeline session `exec_20260529_*` |
| Session detail API | Missing `provider_runtime_panel` fields crash UI | Legacy `exec_test_001` load |
| Panel completeness | `data_completeness` scores wrong | API snapshot test |
| Overview counts | `runtime_active_count` wrong | Summary endpoint test |
| Timeline events | Provider audit not shown | Session with 10I audit |
| CORS / frontend | Poll loop errors | Manual UI refresh |
| API v0.4.0 clients | 202 response unexpected | Document breaking change in 0.5.0; dry-run still 200 |

**High-priority regression suite (run each slice):**

1. `python -m content_brain.execution.seed_runtime_demo_sessions`
2. `python -m content_brain.execution.seed_queue_demo_sessions` + dispatch dry-run
3. `GET /sessions/{legacy_id}` — no 500
4. Import `ui.api.main:app` — routes register

---

## 7. Backward Compatibility Strategy

### 7.1 Session documents

| Scenario | Behavior |
|----------|----------|
| Pre-10J sessions (`10i_v1`, `10h_v1`, …) | Load normally; missing `operations` → panel shows partial/missing |
| No `provider_execution_mode` | Infer from `provider_resolved` suffix (`*_browser` → browser) or catalog `preferred_mode` |
| Existing `execution_runtime` on COMPLETED 10I demos | Unchanged; no re-migration |

### 7.2 API compatibility

| Endpoint | v0.4.0 behavior | v0.5.0 behavior |
|----------|-----------------|-----------------|
| `POST /runtime/dispatch` dry-run | 200 + body | **Unchanged** 200 |
| `POST /runtime/dispatch` real | 200 blocking (10I) | **202** accepted + poll |
| `GET /runtime/status` | Basic fields | **Superset** — old clients ignore new fields |

### 7.3 Feature flags via request body

| Flag | Effect |
|------|--------|
| `skip_provider_execution: true` | Forces sync dry-run (seeds, CI) |
| `execution_mode: "browser"\|"api"` | Optional override; omitted → catalog default |

### 7.4 Schema versioning

- Set `session_schema_version: 10j_v1` on first 10J dispatch only
- Do not bulk-migrate historical sessions

### 7.5 Rollback plan

If 10J must revert:

1. Deploy API `0.4.0` — sync dispatch restored  
2. 10J session fields ignored by 0.4.0 code  
3. `active_jobs.json` can be deleted manually — sessions terminal state preserved  
4. No provider/orchestrator rollback needed

---

## 8. Browser Mode Impact

### 8.1 Operational prerequisites (unchanged from legacy)

1. Chrome with `--remote-debugging-port=9222`
2. Profile at `storage/real_chrome_profile` (via Run Studio **Open AI Browser** or equivalent)
3. Logged-in Runway/Hailuo subscription session

10J **surfaces** these requirements in preflight; does **not** launch Chrome from Execution Center.

### 8.2 Preflight gates specific to browser mode

| Gate | User-visible outcome |
|------|---------------------|
| CDP unavailable | Dispatch rejected before RUNNING; checklist shows fix |
| Profile missing | `BROWSER_PROFILE_MISSING` |
| Session invalid | `BROWSER_SESSION_INVALID` — re-login in Chrome |
| Download dir not writable | `DOWNLOAD_PATH_NOT_WRITABLE` |
| Concurrent browser job | `BROWSER_CONCURRENCY_LIMIT` — wait or cancel other job |

### 8.3 Runtime behavior

- Worker thread blocks on `VideoProviderRouter` → browser orchestrator for full clip duration
- Heartbeat proves process alive; **does not** prove clip progress
- Stale warning after 120s without heartbeat update
- Runway error hang (`sleep(999999)`) — worker stuck; operator must kill thread/process manually (documented)

### 8.4 Cost and concurrency

- Default `max_concurrent_browser_jobs: 1` — avoids CDP contention (Hailuo opens 2 sessions per clip)
- Learning key `runway_browser` / `hailuo_browser` tags subscription-cost executions

### 8.5 Browser mode validation (10J-g manual)

| Step | Action |
|------|--------|
| 1 | Open Chrome CDP via Run Studio |
| 2 | DEQUEUED session, runway family, browser mode |
| 3 | Dispatch → 202 |
| 4 | Poll until COMPLETED or FAILED |
| 5 | Verify artifacts in session artifact dir |

---

## 9. Future API Mode Impact

### 9.1 What 10J prepares (no new API code)

| Capability | 10J deliverable |
|------------|-----------------|
| Mode selection | Catalog + session override + UI display |
| Preflight | Key, endpoint, connectivity probe |
| Routing | `runway` + `api` → existing `RunwayVideoProvider` via router |
| Learning | `runway_api` jsonl slot |
| Artifacts | Same validation path as browser |

### 9.2 What remains for future phases

| Item | Phase hint |
|------|------------|
| Hailuo API provider implementation | 10K+ |
| `hailuo_api` router branch | When provider exists |
| Quota/billing probes | Optional enhancement |
| Auto-switch `preferred_mode` to api | Config-only when economics change |
| Clip-level API retry | Separate from 10J requeue model |
| Mode selector in dispatch UI | Optional enhancement post-10J-f |

### 9.3 Switching preferred mode (future operator action)

```json
// config/provider_mode_catalog.json
"runway": { "preferred_mode": "api" }
```

**No code deploy required** — new sessions default to API; preflight runs API checks; router key `runway` used.

### 9.4 API mode validation (10J-g automated)

| Scenario | Expected |
|----------|----------|
| Runway + api + `RUNWAY_API_KEY` set | Preflight pass (connectivity probe may warn on network) |
| Runway + api + no key | `CREDENTIALS_MISSING` |
| Hailuo + api | `PROVIDER_NOT_IMPLEMENTED` at preflight |
| Dispatch dry-run + api mode metadata | Mode fields persisted on session |

### 9.5 Risk when API mode goes live

| Risk | Mitigation already in 10J |
|------|---------------------------|
| API cost spike | Learning key `runway_api`; governance unchanged |
| Long poll blocking worker | Same async worker + heartbeat as browser |
| Different failure codes | Taxonomy includes `API_*` codes |

---

## 10. Provider Cost Telemetry (storage only)

### 10.1 Scope

Every dispatch writes `execution_runtime.operations.cost_telemetry`:

| Field | Required at end |
|-------|-----------------|
| `provider_name` | yes |
| `provider_execution_mode` | yes |
| `start_time` | yes (at accept) |
| `end_time` | yes (terminal) |
| `duration_seconds` | yes (terminal) |
| `estimated_cost` | optional — copy from session if present |
| `estimated_credits` | optional — copy from session if present |

**No calculations** beyond `duration_seconds = end - start`. No billing APIs. No aggregation.

### 10.2 Estimate sources (read-only at dispatch init)

```
estimated_credits ← simulation_report | approval_request | budget_decision
estimated_cost    ← simulation_report.estimated_provider_cost | budget_decision.estimated_cost
```

### 10.3 Implementation ownership

| Slice | Task |
|-------|------|
| 10J-a | `cost_telemetry.py` schema + snapshot helpers |
| 10J-c | Worker init/finalize + audit event |
| 10J-d | Status API field |
| 10J-f | Drawer display (duration, optional credits) |
| 10J-g | Assert telemetry on completed seed session |

### 10.4 Future use (not built in 10J)

Cost dashboards, browser vs API economics, Suno analysis, automatic provider recommendation — all consume stored telemetry later.

---

## 11. Implementation Checklist Summary

| Slice | Key files | API ver | Schema |
|-------|-----------|---------|--------|
| 10J-a | taxonomy, catalog, operations_policy, **cost_telemetry** | — | telemetry schema |
| 10J-b | preflight, mode_router, adapters, probes | — | fields defined |
| 10J-c | worker, job_registry, session_store | — | 10j_v1 write |
| 10J-d | runtime_service, main, schemas | **0.5.0** | — |
| 10J-e | artifact_validation_engine | — | artifact meta |
| 10J-f | panel_extractor, web UI | — | — |
| 10J-g | seeds, report, validation | — | — |

---

## 12. Success Criteria (implementation complete)

1. Real dispatch → **HTTP 202**; dry-run → **HTTP 200** sync  
2. Status poll shows mode, job phase, heartbeat, stale flag  
3. Browser preflight fails closed without calling router  
4. API preflight validates Runway; Hailuo api fails gracefully  
5. Artifacts validated before COMPLETED  
6. Failure taxonomy with retriable + requeue path  
7. Zero changes to locked provider files  
8. Regression suite green  
9. **`cost_telemetry` on every terminal dispatch** (duration + optional estimates)  
10. `PHASE_10J_IMPLEMENTATION_REPORT.md` published  

---

*End of Phase 10J Implementation Plan Report*
