# PWMAP 60s Exit Code 1 Forensic Report

**Date:** 2026-06-26  
**Phase:** PWMAP-60S-EXIT1-FORENSIC  
**Run ID:** `pwmap_20260626T203630_17bb74ed`

## Executive Summary

Exit code 1 was caused by a **per-clip generation timeout** during **Clip 2/4**, not Playwright import, Use Frame failure, or browser premature close.

| Field | Value |
|-------|-------|
| **Failure stage** | `clip_generation` (wait for Clip 2 render) |
| **Exact error** | `Generation timed out after 900s.` |
| **Failing file** | `C:\Users\kaman\Desktop\pwmap\runway_agent.py` line **606** |
| **Exception type** | `RunwayAgentError` (raised from `wait_for_video_ready`) |
| **Clips completed** | **1 of 4** (Clip 1 downloaded) |
| **Use Frame** | **Succeeded** for Clip 2 setup; generation never finished |
| **Recovery** | **Partial** — Clip 1 MP4 exists on pwmap disk |

---

## Run Parameters

| Parameter | Value |
|-----------|-------|
| `duration_seconds` | 60 |
| `clip_count` | 4 |
| `execution_mode` | `use_frame_chain` |
| `provider` | `kling_3_0_pro_native_audio` |
| `topic` | animation Honor demogogon |
| Python | `C:\Python314\python.exe` |
| Subprocess exit | **1** |
| Run started (UTC) | ~2026-06-26T20:36:30 |
| Run ended (UTC) | 2026-06-26T21:05:24 (~29 min) |

---

## 1. ModirAgentOS Run Folder

**Path:** `C:\Users\kaman\Desktop\ModirAgentOS\outputs\pwmap_agent_runs\pwmap_20260626T203630_17bb74ed`

| Artifact | Present | Notes |
|----------|---------|-------|
| `job.json` | Yes | Valid 4-clip job, `use_frame_second: 14` |
| `subprocess_stdout.log` | Yes | Full batch log; error on last line |
| `subprocess_stderr.log` | **No** | Error emitted to stdout only |
| `stderr.txt` / `stdout.txt` | **No** | Adapter uses `subprocess_*.log` naming |
| `normalized_result.json` | Yes | `ok: false`, `subprocess_exit_code: 1` |
| `execution_report.json` | **No** | Finalization never ran (subprocess failed first) |
| `agent_result.json` | **No** | — |
| `error.json` | **No** | — |
| `finalization_report.json` | **No** | — |
| `last_result.json` | **No** | Not copied (pwmap never wrote batch result) |
| `clip_*.mp4` / `video.mp4` | **No** | Adapter copy step never reached |

### Subprocess command (from `normalized_result.json`)

```text
C:\Python314\python.exe C:\Users\kaman\Desktop\pwmap\runway_agent.py --job C:\Users\kaman\Desktop\pwmap\agent_inbox\job.json --close-browser
```

Note: **No `--timeout` flag** passed → pwmap uses default **900 seconds per clip**.

---

## 2. Exact Error (stdout — no stderr)

From `subprocess_stdout.log` (final lines):

```text
==================================================
  CLIP 2/4
==================================================
[step] Use frame from previous clip (last frame)...
[i] Waiting for 'Use frame' under previous clip (appears only when video is done)...
[OK] 'Use frame' is visible under previous clip.
[step] Seeking previous clip to second 14 (last frame)...
[OK] Video at 14.00s (target 14s)
[OK] Use frame clicked (last frame).
[step] Filling prompt...
[OK] Prompt filled (2497 chars)
[step] Clicking Generate...
[i] Generate clicked — waiting for video (this can take several minutes)...
[i] Clip still generating — waiting until fully built...
... (repeated ~45 times over ~15 minutes) ...
[ERROR] Generation timed out after 900s.
```

### Stack trace equivalent (pwmap source)

```python
# runway_agent.py:571-606  wait_for_video_ready()
raise RunwayAgentError(f"Generation timed out after {timeout_sec}s.")

# Propagates through generate_one_clip() → run_batch_pipeline() → main()
# main() line 1219-1221:
except Exception as exc:
    print(f"[ERROR] {exc}")
    sys.exit(1)
```

**Not a selector crash.** The agent stayed in the generation-wait loop until the 900s deadline expired.

---

## 3. pwmap Side

### `agent_inbox/job.json`

Matches ModirAgentOS `job.json`: 4 prompts, Kling 3.0 Pro, 15s, 9:16, native audio, `use_frame_second: 14`. Job parse succeeded.

### `runway_downloads/last_result.json`

**Stale** — from previous successful **30s / 2-clip** run (2026-06-25):

- Clip 1: `clip_001_20260625_213052.mp4`
- Clip 2: `clip_002_20260625_214420.mp4`

**Not updated** for this run because pwmap exited with code 1 before writing `last_result.json` (write only happens after full batch success at line 1215-1216).

### `runway_downloads/*.mp4` (on disk)

| File | Size | Time | This run? |
|------|------|------|-----------|
| `clip_001_20260626_224933.mp4` | 32,705,823 B | 2026-06-26 22:49:51 | **Yes — Clip 1** |
| `clip_002_20260625_214420.mp4` | 30,347,425 B | 2026-06-25 | Previous run |
| (no clip_002 for 20260626) | — | — | Clip 2 never downloaded |

---

## 4. Clip-by-Clip Status

| Clip | Generated in browser | Use Frame | Downloaded | Notes |
|------|---------------------|-----------|------------|-------|
| **1** | Yes | N/A (first clip) | **Yes** | `clip_001_20260626_224933.mp4` |
| **2** | Started, **not confirmed complete** | **Yes** | **No** | Timed out waiting for render |
| **3** | Never started | — | No | Batch aborted |
| **4** | Never started | — | No | Batch aborted |

### Failure stage checklist

| Stage | Result |
|-------|--------|
| import | PASS |
| job parse | PASS |
| browser launch | PASS |
| clip 1 generation | PASS |
| clip 1 download | PASS |
| use_frame (clip 2) | PASS |
| **clip 2 generation** | **FAIL — 900s timeout** |
| clip 2 download | Not reached |
| clips 3–4 | Not reached |
| finalization (ModirAgentOS) | Not reached |
| browser close | After error (`--close-browser` in `finally`) |

---

## 5. Why 60s Failed but 30s Succeeded

| Factor | 30s run (2 clips) | 60s run (4 clips) |
|--------|-------------------|-------------------|
| Per-clip timeout | 900s default | 900s default (unchanged) |
| Clip 2 generation | Completed ~13 min | **Exceeded 900s** |
| Prompt length | ~2500 chars each | ~2500 chars each (same) |
| Total wall time | ~29 min (2 clips) | ~29 min (failed on clip 2) |

Clip 2 in this run simply took longer than the hard **900-second** wait in `wait_for_video_ready()`. Runway/Kling queue latency varies; a 4-clip batch has **4 independent timeout windows**, any one of which can fail.

ModirAgentOS adapter subprocess timeout is **3600s (1 hour)** — sufficient for this failure window but **would not suffice** for a full 4×20min successful run (~80 min).

---

## 6. Recovery Assessment

| Asset | Recoverable? | Path |
|-------|--------------|------|
| Clip 1 MP4 | **Yes** | `C:\Users\kaman\Desktop\pwmap\runway_downloads\clip_001_20260626_224933.mp4` |
| Clip 2+ | **No** | Never downloaded |
| Partial stitch (15s) | **Yes** | Manual copy clip 1 → run folder |
| Resume from Clip 2 | **Manual** | Re-run pwmap with 3-clip job or resume in browser if session still open (browser was closed by `--close-browser`) |

ModirAgentOS finalization (`execution_report.json`, `agent_result.json`) did **not** run because the adapter treats nonzero subprocess exit as hard failure before `finalize_pwmap_run()`.

---

## 7. Minimal Safe Fix (recommendations only — no code changed in this phase)

### A. Increase per-clip generation timeout (highest impact)

Pass `--timeout` to pwmap subprocess scaled by clip count, e.g.:

```text
--timeout 1800
```

for 4-clip runs (30 min per clip). Default in `runway_agent.py` is 900s (`parse_args` line 1038).

**Where:** adapter `build_subprocess_command()` only — does not change generation flow, mappings, or Use Frame logic.

Suggested formula: `max(900, clip_count * 900)` or fixed `1800` for 3+ clips.

### B. Increase ModirAgentOS subprocess timeout for 60s

Current default `pwmap_timeout_seconds: 3600` (1 hour) is too low for 4 clips at ~20 min each. Suggest:

```text
clip_count * 1800 + 600  →  7800s (~2.2 h) for 4 clips
```

**Where:** Product Studio payload / orchestrator only.

### C. Partial success preservation (optional, separate phase)

On pwmap batch failure after N clips downloaded, write partial `last_result.json` and let ModirAgentOS finalization recover existing MP4s. Would require pwmap `run_batch_pipeline` change — **out of scope** for “no generation flow changes.”

### D. Immediate manual recovery for this run

```powershell
Copy-Item "C:\Users\kaman\Desktop\pwmap\runway_downloads\clip_001_20260626_224933.mp4" `
  "C:\Users\kaman\Desktop\ModirAgentOS\outputs\pwmap_agent_runs\pwmap_20260626T203630_17bb74ed\clip_1.mp4"
```

Re-run Generate for 60s or 45s (3 clips) with increased timeout.

---

## 8. Architecture Confirmation

No changes made in this forensic phase to:

- Product Studio Duration Planner
- Use Frame logic
- Browser mappings
- pwmap generation flow
- Results selection logic

---

## Appendix: Timeline (approximate)

| UTC time | Event |
|----------|-------|
| 20:36:30 | Run started |
| ~20:49 | Clip 1 downloaded |
| ~20:50 | Clip 2 Use Frame applied, Generate clicked |
| ~21:05 | Clip 2 timeout (900s elapsed), exit 1 |
| 21:05:24 | ModirAgentOS `normalized_result.json` written (failure) |
