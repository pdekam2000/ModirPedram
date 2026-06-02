# PHASE RUNWAY-UI-MAPPER-C — Click-to-Label Report

**Date:** 2026-05-31  
**Status:** Implemented  
**Validator:** `project_brain/validate_runway_ui_mapper_click_label.py`

## Goal

Let operators label Runway UI controls by clicking them in the live Chrome CDP session instead of matching stable element IDs in the terminal.

## What was added

### CLI

```bash
python tools/runway_ui_mapper.py --click-label
python tools/runway_ui_mapper.py --click-label --allow-safe-clicks
```

- Connects to Chrome at `http://127.0.0.1:9222`
- Picks the active Runway tab
- Injects a capture-phase click listener with highlight + banner
- On each click: prints metadata, asks **What is this control?** and optional **What does this control do?**
- Saves to `project_brain/runway_ui_mapping/runway_ui_map.json`
- Type `q` + Enter in the terminal to exit and append a `labeling_sessions[]` record

### Label shape (`labels[label_name]`)

```json
{
  "element_id": "btn_001",
  "metadata": { "tag", "text", "aria_label", "css_selector", "bounding_box", "page_url", ... },
  "selector_candidates": { "css": "...", "playwright": "page.locator(...)" },
  "operator_confirmed": true,
  "confirmed_at": "ISO8601",
  "notes": "operator behavior note",
  "auto_click_allowed": false,
  "requires_approval": true
}
```

`generate_button` and Generate-like UI text also set `requires_real_video_approval: true` for backward compatibility with mapper-B.

### Safety

| Rule | Behavior |
|------|----------|
| Dangerous UI text (generate, create, submit, buy, upgrade, subscribe, delete, purchase) | `preventDefault` + `stopPropagation` in capture phase |
| Default (no `--allow-safe-clicks`) | All clicks blocked |
| `--allow-safe-clicks` | Only dangerous text blocked; harmless controls (10s, 16:9, etc.) may receive real clicks |
| `generate_button` / Generate-like capture | `auto_click_allowed=false`, `requires_approval=true` |
| Storage | `sanitize_click_metadata` drops cookie/token/localStorage/sessionStorage keys |

### Files touched

- `tools/runway_ui_mapper.py` — `CLICK_LABEL_INSTALL_JS`, `mode_click_label`, `persist_click_label`, `merge_clicked_element`, `labeling_sessions`
- `project_brain/validate_runway_ui_mapper_click_label.py` — new validator
- `project_brain/PHASE_RUNWAY_UI_MAPPER_C_CLICK_TO_LABEL_REPORT.md` — this report

## Operator workflow

1. Start Chrome with remote debugging on port 9222 and open Runway editor.
2. Optional: `python tools/runway_ui_mapper.py --scan` to seed element inventory.
3. Run `python tools/runway_ui_mapper.py --click-label`.
4. Click each control in Runway; enter labels such as `prompt_box`, `duration_10s`, `aspect_ratio_16_9`, `generate_button`.
5. Press `q` + Enter when done.

## Validation

```bash
python project_brain/validate_runway_ui_mapper_click_label.py
```

Checks:

1. Click metadata capture + sanitization  
2. Operator labels persisted with `operator_confirmed`  
3. Generate-like controls never `auto_click_allowed`  
4. Dangerous semantics blocked in JS + Python safety  
5. JSON round-trip valid  
6. `--scan` / `--label` / `--observe` still present  
7. No cookie/token/localStorage/sessionStorage in saved metadata  

## Success criteria

Operator can run `--click-label`, click Runway controls one by one, and build a confirmed `labels` map without manually typing element IDs.
