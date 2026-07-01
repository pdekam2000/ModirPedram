# Kling Preflight Schema Mismatch — Fix Report

**Phase:** KLING-PREFLIGHT-SCHEMA-MISMATCH-FIX  
**Status:** FIXED — validation PASS  
**Date:** 2026-06-18

---

## 1. Problem

`collect_kling_preflight_warnings()` accessed `clip.shot_1` / `clip.shot_2` for all Kling plans. Product Studio routes the primary Kling path to **Frame-to-Video** (`KlingFrameToVideoClipPlan` with `clip.prompt`), causing:

```
AttributeError: 'KlingFrameToVideoClipPlan' object has no attribute 'shot_1'
```

Broken endpoints:
- `POST /product/create-video/preflight`
- `POST /product/create-video/generate` (preflight stage)

---

## 2. Files Changed

| File | Change |
|------|--------|
| `content_brain/execution/kling_native_audio_planner.py` | Added `_clip_prompt_length_warnings()`; updated `collect_kling_preflight_warnings()` |
| `project_brain/validate_kling_preflight_schema_mismatch_fix.py` | New validation suite |

**Not changed:** UI, live generation, Product Studio routing, Runway/Hailuo paths.

---

## 3. Exact Fix

Added schema-aware helper `_clip_prompt_length_warnings(clip)`:

- **Multishot clips** (`shot_1`, `shot_2`): warn when shot prompt exceeds `KLING_SHOT_PROMPT_MAX_CHARS` (512)
- **Frame-to-Video clips** (`prompt`): warn when frame prompt exceeds `KLING_FRAME_PROMPT_MAX_CHARS` (2500)
- Unknown clip shapes: append `unknown_clip_schema` warning (no crash)

`collect_kling_preflight_warnings()` now:

1. Uses `getattr(plan, "duration_warnings", ())` for both plan types
2. Delegates per-clip checks to `_clip_prompt_length_warnings()`
3. Never accesses `shot_1` on frame clips

---

## 4. Validation Results

### New suite

```bash
python project_brain/validate_kling_preflight_schema_mismatch_fix.py
```

| Test | Result |
|------|--------|
| Kling Frame-to-Video preflight returns 200 | **PASS** |
| Frame warnings collect without AttributeError | **PASS** |
| Frame-to-Video prompt length warning works | **PASS** |
| Multishot warning collection still works | **PASS** |
| Runway preflight still returns 200 | **PASS** |
| Hailuo preflight still returns 200 | **PASS** |
| Generate preflight stage no schema error | **PASS** |
| No `shot_1` access for Frame-to-Video clips | **PASS** |

### Regression reruns

```bash
python project_brain/validate_kling_frame_architecture_switch.py   # PASS
python project_brain/validate_story_progression_engine_p5.py       # PASS
```

### Live API (uvicorn :8765)

```
POST /product/create-video/preflight
provider=kling, audio_strategy=kling_native_audio
→ HTTP 200, ok=True, kling_shot_mode=kling_frame_to_video_native_audio
```

---

## 5. Confirmations

| Item | Status |
|------|--------|
| Kling GUI preflight works | **Confirmed** — service + live API 200 |
| Frame-to-Video remains primary Kling path | **Unchanged** |
| Multishot fallback preserved | **Confirmed** — shot_1/shot_2 warnings still work |
| Runway preflight unaffected | **Confirmed** |
| Hailuo preflight unaffected | **Confirmed** |
| No credits spent | **Confirmed** — preflight/warning logic only |

---

## 6. Risk Assessment

| Risk | Level |
|------|-------|
| Regression on multishot warnings | **Low** — explicit branch retained |
| Frame prompt false positives | **Low** — uses existing 2500 char limit |
| Live generate other failures | **Unchanged** — only preflight warning path fixed |
