# PHASE RUNWAY-BROWSER-CONTINUITY-A — Mapping Audit + Orchestrator Prep

**Date:** 2026-06-03  
**Source:** `project_brain/runway_ui_mapping/runway_ui_map.json`  
**Mapper version:** `runway_ui_mapper_v2`  
**Updated at:** 2026-06-03T17:23:54Z  
**Workflow target:** Gen-4.5 Video Generation (not Multi-Shot Video)  
**Scope:** Audit and preparation only — no automation executed, no credits spent, Generate not clicked.

---

## Executive summary

Manual labeling progressed significantly since the prior scan-only audit (`RUNWAY_UI_MAP_AUDIT_REPORT.md`). The map now holds **41 operator-confirmed labels** across dashboard, Gen-4.5 editor, Multi-Shot (deprecated path), and post-generation views.

**Coverage of the 12 required internal keys:** **9 partially mapped**, **1 broken**, **2 missing**.

| Verdict | Detail |
|---|---|
| Mapping quality | Mixed — strong on Gen-4.5 tab / Try it now / Prompt / Generate; weak on span-only selectors and session-scoped React IDs |
| Continuity readiness | **Not ready** — `use_frame_button` exists but selector is fragile; orchestrator has no Use Frame step |
| Orchestrator wiring | **Not safe to start full continuity runs** — provider still uses hardcoded Playwright, not `runway_ui_map.json`; critical gaps on download MP4 and generation status |
| Safe prep work | Label normalization schema, deprecating Multi-Shot labels, and a map-loader stub can proceed without spending credits |

---

## Correct workflow (reference)

Gen-4.5 single-clip loop (repeat for clip 2+ via Use Frame):

1. Open Video Generation  
2. Select Gen-4.5  
3. Click Try It Now  
4. Enter prompt (≤ 5000 chars)  
5. Set aspect ratio — **9:16** (Shorts/Reels/TikTok) or **16:9** (horizontal/longform)  
6. Set duration **10s**  
7. Click Generate *(approval-gated)*  
8. Wait ~15 minutes  
9. Download MP4  
10. Click Use Frame for next clip  

**Do not use Multi-Shot Video** as the primary workflow (credit-based).

---

## Labels found (41 operator-confirmed)

Grouped by relevance to the Gen-4.5 continuity workflow.

### Core workflow (Gen-4.5 `mode=tools&tool=video`)

| Raw label | Visible text | Selector (stored) | Page context |
|---|---|---|---|
| `Generate Video` | Generate Video | `div` | dashboard |
| `GENERATE VIDEO` | Generate Video | `div` | dashboard |
| `Geerate Video` | Generate Video | `div` | dashboard |
| `Gen-4.5` | Gen-4.5 | `#react-aria7665257423-\:rvs\:-tab-gen45` | generate landing |
| `Ge-4.5` | Gen-4.5 | `#react-aria9301350402-\:reh\:-tab-gen45` | generate session |
| `Try it now` | Try it now | `#react-aria9301350402-\:rep\:` | generate session |
| `Try it` | **Try in Edit Studio** | `#react-aria7665257423-\:r104\:` | generate landing — **wrong CTA** |
| `Prompt Box` | *(empty)* | `div[aria-label="Prompt"]` | generate session |
| `Geerate` | Generate | `#react-aria9301350402-\:rhq\:` | generate session |
| `16:9` | 16:9 | `span` | generate session (toolbar) |
| `16.9 MODE` | 16:9 | `span` | generate session |
| `5s` | 5s | `span` | generate session (current duration chip) |
| `VIEDO DURATION KONOPF` | 5s | `span` | generate session (duration chip, not menu) |
| `10s duration` | 10 seconds | `span` | duration menu option |
| `8s duration` | 8 seconds | `span` | duration menu option |
| `aspect_ratio_menu 16:9` | 16:9 | `span` | aspect menu option |
| `aspect_ratio_menu 9: 16` | 9:16 | `span` | aspect menu option |

### Post-generation / continuity

| Raw label | Visible text | Selector (stored) | Page context |
|---|---|---|---|
| `USE FRAME` | Use frame | `span` | `mode=apps` session recents |
| `DOWNLOAD ALL` | *(empty)* | `#react-aria9301350402-\:r26o\:` | session — aria `Download all` |
| `DOWNLOAD MP4` | *(entire page body)* | **`body`** | recents — **mis-captured** |

### Multi-Shot / deprecated path (do not wire)

| Raw label | Notes |
|---|---|
| `Multi-Shot Video` | Tab on model row — credit workflow |
| `aUTO`, `CUSTOM` | Multi-Shot sub-mode |
| `fIRST fRAME OF vIDEO`, `SELECT FIRST SHOT IMAGE IN CUSTOM MODE`, `ADD SHOT` | Multi-Shot shot builder |
| `10S`, `16.9`, `720P` | Multi-Shot toolbar (`mode=apps&app=multi-shot`) |
| `CREDIT MODE`, `UNLIMIT MODE NACH KLICK CREDIT MODE`, `CREDIT NACH CLICK CREDIT MODE` | Credit billing UI |

### Navigation / noise (low priority)

| Raw label | Notes |
|---|---|
| `HOME`, `IMAGE`, `AUDIO` | Top tool switcher |
| `Aleph 2,0`, `Seedance 2,0`, `Runway Characters`, `Kling 3,0` | Other model tabs |
| `Upload afairst video Frame` | Upload span — not continuity Use Frame |
| `APPS VIEDO ART MODUS ZU WÄHLEN VIEDO ART` | Apps trigger `#related-apps-trigger` |

---

## Required internal keys — coverage matrix

| Internal key | Status | Best raw label(s) | Notes |
|---|---|---|---|
| `video_generation_button` | **Found** | `Generate Video`, `btn_016` / `btn_032` in elements | Prefer sidebar link `href=...tool=video` over dashboard div |
| `gen45_model_button` | **Found** | `Gen-4.5`, `Ge-4.5` | Stable suffix `-tab-gen45`; React prefix is session-volatile |
| `try_it_now_button` | **Found** | `Try it now` | Do **not** use `Try it` (maps to Edit Studio) |
| `prompt_input` | **Found** | `Prompt Box` | `div[aria-label="Prompt"]` is good; mapper canonical name is `prompt_box` |
| `generate_button` | **Found** | `Geerate` | React ID `#react-aria9301350402-\:rhq\:`; safety blocklist active |
| `duration_10s` | **Found** | `10s duration` | Menu option text `10 seconds`; toolbar chip is `5s` until opened |
| `duration_8s` | **Found** | `8s duration` | Menu option only |
| `aspect_ratio_16_9` | **Found** | `aspect_ratio_menu 16:9`, `16:9` | Menu option + toolbar chip |
| `aspect_ratio_9_16` | **Found** | `aspect_ratio_menu 9: 16` | Label key has stray space (`9: 16`) |
| `use_frame_button` | **Partial** | `USE FRAME` | Mapped on recents/apps view; generic `span` selector |
| `download_mp4_button` | **Broken** | `DOWNLOAD MP4` | Captured `body` — unusable; `DOWNLOAD ALL` is batch, not per-clip MP4 |
| `generation_status` | **Missing** | — | No label for queue/progress/complete states |

**Score:** 9 mapped (7 strong enough to guide manual re-label), 1 broken, 2 missing.

---

## Labels missing (critical)

These must be captured in a **follow-up labeling session** on the Gen-4.5 tools path before continuity automation:

| Missing key | Why it matters | Suggested capture moment |
|---|---|---|
| `generation_status` | Orchestrator waits ~15 min on queue/generating/complete signals | After Generate click — map progress text, spinner region, or “In queue” |
| `download_mp4_button` | Continuity loop requires per-clip MP4 export | Re-label on completed generation card — **not** page body, **not** Download all |
| `aspect_ratio_menu` *(trigger)* | Only menu **options** are labeled; opener chip/button is not | Before opening 9:16 / 16:9 dropdown |
| `duration_menu` *(trigger)* | `VIEDO DURATION KONOPF` points at `5s` chip, not the menu control | Click duration chip → then options already mapped |
| `generated_video_card` | Needed to scope Use Frame + download to latest output | When video thumbnail appears in session feed |

Optional but recommended:

| Key | Purpose |
|---|---|
| `aspect_ratio_9_16` toolbar confirmation | Verify 9:16 selected after menu click (Shorts default) |
| `first_video_frame_upload` | Clip 1 cold start when no prior Use Frame |

---

## Recommended label normalization

Apply a **`normalized_keys`** layer (or rename labels in map v3) without deleting operator history. Suggested mapping:

```json
{
  "normalized_keys": {
    "video_generation_button": {
      "canonical_label": "video_generation_button",
      "source_labels": ["Generate Video", "GENERATE VIDEO"],
      "prefer_element": "btn_032",
      "fallback_selector": "a[href*='tool=video']"
    },
    "gen45_model_button": {
      "canonical_label": "gen45_model_button",
      "source_labels": ["Gen-4.5", "Ge-4.5"],
      "prefer_selector_pattern": "[id$='-tab-gen45']",
      "mapper_alias": "gen45_option"
    },
    "try_it_now_button": {
      "canonical_label": "try_it_now_button",
      "source_labels": ["Try it now"],
      "exclude_labels": ["Try it"]
    },
    "prompt_input": {
      "canonical_label": "prompt_input",
      "source_labels": ["Prompt Box"],
      "mapper_alias": "prompt_box",
      "selector": "div[aria-label=\"Prompt\"]"
    },
    "generate_button": {
      "canonical_label": "generate_button",
      "source_labels": ["Geerate"],
      "requires_approval": true
    },
    "duration_10s": {
      "canonical_label": "duration_10s",
      "source_labels": ["10s duration", "10S"],
      "menu_option_text": "10 seconds",
      "toolbar_text": "10s"
    },
    "duration_8s": {
      "canonical_label": "duration_8s",
      "source_labels": ["8s duration"],
      "menu_option_text": "8 seconds"
    },
    "aspect_ratio_16_9": {
      "canonical_label": "aspect_ratio_16_9",
      "source_labels": ["aspect_ratio_menu 16:9", "16:9", "16.9 MODE"]
    },
    "aspect_ratio_9_16": {
      "canonical_label": "aspect_ratio_9_16",
      "source_labels": ["aspect_ratio_menu 9: 16"],
      "rename_from": "aspect_ratio_menu 9: 16"
    },
    "use_frame_button": {
      "canonical_label": "use_frame_button",
      "source_labels": ["USE FRAME"],
      "visible_text": "Use frame",
      "page_hint": "post-generation session feed"
    },
    "download_mp4_button": {
      "canonical_label": "download_mp4_button",
      "source_labels": [],
      "status": "needs_relabel",
      "reject_labels": ["DOWNLOAD MP4", "DOWNLOAD ALL"]
    },
    "generation_status": {
      "canonical_label": "generation_status",
      "source_labels": [],
      "status": "needs_capture",
      "mapper_aliases": ["queue_status_text", "progress_status_text"]
    }
  },
  "deprecated_labels": [
    "Multi-Shot Video", "aUTO", "CUSTOM", "ADD SHOT",
    "fIRST fRAME OF vIDEO", "SELECT FIRST SHOT IMAGE IN CUSTOM MODE",
    "CREDIT MODE", "UNLIMIT MODE NACH KLICK CREDIT MODE",
    "CREDIT NACH CLICK CREDIT MODE", "720P", "Try it"
  ]
}
```

**Naming alignment with existing code:**

| Phase A key | Existing mapper / provider name |
|---|---|
| `prompt_input` | `prompt_box` (`VALID_SEMANTIC_LABELS`) |
| `gen45_model_button` | `gen45_option` |
| `download_mp4_button` | `download_button` |
| `generation_status` | `queue_status_text` / `progress_status_text` |

---

## Selector quality assessment

### Strong (usable with fallbacks)

| Control | Quality | Reason |
|---|---|---|
| Gen-4.5 tab | **High** | `[id$='-tab-gen45']` suffix stable across sessions |
| Try it now | **High** | Dedicated button ID; text match `Try it now` reliable |
| Prompt box | **High** | `div[aria-label="Prompt"]` — semantic, narrow |
| Generate | **Medium-high** | Button text `Generate` + React ID; blocked from mapper auto-click ✓ |
| Download all | **Medium** | `#react-aria…` + `aria-label="Download all"` — wrong semantic (batch) |

### Weak (high flake risk)

| Control | Quality | Reason |
|---|---|---|
| Duration / aspect options | **Low** | Bare `span` — many spans on page; no parent menu scope |
| Duration chip (`5s`) | **Low** | Generic `span`; confusable with menu options |
| Use Frame | **Low** | Generic `span`; captured under `mode=apps` not tools session |
| Dashboard Generate Video | **Low** | Bare `div` — duplicates, overlapping elements |
| DOWNLOAD MP4 | **Broken** | Entire `body` element — label session error |

### Structural map issues

1. **`element_id` reuse** — Dozens of labels point at `el_001` or `btn_001`; metadata in each label entry is authoritative, not `elements[element_id]`.
2. **Session-scoped React IDs** — e.g. `#react-aria9301350402-\:rhq\:` change per page load; store **pattern + text + aria** fallbacks.
3. **Page context drift** — Same control labeled on dashboard vs `mode=tools` vs `mode=apps&app=multi-shot`; continuity must filter by URL `mode=tools&tool=video`.
4. **No `actions` recorded** — Zero observe-mode proofs that clicks open menus or change UI state.
5. **Safety block intact** — `safety.generate_never_auto_clicked: true`, `requires_approval: ["generate_button"]` ✓

---

## Orchestrator wiring safety assessment

### Current runtime (does not consume map yet)

| Component | Behavior |
|---|---|
| `RunwayBrowserProvider` | Hardcoded Playwright locators (`get_by_text`, `click_text_in_region`) |
| `RunwayBrowserOrchestrator` | `prepare_gen45_page` → per-clip prompt → ratio **16:9 only** → duration **10s** → Generate → URL wait → HTTP download |
| `runway_ui_map.json` | Learning artifact only — **not loaded** by provider/orchestrator |

### Gaps blocking continuity automation

| Gap | Risk |
|---|---|
| No `use_frame` step between clips | Clip 2+ cannot chain from last frame |
| No 9:16 ratio path in provider | Shorts/Reels workflow unsupported (hardcoded 16:9) |
| No map-driven selectors | Manual labels do not affect runtime yet |
| Broken / missing download + status labels | Download and wait loops remain brittle |
| Multi-Shot labels in map | Risk of wiring wrong workflow if map loader is naive |

### Verdict: **Not safe to start full continuity orchestration**

Safe to start **Phase B prep only**:

- Normalization schema + deprecated label flags  
- Map loader utility (read-only resolution of normalized keys)  
- Orchestrator **stub** steps for Use Frame with `requires_approval` / dry-run  
- Provider dual-path: map selector first, existing heuristics fallback  

**Do not** enable end-to-end multi-clip Generate runs until `download_mp4_button`, `generation_status`, and `use_frame_button` are re-labeled on the **Gen-4.5 tools** path with non-generic selectors.

---

## Next implementation plan

### Phase A-2 — Label cleanup (manual, no Generate)

1. Re-run mapper on Gen-4.5 session (`mode=tools&tool=video` only).  
2. Re-label `DOWNLOAD MP4` on the **per-clip download control** after a completed generation (shift+click).  
3. Capture `generation_status` — queue / generating / complete text or status region.  
4. Label **aspect ratio menu opener** and **duration menu opener** (parent chips).  
5. Re-label `USE FRAME` from tools-session output view with scoped selector (button/link near video card).  
6. Mark Multi-Shot labels `deprecated: true` in map metadata.  
7. Fix label key `aspect_ratio_menu 9: 16` → `aspect_ratio_menu 9:16`.

### Phase B — Map integration (code, still no credit spend)

1. Add `providers/runway_ui_map_loader.py` — resolve normalized keys with URL context filter.  
2. Extend `VALID_SEMANTIC_LABELS` in `tools/runway_ui_mapper.py`:  
   `use_frame_button`, `duration_8s`, `aspect_ratio_9_16`, `video_generation_button`, `gen45_model_button`, `prompt_input`, `download_mp4_button`, `generation_status`.  
3. Wire provider prep steps to consult map **before** heuristics.  
4. Add `set_ratio_9_16()` parallel to existing `set_ratio_16_9()`.  
5. Unit tests: normalization table, loader rejects `body` / generic `span` without disambiguators.

### Phase C — Continuity orchestrator (approval-gated)

1. After clip N download: `click_use_frame()` → verify first-frame / prompt editor state.  
2. Clip N+1: prompt → ratio (config: 9:16 default) → 10s → **approval gate** → Generate.  
3. Bounded wait using `generation_status` labels + existing video URL detection.  
4. Integration test with mock map + dry-run flag (no browser Generate).

### Phase D — Validated UAT

1. Single-clip dry run (prep only, stop before Generate).  
2. Two-clip continuity UAT with operator approval at each Generate.  
3. Update `RUNWAY_UI_MAP_AUDIT_REPORT.md` or supersede with continuity sign-off doc.

---

## Safety confirmation

| Check | Status |
|---|---|
| Runway automation executed in this phase | **No** |
| Credits spent | **No** |
| Generate clicked automatically | **No** — `safety.generate_never_auto_clicked: true` |
| Multi-Shot workflow wired | **No** — explicitly excluded |

---

## Appendix — elements inventory

- **Scanned elements:** 46 (`btn_001`–`btn_046`, `input_001`, `el_001`)  
- **Operator labels:** 41  
- **Observe actions:** 0  
- **Primary page URLs seen:** dashboard, `mode=tools&tool=video`, `mode=apps&app=multi-shot`, session recents  

**Latest continuity-relevant labels (2026-06-03):** `USE FRAME`, `10s duration`, `8s duration`, `aspect_ratio_menu 16:9`, `aspect_ratio_menu 9: 16`.
