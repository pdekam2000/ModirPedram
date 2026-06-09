# PHASE RUNWAY-UI-MAPPER-D — Shift+Click Label Popup Report

**Date:** 2026-05-31  
**Status:** Implemented  
**Validator:** `project_brain/validate_runway_ui_mapper_shift_click_label.py`

## Problem

Phase C `--click-label` blocked all normal clicks, preventing Runway navigation (menus, dropdowns, pages).

## Solution

Same command, new UX:

```bash
python tools/runway_ui_mapper.py --click-label
```

| Input | Behavior |
|-------|----------|
| **Normal click** | Passes through — Runway works normally |
| **Shift + Click** | Blocks click, highlights element, opens floating label popup |

## In-page popup

Near the clicked element:

- **Label** — e.g. `duration_10s`, `prompt_box`, `generate_button`
- **Notes / function** — optional operator description
- **Parent label** — optional, e.g. `duration_menu` for menu options
- **Type** — `direct_button`, `dropdown_menu`, `hover_menu`, `menu_option`, `upload_area`, `status_text`, `input_box`
- **Save** — persists via `runwayMapperSaveLabel` Playwright binding
- **Cancel** / **Esc** — closes popup without saving

## Save format

```json
"labels": {
  "duration_menu": { "control_type": "dropdown_menu", "options": { ... } },
  "duration_10s": {
    "element_id": "btn_002",
    "metadata": { "text", "aria_label", "css_selector", "bounding_box", ... },
    "selector_candidates": { "css", "playwright" },
    "operator_confirmed": true,
    "confirmed_by": "shift_click_popup",
    "control_type": "menu_option",
    "parent_label": "duration_menu",
    "auto_click_allowed": true,
    "requires_approval": false
  }
}
```

Menu options are also nested: `labels.duration_menu.options.duration_10s`.

## Safety

- Shift+Click on Generate / Create / Submit / Buy / Upgrade / Subscribe / Delete / Purchase: click blocked, label still savable
- Saved entries: `auto_click_allowed=false`, `requires_approval=true` when appropriate

## Dropdown / menu workflow

1. Normal-click `duration_menu` to open dropdown  
2. Shift+Click `10s` → label `duration_10s`, parent `duration_menu`, type `menu_option`  
3. Repeat for `aspect_ratio_menu` → `aspect_ratio_16_9`, `model_menu` → `gen45_option`

## Validation

```bash
python project_brain/validate_runway_ui_mapper_shift_click_label.py
```

## Files changed

- `tools/runway_ui_mapper.py` — Shift+Click listener, popup UI, `process_popup_save_payload`, parent nesting
- `project_brain/validate_runway_ui_mapper_shift_click_label.py`
- `project_brain/PHASE_RUNWAY_UI_MAPPER_D_SHIFT_CLICK_LABEL_POPUP_REPORT.md`
