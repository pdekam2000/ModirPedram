# Kling Use Frame Continuity Integration — Report

**Phase:** `KLING-USE-FRAME-CONTINUITY-INTEGRATION`  
**Status:** IMPLEMENTED — validation PASS; live 30s/45s chain pending operator run  
**Date:** 2026-06-03

---

## 1. Goal

Replace manual last-frame extract/upload continuity with **native Use Frame** as the primary Frame-to-Video handoff between 15s clips. Frame-to-Video Native Audio is the primary production path for long-form cinematic stories.

---

## 2. Continuity Hierarchy

| Priority | Method | When |
|----------|--------|------|
| 1 | **Use Frame** | Button detected, activated, first-frame slot verified |
| 2 | Extract last frame → upload first frame | Use Frame unavailable or activation failed |
| 3 | Starter frame fallback | Extract/upload failed; reuse clip-1 starter PNG |

Runtime flow per clip:

```
Clip N → Generate → Recover MP4 → Use Frame → Clip N+1
```

Fallback path:

```
Clip N → Generate → Recover MP4 → Extract Last Frame → Upload First Frame → Clip N+1
```

---

## 3. Duration Model

Each clip: **15 seconds**.

| Story duration | Clips |
|----------------|-------|
| 15s | 1 |
| 30s | 2 |
| 45s | 3 |
| 60s | 4 |
| 75s | 5 |
| 90s | 6 |

Frame story durations use `normalize_kling_frame_story_duration()` in `kling_frame_to_video_models.py` (up to 90s / 6 clips). Multishot duration caps remain unchanged at 60s.

---

## 4. Story Progression

Clips are **chapters**, not repeats. Continuity preserves characters and environment; prompts advance action:

| Clip | Chapter |
|------|---------|
| 1 | Introduction |
| 2 | Escalation |
| 3 | Conflict |
| 4 | Discovery |
| 5 | Resolution |
| 6 | Finale |

`story_chapter_for_clip()` and per-clip prompt planning enforce distinct beats per clip.

---

## 5. Components Delivered

### Use Frame Runtime

`content_brain/execution/kling_use_frame_runtime.py`

| Function | Purpose |
|----------|---------|
| `detect_use_frame_button()` | Locate Use Frame control via UI map |
| `validate_use_frame_availability()` | Confirm control visible/enabled |
| `activate_use_frame()` | Click Use Frame after prior clip |
| `verify_reference_transferred()` | Confirm first-frame slot populated |
| `apply_continuity_for_next_clip()` | Full hierarchy: Use Frame → extract/upload → starter |
| `write_use_frame_chain()` / `load_use_frame_chain()` | Persist `use_frame_chain.json` |
| `record_clip_continuity_metadata()` | Per-clip handoff records |
| `finalize_story_progression()` | Chain completion status |

### Frame Continuity Chain

`content_brain/execution/kling_frame_continuity_runtime.py`

`run_kling_frame_continuity_chain()` orchestrates:

1. Per-clip approval (`clip_is_approved`, `approve_all_clips`)
2. Generate via `run_kling_frame_to_video_live(clip_index=…)`
3. Recover MP4 (`recover_kling_frame_output`, `verify_recovered_mp4`)
4. Use Frame handoff to next clip
5. Safe stop on download failure, handoff failure, or `stop_after_clip`

### Metadata

Written to:

- `{run_dir}/continuity/use_frame_chain.json`
- `{run_dir}/use_frame_chain.json` (root copy)

Example:

```json
{
  "run_id": "kling_ft_20260617T202616_1e37f8a6",
  "continuity_method": "use_frame",
  "clip_count": 2,
  "chain_complete": true,
  "fallback_used": false,
  "story_progression_status": "complete",
  "clips": [
    { "clip": 1, "used_for_next_clip": true, "continuity_method": "use_frame", "story_chapter": "Introduction" }
  ]
}
```

### Product Studio Wiring

| File | Change |
|------|--------|
| `kling_product_run.py` | Routes frame preflight to `run_kling_frame_continuity_chain`; loads `use_frame_chain.json` in results |
| `kling_native_audio_planner.py` | `plan_kling_frame_from_audio_route`, `build_kling_frame_preflight_api_payload` |
| `product_studio_service.py` | Frame preflight primary; Results API exposes continuity fields; `kling_ft_*` run detection |
| `kling_frame_to_video_live_engine.py` | `clip_index` param for multi-clip runs |

### Results Page

`ui/web/src/pages/ResultsPage.tsx` shows:

- Continuity Method
- Use Frame Status
- Fallback Used
- Clip Count
- Story Progression Status

---

## 6. Validation

`project_brain/validate_kling_use_frame_continuity.py` — **12 checks, all PASS**:

1. Use Frame detected  
2. Use Frame activated  
3. Continuity metadata written  
4. Clip 2 receives Clip 1 continuity (Use Frame)  
5. Fallback works if Use Frame unavailable  
6. Story progression still advances  
7. Existing frame upload path unchanged  
8. Existing multishot path unchanged  
9. Existing download recovery unchanged  
10. No Generate without approval (static gate checks)  
11. Duration model (15–90s)  
12. Frame route detected in preflight  

Run:

```bash
python project_brain/validate_kling_use_frame_continuity.py
```

---

## 7. Success Criteria

| Scenario | Status |
|----------|--------|
| 30s story: Clip 1 → Use Frame → Clip 2 | **Ready** — requires live CDP + credits + recovered MP4 |
| 45s story: Clip 1 → Use Frame → Clip 2 → Use Frame → Clip 3 | **Ready** — same |
| Frame-to-Video primary long-form pipeline | **Implemented** |
| Multishot path unchanged | **Verified** |
| Download recovery unchanged | **Verified** |

### Live test command (after P4 MP4 recovery)

Recover prior clip if needed:

```bash
python tools/kling_frame_to_video_live_p4.py --recover-output --run-id kling_ft_20260617T202616_1e37f8a6
```

Then run Product Studio Generate with frame preflight, 30s duration, and approval flags.

---

## 8. Unchanged Systems

- `kling_continuity_runtime.run_kling_continuity_chain()` — multishot chain  
- `upload_frame_for_next_clip()` — extract/upload fallback  
- `recover_kling_multishot_output()` / `recover_kling_frame_output()` — download recovery  
- Approval gates — `approve_generate`, `approved_by`, `confirm_credit_spend`, per-clip approval  

---

## 9. Next Steps

1. Recover canonical MP4 for run `kling_ft_20260617T202616_1e37f8a6` (>1 MB verified)  
2. Live 30s Use Frame chain with operator approval  
3. Live 45s three-clip chain  
4. Confirm Results Page fields populate from completed chain run  
