# PHASE 12J-C STEP 2 — Runway Wait/Download Hardening Design

**Date:** 2026-06-02  
**Status:** Design freeze — no implementation, no code changes  
**Inputs:** `PHASE_12J_C_STEP1_RUNWAY_DOWNLOAD_TRACE.md`, `exec_uat_20260602_080026`, current `RunwayBrowserOrchestrator` / `VideoProviderRouter` contracts

---

## Purpose

Define a **safer wait + download strategy** for Runway browser mode that:

- Reduces false timeouts when generation is slow or DOM differs from `<video src>` assumptions
- Captures **debug artifacts** when wait/download fails
- Preserves **11E safety** (bounded waits, cancel checkpoints, no infinite sleep)
- Does **not** auto-retry generation, re-click Generate, or spend extra credits

**Out of scope (this design):** Runway API mode, prompt composer (12J-C), voice/subtitle/assembly, browser launcher rewrite.

---

## Problem Statement (Step 1 Recap)

| Symptom | Root cause class |
|---------|------------------|
| `PROVIDER_RUNTIME_ERROR` / clip 1 URL timeout | Wait loop exhausted **180s** (`VideoProviderRouter` override), not 900s env default |
| Prompt submit OK, generation starts | Failure is **detection + wait budget**, not `fill_prompt` |
| No mp4 artifact | `wait_for_generated_video_url()` never returned URL → download never called |
| Unknown if Runway finished | Single-signal `<video>` + `new_sources ∉ before_set`; no snapshot on failure |

---

## Design Principles

1. **One active job per clip** — wait/download only the generation triggered by the current `click_generate()`; never start a second job.
2. **Wait longer, detect smarter** — extend policy-aligned timeout; add multi-signal completion before failing.
3. **Fail loud with evidence** — timeout produces debug bundle under session `artifact_root`, not silent `FAILED` with no context.
4. **Extend, don’t fork** — harden `RunwayBrowserOrchestrator` + `runway_browser_support`; optional new `runway_browser_wait_engine.py` helper module (no parallel orchestrator).
5. **Runtime-visible progress** — heartbeat metadata for UI/ops while state remains `RUNNING`.

---

## Architecture Placement

```text
ProviderRuntimeEngine.dispatch()          [unchanged entry]
  → SessionPromptAdapter                  [unchanged]
  → VideoProviderRouter.generate_clips()
       → RunwayBrowserOrchestrator.run()
            → RunwayBrowserProvider       [submit only — unchanged contract]
            → RunwayBrowserWaitEngine     [NEW — design] wait + signals + debug
            → RunwayDownloadStrategy      [NEW — design] A→B→C→D
            → RunwayDownloadProvider      [extend for browser-download path]
```

**Files touched in future implementation (reference only):**

| File | Change |
|------|--------|
| `core/video_provider_router.py` | Remove hardcoded `wait_seconds=180`; resolve from config |
| `providers/runway_browser_support.py` | Timeout resolution, debug paths, log prefixes |
| `orchestrators/runway_browser_orchestrator.py` | Delegate wait/download to new engines; keep clip loop |
| `content_brain/execution/runway_config.py` | Browser wait policy snapshot fields |
| `config/provider_mode_catalog.json` (optional) | `browser_generation_max_wait_seconds` per family |
| `content_brain/execution/provider_runtime_engine.py` | `category_runtime.video_generation.runway_wait` heartbeat |
| UI ops / UAT panels (12J-C2e) | Display substate, not premature FAILED |

**Unchanged:** `RunwayBrowserProvider` navigation/selectors for submit; `browser_launcher.py`; composer; queue/readiness.

---

## 1. Timeout Policy — Design Decisions

### 1.1 Should Runway Browser use 900s default instead of 180s?

**Decision: YES — make `browser_max_wait_seconds()` the single authoritative default (900s env default).**

| Item | Current | Proposed |
|------|---------|----------|
| `VideoProviderRouter` | Hardcodes `wait_seconds=180` | **Remove override**; pass `None` → orchestrator uses `browser_max_wait_seconds()` |
| `RunwayBrowserOrchestrator.__init__` | `None` → 900 via support | Unchanged |
| Env `RUNWAY_BROWSER_MAX_WAIT_SECONDS` | Default 900 | Keep; document as operator knob |

**Rationale:** Step 1 showed ~217s wall-clock with **180s** wait budget; Gen-4.5 clips (10s output) often exceed 3 minutes in queue+render. 180s causes **false `PROVIDER_TIMEOUT`** when generation is still legitimate.

**Guardrails:**

- Cap via existing `OperationsPolicy.max_clips_cap` and worker `stale_after_seconds` (must remain ≥ max wait or worker must not kill RUNNING early).
- Recommend `stale_after_seconds` ≥ `max_wait + 120` for browser jobs (design note for ops config review).

### 1.2 Should timeout be provider-mode/catalog based?

**Decision: YES — layered resolution (first match wins).**

```text
resolve_runway_browser_max_wait_seconds(session?) -> int

  1. Env RUNWAY_BROWSER_MAX_WAIT_SECONDS (explicit operator override)
  2. session.execution_runtime.operations.runway_browser_max_wait_seconds (optional per-run UAT override)
  3. provider_mode_catalog.runway.browser_generation_max_wait_seconds (design field)
  4. runway_config snapshot default for EXECUTION_MODE_BROWSER (900)
  5. Hard floor 60, hard ceiling 1800 (30 min) — prevent runaway tabs
```

**Catalog addition (design schema):**

```json
{
  "runway": {
    "preferred_mode": "browser",
    "browser_generation_max_wait_seconds": 900,
    "browser_poll_interval_seconds": 10
  }
}
```

**Per-clip wait (multi-clip):** Same budget **per clip**, not shared across clips (avoid clip 2 inheriting clip 1’s exhausted timer). Orchestrator already loops per clip — keep **independent** `start = monotonic()` per clip.

### 1.3 Should UI show “Runway still generating” instead of failed too early?

**Decision: YES — distinguish runtime substate from terminal FAILED.**

| Session `execution_runtime.state` | Substate (new) | UI copy |
|--------------------------------|----------------|---------|
| `RUNNING` | `runway_wait:generating` | “Runway still generating (clip N, elapsed Xs / max Ys)” |
| `RUNNING` | `runway_wait:detecting` | “Runway generation complete — resolving download…” |
| `RUNNING` | `runway_download:attempting` | “Downloading clip N…” |
| `FAILED` | — | Only after **hard wait exhausted** + debug bundle written |

**Mechanism:**

- `ProviderRuntimeEngine` updates `category_runtime.video_generation.runway_wait` every poll (or every 10s): `{ clip_index, elapsed_seconds, max_wait_seconds, page_state, signal_summary, last_log_at }`.
- **Do not** set `state=FAILED` until `RunwayBrowserWaitEngine` raises terminal `RunwayProviderError` with `code=PROVIDER_TIMEOUT` and debug artifact paths attached.
- UAT progress log append: `[RUNWAY_WAIT_STATE] …` mirrored into `operations.uat_run.progress_log` when UAT session.

**Early failure unchanged for true errors:** `LOGIN_REQUIRED`, `GENERATION_ERROR`, `BROWSER_AUTOMATION_NOT_READY` → immediate FAILED (not “still generating”).

---

## 2. Completion Detection — Multi-Signal Design

Replace single-path “new `<video>` src” with a **scoring evaluator** polled each interval.

### 2.1 Signal catalog

| Signal ID | Source | Detection method | Weight |
|-----------|--------|------------------|--------|
| `S1_VIDEO_NEW_SRC` | DOM | `querySelectorAll("video")` → `currentSrc\|src` not in `before_set` | **1.0** (strong) |
| `S2_VIDEO_VISIBLE_STABLE` | DOM | Visible video ≥80×80, same `src` **3** polls | **0.85** |
| `S3_DOWNLOAD_BUTTON` | DOM | Button/link text ∈ `{Download, Download video, Save, Export}` visible+enabled near latest card | **0.9** |
| `S4_GENERATION_CARD_READY` | DOM | Card/container with `data-testid` / aria / class heuristic (see §2.3) showing complete/checkmark/not spinner | **0.8** |
| `S5_PROGRESS_GONE` | Text | Prior poll had `generating`/`in queue`; current lacks those substrings | **0.5** |
| `S6_QUEUE_GENERATING_ABSENT` | Text | `get_page_generation_state()` ∉ `{IN_QUEUE, GENERATING}` for **2** consecutive polls | **0.4** |
| `S7_SELECTED_JOB_STATUS` | DOM+Text | Active generation row for **current job fingerprint** shows Complete/Ready | **0.85** |
| `S8_NETWORK_MEDIA_URL` | Playwright | `page.on("response")` collector: `content-type` video/* or URL pattern `*.mp4`, `*cloudfront*`, `*runway*` during wait window | **0.95** |
| `S9_BROWSER_DOWNLOAD_EVENT` | Playwright | `page.wait_for_event("download")` after intentional download click only | **N/A** (download phase) |

### 2.2 Completion gate

```text
evaluate_completion(signals) -> CompletionDecision

  IMMEDIATE_SUCCESS if:
    - S1_VIDEO_NEW_SRC has candidate URL, OR
    - S8_NETWORK_MEDIA_URL has new URL not in before_set, OR
    - score >= 0.9 from {S3, S7} with corroboration (any one of S5, S6, S2)

  PROBABLE_SUCCESS (one more poll) if:
    - score in [0.6, 0.9)

  CONTINUE_WAIT if:
    - page_state in {IN_QUEUE, GENERATING} and score < 0.6

  STALL_WARNING if:
    - elapsed > 0.5 * max_wait and score == 0 for 6 consecutive polls
    → log [RUNWAY_WAIT_STATE] stall_warning

  NO auto-regenerate, NO second Generate click in any branch
```

**Job fingerprint (for S7):** Hash of `{ clip_index, prompt_hash_prefix, generate_clicked_at }` stored in orchestrator clip context — match latest sidebar/history item **after** click timestamp, not older history.

### 2.3 DOM heuristics (design — tuned at implementation with debug captures)

**Generation card ready (S4):** Evaluate in page:

- Elements containing completed-state cues: `aria-label` matching `/complete|ready|done/i`, absence of `role="progressbar"` within same card, CSS class substrings `/complete|success|ready/i` (fragile — debug JSON will refine).
- Prefer **relative** match: topmost/rightmost card in Gen-4.5 results strip after submit.

**Download button (S3):** Playwright locators (priority order):

```text
get_by_role("button", name=/^Download/i)
locator("button").filter(has_text=/Download/i)
get_by_role("link", name=/Download/i)
```

Scoped to **latest generation card** container when possible (parent walk from newest video/card).

### 2.4 `before_set` refinement

**Problem:** Old history videos pollute `before_set` or mask “new” URL reuse.

**Design:**

1. Capture `before_set` immediately pre-generate (keep).
2. Additionally capture `before_job_ids` from visible card IDs/timestamps if available.
3. On success, prefer URL from signals tied to **post-click** cards only.
4. If `new_sources` empty but S8 network captured new URL after `generate_clicked_at`, accept network URL.

### 2.5 Refactor boundary

Extract from orchestrator into **`RunwayBrowserWaitEngine`**:

- `wait_for_clip_ready(page, clip_context) -> WaitResult`
- `WaitResult`: `{ status: ready|timeout|error, video_url?, signal_evidence[], page_state, elapsed_seconds }`

`wait_for_generated_video_url()` becomes thin wrapper calling wait engine (backward-compatible name).

---

## 3. Debug Capture on Timeout — Design

### 3.1 When to capture

| Trigger | Capture |
|---------|---------|
| `PROVIDER_TIMEOUT` (wait exhausted) | **Full bundle** |
| `PROVIDER_TASK_FAILED` / `GENERATION_ERROR` | Full bundle |
| `DOWNLOAD_FAILED` after all strategies | Full bundle + partial download bytes if any |
| Successful clip | **Minimal** optional snapshot (config flag `RUNWAY_DEBUG_ON_SUCCESS=false` default) |

### 3.2 Artifact layout

```text
{artifact_root}/runway_debug/clip_{NN}_{dispatch_id}_{iso}/
  manifest.json
  screenshot.png
  page_url.txt
  body_text_summary.txt
  dom_excerpt.json
  video_elements.json
  interactive_elements.json
  network_media_candidates.json
  wait_timeline.jsonl          # poll-by-poll signal scores
```

Attach paths to `RunwayProviderError.details.debug_bundle` and `execution_runtime.failure.debug_bundle`.

### 3.3 Field definitions

| Artifact | Content |
|----------|---------|
| `screenshot.png` | Full viewport `page.screenshot(full_page=false)` |
| `page_url.txt` | `page.url` |
| `body_text_summary.txt` | First 8 KB of `innerText`, plus keyword hits: generating, queue, error, download |
| `dom_excerpt.json` | Truncated outerHTML of: main workspace, results strip, top 3 cards (max 32 KB each) |
| `video_elements.json` | All `<video>`: index, src, currentSrc, width, height, visible, bounding rect |
| `interactive_elements.json` | Buttons/links: text, aria-label, disabled, bbox (cap 200 elements) |
| `network_media_candidates.json` | URLs seen since clip generate click: content-type, status, size if known |
| `wait_timeline.jsonl` | One JSON line per poll: timestamp, elapsed, page_state, signals, scores |
| `manifest.json` | composer_version, clip_index, max_wait, prompt_hash, failure_code |

### 3.4 Privacy / size caps

- Strip query tokens from URLs in stored JSON (replace with `<redacted>`) unless needed for download retry in same session.
- Total bundle cap **10 MB**; truncate excerpts with `truncated: true`.

### 3.5 API for orchestrator

```text
RunwayTimeoutDebugCapture.capture(page, clip_context, wait_timeline) -> debug_bundle_paths
```

Invoked in `except`/timeout path only — **no** screenshot on happy path by default.

---

## 4. Download Strategy — Fallback Sequence

### 4.1 Overview

```text
download_clip(page, wait_result, clip_context) -> DownloadResult

  A. direct_video_src_download(wait_result.video_url)
  B. browser_download_button_path()
  C. open_generated_card_and_retry_detection()
  D. fail_loud_with_debug_bundle()
```

Each step logs `[RUNWAY_DOWNLOAD_ATTEMPT] strategy=A|B|C|D`.

### 4.2 Strategy A — Direct video `src` (current path, keep first)

**Precondition:** `wait_result.video_url` non-empty, http(s) or blob (blob handled in B if A fails).

**Action:** Existing `RunwayDownloadProvider.download_video_url()` HTTP GET stream to `artifact_root/downloads/runway_clip_{N}_{ts}.mp4`.

**Success:** `finalize_download_artifact` + min bytes gate (100 KB per 11E-d).

**Fail → B** (do not re-generate).

### 4.3 Strategy B — Runway Download button + browser download event

**Precondition:** S3 detected or button locatable on latest card.

**Safety:**

- Click **at most one** Download per clip.
- **No** Generate, **no** Upscale, **no** Regenerate variants.

**Action:**

1. Register `page.expect_download(timeout=120_000)` (config `RUNWAY_BROWSER_DOWNLOAD_EVENT_TIMEOUT_SECONDS`, default 120).
2. Click scoped Download button on **current job card only**.
3. Save to `artifact_root/runway_clip_{N}_{ts}.mp4`.
4. Validate min bytes.

**Fail → C**.

### 4.4 Strategy C — Open card + retry detection (read-only navigation)

**Precondition:** Card visible but URL not extracted.

**Safety:** Open/detail click only — **no** new generation actions.

**Action:**

1. Click latest generation card/thumbnail (heuristic from debug-tuned selectors).
2. Wait `browser_page_settle_seconds()`.
3. Re-run **read-only** signal probe (S1, S2, S3, S8) for up to **60s** sub-budget (does not extend generation wait; part of download phase).
4. If URL found → A; if Download button → B.

**Fail → D**.

### 4.5 Strategy D — Fail loud

Raise `RunwayProviderError`:

- `code`: `PROVIDER_TIMEOUT` or `DOWNLOAD_FAILED`
- `details`: `{ clip_index, strategies_attempted: ["A","B","C"], debug_bundle: {...}, max_wait_seconds }`

`ProviderRuntimeEngine` maps to `PROVIDER_RUNTIME_ERROR` for session but preserves `failure.debug_bundle` and `failure.provider_code`.

### 4.6 Credit safety summary

| Action | Allowed |
|--------|---------|
| Wait/poll | ✅ |
| Click Download on finished job | ✅ (one click) |
| HTTP fetch URL | ✅ |
| Click Generate again | ❌ |
| Click Regenerate / Variations | ❌ |
| Submit second prompt for same clip | ❌ |
| Open unrelated workspace flows | ❌ |

---

## 5. Safety Rules (Frozen)

1. **Single job per clip** — `generate_clicked_at` monotonic marker; ignore videos/cards older than marker unless explicitly in `before_set` baseline.
2. **No auto-retry of generation** — timeout is terminal for that dispatch attempt; human or explicit requeue only.
3. **No credit spend beyond original job** — forbidden clicks listed in §4.6; implementation uses allowlist click labels.
4. **Cancel still wins** — `check_cancel` at every poll, before each download strategy, during download stream.
5. **Partial artifacts preserved** — if clip 1 downloads and clip 2 fails, retain clip 1 paths in `partial_paths` (11E behavior).
6. **Composer isolation** — wait/download engines must not read `runway_composed_clips`; only orchestrator supplies `prompt` string.

---

## 6. Observability — Log Contract

### 6.1 Required log lines

**`[RUNWAY_WAIT_STATE]`** — every poll (or on state change + every 30s heartbeat):

```text
[RUNWAY_WAIT_STATE] clip=1 elapsed=120 max=900 page_state=GENERATING score=0.35 signals=S6,S5 visible_videos=2 new_src=0 stall=false
```

**`[RUNWAY_VIDEO_CANDIDATES]`** — when any candidate URL/element appears:

```text
[RUNWAY_VIDEO_CANDIDATES] clip=1 count=2 candidates=[{src:"https://.../...", signal:"S1_VIDEO_NEW_SRC", w:640, h:360}, ...]
```

**`[RUNWAY_DOWNLOAD_ATTEMPT]`** — per strategy:

```text
[RUNWAY_DOWNLOAD_ATTEMPT] clip=1 strategy=B button_text="Download" expect_download_timeout=120
```

**`[RUNWAY_TIMEOUT_DEBUG]`** — on terminal failure:

```text
[RUNWAY_TIMEOUT_DEBUG] clip=1 bundle=storage/.../runway_debug/clip_01_... manifest=... screenshot=... videos=3 buttons=47
```

### 6.2 Session persistence

Mirror into `execution_runtime.category_runtime.video_generation`:

```json
{
  "runway_wait": {
    "clip_index": 1,
    "phase": "generating",
    "elapsed_seconds": 120,
    "max_wait_seconds": 900,
    "page_state": "GENERATING",
    "completion_score": 0.35,
    "last_signal": "S6_QUEUE_GENERATING_ABSENT",
    "last_log_at": "2026-06-02 08:02:00"
  },
  "runway_debug_last_bundle": null
}
```

On failure, set `runway_debug_last_bundle` to manifest path.

### 6.3 Audit / UAT

- Append `wait_timeline.jsonl` tail (last 20 lines) into `operations.uat_run` failure stage detail when UAT.
- `validate_12j_c2_runway_wait_hardening.py` (future) — unit tests on signal scorer with fixture DOM JSON from Step 1 replays.

---

## 7. Implementation Phases (Design Roadmap — Not Now)

| Phase | ID | Deliverable |
|-------|-----|-------------|
| Wait policy | **12J-C2a** | Router uses `resolve_runway_browser_max_wait_seconds()`; catalog field; RUNNING substate |
| Multi-signal wait | **12J-C2b** | `RunwayBrowserWaitEngine` + scorer; network listener |
| Debug capture | **12J-C2c** | `RunwayTimeoutDebugCapture` + artifact layout |
| Download fallbacks | **12J-C2d** | Strategies A–D + Playwright download |
| UI observability | **12J-C2e** | Ops/UAT panel: elapsed, substate, debug bundle link |

**Recommended order:** C2a → C2b → C2c → C2d → C2e (C2c can parallel C2b for timeout-only relief).

---

## 8. Configuration Summary (Frozen Names)

| Key | Default | Purpose |
|-----|---------|---------|
| `RUNWAY_BROWSER_MAX_WAIT_SECONDS` | `900` | Per-clip generation wait |
| `RUNWAY_BROWSER_POLL_INTERVAL` | `10` | Poll seconds |
| `RUNWAY_BROWSER_DOWNLOAD_EVENT_TIMEOUT_SECONDS` | `120` | Strategy B download event |
| `RUNWAY_BROWSER_DOWNLOAD_PHASE_MAX_SECONDS` | `180` | Cap for B+C combined |
| `RUNWAY_BROWSER_DEBUG_CAPTURE_ENABLED` | `true` | Timeout debug bundle |
| `RUNWAY_BROWSER_DEBUG_ON_SUCCESS` | `false` | Optional success snapshot |
| `RUNWAY_BROWSER_COMPLETION_SCORE_THRESHOLD` | `0.9` | Immediate success |
| `RUNWAY_BROWSER_STALL_WARNING_RATIO` | `0.5` | Fraction of max_wait for stall log |

Remove: **hardcoded `180`** in `VideoProviderRouter` (design mandate).

---

## 9. Acceptance Criteria (For Future Implementation)

| ID | Criterion |
|----|-----------|
| AC1 | UAT Runway clip wait uses ≥900s default unless env overrides |
| AC2 | While generating, session stays `RUNNING` with `runway_wait` substate; UI can show “still generating” |
| AC3 | Timeout produces `runway_debug/` bundle with screenshot + `video_elements.json` |
| AC4 | If `<video src>` missing but Download button present, Strategy B succeeds without second Generate |
| AC5 | Logs include all four prefixes on a real supervised run |
| AC6 | Composer-enabled session behaves identically in wait/download path except prompt text |
| AC7 | No duplicate Generate clicks in codebase paths (static validator grep) |

---

## 10. Risk Register

| Risk | Mitigation |
|------|------------|
| Longer wait holds worker slot | Align `stale_after_seconds`; UAT single concurrent browser job |
| DOM heuristics break on Runway UI update | Debug bundles + manifest versioning `runway_ui_probe_version` |
| Strategy B saves to wrong file | Scope Download click to job fingerprint card |
| Network listener memory | Cap URL list at 50 entries per clip |
| Blob URLs not HTTP-downloadable | Strategy B mandatory fallback |

---

## 11. Design Decision Summary

| Question | Decision |
|----------|----------|
| 900s vs 180s? | **Use 900s default** via support/catalog; **remove router 180** |
| Catalog-based timeout? | **Yes** — env → session ops → catalog → default |
| UI early failure? | **No** — show **RUNNING / still generating** until true terminal timeout |
| Completion | **Multi-signal scored gate**; network + download button + video + text |
| Debug on timeout | **Mandatory bundle** under `artifact_root/runway_debug/` |
| Download | **A → B → C → D**; single Download click; no re-generate |
| Credits | **No extra generation**; allowlist clicks only |

---

## References

- `project_brain/PHASE_12J_C_STEP1_RUNWAY_DOWNLOAD_TRACE.md`
- `orchestrators/runway_browser_orchestrator.py`
- `core/video_provider_router.py` (180s override)
- `providers/runway_browser_support.py`
- `providers/runway_download_provider.py`
- `project_brain/PHASE_11E_RUNWAY_HARDENING_DESIGN_REPORT.md`
- Session: `exec_uat_20260602_080026`

**Next step:** Implementation approval for **12J-C2a** (timeout policy + router fix) as smallest risk-first slice.
