# PERF-A Storage Audit Report

**Date:** 2026-06-02  
**Session under review:** `exec_uat_20260602_205154`  
**Issue:** `report_perf_a_runway_timings.py --session-id exec_uat_20260602_205154` fails with `FileNotFoundError`, while artifact folder exists.

---

## Executive summary

| Finding | Detail |
|---------|--------|
| **Report script failure cause** | Wrong `ExecutionSessionStore` root path (not missing session file) |
| **Session JSON exists** | Yes — on disk at correct path |
| **Artifact folder** | Separate tree; does **not** contain PERF-A data |
| **PERF-A in this session** | **No** — no `perf_clips`, no `runway_browser_obs`, no `last_perf_report` |
| **Any UAT session with `perf_clips`** | **None** found under `storage/content_brain/execution/sessions/` |

---

## 1. Where does PERF-A store `perf_clips`?

PERF-A does **not** write under `storage/content_brain/execution/artifacts/`.

It persists only through **`RunwayBrowserObservability.record_perf_report()`**, which calls `_persist()` and merges into the **execution session JSON**:

| Field | Path in session document |
|-------|---------------------------|
| Primary | `execution_runtime.operations.runway_browser_obs.perf_clips` |
| Mirror | `execution_runtime.category_runtime.video_generation.runway_browser_obs.perf_clips` |
| Latest single-clip snapshot | `execution_runtime.operations.runway_browser_obs.last_perf_report` |

**Shape:**

```json
"perf_clips": [
  {
    "clip_index": 1,
    "perf_timestamps": {
      "perf_version": "perf_a_v1",
      "marks_monotonic": { "generate_click": 0.0, "video_visible_in_ui": 12.3, ... },
      "timestamps_iso": { "generate_click": "2026-06-02T...", ... },
      "durations_seconds": { "generate_click_to_video_visible_in_ui": 12.3, ... }
    }
  }
]
```

**When it is written:** End of each successful clip in `RunwayBrowserOrchestrator.run()`, after `download_video_url()` completes (`record_perf_report()`). Clips that fail during **wait** (no download) never call `record_perf_report()`.

**Stdout only:** `[RUNWAY_PERF]` log lines are not stored in artifacts; they are console output unless captured externally.

---

## 2. Is it stored in `session_store` only?

**Yes.** Persistence is exclusively via `ExecutionSessionStore.save_session()` into:

`storage/content_brain/execution/sessions/<execution_session_id>.json`

There is no separate `perf_clips.json`, no artifact-side perf file, and no runtime audit line for PERF-A in `storage/content_brain/execution/runtime/audit.jsonl` from this feature.

---

## 3. Is it stored in `execution_runtime.operations.runway_browser_obs.perf_clips`?

**That is the canonical location** (plus mirror under `category_runtime.video_generation`).

Code reference: `content_brain/execution/runway_browser_observability.py` — `record_perf_report()` → `_merge_clip_perf_report()` → `_persist()` sets `operations["runway_browser_obs"]` and copies the same merged object into `category_runtime[CATEGORY_VIDEO]`.

**Requires:** `build_runway_browser_observability(store, session_id, provider="runway_browser")` to be non-null (store + session_id + runway_browser provider).

---

## 4. Why does `report_perf_a_runway_timings.py` fail when the artifact folder exists?

### Two separate problems

#### A) `FileNotFoundError` (what you saw)

The report script constructs the store incorrectly:

```python
# report_perf_a_runway_timings.py (current)
store = ExecutionSessionStore(ROOT / "storage" / "content_brain" / "execution" / "sessions")
```

`ExecutionSessionStore.__init__(project_root)` **always** resolves sessions as:

`project_root / "storage" / "content_brain" / "execution" / "sessions"`

So the report script looks for:

`.../execution/sessions/storage/content_brain/execution/sessions/exec_uat_20260602_205154.json`

That path does **not** exist. The real file is:

`C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\sessions\exec_uat_20260602_205154.json`

**Proof:** With `ExecutionSessionStore(ROOT)` the session loads; with the report script path it raises `FileNotFoundError`.

The **artifact folder** (`storage/content_brain/execution/artifacts/exec_uat_20260602_205154/`) is unrelated to session loading. It only holds video-stage outputs (e.g. `prompt_bundle.json`, clip files if any). The report tool never reads artifacts.

#### B) After fixing the path — still no PERF report

With the correct store root, `report_from_session()` would return exit code **1** and print:

`No PERF-A data in session exec_uat_20260602_205154.`

because this session has no `perf_clips` and no `last_perf_report` (see §6–8).

---

## 5. Which session file should contain `perf_clips`?

For UAT session `exec_uat_20260602_205154`:

| Expected file |
|---------------|
| `storage/content_brain/execution/sessions/exec_uat_20260602_205154.json` |

**Not:**

- `artifacts/exec_uat_20260602_205154/...`
- `runtime/logs/...`
- `project_brain/...`

---

## 6. Does `exec_uat_20260602_205154` contain PERF-A timestamps?

**No.**

Audit of the live session file:

| Check | Result |
|-------|--------|
| `execution_runtime.operations.runway_browser_obs` | **Absent** (no key at all) |
| `perf_clips` | **Not present** anywhere in file |
| `last_perf_report` | **Not present** |
| `RUNWAY_PERF` / `perf_timestamps` | **No matches** in JSON |
| Repo-wide `perf_clips` in `storage/` | **Zero** matches across all session JSON files |

Session metadata:

- `execution_session_id`: `exec_uat_20260602_205154`
- `state`: `FAILED`
- `provider`: `runway_browser`
- UAT error: `Real Runway output not detected (clip 2)` (12J-E1 wait failure)
- `updated_at`: `2026-06-02 21:20:38`

`execution_runtime.operations` contains: `uat_run`, `voice_preflight_dry_run`, `voice_approval_gate`, `failover_advisory` — **not** `runway_browser_obs`.

---

## 7. Exact path (session file — exists)

```
C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\sessions\exec_uat_20260602_205154.json
```

## 8. Exact path for PERF-A data in this session

**None.** There is no path containing PERF-A timestamps for `exec_uat_20260602_205154`.

---

## Why this UAT run has no PERF-A data (even if code exists now)

Plausible explanations (consistent with session contents):

1. **Run ended on clip 2 wait failure** — `record_perf_report()` runs only after a **completed download** per clip. Failure at `wait_for_generated_video_url` (clip 2) means no perf block for that clip; clip 1 would only have perf if it fully downloaded and observability persisted.

2. **No `runway_browser_obs` block at all** — suggests either observability never persisted during this run (e.g. run predates wiring, or no successful `_persist` path), or session was saved without that subtree. Grep shows **no** `exec_uat*.json` session contains `runway_browser_obs`.

3. **PERF-A is session-only** — artifact directory only has:
   - `storage/content_brain/execution/artifacts/exec_uat_20260602_205154/video_generation/prompt_bundle.json`
   - (no perf JSON, no timing files)

4. **Report script path bug** — masks the above: operator sees “session not found” instead of “session found, no perf_clips”.

---

## Artifact vs session (this run)

| Location | Purpose | PERF-A? |
|----------|---------|--------|
| `artifacts/exec_uat_20260602_205154/video_generation/` | Prompt bundle, clip media | **No** |
| `sessions/exec_uat_20260602_205154.json` | Full execution + UAT state | **No perf_clips** |

---

## How to verify after next UAT (correct store + expectations)

```bash
# Correct report invocation (project root as store argument — requires script fix)
python project_brain/report_perf_a_runway_timings.py --session-id exec_uat_<new_id>
```

Or inspect JSON directly:

```text
execution_runtime.operations.runway_browser_obs.perf_clips[]
execution_runtime.operations.runway_browser_obs.last_perf_report
```

Expect `[RUNWAY_PERF]` in terminal during Runway clips when PERF-A code is active.

---

## Related bug (same class)

`project_brain/validate_perf_a_runway_stage_timestamps.py` uses:

`ExecutionSessionStore(session_path.parent)` where `session_path.parent` is the **sessions directory**, not project root — same double-path issue as the report script.

---

## Recommendations (audit only — no code applied)

1. Fix `report_perf_a_runway_timings.py` to use `ExecutionSessionStore(ROOT)` (project root, not `sessions/` subfolder).
2. Re-run 40s UAT with PERF-A deployed; confirm `runway_browser_obs` appears in session during `RUNNING`.
3. For failed clips, expect perf only for clips that **complete download**; wait-timeout failures will not populate `perf_clips` for that clip.
4. Do not look for PERF-A under `artifacts/` — it will never appear there by design.

---

## Answer index

| # | Question | Answer |
|---|----------|--------|
| 1 | Where stored? | Session JSON only, under `runway_browser_obs.perf_clips` |
| 2 | session_store only? | Yes |
| 3 | `operations.runway_browser_obs.perf_clips`? | Yes (canonical) |
| 4 | Why report fails? | Wrong store path; artifacts irrelevant |
| 5 | Which session file? | `sessions/exec_uat_20260602_205154.json` |
| 6 | Contains PERF-A? | **No** |
| 7 | Exact path if yes | N/A |
| 8 | If no, why? | No observability/perf persisted; clip 2 wait fail; perf not in artifacts |
