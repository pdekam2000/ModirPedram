# 45S / 3-CLIP LIVE FORENSIC REPORT

**Investigation date:** 2026-07-08  
**Scope:** Latest live YouTube upload run only  
**Run analyzed:** `pwmap_20260708T191329_14926d07`  
**Automation job:** `auto_0852041eedcb`  
**Status:** Investigation only — no patches applied

---

## Executive summary

The pipeline **correctly planned 45 seconds / 3 clips**, but **only one unique 15-second clip was actually produced**. Clip 2 generation failed verification, clip 3 never started, **FFmpeg merge never ran**, **branding never ran**, and automation still uploaded the single 15.042s `video.mp4` to YouTube as `5tnnjRp-Mak`.

YouTube showing **~16 seconds** matches ffprobe on the uploaded file (**15.042s**, rounded in the UI).

---

## 1. run_id

```
pwmap_20260708T191329_14926d07
```

Automation job: `auto_0852041eedcb`  
Completed: `2026-07-08T19:28:54Z`  
YouTube URL: https://www.youtube.com/watch?v=5tnnjRp-Mak

---

## 2. Planned values

| Field | Value | Source |
|-------|-------|--------|
| **Requested duration** | **45s** | `automation_jobs.json` → `duration: 45` |
| **Resolved duration** | **45s** | `preflight_snapshot.duration_plan.duration_seconds: 45` |
| **Planned clip_count** | **3** | `preflight_snapshot.duration_plan.clip_count: 3` |

Additional preflight confirmation:

```json
"kling_duration_plan": {
  "requested_duration_seconds": 45,
  "planned_duration_seconds": 45,
  "clip_count": 3
}
"kling_frame_to_video_plan": {
  "planned_duration_seconds": 45,
  "clip_count": 3
}
"multiclip_execution_plan": {
  "duration_seconds": 45,
  "clip_count": 3,
  "execution_mode": "use_frame_chain"
}
```

**Conclusion:** Planning layer was correct. The 45s / 3-clip fix reached preflight for this run.

---

## 3. pwmap job.json

Path: `outputs/pwmap_agent_runs/pwmap_20260708T191329_14926d07/job.json`

| Field | Value |
|-------|-------|
| **duration** (per Runway/Kling clip) | `15` |
| **clip_count** | `null` (field not present) |
| **number of prompts** | **3** |
| **use_frame_second** | `15` |
| **model** | `Kling 3.0 Pro` |

pwmap subprocess log confirms intent:

```
[i] Clips to generate: 3
[i] Model: Kling 3.0 Pro | Duration: 15s | Aspect: 9:16
[i]   Clip 1: 2500 chars
[i]   Clip 2: 2500 chars
[i]   Clip 3: 2500 chars
```

**Conclusion:** pwmap was instructed to generate **3 × 15s clips** (45s total). `job.json` does not store top-level `clip_count`; prompt count is the reliable indicator.

---

## 4. Generation

| Clip | Generated? | Evidence |
|------|------------|----------|
| **Clip 1** | **YES** | Downloaded `clip_001_20260708_212759.mp4`; `clip_1.mp4` present; 15.042s |
| **Clip 2** | **FAILED** | Subprocess reached clip 2/3, but exited with: `Could not prove downloaded output belongs to current clip attempt.` |
| **Clip 3** | **NO** | Subprocess terminated after clip 2 failure; no `clip_3.mp4`; log never reached `CLIP 3/3` |

### Clip 2 failure details (`subprocess_stdout.log`)

```
CLIP 2/3
[step] Use frame from previous clip (last frame)...
[OK] 'Use frame' is visible under previous clip.
[step] Seeking previous clip to second 15 (last frame)...
[OK] Video at 0.12s (target 15s)        ← scrub failed (0.12s not 15s)
[OK] Timeline scrubbed to ~15s
[OK] Use frame clicked (last frame).
...
[OK] Clip fully built — Download / Use frame visible.
[FAIL] Could not prove downloaded output belongs to current clip attempt.
```

### Post-failure recovery

`agent_result.json` / `execution_report.json`:

```json
{
  "status": "partial_failed",
  "clip_count": 2,
  "expected_clip_count": 3,
  "failed_clip_index": 2,
  "error": "Could not prove downloaded output belongs to current clip attempt."
}
```

Recovery scan copied two files from `external/pwmap/runway_downloads/`, but both are **byte-identical duplicates of clip 1** (see section 5).

---

## 5. Download

| File | Exists | Duration (ffprobe) | MD5 (first 16) | Notes |
|------|--------|-------------------|----------------|-------|
| `clip_1.mp4` | YES | **15.042s** | `0580b0fcaab1d6b0` | Valid clip 1 download |
| `clip_2.mp4` | YES | **15.042s** | `0580b0fcaab1d6b0` | **Same bytes as clip_1** — not a real clip 2 |
| `clip_3.mp4` | **NO** | — | — | Never generated |
| `video.mp4` | YES | **15.042s** | `0580b0fcaab1d6b0` | **Copy of clip_1** |

Source downloads:

| File | Duration | MD5 |
|------|----------|-----|
| `external/pwmap/runway_downloads/clip_001_20260708_212759.mp4` | 15.042s | `0580b0fcaab1d6b0` |
| `external/pwmap/runway_downloads/clip_002_20260708_212759.mp4` | 15.042s | `0580b0fcaab1d6b0` |

`clip1 == clip2 == video.mp4` → **TRUE** (identical files)

---

## 6. Assembly

### Was FFmpeg invoked?

**NO.**

Evidence:

- No `video_merged.mp4` in run folder
- No `ffmpeg_concat_list.txt` in run folder
- No `product_multiclip_runtime.json` (written only after orchestrator merge path)
- No `publish/` folder or `FINAL_*.mp4` artifacts
- `publish_package_path` in automation job: **empty**

### Which clips would have been passed to FFmpeg?

**None.** The pwmap subprocess exited before orchestrator `finalize_multiclip_output()` could stitch.

If merge had been attempted with recovered artifacts, `pwmap_clip_assembly_guard` would have **blocked** stitching anyway:

- `clip_1.mp4` and `clip_2.mp4` are duplicate bytes
- Guard error: `Duplicate clip bytes detected; assembly blocked.`

### Exact FFmpeg input list

```
(not created — FFmpeg merge never executed)
```

### Total merged duration

```
N/A — no merge performed
```

### What became `video.mp4` instead?

`pwmap_finalization._resolve_final_video_path()` on partial failure:

1. Found 2 "verified" clip paths (both duplicates)
2. Copied **last path** (`clip_2.mp4`) → `video.mp4`
3. Because `clip_2` == `clip_1`, result is a **single 15.042s clip**

---

## 7. Branding

| Stage | Status |
|-------|--------|
| Assembly pipeline | **Skipped** (no publish package) |
| Branding / subtitles / CTA overlay | **Skipped** |
| `FINAL_BRANDED_PUBLISH_READY.mp4` | **Not created** |

| Metric | Value |
|--------|-------|
| **Branding input duration** | 15.042s (`video.mp4`) |
| **Branding output duration** | **N/A** — branding never ran |

Upload used the raw pwmap output copied to:

```
outputs/runs/pwmap_20260708T191329_14926d07/upload/youtube/video.mp4
```

(`upload_manifest.json` → `source_video_path` points to pwmap `video.mp4`)

---

## 8. Upload

| Field | Value |
|-------|-------|
| **Uploaded file path** | `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\pwmap_20260708T191329_14926d07\upload\youtube\video.mp4` |
| **Uploaded duration (ffprobe)** | **15.042 seconds** |
| **YouTube video id** | `5tnnjRp-Mak` |
| **YouTube URL** | https://www.youtube.com/watch?v=5tnnjRp-Mak |
| **Upload time** | `2026-07-08T19:28:42Z` |
| **Upload manifest** | `outputs/upload_packages/youtube_submit_manifest.json` |

Automation job marked upload `ok: true` despite generation `partial_failed`.

`automation_job_runner.py` logic:

```python
has_generated_video = bool(start_result.get("video_path") or ...)
if not start_ok and has_generated_video:
    # continues to upload path  ← partial failure still has video_path
```

---

## 9. Root cause — why YouTube received a ~16-second video

### Proven chain of causation

```
PLAN: 45s / 3 clips ✓
  ↓
PWMAP: 3 prompts dispatched ✓
  ↓
CLIP 1: generated & downloaded ✓ (15.042s)
  ↓
CLIP 2: Use-frame scrub landed at 0.12s not 15s
        → download verification failed
        → subprocess exit code 1
  ↓
CLIP 3: never started ✗
  ↓
RECOVERY: scanned runway_downloads
        → found 2 files with identical bytes (both clip 1)
        → wrote clip_1.mp4 + clip_2.mp4 (duplicates)
  ↓
ASSEMBLY: FFmpeg never called ✗
        → video.mp4 = copy of single 15s clip
  ↓
BRANDING: skipped ✗ (no publish package)
  ↓
UPLOAD: automation uploaded video.mp4 anyway ✓
        → YouTube received 15.042s (~16s in UI)
```

### Primary root cause

**Clip 2 failed during pwmap browser automation** with error:

> `Could not prove downloaded output belongs to current clip attempt.`

Contributing factor visible in log:

> `[OK] Video at 0.12s (target 15s)` — timeline scrub to last frame did not reach second 15 before "Use frame" + generate.

### Secondary root cause

**Partial-failure path still produces an uploadable `video_path`** by copying the last recovered clip (which was a duplicate of clip 1), and **automation does not block upload on `partial_failed` status** when any `video_path` exists.

### What did NOT cause the short upload

| Ruled out | Evidence |
|-----------|----------|
| Wrong scheduler duration | Job + preflight both say 45s |
| Wrong clip_count in queue | `clip_count: 3` in automation job |
| Old 2-clip preflight plan | `kling_frame_to_video_plan.clip_count: 3`, 3 prompts in job.json |
| FFmpeg merge trimming to 16s | FFmpeg never ran |
| Branding shortening video | Branding never ran |

---

## Artifact index

| Artifact | Path |
|----------|------|
| Run folder | `outputs/pwmap_agent_runs/pwmap_20260708T191329_14926d07/` |
| pwmap job | `.../job.json` |
| Subprocess log | `.../subprocess_stdout.log` |
| Agent result | `.../agent_result.json` |
| Execution report | `.../execution_report.json` |
| Normalized result | `.../normalized_result.json` |
| Upload package | `outputs/runs/pwmap_20260708T191329_14926d07/upload/` |
| YouTube manifest | `outputs/upload_packages/youtube_submit_manifest.json` |
| Automation job | `project_brain/automation/automation_jobs.json` → `auto_0852041eedcb` |

---

## Recommended fix targets (for future work — not applied here)

1. **pwmap clip 2 download verification** — fix timeline scrub to true last frame before Use Frame
2. **Block upload on `partial_failed`** when `clips_completed < expected_clip_count`
3. **Duplicate clip guard before upload** — never upload when `clip_1` == `clip_2` bytes
4. **Require FFmpeg merge + duration probe ≥ 40s** before YouTube upload in automation path

---

*End of forensic report. No code changes were made during this investigation.*
