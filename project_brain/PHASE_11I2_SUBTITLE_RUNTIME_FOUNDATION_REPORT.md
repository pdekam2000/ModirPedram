# Phase 11I-2 — Subtitle Runtime Foundation Report

**Status:** COMPLETE  
**Date:** 2026-05-28  
**Scope:** Foundation only — no subtitle generation, no FFmpeg, no voice/video runtime changes

---

## Summary

Phase 11I-2 implements the Subtitle Runtime foundation layer: category aliasing (`subtitles` ↔ `subtitle_generation`), slot schema, dry-run preflight, artifact validator skeleton, artifact path conventions, and panel exposure via existing `build_category_runtime_view`. No subtitle files are generated and no FFmpeg is invoked.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/subtitle_preflight_runtime_slot.py` | Dry-run preflight — source resolution, slot metadata only |
| `content_brain/execution/subtitle_artifact_validator.py` | Skeleton validator for `.srt` / `.ass` / `.vtt` artifacts |
| `project_brain/validate_11i2_subtitle_runtime_foundation.py` | 17 automated foundation tests (15 required + 2 panel/regression helpers) |
| `project_brain/PHASE_11I2_SUBTITLE_RUNTIME_FOUNDATION_REPORT.md` | This report |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/provider_categories.py` | Added `CATEGORY_SUBTITLE_GENERATION`, alias constants, `local_subtitle_runtime` provider default |
| `content_brain/execution/category_runtime_compat.py` | Subtitle slot schema, alias sync, panel view key mapping, preflight router hook |

**Not modified (per constraints):** Voice Runtime, Video Runtime, Runway/Hailuo paths, `full_video_pipeline.py`, UI components (generic panel picks up slots automatically).

---

## Alias Behavior

| Key | Role |
|-----|------|
| `subtitles` | Legacy 11G storage key — preserved in `MEDIA_CATEGORIES` for backward compatibility |
| `subtitle_generation` | Canonical 11I key — exposed in API/panel `category_key` |

`sync_subtitle_category_aliases()` merges legacy and canonical slots into **one shared dict object** — no conflicting duplicates.

- `get_category_slot(session, "subtitles")` and `get_category_slot(session, "subtitle_generation")` return the same normalized slot.
- Legacy sessions with only `subtitles` are migrated on read/ensure.
- New sessions from `ensure_multi_category_shell()` expose both keys pointing to the same slot.

---

## Slot Schema

Canonical subtitle slot fields (11I-2):

```json
{
  "category_name": "subtitle_generation",
  "status": "planned | pending | skipped | failed",
  "provider": "local_subtitle_runtime",
  "source_type": null,
  "source_ready": false,
  "supported_formats": ["srt", "ass", "vtt"],
  "artifacts": [],
  "validation_status": null,
  "runtime_notes": [],
  "error": null,
  "created_at": null,
  "updated_at": null,
  "subtitle_preflight": null,
  "slot_version": "11i2_v1"
}
```

**Artifact path convention:** `storage/content_brain/execution/artifacts/{session_id}/subtitle_generation/`  
(constant: `SUBTITLE_ARTIFACT_CATEGORY`)

---

## Preflight Behavior

`apply_subtitle_preflight_dry_run(session, execution_runtime)`:

1. Checks `voice_generation` status (read-only).
2. Resolves subtitle source via `SessionNarrationAdapter` and optional `voice_manifest.json`.
3. Sets `source_type`:

   | Condition | `source_type` | `status` | `source_ready` |
   |-----------|---------------|----------|----------------|
   | Voice completed + manifest with timing/files | `narration_with_timing` | `pending` | `true` |
   | Narration segments available | `narration_text_only` | `pending` | `true` |
   | Neither | `unavailable` | `skipped` | `false` |

4. Records `subtitle_preflight` summary and `operations.subtitle_preflight_dry_run`.
5. **Does not** write subtitle files, call FFmpeg, or modify voice/video slots.

---

## Validator Skeleton

`SubtitleArtifactValidator.validate(artifacts)` checks:

- File path present and file exists
- Extension in `.srt`, `.ass`, `.vtt`
- Non-empty file (min 1 byte)
- Placeholder cue/timestamp structure (SRT `-->` timestamps, VTT `WEBVTT` + cues, ASS `Dialogue:` events)

No FFmpeg dependency.

---

## Panel Exposure

`build_category_runtime_view()` maps internal `subtitles` storage to `category_key: subtitle_generation` in the ordered slot list. `PanelExtractor` already consumes this view — no UI file changes required.

---

## Validation Results

```bash
python -m project_brain.validate_11i2_subtitle_runtime_foundation   # 17/17 PASS
python -m project_brain.validate_11g_multi_category_runtime_shell # 20/20 PASS
python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution  # 17/17 PASS
```

### 11I-2 test matrix

| # | Test | Result |
|---|------|--------|
| 1 | Legacy `subtitles` aliases to `subtitle_generation` | PASS |
| 2 | New sessions expose `subtitle_generation` | PASS |
| 3 | No source → subtitle slot skipped | PASS |
| 4 | Narration text → pending / `narration_text_only` | PASS |
| 5 | Voice manifest → pending / `narration_with_timing` | PASS |
| 6 | Supported formats srt/ass/vtt | PASS |
| 7 | Validator passes non-empty fake `.srt` | PASS |
| 8 | Validator fails missing file | PASS |
| 9 | Validator fails unsupported extension | PASS |
| 10 | Preflight generates no subtitle files | PASS |
| 11 | No FFmpeg import/call in subtitle modules | PASS |
| 12 | Voice slot unchanged | PASS |
| 13 | Video slot unchanged | PASS |
| 14 | 11G validator regression | PASS |
| 15 | 11H-2d validator regression | PASS |

---

## Confirmations

| Constraint | Status |
|------------|--------|
| No FFmpeg | Confirmed — AST scan of new modules; docstrings only mention FFmpeg as exclusion |
| No subtitle generation | Confirmed — preflight metadata only; zero artifact files written |
| Voice runtime unchanged | Confirmed — voice slot byte-identical before/after preflight |
| Video runtime unchanged | Confirmed — video slot byte-identical before/after preflight |

---

## Next Recommended Phase

**PHASE 11I-3 — Subtitle Cue Generation Engine Design**

Design-only deliverable covering:

- Cue generation algorithm for `narration_text_only` (Level 1) and `narration_with_timing` (Level 2)
- SRT/ASS/WebVTT writer interfaces
- Segment → cue mapping rules
- Integration point with `apply_subtitle_preflight_dry_run` → future execution engine
- No implementation until 11I-3 design approval
