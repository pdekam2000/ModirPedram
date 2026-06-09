# Phase RUNWAY-STARTER-TO-VIDEO-E — Operator-Approved Semi-Automation Report

**Status:** Complete (simulate default; live browser optional)  
**Date:** 2026-06-03  
**Validators:**
- `python project_brain/validate_runway_starter_to_video_dry_run.py` → **PASS** (19/19 controls, `ok=True`)
- `python project_brain/validate_runway_starter_to_video_semi_auto.py` → **PASS**

---

## Pre-Phase E Confirmation (Phase D gate)

| Check | Result |
|-------|--------|
| All controls resolved | ✅ 19/19 |
| `image_quality_menu` | ✅ resolved |
| `image_quality_2k` | ✅ resolved |
| Dry-run `ok=True` | ✅ |

---

## Summary

Phase E adds **operator-approved semi-automation** on top of Phase D dry-run planning. The system auto-prepares Runway (mapped navigation, prompt fill, 9:16, 2K, 10s duration, completion polling) and **pauses** before every dangerous action until the operator explicitly approves.

**Still approval-gated (not removed):**
- `image_generate_button`
- `generate_button`
- `download_mp4_button`

**Not in scope:** fully autonomous generation, provider router changes, `RunwayBrowserProvider` mutation.

---

## Operator Flow

1. Operator starts semi-auto session (`run_semi_auto_prepare`)
2. System auto-runs prep steps (image prompt, 9:16, 2K)
3. **Pause** → awaiting approval for `image_generate_button`
4. Operator clicks **Approve** → system clicks Generate (only after approval)
5. Manual/simulated wait for starter image output
6. System auto-runs App menu → Use to Video → clip prep
7. **Pause** → awaiting approval for `generate_button`
8. Operator approves → Generate
9. System auto-waits for `download_mp4_button OR use_frame_button`
10. **Pause** → awaiting approval for `download_mp4_button`
11. Operator approves → Download
12. Repeat for clips 2+ (`use_frame_button` auto)
13. Final clip: download (approved) → `remove_image` (auto)

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/runway_continuity_approval_guard.py` | Approval gate evaluation, grant, dangerous-action block |
| `content_brain/execution/runway_ui_navigator.py` | Mapped selector navigation (fill, click, menu, completion poll) |
| `content_brain/execution/runway_continuity_semi_auto.py` | Semi-auto engine, session state, advance/approve API |
| `project_brain/validate_runway_starter_to_video_semi_auto.py` | Phase E validator (simulate mode) |

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/runway_continuity_models.py` | Added semi-auto session/result/approval models |
| `content_brain/execution/runway_ui_map_loader.py` | Exported public `selector_is_weak()` helper |

## Files Not Modified

- `providers/runway_browser_provider.py`
- Provider router, Hailuo, browser hardening
- Phase D dry-run orchestrator behavior (unchanged)

---

## Safety Gates

```
no_autonomous_generate
no_autonomous_download
dangerous_steps_require_operator_approval
no_runway_browser_provider_mutation
no_provider_router_execution
mapped_selectors_only
completion_via_download_or_use_frame
semi_auto_preparation_allowed
```

---

## Allowed vs Gated Actions

| Action | Phase E behavior |
|--------|------------------|
| Load UI map | ✅ auto |
| Navigate mapped pages | ✅ auto |
| Fill image prompt | ✅ auto |
| Select 9:16 (image + video verify) | ✅ auto |
| Select 2K | ✅ auto |
| Fill video prompt | ✅ auto |
| Select duration 10s | ✅ auto |
| App menu → Use to Video | ✅ auto |
| Use Frame (between clips) | ✅ auto |
| Remove image (final clip) | ✅ auto |
| Completion signal poll | ✅ auto |
| Image Generate | ⛔ operator approval |
| Video Generate | ⛔ operator approval |
| Download MP4 | ⛔ operator approval |

---

## Validation Highlights

- Unapproved `generate_button` click raises `PermissionError`
- `run_semi_auto_prepare` pauses at `image_generate_button` after 4 prep steps
- Simulated 3-clip flow completes with 7 explicit approvals (1 image + 3 generate + 3 download)
- All executed dangerous steps record `approval_granted=True`
- Live map: 19/19 controls, dry-run `ok=True`, semi-auto prepare pauses correctly

---

## Usage

```python
from content_brain.execution.runway_continuity_semi_auto import (
    build_continuity_plan,
    run_semi_auto_prepare,
    run_semi_auto_with_approval,
)
from content_brain.execution.runway_continuity_semi_auto import RunwayContinuitySemiAutoEngine
from content_brain.execution.runway_continuity_approval_guard import grant_continuity_approval
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

plan = build_continuity_plan(
    project_id="my_short",
    starter_image_prompt="Vertical cinematic portrait, neon rain.",
    clip_prompts=["Beat 1", "Beat 2", "Beat 3"],
)

# Step 1: auto-prep until first approval gate (simulate=True default)
result = run_semi_auto_prepare(plan, simulate=True)
print(result.session.status, result.session.awaiting_control_key)

# Step 2: operator approves, then advance (attach real page with simulate=False for live)
navigator = MappedRunwayUINavigator.from_map(simulate=False, page=page)
engine = RunwayContinuitySemiAutoEngine(navigator)
engine.approve(
    result.session,
    control_key="image_generate_button",
    step_id=result.session.awaiting_step_id or "",
    approved_by="operator",
)
engine.advance(result.session)
```

---

## Next Recommended Phase

**PHASE RUNWAY-STARTER-TO-VIDEO-F — Live Browser Semi-Auto Pilot**

- Wire semi-auto engine to Runtime Studio operator Approve button
- Live CDP browser session (`simulate=False`)
- Persist approval audit trail per session
- Optional: map `wait_for_image_ready` completion signal
- Keep Generate/Download gated until pilot sign-off

---

## No Fully Autonomous Generation

Phase E intentionally does **not** remove approval gates. Credits are only spent when the operator has approved the specific Generate/Download step for that clip.
