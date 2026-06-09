# RUNWAY COMPLETION DETECTION REPORT

**Phase:** RUNWAY-BROWSER-CONTINUITY-C  
**Date:** 2026-06-03  
**Prior phases:** Phase A mapping audit, Phase B relabeling guide  
**Scope:** Analysis and validation prep only — no Runway automation, no Generate automation, no provider execution changes.

---

## Executive summary

Runway Gen-4.5 exposes **output controls only after generation completes**. Parsing queue/status text is fragile and was never reliably mapped. Phase C replaces `generation_status` as a **hard requirement** with a **completion-by-visibility rule**:

```text
generation_complete =
    download_mp4_button visible
    OR
    use_frame_button visible
```

Poll the page every **30–60 seconds** after Generate (operator-approved) until this condition is true, then download and continue the clip chain.

One new required label supports project hygiene after the final clip: **`remove_image`**.

---

## Rationale

### Why drop `generation_status` as required

| Approach | Problem |
|----------|---------|
| Queue / progress text | Copy changes, localization, nested React trees; never consistently labeled |
| Video URL detection (existing orchestrator) | Works for download but fires at different timing than UI output card |
| **Output control visibility** | Same moment the operator uses Download / Use Frame; aligns with manual workflow |

Runway’s Gen-4.5 tools session shows **`download_mp4_button`** and **`use_frame_button`** together on the completed clip card. Either signal means the generation is done enough to proceed.

`generation_status`, `queue_status_text`, and `progress_status_text` remain **optional** semantic labels if an operator wants to map them later — they are not gating validator pass.

### Why `download_mp4_button` must be re-labeled

The current map entry `DOWNLOAD MP4` points at:

- `tag=body`
- `selector=body`

That is **invalid** for automation. The operator must Shift+Click the **per-clip Download control** on the completed output view (not page body, not “Download all”).

Until relabeled, `completion_signals_ready=false` and validation **fails** even if `use_frame_button` exists.

### Why tolerate weak `use_frame_button` selectors (temporarily)

`use_frame_button` is present but uses a generic `span` selector. Phase C:

- Does **not** fail validation on generic selector / page-path warnings for `use_frame_button`
- Emits `WEAK_SELECTOR_TOLERATED` info for future relabeling
- Still **fails** if mapped to `body` / `html`

---

## Continuity workflow

### Clip 1 (cold start)

1. Open video generation  
2. Select Gen-4.5  
3. Click Try it now  
4. Fill `prompt_input`  
5. Set `aspect_ratio_9_16` (default Shorts / Reels / TikTok)  
6. Set `duration_10s` via `duration_menu`  
7. Operator clicks `generate_button` (approval-gated — not automated in this phase)

### Wait loop (all clips)

```text
every 30–60 seconds:
  if download_mp4_button visible OR use_frame_button visible:
    generation_complete = true
    break
  else:
    continue polling (bounded max wait in orchestrator TBD)
```

No dependency on status text parsing.

### After completion (non-final clip)

1. Click `download_mp4_button` → save MP4  
2. Click `use_frame_button` → seeds next clip from last frame  
3. Fill next `prompt_input`  
4. Operator clicks `generate_button`  
5. Repeat wait → download → use frame

### Final clip

1. Wait for completion (same rule)  
2. Click `download_mp4_button` → save MP4  
3. **Do not** click `use_frame_button`  
4. Click `remove_image` — clears reference image left by Use Frame so the next project starts clean

---

## Label normalization (canonical keys)

| Raw / legacy label | Canonical key |
|--------------------|---------------|
| `Prompt Box` | `prompt_input` |
| `Gen-4.5` / `Ge-4.5` | `gen45_model_button` |
| `Try it now` | `try_it_now_button` |
| `Geerate` | `generate_button` |
| `VIEDO DURATION KONOPF` | `duration_menu` |
| `10s duration` | `duration_10s` |
| `aspect_ratio_menu 16:9` | `aspect_ratio_16_9` |
| `aspect_ratio_menu 9: 16` | `aspect_ratio_9_16` |
| `DOWNLOAD MP4` | `download_mp4_button` |
| `USE FRAME` | `use_frame_button` |
| `REMOVE IMAGE` / `Remove image` | `remove_image` |

View normalization without editing the map:

```bash
python tools/runway_ui_mapper.py --normalize-continuity
```

---

## Required labels (Phase C validator)

### Required (13)

**Prerequisites**

- `prompt_input`
- `gen45_model_button`
- `try_it_now_button`
- `generate_button`

**Editor / settings**

- `duration_menu`
- `duration_10s`
- `aspect_ratio_menu`
- `aspect_ratio_16_9`
- `aspect_ratio_9_16`

**Output / continuity**

- `download_mp4_button` — must not be `body`/`html`
- `use_frame_button` — weak selector tolerated; must not be `body`/`html`
- `remove_image` — clear reference image after final clip

### Optional

- `generation_status`
- `queue_status_text`
- `progress_status_text`

### Completion signals (subset of required)

At least one must be **valid** (non-body selector):

- `download_mp4_button`
- `use_frame_button`

---

## Validator impact

### Commands

```bash
python tools/runway_ui_mapper.py --validate-continuity
python tools/runway_ui_mapper.py --normalize-continuity
python project_brain/validate_runway_mapping_continuity_controls.py
```

### Pass criteria changes (B → C)

| Check | Phase B | Phase C |
|-------|---------|---------|
| `generation_status` required | Yes | **No** (optional) |
| `remove_image` required | No | **Yes** |
| Completion detection | Status text (planned) | **Output controls OR rule** |
| `use_frame_button` weak selector | Warning → fail on some paths | **Warning only** |
| `download_mp4_button` = body | Fail | **Still fail** |
| `completion_signals_ready` | N/A | **Must be true** |

### Report fields added

- `completion_rule` — documented expression and poll interval  
- `completion_signals_ready` — at least one valid completion signal in map  
- `normalized_labels` — canonical → source alias / selector view  
- `optional_present` — e.g. legacy `generation_status` if mapped  

---

## Current map status (at Phase C authoring)

Based on Phase B/C validation against `runway_ui_map.json`:

| Label | Status |
|-------|--------|
| Prerequisites + menus | Present (legacy alias names) |
| `use_frame_button` | Present — weak `span` selector (tolerated) |
| `download_mp4_button` | Present as `DOWNLOAD MP4` — **invalid (`body`)** |
| `remove_image` | **Missing** — operator must label after final-clip cleanup UI |
| `generation_status` | Not required |

**Blocking actions before orchestrator wiring:**

1. Re-label `download_mp4_button` from completed output Download control  
2. Label `remove_image` on reference-image remove/clear control  

---

## Future orchestrator implications (Phase D+ — not implemented here)

When provider wiring is approved:

1. **Wait loop** — replace or supplement URL-based wait with DOM poll for completion signals every 30–60s (keep bounded timeout ~15 min).  
2. **Dual signal** — succeed if either mapped control becomes visible; prefer `download_mp4_button` for download step.  
3. **Multi-clip state machine**  
   - `clip_index < total`: download → `use_frame_button` → next prompt  
   - `clip_index == total`: download → `remove_image` → skip use frame  
4. **Map loader** — resolve canonical keys via `build_continuity_normalized_labels()`; heuristics fallback unchanged until map entries valid.  
5. **Generate** — remains approval-gated; no change in Phase C.  
6. **Optional status labels** — may enrich observability/logging only; not completion gate.

### Pseudocode (orchestrator sketch)

```python
def wait_for_generation_complete(page, ui_map, poll_seconds=45, max_wait=900):
    while elapsed < max_wait:
        if control_visible(page, ui_map, "download_mp4_button"):
            return "download_ready"
        if control_visible(page, ui_map, "use_frame_button"):
            return "output_ready"
        sleep(poll_seconds)
    raise TimeoutError("completion signals never appeared")
```

---

## Safety confirmation

| Item | Status |
|------|--------|
| Runway browser automation in Phase C | **No** |
| Generate auto-click | **No** |
| Provider execution modified | **No** |
| Credits spent by tooling | **No** |

---

## Related documents

- `PHASE_RUNWAY_BROWSER_CONTINUITY_A_MAPPING_AUDIT_REPORT.md`  
- `PHASE_RUNWAY_BROWSER_CONTINUITY_B_RELABELING_GUIDE.md`  
- `tools/runway_ui_mapper.py` — `GENERATION_COMPLETE_RULE`, `validate_continuity_mapping()`  
- `project_brain/validate_runway_mapping_continuity_controls.py`
