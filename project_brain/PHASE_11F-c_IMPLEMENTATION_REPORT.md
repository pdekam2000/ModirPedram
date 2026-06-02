# Phase 11F-c — Hailuo Download & Artifact Continuity

**Status:** Complete  
**Date:** 2026-05-30  
**Prerequisites:** Phase 11F-b browser hardening · Runway 11E-d baseline

---

## Summary

Hailuo download and artifact handling now **fully mirrors Runway 11E-d**: standardized `clip_results[]` records, min-size gate with file preservation, partial bundles on cancel/failure, source URL validation, and 10J-e `ArtifactValidationEngine` compatibility.

---

## Files Created

| File | Purpose |
|------|---------|
| `project_brain/validate_11f_c_hailuo_artifacts.py` | Mock-only artifact continuity matrix (20 tests) |
| `project_brain/PHASE_11F-c_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `providers/hailuo_artifact_utils.py` | 11F-c schema: `task_id`, `job_id`, `artifact_preserved`, `REQUIRED_ARTIFACT_FIELDS`, `clip_result_paths`, URL validation |
| `providers/hailuo_download_provider.py` | Clip-aware video select, source URL gate, `job_id` filenames, `clip_results` on provider |
| `orchestrators/hailuo_multi_clip_orchestrator.py` | `require_download_path`, partial bundle with `artifact_preserved`, final `clip_result_paths` guard |
| `providers/hailuo_api_errors.py` | `artifact_preserved` on cancel details; version `11f_c_v1` |
| `providers/hailuo_error_classifier.py` | `ARTIFACT_NULL_PATH`, `ARTIFACT_PATH_MISSING`, invalid source URL, cancel-during-download patterns |
| `project_brain/validate_11f_b_hailuo_browser_hardening.py` | Mock `open_video_for_clip` alias (regression fix only) |

---

## Artifact Schema (`hailuo_artifact_utils` v `11f_c_v1`)

| Field | Description |
|-------|-------------|
| `file_path` | Required absolute path |
| `provider` / `provider_id` | `hailuo_browser` |
| `mode` | `browser` |
| `capability` | `text_to_video` |
| `clip_index` | 1-based clip number |
| `task_id` / `job_id` | `hailuo_clip_{NN}` when no external task |
| `source_url` | CDN/blob URL when available |
| `size_bytes` | File size on disk |
| `sha256` | Computed when file exists |
| `downloaded_at` | Timestamp |
| `validation_status` | `pending` / `valid` / `partial` / `invalid_too_small` |
| `partial` | True when run ended early |
| `artifact_preserved` | **Always true when file written** — never deleted on failure |
| `metadata` | MIME, `hailuo_job_id`, etc. |

---

## Provider / Download Normalization

- **`finalize_download_artifact`**: min 100KB gate; raises `ARTIFACT_TOO_SMALL` but **preserves file**
- **`require_file_path` / `require_download_path`**: block missing paths (`ARTIFACT_NULL_PATH`)
- **`clip_result_paths`**: validates no `None` entries before orchestrator return
- **Source URL**: validated via `is_valid_source_url` (http/https/blob) before finalize
- **Download select**: `open_video_for_clip(clip_index=)` — bounded index pick on assets page

---

## Partial Artifact Behavior

On cancel or failure:

1. `mark_clip_results_partial()` — sets `partial=True`, `artifact_preserved=True`, `validation_status=partial`
2. `partial_artifact_bundle()` — attaches `partial_paths`, `clip_results`, `artifact_preserved=True`
3. Orchestrator `_attach_partial_artifacts()` merges bundle into exception details
4. `HailuoCancelledError` receives updated `partial_paths` + `clip_results`
5. **Files are never deleted**

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11f_c_hailuo_artifacts  # 20/20 PASS
py -3.11 -m project_brain.validate_11f_b_hailuo_browser_hardening  # 23/23 PASS (regression)
py -3.11 -m project_brain.validate_11f_a_hailuo_preflight  # nested PASS
# validate_11e_matrix + validate_10k_matrix — nested PASS
```

**Mock files only** — no browser automation or API calls.

---

## Scope Compliance

| Rule | Status |
|------|--------|
| Download/artifact normalization only | ✅ |
| No API / UI / default provider / failover changes | ✅ |
| No runtime dispatch structure changes | ✅ |
| Artifacts never deleted | ✅ |
| 10J/10K/11A–11F-b preserved | ✅ |

---

## Known Limitations

1. Assets-page video index is best-effort (`min(clip_index-1, count-1)`); true prompt-hash matching deferred.
2. Blob URLs accepted for in-page extraction; invalid URLs blocked at finalize.
3. Runtime engine does not yet map `HailuoCancelledError` to CANCELLED (11F-d scope).
4. Session artifact root copy still uses generic runtime canonicalization.

---

## Next Recommended Slice

**11F-d — Runtime Cancel Wiring**

- Add Hailuo to `provider_cancel_wiring`
- Handle `HailuoCancelledError` in `ProviderRuntimeEngine`
- `validate_11f_d_runtime_cancel_wiring`

---

## Production Code Changed?

**Yes** — Hailuo artifact utils, download provider, orchestrator, error classifier, and cancel error metadata only. No router, UI, runtime engine, or preflight changes.
