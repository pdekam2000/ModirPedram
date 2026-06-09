# Phase RUNWAY-STARTER-TO-VIDEO-D — Dry-Run Orchestrator Foundation Report

**Status:** Complete (simulation only — no credits spent)  
**Date:** 2026-06-03  
**Validator:** `python project_brain/validate_runway_starter_to_video_dry_run.py` → **PASS**

---

## Summary

Phase D delivers a **read-only dry-run orchestrator** for the Runway **Image Generation → Use to Video → multi-clip continuity** workflow. It loads operator-mapped UI controls, builds an ordered step plan, validates mandatory controls, and marks dangerous actions as operator-approval-gated. **No browser launch, no Generate click, no Download click, no provider execution, no credit spend.**

**Do not use Multi-Shot Video.** Clip 1 must enter Video Generation via **App menu → Use to Video** on the starter image.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/runway_ui_map_loader.py` | Load `runway_ui_map.json`, normalize labels, resolve 19 canonical controls, reject body/html on critical controls, warn on weak selectors |
| `content_brain/execution/runway_continuity_models.py` | `StarterImagePlan`, `VideoClipPlan`, `RunwayContinuityPlan`, `RunwayContinuityStep`, `RunwayDryRunResult` |
| `content_brain/execution/runway_continuity_dry_run.py` | Build step plan, validate controls, simulate workflow only |
| `project_brain/validate_runway_starter_to_video_dry_run.py` | Unit + live map validation (37 checks) |

## Files Modified

| File | Change |
|------|--------|
| *(none in tracked repo)* | Phase D adds new modules only; existing `RunwayBrowserProvider`, Hailuo, provider router, and browser hardening were **not touched** |

---

## Controls Loaded from Map

**Source:** `project_brain/runway_ui_mapping/runway_ui_map.json`

**Canonical controls (19 required):**

| Control | Live map status |
|---------|-----------------|
| `image_prompt_input` | ✅ resolved |
| `image_aspect_ratio_menu` | ✅ resolved (weak: `span`) |
| `image_aspect_ratio_9_16` | ✅ resolved |
| `image_quality_menu` | ❌ **missing** |
| `image_quality_2k` | ❌ **missing** |
| `image_generate_button` | ✅ resolved |
| `image_app_menu_button` | ✅ resolved |
| `image_use_to_video_option` | ✅ resolved (weak: `span`, tolerated) |
| `gen45_model_button` | ✅ resolved (alias: `Gen-4.5`) |
| `try_it_now_button` | ✅ resolved (alias: `Try it now`) |
| `prompt_input` | ✅ resolved (alias: `Prompt Box`) |
| `aspect_ratio_menu` | ✅ resolved (weak: `span`) |
| `aspect_ratio_9_16` | ✅ resolved (weak: `span`) |
| `duration_menu` | ✅ resolved (weak: `span`) |
| `duration_10s` | ✅ resolved (weak: `span`) |
| `generate_button` | ✅ resolved |
| `download_mp4_button` | ✅ resolved (weak: `svg`; no longer `body`) |
| `use_frame_button` | ✅ resolved (weak: `span`, tolerated) |
| `remove_image` | ✅ resolved |

**Live snapshot:** 17/19 controls resolved. Dry-run `ok=False` until image quality controls are mapped.

---

## Missing / Weak Controls

### Missing (blocks full dry-run `ok`)

- `image_quality_menu` — not yet labeled in mapper session
- `image_quality_2k` — not yet labeled in mapper session

**Action before Phase E:** Run `python tools/runway_ui_mapper.py --hover-label` on Runway Image Generation quality menu + 2K option.

### Weak selectors (warn only — dry-run continues)

| Control | Selector | Notes |
|---------|----------|-------|
| `image_aspect_ratio_menu` | `span` | Generic; refine when possible |
| `image_use_to_video_option` | `span` | Tolerated (popup menu item) |
| `aspect_ratio_menu` | `span` | Generic |
| `aspect_ratio_9_16` | `span` | Generic |
| `duration_menu` | `span` | Generic |
| `duration_10s` | `span` | Generic |
| `download_mp4_button` | `svg` | Hover-label capture; acceptable for now |
| `use_frame_button` | `span` | Tolerated (continuity control) |

### Invalid (critical body/html)

- **None** on live map (`download_mp4_button` fixed via hover-label mode)

---

## Default Settings (Plan Model)

| Setting | Default |
|---------|---------|
| Target platform | `shorts` (Shorts/Reels/TikTok/YouTube Shorts) |
| Aspect ratio | `9:16` |
| Duration | `10s` |
| Image quality | `2K` |
| Video model | Gen-4.5 (via mapped `gen45_model_button`) |
| Max wait per clip | 20 minutes |
| Completion rule | `download_mp4_button_visible OR use_frame_button_visible` |

---

## Dry-Run Step List (3-clip example)

Ordered simulated workflow (`run_default_dry_run_demo(clip_count=3)` → **27 steps**):

### Starter image (A–H)

| # | Step ID | Action |
|---|---------|--------|
| 1 | `image_generation_open` | Open Runway Image Generation |
| 2 | `fill_image_prompt` | Simulate fill starter image prompt |
| 3 | `select_image_9_16` | Simulate select 9:16 |
| 4 | `select_image_2k` | Simulate select 2K |
| 5 | `image_generate_manual_required` | **STOP** — operator clicks Generate (image) |
| 6 | `wait_for_image_ready_manual` | **STOP** — wait for image output |
| 7 | `image_app_menu` | Simulate open App menu |
| 8 | `image_use_to_video` | Simulate **Use to Video** → Video Gen with reference |

### Clip 1 (I–M)

| # | Step ID | Action |
|---|---------|--------|
| 9 | `video_prompt_clip_1` | Simulate fill clip 1 prompt |
| 10 | `select_video_aspect_9_16_clip_1` | Verify 9:16 (inherited from starter) |
| 11 | `select_duration_10s_clip_1` | Simulate select 10s |
| 12 | `video_generate_manual_required_clip_1` | **STOP** — operator clicks Generate (video) |
| 13 | `wait_until_completion_signal_clip_1` | Poll until download OR use_frame visible |
| 14 | `download_mp4_clip_1` | **STOP** — download clip 1 MP4 |

### Clips 2–3 (N–O repeat)

| # | Step ID | Action |
|---|---------|--------|
| 15–20 | clip 2 chain | `use_frame` → prompt → duration → generate (manual) → wait → download |
| 21–25 | clip 3 chain | `use_frame` → prompt → duration → generate (manual) → wait |

### Final clip (P–Q)

| # | Step ID | Action |
|---|---------|--------|
| 26 | `final_download_clip_3` | **STOP** — final MP4 download (no `use_frame`) |
| 27 | `remove_image_clip_3` | Simulate `remove_image` — clear reference |

---

## Safety Gates

Enforced in `runway_continuity_dry_run.py` (`SAFETY_GATES`):

1. `no_browser_launch`
2. `no_generate_click`
3. `no_download_click`
4. `no_credit_spend`
5. `no_provider_execution`
6. `no_runway_browser_provider_mutation`
7. `simulated_steps_only`
8. `dangerous_steps_require_operator_approval`

### Operator-approval-gated controls (`requires_operator_approval=true`)

| Control | When |
|---------|------|
| `image_generate_button` | Starter image generate |
| `generate_button` | Each video clip generate |
| `download_mp4_button` | Each clip download + final download |

---

## No Credits Spent — Confirmation

| Check | Result |
|-------|--------|
| Browser launched | ❌ No |
| Generate clicked | ❌ No |
| Download clicked | ❌ No |
| `RunwayBrowserProvider` invoked | ❌ No |
| Provider router / Hailuo touched | ❌ No |
| All steps `simulated=True` | ✅ Yes |
| Validator `no_generate_click` / `no_download_click` | ✅ PASS |

---

## Validation Results

```
python project_brain/validate_runway_starter_to_video_dry_run.py
```

- Map loader loads all required controls (mock map)
- body/html critical selectors fail safely
- Weak selectors warn only (do not fail)
- Starter image workflow included
- Use to Video step included
- Completion rule uses `download_mp4_button OR use_frame_button`
- Final clip uses `remove_image`
- No Generate / Download execution in dry-run module
- 3-clip plan produces 27 steps
- Missing `image_use_to_video_option` fails safely
- Missing `remove_image` fails safely
- Defaults: 9:16, 10s, 2K

---

## Next Recommended Phase

### PHASE RUNWAY-STARTER-TO-VIDEO-E — Operator-Approved Semi-Automation

**Prerequisites:**

1. Map `image_quality_menu` and `image_quality_2k` in mapper session
2. Live dry-run returns `ok=True`

**Phase E may allow (with operator approval still required for Generate/Download):**

- Auto-fill prompts
- Auto-select aspect ratio, duration, quality, model
- Auto wait/poll for completion signals (`download_mp4_button` OR `use_frame_button`)

**Phase E must still block until tested:**

- Unattended Generate clicks
- Unattended Download clicks
- Credit spend without explicit operator approval

---

## Usage

```python
from content_brain.execution.runway_continuity_dry_run import (
    build_continuity_plan,
    run_dry_run,
)

plan = build_continuity_plan(
    project_id="my_project",
    starter_image_prompt="Vertical neon portrait starter frame.",
    clip_prompts=["Clip 1 motion", "Clip 2 motion", "Clip 3 motion"],
)
result = run_dry_run(plan)
print(result.ok, len(result.steps), result.errors)
```

```bash
python project_brain/validate_runway_starter_to_video_dry_run.py
```
