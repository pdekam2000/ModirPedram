# PWMAP Download Selection Repair Report

**Phase:** PWMAP-DOWNLOAD-SELECTION-REPAIR  
**Date:** 2026-06-29  
**Verdict:** **PASS** (code + validation) — no provider generation performed

---

## 1. Root cause

**Bug:** `runway_agent.py` `_latest_video_src()` scanned **the entire page** for the first `<video>` with an `http` src. When the per-card Download button path failed, clip 2+ fell back to that URL — which was still clip 1’s CDN source.

**Contributing factors:**

| Factor | Effect |
|--------|--------|
| Download button loop started at feed index 0 | Could target an older card’s button |
| URL fallback was page-wide, not feed-scoped | Reused stale clip 1 source for clip 2 |
| No pre/post output snapshot at download time | Could not prove output belonged to current attempt |
| No source/SHA rejection in pwmap runner | Distinct filenames masked identical bytes |
| Success reported even when bytes duplicated | `generation_success` implied `download_success` |

**Forensic confirmation (both failed runs):**

| Run | Clip 1 download | Clip 2 download | Use Frame | SHA-256 |
|-----|-----------------|-------------------|-----------|---------|
| `pwmap_20260628T123316_297556ee` | URL fallback | URL fallback | Yes | `e8949dbd…` (identical) |
| `pwmap_20260629T101232_eda2c865` | URL fallback | URL fallback | Yes | `cb01be2c…` (identical) |

Both runs show `[i] Download via video URL...` in `subprocess_stdout.log` for every clip. Generation and Use Frame succeeded; **download selection** picked the wrong source.

**Stale URL/source reuse:** Confirmed — same bytes, different timestamped filenames, URL fallback on clip 2.

---

## 2. Files changed

### pwmap (browser runner)

| File | Change |
|------|--------|
| `C:\Users\kaman\Desktop\pwmap\download_selection.py` | **New** — snapshot diff, stale source rejection, duplicate MP4 quarantine, clip status builder |
| `C:\Users\kaman\Desktop\pwmap\runway_agent.py` | `capture_output_snapshot`, `download_clip_output`, feed-scoped `_feed_top_video_src`, pre/post snapshots per clip, `--inspect-existing-outputs`, separate generation/download status in `last_result` |

### ModirAgentOS

| File | Change |
|------|--------|
| `content_brain/execution/pwmap_clip_assembly_guard.py` | **New** — SHA-256 uniqueness check before stitch |
| `content_brain/execution/product_multiclip_orchestrator.py` | Block assembly + YouTube upload when duplicate bytes detected |
| `project_brain/validate_pwmap_download_selection_repair.py` | **New** — 23-check validation suite |

**Not changed:** prompts, Use Frame logic, browser mappings, YouTube OAuth, finalization duplicate guard (kept as safety net).

---

## 3. Repair behavior

### Output snapshot tracking (Part B)

Before Generate and after generation completes, `capture_output_snapshot()` records:

- Feed video count, per-video `src` / `currentSrc` / `poster`
- Output card `data-index`, card text hash
- Download button count, timestamp

### New output selection (Part C)

For each clip, `detect_new_output()` requires post-generation output to differ from pre-generation snapshot and all prior accepted clips. If unprovable:

- `download_status = ambiguous_stale_output`
- Error: *"Could not prove downloaded output belongs to current clip attempt."*
- No success registration

### Stale source rejection (Part D)

Before download, selected URL/fingerprint is compared to prior clips. Match → `stale_source_rejected`, no download.

### Duplicate MP4 rejection (Part E)

After download, SHA-256 is computed immediately. Duplicate → file moved to `runway_downloads/quarantine/`, `duplicate_mp4_rejected`, clip not registered.

### Separate statuses (Part F)

Each clip in `last_result.json` now includes: `generation_success`, `download_success`, `selected_source`, `output_card_fingerprint`, `download_status`, `duplicate_guard_status`, full `clip_status` object.

### Diagnostic mode (Part G)

```bash
python runway_agent.py --inspect-existing-outputs --output runway_downloads
```

Inspects visible feed outputs only — no Generate, no credits. Writes `inspect_existing_outputs.json`.

---

## 4. Validation

```bash
python -m project_brain.validate_pwmap_download_selection_repair
```

**Result: 23/23 PASS**

Chained validators also pass:

| Validator | Result |
|-----------|--------|
| `validate_pwmap_30s_live_retest_safety` | 15/15 |
| `validate_pwmap_30s_two_clip_duplicate_guard` | 15/15 |
| `validate_channel_story_ideation_diversity` | 19/19 |
| `validate_results_run_truth_consistency` | 19/19 |

---

## 5. Can old broken runs be repaired?

**No.** Runs `pwmap_20260628T123316_297556ee` and `pwmap_20260629T101232_eda2c865` already have byte-identical MP4s on disk. The repair applies to **future runs only**. Re-running generation (free-credit retest) is required to obtain distinct clip hashes.

ModirAgentOS correctly marks these runs unapproved with `duplicate_chain_failed: true`.

---

## 6. Duplicate clips cannot be assembled/uploaded

Three layers now block duplicates:

1. **pwmap runner** — rejects stale source / duplicate MP4 before clip registration  
2. **ModirAgentOS finalization** — `pwmap_clip_duplicate_guard.py` (unchanged, fail-closed)  
3. **Assembly guard** — `verify_clips_unique_for_assembly()` blocks FFmpeg stitch and sets `youtube_upload_allowed: false`

---

## 7. Confirmations

| Item | Status |
|------|--------|
| Provider generation during repair | **None** |
| Paid credits spent | **None** |
| Upload/publish bypass | **None** |
| Duplicate guard weakened | **No** |
| Visual diversity bypass | **No** |

---

## 8. Next recommended phase

**PHASE PWMAP-30S-TWO-CLIP-LIVE-RETEST-2**

- Duration: 30s, 2 clips, `free_credit_mode=true`
- Verify clip 1 SHA ≠ clip 2 SHA with repaired download selection
- Do **not** start 40s/60s until retest-2 passes
