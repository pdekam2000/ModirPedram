# PHASE RUNWAY-UI-MAPPER-B — Manual Learning Mode

**Date:** 2026-06-02  
**Tool:** `tools/runway_ui_mapper.py`  
**Outputs:** `project_brain/runway_ui_mapping/`

---

## Goal

Let operators **teach** what Runway UI controls mean (not only auto-detect), using a logged-in Chrome CDP session — with zero credit spend and no credential storage.

---

## Modes

| Mode | Command | Behavior |
|------|---------|----------|
| **Scan** | `python tools/runway_ui_mapper.py --scan` | Read-only CDP scan; stable IDs (`btn_001`, `input_001`, …); saves candidates + v2 map + screenshots |
| **Label** | `python tools/runway_ui_mapper.py --label` | Interactive CLI: assign semantic labels to element IDs |
| **Observe** | `python tools/runway_ui_mapper.py --observe` | Polls UI; on manual operator clicks records before/after + asks action meaning |

Default (no flag) = **scan** (same as `--scan`).

### Batch labeling (non-interactive)

```bash
python tools/runway_ui_mapper.py --label-batch "element_id=btn_003 label=prompt_box
element_id=btn_012 label=generate_button"
```

---

## Semantic labels (operator)

`prompt_box`, `generate_button`, `try_it_now_button`, `duration_10s`, `aspect_ratio_16_9`, `model_selector`, `gen45_option`, `first_video_frame_upload`, `reference_image_upload`, `download_button`, `generated_video_card`, `queue_status_text`, `progress_status_text`, `skip`, `unknown`

### Generate safety defaults

When labeled `generate_button`:

```json
{
  "auto_click_allowed": false,
  "requires_real_video_approval": true
}
```

---

## Action labels (observe mode)

`open_editor`, `set_duration_10s`, `set_aspect_ratio_16_9`, `open_first_video_frame`, `open_reference_image`, `open_model_menu`, `select_gen45`, `open_duration_menu`, `open_aspect_menu`, `focus_prompt_box`, `other`

Observe records: URL/title/body changes, added/removed/changed elements, active element, full before/after snapshots. **Tool never clicks** (`tool_auto_clicked: false`).

---

## Output files

| File | Contents |
|------|----------|
| `selector_candidates.json` | Flat scan list with `element_id`, locators, bbox, nearby text |
| `runway_ui_map.json` | v2 schema: `elements`, `labels`, `actions`, `safety`, `scan` |
| `screenshots/` | `00_full_page`, `01_viewport`, `02_overlay_numbered` (IDs on boxes) |

### v2 schema (summary)

```json
{
  "version": "runway_ui_mapper_v2",
  "created_at": "...",
  "updated_at": "...",
  "page": { "url", "title", "is_runway_url" },
  "open_tabs": [],
  "elements": { "btn_001": { "element_id", "text", "css_selector", "playwright_locator", ... } },
  "labels": { "prompt_box": { "element_id", "semantic_label", "auto_click_allowed", ... } },
  "actions": { "set_duration_10s": { "before", "after", "diff", "tool_auto_clicked": false } },
  "safety": {
    "auto_click_blocklist": ["generate", "create", ...],
    "requires_approval": ["generate_button"]
  }
}
```

---

## Safety

- No Generate / Create / Submit / Buy / Upgrade / Subscribe / Delete / Purchase **clicks by tool**
- No cookies, tokens, localStorage, sessionStorage in output
- No auto-login
- Missing Runway tab → clear error (no silent fallback to random tabs)

---

## Recommended workflow

1. Log into Runway in Chrome (`:9222` debugging).
2. `--scan` on Gen-4.5 landing.
3. Manually open editor → `--scan` again (refresh candidates).
4. `--label` important controls (prompt, Generate, 10s, 16:9, Try it now).
5. `--observe` while clicking duration/ratio menus; name each action.
6. Use `runway_ui_map.json` labels in `runway_browser_provider.py` hardening.

---

## Validation

```bash
python project_brain/validate_runway_ui_mapper_manual_learning.py
python project_brain/validate_runway_ui_mapper.py
```

---

## Backward compatibility

- v1 `categories` layout replaced by v2 `elements` + `labels`
- Legacy `--interactive-map` runs **scan only** (no automated clicking)
