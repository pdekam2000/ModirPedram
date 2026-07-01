# PWMAP 30s Two-Clip Duplicate Root Cause — pwmap_20260628T123316_297556ee

**Run ID:** `pwmap_20260628T123316_297556ee`  
**Phase:** PWMAP-30S-TWO-CLIP-DUPLICATE-ROOT-CAUSE  
**Date:** 2026-06-20  
**No generation, Runway/Kling calls, credits spent, upload, or gate bypass performed.**

---

## 1. Duration planner truth (30s → 2 clips)

| Field | Value | Source |
|-------|-------|--------|
| `selected_duration_seconds` | **30** | `normalized_result.json` → `duration_plan.requested_duration_seconds` |
| `requested_clip_count` | **2** | `PRODUCT_DURATION_PRESETS[30] == 2`, `job.json` (2 prompts) |
| `expected_clip_count` | **2** | `execution_report.json`, `agent_result.json` |
| `clip_3.mp4` required? | **No** | 30s rule maps to exactly 2 clips |

Confirmed via `calculate_product_clip_count(30) == 2` and on-disk artifacts (only `clip_1.mp4`, `clip_2.mp4`).

**Missing `clip_3.mp4` is not a bug for this run.**

---

## 2. Duplicate mechanism classification

**Primary root cause: B — Clip 2 generated, but downloader captured stale/previous output**

| Check | Finding |
|-------|---------|
| Clip 2 generation started? | **Yes** — subprocess log shows full CLIP 2/2 workflow (~16 min after clip 1) |
| Prompts different? | **Yes** — clip1 SHA `5785170f…` (2493 chars), clip2 SHA `f9e90c3c…` (2497 chars) in `job.json` |
| Use Frame invoked? | **Yes** — log: seek second 14, “Use frame clicked (last frame)” |
| Separate download paths? | **Yes** — `clip_001_20260628_144453.mp4` vs `clip_002_20260628_150056.mp4` |
| Source bytes identical before Modir copy? | **Yes** — pwmap `runway_downloads` sources share SHA-256 `e8949dbd…` |
| Modir finalization copied clip1→clip2? | **No** — `copy_mp4_outputs` copies from distinct source paths; identity predates ModirAgentOS |
| `video.mp4` origin | Copy of **last clip** (`clip_2.mp4`) per `copy_mp4_outputs` — inherits duplicate |

**Ruled out:**

- **A** — Clip 2 was not skipped; generation + download events logged  
- **D** — Prompt text differs (not duplicate prompts)  
- **E** — Finalization did not invent duplicate; it faithfully copied already-identical sources  
- **F** — Paths are distinct files, not aliased metadata  

**Contributing factor:** pwmap runner uses **“Download via video URL”** without post-download hash verification against prior clip. Separate filenames/timestamps masked identical media payload.

---

## 3. Files inspected

| File | Role |
|------|------|
| `job.json` | 2 distinct prompts, 15s per clip, Use Frame second 14 |
| `subprocess_stdout.log` | Full CLIP 1/2 and CLIP 2/2 automation trace |
| `last_result.json` | Per-clip download paths, Use Frame flags, timestamps |
| `agent_result.json` | 2 valid clips registered (pre-guard) |
| `execution_report.json` | Finalization stages |
| `normalized_result.json` | `duration_plan`: 30s / 2 clips |
| `visual_diversity_report.json` | `visual_repetition_failed`, similarity 1.0 (clips 1–2) |
| `C:/Users/kaman/Desktop/pwmap/runway_downloads/clip_001_*.mp4` | Source clip 1 (31,626,731 B) |
| `C:/Users/kaman/Desktop/pwmap/runway_downloads/clip_002_*.mp4` | Source clip 2 — **byte-identical to clip 1** |
| Run folder `clip_1.mp4`, `clip_2.mp4`, `video.mp4` | All identical SHA-256 |

---

## 4. Files changed

| File | Change |
|------|--------|
| `content_brain/execution/pwmap_clip_duplicate_guard.py` | **New** — SHA-256 duplicate guard, download freshness, Use Frame gate |
| `content_brain/execution/pwmap_finalization.py` | Wire guards into `verify_and_recover_clip_downloads`; block registration on duplicate |
| `content_brain/platform/run_truth_resolver.py` | Disk duplicate analysis, 30s clip-3 N/A, block approval on duplicate chain |
| `ui/api/product_studio_service.py` | Expose `selected_duration_seconds` |
| `ui/api/schemas/product_studio.py` | Duplicate / clip status fields |
| `ui/web/src/pages/ResultsPage.tsx` | Requested/downloaded/duplicate/clip-3 N/A display |
| `project_brain/validate_pwmap_30s_two_clip_duplicate_guard.py` | **New** validation (15 tests) |

---

## 5. New guard behavior

### Anti-duplicate guard (before clip registration)

- SHA-256 each downloaded clip against prior clips in the same run  
- On match → `status: duplicate_failed`, error: *“Downloaded clip is byte-identical to a previous clip; possible stale output/download selection.”*  
- Does not count duplicate toward valid clip count  
- Blocks `video.mp4` approval / publish continuation  

### Download freshness guard (clip 2+)

- Requires evidence clip is not stale: `finished_at` ordering, mtime, size/hash difference  
- If unprovable → `download_status: ambiguous_stale_output` (fail closed)  

### Use Frame guard (clip 2+)

- Requires `used_frame_from_previous`, `use_frame_second`, and subprocess “Use frame clicked” evidence  
- Missing → `use_frame_missing` (blocks registration)  

---

## 6. Corrected Results truth (this run)

| Field | Value |
|-------|-------|
| Duration | **30s** |
| Requested clips | **2** |
| Downloaded clips | **2** (files exist) |
| Clip 1 | exists |
| Clip 2 | exists, **duplicate_failed** |
| Clip 3 | **not applicable** |
| Duplicate clips | **failed** |
| Candidate video | unapproved (`video.mp4`) |
| Delivery Truth | FAIL |
| Approved | No |
| YouTube upload | Blocked |
| Reason | duplicate clip output + visual repetition |
| Assembly | missing |
| Publish package | missing |

---

## 7. Validation results

```text
python project_brain/validate_pwmap_30s_two_clip_duplicate_guard.py  → 15/15 PASS
python project_brain/validate_results_run_truth_consistency.py     → 19/19 PASS
```

---

## 8. Confirmations

- No new video generation performed  
- No Runway/Kling API or browser generation invoked  
- No credits spent  
- Visual diversity block preserved  
- No publish/upload bypass  
- Missing `clip_3.mp4` correctly treated as N/A for 30s  

---

## 9. Next recommended phase

**PHASE PWMAP-30S-TWO-CLIP-LIVE-RETEST**

Before live retest, harden the **pwmap runner download path** (outside ModirAgentOS repo at `Desktop/pwmap`) to:

1. Capture video URL / card fingerprint at generation-complete time per clip  
2. Reject download if URL/hash matches prior clip in batch  
3. Integrate with existing `kling_useframe_generation_completion_gate` artifact signature pattern  

ModirAgentOS guards now fail closed at finalization/Results; the stale URL selection fix in the pwmap browser runner is required to prevent recurrence on the next live 30s run.
