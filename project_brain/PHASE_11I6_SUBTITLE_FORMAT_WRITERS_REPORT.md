# Phase 11I-6 — Subtitle Format Writers Report

**Status:** COMPLETE  
**Date:** 2026-05-31  
**Scope:** Write SRT / VTT / ASS sidecar files + `subtitle_manifest.json` from in-memory `SubtitleCueBatch` — no FFmpeg, no burn-in

---

## Summary

Phase 11I-6 implements **Subtitle Format Writers** for the Content Brain subtitle runtime. The writer accepts a validated `SubtitleCueBatch` and `session_id`, renders selected formats, writes artifacts under the standard execution artifact tree, validates output with `SubtitleArtifactValidator`, and returns a structured `SubtitleWriteResult`.

Voice Runtime, Video Runtime, Runway/Hailuo, legacy `engines/subtitle_engine.py`, and `pipelines/full_video_pipeline.py` were **not modified**.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/subtitle_format_writer.py` | SRT / VTT / ASS renderers, atomic write, manifest builder, `SubtitleFormatWriter` |
| `project_brain/validate_11i6_subtitle_format_writers.py` | 19 automated tests + regressions |
| `project_brain/PHASE_11I6_SUBTITLE_FORMAT_WRITERS_REPORT.md` | This report |

**Reads (unchanged):** `subtitle_models.py`, `subtitle_cue_validator.py`, `subtitle_artifact_validator.py`, `session_store.py`, `category_runtime_compat.py`

---

## Formats Implemented

| Format | Filename | Timestamp format | Notes |
|--------|----------|------------------|-------|
| **SRT** | `subtitles.srt` | `HH:MM:SS,mmm --> HH:MM:SS,mmm` | Numbered cue blocks |
| **VTT** | `subtitles.vtt` | `HH:MM:SS.mmm --> HH:MM:SS.mmm` | `WEBVTT` header |
| **ASS** | `subtitles.ass` | `H:MM:SS.cc` (centiseconds) | Script Info, V4+ Styles, Dialogue events |

### ASS styling

- **Default:** Lower-third readable style (Arial 72, white text, outline, alignment 2, margin 220)
- **Emphasis:** Inline overrides from `cue.highlight_terms` only — no hardcoded niche words
- Fade-in/out via `{\fad(80,80)}` on each Dialogue line

### Write behavior

- Output directory: `storage/content_brain/execution/artifacts/{session_id}/subtitle_generation/`
- Atomic write: `.tmp.{pid}` + `Path.replace()`
- `overwrite=False` by default — existing files return `FILE_EXISTS`
- `overwrite=True` allows controlled rewrite
- Post-write validation failure triggers rollback (delete written files)
- Reject codes: `SESSION_ID_REQUIRED`, `CUE_BATCH_INVALID`, `UNSUPPORTED_FORMAT`, `FILE_EXISTS`, `WRITE_FAILED`, `ARTIFACT_VALIDATION_FAILED`

---

## Manifest Schema (`subtitle_manifest.json`)

| Field | Type | Description |
|-------|------|-------------|
| `manifest_version` | string | `11i_v1` |
| `writer_version` | string | `11i6_v1` |
| `session_id` | string | Execution session ID |
| `category` | string | `subtitle_generation` |
| `provider` | string | `local_subtitle_runtime` |
| `provider_mode` | string | `local` |
| `source_type` | string | From batch (e.g. `narration_text_only`) |
| `timing_strategy` | string | From batch (e.g. `equal_chunk`) |
| `language` | string | From batch (e.g. `en`) |
| `cue_count` | int | Number of cues written |
| `segment_count` | int \| null | From batch metadata |
| `formats_written` | string[] | e.g. `["srt", "ass", "vtt"]` |
| `format_list` | string[] | Alias of `formats_written` |
| `files` | object[] | Per-file records (format, path, size, cue_count, validation_status) |
| `total_duration_seconds` | float | Batch total duration |
| `total_duration` | float | Alias of `total_duration_seconds` |
| `validation_status` | string | `valid` / `pending` / `invalid` |
| `generated_at` | string | Write timestamp |
| `batch_version` | string | From cue batch |
| `voice_manifest_ref` | string \| null | Optional request ref |
| `narration_source_path` | string \| null | Optional request ref |
| `execution_status` | string | `completed` |
| `partial` | bool | `false` for full write |
| `real_provider_called` | bool | Always `false` |
| `artifact_dir` | string | Absolute artifact directory |
| `warnings` | string[] | Propagated from batch |

---

## Validation Results

| Validator | Result |
|-----------|--------|
| `python -m project_brain.validate_11i6_subtitle_format_writers` | **19/19 PASS** |
| `python -m project_brain.validate_11i4_subtitle_cue_generation_engine` | **20/20 PASS** |
| `python -m project_brain.validate_11i2_subtitle_runtime_foundation` | **17/17 PASS** |
| `python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution` | **17/17 PASS** |

### 11I-6 test coverage

1. Writes SRT file  
2. SRT timestamp format correct  
3. Writes VTT file  
4. VTT has WEBVTT header  
5. Writes ASS file  
6. ASS has Dialogue lines  
7. Writes `subtitle_manifest.json`  
8. Manifest `cue_count` matches batch  
9. Unsupported format fails safely (`UNSUPPORTED_FORMAT`)  
10. `overwrite=False` blocks existing files (`FILE_EXISTS`)  
11. `overwrite=True` allows controlled rewrite  
12. Post-write `SubtitleArtifactValidator` passes  
13. No FFmpeg import/call  
14. No legacy `subtitle_engine` import  
15. Voice slot unchanged  
16. Video slot unchanged  
17. 11I-4 regression  
18. 11I-2 regression  
19. 11H-2d regression  

---

## Artifact Example Paths

Session: `exec_11i6_format_writers`

```
storage/content_brain/execution/artifacts/exec_11i6_format_writers/subtitle_generation/
├── subtitles.srt
├── subtitles.vtt
├── subtitles.ass
└── subtitle_manifest.json
```

Example manifest excerpt:

```json
{
  "writer_version": "11i6_v1",
  "session_id": "exec_11i6_format_writers",
  "category": "subtitle_generation",
  "source_type": "narration_text_only",
  "timing_strategy": "equal_chunk",
  "language": "en",
  "cue_count": 2,
  "formats_written": ["srt", "ass", "vtt"],
  "validation_status": "valid",
  "total_duration": 15.0
}
```

---

## Safety Confirmations

| Check | Status |
|-------|--------|
| No FFmpeg import or invocation | Confirmed (AST scan in validator) |
| No legacy `subtitle_engine` import | Confirmed |
| Voice runtime slot unchanged after write | Confirmed |
| Video runtime slot unchanged after write | Confirmed |
| No subtitle burn-in | Confirmed — sidecar files only |
| No voice/video runtime execution modified | Confirmed |

---

## Architecture Notes

```
SubtitleCueBatch (11I-4)
        │
        ▼
SubtitleFormatWriter.write()
        ├── SubtitleCueValidator (pre-write)
        ├── render_srt / render_vtt / render_ass
        ├── atomic_write_text (per file)
        ├── subtitle_manifest.json
        └── SubtitleArtifactValidator (post-write)
                │
                ▼
        SubtitleWriteResult
```

The writer is intentionally isolated from execution orchestration. It does not update session JSON on disk or mutate `category_runtime` slots — artifact persistence only.

---

## Next Recommended Phase

**PHASE 11I-7 — Subtitle Runtime Execution API Design**

Design the orchestration layer that wires:

- Preflight (11I-2) → Cue generation (11I-4) → Format write (11I-6)
- Session artifact registration and runtime slot status updates
- Approval / execution entry points for Content Brain subtitle runs
- API contract for UI and pipeline consumers

Implementation of the execution API should remain separate from this phase’s file-only writer.
