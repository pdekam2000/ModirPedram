# PHASE RUNWAY-BROWSER-CONTINUITY-B — Real Output Control Relabeling

**Date:** 2026-06-03  
**Phase A report:** `PHASE_RUNWAY_BROWSER_CONTINUITY_A_MAPPING_AUDIT_REPORT.md`  
**Map file:** `project_brain/runway_ui_mapping/runway_ui_map.json`  
**Scope:** Operator relabeling prep + validation only — no provider wiring, no auto-Generate, no credit spend.

---

## Why this phase exists

Phase A found **9 of 12** continuity keys partially mapped, with **`download_mp4_button` broken** (captured as `body`) and **`generation_status` missing**. Orchestrator wiring stays blocked until output controls are re-labeled on a **real completed Gen-4.5 generation**.

---

## Safety rules (read first)

| Rule | Detail |
|------|--------|
| Workflow | Gen-4.5 **Video Generation** — `mode=tools&tool=video` |
| Do **not** use | Multi-Shot Video (`mode=apps&app=multi-shot`) |
| Mapper | Shift+Click / `--click-label` only — never auto-clicks Generate |
| Credits | Operator manually generates **one** test clip when ready; mapper does not spend credits |
| Provider | `RunwayBrowserProvider` is **not** wired to the map in this phase |

---

## Quick commands

```bash
# Print step-by-step checklist (no browser)
python tools/runway_ui_mapper.py --continuity-checklist

# Validate current map against continuity requirements
python tools/runway_ui_mapper.py --validate-continuity

# Standalone validator (same checks + unit self-test)
python project_brain/validate_runway_mapping_continuity_controls.py
```

### Start labeling session (when Chrome + Runway are open)

```bash
python tools/runway_ui_mapper.py --click-label
```

After each Shift+Click save, the mapper prints **validation warnings** if the capture looks wrong (body tag, generic selector, wrong page path, text mismatch).

---

## Operator checklist

Check items off as you label. Use **exact canonical names** in the popup when possible.

### Prerequisites (Phase A — verify still present)

- [ ] `prompt_input` — `div[aria-label="Prompt"]` on Gen-4.5 editor  
- [ ] `gen45_model_button` — Gen-4.5 tab (`-tab-gen45`)  
- [ ] `try_it_now_button` — button text **Try it now** (not "Try in Edit Studio")  
- [ ] `generate_button` — Generate submit (approval-gated; label only, do not auto-click)

### Critical relabeling (Phase B — after one real completed clip)

| Step | Label name | When | Click target | Avoid |
|------|------------|------|--------------|-------|
| 1 | `duration_menu` | Editor open, menu **closed** | Duration chip (shows e.g. `5s`) | Menu rows — those are `duration_10s` |
| 2 | `duration_10s` | After opening duration menu | Row `10 seconds` / `10s` | Multi-Shot toolbar |
| 3 | `aspect_ratio_menu` | Editor open, menu **closed** | Aspect chip (shows `16:9` or `9:16`) | Menu option rows |
| 4 | `aspect_ratio_16_9` | After opening aspect menu | Menu row `16:9` | `mode=apps` pages |
| 5 | `aspect_ratio_9_16` | After opening aspect menu | Menu row `9:16` | Label key with space typo |
| 6 | `generation_status` | While processing **or** when ready | Queue/progress/ready text near output | Entire page / `body` |
| 7 | `download_mp4_button` | Clip complete, download visible | Per-clip Download button/link | `body`, **Download all** batch |
| 8 | `use_frame_button` | Tools session output view | **Use frame** on video card | `mode=apps`, recents, multi-shot |

---

## Label normalization

When saving in the popup, prefer **canonical names** on the left:

| Old / raw label | Canonical name |
|-----------------|----------------|
| `DOWNLOAD MP4` | `download_mp4_button` |
| `DOWNLOAD ALL` | *(not equivalent — use per-clip control only)* |
| `USE FRAME` | `use_frame_button` |
| `aspect_ratio_menu 9: 16` | `aspect_ratio_9_16` |
| `aspect_ratio_menu 16:9` | `aspect_ratio_16_9` |
| `10s duration` | `duration_10s` |
| `Prompt Box` | `prompt_input` |
| `Gen-4.5` / `Ge-4.5` | `gen45_model_button` |
| `Try it now` | `try_it_now_button` |
| `Geerate` | `generate_button` |
| `VIEDO DURATION KONOPF` | `duration_menu` |

The mapper prints a **normalization suggestion** when you save under a legacy name.

---

## Validation warnings (mapper live feedback)

On each save, `--click-label` warns when:

| Code | Meaning | Fix |
|------|---------|-----|
| `FORBIDDEN_TAG` | Target is `body` or `html` | Re-click the actual button/link/menu row |
| `GENERIC_SELECTOR` | Selector is bare `span` / `div` / etc. | Prefer element with `aria-label`, stable id suffix, or `data-testid` |
| `TEXT_MISMATCH` | Visible text doesn't match control type | Confirm you clicked the right UI piece |
| `DOWNLOAD_NOT_BODY` | Download mapped to page root | Re-label per-clip Download control |
| `USE_FRAME_WRONG_PAGE` | Captured on apps/recents/multi-shot | Open tools session output (`mode=tools&tool=video`) |
| `USE_FRAME_PAGE_UNCONFIRMED` | URL missing tools+video markers | Navigate to Gen-4.5 session before labeling |
| `STATUS_NOT_BODY` | Status mapped to page root | Click status text/region only |
| `WRONG_WORKFLOW_PAGE` | Label on Multi-Shot path | Switch to Gen-4.5 tools workflow |
| `NORMALIZE_LABEL` | Legacy label name used | Re-save using canonical name from table above |

Warnings do **not** block save — fix and re-label to overwrite the bad entry.

---

## Recommended session flow

1. Open Runway in Chrome (logged in). Connect CDP on port 9222.  
2. Navigate: Dashboard → **Generate Video** → **Gen-4.5** → **Try it now**.  
3. Confirm URL contains `mode=tools&tool=video`.  
4. Run `python tools/runway_ui_mapper.py --click-label`.  
5. Label steps **1–5** (menus + options) — **no Generate required**.  
6. Manually run **one** real generation (operator clicks Generate — not the mapper).  
7. While processing: Shift+Click status region → label `generation_status`.  
8. When complete: label `download_mp4_button` on **per-clip** download.  
9. Click **Use frame** on the output card → label `use_frame_button`.  
10. Run validators (both commands above). All required labels must pass with no `body`/`html` targets.

---

## Pass criteria (`--validate-continuity`)

All must be true:

- [ ] `prompt_input`, `gen45_model_button`, `try_it_now_button`, `generate_button` exist  
- [ ] `duration_menu`, `duration_10s`, `aspect_ratio_menu`, `aspect_ratio_16_9`, `aspect_ratio_9_16` exist  
- [ ] `generation_status` exists  
- [ ] `download_mp4_button` exists and is **not** `body`/`html`  
- [ ] `use_frame_button` exists and is **not** `body`/`html`  
- [ ] Every required label has non-empty `selector_candidates.css`  
- [ ] No error-severity validation on output controls  

When this passes, Phase C (map loader + orchestrator prep stubs) can proceed — still with Generate approval-gated.

---

## Known bad entries to overwrite (Phase A)

| Label | Problem | Action |
|-------|---------|--------|
| `DOWNLOAD MP4` | Mapped to `body` | Re-label step 7 |
| `USE FRAME` | Generic `span` on `mode=apps` | Re-label step 8 on tools session |
| `Try it` | Maps to Edit Studio CTA | Ignore — use `try_it_now_button` only |
| Multi-Shot labels | Wrong workflow | Do not wire; leave deprecated |

---

## What this phase does **not** do

- Does not modify `RunwayBrowserProvider` execution logic  
- Does not wire the orchestrator to the map  
- Does not auto-click Generate or spend credits  
- Does not run browser automation in the validator scripts  

---

## Next phase preview (Phase C — after validation passes)

1. Add read-only `runway_ui_map_loader` (no provider behavior change yet)  
2. Orchestrator dry-run steps for Use Frame (approval-gated)  
3. Dual-path selectors: map first, heuristic fallback  
4. Two-clip continuity UAT with operator approval at each Generate  
