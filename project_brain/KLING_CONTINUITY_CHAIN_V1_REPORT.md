# Kling Continuity Chain V1 — Report

**Phase:** `KLING-CONTINUITY-CHAIN-V1`  
**Status:** IMPLEMENTED — runtime + validation PASS  
**Date:** 2026-06-17

---

## 1. Goal

Enable seamless multi-clip Kling Native Audio storytelling with visual continuity:

| Duration | Clips |
|----------|-------|
| 15s | 1 |
| 30s | 2 |
| 45s | 3 |
| 60s | 4 |

Each clip uses **Shot 1 = 12s main action** and **Shot 2 = 3s continuity bridge**. The bridge last frame becomes the first frame for the next clip.

---

## 2. Continuity Flow

```
Clip N → Generate → Recover MP4 → Extract Last Frame → Save PNG
  → Upload as First Frame → Clip N+1 → … → Chain Complete
```

---

## 3. Components Delivered

### Last Frame Extractor

`content_brain/execution/kling_last_frame_extractor.py`

| Function | Purpose |
|----------|---------|
| `extract_last_frame()` | ffmpeg `-sseof -0.15` final frame |
| `save_frame()` | Persist to canonical path |
| `validate_frame()` | Size / PNG checks |
| `extract_and_save_continuity_frame()` | Full clip handoff |

Output path:

```text
outputs/kling_multishot_live/{run_id}/continuity/frame_c{N}.png
```

Validated against real recovered MP4 (`kling_ms_20260617T035534_f392af70`).

### First Frame Upload Runtime

`content_brain/execution/kling_continuity_runtime.py`

Reuses mapped control **`first_frame_upload`** (no new UI mapping):

| Function | Purpose |
|----------|---------|
| `upload_frame_for_next_clip()` | Upload via mapped locator |
| `verify_upload_visible()` | Control visibility check |
| `record_upload_status()` | Persist upload metadata |

Primary upload path remains inside `run_kling_multishot_live()` for generate prep; standalone helpers available for verification and future resume flows.

### Continuity Metadata

Written to:

- `{run_dir}/continuity/continuity_chain_v1.json`
- `{run_dir}/continuity_chain.json` (merged plan + runtime)

Structure includes:

```json
{
  "version": "kling_continuity_chain_v1",
  "run_id": "...",
  "clip_count": 2,
  "continuity_status": "complete",
  "chain_complete": true,
  "frames_extracted_count": 1,
  "frames_uploaded_count": 1,
  "clips": [
    {
      "clip": 1,
      "last_frame": ".../continuity/frame_c1.png",
      "next_clip": 2
    }
  ]
}
```

### Content Brain Continuity Support

Extended `kling_native_audio_models.py` and `kling_native_audio_planner.py`:

- `continuity_anchor` on Shot 2 (existing)
- `next_clip_reference_hint` (existing)
- **`prior_clip_reference`** (new) — Clip 2+ Shot 1 receives prior-bridge language

Example Clip 2 Shot 1 lead:

> "Continuing from the previous bridge, same young boy and baby dragon move toward …"

### Multi-Clip Runtime

`content_brain/execution/kling_continuity_runtime.py`

`run_kling_continuity_chain()` responsibilities:

1. Per-clip approval via `approved_clips` / `approve_all_clips`
2. Generate clip (`run_kling_multishot_live`)
3. Recover MP4 if download failed (`recover_kling_multishot_output`)
4. Extract last frame PNG
5. Pass frame to next clip first-frame upload
6. Safe stop at any clip (`stop_after_clip`, awaiting approval for clip N+1)

Wired through `kling_product_run._execute_kling_clips()`.

---

## 4. Safety

| Rule | Implementation |
|------|----------------|
| Generate approval active | Existing `grant_continuity_approval` gate in live engine |
| Per-clip approval | Default: clip 1 only on first `approve_generate`; clip 2+ requires `approved_clips: [2]` or `approve_all_clips: true` |
| Credit spend visible | `credits_spent` / `generate_clicked` per clip result |
| Operator stop | `stop_after_clip` or natural pause at `awaiting_approval` |

---

## 5. Results Page

`ResultsPage.tsx` + `product_studio_service.py` now show:

- Continuity Status
- Frames Extracted
- Frames Uploaded
- Chain Complete
- Clip Count (existing)

---

## 6. Validation

```bash
python project_brain/validate_kling_continuity_chain_v1.py
```

**All 10 test groups passed**

| # | Test | Result |
|---|------|--------|
| 1 | Extract last frame | PASS (real 30 MB MP4) |
| 2 | Frame file exists | PASS |
| 3 | Upload uses mapped control | PASS |
| 4 | Continuity metadata created | PASS |
| 5 | Clip 2 receives frame from Clip 1 | PASS (planner + source) |
| 6 | Clip 3 receives frame from Clip 2 | PASS |
| 7 | Chain can stop safely | PASS |
| 8 | Approval still enforced | PASS |
| 9 | Single-clip flow unchanged | PASS (via continuity runtime) |
| 10 | Runway flow unchanged | PASS |

---

## 7. Operator Workflow — 30s Story (2 Clips)

### First call — Clip 1 only (default approval)

```json
{
  "approve_generate": true,
  "approved_by": "operator",
  "confirm_credit_spend": true,
  "approved_clips": [1]
}
```

After Clip 1 completes: frame extracted to `continuity/frame_c1.png`, chain pauses at `awaiting_approval`.

### Second call — Clip 2

```json
{
  "run_id": "kling_ms_...",
  "approve_generate": true,
  "approved_by": "operator",
  "confirm_credit_spend": true,
  "approved_clips": [2]
}
```

Or approve both upfront:

```json
{ "approve_all_clips": true }
```

---

## 8. Files Created / Modified

| File | Change |
|------|--------|
| `content_brain/execution/kling_last_frame_extractor.py` | **NEW** |
| `content_brain/execution/kling_continuity_runtime.py` | **NEW** |
| `content_brain/execution/kling_native_audio_models.py` | `prior_clip_reference` |
| `content_brain/execution/kling_native_audio_planner.py` | Continuity hints |
| `content_brain/execution/kling_product_run.py` | Wire continuity runtime + Results fields |
| `ui/api/product_studio_service.py` | Results API fields |
| `ui/web/src/api/productClient.ts` | Types |
| `ui/web/src/pages/ResultsPage.tsx` | Continuity UI |
| `project_brain/validate_kling_continuity_chain_v1.py` | **NEW** |
| `project_brain/KLING_CONTINUITY_CHAIN_V1_REPORT.md` | **NEW** |

---

## 9. Next Step — Live 30s Production

Run a **30s** Kling Native Audio story with CDP browser connected:

1. Preflight with `planned_duration_seconds: 30`
2. Approve Clip 1 → verify `continuity/frame_c1.png` extracted
3. Approve Clip 2 → verify Clip 2 uses uploaded frame and visual continuity holds
4. Confirm `chain_complete: true` and both clips under `clips/c1/` and `clips/c2/`

No assembly phase in this version — continuity chain only.
