# Phase I — Clip 1 → Clip 2 Workspace Transition Audit

**Date:** 2026-06-04  
**Failure step:** `020_video_prompt_clip_2`  
**Error:** `Locator.click: Timeout 30000ms exceeded` waiting for `div[aria-label="Prompt"].first`  
**Scope:** Post-download state, post–Use Frame state, prompt workspace readiness, Clip 2 entry conditions only.  
**Out of scope:** StoryBrief Builder, Prompt Builder, Assembly, Voice, Subtitle.

---

## Executive summary

Clip 1 completed successfully (generate → completion → download approval → Use Frame click logged). The run failed when **Clip 2 prompt fill** tried to click the mapped video prompt control. The failure is **not** a missing StoryBrief or prompt text issue — it is a **Runway UI workspace / state-machine gap** between Clip 1 handoff and Clip 2 prompt entry.

**Primary hypothesis (confirmed by logs):** After Clip 1 download and Use Frame, the browser was still on a valid video session URL, but the **video prompt editor (`div[aria-label="Prompt"]`) was not in a clickable state** (hidden, covered, unloaded, or replaced by session/clip chrome). The engine still believed the workspace was ready because it reuses a **stale `video_transition_verified` flag** from the starter Use-to-Video step and does not re-validate prompt readiness after download or Use Frame.

---

## Evidence from last live run

**Source:** `project_brain/runway_phase_i_3clip_last_report.json` (project `phase_i_live`)

| Signal | Value | Interpretation |
|--------|--------|----------------|
| `stopped_reason` | `step failed at 020_video_prompt_clip_2` + Prompt locator timeout | Failure at Clip 2 prompt fill, not generate/download |
| `clips_completed` | `1` | Clip 1 generation cycle reached completion waiter |
| `video_completion_detected` | `true` | `download_mp4_button` and `use_frame_button` were visible after Clip 1 |
| `approvals_granted` | image generate, clip 1 generate, clip 1 download | Through Clip 1 download gate |
| `use_frame_after_clips` | `[]` (empty) | Run failed before progress markers recorded Use Frame for clip 1 |
| `page_url` (end) | `...mode=sessions&tool=video&sessionId=...` | Still video session route |
| `video_transition_verified` (implicit) | Still true from starter routing | Stale gate for Clip 2 |
| Action log tail | download click → use_frame click → fill_prompt (fail) | See sequence below |

### Action log sequence (tail)

```
wait_completion_done     → download_mp4_button, use_frame_button
click download_mp4_button → mapped css=svg (approved)
click use_frame_button    → mapped_text=Use frame
fill_prompt prompt_input  → chars=2574 → TIMEOUT on click
```

Earlier in the same run:

```
fill_prompt prompt_input → chars=2588   ← Clip 1 prompt fill SUCCEEDED
```

So **the same selector worked for Clip 1** and **failed for Clip 2** after download + Use Frame.

---

## Planned step order (Clip 1 → Clip 2)

From `runway_continuity_dry_run.py` (31 steps):

```
017  wait_until_completion_signal_clip_1
018  download_mp4_clip_1              ← approval gate
019  use_frame_for_clip_2             ← auto click Use Frame
020  video_prompt_clip_2               ← FAIL: fill_prompt → click Prompt
021  select_duration_10s_clip_2
022  video_generate_manual_required_clip_2
...
```

There is **no** manual hold, **no** workspace settle wait, and **no** post-download / post–Use Frame readiness step between 018–020.

---

## Part 1 — Post-download state audit

### What the engine does today

**Module:** `runway_continuity_semi_auto.py` → `download_mp4_clip_*` / `final_download_clip_*`

```python
nav.click_control("download_mp4_button", step_id=..., approved=gate_approved)
```

**Module:** `runway_ui_navigator.py` → `click_control`

- Clicks mapped selector for `download_mp4_button` (live log: `mapped css=svg` — **high ambiguity**).
- No wait for browser save dialog to close.
- No wait for new file on disk (Phase I.5 tracker runs separately in live smoke markers; this run showed `clip_1_downloaded=false`, `downloaded_file_paths=[]`).
- No check that `prompt_input` remains visible after download.

### Likely Runway UI behavior after Download

| Scenario | Effect on Clip 2 |
|----------|------------------|
| Native browser save dialog opens | Blocks automation; prompt not focusable |
| Download toast / modal overlay | `is_visible()` may still pass for elements underneath |
| Focus moves to clip thumbnail / timeline | Prompt editor deprioritized or unmounted |
| Session panel expands on completed clip 1 | Prompt `div[aria-label="Prompt"]` not in DOM or `display:none` |

### Audit conclusion — post-download

**Download approval succeeded; download workspace stabilization did not.**

The pipeline treats “download button clicked” as step complete. It does **not** verify:

- Save dialog dismissed  
- Prompt workspace restored  
- `prompt_input` visible **and** enabled for Clip 2  

---

## Part 2 — Post–Use Frame state audit

### What the engine does today

**Module:** `runway_continuity_semi_auto.py`

```python
if step_key.startswith("use_frame_for_clip_"):
    nav.click_control("use_frame_button")
    return
```

- Single click on `use_frame_button`.
- No follow-up wait for reference frame to load into the composer.
- No re-check of `prompt_input`.
- No screenshot gate specific to post–Use Frame.

### Mapped control weakness

**Source:** `project_brain/runway_ui_map.json`

| Control | Selector | Risk |
|---------|----------|------|
| `use_frame_button` | `span` + text fallback `"Use frame"` | Generic `span` — may match wrong control |
| `prompt_input` | `div[aria-label="Prompt"]` | Contenteditable div; may not exist until composer ready |
| `download_mp4_button` | `svg` | Any visible SVG on page |

Action log shows Use Frame click via `mapped_text=Use frame` — click returned success, but **success does not prove** the frame was applied to the **video prompt** workspace.

### Likely Runway UI behavior after Use Frame

| Scenario | Effect |
|----------|--------|
| Use Frame applies frame to timeline but prompt UI not refocused | Click on Prompt times out |
| Prompt cleared/replaced; new empty state not mounted yet | Locator not attached |
| Clip 2 expects operator to select clip row first | Prompt only appears after selection |
| Reference image strip covers prompt area | Visible in DOM but not clickable |

### Audit conclusion — post–Use Frame

**Use Frame click executed; Use Frame → prompt-ready transition was not verified.**

---

## Part 3 — Prompt workspace readiness detection audit

### Current detection (`verify_video_generation_transition`)

**Module:** `runway_ui_navigator.py`

```python
verified = (
    "tool=video" in url.lower()
    or is_control_visible("prompt_input")
    or is_control_visible("generate_button")
)
```

Problems for Clip 2:

1. **URL check** — Still `tool=video` after download/Use Frame even when prompt is unusable → **false positive**.
2. **OR generate_button** — May remain visible while Prompt div is not → **false positive**.
3. **Called once** after starter `use_starter_image_for_video`; result stored on `last_latest_image_card.video_transition_verified` and **never refreshed** before Clip 2.

### Clip 2 entry gate (`video_prompt_clip_*`)

**Module:** `runway_continuity_semi_auto.py`

```python
if latest is None or not latest.video_transition_verified:
    raise RuntimeError("video transition not verified before filling video prompt")
nav.fill_prompt_control("prompt_input", clip.prompt)
```

This checks **starter-era transition state**, not **post–Clip 1 handoff state**.

### Pre-step visibility check (`_verify_page_state_before_advance`)

**Module:** `runway_live_smoke_test.py`

- Runs `is_control_visible(control_key)` for the **current** step before `engine.advance()`.
- For step 020, control is `prompt_input`.
- If this passed, then `fill_prompt` timed out on click → classic **visible but not interactable** (overlay, opacity, pointer-events, off-screen, or detached).

If this did not run (timing/index edge), failure still occurs inside `fill_prompt_control` → `locator.click()`.

### `fill_prompt_control` behavior

**Module:** `runway_ui_navigator.py`

```python
locator = self._locator_for(ctrl)  # div[aria-label="Prompt"]
locator.click(force=True, timeout=prep_timeout_ms)  # 30s default
```

- No scroll-into-view for prompt.
- No wait for Runway session UI to finish loading after Use Frame.
- No fallback selectors for Clip 2+.

### Audit conclusion — readiness detection

**Readiness detection is insufficient for multi-clip continuity.** It validates “we entered video mode once at starter” not “prompt editor is ready for Clip N.”

---

## Part 4 — Clip 2 entry conditions (required vs actual)

| Requirement (operator expectation) | Implemented today | Gap |
|-----------------------------------|-------------------|-----|
| Clip 1 fully generated | `wait_until_completion_signal_clip_1` | OK |
| Clip 1 downloaded (file + UI settled) | `download_mp4` click only | No UI settle / file verify in semi-auto |
| Last frame seeded for Clip 2 | `use_frame_for_clip_2` click | No confirm frame applied to prompt |
| Video prompt workspace active | Stale `video_transition_verified` | **Stale flag** |
| `prompt_input` visible & clickable | Optional pre-advance check; then click | **Failed at click** |
| Clip 2 prompt text filled | `fill_prompt_control` | Never reached fill |

---

## Root cause chain (ranked)

1. **Stale workspace flag** — `video_transition_verified` set at step 011 (`use_starter_image_for_video`), reused at step 020 without re-probe.  
2. **Missing transition steps** — No `wait_for_prompt_workspace_ready` after download or Use Frame.  
3. **Post-download UI interference** — Save dialog / session chrome / focus loss after `download_mp4_button` (svg).  
4. **Post–Use Frame UI lag** — Prompt composer not remounted when automation clicks `div[aria-label="Prompt"]`.  
5. **Weak selectors** — `svg` (download), `span` (use frame) increase wrong-click or partial UI transition risk.  
6. **False-positive completion rule** — `use_frame_button` visible alongside download does not mean prompt is ready for next clip.

---

## Modules responsible (fix ownership)

| Concern | Primary module | Secondary |
|---------|----------------|-----------|
| Clip 2 entry gate | `runway_continuity_semi_auto.py` | `runway_live_smoke_test.py` |
| Prompt fill / click | `runway_ui_navigator.py` | — |
| Video workspace verify | `runway_ui_navigator.py` | — |
| Step plan (no settle steps) | `runway_continuity_dry_run.py` | — |
| Pre-advance visibility | `runway_live_smoke_test.py` | — |
| Selector map | `project_brain/runway_ui_mapping/runway_ui_map.json` | `runway_ui_map_loader.py` |
| **Not responsible** | `runway_story_brief_builder.py` | `runway_prompt_builder.py` |

---

## Recommended fixes (workspace transition only)

Do **not** change StoryBrief or Prompt Builder. Suggested engineering in navigator + semi-auto + dry-run plan only:

### A. Re-verify workspace before each `video_prompt_clip_N` (N ≥ 2)

- Call new `ensure_video_prompt_workspace_ready(clip_index)` that:
  - Polls up to N seconds for `prompt_input` visible **and** enabled (Playwright `is_enabled()`).
  - Optionally requires `generate_button` visible.
  - Fails with diagnostic screenshot + URL + visible button list (reuse `collect_phase_i_failure_diagnostics` pattern).

### B. Post-download settle step (auto, non-approval)

After `download_mp4_clip_1`:

- Wait for absence of native dialog (or fixed delay + operator-dismiss note in manual hold if needed).
- Poll `prompt_input` or session “ready for next clip” signal.
- Log `post_download_prompt_visible=true/false`.

### C. Post–Use Frame settle step

After `use_frame_for_clip_2`:

- Click Use Frame (existing).
- Wait for prompt workspace (new helper).
- Log `use_frame_applied=true`, `prompt_ready_after_use_frame=true`.
- Screenshot `clip2_post_use_frame`.

### D. Invalidate stale transition flag

- Set `video_transition_verified=False` after each download until re-verified.
- Or stop using starter card state for clip ≥ 2; use per-clip workspace state object.

### E. Selector hardening (map only)

- Replace `download_mp4_button` css=`svg` with operator-confirmed unambiguous selector near completed clip.
- Replace `use_frame_button` css=`span` with button/menu item tied to last frame.

### F. Optional manual hold (operator-friendly)

- `manual_required` hold after Clip 1 download: “Dismiss save dialog; confirm timeline shows Clip 1 complete; click Continue.”

---

## Operator instructions (next live Clip 2 attempt)

Until workspace fixes land:

1. After **Download MP4** approval for Clip 1:
   - Dismiss any browser save dialog.
   - Confirm Clip 1 appears complete in the Runway session timeline.
2. When automation clicks **Use Frame**:
   - Confirm the last frame of Clip 1 is applied as reference (thumbnail/strip update).
   - Confirm the **Prompt** box is visible and empty (or ready to edit) before Clip 2 auto-fill runs.
3. If Prompt is hidden, click into the video composer / new clip row, then retry from **Runway Live Smoke** (or add manual continue if hold step added).
4. Attach on failure:
   - `project_brain/runway_phase_i_3clip_last_report.json`
   - `project_brain/runway_live_smoke_artifacts/phase_i_live_failure_*.png`
   - `project_brain/runway_phase_i_last_failure_diagnostics.json` (if present)

---

## Validation suggestions (future, out of this audit doc)

Add `validate_phase_i_clip2_workspace_transition.py` (when implementing fixes):

- Simulate plan includes post-download / post–use-frame settle steps before `video_prompt_clip_2`.
- Unit: `ensure_video_prompt_workspace_ready` fails when prompt not visible.
- Unit: stale `video_transition_verified` alone does not authorize clip 2 fill.
- Regression: Clip 1 `fill_prompt` path unchanged.

---

## Summary

| Phase | Status in live run |
|-------|-------------------|
| Starter image → video (011) | Working (per operator + logs) |
| Clip 1 prompt fill (013) | Working (`chars=2588`) |
| Clip 1 generate + complete (016–017) | Working |
| Clip 1 download click (018) | Click OK; disk/UI settle **not verified** |
| Use Frame for Clip 2 (019) | Click OK; prompt readiness **not verified** |
| Clip 2 prompt fill (020) | **FAILED** — `div[aria-label="Prompt"]` not clickable |

**Verdict:** Phase I multi-clip failure is a **Clip 1 → Clip 2 workspace transition** problem in `runway_ui_navigator` + `runway_continuity_semi_auto`, not content generation logic. Fix by re-probing prompt workspace after download and Use Frame, and by not reusing starter-only `video_transition_verified` for Clip 2 entry.
