# Subtitle Pipeline Failure Report

**Phase:** DELIVERY-QUALITY-RECOVERY — Priority 4  
**Run:** `cb_e2e_20260614_195440_8bf41b6b`  

---

## Summary

| Step | Status |
|------|--------|
| Subtitle files generated | **YES** |
| Styled ASS prepared | **YES** |
| FFmpeg burn executed | **YES** |
| Visibility QA | **FAILED** |
| Subtitled video used in branding chain | **NO** |
| Subtitles in canonical deliverable | **NO** |

---

## Pipeline stages

### 1. Subtitle generation (PASS)

| Item | Detail |
|------|--------|
| **File** | `content_brain/audio/audio_post_processing.py` |
| **Function** | `run_audio_post_processing()` → `generate_timed_subtitles()` |
| **Outputs** | `outputs/audio/subtitles/subtitles.srt`, `.vtt`; styled via `write_styled_ass_outputs()` |
| **Publish copies** | `publish/subtitles/subtitles.srt`, `.vtt`, `subtitles_styled.ass` |
| **Cues** | 5 cues, 0.000 → 18.553 s |
| **Timing mode** | `proportional_by_segment_length` tied to **narration audio** (~18.55 s), not 40 s video |

**Manifest:** `subtitle_status: "Subtitle: pending burn — styled ASS ready for branding"`

---

### 2. Subtitle burn (executed, then failed QA)

| Item | Detail |
|------|--------|
| **File** | `content_brain/branding/subtitle_burn_engine.py` |
| **Function** | `burn_subtitles()` |
| **Input video** | `final/FINAL_RUNWAY_PHASE_I_ENV.mp4` |
| **Subtitle source** | `outputs/audio/subtitles/subtitles_styled.ass` |
| **Method** | FFmpeg `drawtext` filter (`burn_method: drawtext`) |
| **Output** | `final/branding_staging/FINAL_RUNWAY_PHASE_I_SUBTITLED.mp4` |

**FFmpeg:** executed (`ffmpeg_executed: true`)

---

### 3. Visibility QA failure (root cause)

| Item | Detail |
|------|--------|
| **File** | `content_brain/branding/subtitle_format_engine.py` |
| **Functions** | `compare_subtitle_burn_visibility()`, `measure_subtitle_text_bbox()` |
| **Dependency** | **`numpy`** (and PIL) for pixel/bbox analysis |

**Evidence from manifest (`burn_bbox_samples`):**

```json
"error": "No module named 'numpy'"
"visible": false
"burn_visible_enough": false
"burn_psnr_avg": 14.393625
```

**Logic in `subtitle_burn_engine.py` (lines 237–241):**

```python
if result.status == "COMPLETED" and not burn_visible:
    result.status = "FAILED"
    result.error = "subtitle_burn_not_visible"
```

Burn may have run, but QA cannot confirm visible text → status downgraded to **FAILED**.

---

### 4. Branding fallback (non-subtitled base used)

| Item | Detail |
|------|--------|
| **File** | `content_brain/branding/branding_runtime.py` |
| **Function** | `run_branding_runtime()` |

**Fallback behavior:**

| Line | Behavior |
|------|----------|
| 153–158 | If burn completes but not visible → set `subtitle_status` FAILED, `warnings.append("subtitle_burn_not_visible")`, **`base["status"] = "failed"`** |
| 163–164 | **`current_video = subtitled output` ONLY if `subtitle_result.status == "COMPLETED"`** |
| 163–167 | On **FAILED**, `current_video` **stays** `FINAL_RUNWAY_PHASE_I_ENV.mp4` (no subtitles) |
| 205–219 | CTA overlay applied to **non-subtitled** base |
| 273–274 | `shutil.copy2(current_video, branded_out)` |
| **276** | **`base["status"] = "completed"`** — overwrites earlier `"failed"` |

**Result:** Canonical branded file = **CTA on ENV video**, hash matches `cta_overlay.mp4`, **not** subtitled staging file.

---

### 5. Publish (sidecar only)

| Item | Detail |
|------|--------|
| **File** | `content_brain/execution/runway_live_post_processor.py` |
| **Function** | `run_publish_package()` |

- Copies `.srt`/`.vtt`/`.ass` into `publish/subtitles/` (**sidecar files**)
- Promotes `FINAL_BRANDED_VIDEO_CANONICAL.mp4` from branding (**no burned subs**)
- Records `subtitle_status: "Subtitle: FAILED — burn failed"` in metadata
- Still sets `status: PUBLISHED_PACKAGE_CREATED`

---

## Why QA failed

| Cause | Detail |
|-------|--------|
| **Primary** | Missing Python package **`numpy`** in runtime environment |
| **Secondary** | `measure_subtitle_text_bbox()` also fails without numpy → all samples `visible: false` |
| **Tertiary** | Low PSNR (~14.4) may indicate burn weak even if QA ran — cannot verify without numpy |

---

## Why final delivery ignored subtitle version

1. `burn_subtitles()` returns **`status: FAILED`** after visibility check.
2. Branding runtime **only advances `current_video` to subtitled file on `COMPLETED`**.
3. Failed burn → chain continues from **ENV** (fail-open).
4. Final **`status: completed`** on branding masks subtitle failure for checkpoint logic.

---

## Exact failure point

```
burn_subtitles()
  → FFmpeg drawtext (may produce output file)
  → compare_subtitle_burn_visibility() / measure_subtitle_text_bbox()
  → ImportError: No module named 'numpy'
  → burn_visible = False
  → result.status = FAILED, error = subtitle_burn_not_visible
  → branding_runtime: current_video NOT updated
  → CTA → FINAL_BRANDED_VIDEO_CANONICAL.mp4 (no visible subtitles)
```

---

## Recommended fix direction (design only)

1. Install **numpy** (and verify PIL) in production runtime OR degrade QA gracefully with explicit “QA skipped” vs “burn failed”.
2. **Fail closed:** do not set branding/publish `completed` when `subtitle_enabled` and burn FAIL.
3. Do not overwrite branding `status: failed` → `completed` at end of `run_branding_runtime()`.
4. Align subtitle timing to **final video duration** (40 s target), not truncated narration-only timeline.

**No implementation in this phase.**
