# Phase 10J-e — Implementation Report

Generated: 2026-05-30  
Status: **Complete**  
Scope: Post-provider artifact validation before COMPLETED

---

## Summary

Phase 10J-e adds **`ArtifactValidationEngine`** to validate provider output after clip execution and **before** marking a session `COMPLETED`. Invalid artifacts fail with **`ARTIFACT_REJECT`** codes; **valid clips are preserved** on disk and in session JSON for inspection.

**Unchanged:** `VideoProviderRouter`, `providers/*`, `BrowserManager`, orchestrators, `full_video_pipeline.py`, `ui/app.py`.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/artifact_validation_engine.py` | Path/size/extension/count checks, metadata enrichment, sha256 |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/provider_runtime_engine.py` | Validate after `_build_video_artifacts`, before COMPLETED; `_mark_artifact_validation_failed` |
| `content_brain/execution/failure_taxonomy.py` | Added `ARTIFACT_PATH_MISSING` |
| `content_brain/execution/__init__.py` | Lazy exports for validation engine |
| `ui/api/services/runtime_service.py` | `progress.clip_validated_count` from operations.validation |

---

## Validation Rules

| Check | Fail code |
|-------|-----------|
| `file_path` null/empty | `ARTIFACT_NULL_PATH` |
| Path does not exist | `ARTIFACT_PATH_MISSING` |
| Extension not in `.mp4/.webm/.mov` (or `.mock` dry-run) | `ARTIFACT_INVALID_TYPE` |
| Size below `min_artifact_bytes` (default 100_000) | `ARTIFACT_TOO_SMALL` |
| Clip count ≠ target | `ARTIFACT_COUNT_MISMATCH` |
| Multiple issues | First specific code; umbrella `ARTIFACT_VALIDATION_FAILED` if unset |

Dry-run: `.mock` files allowed with **min size = 1 byte**.

Optional **sha256** computed and stored when file is readable.

---

## Integration Flow

```
ProviderRuntimeEngine._execute_clips()
  → _build_video_artifacts()
  → ArtifactValidationEngine.validate()
       ├─ pass → ARTIFACT_VALIDATED audit → COMPLETED
       └─ fail → artifacts persisted → FAILED (ARTIFACT_REJECT)
```

Worker async path uses the same engine via `dispatch_by_id()` — no worker rewrite required.

---

## Validation Result Example (pass)

```json
{
  "validated_at": "2026-05-30 01:15:00",
  "passed": true,
  "validation_version": "10j_v1",
  "clip_target": 2,
  "clip_valid": 2,
  "clip_invalid": 0,
  "invalid_clips": [],
  "checks": [
    {"id": "MIN_SIZE", "passed": true, "message": "Clip 1: size 42 OK"},
    {"id": "COUNT_MATCH", "passed": true, "message": "Clip count 2 matches target 2"}
  ]
}
```

Stored at: `execution_runtime.operations.validation`

---

## Artifact Metadata Example

```json
{
  "artifact_id": "art_a1b2c3d4e5f6",
  "artifact_type": "video_clip",
  "clip_number": 1,
  "file_path": "storage/content_brain/execution/artifacts/exec_10i_dequeued_demo/video_generation/clip_01.mock",
  "size_bytes": 52,
  "sha256": "sha256:abc123...",
  "validated_at": "2026-05-30 01:15:00",
  "validation_status": "valid",
  "validation_error": null,
  "provider_execution": {
    "provider_name": "hailuo",
    "provider_category": "video_generation",
    "execution_mode": "browser",
    "learning_key": "hailuo_browser",
    "router_key": "hailuo_browser"
  }
}
```

---

## Failure Examples

### Null path

```json
{
  "state": "FAILED",
  "failure": {
    "code": "ARTIFACT_NULL_PATH",
    "category": "ARTIFACT_REJECT",
    "message": "Clip 1: null file_path",
    "retriable": true,
    "details": {
      "clip_target": 2,
      "clip_valid": 0,
      "clip_invalid": 1,
      "invalid_clips": [1]
    }
  }
}
```

### Missing path

```json
{
  "failure": {
    "code": "ARTIFACT_PATH_MISSING",
    "category": "ARTIFACT_REJECT",
    "message": "Clip 2: path missing"
  }
}
```

### Too small

```json
{
  "failure": {
    "code": "ARTIFACT_TOO_SMALL",
    "category": "ARTIFACT_REJECT",
    "message": "Clip 2: too small (10 bytes)"
  }
}
```

### Count mismatch

```json
{
  "failure": {
    "code": "ARTIFACT_COUNT_MISMATCH",
    "category": "ARTIFACT_REJECT",
    "message": "Expected 2 clips, got 1"
  }
}
```

### Partial failure — valid clips preserved

When clip 1 is valid (200 KB) and clip 2 is too small:

- Session state → **FAILED**
- `artifacts_by_category.video_generation` contains **both** clips
- Clip 1: `validation_status: "valid"`
- Clip 2: `validation_status: "invalid"`, `validation_error: "ARTIFACT_TOO_SMALL"`
- **Files not deleted**

Audit events: `ARTIFACT_VALIDATION_FAILED`, `FAILED`

---

## Regression Results

| Test | Result |
|------|--------|
| Null path → `ARTIFACT_NULL_PATH` | **PASS** |
| Missing path → `ARTIFACT_PATH_MISSING` | **PASS** |
| Tiny file → `ARTIFACT_TOO_SMALL` | **PASS** |
| Count mismatch → `ARTIFACT_COUNT_MISMATCH` | **PASS** |
| Partial failure preserves valid clip metadata | **PASS** |
| Dry-run `.mock` → COMPLETED | **PASS** |
| Dry-run sha256 stored | **PASS** |
| `operations.validation.passed: true` on dry-run | **PASS** |
| API dry-run dispatch **200** | **PASS** |
| Legacy session status **200** | **PASS** |
| Linter | **PASS** |

---

## Backward Compatibility

| Area | Status |
|------|--------|
| Dry-run seeds / CI | **OK** — `.mock` exempt from size threshold |
| Sync API dispatch | **OK** — validation runs, passes for mocks |
| Worker async path | **OK** — uses same engine hook |
| Legacy sessions without validation block | **OK** — status API unchanged for old data |
| No provider/router/orchestrator edits | **Confirmed** |

---

## Next Recommended Slice: **10J-f — UI Observability**

| Deliverable | Purpose |
|-------------|---------|
| Extend `panel_extractor.extract_provider_runtime()` | Mode, preflight, validation summary |
| `useRuntimeStatusPoll` hook | 5s poll while job active |
| Session drawer | Stale banner, duration, cost telemetry |
| OverviewCards | `runtime_stale_count` |

**Exit gate:** Open RUNNING session → elapsed/heartbeat updates; validation fail shows artifact reject code; stale badge when heartbeat old.

---

*End of Phase 10J-e Implementation Report*
