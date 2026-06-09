# RUNWAY UI Mapper — ALT_CLICK_AND_FORCE_MODE_FIX

**Date:** 2026-05-31  
**Status:** Implemented  
**Command:** `python tools/runway_ui_mapper.py --click-label`

## Problem

Shift+Click was unreliable on Runway (modifier not detected or events consumed before mapper handlers).

## Solution

Replaced Shift capture with two reliable modes:

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Alt+Click** | Hold Alt + click element | Block real click, open label popup |
| **Mapper ON** | Click top-right `Mapper: ON` | Every click captures (blocks site click, opens popup) |
| **Mapper OFF** | Click `Mapper: OFF` | Normal website behavior |
| **Normal click** | No Alt, Mapper OFF | Website works normally |

## UI

- Fixed button top-right: **Mapper: OFF** / **Mapper: ON**
- Label popup unchanged: Label input, Save, Cancel
- Save bridge unchanged: DOM `data-runway-mapper-pending-save` + console + CDP

## Capture implementation

- `pointerdown`, `mousedown`, `click` — `capture: true`, `passive: false`
- Active when: `event.altKey === true` OR `window.__runwayMapperForceMode === true`
- Alt fallback: `window.__runwayMapperAltDown` via keydown/keyup on Alt
- On capture: `preventDefault`, `stopPropagation`, `stopImmediatePropagation`, `openPopup(ev.target)`
- Mapper UI (popup + toggle) excluded via `data-runway-mapper-ui` / `data-runway-mapper-popup`
- Installed on all frames; re-injected on `framenavigated`

## Manual validation

1. `python tools/runway_ui_mapper.py --click-label`
2. Normal click → Runway navigates normally
3. **Alt+Click** element → popup opens, no Runway action
4. Top-right **Mapper: OFF** visible
5. Click **Mapper: ON** → button turns blue
6. Single-click any element → popup opens
7. Save label → terminal: `Saved label '...' -> runway_ui_map.json`
8. **Mapper: OFF** → normal clicks restored

## Debug

Console logs `MAPPER_CLICK` with `altKey`, `forceMode`, `captureActive` per event.

## Files

- `tools/runway_ui_mapper.py` — Alt+Click + force mode + toggle button
- `project_brain/PHASE_RUNWAY_UI_MAPPER_ALT_CLICK_AND_FORCE_MODE_FIX.md` — this report

Save logic and DOM polling were not changed.

## Popup button fix (2026-05-31)

Save/Cancel failed because capture-phase `stopImmediatePropagation` on the popup blocked button handlers.

- Popup root id: `runway-mapper-popup`
- Toggle id: `runway-mapper-toggle`
- Capture handlers return immediately when `popup.contains(event.target)` or `toggle.contains(event.target)`
- Removed blanket stop listeners on popup
- Save sets `data-runway-mapper-pending-save` directly; Cancel calls `closePopup()` in JS
- Debug: `MAPPER_POPUP_SAVE_CLICKED`, `MAPPER_POPUP_CANCEL_CLICKED`
