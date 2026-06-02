# PHASE 12J-E1 — Runway Real Output Detection Fix

**Date:** 2026-05-31  
**Session reference:** `exec_uat_20260602_190032` (clips 1–2 downloaded `edit-studio-empty-state.webm`)  
**Scope:** Output URL detection and artifact validation only (no prompt/generate/voice/subtitle/assembly changes).

---

## Problem

`wait_for_generated_video_url()` accepted a stable visible `<video>` whose `src` was Runway’s edit-studio empty-state asset (`…/app/mira/empty-states/edit-studio-empty-state.webm`). `finalize_download_artifact()` only required HTTP 200 and size ≥ 100 KB, so ~6 MB placeholders passed as clips.

---

## Solution

### 1. URL classifier (`providers/runway_output_url_classifier.py`)

- `is_real_runway_output_url(url)` / `runway_output_rejection_reason(url)`
- Rejects: `empty-states`, `edit-studio-empty-state`, `placeholder`, `loading`, app shell paths, empty-state filenames, data-URI images
- Allows: signed CDN / generated-looking media URLs (e.g. `cloudfront.net/.../output.mp4`)
- `assert_real_runway_output_source()` for download-time validation
- Codes: `RUNWAY_REAL_OUTPUT_NOT_DETECTED`, `RUNWAY_PLACEHOLDER_OUTPUT_REJECTED`

### 2. Wait loop (`orchestrators/runway_browser_orchestrator.py`)

- New sources and fallback visible video must pass classifier
- Rejects URLs present in `before_sources` or `already_downloaded_urls`
- Fallback stability (3 polls) only for **real** candidates; resets when placeholder seen
- No fallback while `IN_QUEUE` / `GENERATING` (unchanged guard)
- On timeout with any video activity or rejections → `RUNWAY_REAL_OUTPUT_NOT_DETECTED` + debug payload
- Pure empty wait (no sources) → `PROVIDER_TIMEOUT` (11E-C compatible)
- Debug: `rejected_candidates`, `before_sources`, `visible_videos`, `page_state`, `body_text_summary`, `screenshot_path` (if Playwright supports it)

### 3. Download validation (`providers/runway_artifact_utils.py`)

- `finalize_download_artifact()` calls `assert_real_runway_output_source()` **before** size check
- Placeholder rejected even when file size > 100 KB

### 4. Observability (`content_brain/execution/runway_browser_observability.py`)

- `record_output_detection_failure(debug)` persisted under `runway_browser_obs`

### 5. Generation-in-progress report (`providers/runway_browser_provider.py`)

- `click_generate` refusal when already generating includes: `page_state`, real vs placeholder visible URLs, job text snippet (no full fix for in-progress race)

---

## Files touched

| File | Change |
|------|--------|
| `providers/runway_output_url_classifier.py` | New classifier + assert helper |
| `orchestrators/runway_browser_orchestrator.py` | Hardened `wait_for_generated_video_url()` |
| `providers/runway_artifact_utils.py` | Placeholder guard in `finalize_download_artifact()` |
| `content_brain/execution/runway_browser_observability.py` | `record_output_detection_failure()` |
| `providers/runway_browser_provider.py` | Richer “generating” block message |
| `project_brain/validate_12j_e1_runway_real_output_detection.py` | E1 validator |
| `project_brain/validate_11e_c_runway_browser_hardening.py` | Mock `prepare_clip_for_generate` (E0 API alignment) |

**Not modified:** Content Brain, prompt composer, story intelligence, prompt insertion, generate click logic, voice/subtitle/assembly runtimes.

---

## Validation

```text
python project_brain/validate_12j_e1_runway_real_output_detection.py  → OK
python project_brain/validate_11e_c_runway_browser_hardening.py       → OK
```

E1 checks (10):

1. `edit-studio-empty-state.webm` rejected  
2. `empty-states` paths rejected  
3. Generic `placeholder` rejected  
4. Real-looking generated URL accepted  
5. Fallback does not return placeholder  
6. Download rejects placeholder despite size > 100 KB  
7. Wait records rejections instead of accepting  
8. Failure code `RUNWAY_REAL_OUTPUT_NOT_DETECTED`  
9. `rejected_candidates` persisted in error details  
10. Prompt/generate paths unchanged (static guard)

---

## Expected UAT behavior

- **Success:** Next 40s UAT must not download `edit-studio-empty-state.webm` as clip output.  
- **Failure:** If Runway never exposes a real output URL, the run waits until max wait, then fails with `RUNWAY_REAL_OUTPUT_NOT_DETECTED` and session debug (rejected URLs, page state, visible videos)—not silent placeholder assembly.

---

## Follow-up (out of scope)

- Full “generation already in progress” recovery between clips (clip 3 blocker in `exec_uat_20260602_190032`) remains a separate hardening item.
