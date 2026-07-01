# UI Runtime Regression Fix Report

**Date:** 2026-06-18  
**Scope:** Product Studio Create Video — aspect ratio 16:9 regression + placeholder starter frame  
**Method:** Runtime/UI path inspection (not validator-only)

---

## Executive summary

| Issue | Root cause | Fix |
|-------|------------|-----|
| Shorts showing 16:9 | (1) Stale `ui/web/dist` bundle without aspect selector; (2) Kling live engine never applied aspect ratio on Runway UI; (3) Placeholder PNG was 1920×1080 (16:9) uploaded to Frames mode | Rebuilt frontend; platform-aware aspect resolution; clip 1 text-to-video applies 9:16 via `MappedRunwayUINavigator` |
| Golden placeholder visible | `ensure_kling_starter_frame_path()` auto-generated purple/gold gradient PNG and uploaded it as clip 1 first frame | Removed from Product Studio generate path; clip 1 = prompt-only text-to-video |

---

## 1. Why Create Video showed 16:9

### Investigation path

| Layer | Finding |
|-------|---------|
| **Frontend default state** | `CreateVideoPage.tsx` initializes `platform=youtube_shorts`, `aspectRatio=defaultAspectRatioForPlatform("youtube_shorts")` → `9:16` |
| **Channel profile** | `project_brain/product_settings/channel_profile.json` → `default_platform: "youtube_shorts"`, no `aspect_ratio` override |
| **Backend preflight** | `resolve_aspect_ratio(platform=youtube_shorts)` → `9:16` |
| **Stale bundle (confirmed)** | Old `ui/web/dist/assets/index-DJUs6TCb.js` contained **no** `Aspect ratio` / `defaultAspectRatioForPlatform` strings. Operator UI was serving outdated build. |
| **Runway/Kling browser UI** | `kling_frame_to_video_live_engine.py` always selected **Frames** mode and uploaded starter PNG (1920×1080). Runway toolbar stayed **16:9**. No aspect chip was ever set. |

### What overwrote 9:16

Not the Create Video form defaults — the **Runway generate page** during live clip 1:

1. Frames mode selected
2. 1920×1080 placeholder uploaded → Runway inferred horizontal
3. No `aspect_ratio_menu` / `aspect_ratio_9_16` click

### Fixes applied

- **`ui/web` rebuild:** `npx vite build` → `dist/assets/index-B1B5bBso.js` (contains `9:16 (Vertical)`, `Aspect ratio`)
- **`CreateVideoPage.tsx`:** `aspectRatioManual` flag; platform change resets aspect unless user manually changed selector
- **`platform_aspect_defaults.py`:** Stale `16:9` on vertical platforms coerced to `9:16` unless `aspect_ratio_manual=true`
- **`kling_frame_to_video_live_engine.py`:** Clip 1 text-to-video path calls `_apply_video_aspect_ratio()` via `MappedRunwayUINavigator.ensure_menu_setting("aspect_ratio_menu", "aspect_ratio_9_16", ...)`

---

## 2. Why placeholder starter frame appeared

### Investigation path

| Check | Result |
|-------|--------|
| Starter frame component in React UI | **None** — no starter frame preview in `CreateVideoPage.tsx` |
| Placeholder source | `kling_starter_frame_generator.py` → `_render_local_starter_frame()` draws purple/cyan gradient + gold ellipse at **1920×1080** |
| Generation flow | `kling_product_run.py` called `ensure_kling_starter_frame_path()` before every frame-to-video generate |
| Live upload | `kling_frame_continuity_runtime.py` clip 1 required `starter_frame_path`; `run_kling_frame_to_video_live()` uploaded PNG to Runway |

### UI-only vs generation?

**Both.** The golden ring was not a React placeholder — it was the **actual PNG uploaded into Runway Frames mode** and a **hard precondition** for clip 1 generate.

### Fixes applied (approved architecture)

| Clip | Mode |
|------|------|
| **Clip 1** | Text-to-video, prompt only — no PNG, no upload, no `starter_frame_required` |
| **Clip 2+** | Frames mode + Use Frame continuity from prior clip |

**Files changed:**

- `kling_product_run.py` — removed `ensure_kling_starter_frame_path()` from generate path
- `kling_frame_continuity_runtime.py` — clip 1 passes `starter_frame_path=None`; clip 2+ requires prior Use Frame handoff
- `kling_frame_to_video_live_engine.py` — clip 1 branch: Video mode + aspect + prompt; skip upload
- `kling_frame_to_video_planner.py` — clip 1 `first_frame_source: "prompt_only"`
- `kling_native_audio_planner.py` — preflight exposes `clip1_generation_mode`, `clip1_starter_frame_required: false`

---

## 3. Runtime evidence (actual UI path)

Evidence file: `project_brain/ui_runtime_regression_evidence.json`

### Backend preflight (live service call)

```json
{
  "platform": "youtube_shorts",
  "aspect_ratio": "9:16",
  "clip1_generation_mode": "text_to_video_prompt_only",
  "clip1_starter_frame_required": false,
  "first_clip_source": "prompt_only"
}
```

### Frontend state (source)

```typescript
// CreateVideoPage.tsx initial + payload
platform: "youtube_shorts"
aspectRatio: "9:16"  // from defaultAspectRatioForPlatform
aspect_ratio_manual: false  // until user changes selector
```

### Generate runtime (mocked _execute_kling_clips — proves wiring)

```json
{
  "first_frame_path_passed_to_runtime": null,
  "aspect_ratio_in_payload": "9:16",
  "clip1_starter_frame_required": false,
  "generate_status": "completed"
}
```

### Channel profile

```json
{ "default_platform": "youtube_shorts" }
```

### Frontend bundle (post-fix)

| Artifact | Proof |
|----------|-------|
| `ui/web/dist/assets/index-B1B5bBso.js` | Contains `9:16 (Vertical)` and aspect selector strings |
| Previous stale bundle | `index-DJUs6TCb.js` — missing aspect UI |

### Screenshot source paths (live Kling generate)

On next operator Generate (clip 1), live engine captures:

| Step | Screenshot path pattern |
|------|-------------------------|
| Video mode selected | `project_brain/runway_ui_mapping/screenshots/kling_frame_to_video_live/03_video_mode_selected.png` |
| Aspect 9:16 applied | `.../04_aspect_ratio_applied.png` |
| Prompt filled (no upload) | `.../05_prompt_filled.png` |

*(Not captured in this session — no live CDP/Kling credit spend per operator instruction.)*

---

## 4. Operator verification checklist

When opening Create Video with YouTube Shorts:

- [ ] **Aspect ratio selector** shows **9:16 (Vertical)** (hard refresh if cached: Ctrl+Shift+R on Vite dev `:5173`)
- [ ] Preflight panel shows `Aspect Ratio: 9:16`
- [ ] After Generate clip 1: Runway shows **Video** mode (not Frames), **no uploaded image**, toolbar **9:16**
- [ ] Clip 2+: Frames mode with Use Frame from clip 1 output

---

## 5. Validation

```
python project_brain/validate_product_studio_default_kling_ux.py
→ All Product Studio default Kling UX checks passed.
```

Key new checks:

- `clip1_no_starter_frame` — generate passes empty first_frame to runtime
- `clip1_mode` / `clip1_source` — preflight declares `text_to_video_prompt_only` / `prompt_only`

---

## 6. Architecture preserved

- Clip 2+ continuity validation unchanged (`ensure_prior_clip_continuity_language`)
- Story-first prompts unchanged
- `kling_starter_frame_generator.py` retained for P3/P4 tooling only — **not wired to Product Studio**
