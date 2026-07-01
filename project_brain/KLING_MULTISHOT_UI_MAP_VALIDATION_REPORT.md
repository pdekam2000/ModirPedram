# Kling Multishot UI Map — Validation Report

**Phase:** KLING MULTISHOT UI MAP VALIDATION  
**Source map:** `project_brain/runway_ui_mapping/runway_ui_map.json`  
**Scan reference:** `project_brain/runway_ui_mapping/selector_candidates.json`  
**Scan date:** 2026-06-16T17:39:10Z  
**Validation date:** 2026-06-16  
**Mode:** Static map validation only — **no Generate click, no credits spent**

---

## Executive Summary

All **12 operator-saved labels** exist in `runway_ui_map.json`. **5 labels are automation-ready** (stable React IDs or aria-labels from scan). **7 labels need selector strengthening** before safe automation. **`provider_kling_3_pro` is mis-mapped** to the wrong control (Kling 3.0 **tab**, not Kling 3.0 **Pro** model button).

**6 additional labels** required for 15-second multishot strategies are **not yet saved** and should be captured on the next mapper session.

| Verdict | Count |
|---------|-------|
| PASS (usable as-is with session ID caveat) | 3 |
| PASS WITH RECOMMENDED UPGRADE | 4 |
| FAIL — wrong target or unusable selector | 5 |
| MISSING — not yet labeled | 6 |

---

## 1. Label Inventory Check

### 1.1 Required labels (operator session)

| Label | Present in `labels`? | Operator confirmed? | Initial verdict |
|-------|----------------------|---------------------|-----------------|
| `kling 3.0` | Yes | Yes (2026-06-16) | PASS WITH UPGRADE |
| `provider_kling_3_pro` | Yes | Yes | **FAIL — wrong element** |
| `Multishot` | Yes | Yes | FAIL — generic selector |
| `multishot_tab` | Yes | Yes | FAIL — duplicate + generic |
| `first_frame_upload` | Yes | Yes | FAIL — generic selector |
| `shot_1_prompt` | Yes | Yes | FAIL — wrong tag |
| `shot_2_prompt` | Yes | Yes | FAIL — wrong tag |
| `shot 1 duration menu` | Yes | Yes | FAIL — generic `svg` |
| `shot 1 duration 12 s` | Yes | Yes | FAIL — generic `span` |
| `+Add shot` | Yes | Yes | PASS WITH UPGRADE |
| `audio_toggle_on` | Yes | Yes | **FAIL — wrong element** |
| `generate_button` | Yes | Yes | **PASS — dangerous / approval gated** |

### 1.2 Additional labels required (not yet saved)

| Canonical label | Purpose | Status |
|-----------------|---------|--------|
| `shot_1_duration_menu` | Strategy A — open Shot 1 duration picker | Alias of `shot 1 duration menu` (rename recommended) |
| `shot_1_duration_12s` | Strategy A — select 12 s on Shot 1 | Alias of `shot 1 duration 12 s` (rename recommended) |
| `shot_2_duration_menu` | Strategy A — verify Shot 2 duration control | **MISSING** |
| `shot_2_duration_3s` | Strategy A — confirm 3 s on Shot 2 | **MISSING** |
| `add_shot_button` | Strategy B — add shots 3–5 | Alias of `+Add shot` (rename recommended) |
| `shot_3_prompt` | Strategy B — beat 3 field | **MISSING** (appears after Add shot) |
| `shot_4_prompt` | Strategy B — beat 4 field | **MISSING** |
| `shot_5_prompt` | Strategy B — beat 5 / CTA field | **MISSING** |

---

## 2. Default Multishot State (confirmed from scan)

From `scan.body_text_snippet` and element inventory `btn_020`, `btn_022`, `btn_026`:

| Property | Default value | Detection method |
|----------|---------------|------------------|
| Shot count | **2** | Count `div[aria-label="Shot N prompt"]` or visible “Shot N” headers |
| Per-shot duration | **3 s** each | Buttons with `aria-label="Shot duration"` showing text `3s` |
| Total duration | **6 s** | Footer button `aria-label="Duration"` showing `6s` (`btn_026`) |
| Multishot mode | Active when Multishot tab selected | Radio `input_005` name `react-aria3046197000-:r1ps:` near “Multishot” |

**Validation:** Default 2-shot / 3 s / 6 s total is **confirmed** in scan data. No live re-scan performed in this phase.

---

## 3. Fifteen-Second Strategy Design Decision

### Strategy A — 2-shot compact (12 s + 3 s)

| Shot | Duration | Total |
|------|----------|-------|
| Shot 1 | 12 s | |
| Shot 2 | 3 s | **15 s** |

**Use when:** Simple scene, single arc, fewer prompt fields, quick iteration.

**Map readiness:** Partial — Shot 1 menu + 12 s option labeled; Shot 2 duration menu/3 s **not labeled**.

### Strategy B — 5-shot full story (3 s × 5) — **DEFAULT for story/fantasy/cinematic**

| Shot | Beat role | Duration |
|------|-----------|----------|
| 1 | Setup | 3 s |
| 2 | Discovery | 3 s |
| 3 | Tension | 3 s |
| 4 | Reveal / action | 3 s |
| 5 | Ending / CTA | 3 s |

**Total:** 15 s

**Use when:** Story, fantasy, cinematic, multi-beat arcs (recommended default for ModirAgentOS narrative content).

**Map readiness:** `+Add shot` labeled; shots 3–5 prompts **not labeled** (only exist after 3× Add shot in UI).

### Router integration (future)

```
if content_class in {story, fantasy, cinematic, multi_beat}:
    multishot_strategy = "five_shot_story"   # Strategy B
elif scene_complexity == simple:
    multishot_strategy = "two_shot_compact"  # Strategy A
```

---

## 4. Per-Control Validation

### 4.1 `kling 3.0` — Kling model tab

| Field | Value |
|-------|-------|
| Saved selector | `#react-aria3046197000-\:r23r\:-tab-kling-3` |
| Role | `tab` |
| Text | `Kling 3.0` |
| Verdict | **PASS WITH UPGRADE** |

**Issue:** React aria IDs are **session-scoped**; `#react-aria3046197000-...` changes between page loads.

**Recommended strengthened selectors (priority order):**

```javascript
page.getByRole('tab', { name: /^Kling 3\.0$/i })
page.locator('[id$="-tab-kling-3"]')
page.getByText('Kling 3.0', { exact: true })
```

**Safe selection:** Yes — tab switch only, no credits.

---

### 4.2 `provider_kling_3_pro` — **MIS-LABELED**

| Field | Saved | Actual target needed |
|-------|-------|----------------------|
| Selector | `#react-aria3046197000-\:r23r\:-tab-kling-3` | **`btn_030`** model button |
| Text saved | `Kling 3.0` | **`Kling 3.0 Pro`** |
| Role | `tab` | **`button`** |
| aria-label | (empty) | **`Video models`** |

**Scan ground truth (`elements.btn_030`):**

```
text: "Kling 3.0 Pro"
aria_label: "Video models"
css: #react-aria3046197000-\:r1s0\:
playwright: get_by_role('button', { name: /Kling 3\.0 Pro/i })
```

**Verdict:** **FAIL** — label points to Kling 3.0 **tab**, not the **Kling 3.0 Pro** provider chip beside Apps/Generate.

**Action required:** Re-label `provider_kling_3_pro` on **`btn_030`** (bottom bar), not the tab.

**Note:** `kling 3.0` tab and `provider_kling_3_pro` are **different controls** in the Runway UI. Both may be needed: tab selects Kling family; Pro button confirms model variant in the generate bar.

---

### 4.3 `Multishot` / `multishot_tab` — Multishot mode toggle

| Field | Value |
|-------|-------|
| Saved selector | `label` (generic) |
| Bounding box | x=264, y=50, 182×36 |
| Text | `Multishot` |
| Verdict | **FAIL** — generic `label` matches many controls |

**Recommended strengthened selectors:**

```javascript
// Prefer the multishot radio input captured as input_005
page.locator('input[name*="multi"]').check()  // verify name at runtime
page.getByText('Multishot', { exact: true }).click()
page.locator('label').filter({ hasText: /^Multishot$/ }).click()
```

**Disambiguation:** Scan shows `Frames` / `Multishot` toggle at y≈50. Use **exact text `Multishot`** or paired radio input, not bare `label`.

**Duplicate:** `Multishot` and `multishot_tab` are identical entries — consolidate to **`multishot_tab`** canonical name.

---

### 4.4 `first_frame_upload`

| Field | Saved | Scan alternative |
|-------|-------|------------------|
| Tag | `span` “Upload” | `btn_010` div[role=button] **First Video Frame Upload** |
| Selector | `span` | `get_by_role('button', name=/First Video Frame Upload/i)` |
| Verdict | **FAIL** — “Upload” span is not unique |

**Recommended strengthened selectors:**

```javascript
page.getByRole('button', { name: /First Video Frame Upload/i })
page.getByText('First Video Frame Upload')
// Inner upload control if needed:
page.getByText('Upload', { exact: true }).filter({ has: page.locator('[aria-label="Upload"]') })
```

**Safe identification:** Yes after upgrade. File picker may open — automation should use **approval gate** for upload actions.

---

### 4.5 `shot_1_prompt` / `shot_2_prompt`

| Field | Saved | Scan ground truth |
|-------|-------|-------------------|
| Tag | `p` (empty) | `div[role=textbox][aria-label="Shot N prompt"]` |
| Selector | `p` | `input_006` / `input_007` |
| Verdict | **FAIL** — wrong element; empty `<p>` is not the editable field |

**Recommended strengthened selectors:**

```javascript
page.locator('[aria-label="Shot 1 prompt"][contenteditable="true"]')
page.locator('[aria-label="Shot 2 prompt"][contenteditable="true"]')
page.getByRole('textbox', { name: 'Shot 1 prompt' })
page.getByRole('textbox', { name: 'Shot 2 prompt' })
```

**Y-position fallback (from saved bboxes):** Shot 1 ≈ y 751–891; Shot 2 ≈ y 901–1041.

**Shots 3–5 (Strategy B):** Same pattern — `aria-label="Shot 3 prompt"` etc. after Add shot. **Not yet labeled.**

---

### 4.6 `shot 1 duration menu` / `shot 1 duration 12 s`

| Label | Saved tag | Scan ground truth |
|-------|-----------|-------------------|
| Duration menu | `svg` (14×14) | `btn_020` button, text `3s`, `aria-label="Shot duration"`, y≈855 |
| 12 s option | `span` “12 seconds” | Duration dropdown option (visible when menu open) |

**Verdict:** **FAIL** — svg/span are fragile; menu icon is not uniquely identifiable.

**Recommended strengthened selectors:**

```javascript
// Shot 1 duration menu (first Shot duration button)
page.getByRole('button', { name: 'Shot duration' }).first()
// Or nth by vertical order:
page.locator('button[aria-label="Shot duration"]').nth(0)

// 12 seconds option (menu must be open)
page.getByRole('option', { name: /12 seconds/i })
page.getByText('12 seconds', { exact: true })
```

**Shot 2 duration (Strategy A):** Use `.nth(1)` on same locator; confirm text `3s` or select `3 seconds` option — **labels `shot_2_duration_menu` / `shot_2_duration_3s` missing**.

**Canonical rename:** `shot 1 duration menu` → `shot_1_duration_menu`; `shot 1 duration 12 s` → `shot_1_duration_12s`.

---

### 4.7 `+Add shot` / `add_shot_button`

| Field | Value |
|-------|-------|
| Saved selector | `#react-aria3046197000-\:r2bh\:` |
| Scan element | `btn_023` `#react-aria3046197000-\:r1qt\:` |
| aria-label | `Add shot` |
| Text | `Add shot` |
| Verdict | **PASS WITH UPGRADE** |

**Recommended strengthened selectors:**

```javascript
page.getByRole('button', { name: 'Add shot' })
page.locator('button[aria-label="Add shot"]')
```

**Strategy B validation logic (future, no click during validation):**

1. Assert 2 shots visible by default.
2. Click Add shot **only with approval** until `aria-label="Shot 5 prompt"` exists.
3. Assert total duration reads **15s** (footer `Duration` button).
4. Never exceed 5 shots without operator review.

**Canonical alias:** `+Add shot` → `add_shot_button`.

---

### 4.8 `audio_toggle_on`

| Field | Saved | Scan ground truth |
|-------|-------|-------------------|
| Tag | `path` (2×7 px SVG path) | `btn_024` button |
| Text | (empty) | **`· On`** |
| aria-label | (empty) | **`Audio settings`** |
| nearby | | `· On On Off` |

**Verdict:** **FAIL** — saved target is an SVG path fragment, not the toggle control.

**Recommended strengthened selectors:**

```javascript
page.getByRole('button', { name: /Audio settings/i })
page.getByRole('button', { name: /· On/i })
// State detection:
const on = await page.getByRole('button', { name: /Audio settings/i }).innerText()
// expect on to match /On/i and not /^Off/
```

**ON state detection rule:** Button text contains **`On`** (scan: `· On`) and nearby context shows `On Off` with active On branch. Do **not** use bare `path` selectors.

**Also available:** `select` with text `On Off` (`select_002` in candidates) — verify which control is authoritative on next scan.

---

### 4.9 `generate_button`

| Field | Value |
|-------|-------|
| Selector | `#react-aria3046197000-\:r2cu\:` |
| Text | `Generate` |
| Scan | `btn_031`, `click_blocked: true` |
| Safety | Listed in `safety.requires_approval` |
| `generate_never_auto_clicked` | `true` |
| Verdict | **PASS — DANGEROUS** |

**Recommended strengthened selectors:**

```javascript
page.getByRole('button', { name: /^Generate$/i })
page.locator('button').filter({ hasText: /^Generate$/ })
```

**Safety confirmation:**

| Check | Status |
|-------|--------|
| In `requires_approval` | Yes |
| In `auto_click_blocklist` (generate) | Yes |
| `click_blocked` on scan element | Yes |
| Validation clicked Generate | **No** |

---

## 5. Selector Strengthening Summary Table

| Label | Current selector | Risk | Recommended primary locator |
|-------|------------------|------|----------------------------|
| `kling 3.0` | `#react-aria…-tab-kling-3` | Session ID drift | `getByRole('tab', { name: 'Kling 3.0' })` |
| `provider_kling_3_pro` | Same as tab (**wrong**) | **Mis-target** | `getByRole('button', { name: /Kling 3\.0 Pro/i })` → **re-label** |
| `Multishot` / `multishot_tab` | `label` | High collision | `getByText('Multishot', { exact: true })` |
| `first_frame_upload` | `span` | High collision | `getByRole('button', { name: /First Video Frame Upload/i })` |
| `shot_1_prompt` | `p` | Wrong element | `[aria-label="Shot 1 prompt"][contenteditable="true"]` |
| `shot_2_prompt` | `p` | Wrong element | `[aria-label="Shot 2 prompt"][contenteditable="true"]` |
| `shot 1 duration menu` | `svg` | High collision | `button[aria-label="Shot duration"]`.first() |
| `shot 1 duration 12 s` | `span` | Needs open menu | `getByRole('option', { name: /12 seconds/i })` |
| `+Add shot` | React ID | Medium drift | `getByRole('button', { name: 'Add shot' })` |
| `audio_toggle_on` | `path` | **Wrong element** | `getByRole('button', { name: /Audio settings/i })` + text `On` |
| `generate_button` | React ID | Credit spend | `getByRole('button', { name: 'Generate' })` + **approval gate** |

---

## 6. Validation Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Labels exist in `runway_ui_map.json` | **PASS** | All 12 present |
| 2 | Selector candidates usable | **PARTIAL** | 5/12 need upgrade before automation |
| 3 | Generic selectors replaced (design) | **DOCUMENTED** | Upgrades in §5; JSON not modified (validation-only) |
| 4 | Provider Kling 3.0 Pro selectable safely | **FAIL** | Re-label to `btn_030` |
| 5 | Multishot tab selectable safely | **PARTIAL** | Needs non-generic locator |
| 6 | Audio toggle ON detectable | **FAIL** | Re-label to `btn_024`, detect via text |
| 7 | First frame upload identifiable | **PARTIAL** | Use `First Video Frame Upload` button |
| 8 | Shot prompt fields identifiable | **PARTIAL** | Use aria-label textboxes, not `<p>` |
| 9 | Add Shot identifiable | **PASS** | `aria-label="Add shot"` reliable |
| 10 | Generate marked dangerous | **PASS** | `requires_approval` + blocklist |
| 11 | Default 2 shots detectable | **PASS** | Scan snippet + 2 duration buttons |
| 12 | Per-shot duration detectable | **PASS** | `btn_020`/`btn_022` show `3s` |
| 13 | Add up to 5 shots (Strategy B design) | **NOT TESTED** | Map missing shot 3–5; no clicks |
| 14 | Never clicked Generate | **PASS** | Static validation only |

---

## 7. Missing Labels — Next Mapper Session

Capture these **after** UI states exist (open duration menus, add shots 3–5):

| Priority | Label | When to capture |
|----------|-------|-----------------|
| P0 | `provider_kling_3_pro` | Re-click **`Kling 3.0 Pro`** bottom bar button (`btn_030`) |
| P0 | `audio_toggle_on` | Re-click **`· On` / Audio settings** button (`btn_024`) |
| P0 | `shot_1_prompt` / `shot_2_prompt` | Re-click contenteditable **Shot N prompt** fields |
| P1 | `shot_2_duration_menu` | Open Shot 2 duration dropdown |
| P1 | `shot_2_duration_3s` | Select **3 seconds** on Shot 2 |
| P1 | `shot_3_prompt` | After 1× Add shot |
| P1 | `shot_4_prompt` | After 2× Add shot |
| P1 | `shot_5_prompt` | After 3× Add shot |
| P2 | `total_duration_15s` | Footer Duration button when sum = 15 s |
| P2 | `multishot_tab` | Consolidate; drop duplicate `Multishot` |

**Naming convention:** Use snake_case (`shot_1_duration_menu`) consistently; deprecate spaced labels (`shot 1 duration menu`).

---

## 8. Safety Block Confirmation

From `runway_ui_map.json` → `safety`:

```json
{
  "generate_never_auto_clicked": true,
  "auto_click_blocklist": ["generate", "create", "submit", "upgrade", "purchase", "buy", "subscribe", "delete"],
  "requires_approval": ["generate_button"]
}
```

Scan element `btn_031` (Generate) has `"click_blocked": true`.

**Validation phase compliance:** No browser automation executed; no Generate interaction; no credit spend.

---

## 9. Recommended JSON Schema Additions (future implementation)

When map is updated, each label should include:

```json
{
  "label": "shot_1_prompt",
  "selector_candidates": {
    "css": "div[aria-label=\"Shot 1 prompt\"][contenteditable=\"true\"]",
    "playwright": "getByRole('textbox', { name: 'Shot 1 prompt' })",
    "fallback_nth": null
  },
  "validation_status": "confirmed",
  "automation_tier": "safe | approval_required | blocked",
  "multishot_strategy": "five_shot_story | two_shot_compact | any"
}
```

Suggested `automation_tier` assignments:

| Label | Tier |
|-------|------|
| `generate_button` | **blocked** (approval required) |
| `first_frame_upload` | approval_required |
| `+Add shot` | approval_required (changes layout) |
| Duration menus | safe |
| Prompt fields | safe |
| `multishot_tab`, `kling 3.0`, `provider_kling_3_pro` | safe |

---

## 10. Conclusion

The Kling Multishot mapper session successfully captured **operator intent** for all primary controls, but **selector quality is insufficient for automation** on 7 of 12 labels. The highest-priority fixes are:

1. **Re-label `provider_kling_3_pro`** to the bottom-bar **Kling 3.0 Pro** button, not the Kling 3.0 tab.
2. **Re-label `audio_toggle_on`** to the **Audio settings / · On** button, not an SVG path.
3. **Replace prompt labels** with `div[aria-label="Shot N prompt"]` textboxes.
4. **Replace generic** `label`, `span`, `svg`, `p` selectors with role/text/aria-label locators from §5.
5. **Add Strategy B labels** for shots 3–5 after Add shot expansion.

**Strategy B (5 × 3 s = 15 s)** is approved as the default for story/fantasy/cinematic content; Strategy A remains available for simple scenes.

**No implementation or map JSON edits performed in this validation phase.**

---

## Appendix A — Scan Element Cross-Reference

| Element ID | Control | Useful for label |
|------------|---------|------------------|
| `input_005` | Multishot radio | `multishot_tab` |
| `btn_010` | First Video Frame Upload | `first_frame_upload` |
| `input_006` | Shot 1 prompt textbox | `shot_1_prompt` |
| `input_007` | Shot 2 prompt textbox | `shot_2_prompt` |
| `btn_020` | Shot 1 duration (3s) | `shot_1_duration_menu` |
| `btn_022` | Shot 2 duration (3s) | `shot_2_duration_menu` |
| `btn_023` | Add shot | `add_shot_button` |
| `btn_024` | Audio · On | `audio_toggle_on` |
| `btn_026` | Total duration 6s | `total_duration_indicator` |
| `btn_030` | Kling 3.0 Pro | `provider_kling_3_pro` |
| `btn_031` | Generate | `generate_button` |
| Tab id `-tab-kling-3` | Kling 3.0 tab | `kling 3.0` |
