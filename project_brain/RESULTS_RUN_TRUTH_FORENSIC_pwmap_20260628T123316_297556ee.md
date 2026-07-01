# Results Run Truth Forensic — pwmap_20260628T123316_297556ee

**Run ID:** `pwmap_20260628T123316_297556ee`  
**Run folder:** `outputs/pwmap_agent_runs/pwmap_20260628T123316_297556ee/`  
**Forensic date:** 2026-06-20  
**Scope:** Read-only disk inspection + reporting-path root-cause analysis. No new generation, Runway, YouTube upload, or gate bypass.

---

## 1. Files found on disk

| File | Present | Size (bytes) |
|------|---------|--------------|
| `clip_1.mp4` | Yes | 31,626,731 |
| `clip_2.mp4` | Yes | 31,626,731 |
| `clip_3.mp4` | **No** | — |
| `video.mp4` | Yes | 31,626,731 |
| `agent_result.json` | Yes | 2,703 |
| `execution_report.json` | Yes | 1,898 |
| `job.json` | Yes | 5,205 |
| `last_result.json` | Yes | 759 |
| `normalized_result.json` | Yes | 118,085 |
| `visual_diversity_report.json` | Yes | 2,045 |
| `subprocess_stdout.log` | Yes | 6,743 |
| `publish/` folder | **No** | — |
| Assembly manifest | **No** | — |
| `publish_package.json` | **No** | — |

---

## 2. Hashes (SHA-256)

| File | SHA-256 |
|------|---------|
| `clip_1.mp4` | `e8949dbd23dc94d202b748c11600b965b101c2d4c071ad2b831e1de6d3512fc3` |
| `clip_2.mp4` | `e8949dbd23dc94d202b748c11600b965b101c2d4c071ad2b831e1de6d3512fc3` |
| `video.mp4` | `e8949dbd23dc94d202b748c11600b965b101c2d4c071ad2b831e1de6d3512fc3` |

All three files are **byte-identical**. Visual repetition is **real**, not a reporting artifact.

---

## 3. video.mp4 readability

- File exists and exceeds minimum MP4 size threshold.
- `validate_mp4_path()` returns valid for all three MP4s.
- `video.mp4` is a **raw candidate/stitch**, not a publish-ready deliverable (no `publish/` package, no branded final).

---

## 4. Contradictory claims (before fix)

| Source | Claims |
|--------|--------|
| `agent_result.json` | `ok: true`, `status: completed`, `clip_count: 2`, 2 valid clips |
| `project_brain/runtime_state/latest_run_attempt.json` | `status: failed`, `clips_completed: 3`, `message: partial_finalization`, lists `video.mp4` as third “clip” path |
| Results UI (pre-fix) | Metadata “completed”, Run Attempt “failed / 3 clips”, Delivery Truth “No final MP4 available”, “Latest Approved Video: video.mp4” with “Approved: No” |

---

## 5. Root causes

### clips_completed = 3

- **Source:** `latest_run_attempt.json` → `downloaded_clip_paths` included `video.mp4` alongside `clip_1.mp4` and `clip_2.mp4`.
- **Cause:** Pre-fix `register_pwmap_product_studio_run()` / `record_latest_run_attempt()` counted every valid path in `downloaded_file_paths`, and registration previously appended the merged `video.mp4` as if it were a third clip.
- **Disk truth:** 2 clip files only (`clip_1.mp4`, `clip_2.mp4`).

### clip_count = 2 (metadata)

- **Source:** `agent_result.json` and `visual_diversity_report.json` metadata — correct for downloaded Runway clips.
- **Requested count:** `job.json` has **2 prompts** → requested = 2, downloaded = 2 (not a 3-requested / 2-downloaded scenario).

### Delivery Truth “No final MP4 available”

- **Cause:** `_merge_pwmap_results()` did not call `build_delivery_truth_panel()`; `delivery_truth_checks` was empty in the API payload.
- **Secondary cause (fixed):** `resolve_audit_mp4_for_run()` previously pulled a **stale global registry** MP4 from another run instead of the pwmap folder’s `video.mp4`.
- **Disk truth:** `video.mp4` exists and is readable; audit now targets it as **candidate** (`audit_target_kind: candidate`).

### “Latest Approved Video” with Approved: No

- **Cause:** `_merge_pwmap_results()` set `latest_approved_video_path = video_path` unconditionally from agent metadata, without audit / diversity / publish gates.

### Pipeline: Post-processing not started / Assembly missing

- **Disk truth:** Correct — only raw clips + candidate `video.mp4`; no assembly bridge output, no publish package.

### Visual diversity

- `visual_diversity_report.json`: `status: visual_repetition_failed`, pair 1–2 similarity **1.0**, `youtube_upload_allowed: false`.
- Confirmed by identical file hashes — upload block is **correct**.

---

## 6. Fixes applied (reporting only)

| File | Change |
|------|--------|
| `content_brain/platform/run_truth_resolver.py` | **New** — disk-backed clip discovery, candidate vs approved video, unified status/counts |
| `content_brain/platform/delivery_truth_loader.py` | `resolve_audit_mp4_for_run()` audits publish deliverable → candidate `video.mp4` |
| `content_brain/execution/pwmap_finalization.py` | Registration counts **clip_N.mp4 only**; stores `candidate_video_path` separately |
| `ui/api/product_studio_service.py` | `_merge_pwmap_results()` calls `enrich_pwmap_results_truth()` |
| `ui/api/schemas/product_studio.py` | `video_approved`, `video_display_label`, `candidate_video_path`, `run_truth` |
| `ui/web/src/pages/ResultsPage.tsx` | “Unapproved Candidate Video” label; clips downloaded; approval gate wording |
| `project_brain/validate_results_run_truth_consistency.py` | **New** validation suite |

---

## 7. Corrected canonical state (expected UI)

| Field | Value |
|-------|-------|
| Runway | completed (2 clips downloaded) |
| Downloaded clips | **2** |
| Requested clips | **2** |
| Assembly | missing |
| Publish package | missing |
| Candidate video | `video.mp4` (unapproved) |
| Latest Approved Video | *(empty — not shown)* |
| Delivery Truth | **FAIL** (audits `video.mp4`, checks populated) |
| Approved | **No** |
| YouTube upload | **Blocked** |
| Visual diversity | `visual_repetition_failed` (clips 1–2 identical) |
| Run attempt status | **failed** / `partial_finalization` |

**Block reasons:** publish package missing; visual diversity failed; delivery audit did not pass; candidate is not canonical publish deliverable.

---

## 8. Validation

Run:

```bash
python project_brain/validate_results_run_truth_consistency.py
```

Restart API after code changes: `python -m ui.api.main` (port 8765).

---

## 9. Operator notes

- On-disk `latest_run_attempt.json` still shows `clips_completed: 3` until the next registration; the **API enrich layer overrides** to 2 for matching run ID.
- `agent_result.json` on disk retains `status: completed` (generation subprocess outcome); Results API now exposes **unified** `status: failed` when attempt/delivery gates fail.
- Do **not** mark publish-ready or upload manually for this run.
