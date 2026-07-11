# PHASE 45S-3CLIP ROOT CAUSE REPAIR REPORT

**Date:** 2026-07-08  
**Phase:** `PHASE 45S-3CLIP-ROOT-CAUSE-REPAIR`  
**Forensic source:** `45S_3CLIP_FORENSIC_REPORT.md` (run `pwmap_20260708T191329_14926d07`)

---

## Executive summary

All four root causes from the forensic investigation have been repaired. A fail-closed upload gate now blocks partial, duplicate, unassembled, and unbranded runs. Use Frame seek for clip 2+ waits for HTML5 metadata, seeks to `duration - 0.30s`, verifies within ±0.75s (3 retries), and fails closed with `failure_stage=use_frame_seek_failed`. Recovery no longer duplicates prior clip bytes. FFmpeg assembly is blocked when clips are missing or byte-identical.

**Validator:** `project_brain/validate_45s_use_frame_and_fail_closed.py` — **16/16 PASS**

---

## Root cause 1 — Use Frame seek lands at 0.12s

### Problem
Clip 2+ Use Frame scrub accepted `0.12s` instead of the previous clip end (~15s), causing download verification failure and subprocess exit.

### Fix (`external/pwmap/runway_agent.py`, synced to `C:\Users\kaman\Desktop\pwmap\runway_agent.py`)

| Constant | Value |
|----------|-------|
| `USE_FRAME_END_OFFSET_SEC` | `0.30` |
| `USE_FRAME_SEEK_TOLERANCE_SEC` | `0.75` |
| `USE_FRAME_SEEK_MAX_RETRIES` | `3` |

**Behavior for clip index ≥ 2:**
1. Open previous clip preview video element
2. Wait until `video.duration` is finite and > 0 (`_wait_for_video_metadata_loaded`)
3. Seek to `duration - 0.30` seconds (not first frame, not hardcoded 0.12)
4. Verify `abs(currentTime - target) <= 0.75`
5. Reject seek if `currentTime <= 1.0` when `target > 1.0`
6. On persistent failure → raise `UseFrameSeekFailedError` with `failure_stage=use_frame_seek_failed`, `failed_clip_index=N`
7. **No generate, no download, no recovery** — subprocess exits immediately

---

## Root cause 2 — Partial runs uploaded

### Problem
`automation_job_runner` treated `partial_failed` + existing `video_path` as uploadable.

### Fix

**New module:** `content_brain/automation/fail_closed_upload_gate.py`

Upload allowed **only** when ALL are true:
- `run_status == completed` (not `partial_failed`, `failed`, etc.)
- `completed_clip_count == planned_clip_count`
- All clips on disk and SHA-256 unique
- `assembly_status == completed` (for multi-clip)
- `branding_status == completed`
- `publish_ready == true`
- `FINAL_BRANDED_PUBLISH_READY.mp4` exists
- `youtube_metadata.json` exists
- `youtube_upload_allowed == true`

**Blocked reasons returned explicitly:**
- `blocked_partial_failed`
- `blocked_missing_clip`
- `blocked_duplicate_clips`
- `blocked_missing_assembly`
- `blocked_missing_branding`
- `blocked_publish_not_ready`

**Wired into:**
- `content_brain/automation/automation_job_runner.py` — replaces `has_generated_video` partial-upload path
- `content_brain/automation/auto_platform_upload.py` — gate before any platform submit

---

## Root cause 3 — Recovery duplicates clip 1

### Problem
Partial recovery copied identical bytes into `clip_2.mp4` and synthesized `video.mp4` from last clip.

### Fix

| File | Change |
|------|--------|
| `content_brain/execution/pwmap_finalization.py` | `recover_partial_clips_to_run_dir()` dedupes by SHA-256; skips duplicate downloads |
| `content_brain/execution/pwmap_finalization.py` | `_resolve_final_video_path()` no longer copies single/last clip to `video.mp4` |
| `content_brain/execution/pwmap_finalization.py` | `finalize_partial_pwmap_run()` sets `status=partial_failed`, `youtube_upload_allowed=false`, `publish_ready=false`, clears upload path |
| `content_brain/execution/pwmap_runway_agent_adapter.py` | `copy_mp4_outputs()` only writes `video.mp4` when assembly guard passes |
| `content_brain/execution/product_multiclip_orchestrator.py` | Partial branch: `ok=False`, `status=partial_failed`, `video_path=""`, `youtube_upload_allowed=False` |

---

## Root cause 4 — FFmpeg starts on missing/duplicate clips

### Fix (`content_brain/execution/pwmap_clip_assembly_guard.py` v2)

`verify_clips_unique_for_assembly()` checks:
- All `clip_1..clip_N` exist
- All SHA-256 hashes unique

When blocked → `assembly_status = blocked_duplicate_or_missing_clips`, FFmpeg never starts.

**Wired into:**
- `product_multiclip_orchestrator.finalize_multiclip_output()`
- `pwmap_runway_agent_adapter.copy_mp4_outputs()`
- `fail_closed_upload_gate.evaluate_automation_upload_gate()`

---

## Validator results

```
python project_brain/validate_45s_use_frame_and_fail_closed.py
```

| Check | Result |
|-------|--------|
| seek never accepts 0.12s | PASS |
| seek accepts duration-0.3 | PASS |
| duplicate clips block assembly | PASS |
| duplicate clips block upload | PASS |
| partial_failed blocks upload | PASS |
| branding missing blocks upload | PASS |
| assembly missing blocks upload | PASS |
| FINAL_BRANDED_PUBLISH_READY required | PASS |
| 30s / 2 clips still works | PASS |
| 45s / 3 clips generates 3 prompts | PASS |
| recovery never duplicates prior clip | PASS |

**SUMMARY: 16/16 checks passed**

---

## Files changed

| File | Purpose |
|------|---------|
| `external/pwmap/runway_agent.py` | Use Frame seek fail-closed |
| `C:\Users\kaman\Desktop\pwmap\runway_agent.py` | Runtime mirror (adapter precedence) |
| `content_brain/automation/fail_closed_upload_gate.py` | **NEW** — upload gate |
| `content_brain/automation/automation_job_runner.py` | Gate wiring, remove partial upload |
| `content_brain/automation/auto_platform_upload.py` | Gate wiring |
| `content_brain/execution/pwmap_clip_assembly_guard.py` | Missing + duplicate guard v2 |
| `content_brain/execution/pwmap_finalization.py` | Recovery dedupe, partial fail-closed |
| `content_brain/execution/pwmap_runway_agent_adapter.py` | Guarded video.mp4 copy |
| `content_brain/execution/product_multiclip_orchestrator.py` | Partial failed + assembly guard |
| `project_brain/validate_45s_use_frame_and_fail_closed.py` | **NEW** — validator |

---

## Live test (45s / 3 clips / private upload)

**Validator:** PASS (16/16) — prerequisite met.

**Launch attempt:** 2026-07-08  
**Job created:** `auto_5c619c3ea7cf` (45s / 3 clips / `youtube_shorts`)  
**Result:** **BLOCKED** — `browser_disconnected` (Runway browser session not connected at launch time)

**To complete live retest:**
1. Connect Runway browser (`Connect Runway Browser` in UI or ensure `project_brain/sessions/runway_session.json` is valid)
2. Restart API if needed: `python -m ui.api.main`
3. Run: `python project_brain/run_45s_live_retest_private.py`

Or start the queued job directly once browser is connected:
```powershell
curl -X POST http://127.0.0.1:8765/automation/start
```

**Expected on success:**
| Artifact | Expected |
|----------|----------|
| `clip_1.mp4`, `clip_2.mp4`, `clip_3.mp4` | All present, unique SHA-256 |
| `video_merged.mp4` / `video.mp4` | FFmpeg merge executed |
| `publish/FINAL_BRANDED_PUBLISH_READY.mp4` | Present |
| Uploaded duration | ≈ 45s (ffprobe ≥ 40s) |
| YouTube privacy | `private` |

**Expected on clip 2 seek failure:**
- Run stops at `partial_failed`
- `failure_stage=use_frame_seek_failed`
- **No upload** — gate returns `blocked_partial_failed`

---

## Regression safety

- **30s / 2 clips:** duration planner and execution plan unchanged (validator confirmed)
- **Single-clip 15s:** assembly guard allows single clip; upload gate skips multi-clip assembly check when `planned <= 1`
- **Prior forensic run** (`pwmap_20260708T191329_14926d07`) would now be blocked at upload with `blocked_partial_failed`

---

*Repair complete. Validator PASS (16/16). Live retest job queued; blocked on `browser_disconnected` until Runway session is connected.*
