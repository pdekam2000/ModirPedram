# Phase I Starter Image — Pre-Clean + Use for Video Fix Report

**Date:** 2026-06-03  
**Issue:** Live Phase I failed at `013_video_prompt_clip_1` with `Locator.click Timeout 30000ms` after Image Ready approval.

---

## Root cause hypothesis

Two compounding issues:

1. **Missing explicit Use-for-Video routing after Image Ready** — the plan assumed App menu → Use to Video would always transition to the video workspace. Runway often exposes **Apply / Use for Video / Use to Video** directly on the newest result card; if that action is not clicked, `prompt_input` is not on the current page and clip 1 prompt fill times out.

2. **Cleanup navigated away from video UI too early** — `cleanup_used_image_card_after_use_to_video` called `_return_to_image_generation_board()` before clip 1 video work, which could leave the session on the image board while the next step expected video controls.

3. **Stale image preview state** — a prior result card or open preview/modal before Generate could confuse card selection or block the result action area.

---

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/runway_continuity_dry_run.py` | Added `preclean_starter_image_workspace`; replaced `image_app_menu` + `image_use_to_video` with `use_starter_image_for_video` |
| `content_brain/execution/runway_continuity_semi_auto.py` | Handlers for preclean + consolidated use-starter routing |
| `content_brain/execution/runway_ui_navigator.py` | `preclean_starter_image_workspace()`, `use_starter_image_for_video()`, multi-label fallback, failure diagnostics collector; cleanup defers physical remove on video page |
| `content_brain/execution/runway_live_smoke_test.py` | Preclean report fields, failure diagnostics JSON writer, step-order guards |
| `project_brain/validate_runway_phase_i_starter_image_use_for_video.py` | **New** validator |
| `project_brain/PHASE_I_STARTER_IMAGE_USE_FOR_VIDEO_FIX_REPORT.md` | **This report** |

**Unchanged:** provider router, approval gate semantics (still 7 gates), StoryBrief Builder, Prompt Builder core logic.

---

## New step 012 behavior — `use_starter_image_for_video`

Sequence after Image Ready:

```
011_wait_for_image_ready_manual
→ clear_image_prompt_after_generation (unchanged prep)
→ 012_use_starter_image_for_video   ← NEW consolidated step
→ cleanup_used_image_card_after_use_to_video (mark-only on video page)
→ 013_video_prompt_clip_1
```

**012 actions:**

1. Locate newest starter image card (diff vs pre-generate snapshot).
2. Try direct buttons on the card with fallback labels (priority order):
   - Use for Video, Use to Video, Use in video, Use image, Image to Video, Apply, Create Video, Video
3. Prefer enabled buttons on the **latest result card**; log all candidates.
4. If direct click fails, fall back to App menu → Use to Video.
5. Wait until video UI is visible (`tool=video`, `prompt_input`, or `generate_button`).
6. Only then advance to `video_prompt_clip_1`.

Does **not** click Generate Video before the video prompt is filled.

---

## Pre-clean behavior — `preclean_starter_image_workspace`

Runs **before** `image_generate_button` approval:

- Inspects image workspace for stale dialogs, modals, or preview close buttons.
- Clicks safe Close/Dismiss controls only (skips delete/account/billing/project destructive text).
- Logs skipped unsafe overlays.

**Report / log fields:**

| Field | Meaning |
|-------|---------|
| `preclean_attempted` | Pre-clean step ran |
| `stale_image_preview_detected` | Stale overlay/preview found |
| `stale_preview_closed` | Safe close clicked |
| `preclean_notes` | Human-readable actions/skips |

---

## Failure diagnostics

On failure at `use_starter_image_for_video` or `video_prompt_clip_1`, writes:

`project_brain/runway_phase_i_last_failure_diagnostics.json`

**Fields:**

- `timestamp`, `step_id`, `error`, `screenshot_path`
- `current_url`, `page_title`
- `visible_buttons`, `image_result_area_text`
- `selector_attempted`
- `stale_image_preview_detected`, `stale_preview_closed`, `preclean_notes`
- `use_for_video_candidates_visible`, `use_for_video_action_used`
- `latest_image_card_index`

Screenshot captured to `project_brain/runway_live_smoke_artifacts/` when live CDP is active.

---

## Validation results

```bash
python project_brain/validate_runway_phase_i_starter_image_use_for_video.py  # 33/33 PASS
python project_brain/validate_runway_story_brief_builder.py                  # 34/34 PASS
python project_brain/validate_runway_phase_i_3clip_live_continuity.py        # 26/26 PASS
```

Confirmed:

- Pre-clean safe when no stale preview; closes simulated stale preview when present
- `use_starter_image_for_video` inserted after wait, before `video_prompt_clip_1`
- Apply / Use for Video labels recognized
- 7 approval gates unchanged
- No provider router / StoryBrief / Prompt Builder regression

---

## Operator instruction — next live re-run

1. **Execution Center → Runway Live Smoke → 3-Clip Continuity (Phase I) → Start 3-Clip Live (CDP)**
2. At **Generate (image)** approval: confirm workspace looks clean (no old preview blocking the board).
3. After generation completes, click **Image Ready** when the **new** starter image is visible.
4. **Do not manually navigate** — the runner will:
   - click Apply / Use for Video / Use to Video on the newest card (or App menu fallback)
   - wait for the video generation page
   - then pause at clip 1 video prompt prep
5. If it fails again, attach:
   - `project_brain/runway_phase_i_last_failure_diagnostics.json`
   - latest screenshot from `project_brain/runway_live_smoke_artifacts/`
   - `project_brain/runway_phase_i_3clip_last_report.json`

**Do not use UAT Runtime** for Phase I continuity (see `PHASE_UAT_RUNWAY_PHASE_I_ROUTING_AUDIT_REPORT.md`).
