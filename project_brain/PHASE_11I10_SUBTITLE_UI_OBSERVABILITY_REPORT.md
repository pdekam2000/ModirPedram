# Phase 11I-10 — Subtitle UI Observability Panel Report

**Status:** COMPLETE  
**Date:** 2026-05-31  
**Scope:** Read-only Subtitle Runtime observability in Execution Center — no FFmpeg, no burn-in, no action buttons

---

## Summary

Phase 11I-10 implements the **SubtitleRuntimeObservabilityPanel** in Execution Center. Operators can view subtitle slot status, source metadata, timing, validation, manifest path, and artifact file paths (SRT / VTT / ASS / manifest) without triggering generation, burn-in, or assembly.

Voice and video observability sections remain unchanged.

---

## Files Changed

### Created

| File | Purpose |
|------|---------|
| `ui/web/src/components/SubtitleRuntimeObservabilityPanel.tsx` | Dedicated read-only subtitle panel |
| `ui/web/src/utils/subtitleRuntimeObservability.ts` | Resolver, status labels, artifact rows, safety copy |
| `project_brain/validate_11i10_subtitle_ui_observability.py` | 19 automated checks |
| `project_brain/PHASE_11I10_SUBTITLE_UI_OBSERVABILITY_REPORT.md` | This report |

### Modified

| File | Change |
|------|--------|
| `ui/web/src/components/RuntimeObservability.tsx` | Mount subtitle panel below voice panel |
| `ui/web/src/utils/categoryRuntimeShell.ts` | Subtitle slot TypeScript fields; canonical placeholder key |
| `ui/web/src/components/CategoryRuntimeSlotsPanel.tsx` | Updated media categories note |
| `ui/web/src/App.css` | `.subtitle-runtime-observability` styles |

**Not modified:** Voice runtime execution, video runtime, Runway/Hailuo, legacy pipeline, backend API (existing `category_runtime_slots` sufficient).

---

## UI Fields Added

| Field | Source |
|-------|--------|
| Status + badge | `status` → mapped labels |
| Provider | `provider` |
| Source type | `source_type` / preflight |
| Source ready | `source_ready` |
| Timing strategy | `timing_strategy` |
| Cue count | `cue_count` |
| Formats written | `formats_written` |
| Validation status | `validation_status` |
| Manifest path | `manifest_path` |
| Artifacts | `subtitles.srt`, `subtitles.vtt`, `subtitles.ass`, `subtitle_manifest.json` |
| Started / Completed | `started_at`, `completed_at` |
| Duration | `duration_seconds` |
| Runtime notes | `runtime_notes[]` |
| Error code / message | `error.code`, `error.message` |

### Status badge mapping

| Status | Label |
|--------|-------|
| `planned` | Not started |
| `pending` | Ready |
| `running` | Generating subtitles |
| `completed` | Subtitles ready |
| `failed` | Failed |
| `skipped` | No subtitle source |
| `cancelled` | Cancelled |

---

## Safety Copy

Permanent banner (exact text):

> **Subtitle files only — no video burn-in yet.**

No buttons for FFmpeg, burn-in, Assembly, Send to Assembly, or Run Subtitles.

---

## Validation Results

| Command | Result |
|---------|--------|
| `python -m project_brain.validate_11i10_subtitle_ui_observability` | **19/19 PASS** |
| `python -m project_brain.validate_11i8_subtitle_runtime_execution_api` | **19/19 PASS** (regression) |
| `python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution` | **17/17 PASS** (regression) |
| `npm run build` | **PASS** |

---

## Safety Confirmations

| Check | Status |
|-------|--------|
| No FFmpeg controls | Confirmed |
| No burn-in controls | Confirmed |
| No Assembly controls | Confirmed |
| Voice observability unchanged | Confirmed |
| Video clip artifacts section unchanged | Confirmed |
| Legacy `subtitles` alias → `subtitle_generation` | Confirmed |
| Missing fields render `—` | Confirmed |

---

## Placement

```
RuntimeObservabilityPanel
  ├── CategoryRuntimeSlotsPanel
  ├── VoiceRuntimeObservabilityPanel
  ├── SubtitleRuntimeObservabilityPanel   ← NEW
  └── Clip artifacts (video)
```

---

## Next Recommended Phase

**PHASE 11I-11 — Subtitle Runtime UI Actions Design**

Design (only) operator controls for:

- Run subtitles (`POST /subtitle/run`)
- Regenerate with overwrite confirmation
- Download SRT/VTT/ASS
- Future Assembly handoff

No implementation until explicit approval after design review.
