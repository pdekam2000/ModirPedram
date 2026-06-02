# RUNWAY UI Mapping — Safe Discovery + Manual Learning

**Phase:** RUNWAY-UI-MAPPER-B  
**Tool:** `tools/runway_ui_mapper.py`  
**Output:** `project_brain/runway_ui_mapping/`  
**Full report:** `project_brain/PHASE_RUNWAY_UI_MAPPER_B_MANUAL_LEARNING_REPORT.md`

---

## Purpose

Inspect a **live, manually logged-in** Runway Chrome session via CDP and produce a structured map of UI controls for automation hardening — **without spending credits**.

---

## Safety guarantees

| Rule | Enforcement |
|------|-------------|
| No Generate click | Read-only by default; Generate never clicked even in interactive mode |
| No video creation | No Generate / Create / Submit clicks |
| No credentials | JSON stores URLs/titles only — no cookies, tokens, localStorage, sessionStorage |
| No auto-login | User opens Chrome and logs in manually |
| Blocked clicks (interactive only) | `Generate`, `Create`, `Submit`, `Upgrade`, `Purchase`, `Buy`, `Subscribe`, `Delete` |

---

## Prerequisites

1. Start Chrome with remote debugging on `http://127.0.0.1:9222` (same as ModirAgentOS browser bridge).
2. Open [Runway](https://app.runwayml.com) and log in manually.
3. Navigate to the Gen-4.5 / video generate editor you want mapped.

---

## Usage

```bash
# Scan (read-only, default)
python tools/runway_ui_mapper.py --scan

# Label controls interactively
python tools/runway_ui_mapper.py --label

# Observe manual clicks (tool never clicks)
python tools/runway_ui_mapper.py --observe

# Specific tab / CDP
python tools/runway_ui_mapper.py --scan --tab-index 0 --cdp-url http://127.0.0.1:9222
```

**Validation:**

```bash
python project_brain/validate_runway_ui_mapper.py
```

---

## Outputs

| Artifact | Description |
|----------|-------------|
| `project_brain/runway_ui_mapping/runway_ui_map.json` | Full structured map |
| `project_brain/runway_ui_mapping/screenshots/00_full_page.png` | Full-page capture |
| `project_brain/runway_ui_mapping/screenshots/01_viewport.png` | Viewport capture |
| `project_brain/runway_ui_mapping/screenshots/02_overlay_numbered.png` | Numbered bounding boxes (when Pillow available) |

---

## JSON schema (summary)

- `current_page` — URL, title, `is_runway_url`
- `open_tabs` — all CDP tabs (safe URLs only)
- `categories` — grouped candidates:
  - `prompt_inputs`
  - `generate_buttons` (always `click_blocked: true`)
  - `try_it_now_buttons`
  - `video_mode_controls`
  - `model_selector_controls` / `gen45_selector`
  - `duration_controls` (5s / 10s)
  - `aspect_ratio_controls` (16:9 / 9:16)
  - `first_video_frame_upload` / `reference_image_upload`
  - `download_buttons`
  - `generated_video_cards`
  - `queue_progress_text`
  - `all_visible_buttons` / `all_elements_sample`
- Per element: `css_selector`, `playwright_locator_hint`, `bounding_box`, `visible`, `categories`, `click_blocked`
- `safety` — explicit flags (no secrets stored)
- `screenshots` — relative paths to PNGs

---

## Workflow recommendation

1. Land on Gen-4.5 apps page → run mapper (read-only).
2. Click **Try it now** manually → run mapper again on editor tab.
3. Set 16:9 + 10s manually → run mapper to capture stable control labels.
4. Compare `runway_ui_map.json` with `providers/runway_browser_provider.py` selectors.

---

## Notes

- Mapper **detects** Generate buttons but **does not click** them.
- If CDP is offline, validation still passes static checks; live checks warn and skip.
- Re-run after Runway UI updates to refresh `runway_ui_map.json`.
