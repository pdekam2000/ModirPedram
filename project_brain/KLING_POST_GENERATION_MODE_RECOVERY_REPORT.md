# KLING POST-GENERATION MODE RECOVERY REPORT

Generated: 2026-06-20

## Problem

After Clip 1 generation completes on Runway, the UI often **switches back to Image mode / Image tab**. The runtime assumed Video/Kling mode was still active when starting Clip 2, so:

- Use Frame could activate but the Video composer was wrong
- Clip 2 prompt / Generate path never executed
- Chain stopped after Clip 1 despite generation success

## Root cause

**Files:** `kling_use_frame_runtime.py`, `kling_frame_to_video_live_engine.py`

1. **No post-generation tab detection** — handoff did not check Image vs Video tab after Clip 1 output
2. **Use Frame without mode recovery** — clicked Use Frame but did not restore Video tab + Kling toolbar
3. **Clip 2 live engine skipped recovery** — `run_kling_frame_to_video_live(clip_index=2)` assumed Frames/Video mode still active

## Fix

### New module: `kling_post_generation_mode_recovery.py`

| Function | Purpose |
|----------|---------|
| `detect_active_runway_tool_tab()` | Detect Image / Video / Audio via aria-selected tabs + URL |
| `recover_video_kling_mode_after_generation()` | Click Video tab → wait for composer → `resolve_kling_3_pro_provider()` |
| `detect_clip_output_visible()` | Confirm Clip 1 output ready before Use Frame |
| `select_use_frame_dropdown_option()` | Handle Use Frame dropdown (First video frame, etc.) |
| `wait_for_continuity_frame_populated()` | Wait until First Video Frame slot populated |

### Updated handoff: `kling_use_frame_runtime_v2`

`apply_continuity_for_next_clip()` now:

1. Detect Clip 1 output visible
2. Click **Use Frame** (+ dropdown if shown)
3. **Recover Video tab + Kling 3.0 Pro** (reuses current-model detection)
4. Wait for First Video Frame populated
5. Return `continuity_frame_in_ui: true` in handoff payload

### Updated Clip 2 live path: `kling_frame_to_video_live_engine.py`

Before Clip 2 provider/prompt steps:

1. `recover_video_kling_mode_after_generation()` when `clip_index > 1` or `continuity_frame_in_ui`
2. Step `post_generation_mode_recovery` recorded (fail-fast if recovery fails)
3. Clip 2 prompt uses `clear_first=True`
4. Aspect ratio 9:16 re-applied on Frames path (preserve settings)

## Flow after fix

```
Clip 1 Generate → generation wait → output visible
  → Use Frame (+ dropdown)
  → detect Image tab → click Video tab
  → confirm Kling 3.0 Pro (model_already_selected)
  → verify First Video Frame populated
  → continuity_frame_in_ui = true
Clip 2 live engine:
  → post_generation_mode_recovery (safety re-check)
  → Frames mode → skip upload
  → clear + write Clip 2 prompt
  → 15s + audio ON → Generate once
```

## Safety

| Rule | Status |
|------|--------|
| No automatic retry Generate | Recovery/handoff modules do not click Generate |
| Max 2 Generate clicks (2-clip plan) | One `run_kling_frame_to_video_live` per clip |
| No Clip 3 | Unchanged `clip_count=2` plans |
| No credit spend in validation | Offline mocks only |

## Validation

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS
python project_brain/validate_kling_post_generation_mode_recovery.py
```

Tests cover:

- Image mode detected after Clip 1
- Video tab recovery + composer ready
- Current-model detection reused via `resolve_kling_3_pro_provider`
- Use Frame handoff sets `continuity_frame_in_ui=true`
- Clip 2 prompt path includes recovery + clear-first
- Generate not clicked in recovery modules
- Mocked 2-clip chain: max 2 generate clicks

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/kling_post_generation_mode_recovery.py` | **New** — tab detection + Video/Kling recovery |
| `content_brain/execution/kling_use_frame_runtime.py` | v2 handoff with mode recovery + dropdown |
| `content_brain/execution/kling_frame_to_video_live_engine.py` | Clip 2 preflight recovery, clear prompt, aspect preserve |
| `content_brain/execution/kling_frame_continuity_runtime.py` | Read `continuity_frame_in_ui` from handoff |
| `project_brain/validate_kling_post_generation_mode_recovery.py` | Offline validation |

## Live re-test

Run only after validation passes:

```powershell
python project_brain/run_kling_real_2clip_15s_live_test.py
```

Expected: Clip 2 starts after Clip 1 even when UI returns to Image tab post-generation.
