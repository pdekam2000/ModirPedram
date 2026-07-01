# Kling Download Recovery Fix — Report

**Phase:** `KLING-DOWNLOAD-RECOVERY-FIX`  
**Status:** Implemented  
**Date:** 2026-06-17  

---

## 1. Problem

Run `kling_ms_20260617T020932_34fa50d2_c1` showed:

- Generate clicked: true
- Credits spent: true
- `generation_wait`: passed
- `video_element_ready`
- `download`: failed — **Could not download MP4 output**

Generation succeeded in Runway UI, but MP4 was not saved locally. A sibling `_c1` folder was created instead of canonical parent/clip structure.

---

## 2. Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/kling_multishot_live_engine.py` | Multi-strategy download (UI, blob, HTTP, menu); recovery mode; download-failed status |
| `content_brain/execution/kling_product_run.py` | Parent/clips folder layout; recovery API; status semantics |
| `tools/kling_multishot_live_runner.py` | `--recover-latest-output --run-id` CLI |
| `ui/api/product_studio_service.py` | Results merge for recovery/output fields |
| `ui/api/schemas/product_studio.py` | DTO fields for recovery state |
| `ui/web/src/api/productClient.ts` | Results types |
| `ui/web/src/pages/ResultsPage.tsx` | Recovery/output status UI |

## Files Created

| File | Purpose |
|------|---------|
| `project_brain/validate_kling_download_recovery_fix.py` | Validation suite |
| `project_brain/KLING_DOWNLOAD_RECOVERY_FIX_REPORT.md` | This report |

---

## 3. Download Detection Fixes

Enhanced `_download_output()` strategies:

1. **UI download button** (including overflow/menu triggers)
2. **Blob URL fetch** via in-page `fetch()` + base64 transfer
3. **HTTP video `src` fetch** with credentials
4. **Legacy filename fallback** then normalize to `video.mp4`

Generation wait now distinguishes:

- `download_button_visible`
- `video_element_ready`
- `video_source_ready`
- `download_link_visible`

When generation completes but download fails:

- `status`: `download_failed`
- `generation_completed`: true
- `download_status`: `failed`
- `ok`: false (not treated as final success)

---

## 4. Manual Recovery

### CLI

```bash
python tools/kling_multishot_live_runner.py \
  --recover-latest-output \
  --run-id kling_ms_20260617T020932_34fa50d2 \
  --clip-index 1
```

Also accepts legacy sibling id (`..._c1`) — resolves to parent run.

### API

`recover_kling_product_run(project_root, run_id, clip_index=1, cdp_url=...)`

Guarantees:

- Does **not** click Generate
- Does **not** spend credits
- Finds ready output in open Runway CDP tab
- Saves to `{parent}/clips/c{N}/video.mp4`
- Updates `generation_report.json`, `download_report.json`, `metadata.json`

---

## 5. Folder Consolidation

**Canonical layout:**

```text
outputs/kling_multishot_live/kling_ms_20260617T020932_34fa50d2/
  preflight.json
  metadata.json
  generation_report.json
  download_report.json
  video.mp4                     # final consolidated output
  clips/
    c1/
      video.mp4
      live_run_result.json
      legacy_sibling_run.json   # if legacy folder exists
```

**Legacy sibling** `..._c1` folders are no longer created by product runs. Existing siblings are recorded in `legacy_sibling_run.json` and `legacy_run_folders` in results.

---

## 6. Results Page

Kling Native Audio panel now shows:

- Generation Status
- Output Ready: yes/no
- Recovery Available: yes/no
- Download failed message when applicable
- Output not ready until MP4 exists
- Legacy partial folder paths (if any)

---

## 7. Validation

```bash
python project_brain/validate_kling_download_recovery_fix.py
```

**All checks passed**

| Test | Result |
|------|--------|
| Recover mode never clicks Generate | PASS |
| Recover mode never spends credits | PASS |
| Failed download status reported clearly | PASS |
| Parent/clip folder structure correct | PASS |
| Sibling `_c1` not canonical output | PASS |
| Generation success + download failure ≠ final success | PASS |
| Results page shows pending recovery | PASS |

---

## 8. Recovery Command for Confirmed Run

For the confirmed failure run:

```bash
python tools/kling_multishot_live_runner.py \
  --recover-latest-output \
  --run-id kling_ms_20260617T020932_34fa50d2_c1 \
  --clip-index 1
```

Requirements:

- Chrome CDP open on Runway tab with generated output still visible
- No Generate click; no new credits

---

## 9. Next Recommended Phase

1. Wire **Recover Output** button on Results page (calls recovery endpoint)
2. Auto-retry download strategies with backoff before marking `download_failed`
3. Network-response hook to capture direct MP4 URL during generation (CDP response listener)
4. Migrate legacy `_c1` sibling artifacts into parent `clips/c1/` on load
