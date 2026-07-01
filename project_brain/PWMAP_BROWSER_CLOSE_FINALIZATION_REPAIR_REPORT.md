# PWMAP Browser Close Finalization Repair Report

**Date:** 2026-06-25  
**Phase:** PWMAP-BROWSER-CLOSE-FINALIZATION-REPAIR

## Problem

Product Studio 30s live run successfully generated both clips in browser (Use Frame worked), but:

- Browser appeared to close before finalization completed
- Results page showed stale **Dog Training** canonical run instead of the new pwmap run
- Run metadata existed (`pwmap_20260625T191853_1e6c6869`) but was not registered as the current Product Studio result

## Root Causes

1. **No staged finalization in ModirAgentOS** — adapter copied files and wrote `normalized_result.json` but did not verify disk artifacts, register `latest_run_attempt.json`, or write `agent_result.json` / `execution_report.json`.

2. **Results resolution order** — `get_results()` loaded canonical runway (`Dog Training`) **before** pwmap Product Studio runs when no `run_id` was passed.

3. **Browser close timing** — pwmap subprocess did not pass `--close-browser`; browser lifecycle was ambiguous after subprocess exit. Browser close is now requested **after** pwmap writes `last_result.json` (inside pwmap's own success path), and ModirAgentOS records close state during finalization.

4. **Missing MP4 recovery** — if local run-folder copies were missing but pwmap source paths remained, run was marked complete without recovery attempt.

## What Was NOT Modified

- Product Studio duration planner
- Prompt generation
- Use Frame logic
- Browser mappings (`runway_agent.py` generation flow)
- Clip generation pipeline inside pwmap

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/pwmap_finalization.py` | Staged finalization, recovery, registration, Results resolution |
| `project_brain/validate_pwmap_browser_close_finalization.py` | Validation (11 checks) |
| `project_brain/PWMAP_BROWSER_CLOSE_FINALIZATION_REPAIR_REPORT.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/pwmap_runway_agent_adapter.py` | `--close-browser` flag; calls `finalize_pwmap_run()`; improved loader |
| `content_brain/execution/product_multiclip_orchestrator.py` | Re-register after merge; partial recovery path |
| `ui/api/product_studio_service.py` | Prefer Product Studio pwmap in `get_results()`; enriched `_merge_pwmap_results()` |

## Finalization Stages

| Stage | When |
|-------|------|
| `clips_generated` | `last_result.json` parsed; clip count known |
| `downloads_verified` | Local MP4s validated; recovery from pwmap source if missing |
| `manifest_written` | `normalized_result.json`, `execution_report.json`, `agent_result.json` |
| `result_registered` | `latest_run_attempt.json` updated via `record_latest_run_attempt()` |
| `browser_closed` | Recorded from subprocess stdout + `--close-browser` flag |

Artifacts per run folder:

```
outputs/pwmap_agent_runs/<run_id>/
├── job.json
├── last_result.json
├── normalized_result.json
├── execution_report.json      ← NEW
├── agent_result.json          ← NEW
├── error.json                 ← if finalization failed
├── subprocess_stdout.log
├── clip_1.mp4 / clip_2.mp4 ...
└── video.mp4
```

## Browser Close Behavior

- Adapter now appends `--close-browser` to subprocess command
- pwmap `runway_agent.py` closes browser in `finally` **after** writing `last_result.json`
- ModirAgentOS records close reason in finalization stage (does not alter pwmap generation code)

## Results Page Fix

When Results loads with no `run_id`:

1. **First:** latest Product Studio pwmap run (`preflight_snapshot` present)
2. Sets `is_canonical_latest: true` and `canonical_run_id` to pwmap run
3. Includes `run_history` from pwmap Product Studio folders
4. Includes `latest_run_attempt` from registration
5. **Only then** falls back to legacy canonical runway if no pwmap Product run exists

## Partial / Recovery

If clips exist but final MP4 missing:

- Status: `partial`
- `recovery_available: true`
- `error.json` documents missing paths
- Clips preserved via source-path recovery when possible

## Validation

```
python project_brain/validate_pwmap_browser_close_finalization.py
TOTAL: 11  PASS: 11  FAIL: 0
ALL PASS
```

Checks include:

- `--close-browser` in subprocess command
- Finalization stage order (manifest before result registration before browser record)
- 2-clip run records both clips
- Recovery from source when local copy missing
- Results prefers Product Studio pwmap over Dog Training canonical
- `latest_attempt_run_id` is pwmap

## Architecture Confirmation

Product Studio orchestration (duration planner, multi-clip routing) unchanged. Repair is isolated to **post-generation finalization** and **Results resolution** at the pwmap adapter boundary.
