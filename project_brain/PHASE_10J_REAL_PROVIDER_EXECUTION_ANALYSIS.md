# Phase 10J — Real Provider Execution Analysis Report

Generated: 2026-05-30  
Status: **Pre-design analysis only** — no implementation, no provider changes.

---

## Executive Summary

Phase 10I already connects **DEQUEUED sessions** to **real provider code** via `VideoProviderRouter.generate_clips()`. The gap for 10J is not “wire the router” — it is **operationalizing** real execution: browser prerequisites, long-running synchronous calls, incremental state, partial failure, artifact validation, and a retry/requeue model that respects existing orchestrators without rewriting them.

**Safest 10J path:** keep orchestrators untouched; add a **runtime execution wrapper** (worker/thread + checkpoint saves) around the existing router call, plus **pre-flight gates** (browser CDP, credentials, provider mode).

---

## 1. What execution path already exists?

### End-to-end chain (Content Execution Center)

```
ContentBriefOrchestrator
  → SessionPopulationBuilder (10D)
  → SimulationReportBuilder (10E)
  → ApprovalBudgetGovernanceEngine (10F)
  → ExecutionReadinessGate (10G)
  → ExecutionQueueEngine (10H)
  → ProviderRuntimeEngine (10I)
       → SessionPromptAdapter (brief_snapshot → prompts[])
       → QueueIntegrityValidator
       → VideoProviderRouter.generate_clips(prompts, provider_override)
            → HailuoMultiClipOrchestrator | RunwayBrowserOrchestrator | RunwayVideoProvider | MiniMaxVideoProvider
       → copy clips → storage/content_brain/execution/artifacts/{session_id}/video_generation/
       → execution_runtime.artifacts_by_category.video_generation[]
```

### Legacy parallel path (unchanged, separate app)

```
ui/app.py (Run Studio)
  → full_video_pipeline.py / VideoGenerationEngine
       → VideoProviderRouter.generate_clips(video_prompts)   # uses active_providers.json default
```

These two paths **converge only at `VideoProviderRouter`**. They do not share session state, artifact dirs, or audit logs.

### Router dispatch table

| `provider_override` / active | Module | Mode | Returns |
|------------------------------|--------|------|---------|
| `hailuo`, `hailuo_browser` | `orchestrators/hailuo_multi_clip_orchestrator.py` | browser | `list[str \| None]` file paths |
| `runway_browser` | `orchestrators/runway_browser_orchestrator.py` | browser | `list[str]` paths |
| `runway`, `runway_api` | `providers/runway_video_provider.py` | API | `list[str]` paths |
| `minimax_api` | `providers/minimax_video_provider.py` | API | **NotImplementedError** |

Active default today: `config/active_providers.json` → `"video": "runway_browser"`.

### 10I real-execution hook (already present)

In `provider_runtime_engine._execute_clips()`:

- `skip_provider_execution=True` → mock `.mock` files (validated in 10I)
- `skip_provider_execution=False` → `VideoProviderRouter().generate_clips(...)` then `shutil.copy2` into session artifact dir

**Conclusion:** Real execution is one flag away at the engine layer. 10J work is **everything around** that call.

---

## 2. What browser automation already exists?

### Infrastructure

| Component | Role |
|-----------|------|
| `automation/browser_manager.py` | Playwright **CDP attach** to Chrome at `http://127.0.0.1:9222` |
| `ui/app.py` → `open_ai_browser()` | Launches Chrome with `--remote-debugging-port=9222` + persistent profile at `storage/real_chrome_profile` |
| Download root | `downloads/` (Hailuo flat, Runway under `downloads/runway/`) |

**Hard prerequisite:** Chrome must be running with remote debugging before any browser provider works. `BrowserManager.launch()` raises if CDP is unavailable.

### Hailuo browser flow (`HailuoMultiClipOrchestrator`)

Per clip (sequential):

1. **New browser session** → `HailuoBrowserProvider.start()` → navigate hailuoai.video → fill prompt → click Create → **fixed sleep `wait_seconds` (default 150s)** → close browser
2. **Separate new browser session** → `HailuoDownloadProvider.start()` → open `/mine` → click latest video → extract via page JS fetch → save to `downloads/hailuo_clip_*.mp4` → close

**Characteristics:**
- 2 browser connect/disconnect cycles **per clip**
- No DOM polling for generation completion (timer-based wait only)
- Download failure returns `None` **without raising** — orchestrator still appends `None` to results
- No session reuse across clips

### Runway browser flow (`RunwayBrowserOrchestrator`)

Single browser session for all clips:

1. `RunwayBrowserProvider.start()` → prepare Gen-4.5 page
2. For each prompt: snapshot video sources → fill → generate → **poll up to 900s** for new video URL (DOM + page text state: `IN_QUEUE`, `GENERATING`, fallback stable visible video)
3. `RunwayDownloadProvider.download_video_url()` via HTTP GET → `downloads/runway/runway_clip_N_*.mp4`

**Characteristics:**
- Better multi-clip continuity (one browser)
- Active polling with timeout
- On exception: prints error, **`time.sleep(999999)`** — blocks forever, browser left open for manual debug
- Validates file size ≥ 100KB after download

---

## 3. What provider adapters already exist?

There is no formal adapter interface. Layers are:

| Layer | File | Responsibility |
|-------|------|----------------|
| Registry | `core/provider_registry_engine.py` + `config/provider_registry.json` | Catalog, enabled flags, credential env keys |
| Active selection | `config/active_providers.json` | Global active provider per category |
| Router | `core/video_provider_router.py` | Name normalization + orchestrator/provider dispatch |
| Browser providers | `providers/hailuo_browser_provider.py`, `providers/runway_browser_provider.py` | DOM interaction |
| Download providers | `providers/hailuo_download_provider.py`, `providers/runway_download_provider.py` | Asset extraction |
| Orchestrators | `orchestrators/hailuo_multi_clip_orchestrator.py`, `orchestrators/runway_browser_orchestrator.py` | Multi-clip sequencing |
| API providers | `providers/runway_video_provider.py`, `providers/minimax_video_provider.py` | REST (Runway complete; MiniMax stub) |
| Thin engine | `engines/video_generation_engine.py` | Legacy wrapper over router |
| Content runtime | `content_brain/execution/session_prompt_adapter.py` | Session → prompts (Runway 950-char trim) |
| Content runtime | `content_brain/execution/provider_runtime_engine.py` | Dispatch, audit, artifact canonicalization |

### Session-side provider resolution (10I)

`resolve_video_provider(session)` reads, in order:

1. `provider_selection.category_selections.video_generation.provider`
2. `provider_selection.primary_provider`
3. `session.provider`

Normalized against `ROUTER_SUPPORTED`: `hailuo_browser`, `runway_browser`, `runway`, `minimax_api`.

**Gap:** Session-selected provider can differ from `active_providers.json`. Router honors `provider_override` from runtime, not global active file — correct for per-session execution.

---

## 4. What runtime state transitions are missing?

### Implemented (10I)

```
DEQUEUED → DISPATCHED → RUNNING → COMPLETED | FAILED
```

Set **synchronously** inside a single `dispatch()` call before and after the full router run.

### Missing for real execution

| Gap | Why it matters |
|-----|----------------|
| **Per-clip progress** | Multi-clip runs can take 15–60+ minutes; UI shows RUNNING with no intermediate signal |
| **Checkpoint saves mid-run** | Crash mid-orchestrator loses all progress; session stuck RUNNING or inconsistent |
| **PARTIAL / COMPLETED_WITH_WARNINGS** | Hailuo can return `[path, None, path]`; current engine fails entirely or accepts incomplete set inconsistently |
| **Provider sub-states** | Runway has `IN_QUEUE` / `GENERATING`; not surfaced to `execution_runtime` |
| **Browser preflight state** | No `AWAITING_BROWSER` or `BROWSER_UNAVAILABLE` before RUNNING |
| **Credential preflight** | API providers fail deep in router; no early `CREDENTIALS_MISSING` |
| **Cancel / abort** | No way to stop in-flight browser orchestration from API |
| **Re-entry after failure** | Failed session cannot redispatch without new queue cycle (by design in 10I: `requeue_required_for_retry: true`) |
| **Async dispatch** | `POST /runtime/dispatch` blocks until all clips finish — unacceptable for browser providers over HTTP |

### Recommended 10J state extensions (design only)

```
RUNNING.clip_index / RUNNING.clip_total / RUNNING.provider_phase
  (optional) COMPLETED_WITH_PARTIAL — N of M clips, failure object per missing clip
  (optional) AWAITING_BROWSER — preflight failed, no provider call started
```

Do **not** change queue states (DEQUEUED consumed at dispatch start).

---

## 5. How should RUNNING / COMPLETED / FAILED be updated from real provider results?

### Current behavior

1. Validate eligibility → write DISPATCHED + audit
2. Write prompt_bundle.json → set RUNNING + audit
3. **Single blocking call** `router.generate_clips(prompts)`
4. On success: COMPLETED + artifacts + audit
5. On any exception: FAILED + failure object + audit

All session saves happen at steps 1–2 and 4–5 only.

### Recommended update model (without rewriting orchestrators)

**Option A — Wrapper with post-hoc results (minimal change)**  
Keep orchestrators as black boxes. Wrapper:
- Sets RUNNING before call
- After return: validate path list (count, non-null, file exists, min size)
- COMPLETED only if all clips valid; else FAILED with `PARTIAL_CLIP_FAILURE` detail listing clip indices

**Option B — Checkpoint wrapper (preferred for 10J)**  
Do not modify orchestrator internals. Instead:
- Run dispatch in a **background worker thread/process** (mirror `ui/app.py` `run_threaded` pattern)
- API returns `{ accepted: true, state: RUNNING }` immediately
- Worker calls existing router unchanged
- After worker completes, single transition to COMPLETED | FAILED
- UI polls `GET /runtime/status`

**Option C — Instrumented router shim (future, higher effort)**  
Inject a progress callback into router/orchestrators — **violates “do not rewrite orchestration”** for 10J; defer.

### Mapping provider outcomes → runtime

| Provider outcome | Session state | `execution_runtime.failure` |
|------------------|---------------|----------------------------|
| All paths valid | COMPLETED | null |
| Empty list / all None | FAILED | `PROVIDER_RUNTIME_ERROR` |
| Some None (Hailuo) | FAILED (or PARTIAL if added) | `PARTIAL_CLIP_FAILURE` + clip index list |
| Router ValueError (unsupported) | FAILED | `PROVIDER_UNSUPPORTED` |
| Browser CDP error | FAILED | `BROWSER_UNAVAILABLE` |
| Runway timeout (900s) | FAILED | `PROVIDER_TIMEOUT` |
| Runway API task FAILED | FAILED | `PROVIDER_TASK_FAILED` |
| MiniMax NotImplementedError | FAILED | `PROVIDER_NOT_IMPLEMENTED` |

### Audit events to add (design)

- `CLIP_STARTED` / `CLIP_COMPLETED` / `CLIP_FAILED` (optional, if checkpoint wrapper can infer from orchestrator logs only — otherwise defer)
- `BROWSER_PREFLIGHT_FAILED`
- `ARTIFACT_PERSISTED` per clip after copy to artifact dir

---

## 6. How should artifacts be persisted?

### Already implemented (10I)

```
storage/content_brain/execution/artifacts/{session_id}/video_generation/
  prompt_bundle.json
  clip_01.mp4 | clip_01.mock
  clip_02.mp4 | ...
```

Runtime copies from provider output paths into canonical names. Artifact records:

```json
{
  "artifact_id": "art_...",
  "provider_category": "video_generation",
  "artifact_type": "video_clip",
  "provider": "runway_browser",
  "file_path": ".../clip_01.mp4",
  "clip_number": 1,
  "metadata": { "prompt_hash": "sha256:...", ... }
}
```

### Gaps for real execution

| Gap | Recommendation |
|-----|----------------|
| Provider writes to `downloads/` first | Keep copy step; add `source_path` + `copied_at` in artifact metadata |
| No file validation | After copy: `stat().st_size`, optional ffprobe duration, min size threshold (Runway uses 100KB) |
| No checksum | Store `sha256` of final artifact file in metadata |
| Hailuo `None` paths | Treat as missing artifact; do not copy |
| Orphan downloads | Optional cleanup policy for `downloads/` after successful copy (config flag) |
| Large files / disk space | Preflight disk check in artifact dir parent (optional) |

**Do not** change provider download locations in 10J — canonicalization stays in `ProviderRuntimeEngine._execute_clips()`.

---

## 7. What retry model should be used?

### Current 10I placeholder

```json
"retry": {
  "max_dispatch_attempts": 1,
  "dispatch_attempts_used": 1,
  "requeue_required_for_retry": true
}
```

Failed dispatch does **not** auto-requeue. Session stays FAILED; new attempt requires new queue cycle (10H).

### Existing retry code in providers

- `providers/runway_video_provider.py` has empty stubs: `retry_generation()`, `timeout_wrapper()` — **not wired**
- Orchestrators have **no retry loops**
- Hailuo relies on fixed wait; Runway relies on poll timeout

### Recommended 10J retry model (layered)

**Layer 1 — Clip-level (defer / optional)**  
Would require orchestrator changes → **out of scope** per constraints.

**Layer 2 — Dispatch-level (recommended)**  
On FAILED with retriable codes (`BROWSER_UNAVAILABLE`, `PROVIDER_TIMEOUT`, transient network):

1. Do **not** auto-retry in same dispatch (browser state unknown)
2. Mark session FAILED with `failure.retriable: true`
3. Operator re-enqueues via 10H (new queue item, new fingerprint) → DEQUEUED → dispatch again
4. Increment `dispatch_attempts_used` if same session document reused (or new session lineage)

**Layer 3 — Policy caps**  
Extend `RuntimePolicy`:

- `max_dispatch_attempts_per_session` (e.g. 2)
- `retriable_failure_codes: [...]`
- Block dispatch if attempts exhausted → `RETRY_EXhaustED`

**Layer 4 — Partial re-run (future 10K+)**  
Re-dispatch only missing clip indices — requires orchestrator support or clip-level router API → not 10J.

### Requeue vs in-place retry

| Strategy | Pros | Cons |
|----------|------|------|
| **Requeue (10H)** | Clean fingerprint, aligns with governance | Manual or automated re-enqueue step |
| **In-place redispatch** | Faster | Violates DEQUEUED-only rule unless state machine extended |
| **Same-thread immediate retry** | Simple | Dangerous for browser providers (stale DOM, double billing) |

**Recommendation:** **Requeue-first** for browser; **single automatic retry** only for API providers with idempotent task IDs (Runway API) in a later sub-phase.

---

## 8. What provider-specific risks exist?

### Cross-cutting

| Risk | Impact | Mitigation (10J design) |
|------|--------|-------------------------|
| Sync dispatch in FastAPI | HTTP timeout, UI freeze | Background worker + async accept + status poll |
| Chrome CDP not running | Immediate failure | Preflight `BrowserManager` connect test → `BROWSER_UNAVAILABLE` |
| Long runtimes | 150s × N (Hailuo), up to 900s × N (Runway) | Worker thread; show RUNNING + elapsed; no HTTP hold |
| Session provider ≠ tested provider | Wrong orchestrator | Already resolved via `provider_override`; add registry mode check |
| Selector/DOM drift | Silent failures, timeouts | Document manual recovery; capture screenshot hook (Runway already pauses) |

### Hailuo-specific

| Risk | Detail |
|------|--------|
| Timer-based wait | 150s may be too short (fail) or too long (waste) |
| Dual browser per clip | 2× CDP connect overhead; race if multiple jobs |
| `None` download | Appends null without raise → runtime must validate |
| Login/session | Uses shared Chrome profile; no explicit login check |
| UI selectors | `[contenteditable='true']`, Create button fallbacks — fragile |

### Runway browser-specific

| Risk | Detail |
|------|--------|
| Infinite block on error | `sleep(999999)` hangs worker forever |
| Gen-4.5 UI navigation | Region-based clicks; UI updates break flow |
| Fallback video detection | May grab wrong clip if multiple visible |
| Signed URL expiry | Download must happen promptly after detection |
| Queue/generation text parsing | English UI strings only |

### Runway API-specific

| Risk | Detail |
|------|--------|
| `RUNWAY_API_KEY` required | Fail fast if missing |
| Task polling | 60 attempts × 10s default; cost per clip |
| Prompt length | 950 char cap (adapter + provider both trim) |
| Rate limits / billing | No handling today |

### MiniMax-specific

| Risk | Detail |
|------|--------|
| **Not implemented** | Always `NotImplementedError` — must remain blocked in 10J unless implemented separately |

### Registry / config drift

| Risk | Detail |
|------|--------|
| `provider_registry.json` enabled flags | e.g. `hailuo_browser enabled: false` but still routable via override |
| `active_providers.json` | Legacy pipeline default; content sessions use session `provider_selection` |

---

## Architecture Diagram — 10J Target (proposed)

```
┌─────────────────┐     POST /dispatch      ┌──────────────────────┐
│  Execution UI   │ ───────────────────────►│  RuntimeService      │
└─────────────────┘                         │  (accept + enqueue)  │
        ▲                                   └──────────┬───────────┘
        │ poll GET /status                               │
        │                                              ▼
        │                                   ┌──────────────────────┐
        │                                   │  RuntimeWorker       │
        │                                   │  (thread/process)    │
        │                                   └──────────┬───────────┘
        │                                              │
        │   save RUNNING                               ▼
        │◄──────────────────────────────  ProviderRuntimeEngine
        │                                   (skip_provider=False)
        │                                              │
        │                                              ▼
        │                                   VideoProviderRouter
        │                                   (UNCHANGED)
        │                                              │
        │                         ┌────────────────────┼────────────────────┐
        │                         ▼                    ▼                    ▼
        │                  HailuoOrchestrator   RunwayOrchestrator   RunwayAPI
        │                         │                    │                    │
        │                         └────────────────────┴────────────────────┘
        │                                              │
        │                                   downloads/* → copy → artifacts/
        │                                              │
        └──────────────────────────────  COMPLETED | FAILED + audit
```

---

## 10J Scope Recommendation

### In scope (safe, no orchestrator rewrite)

1. **Background dispatch worker** + immediate API response
2. **Browser/credential preflight** before RUNNING
3. **Post-run artifact validation** (exists, size, count match)
4. **Retriable failure taxonomy** + requeue documentation/automation hook
5. **Runtime status enrichment** (elapsed, clip counts, provider_phase from worker)
6. **Default `skip_provider_execution=False`** only when preflight passes (explicit API flag)

### Out of scope (explicit)

- Rewriting `HailuoMultiClipOrchestrator` / `RunwayBrowserOrchestrator`
- Changing `providers/*` DOM logic
- Suno / ElevenLabs / assembly / narration
- Clip-level retry inside orchestrators
- Modifying `ui/app.py` or `full_video_pipeline.py`

### Open decisions for approval

1. Async worker: **thread** (simple, GIL ok for I/O-bound browser) vs **subprocess** (isolation from API)?
2. Partial success state: **strict FAILED** vs new **COMPLETED_WITH_PARTIAL**?
3. Who opens Chrome: still manual via legacy app, or headless preflight message in Execution Center UI?
4. First real provider for 10J validation: **runway_browser** (active default) vs **runway API** (no browser deps)?

---

## Appendix — Key file references

| Path | Role |
|------|------|
| `content_brain/execution/provider_runtime_engine.py` | Dispatch lifecycle, `_execute_clips` |
| `core/video_provider_router.py` | Provider routing |
| `orchestrators/hailuo_multi_clip_orchestrator.py` | Hailuo multi-clip browser |
| `orchestrators/runway_browser_orchestrator.py` | Runway browser multi-clip |
| `providers/runway_video_provider.py` | Runway REST API |
| `automation/browser_manager.py` | CDP Chrome attach |
| `config/active_providers.json` | Global active video provider |
| `config/provider_registry.json` | Provider catalog |
| `engines/video_generation_engine.py` | Legacy router wrapper |
