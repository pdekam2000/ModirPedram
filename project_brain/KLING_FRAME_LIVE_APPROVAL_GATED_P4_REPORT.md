# Kling Frame-to-Video Live Approval-Gated P4 Report

**Phase:** KLING-FRAME-LIVE-APPROVAL-GATED-P4  
**Date:** 2026-06-17  
**Engine:** `kling_frame_to_video_live_p4_v1`  
**Run ID:** `kling_ft_20260617T202616_1e37f8a6`

---

## Summary

First **approval-gated** Kling 3.0 Pro **Frame-to-Video** live run from the Product pipeline. UI prepare, explicit operator approval, and **Generate** succeeded. Runway reported generation complete, but **CDP/CloudFront download recovery did not produce a real >1MB MP4** — status `download_failed`, `recovery_available=true`. No mock/placeholder file is treated as success.

---

## Run ID & Inputs

| Field | Value |
|-------|-------|
| **run_id** | `kling_ft_20260617T202616_1e37f8a6` |
| **Starter frame** | `outputs/kling_frame_to_video/kling_ft_20260617T202616_1e37f8a6/starter_frame/frame_001.png` (9,495 bytes) |
| **Provider** | Kling 3.0 Pro Native Audio |
| **Mode** | Frame-to-Video (Frames) |
| **Duration (UI)** | 15s — stable after popover dismiss |
| **Native audio (UI)** | ON |

---

## Prompt Used

- **Chars:** 1324 (target 1200–1800, max 2500)
- **Source:** P3 planner + live enrichment (`resolve_frame_prompt` / `_enrich_frame_prompt_for_live`)
- **Saved:** `outputs/kling_frame_to_video/kling_ft_20260617T202616_1e37f8a6/frame_prompt.txt`

---

## Approval

| Field | Value |
|-------|-------|
| **Flags** | `--approve-generate --approved-by "Pedram" --confirm-credit-spend` |
| **Approved by** | Pedram |
| **Approved at** | 2026-06-17 23:35:57 (local) |
| **Prepare-only gate** | Prior run stopped at `awaiting_approval` with full checklist |

---

## Generate Status

| Field | Value |
|-------|-------|
| **Generate clicked** | **Yes** |
| **Credits spent** | **Yes** |
| **Generation completed** | **Yes** (`download_button_visible`) |
| **Engine status** | `download_failed` (not `completed`) |

---

## Download Status

| Field | Value |
|-------|-------|
| **output_ready** | `false` |
| **recovery_available** | `true` |
| **download_status** | `failed` |
| **Strategies tried** | `runway_artifact_card_missing`, `http_fetch`, `http_fetch_failed` |
| **Partial file** | `outputs/.../clips/c1/video.mp4` — **383,006 bytes** (rejected: `< 1MB`, ffprobe unavailable/failed) |
| **Canonical root copy** | Not written (download verify failed) |

**Recovery command (no new Generate):**

```bash
python tools/kling_frame_to_video_live_p4.py \
  --recover-output \
  --run-id kling_ft_20260617T202616_1e37f8a6
```

Re-run with Runway generate tab open on the completed session so Phase-I CDP / UI download can attach to the artifact card.

---

## Output Paths

| Path | Status |
|------|--------|
| `outputs/kling_frame_to_video/kling_ft_20260617T202616_1e37f8a6/clips/c1/video.mp4` | Partial (383 KB — **not** canonical success) |
| `outputs/kling_frame_to_video/kling_ft_20260617T202616_1e37f8a6/video.mp4` | Not created |
| `outputs/.../live_run_result.json` | Saved |
| `outputs/.../approval_checklist.json` | Saved |
| `outputs/.../frame_prompt.txt` | Saved |

---

## Duration & Audio (post-download)

| Check | Result |
|-------|--------|
| **UI duration** | 15s confirmed pre-Generate |
| **UI audio** | ON |
| **ffprobe duration** | Pending — real MP4 not recovered |
| **Native audio in file** | Pending — requires successful download + ffprobe |

---

## Screenshots / Checkpoints

| Step | File |
|------|------|
| Frame mode | `project_brain/runway_ui_mapping/screenshots/kling_frame_live_p4/kling_ft_20260617T202616_1e37f8a6_03_frame_mode_selected_20260617T205836.png` |
| First frame upload | `..._04_first_frame_uploaded_20260617T211147.png` |
| Prompt filled | `..._05_prompt_filled_20260617T211150.png` |
| Duration 15s | `..._06_duration_after_15s_20260617T211155.png` |
| Audio ON | `..._07_audio_on_20260617T211202.png` |
| Approval gate | `..._09_approval_gate_20260617T211543.png` |
| Generate clicked | `..._11_generate_clicked_20260617T213557.png` |
| Generation complete | `..._12_generation_complete_20260617T213557.png` |

---

## Validation Results

**Script:** `project_brain/validate_kling_frame_live_approval_gated_p4.py`

| # | Test | Result |
|---|------|--------|
| 1 | Starter frame exists | **PASS** |
| 2 | Prompt exists, ≤2500 chars (1324) | **PASS** |
| 3 | Generate requires approval flags | **PASS** |
| 4 | Missing approval stops safely (`awaiting_approval`) | **PASS** (live prepare) |
| 5 | Duration 15s stable after outside click | **PASS** (live prepare) |
| 6 | Audio ON confirmed | **PASS** (live prepare) |
| 7 | Real MP4 > 1MB | **FAIL** — partial 383 KB only |
| 8 | ffprobe PASS | **FAIL** — ffprobe unavailable / file too small |
| 9 | Native audio present | **PENDING** — needs real MP4 |
| 10 | Canonical folder output | **FAIL** — no verified canonical MP4 |
| 11 | No mock placeholder as success | **PASS** — engine rejected partial file |
| 12 | Download recovery reuses CDP/CloudFront logic | **PASS** — `_download_output` / Phase-I CDP reused |

```bash
# Static + guards
python project_brain/validate_kling_frame_live_approval_gated_p4.py

# Live prepare (no credits)
python project_brain/validate_kling_frame_live_approval_gated_p4.py --prepare-live
```

---

## Artifacts Delivered

| File | Role |
|------|------|
| `content_brain/execution/kling_frame_to_video_live_engine.py` | P4 approval-gated live engine + recovery |
| `tools/kling_frame_to_video_live_p4.py` | CLI (`--approve-generate`, `--recover-output`) |
| `project_brain/validate_kling_frame_live_approval_gated_p4.py` | 12-check validation suite |
| `project_brain/kling_frame_live_p4_summary.json` | Latest run summary |
| `outputs/.../live_run_result.json` | Full step trace |

---

## Safety Compliance

- Generate **never** ran without all three approval flags.
- Missing approval → `status=awaiting_approval`, `generate_clicked=false`.
- Download failure → `status=download_failed`, `generation_completed=true`, `output_ready=false`, `recovery_available=true`.
- Partial 383 KB file **not** promoted as success.

---

## Next Step

With the Runway session still showing the completed Kling frame output, run recovery (or re-open that session in Chrome CDP) and retry:

```bash
python tools/kling_frame_to_video_live_p4.py \
  --recover-output \
  --run-id kling_ft_20260617T202616_1e37f8a6
```

Once a real MP4 passes ffprobe (>1MB, ~15s, audio track), copy to:

- `outputs/kling_frame_to_video/kling_ft_20260617T202616_1e37f8a6/clips/c1/video.mp4`
- `outputs/kling_frame_to_video/kling_ft_20260617T202616_1e37f8a6/video.mp4`
