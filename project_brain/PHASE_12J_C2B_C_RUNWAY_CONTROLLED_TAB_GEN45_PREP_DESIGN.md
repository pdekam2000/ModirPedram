# PHASE 12J-C2B-C — Runway Controlled Tab + Gen-4.5 Prep Hardening Design

**Date:** 2026-06-02  
**Status:** Design freeze — no implementation, no code changes  
**Inputs:** `PHASE_12J_C2B_B_RUNWAY_PROMPT_INJECTION_TRACE.md`, `PHASE_12J_C2A_RUNWAY_BROWSER_OBSERVABILITY_REPORT.md`, `PHASE_12J_C_STEP2_RUNWAY_WAIT_DOWNLOAD_HARDENING_DESIGN.md`

---

## Purpose

Make Runway browser automation **deterministic** before prompt injection:

1. **Controlled tab** — always the Runway Gen-4.5 generate surface the operator can verify, never blind `context.pages[0]`.
2. **Gen-4.5 prep** — explicit, observable substeps with bounded waits and fail-loud diagnostics.
3. **Gate** — `fill_prompt()` / first keystroke only after `ready_for_prompt`.

**Out of scope (this design):** wait/download hardening (12J-C Step 2), prompt composer, browser launcher rewrite, API Runway mode, voice/subtitle/assembly.

---

## Problem Statement (12J-C2B-B Recap)

| Finding | Implication |
|---------|-------------|
| Dispatch + orchestrator + `run()` work | Fix target is **tab selection** and **prep**, not queue/router |
| Stalls with no typing | Worker blocked in **`prepare_gen45_page()`** or automating **wrong tab** |
| Some sessions reach `waiting_for_generation` | Path is viable; need **repeatable** tab + prep |
| `BrowserManager.launch()` uses `pages[0]` | Tab mismatch when operator watches another Runway tab (same URL, different index) |
| Monolithic `preparing_gen45_page` OBS step | Cannot tell which prep sub-step stalled |
| `open_runway()` always `goto` dashboard | Can disrupt operator who already sits on generate page |

---

## Design Principles

1. **Select before prep** — resolve controlled `Page` once after CDP attach; all prep and typing use that page only.
2. **Prefer reuse over navigation** — if a suitable generate tab exists, use it; minimize `goto` that disturbs unrelated tabs (ChatGPT, etc.).
3. **Probe, don’t spend** — prep may click navigation/model UI only; **never** click final **Generate** (credits).
4. **Fail loud with evidence** — per-step timeout → structured error + optional debug bundle (screenshot, DOM probes).
5. **Extend 12J-C2A-OBS** — granular prep substeps in session + UAT UI; no parallel observability system.
6. **No secrets in session** — safe URLs (path only, no query), titles, indices; no cookies/tokens/localStorage dumps.

---

## Architecture Placement

```text
ProviderRuntimeEngine._execute_clips()
  → VideoProviderRouter.generate_clips()
       → RunwayBrowserOrchestrator.run()
            → RunwayBrowserProvider.start()
                 → BrowserManager.launch()                    [CDP attach — unchanged entry]
                 → RunwayPageSelector.select_controlled_page()  [NEW — design]
                      → persist page + bring_to_front (safe)
            → RunwayGen45PrepEngine.run()                      [NEW — design]
                 → substeps (dashboard → … → ready_for_prompt)
                 → probes: prompt_box_found, generate_button_found (visibility only)
            → [clip loop] fill_prompt() only if prep.ready_for_prompt
```

**Proposed modules (implementation reference only):**

| Module | Responsibility |
|--------|----------------|
| `content_brain/execution/runway_page_selector.py` | Deterministic tab scoring + selection + front |
| `content_brain/execution/runway_gen45_prep_engine.py` | Substep state machine + timeouts + debug capture |
| `providers/runway_browser_provider.py` | Thin delegates to prep engine; keeps `fill_prompt` / `click_generate` |
| `automation/browser_manager.py` | CDP connect only; **no** `pages[0]` default in `launch()` return contract |
| `content_brain/execution/runway_browser_observability.py` | Extend step enum + prep probe fields |

**Unchanged:** `automation/browser_launcher.py`, `VideoProviderRouter` dispatch contract, `RunwayDownloadProvider`, wait loop (until 12J-C Step 2).

---

## 1. Controlled Tab Selection

### 1.1 Goals

- Never assign control via `context.pages[0]` alone.
- Prefer an **already-open Runway generate** tab that matches readiness heuristics.
- Else open or navigate to a **canonical generate surface** without touching non-Runway tabs.
- Persist selection for operator + UI.
- Bring selected tab to front when safe (visibility for supervised UAT).

### 1.2 Page inventory (all contexts)

After CDP attach, enumerate every `Page` in every `BrowserContext`:

```python
PageCandidate {
  global_index: int          # stable across contexts, 0..N-1
  context_index: int
  page_index_in_context: int
  safe_url: str              # scheme + host + path only
  title: str
  is_runway_host: bool
  is_auth_url: bool          # /login, /sign-in, /signup, auth.*
  is_generate_surface: bool  # URL path heuristic
  generate_surface_score: int
  workspace_signals: {       # DOM probes on that page only
    describe_your_shot: bool
    gen45_visible: bool
    textarea_count: int
    contenteditable_count: int
  }
}
```

### 1.3 URL heuristics (no query strings stored)

| Class | Path patterns (case-insensitive) | Score contribution |
|-------|----------------------------------|--------------------|
| **Generate surface (strong)** | `/ai-tools/generate`, `/tools/generate`, ends with `/generate` under `app.runwayml.com` | +100 |
| **Video tools (medium)** | `/video-tools/` and contains `generate` or `ai-tools` | +80 |
| **Runway app (weak)** | `app.runwayml.com` not auth | +20 |
| **Non-Runway** | anything else | excluded from selection |
| **Auth** | `/login`, `/sign-in`, `/signup`, `auth.` | excluded |

**Canonical fallback URL (navigation target when no candidate wins):**

```text
https://app.runwayml.com/
```

Then prep engine runs UI path (`open_generate_tools` → …) to reach generate surface.  
**Do not** hardcode team slug in config for v1; discover generate URL from **best existing tab** or post-login navigation.  
Optional v2: persist last successful `safe_url` pattern per operator profile metadata (path template only, no tokens).

Evidence from successful UAT:  
`https://app.runwayml.com/video-tools/teams/.../ai-tools/generate` — matcher uses `/ai-tools/generate` suffix, not full team path.

### 1.4 Selection algorithm (deterministic)

```
INPUT: all PageCandidates (Runway-only, non-auth)
OUTPUT: selected Page, selection_reason

1. FILTER: is_runway_host && !is_auth_url

2. RANK each candidate by total_score:
   total_score =
     generate_surface_score
     + (30 if workspace_signals.gen45_visible)
     + (25 if workspace_signals.describe_your_shot or textarea_count > 0)
     + (15 if workspace_signals.contenteditable_count > 0)
     + (10 if page appears focused — see 1.5)
     - (50 if URL is dashboard/home only and no workspace signals)

3. TIE-BREAK (stable ordering):
   a) Higher total_score
   b) Prefer URL with `/ai-tools/generate`
   c) Lower global_index (deterministic, documented — not “random”)
   d) Longer title match "Generative Session" (+5)

4. IF no candidate with total_score >= 40:
   → SELECTION_MODE = "navigate_canonical"
   → Use existing context; open NEW page OR reuse lowest-index Runway app tab
   → goto https://app.runwayml.com/ then prep engine navigates to generate
   ELSE:
   → SELECTION_MODE = "reuse_tab"
   → selected = top ranked page

5. NEVER select non-Runway tabs (ChatGPT, etc.) even if pages[0]

6. Persist + log:
   [RUNWAY_PAGE_SELECTED] mode=reuse_tab|navigate_canonical index=N score=S url=... reason=...
```

### 1.5 “Active tab” detection (safe, best-effort)

Playwright CDP does not always expose Chrome’s focused tab reliably across versions. Design uses **graded** signals:

| Signal | Weight | Notes |
|--------|--------|-------|
| `document.visibilityState === 'visible'` on page | +10 | evaluate on candidate |
| Page is most recently created Runway generate tab | +5 | optional heuristic |
| **Not used for v1** | — | OS window focus APIs (out of scope) |

**Bring to front (after selection):**

```text
selected_page.bring_to_front()
short settle (configurable, default 0.5s, max 2s)
re-run workspace_signals on selected page only
```

**Safety:** `bring_to_front` does not submit jobs or spend credits. Skip if `MODIR_RUNWAY_SKIP_BRING_TO_FRONT=true` (operator preference).

### 1.6 Persistence (extends 12J-C2A-OBS)

Add to `runway_browser_obs.controlled_page`:

| Field | Example |
|-------|---------|
| `selection_mode` | `reuse_tab` \| `navigate_canonical` |
| `selection_reason` | `ranked_generate_surface_score_125` |
| `page_index` | global index |
| `page_url` | safe path URL |
| `page_title` | trimmed title |
| `is_runway_url` | true |
| `generate_surface_match` | `ai-tools/generate` |
| `total_score` | 125 |
| `brought_to_front` | true/false |

Refresh `open_pages[]` with `controlled: true` on selected index only.

### 1.7 Contract change: `BrowserManager.launch()`

**Design intent:** `launch()` returns CDP browser + context; **does not** implicitly set `self.page = pages[0]`.  
`RunwayPageSelector` sets `BrowserManager.page` after selection.  
Backward-compat shim: orchestrator always calls selector immediately after `start()`.

---

## 2. Gen-4.5 Preparation — Step State Machine

Replace monolithic `prepare_gen45_page()` with explicit substeps. Map to OBS keys (extend `RUNWAY_BROWSER_STEPS` or nested `prep_step`).

### 2.1 Prep states (ordered)

| State key | Replaces (current) | Action summary |
|-----------|-------------------|----------------|
| `open_runway_dashboard` | `open_runway()` partial | Only if not already on generate surface: `goto` `https://app.runwayml.com/` + load settle |
| `open_generate_tools` | `click_generate_video_home()` | Enter video workspace / “Generate Video” if signals missing |
| `select_video_mode` | (implicit in workspace) | Confirm video workspace markers (`Describe your shot`, etc.) |
| `select_gen45_model` | `select_gen45()` | Select Gen-4.5 tab; Escape dismiss overlays first |
| `ensure_prompt_box_visible` | `click_try_it()` | Open prompt surface; skip if `is_prompt_box_ready()` |
| `ready_for_prompt` | (new gate) | Probes pass; **no** Generate click |

**Terminal success:** `ready_for_prompt == true`  
**Terminal failure:** `failed` with `prep_step`, `failure_code`, debug bundle path

### 2.2 Per-state behavior (high level)

```text
open_runway_dashboard
  IF controlled page already is_generate_surface AND workspace_signals OK:
    SKIP (log: skipped_dashboard_nav)
  ELSE:
    goto app.runwayml.com/ (domcontentloaded)
    settle

open_generate_tools
  IF is_video_workspace_ready(): SKIP
  ELSE: click "Generate Video" (existing selectors, region-safe)

select_video_mode
  ASSERT at least one of: Describe your shot, First Video Frame, Gen-4.5
  IF none after probe timeout: FAIL (BROWSER_AUTOMATION_NOT_READY)

select_gen45_model
  IF Gen-4.5 already selected (visible + active heuristic): SKIP
  ELSE: click_text_in_region / role selectors (existing)
  short settle (3s cap configurable)

ensure_prompt_box_visible
  IF is_prompt_box_ready(): SKIP
  ELSE: click Try it variants (existing selectors)
  re-probe prompt box

ready_for_prompt
  REQUIRE is_prompt_box_ready() == true
  PROBE generate_button_visible (DOM only — see 2.3)
  SET obs prep_step=ready_for_prompt
  ALLOW orchestrator to call fill_prompt()
```

### 2.3 Non-destructive probes (credits-safe)

| Probe | Method | Stored field |
|-------|--------|--------------|
| `prompt_box_found` | `textarea` \| `[contenteditable=true]` \| text “Describe your shot” count > 0 | bool |
| `generate_button_found` | Visible button/locator with text “Generate”, **no click** | bool |
| `gen45_model_found` | Text “Gen-4.5” visible in header region | bool |

**Explicit deny list during prep:**

- Do not call `click_generate()`
- Do not call `click_text_in_region("Generate", ...)`
- Do not press Enter on queue/submit shortcuts
- Do not upload assets or change billing settings

### 2.4 Skip / idempotency rules

| Condition | Skip steps |
|-----------|------------|
| Reuse tab + already on `/ai-tools/generate` + prompt box ready | dashboard, generate_tools, try_it |
| Gen-4.5 visible + prompt ready | select_gen45, ensure_prompt_box |
| Operator on workspace but wrong model | run select_gen45 only |

Logs: `[RUNWAY_PREP_SKIP] step=... reason=already_ready`

### 2.5 Orchestrator gate

```text
prep_result = RunwayGen45PrepEngine.run(page, obs, cancel_check)
IF NOT prep_result.ready_for_prompt:
  RAISE RunwayProviderError(code=BROWSER_AUTOMATION_NOT_READY, details={ prep_step, probes, debug_bundle })
# Only then:
for prompt in prompts:
  fill_prompt(prompt)
  ...
```

---

## 3. Timeout Behavior (Per Prep Step)

### 3.1 Configuration (env + session override pattern — align with `runway_browser_support`)

| Env key | Default | Purpose |
|---------|---------|---------|
| `RUNWAY_PREP_STEP_TIMEOUT_MS` | 15000 | Per-step Playwright action timeout (clicks, goto) |
| `RUNWAY_PREP_STEP_MAX_RETRIES` | 2 | Retries per step (not per selector infinite loop) |
| `RUNWAY_PREP_SETTLE_SECONDS` | 3 | Post-navigation / post-model select settle (cap 8) |
| `RUNWAY_PREP_TOTAL_BUDGET_SECONDS` | 120 | Whole prep phase budget (fail loud) |
| `RUNWAY_PAGE_SELECT_TIMEOUT_MS` | 8000 | Per-tab probe budget during inventory |

Session override (optional): `operations.runway_prep_policy` snapshot at dispatch — no secrets.

### 3.2 Per-step table

| Step | Max wait (single attempt) | Retries | Backoff | Fail-loud code |
|------|---------------------------|---------|---------|----------------|
| `open_runway_dashboard` | 15s goto + 8s settle | 1 retry goto | 2s | `PREP_DASHBOARD_NAV_TIMEOUT` |
| `open_generate_tools` | 15s per selector pass | 2 step retries | 1s between selectors | `PREP_GENERATE_TOOLS_CLICK_FAILED` |
| `select_video_mode` | 10s probe poll | 3 polls @ 2s | — | `PREP_VIDEO_WORKSPACE_NOT_READY` |
| `select_gen45_model` | 15s click + 3s settle | 2 | 1s | `PREP_GEN45_SELECT_FAILED` |
| `ensure_prompt_box_visible` | 15s click + 8s settle | 2 | 1s | `PREP_PROMPT_SURFACE_FAILED` |
| `ready_for_prompt` | 5s final probe | 0 | — | `PREP_NOT_READY_FOR_PROMPT` |

**Total budget:** If monotonic clock exceeds `RUNWAY_PREP_TOTAL_BUDGET_SECONDS`, abort with `PREP_TOTAL_BUDGET_EXCEEDED` even if step retries remain.

### 3.3 Fail-loud message shape

```text
[Runway Browser] Prep failed at step={prep_step} code={code} 
  controlled_tab={safe_url} prompt_box={bool} generate_visible={bool}
  debug_bundle={path}
```

`RunwayProviderError.details`:

```json
{
  "phase": "runway_gen45_prep",
  "prep_step": "select_gen45_model",
  "failure_code": "PREP_GEN45_SELECT_FAILED",
  "controlled_page": { "page_index": 0, "page_url": "..." },
  "probes": {
    "prompt_box_found": false,
    "generate_button_found": true,
    "gen45_model_found": false
  },
  "debug_bundle": "storage/.../video_generation/runway_debug/prep_{dispatch_id}_{step}/"
}
```

### 3.4 Debug capture on prep failure (align 12J-C Step 2)

**Only on prep failure** (not happy path):

| Artifact | Content |
|----------|---------|
| `screenshot.png` | Viewport of **controlled** page (no full-page scroll) |
| `page_state.json` | safe_url, title, prep_step, probes, open_pages summary |
| `dom_probe.json` | Counts: textareas, contenteditable, “Generate” buttons visible, “Gen-4.5” |
| `manifest.json` | timestamps, session_id, dispatch_id, step |

Path: `{artifact_root}/runway_debug/prep_{clip_index}_{prep_step}_{ts}/`

**Redaction:** No cookies, localStorage, network HAR, or screenshot of non-Runway tabs.

---

## 4. UI Observability

Extend existing UAT **Video Runtime** panel (12J-C2A) — no new page.

### 4.1 Session payload additions

Under `runway_browser_obs`:

```json
{
  "step": "preparing_gen45_page",
  "prep_step": "select_gen45_model",
  "prep_step_updated_at": "ISO-8601",
  "controlled_page": { "...": "see 1.6" },
  "probes": {
    "prompt_box_found": false,
    "generate_button_found": true,
    "gen45_model_found": true
  },
  "prep_ready": false
}
```

When gate opens: `prep_step: "ready_for_prompt"`, `prep_ready: true`, then transition to `filling_prompt`.

### 4.2 UAT UI display (under Video Runtime)

| Row | Source |
|-----|--------|
| Video Runtime | `video_runtime.state` → ACTIVE |
| Runway step | `runway_browser_obs.step` |
| **Prep step** | `runway_browser_obs.prep_step` |
| Controlled tab | `controlled_page.page_url` |
| Page title | `controlled_page.page_title` |
| Selection mode | `controlled_page.selection_mode` |
| Prompt box | `probes.prompt_box_found` → Yes/No |
| Generate button (visible) | `probes.generate_button_found` → Yes/No (not clicked) |
| Ready for prompt | `prep_ready` → Yes/No |

Optional: link to debug bundle path when `failed` + bundle exists (operator-only, local path).

### 4.3 Stdout tags (prep)

| Tag | When |
|-----|------|
| `[RUNWAY_PREP_STEP]` | Enter each prep substep |
| `[RUNWAY_PREP_SKIP]` | Skipped substep + reason |
| `[RUNWAY_PREP_PROBE]` | Probe results at ready_for_prompt |
| `[RUNWAY_PAGE_SELECTED]` | After selection (extended fields) |

---

## 5. Safety

| Rule | Enforcement |
|------|-------------|
| No Generate during prep | Prep engine code path has no import/call to `click_generate`; deny-list in prep module |
| No credits spent | No submit/queue actions; only navigation/model/prompt-surface UI |
| No credentials stored | OBS + debug bundle use safe_url only; no cookie/localStorage export |
| No auth automation | Launcher unchanged; login still manual pre-UAT |
| Controlled profile only | CDP attach to Modir Chrome profile (existing 12I-A) |
| Cancel cooperative | `check_cancel` at each prep substep boundary |
| Tab isolation | Selection scans all tabs but only **navigates/clicks** selected Runway page |

---

## 6. Validation Plan

### 6.1 Test matrix (manual supervised UAT)

| # | Chrome tabs open | Expected selection | Expected prep | Pass criteria |
|---|------------------|--------------------|---------------|---------------|
| V1 | ChatGPT + Runway home + Runway generate (ready) | Reuse generate tab (highest score) | Skips dashboard; may skip try_it | OBS `selection_mode=reuse_tab`; typing on visible tab; `ready_for_prompt` before `[RUNWAY_PROMPT_TYPING_START]` |
| V2 | Only ChatGPT + Runway home | Reuse Runway home → navigate via prep | Full prep chain | Ends on generate surface; not ChatGPT |
| V3 | Two Runway generate tabs (duplicate URL) | Deterministic lower `global_index` | Prep skips or minimal | Same URL both tabs; control stable across runs |
| V4 | Single Runway generate, prompt already visible | Reuse + skip try_it/dashboard | Fast path | `prep_step` advances to `ready_for_prompt` in &lt; 30s |
| V5 | Runway logged out tab (auth URL) | Excluded; open canonical | Fail loud at dashboard or login probe | Clear `PREP_*` or pre-dispatch `validate_runway_browser_operator_ready` |
| V6 | No Runway tabs (only ChatGPT) | `navigate_canonical` | Full prep from dashboard | Generate surface reached; prompt typing visible |

### 6.2 Observability checks

- [ ] UAT UI shows **Prep step** updating through all six states on V2/V6.
- [ ] **Controlled tab** URL matches tab that receives keystrokes (operator visual confirm after `bring_to_front`).
- [ ] `prompt_box_found: true` only when `ready_for_prompt` set.
- [ ] `generate_button_found` may be true before prep complete; **no** `generate_clicked` OBS until after `fill_prompt` path in clip loop.

### 6.3 Failure injection checks

- [ ] Block “Gen-4.5” UI → fail at `select_gen45_model` with screenshot bundle.
- [ ] Close prompt panel → fail at `ensure_prompt_box_visible` with fail-loud code.
- [ ] Verify session → `FAILED` with `failure_code` and `prep_step` preserved.

### 6.4 Regression guards

- [ ] Sessions that previously reached `waiting_for_generation` still complete (V1/V4).
- [ ] 12J-C2a wait authority (900s) unchanged — prep design does not alter wait loop.
- [ ] `validate_runway_browser_operator_ready` still runs **before** dispatch (unchanged).

### 6.5 Automated validator (future implementation phase)

`project_brain/validate_12j_c2b_c_runway_tab_prep_design.py` — static checks:

- Page selector module exists with scoring tests (fixture URLs).
- Prep state enum matches design table.
- No `click_generate` reference in prep engine.
- OBS schema includes `prep_step` + `probes`.

---

## Migration From Current Code

| Current | Target |
|---------|--------|
| `BrowserManager.launch()` → `pages[0]` | Selector sets page |
| `prepare_gen45_page()` monolith | `RunwayGen45PrepEngine.run()` |
| OBS `preparing_gen45_page` only | `prep_step` substeps + legacy `step` for coarse phase |
| `open_runway()` unconditional goto | Conditional `open_runway_dashboard` |
| `record_controlled_page()` at connect | `record_controlled_page()` **after** selection + bring_to_front |

**Implementation order (recommended, not this phase):**

1. `RunwayPageSelector` + OBS persistence + bring_to_front flag  
2. `RunwayGen45PrepEngine` + per-step timeouts + fail-loud  
3. UAT UI prep rows + debug bundle on prep fail  
4. Deprecate `pages[0]` assignment in `BrowserManager`  

---

## Relationship to Other Phases

| Phase | Relationship |
|-------|----------------|
| **12J-C2A-OBS** | Extend schema; keep single `runway_browser_obs` object |
| **12J-C2B-B** | Addresses root causes identified in trace audit |
| **12J-C Step 2** | Wait/download hardening runs **after** `ready_for_prompt` + `click_generate` in clip loop |
| **12J-C2e (UI substate)** | Prep substeps satisfy “runway_wait vs prep” clarity for operators |

---

## Open Questions (for implementation approval)

1. **Team-scoped generate URL cache** — store last successful path template in operator metadata (v2)?  
2. **New tab vs navigate** — when no generate tab exists, prefer `context.new_page()` vs reusing Runway home tab? Design default: reuse lowest-index Runway app tab, else `new_page()`.  
3. **bring_to_front default** — on for UAT supervised runs only, or always when `confirm_real_video`?

---

## Summary

| Area | Design decision |
|------|-----------------|
| Tab control | Ranked selection over all CDP pages; never `pages[0]`; reuse generate tab first |
| Prep | Six named substeps ending in `ready_for_prompt` |
| Timeouts | Per-step 15s / retries 2 / total budget 120s / fail-loud + debug bundle |
| UI | Prep step + probes + controlled tab in existing UAT Video Runtime panel |
| Safety | No Generate, no credentials, probe-only generate button visibility |
| Validation | Six-scenario tab matrix + OBS gates before prompt typing |

**No code changes in this phase.** Implementation requires separate approval per ModirAgentOS architecture rules.
