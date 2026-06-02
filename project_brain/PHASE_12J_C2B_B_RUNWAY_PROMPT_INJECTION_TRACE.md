# PHASE 12J-C2B-B — Runway Prompt Injection Trace

**Date:** 2026-06-02  
**Status:** Audit only — no fixes, no implementation  
**Symptom:** Video Runtime `ACTIVE`, Runway browser open/logged in/on generate page, but **no prompt typing** and **no Generate click** visible to operator.  
**Conclusion class:** Failure occurs **before** first prompt keystroke **or** automation runs on a **different CDP tab** than the one the operator watches.

**Related:** `PHASE_12J_C2A_VIDEO_RUNTIME_STALL_AUDIT.md`, `PHASE_12J_C2A_RUNWAY_BROWSER_OBSERVABILITY_REPORT.md`

---

## Executive Summary

The only function that injects prompt text is **`RunwayBrowserProvider.fill_prompt()`**, specifically **`page.keyboard.type(prompt, delay=5)`**. It is invoked only from **`RunwayBrowserOrchestrator.run()`** after **`prepare_gen45_page()`** completes.

For supervised UAT, the call stack is **fully synchronous** on a **daemon background thread**. There is **no** queue wait after `DEQUEUED`, **no** asyncio `Future`, and **no** provider-runtime mutex on the Runway path. `RUNNING` is persisted **before** `_execute_clips()` begins, so the UI can show Video Runtime **ACTIVE** while Playwright is still in page-prep (pre-keystroke).

**Most likely pre-injection blockers (code order):**

1. **`prepare_gen45_page()`** sub-step — `open_runway()`, `click_generate_video_home()`, `select_gen45()`, or `click_try_it()` (Playwright `goto` / `_click_first` with 15s click timeouts).
2. **Tab mismatch** — automation uses `context.pages[0]`; operator may watch another tab at the same Runway URL (seen in session `exec_uat_20260602_110110` with two generate tabs).

---

## Required Trace (Call Graph)

```text
run_uat_pipeline()                          [UAT daemon thread]
  └─ _update_uat_progress("Running video stage.")
  └─ _run_video_stage()                     content_brain/execution/uat_runtime_engine.py:314
       ├─ validate_runway_browser_operator_ready()   [PRE-dispatch; CDP + login probe]
       ├─ uat_runway_queue_and_dispatch_prepare()  [enqueue + dequeue; must be DEQUEUED]
       └─ ProviderRuntimeEngine.dispatch_by_id()    :368 → dispatch() :213
            ├─ validate_dispatch_eligibility()
            ├─ resolve_video_provider() → runway_browser
            ├─ SessionPromptAdapter.build() → prompts[]
            ├─ save DISPATCHED
            ├─ save RUNNING  ◄── UI: Video Runtime ACTIVE
            └─ _execute_clips()                  :356
                 └─ VideoProviderRouter.generate_clips()   core/video_provider_router.py:14
                      ├─ log_runway_wait_config()
                      ├─ RunwayBrowserOrchestrator(...)   :51  ◄── Q1: instantiated here
                      └─ orchestrator.run(prompts)        :56  ◄── Q2: entered here
                           ├─ RunwayBrowserProvider.start()
                           │    └─ BrowserManager.launch() → pages[0]
                           ├─ prepare_gen45_page()         ◄── Q6: common blocker BEFORE fill_prompt
                           │    ├─ open_runway()
                           │    ├─ click_generate_video_home()
                           │    ├─ select_gen45()
                           │    └─ click_try_it()
                           └─ [CLIP loop]
                                ├─ clip_obs.set_step("filling_prompt")  [12J-C2A-OBS]
                                ├─ fill_prompt(prompt)              ◄── Q4/Q5: injection gate
                                │    ├─ print "[Runway Browser] Filling prompt..."
                                │    ├─ [RUNWAY_PROMPT_TYPING_START]
                                │    ├─ box.wait_for(5000)
                                │    ├─ box.click(force=True)
                                │    ├─ keyboard Control+A / Backspace
                                │    └─ page.keyboard.type(...)     ◄── Q10: FIRST KEYSTROKE
                                ├─ apply_default_settings()
                                └─ click_generate()
```

---

## Execution Path With Timestamps

Timestamps are taken from session JSON / audit where available. **Stdout lines are not persisted** to the session; they exist only on the **UAT worker thread** console (not uvicorn API logs).

### Reference session A — pre-injection stall pattern (`exec_uat_20260602_105348`)

| Phase | Timestamp (local) | Entered | Exited | Evidence |
|-------|-------------------|---------|--------|----------|
| UAT video stage start | ~10:53:48 | `_run_video_stage` | — | `progress_log`: "Running video stage." |
| Pre-dispatch browser probe | ~10:53:48–50 | `validate_runway_browser_operator_ready` | ✓ | Dispatch reached; would have raised if CDP/login failed |
| Queue bridge | ~10:53:50 | `uat_runway_queue_and_dispatch_prepare` | ✓ | `state_history`: QUEUED → DEQUEUED |
| Dispatch + RUNNING | **10:53:50** | `ProviderRuntimeEngine.dispatch` | — still open | `running_at`, audit `RUNNING`, no `completed_at` |
| Provider execution | ≥10:53:50 | `_execute_clips` → router → orchestrator | **not exited** | `category_runtime.video_generation.executed: false`, no `runway_clip_*.mp4`, no `runway_browser_obs` (OBS not written = likely never passed early OBS steps or session predates OBS) |
| Prompt injection | — | `fill_prompt` | **not reached** (inferred) | No typing/Generate observed; no failure record yet |

### Reference session B — post-injection (`exec_uat_20260602_110110`, with 12J-C2A-OBS)

| Phase | Timestamp | Step / note |
|-------|-----------|-------------|
| RUNNING | 11:01:12 | `running_at` |
| Page selected | — | Controlled: `.../ai-tools/generate`, title `Generative Session \| Runway AI` |
| **Past injection** | 09:01:46Z (UTC) | `runway_browser_obs.step`: **`waiting_for_generation`**, `clip_index: 1` |

Session B proves the path **can** reach keystroke + Generate + wait; operator “no typing” on a **different** run may be tab mismatch or a **105348-class** stall still inside `prepare_gen45_page()`.

### Synthetic timeline (any RUNNING / no-typing run)

| T+ | Function | Typical stdout / persisted marker |
|----|----------|-----------------------------------|
| T0 | `_run_video_stage` entry | `[UAT_RUNWAY_EXECUTION] dispatch_started=True` |
| T1 | `dispatch` eligibility + adapter | `prompt_bundle.json` written |
| T2 | `dispatch` RUNNING save | Audit `RUNNING`; UAT poll shows Video ACTIVE |
| T3 | `VideoProviderRouter.generate_clips` | `VIDEO PROVIDER ROUTER` |
| T4 | `RunwayBrowserOrchestrator.__init__` | `[RUNWAY_WAIT_CONFIG] wait_seconds=900 ...` |
| T5 | `orchestrator.run` entry | `[Runway Browser Orchestrator] STARTED` |
| T6 | `provider.start` | `[BrowserManager] Download path: ...` |
| T7 | `prepare_gen45_page` start | `[RUNWAY_STEP] preparing_gen45_page` (if OBS on) |
| T7a | `open_runway` | `[Runway Browser] Opening Runway dashboard...` |
| T7b | `click_generate_video_home` | `Checking Generate Video...` / `Already inside video workspace.` |
| T7c | `select_gen45` | `Selecting Gen-4.5 top tab...` |
| T7d | `click_try_it` | `Clicking Try it...` / `Prompt box already ready. Skipping Try it.` |
| T8 | Clip loop | `[Runway Browser] CLIP 1` |
| T9 | **Pre-keystroke** | `[Runway Browser] Filling prompt...` / `[RUNWAY_PROMPT_TYPING_START]` |
| **T10** | **First keystroke** | `page.keyboard.type(prompt, delay=5)` inside `fill_prompt` |

**Current blocking function (when symptom = no typing, RUNNING, no `filling_prompt` step):**  
One of **`prepare_gen45_page`’s callees** (still inside T7a–T7d), or **`BrowserManager.launch()`** / **`connect_over_cdp`** immediately before T7.

**Current blocking function (when OBS shows `waiting_for_generation` but operator sees idle UI):**  
Not pre-injection — either **wrong tab** or **post-submit wait** (`wait_for_generated_video_url`, up to 900s).

---

## Answers to Required Questions

### 1. Is `RunwayBrowserOrchestrator` actually instantiated?

**Yes**, when `provider_override` resolves to `runway_browser`.

```44:56:core/video_provider_router.py
        if provider_name == "runway_browser":
            ...
            orchestrator = RunwayBrowserOrchestrator(
                wait_seconds=wait_seconds,
                runway_obs=runway_obs,
            )
            return call_with_optional_cancel_check(orchestrator.run, prompts, cancel_check=cancel_check)
```

Instantiation occurs **inside** `VideoProviderRouter.generate_clips()`, called from `ProviderRuntimeEngine._execute_clips()` after session is already `RUNNING`.

---

### 2. Is `orchestrator.run()` entered?

**Yes — inferred whenever** `execution_runtime.state == RUNNING`, `provider_resolved == runway_browser`, and dispatch has not failed with `execution_runtime.failure`.

`dispatch()` calls `_execute_clips()` synchronously; router immediately calls `orchestrator.run()`. There is no alternate async entry.

Entry marker:

```58:61:orchestrators/runway_browser_orchestrator.py
        print("\n" + "=" * 60)
        print("[Runway Browser Orchestrator] STARTED")
```

If this line never appears, the stall is **before** orchestrator (unlikely once RUNNING) or logs are on the **daemon thread**, not the API terminal.

---

### 3. What is the last log line emitted before stall?

**Depends on stall depth** (stdout only unless 12J-C2A-OBS persisted a step).

| Stall region | Last expected stdout line | Last persisted UAT log (typical) |
|--------------|---------------------------|----------------------------------|
| Before orchestrator | `[RUNWAY_WAIT_CONFIG] wait_seconds=...` | `"Running video stage."` |
| CDP / launch | `[BrowserManager] Download path: ...` | same |
| Page prep | `[Runway Browser] Selecting Gen-4.5...` or `Clicking Try it...` or `Opening Runway dashboard...` | same |
| **Immediately before first keystroke** | **`[Runway Browser] Filling prompt...`** then **`[RUNWAY_PROMPT_TYPING_START]`** | OBS: `filling_prompt` |
| After injection (different symptom) | `[Runway Browser] Waiting for generated video URL...` | OBS: `waiting_for_generation` |

For **no typing / no Generate** (pre-injection), the last line is **not** `Filling prompt...` — it is the **last `prepare_gen45_page` sub-step print** still running or blocked inside Playwright.

---

### 4. Which function performs prompt injection?

**`RunwayBrowserProvider.fill_prompt()`** in `providers/runway_browser_provider.py`.

**First keystroke (exact):**

```167:169:providers/runway_browser_provider.py
                        self.page.keyboard.press("Control+A")
                        self.page.keyboard.press("Backspace")
                        self.page.keyboard.type(prompt, delay=5)
```

Caller:

```102:104:orchestrators/runway_browser_orchestrator.py
                if clip_obs is not None:
                    clip_obs.set_step("filling_prompt")
                provider.fill_prompt(prompt)
```

There is **no** other prompt-injection path on the `runway_browser` branch (composer only rewrites session prompts **before** dispatch).

---

### 5. Is that function called?

**Not yet** on runs that stall in `prepare_gen45_page()` (symptom: correct page visually, no typing).

**Yes** on runs that reach later OBS steps — e.g. `exec_uat_20260602_110110` with `step: waiting_for_generation` (injection and Generate already occurred on the automation timeline).

**Detection:**

| Signal | `fill_prompt` called? |
|--------|------------------------|
| Stdout `[Runway Browser] Filling prompt...` | Yes |
| `[RUNWAY_PROMPT_TYPING_START]` | Yes |
| OBS `step == filling_prompt` | Yes |
| OBS `step` ∈ {`generate_clicked`, `waiting_for_generation`, ...} | Yes (downstream of fill) |
| RUNNING, none of above, operator sees idle UI | **No** (or ran on another tab) |

---

### 6. If not called, what condition blocks it?

`fill_prompt()` runs only after **`prepare_gen45_page()` returns**. Anything that prevents return blocks injection:

| Blocker | Location | Mechanism |
|---------|----------|-----------|
| **A. Page prep loop** | `prepare_gen45_page()` → `open_runway` / `click_generate_video_home` / `select_gen45` / `click_try_it` | Sync Playwright; `_click_first` retries selectors with **`click(timeout=15000)`** and **1s sleep** between attempts |
| **B. Navigation wait** | `open_runway()` | `page.goto` + `wait_for_load_state("domcontentloaded", timeout=15000)` + **`browser_page_settle_seconds()` default 8s** |
| **C. Early exception** | Any prep step | Raises `RunwayProviderError` → dispatch would eventually mark **FAILED** (if exception propagates) |
| **D. Cancel** | `check_cancel()` | Cooperative cancel → `RunwayCancelledError` |
| **E. Tab mismatch (logical)** | `BrowserManager.launch()` | Prep/typing on **`context.pages[0]`** while operator watches another tab — prep may “succeed” on wrong surface while visible tab stays idle |
| **F. Operator already on workspace** | `is_video_workspace_ready()` / `is_prompt_box_ready()` | May **skip** clicks but still runs `open_runway()` (always navigates to dashboard first) — can disrupt manual tab state |

**Not a blocker:** queue/dequeue (completed pre-dispatch), `validate_runway_browser_operator_ready` (completed pre-dispatch), prompt composer (off unless flag), `skip_provider_execution` (UAT real run uses `False`).

```284:292:providers/runway_browser_provider.py
    def prepare_gen45_page(self):
        check_cancel(self._cancel_check, "prepare_page")
        self.open_runway()
        ...
        self.click_generate_video_home()
        ...
        self.select_gen45()
        ...
        self.click_try_it()
```

---

### 7. Is a lock/mutex/semaphore preventing execution?

**No Runway-specific lock** on the dispatch → orchestrator → provider path.

| Mechanism | Scope | Blocks prompt injection? |
|-----------|--------|-------------------------|
| `UATRuntimeEngine._global_lock` | Only `_claim_active` / `_release_active` for one UAT session id | **No** during `run_uat_pipeline` body |
| Playwright sync API | Blocks **only the UAT daemon thread** | Can **look** like a hung system, but not waiting on another thread’s lock |
| `ExecutionSessionStore` file writes | Per `save_session` | No cross-process mutex in code reviewed |

Grep: no `Semaphore` / `threading.Lock` in `orchestrators/`, `core/video_provider_router.py`, or `provider_runtime_engine` Runway path.

---

### 8. Is provider dispatch waiting on another future/task?

**No.**

- UAT API: `threading.Thread(target=_worker, daemon=True).start()` — fire-and-forget, **no** `join()` on dispatch.
- Inside worker: **`dispatch_by_id` → `_execute_clips` → `router.generate_clips` → `orchestrator.run`** is a **single synchronous stack**.
- No `asyncio`, no `concurrent.futures` wait, no background provider job handle.

The API returns immediately; the **worker thread** blocks inside Playwright until `run()` finishes or raises.

---

### 9. Is browser readiness check hanging?

**Pre-dispatch:** `validate_runway_browser_operator_ready()` uses `get_browser_operator_status(probe_login=True)`. It runs **once** before `dispatch_by_id`. If it hung, **`RUNNING` would not be reached**. Operator report (logged in, controlled profile) implies this **completed**.

**During execution (where stall actually occurs):**

| Check | When | Hang risk |
|-------|------|-----------|
| `get_browser_operator_status` | Pre-dispatch | Low once RUNNING |
| `BrowserManager.launch()` → `connect_over_cdp` | `provider.start()` | Can block on CDP (Playwright default timeouts) |
| `open_runway` load state | `prepare_gen45_page` | Up to **15s** + **8s settle** |
| `is_video_workspace_ready` / `is_prompt_box_ready` | Prep branches | DOM **count** queries — fast unless page dead |
| `_click_first` | Prep clicks | **Up to 15s per selector attempt** — **primary hang candidate** |

There is **no** continuous “readiness gate” loop between RUNNING and `fill_prompt`.

---

### 10. Exact line/function immediately before prompt typing

**Call chain (last three frames before keystroke):**

1. `RunwayBrowserOrchestrator.run` — `provider.fill_prompt(prompt)`  
   `orchestrators/runway_browser_orchestrator.py` **line 104**

2. `RunwayBrowserProvider.fill_prompt` — after selector loop finds a box:  
   - **line 163:** `box.wait_for(timeout=5000)`  
   - **line 164:** `box.click(force=True)`  
   - **lines 167–168:** `Control+A`, `Backspace`  

3. **First keystroke — line 169:** `self.page.keyboard.type(prompt, delay=5)`

**Last log lines before keystroke:**

```137:140:providers/runway_browser_provider.py
        print("[Runway Browser] Filling prompt...")
        if self._runway_obs is not None and hasattr(self._runway_obs, "log_prompt_typing_start"):
            self._runway_obs.log_prompt_typing_start()
```

---

## Entered / Exited / Blocking Summary

| Function | Entered when | Exited when | Can block pre-keystroke? |
|----------|--------------|-------------|---------------------------|
| `_run_video_stage` | UAT video stage | `dispatch_by_id` returns | Only via dispatch failure |
| `ProviderRuntimeEngine.dispatch` | `dispatch_by_id` | After `_execute_clips` returns | **Yes** — entire browser run |
| `VideoProviderRouter.generate_clips` | `_execute_clips` | `orchestrator.run` returns | **Yes** |
| `RunwayBrowserOrchestrator.run` | Router calls | All clips downloaded or exception | **Yes** |
| `RunwayBrowserProvider.start` | Start of `run` | `launch()` returns page | **Yes** — CDP |
| `prepare_gen45_page` | Before clip loop | All four sub-steps return | **Yes — primary** |
| `fill_prompt` | After prep | Return or raise | Only if never entered |
| `page.keyboard.type` | Inside `fill_prompt` | After typing completes | N/A if not reached |

**Blocking function for reported symptom (no typing, no Generate, RUNNING):**  
**`RunwayBrowserProvider.prepare_gen45_page()`** (or its child **`_click_first` / `open_runway`**) — **not** `fill_prompt`.

---

## Tab Mismatch Note (Operator vs Playwright)

```40:44:automation/browser_manager.py
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()
```

Session `exec_uat_20260602_110110` recorded **two** tabs on the same generate URL; **index 0** controlled, **index 1** not. Operator may watch tab 1 while automation types on tab 0 — matches “correct page” visually with **no typing** on the watched tab.

---

## Diagnostic Checklist (Audit Validation)

1. On UAT worker console (not API uvicorn), confirm order: `Orchestrator STARTED` → prep logs → `CLIP 1` → `Filling prompt...`.
2. If OBS enabled: last `runway_browser_obs.step` before stall — `preparing_gen45_page` vs `filling_prompt`.
3. Compare OBS **Controlled tab** index/URL to the tab you are watching in Chrome.
4. If step is `waiting_for_generation`, injection already happened — investigate wait/tab, not prompt gate.

---

## Files Referenced

| File | Role |
|------|------|
| `content_brain/execution/uat_runtime_engine.py` | `_run_video_stage`, UAT thread |
| `content_brain/execution/uat_real_video_bridge.py` | Pre-dispatch browser + queue bridge |
| `content_brain/execution/provider_runtime_engine.py` | `dispatch`, `_execute_clips`, RUNNING ordering |
| `core/video_provider_router.py` | Orchestrator instantiation |
| `orchestrators/runway_browser_orchestrator.py` | `run`, clip loop |
| `providers/runway_browser_provider.py` | `prepare_gen45_page`, `fill_prompt`, keystroke |
| `automation/browser_manager.py` | `pages[0]` selection |
| `providers/runway_browser_support.py` | Timeouts / settle seconds |

---

## Out of Scope (Per Phase)

- No code changes  
- No wait/download hardening  
- No prompt composer changes  
- No browser launcher changes
