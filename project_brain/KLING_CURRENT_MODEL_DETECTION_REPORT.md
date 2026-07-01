# KLING CURRENT MODEL DETECTION REPORT

Generated: 2026-06-20

## Problem

Live Runway generate pages often **already have Kling 3.0 Pro active** when automation connects:

- Generate button visible
- **Kling 3.0 Pro** shown in bottom toolbar
- Prompt editor loaded
- Duration and aspect ratio controls visible

The runtime still executed:

1. Find **Video models**
2. Open model picker
3. Select **Kling 3.0 Pro**

When the picker was not open, `locate_control()` fell through to the `Video models` strategy and **timed out** — even though the page was already in Kling mode.

## Root cause

**File:** `content_brain/execution/kling_multishot_locator.py`

`provider_kling_3_pro` strategies were tried sequentially:

1. `role_button_kling_3_pro`
2. `text_kling_3_pro`
3. **`role_button_video_models`** ← 8s timeout when picker closed

No pre-check existed for **current model already selected**. Both live engines called `locate_control()` directly and treated a missing picker as failure.

## Fix

Added current-model detection and a resolver that **skips the picker** when Kling is already active.

### New helpers (`kling_multishot_locator.py`)

| Function | Purpose |
|----------|---------|
| `detect_kling_3_pro_current_model(page)` | Returns `model_already_selected`, `detected_text`, `generate_visible`, `prompt_editor_ready` |
| `try_locate_kling_3_pro_active(page)` | Fast probe for visible Kling 3.x Pro toolbar/button/text |
| `resolve_kling_3_pro_provider(page, entry)` | Detection-first resolver; only calls `locate_control()` (picker path) when not already in Kling |

### Detection signals

1. Visible button/text matching `Kling 3.x Pro`
2. **Generate** button visible + prompt editor ready + body text contains `Kling 3.x Pro` (Case C — picker unavailable)

When `model_already_selected = true`:

- Skip open model picker
- Skip model search/selection click
- Proceed to aspect ratio → duration → audio → generate

### Engine integration

| File | Change |
|------|--------|
| `kling_frame_to_video_live_engine.py` | Step 02 uses `resolve_kling_3_pro_provider`; sets `checklist.model_already_selected` |
| `kling_multishot_live_engine.py` | Step 01 uses same resolver; skips provider click when already selected |

Checklist field: `model_already_selected: true` written to `approval_checklist.json` / live result payloads.

## Validation cases

| Case | Scenario | Expected |
|------|----------|----------|
| **A** | Page already in Kling 3.0 Pro | Skip picker; `strategy=model_already_selected:*` |
| **B** | Page not in Kling | Call `locate_control()` → Video models / picker path |
| **C** | Picker unavailable, Kling visible in body + Generate + prompt | PASS via `body_text_generate_prompt_ready` |

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS
python project_brain/validate_kling_current_model_detection.py
```

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/kling_multishot_locator.py` | Detection + `resolve_kling_3_pro_provider` |
| `content_brain/execution/kling_frame_to_video_live_engine.py` | Step 02 provider gate |
| `content_brain/execution/kling_multishot_live_engine.py` | Step 01 provider gate |
| `project_brain/validate_kling_current_model_detection.py` | Offline validation (Cases A/B/C) |

## Expected live behavior

When Chrome CDP connects to an already-configured Kling generate tab:

1. Step 02 (frame) / 01 (multishot) passes in **<3s** with `model_already_selected=true`
2. No timeout on **Video models**
3. Flow continues to aspect ratio, duration, audio, Generate unchanged

Generation, prompt, and credit-spend paths are **not modified** — only provider preflight detection.
