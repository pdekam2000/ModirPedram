# Phase 11I-8 — Subtitle Runtime Execution API Report

**Status:** COMPLETE  
**Date:** 2026-05-31  
**Scope:** `POST /sessions/{session_id}/subtitle/run` — cue generation + file write + slot update; no FFmpeg, no burn-in

---

## Summary

Phase 11I-8 implements the **Subtitle Runtime Execution API**. A single POST endpoint orchestrates subtitle cue generation (11I-4), format writing (11I-6), artifact validation, session persistence, and `subtitle_generation` slot lifecycle updates. Voice and video runtime slots are preserved unchanged.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/subtitle_run_action_policy.py` | Guard/policy — source ready, no active run, overwrite rules |
| `content_brain/execution/subtitle_runtime_engine.py` | Core orchestrator — cue gen → write → slot update |
| `ui/api/subtitle_run_service.py` | Thin API service wrapper |
| `ui/api/schemas/subtitle_run.py` | Pydantic request/response models |
| `project_brain/validate_11i8_subtitle_runtime_execution_api.py` | 19 automated tests + regressions |
| `project_brain/PHASE_11I8_SUBTITLE_RUNTIME_EXECUTION_API_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `ui/api/main.py` | Added `POST /sessions/{session_id}/subtitle/run` |
| `ui/api/dependencies.py` | Added `get_subtitle_run_service()` |
| `content_brain/execution/subtitle_preflight_runtime_slot.py` | Preserve completed executed subtitle runs on preflight refresh |

**Not modified:** Voice runtime, video runtime, Runway/Hailuo, `engines/subtitle_engine.py`, `pipelines/full_video_pipeline.py`

---

## Endpoint Added

```
POST /sessions/{session_id}/subtitle/run
```

**Request body:**

```json
{
  "formats": ["srt", "ass", "vtt"],
  "timing_strategy": "auto",
  "overwrite": false,
  "language": "auto",
  "triggered_by": "operator",
  "force_retry": false
}
```

**HTTP mapping:**

| Outcome | Status |
|---------|--------|
| Success | `200` |
| Guard/write failure | `409` |
| Session not found | `404` |

**API version:** `0.7.3`

---

## Lifecycle Behavior

```
pending → running → completed | failed | cancelled
```

On success, the `subtitle_generation` slot records:

- `status=completed`, `executed=true`, `provider=local_subtitle_runtime`
- `source_type`, `timing_strategy`, `language`, `cue_count`
- `formats_written`, `artifacts`, `manifest_path`, `validation_status`
- `started_at`, `completed_at`, `duration_seconds`
- `runtime_engine_version=11i8_v1`, `slot_version=11i7_v1`

`artifacts_by_category.subtitle_generation` is updated with file records on completion.

---

## Validation Results

| Command | Result |
|---------|--------|
| `python -m project_brain.validate_11i8_subtitle_runtime_execution_api` | **19/19 PASS** |
| `python -m project_brain.validate_11i6_subtitle_format_writers` | **19/19 PASS** (via regression) |
| `python -m project_brain.validate_11i4_subtitle_cue_generation_engine` | **20/20 PASS** (via regression) |
| `python -m project_brain.validate_11i2_subtitle_runtime_foundation` | **17/17 PASS** (via regression) |
| `python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution` | **17/17 PASS** (via regression) |

---

## Artifact Example Paths

Session: `exec_11i8_narration_text`

```
storage/content_brain/execution/artifacts/exec_11i8_narration_text/subtitle_generation/
├── subtitles.srt
├── subtitles.vtt
├── subtitles.ass
└── subtitle_manifest.json
```

Voice-timing session: `exec_11i8_voice_timing` (uses `audio_duration` strategy)

---

## Safety Confirmations

| Check | Status |
|-------|--------|
| No FFmpeg import or invocation | Confirmed (AST scan) |
| No legacy `subtitle_engine` import | Confirmed |
| No `full_video_pipeline` import | Confirmed |
| Voice slot unchanged after run | Confirmed |
| Video slot unchanged after run | Confirmed |
| Response `video_mutated=false` | Confirmed |
| Response `voice_mutated=false` | Confirmed |
| No subtitle burn-in | Confirmed — sidecar files only |

---

## Architecture

```
POST /subtitle/run
  → SubtitleRunService
    → SubtitleRuntimeEngine
      → evaluate_subtitle_run_request (policy)
      → apply_subtitle_preflight_dry_run
      → SubtitleCueGenerationEngine
      → SubtitleFormatWriter
      → ExecutionSessionStore.save_session
```

---

## Next Recommended Phase

**PHASE 11I-9 — Subtitle Runtime UI Observability Design**

Design UI panel controls and status display for:

- Subtitle slot lifecycle (`pending` / `running` / `completed` / `failed`)
- Artifact list with format badges (SRT, VTT, ASS)
- Run Subtitles action wired to `POST /subtitle/run`
- Manifest excerpt and validation status in Runtime Studio
