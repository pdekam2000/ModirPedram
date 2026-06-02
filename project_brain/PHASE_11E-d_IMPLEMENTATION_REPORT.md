# Phase 11E-d — Runway Download & Artifact Continuity

**Status:** Complete  
**Date:** 2026-05-28  
**Validation:** `validate_11e_d_runway_artifacts` **20/20 PASS** (includes 11E-a/b/c, 11A–11D, 10K regression)

---

## Summary

Phase 11E-d unifies Runway **download and artifact metadata** across API and browser paths via a shared normalization helper. Both paths now emit compatible `clip_results` records with required fields, size/sha256 metadata, taxonomy-mapped errors, and explicit partial-artifact bundles on cancel/failure. **Files are never deleted on validation failure.** Active default (`runway_browser`), router dispatch, UI, and I2V scope remain unchanged.

---

## Files Created

| File | Purpose |
|------|---------|
| `providers/runway_artifact_utils.py` | Shared artifact normalization, finalize gate, partial bundles, sha256 |
| `project_brain/validate_11e_d_runway_artifacts.py` | Mock-only validation (20 tests + regressions) |
| `project_brain/PHASE_11E-d_IMPLEMENTATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `providers/runway_video_provider.py` | Uses `finalize_download_artifact`; normalized `clip_results`; cancel attaches `partial_artifact_bundle`; no file deletion on too-small |
| `providers/runway_download_provider.py` | Uses `finalize_download_artifact`; returns normalized dict; preserves files on size failure |
| `providers/runway_browser_support.py` | Imports `MIN_ARTIFACT_BYTES` from artifact utils (single source of truth) |
| `orchestrators/runway_browser_orchestrator.py` | `_attach_partial_artifacts()` on cancel/failure; partial `clip_results` + `partial_paths` |
| `project_brain/validate_11e_b_runway_api_hardening.py` | Small-download test asserts file preserved + `artifact_preserved: True` |
| `project_brain/validate_11e_c_runway_browser_hardening.py` | Fake download provider returns normalized records; asserts `provider_id` |

**Unchanged:** `VideoProviderRouter`, `ProviderRuntimeEngine`, UI, `active_providers.json` default, I2V, failover dispatch.

---

## Artifact Schema

Each normalized clip artifact record includes:

| Field | Type | Notes |
|-------|------|-------|
| `artifact_utils_version` | str | `"11e_d_v1"` |
| `file_path` | str | **Required** — raises `ARTIFACT_NULL_PATH` if missing |
| `provider` | str | Same as `provider_id` (backward compat) |
| `provider_id` | str | `"runway"` (API) or `"runway_browser"` (browser) |
| `mode` | str | `"api"` or `"browser"` |
| `capability` | str | `"text_to_video"` |
| `clip_index` | int \| null | 1-based clip index when known |
| `task_id` | str \| null | Runway API task id when available |
| `job_id` | str \| null | Alias of `task_id` when set |
| `source_url` | str \| null | CDN/download URL when available |
| `size_bytes` | int \| null | From filesystem stat |
| `sha256` | str \| null | `sha256:<hex>` when file exists and readable |
| `downloaded_at` | str | `YYYY-MM-DD HH:MM:SS` local timestamp |
| `validation_status` | str | `pending`, `valid`, `invalid_too_small`, `partial` |
| `partial` | bool | True when run ended before full completion |
| `metadata` | dict | Extensible provider-specific payload |

**Partial bundle** (attached to cancel/error `details`):

```json
{
  "partial": true,
  "partial_paths": ["..."],
  "clip_results": [/* marked partial records */],
  "clip_count": 1
}
```

**Minimum size gate:** `MIN_ARTIFACT_BYTES = 100_000` (100 KB). Too-small downloads raise `RunwayProviderError` code `ARTIFACT_TOO_SMALL` with `artifact_preserved: True`.

---

## API / Browser Normalization Behavior

| Path | Entry point | Mode | provider_id |
|------|-------------|------|-------------|
| REST API | `RunwayVideoProvider._download_video` → `finalize_download_artifact` | `api` | `runway` |
| Browser download | `RunwayDownloadProvider.download_video_url` → `finalize_download_artifact` | `browser` | `runway_browser` |
| Browser orchestrator | Aggregates download provider records into `clip_results` | `browser` | `runway_browser` |

Both paths:

1. Verify path exists (`ARTIFACT_PATH_MISSING` if not).
2. Enforce minimum byte size without deleting the file.
3. Compute sha256 when safe.
4. Set `validation_status` to `valid` (or `partial` when flagged).
5. Populate consistent top-level keys for 10J-e / 10K consumers.

Legacy keys (e.g. `video_url`) may appear in `metadata` or via `**extra` passthrough but standard fields are always present on success.

---

## Partial Artifact Behavior

| Scenario | Behavior |
|----------|----------|
| API cancel mid-poll | `RunwayCancelledError.details` includes `partial_artifact_bundle` with any completed `clip_results` and `partial_paths` |
| Browser cancel / failure | Orchestrator `_attach_partial_artifacts` marks existing records partial and merges bundle into error details |
| Too-small download | File **retained** on disk; error raised with path + size in details |
| Empty / missing path | Blocked at normalization — no silent empty artifacts |

`mark_clip_results_partial()` sets `partial: true` and `validation_status: partial` on each completed clip record.

---

## Error Handling

Errors flow through existing Runway taxonomy (`RunwayProviderError` / `RunwayCancelledError`):

| Code | When |
|------|------|
| `ARTIFACT_NULL_PATH` | Missing or blank `file_path` |
| `ARTIFACT_PATH_MISSING` | Path does not exist on finalize |
| `ARTIFACT_TOO_SMALL` | File below `MIN_ARTIFACT_BYTES` (file preserved) |

Classifier integration from 11E-a/b/c unchanged; artifact codes are additive.

---

## Validation Results

```bash
py -3.11 -m project_brain.validate_11e_d_runway_artifacts   # 20/20 PASS
```

| Test | Result |
|------|--------|
| API artifact record shape | PASS |
| Browser artifact record shape | PASS |
| Too-small artifact flagged (file preserved) | PASS |
| Missing file_path blocked | PASS |
| sha256 / size metadata | PASS |
| Partial artifact preservation | PASS |
| 10J-e ArtifactValidationEngine | PASS |
| Session metadata compatibility | PASS |
| API provider clip_results normalized | PASS |
| API cancel partial bundle | PASS |
| Active default runway_browser | PASS |
| No router dispatch change | PASS |
| 11E-a / 11E-b / 11E-c regressions | PASS |
| 11A / 11B / 11C / 11D regressions | PASS |
| 10K matrix | PASS |

Mock files only — no Runway API calls, no browser automation.

---

## Scope Compliance

| Requirement | Status |
|-------------|--------|
| Shared artifact metadata helper | ✅ `runway_artifact_utils.py` |
| API/browser compatible structures | ✅ |
| Partial artifacts preserved, not deleted | ✅ |
| 10J-e / 10K compatibility | ✅ |
| Taxonomy error mapping | ✅ |
| Validation script | ✅ |
| No Runway API in validation | ✅ |
| No browser automation in validation | ✅ |
| No provider default switch | ✅ |
| No UI changes | ✅ |
| No image-to-video | ✅ |
| No automatic failover | ✅ |
| No router dispatch changes | ✅ |

---

## Known Limitations

1. **Cancel wiring:** `cancel_check` is supported on providers/orchestrator but not yet propagated from `ProviderRuntimeEngine` (planned 11E-e).
2. **Session persistence mapping:** Runtime session layer still maps artifacts via existing 10J-e shape; normalized Runway fields live in `clip_results` / error `details` — full session field mirroring is a follow-up if needed.
3. **Browser partial paths:** `partial_paths` reflects files downloaded before failure; in-flight generation without download may yield empty `partial_paths` with partial flag only on completed clips.
4. **sha256 cost:** Computed synchronously on finalize for files passing size gate; skipped only on I/O failure.

---

## Next Recommended Slice

**11E-e — Runtime cancel_check wiring:** Thread cooperative cancel from `ProviderRuntimeEngine` / worker cancel (10K) into API and browser Runway providers so partial bundles are produced in live sessions, not only when callers pass `cancel_check` manually.

Alternative follow-up: unify asset downloader to consume normalized records for cross-provider audit history (10K operations panel).

---

## Quick Reference

```python
from providers.runway_artifact_utils import finalize_download_artifact, MODE_API, MODE_BROWSER

record = finalize_download_artifact(
    path,
    mode=MODE_BROWSER,
    provider_id="runway_browser",
    clip_index=1,
    source_url=url,
)
```
