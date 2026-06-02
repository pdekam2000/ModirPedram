# PHASE 12I-B — Real Runway Execution Bridge Report

**Date:** 2026-05-31  
**Status:** Implemented  
**Validator:** `project_brain/validate_12i_b_uat_real_runway_bridge.py` — **11/11 PASS**

---

## Summary

Supervised real-video UAT can now reach the **existing** Runway browser stack (`ProviderRuntimeEngine` → `VideoProviderRouter` → `RunwayBrowserOrchestrator`) by applying a **UAT-only queue bridge** (enqueue → dequeue) and a **session-level supervised approval override** before dispatch.

Silent FFmpeg placeholder fallback is **blocked** when `video_provider=runway_browser` and `confirm_real_video=true`. Mock UAT (`video_provider=mock` or Runway without `confirm_real_video`) is unchanged.

**No changes** to RunwayBrowserOrchestrator, RunwayBrowserProvider, VideoProviderRouter, Content Brain, voice/subtitle/assembly runtimes, or browser launcher.

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/uat_real_video_bridge.py` | **New** — UAT-only bridge, logging, browser preflight, queue prepare |
| `content_brain/execution/uat_runtime_engine.py` | `_run_video_stage` bridge + fail-loud + trace logs |
| `content_brain/execution/uat_runtime_profile.py` | `confirm_real_video` on `UatRuntimeConfig` |
| `ui/api/schemas/uat_runtime.py` | `confirm_real_video` request field |
| `ui/api/uat_runtime_service.py` | Pass `confirm_real_video` into config |
| `ui/web/src/api/uatRuntimeClient.ts` | API type + payload |
| `ui/web/src/utils/uatRuntimeEligibility.ts` | Video approval + browser readiness gates |
| `ui/web/src/pages/UatRuntimePage.tsx` | Video approval toggle, compact `RunwayBrowserPanel`, browser poll |
| `project_brain/run_12b_uat_supervised_pipeline.py` | `--confirm-real-video` CLI flag |
| `project_brain/validate_12i_b_uat_real_runway_bridge.py` | **New** — automated checks |

---

## Queue Bridge Design

**Scope:** Only when `uat_supervised_real_runway_requested()` is true:

- `video_provider == runway_browser`
- `confirm_real_video == true`
- not `mock_paid_providers`

**Steps (UAT session only, actor `operator_uat`):**

1. `validate_runway_browser_operator_ready(project_root)` — uses existing `get_browser_operator_status()` (no launcher changes).
2. `apply_uat_supervised_video_dispatch_readiness(session)` — UAT-only patch:
   - `approval_decision.status` → `APPROVED_FOR_EXECUTION` with `override.source=uat_supervised_real_video`
   - `session.state` → `GOVERNED`
   - Re-run **`ExecutionReadinessGate.enrich_session` only** (does not re-run Content Brain or `ApprovalBudgetGovernanceEngine`).
3. `ExecutionQueueEngine.enqueue_by_id(session_id)`
4. `ExecutionQueueEngine.dequeue_by_id(session_id)` → `session.state=DEQUEUED`, `queue_item.queue_state=DEQUEUED`
5. `ProviderRuntimeEngine.dispatch_by_id(..., skip_provider_execution=False)`

Production / Execution Center paths are untouched; bridge functions are only called from `_run_video_stage`.

---

## Dispatch Path (Real Runway)

```text
UAT POST /uat/run (confirm_real_video=true, video_provider=runway_browser)
  → run_uat_pipeline()
  → Content Brain + _pipeline_session() [governance may still show REVISE — overridden later for video only]
  → _run_video_stage()
       → [UAT_REAL_VIDEO] browser preflight
       → uat_runway_queue_and_dispatch_prepare()  [UAT_QUEUE logs]
       → ProviderRuntimeEngine.dispatch_by_id()
            → QueueIntegrityValidator PASS (DEQUEUED)
            → SessionPromptAdapter.build()
            → _execute_clips()
            → VideoProviderRouter.generate_clips(provider_override=runway_browser)
            → RunwayBrowserOrchestrator.run(prompts)   [UNCHANGED]
                 → RunwayBrowserProvider.prepare_gen45_page / fill_prompt / click_generate
                 → wait_for_generated_video_url
                 → RunwayDownloadProvider.download_video_url
            → artifacts copied to session video_generation/
  → voice → subtitle → assembly (unchanged)
```

---

## Placeholder Fallback Policy

| Mode | Behavior |
|------|----------|
| `video_provider=mock` | `_apply_mock_video_artifacts()` — unchanged |
| `runway_browser` without `confirm_real_video` | dispatch may fail → **mock fallback still allowed** (Test 5) |
| `runway_browser` + `confirm_real_video` | enqueue/dequeue → dispatch; on failure **`RuntimeError`** + `[UAT_PLACEHOLDER_BLOCKED]` — **no** mock MP4 |

---

## Traceability Logging

Console prefixes (stdout):

- `[UAT_REAL_VIDEO] session_id=... provider=runway_browser confirm_real_video=True`
- `[UAT_QUEUE] session_id=... enqueued=True|False ...`
- `[UAT_QUEUE] session_id=... dequeued=True|False ...`
- `[UAT_QUEUE] session_id=... dispatch_started=True session_state=DEQUEUED`
- `[UAT_RUNWAY_EXECUTION] session_id=... router_selected=VideoProviderRouter provider_selected=...`
- `[UAT_PLACEHOLDER_BLOCKED] session_id=... reason=... detail=...`

---

## Validation Results

### Automated (11/11 PASS)

```bash
$env:PYTHONPATH=<repo_root>
python project_brain/validate_12i_b_uat_real_runway_bridge.py
```

| Test | Result |
|------|--------|
| Bridge module + engine wiring | PASS |
| Placeholder blocked for supervised path | PASS |
| Mock fallback retained for non-supervised | PASS |
| `confirm_real_video` profile + API schema | PASS |
| Supervised flag logic | PASS |
| Readiness override → READY / READY_WITH_WARNINGS | PASS |

### Manual operator tests (required for Runway UI)

| # | Scenario | Expected | Operator |
|---|----------|----------|----------|
| 1 | Browser running, CDP, Runway login; UAT 10s, **Video Approval** on | Session `DEQUEUED`, dispatch runs, `[UAT_RUNWAY_EXECUTION]` in API worker log | **Pending manual** |
| 2 | Runway UI during clip generation | Prompt entered, Generate clicked, progress, new generation | **Pending manual** |
| 3 | Dispatch blocked (e.g. browser down) | UAT `failed`, explicit error, **no** `uat_mock` clips | **Pending manual** |
| 4 | Voice / subtitle / assembly | Unchanged code paths | **By inspection** |
| 5 | `video_provider=mock` or Runway without video approval | Mock FFmpeg path still works | **Pending manual** |

---

## Exact Execution Trace (Expected — Test 1)

```text
[UAT_REAL_VIDEO] session_id=exec_uat_YYYYMMDD_HHMMSS provider=runway_browser confirm_real_video=True
[UAT_QUEUE] session_id=exec_uat_... enqueued=True reject_code=
[UAT_QUEUE] session_id=exec_uat_... dequeued=True reject_code=
[UAT_QUEUE] session_id=exec_uat_... dispatch_started=True session_state=DEQUEUED
[UAT_RUNWAY_EXECUTION] session_id=exec_uat_... dispatch_started=True router_selected=VideoProviderRouter
============================================================
[Runway Browser Orchestrator] STARTED
...
[Runway Browser] Filling prompt...
[Runway Browser] Clicking final Generate...
[Runway Browser] Waiting for generated video URL ...
[Runway Download] Saved video: downloads/runway/runway_clip_1_....mp4
[UAT_RUNWAY_EXECUTION] session_id=exec_uat_... provider_selected=runway_browser dispatch_success=True
```

Session artifacts should **not** contain `"uat_mock": true` on video clips when dispatch succeeds.

---

## Confirmations

| Requirement | Status |
|-------------|--------|
| Reused existing Runway automation (orchestrator + provider + router) | Yes — no edits to those modules |
| UAT-only queue bridge | Yes — `uat_real_video_bridge.py` |
| Fail loud for supervised real Runway | Yes — `RuntimeError` + `UAT_PLACEHOLDER_BLOCKED` |
| Mock UAT preserved | Yes — when `confirm_real_video` false or `mock` provider |
| Browser launcher unchanged | Yes — only **reads** `get_browser_operator_status` |

---

## Operator Checklist (Test 1)

1. Execution Center or UAT page → **Launch / verify** controlled Chrome (CDP + Runway login green).
2. UAT Runtime → **Runway Browser** video provider, **10s** duration (smoke may auto-cap).
3. Enable **Video Approval** (`confirm_real_video`).
4. Enable voice/assembly approvals as needed.
5. Start UAT → watch API terminal for `[UAT_*]` lines and Runway UI for generation.

---

*End of Phase 12I-B implementation report.*
