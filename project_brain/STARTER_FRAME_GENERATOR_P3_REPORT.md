# Starter Frame Generator P3 Report

**Phase:** `STARTER-FRAME-GENERATOR-P3`  
**Version:** `kling_starter_frame_generator_p3_v1`  
**Date:** 2026-06-17  
**Status:** **PASS** — local prepare only, no Generate, no credits

---

## Goal

Create a strong **Clip 1 first frame** for Kling Frame-to-Video:

1. Content Brain builds a cinematic **starter image prompt** from topic/story  
2. Prepare `frame_001.png` locally (no Runway/Kling image Generate)  
3. Save under `outputs/kling_frame_to_video/{run_id}/starter_frame/frame_001.png`  
4. Hand off path to Frame-to-Video dry-run (upload-ready validation)  
5. Validate existence, image type, topic alignment, upload readiness  

**Next phase:** `KLING-FRAME-LIVE-APPROVAL-GATED-P4`

---

## Constraints (held)

| Rule | Status |
|------|--------|
| No Generate | PASS |
| No Runway credits | PASS |
| No Kling credits | PASS |

Generation mode: **`local_pil_prepare`** (cinematic placeholder PNG) or optional **`reference_copy_resize`**.

---

## Pipeline

```
Topic / story
  ↓
Content Brain (kling_frame_to_video_planner + story context)
  ↓
starter_image_prompt
  ↓
Local PIL render → frame_001.png
  ↓
validate_starter_frame_for_upload()
  ↓
Kling Frame dry-run (starter_frame_path handoff)
```

---

## Output layout

```
outputs/kling_frame_to_video/{run_id}/
  starter_frame/
    frame_001.png
    starter_frame_prompt.json
```

---

## Validation checks

| Check | Description |
|-------|-------------|
| `frame_exists` | PNG on disk |
| `frame_is_image` | Valid image via PIL verify |
| `prompt_matches_topic` | Topic keywords present in starter prompt |
| `ready_for_first_frame_upload` | All above pass |

---

## Commands

```powershell
# Generate starter frame
.\venv\Scripts\python.exe tools\kling_starter_frame_generator.py

# Validate P3
.\venv\Scripts\python.exe project_brain\validate_starter_frame_generator_p3.py

# Hand off to Frame dry-run (map-only starter validation)
.\venv\Scripts\python.exe tools\kling_frame_to_video_live_dry_run.py `
  --map-only `
  --starter-frame outputs/kling_frame_to_video/{run_id}/starter_frame/frame_001.png `
  --starter-prompt "{prompt}" `
  --topic "{topic}"
```

---

## Deliverables

| Artifact | Path |
|----------|------|
| Generator engine | `content_brain/execution/kling_starter_frame_generator.py` |
| CLI | `tools/kling_starter_frame_generator.py` |
| Validation | `project_brain/validate_starter_frame_generator_p3.py` |
| Starter summary | `project_brain/kling_starter_frame_p3_summary.json` |
| Dry-run handoff | `content_brain/execution/kling_frame_to_video_live_dry_run.py` (`starter_frame_path`) |

---

## Integration notes

- Clip 1 `first_frame_source` remains `user_upload`; P3 fills that slot with `frame_001.png`  
- P4 can wire CDP `first_frame_upload` file chooser using this path (approval-gated)  
- Continuity clips (2+) still use `prior_clip_final_frame` from `kling_last_frame_extractor`  

---

## Latest validation

Run:

```powershell
.\venv\Scripts\python.exe project_brain\validate_starter_frame_generator_p3.py
```

Expected: all checks PASS, summary written to `project_brain/kling_starter_frame_p3_summary.json`.

### Latest run

| Field | Value |
|-------|-------|
| `run_id` | `kling_ft_20260617T202616_1e37f8a6` |
| `starter_frame_path` | `outputs/kling_frame_to_video/kling_ft_20260617T202616_1e37f8a6/starter_frame/frame_001.png` |
| `frame_bytes` | 9495 |
| `ready_for_first_frame_upload` | `true` |
| `generation_mode` | `local_pil_prepare` |
| Dry-run handoff | PASS (`starter_frame_ready: true`) |
