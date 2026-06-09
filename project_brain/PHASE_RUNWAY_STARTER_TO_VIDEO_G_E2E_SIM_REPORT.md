# Phase RUNWAY-STARTER-TO-VIDEO-G — End-to-End Simulated Flow Report

**Status:** All PASS  
**Date:** 2026-06-03  
**Validator:** `python project_brain/validate_runway_end_to_end_simulated_flow.py`  
**Flow version:** `runway_starter_to_video_g_e2e_sim_v1`

---

## Summary

End-to-end **simulated** validation chains the full starter-to-video pipeline from story idea through prompt building, continuity planning, dry-run orchestration, semi-auto preparation, and operator approval simulation.

**No browser. No Generate. No Download. No credits.**

---

## Sample Input

**Story idea** (464 chars):

> A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere, neon teal and amber reflections, dramatic volumetric fog, ultra realistic detail. Clip 1: rain intensifies as she turns toward the skyline. Clip 2: she walks along the platform edge with city lights pulsing below. Clip 3: she reaches a dormant launch cradle and places her gloved hand on its surface.

**Project:** `e2e_sim_flow`  
**Clips:** 3  
**Operator (simulated):** `e2e_sim_operator`

---

## Simulated Flow Chain

```
build_continuity_prompts(story)
        ↓
bundle.to_continuity_plan()
        ↓
run_dry_run(plan)                    [Phase D]
        ↓
run_semi_auto_prepare(simulate=True) [Phase E]
        ↓
run_semi_auto_with_approval(...)   [Phase E approval simulation]
        ↓
status: completed
```

---

## Stage Results

| Stage | Module | Result | Key metrics |
|-------|--------|--------|-------------|
| 1 — Prompt builder | `runway_prompt_builder.py` | ✅ PASS | starter 845 chars; clips 2201 / 2239 / 2187 chars |
| 2 — Continuity plan | `runway_continuity_models.py` | ✅ PASS | 9:16, 10s, completion rule OK |
| 3 — Dry-run | `runway_continuity_dry_run.py` | ✅ PASS | 27 steps, 7 approval gates, 19/19 controls |
| 4 — Semi-auto prepare | `runway_continuity_semi_auto.py` | ✅ PASS | Paused at `image_generate_button` after 4 prep steps |
| 5 — Approval simulation | `runway_continuity_approval_guard.py` | ✅ PASS | 7 approvals → `completed` |

---

## Stage 1 — Prompt Builder (Phase F)

```python
bundle = build_continuity_prompts(SAMPLE_STORY, project_id="e2e_sim_flow", clip_count=3)
```

- `starter_image_prompt`: 845 chars (≤ 2500 max)
- `clip_prompts`: 3 prompts in 2000–3500 soft range
- `validate_prompt_bundle`: no warnings
- Continuity anchors extracted (character, location, lighting, camera, palette)

---

## Stage 2 — Continuity Plan

```python
plan = bundle.to_continuity_plan()
```

| Field | Value |
|-------|-------|
| `aspect_ratio` | 9:16 |
| `duration_seconds` | 10 |
| `completion_rule` | `download_mp4_button_visible OR use_frame_button_visible` |
| `clip_prompts` | 3 (matches bundle) |

---

## Stage 3 — Dry-Run Orchestrator (Phase D)

```python
dry = run_dry_run(plan, map_path=runway_ui_map.json)
```

| Check | Value |
|-------|-------|
| `dry.ok` | True |
| Steps | 27 |
| Approval-gated steps | 7 |
| UI controls resolved | 19/19 |
| `image_use_to_video_option` step | Present |
| `remove_image` final step | Present |

---

## Stage 4 — Semi-Auto Prepare (Phase E, simulate=True)

```python
prep = run_semi_auto_prepare(plan, simulate=True)
```

| Check | Value |
|-------|-------|
| `prep.ok` | True |
| Status after advance | `awaiting_approval` |
| Awaiting control | `image_generate_button` |
| Auto prep steps completed | 4 (navigate, fill prompt, 9:16, 2K) |

System auto-prepared mapped controls then **paused before Generate** — correct operator gate behavior.

---

## Stage 5 — Approval Gate Simulation

**Unapproved gate check:**

- `image_generate_button` → `STATE_REQUIRED`, not eligible

**Simulated operator approvals:** 7 total

| # | Control | Purpose |
|---|---------|---------|
| 1 | `image_generate_button` | Starter image generate |
| 2–4 | `generate_button` | Video generate clips 1–3 |
| 5–7 | `download_mp4_button` | Download clips 1–3 |

```python
semi = run_semi_auto_with_approval(plan, simulate=True, approvals=approvals)
```

| Check | Value |
|-------|-------|
| Final status | `completed` |
| Gated steps executed | 7/7 |
| All `approval_granted` | True |
| Completion signals detected | `download_mp4_button`, `use_frame_button` |
| Wrong step_id blocked | True |

---

## Safety Confirmation

| Gate | Result |
|------|--------|
| Browser launched | ❌ No |
| Playwright used | ❌ No |
| `RunwayBrowserProvider` imported | ❌ No |
| Provider mutated | ❌ No |
| `simulate=True` throughout semi-auto | ✅ Yes |
| Generate clicked (live) | ❌ No |
| Download clicked (live) | ❌ No |
| Credits spent | ❌ No |

---

## Validation Output

```
python project_brain/validate_runway_end_to_end_simulated_flow.py
```

**36/36 checks PASS** — `e2e_all_pass: true`

---

## Files

| File | Role |
|------|------|
| `project_brain/validate_runway_end_to_end_simulated_flow.py` | E2E simulated flow validator |
| `content_brain/execution/runway_prompt_builder.py` | Stage 1 |
| `content_brain/execution/runway_continuity_dry_run.py` | Stage 3 |
| `content_brain/execution/runway_continuity_semi_auto.py` | Stages 4–5 |
| `content_brain/execution/runway_continuity_approval_guard.py` | Stage 5 gates |
| `project_brain/runway_ui_mapping/runway_ui_map.json` | Live UI map (19 controls) |

---

## Next Recommended Phase

**PHASE RUNWAY-STARTER-TO-VIDEO-H — Runtime Studio Operator Wiring (Live CDP Pilot)**

- Wire Approve button in Runtime Studio to `RunwayContinuitySemiAutoEngine.approve()` + `advance()`
- Live CDP session with `simulate=False` (operator still approves Generate/Download)
- Persist approval audit trail per session
- Do **not** enable fully autonomous generation until pilot sign-off

---

## Run Command

```bash
python project_brain/validate_runway_end_to_end_simulated_flow.py
```

Expected: all stages PASS, JSON summary with `"all_pass": true`.
