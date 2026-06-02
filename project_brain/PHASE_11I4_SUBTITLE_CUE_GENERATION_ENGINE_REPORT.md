# Phase 11I-4 — Subtitle Cue Generation Engine V1 Report

**Status:** COMPLETE  
**Date:** 2026-05-28  
**Scope:** In-memory cue generation only — no subtitle files, no FFmpeg

---

## Summary

Phase 11I-4 implements the Content Brain **Subtitle Cue Generation Engine V1**. The engine reads execution session narration (and optional voice manifest timing), produces a validated `SubtitleCueBatch` in memory, and does not write SRT/ASS/VTT files or modify voice/video runtime slots.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/subtitle_models.py` | `SubtitleCue`, `SubtitleCueBatch`, enums |
| `content_brain/execution/subtitle_text_normalizer.py` | Text normalization and cue line splitting |
| `content_brain/execution/subtitle_highlight_terms.py` | Dynamic highlight term resolution |
| `content_brain/execution/subtitle_cue_validator.py` | In-memory cue batch validation |
| `content_brain/execution/subtitle_cue_generation_engine.py` | Main orchestrator |
| `project_brain/validate_11i4_subtitle_cue_generation_engine.py` | 20 automated tests |
| `project_brain/PHASE_11I4_SUBTITLE_CUE_GENERATION_ENGINE_REPORT.md` | This report |

**Not modified:** Voice Runtime, Video Runtime, Runway/Hailuo, legacy pipeline, `engines/subtitle_engine.py`, 11I-2 foundation modules (except read-only imports from preflight).

---

## Cue Model Summary

### `SubtitleCue`

| Field | Description |
|-------|-------------|
| `index` | 1-based cue index |
| `start_time` / `end_time` | Seconds (float, 3 decimal places in JSON) |
| `text` | Normalized display line |
| `source_segment_id` | e.g. `beat_HOOK`, `segment_1` |
| `confidence` | 0.6 (L1) or 0.85 (L2) |
| `highlight_terms` | Dynamic per-cue emphasis tokens |
| `style_tags` | `["default"]` for future ASS mapping |

### `SubtitleCueBatch`

| Field | Description |
|-------|-------------|
| `cues` | Ordered list of `SubtitleCue` |
| `language` | From profile or brief (default `en`) |
| `source_type` | `narration_text_only` / `narration_with_timing` |
| `timing_strategy` | `equal_chunk` / `audio_duration` |
| `total_duration` | Last cue end time |
| `warnings` | e.g. `TIMING_ESTIMATED_EQUAL_CHUNK` |
| `metadata` | segment_count, highlight sources, quality_level |

Enums: `SubtitleSourceType`, `SubtitleTimingStrategy` (`word_level`, `karaoke` reserved).

---

## Timing Strategies Implemented

### A. `equal_chunk` (Level 1)

- Used when no voice manifest segment durations are available
- Total duration from: voice manifest total → brief `default_duration_seconds` → text estimate (~2.8 words/sec)
- Segment windows allocated by character weight
- Cue lines split via text normalizer; time distributed by word count within each window
- Short final cues merged into previous cue to satisfy min duration (0.8s)

### B. `audio_duration` (Level 2)

- Auto-selected when voice slot is `completed` and manifest has per-file `duration_seconds` (or splittable total)
- Segments chained sequentially: segment N starts where N-1 ends
- Cue timing distributed within each segment duration

**Not implemented (by design):** `word_level`, `karaoke` — reserved for 11I-6+.

---

## Highlight Strategy

Priority order (no fixed niche lists):

1. `channel_identity.highlight_keywords`
2. `profile.highlight_keywords` / `subtitle_rules.highlight_keywords`
3. `profile.seo_keywords` / `seo_rules`
4. Brief topic / title / semantic universe tokens
5. Narration-derived frequent tokens (stop-word filtered)
6. Neutral fallback: `secret`, `hidden`, `important`, `never`, `always`, `stop`, `watch`

Per cue: up to 3 terms that appear as substrings in cue text.

Default sessions with football/topic narration derive terms from **brief/topic/narration** — not skincare defaults.

---

## Text Normalization

- Default max line length: **42** (profile `subtitle_rules.max_line_length`)
- Sentence-first split → clause split → word wrap
- Whitespace collapsed; short fragments merged
- No niche-specific assumptions

---

## Cue Validation

`SubtitleCueValidator` checks:

- Non-empty cue text
- `start_time >= 0`, `end_time > start_time`
- Ordered, non-overlapping cues
- Min duration 0.5s (reject), max 8.0s (warn)
- Sequential indices 1..N
- Highlight terms contained in cue text (warn + strip invalid)

---

## Validation Results

```bash
python -m project_brain.validate_11i4_subtitle_cue_generation_engine   # 20/20 PASS
python -m project_brain.validate_11i2_subtitle_runtime_foundation     # 17/17 PASS
python -m project_brain.validate_11i2b_hardcoded_niche_fixes            # 12/12 PASS
python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution  # 17/17 PASS
```

### 11I-4 test matrix (20 tests)

| # | Test | Result |
|---|------|--------|
| 1 | Generates cues from narration text | PASS |
| 2 | Ordered timestamps | PASS |
| 3 | Non-empty cue text | PASS |
| 4 | Long narration → multiple cues | PASS |
| 5 | `equal_chunk` without audio | PASS |
| 6 | `audio_duration` with manifest | PASS |
| 7 | No skincare highlight defaults | PASS |
| 8 | Dynamic highlight sources | PASS |
| 9 | Custom profile `highlight_keywords` | PASS |
| 10 | Profile keywords on cues | PASS |
| 11 | Validator rejects negative timestamps | PASS |
| 12 | Validator rejects empty text | PASS |
| 13 | No subtitle files written | PASS |
| 14 | No FFmpeg | PASS |
| 15 | No legacy `subtitle_engine` import | PASS |
| 16 | Voice slot unchanged | PASS |
| 17 | Video slot unchanged | PASS |
| 18 | 11I-2 regression | PASS |
| 19 | 11I-2B regression | PASS |
| 20 | 11H-2d regression | PASS |

---

## Confirmations

| Constraint | Status |
|------------|--------|
| No subtitle files written | Confirmed — engine is in-memory only |
| No FFmpeg | Confirmed — AST scan of all new modules |
| No legacy `subtitle_engine` import | Confirmed |
| Voice runtime unchanged | Confirmed — slot byte-identical after generate |
| Video runtime unchanged | Confirmed — slot byte-identical after generate |

---

## Engine API (usage)

```python
from content_brain.execution.subtitle_cue_generation_engine import (
    SubtitleCueGenerationEngine,
    SubtitleCueGenerationRequest,
)

engine = SubtitleCueGenerationEngine(project_root=".")
result = engine.generate(SubtitleCueGenerationRequest(session=session, profile=profile))
if result.passed:
    batch = result.batch  # SubtitleCueBatch — JSON via batch.to_dict()
```

---

## Next Recommended Phase

**PHASE 11I-5 — Subtitle Format Writers Design**

Design-only deliverable for:

- `SubtitleFormatWriter` — SRT / ASS / VTT from `SubtitleCueBatch`
- ASS highlight styling using dynamic `highlight_terms` (not legacy word lists)
- `subtitle_manifest.json` schema finalization
- Integration hook in future `SubtitleRuntimeEngine` (11I-6)

**Do not implement file writers until 11I-5 design approval.**
