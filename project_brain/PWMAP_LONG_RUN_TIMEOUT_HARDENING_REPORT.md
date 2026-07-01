# PWMAP Long-Run Timeout Hardening Report

**Phase:** `PWMAP-LONG-RUN-TIMEOUT-HARDENING`  
**Date:** 2026-06-27  
**Reference failure:** `pwmap_20260626T203630_17bb74ed` (60s / 4 clips — Clip 2 timed out at 900s)

---

## Problem

Multi-clip Product Studio runs were launched with a fixed **900s per-clip** timeout and a **3600s** ModirAgentOS subprocess cap. A 60s (4-clip) run exceeded the per-clip budget on Clip 2. Clip 1 downloaded successfully but no partial artifacts were written, and Results could fall back to an older successful 30s run.

---

## Solution Summary

| Area | Change |
|------|--------|
| Per-clip timeout | Scale by clip count: 900 / 1200 / 1500 / 1800 |
| Subprocess timeout | `(per_clip_timeout × clip_count) + 900` |
| Env overrides | `PWMAP_CLIP_TIMEOUT_SECONDS`, `PWMAP_SUBPROCESS_TIMEOUT_SECONDS` |
| Partial recovery | Scan `pwmap/runway_downloads`, copy clips into run folder, write manifests |
| Results | Show `partial_failed` with recovery metadata; prefer newest run by mtime |
| Retry | **Not implemented** (by design) |

**Not modified:** duration planner, prompt/story generation, Use Frame logic, browser mappings, provider selection core routing.

---

## Files Changed / Added

### New

- `content_brain/execution/pwmap_timeout_policy.py` — clip-count timeout policy + env overrides
- `project_brain/validate_pwmap_long_run_timeout_hardening.py` — validation (17 tests)
- `project_brain/PWMAP_LONG_RUN_TIMEOUT_HARDENING_REPORT.md` — this report

### Modified

- `content_brain/execution/pwmap_runway_agent_adapter.py`
  - `build_subprocess_command()` passes `--timeout {clip_timeout_seconds}`
  - `run_pwmap_agent()` resolves clip timeout from job; on failure calls partial finalization
  - `run_pwmap_product_studio_generate()` uses `resolve_subprocess_timeout_seconds()`
- `content_brain/execution/pwmap_finalization.py`
  - `parse_subprocess_failure_details()`, `scan_runway_downloads_for_run_window()`
  - `recover_partial_clips_to_run_dir()`, `finalize_partial_pwmap_run()`
  - `load_latest_product_studio_pwmap_results()` sorts by **mtime first** (newest wins)
  - `build_pwmap_results_payload()` exposes `partial_failed` fields
- `ui/api/product_studio_service.py` — `_merge_pwmap_results()` forwards partial fields
- `ui/web/src/pages/ResultsPage.tsx` — partial_failed display block

---

## Timeout Policy

| Clip count | `--timeout` (seconds) | Subprocess budget (default) |
|------------|----------------------|-------------------------------|
| 1 | 900 | 1800 |
| 2 | 1200 | 3300 |
| 3 | 1500 | 5400 |
| 4 | 1800 | 8100 |

**Env overrides (take precedence):**

```powershell
$env:PWMAP_CLIP_TIMEOUT_SECONDS = "2400"
$env:PWMAP_SUBPROCESS_TIMEOUT_SECONDS = "99999"
```

Subprocess command example (4 clips):

```
python runway_agent.py --job ... --timeout 1800 --close-browser
```

---

## Partial Progress Flow

When pwmap exits non-zero or subprocess times out:

1. Parse stdout for `CLIP N/M`, `[OK] Downloaded`, `[ERROR]`
2. Derive `run_started` from run_id timestamp (`pwmap_YYYYMMDDTHHMMSS_...`)
3. Scan `C:\Users\kaman\Desktop\pwmap\runway_downloads\clip_*.mp4` with mtime ≥ run start
4. Copy valid clips into `outputs/pwmap_agent_runs/{run_id}/`
5. Write:
   - `normalized_result.json` (status `partial_failed`)
   - `execution_report.json`
   - `agent_result.json` with:
     - `status: partial_failed`
     - `clips_completed`, `expected_clip_count`
     - `recovery_available: true`
     - `failure_stage: clip_generation`
     - `failed_clip_index`
     - `error` (actual timeout message)

**No automatic retry** — no re-click Generate, no extra credits.

---

## Live Recovery: Failed 60s Run

Run `pwmap_20260626T203630_17bb74ed` was reprocessed via validation:

- **Clip 1 recovered:** `clip_1.mp4` (32.7 MB) from `runway_downloads/clip_001_20260626_224933.mp4`
- **agent_result.json:** `status: partial_failed`, `clips_completed: 1`, `failed_clip_index: 2`
- **error:** `Generation timed out after 900s.`

Results now selects this run over the older successful 30s run (`pwmap_20260625T191853_1e6c6869`).

---

## Results UI

Product Multi-Clip Output panel shows when `status === partial_failed`:

- Status: `partial_failed`
- Clips completed: `1 / 4`
- Recovery available: `yes`
- Failure stage: `clip_generation`
- Failed clip index: `2`
- Error message

---

## Validation

```powershell
python project_brain\validate_pwmap_long_run_timeout_hardening.py
```

**Result:** 17/17 PASS

| Test | Result |
|------|--------|
| 1–4 clip timeout mapping (900/1200/1500/1800) | PASS |
| Env clip timeout override | PASS |
| Subprocess timeout > pwmap budget | PASS |
| Env subprocess override | PASS |
| `--timeout` in subprocess command | PASS |
| Partial clip recovery | PASS |
| `partial_failed` agent_result.json | PASS |
| Partial metadata fields | PASS |
| Live 60s run reprocessed | PASS |
| Results chooses latest pwmap run | PASS |
| Results shows 60s partial (not 30s success) | PASS |
| Latest loader supports partial_failed | PASS |
| External pwmap agent untouched | PASS |
| Adapter timeout/partial wiring only | PASS |

---

## Operational Notes

- For the next 60s run, expect **1800s per clip** and **8100s** subprocess budget (~2h 15m total headroom).
- If a run still fails mid-batch, check `outputs/pwmap_agent_runs/{run_id}/agent_result.json` for recovered clips before retrying manually.
- Set env overrides only when debugging; defaults follow clip-count policy.

---

## Out of Scope (Future Phase)

- Automatic retry from failed clip index
- Re-click Generate without user action
- FFmpeg stitch of partial clip sets
- Changes to pwmap `runway_agent.py`, Use Frame, or browser mappings
