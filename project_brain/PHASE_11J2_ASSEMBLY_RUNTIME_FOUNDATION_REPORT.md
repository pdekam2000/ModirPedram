# Phase 11J-2 — Assembly Runtime Foundation Implementation Report

**Status:** Implemented — foundation only (no FFmpeg, no assembly execution, no `FINAL_PUBLISH_READY.mp4`)
**Date:** 2026-05-31
**Prerequisites:** 11G shell, Voice Runtime (11H), Subtitle Runtime (11I-2→11I-10), 11J-1 design
**Next phase:** **11J-3 — Assembly Plan Builder Design**

---

## Executive Summary

Phase 11J-2 lands the **Assembly Runtime foundation** — category support, alias
sync, slot schema, pure data models, a read-only artifact validator skeleton, and
a dry-run preflight that updates **only** the `assembly_generation` slot.

No media is processed. No FFmpeg is imported or invoked. No video/voice/subtitle
runtime execution is touched. The legacy `pipelines/full_video_pipeline.py` is not
imported.

The foundation mirrors the proven subtitle runtime pattern
(`subtitles ↔ subtitle_generation`) exactly, so the new category integrates with
the existing multi-category shell, panel, and runtime view without parallel
architecture.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/assembly_models.py` | `AssemblyInputArtifact`, `AssemblyPlan`, `AssemblyValidationResult`, `AssemblyManifestSkeleton` + mode/subtitle/role/validation constants |
| `content_brain/execution/assembly_artifact_validator.py` | `AssemblyArtifactValidator` — read-only existence checks → READY/PARTIAL/FAILED (no FFmpeg, no probing) |
| `content_brain/execution/assembly_preflight_runtime_slot.py` | `apply_assembly_preflight_dry_run()` — dry-run slot wiring, updates only `assembly_generation` |
| `project_brain/validate_11j2_assembly_runtime_foundation.py` | 15-test validator + 3 regressions |
| `project_brain/PHASE_11J2_ASSEMBLY_RUNTIME_FOUNDATION_REPORT.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `content_brain/execution/provider_categories.py` | Added `CATEGORY_ASSEMBLY_GENERATION`, `ASSEMBLY_CANONICAL_CATEGORY`, `ASSEMBLY_LEGACY_CATEGORY`, `ASSEMBLY_CATEGORY_ALIASES`; registry map + `local_assembly_runtime` planned provider; exports |
| `content_brain/execution/category_runtime_compat.py` | Added assembly constants, `is_assembly_category_key`, `default_assembly_category_slot`, `sync_assembly_category_aliases`; wired assembly into `default_category_runtime_slots`, `normalize_category_slot`, `normalize_category_runtime`, `get_category_slot`, `ensure_multi_category_shell`, `build_category_runtime_view`, short names, future routers, exports |

> No UI files and no panel extractor changes were required — `PanelExtractor`
> consumes `build_category_runtime_view`, which now emits the canonical
> `assembly_generation` key automatically.

---

## Category / Alias Behavior

Mirrors the subtitle `subtitles ↔ subtitle_generation` pattern.

| Key | Role |
|-----|------|
| `assembly` | Legacy 11G storage key — preserved for backward compatibility |
| `assembly_generation` | **Canonical key** — exposed in runtime view / panel `category_key` |

- `MEDIA_CATEGORIES` is **unchanged** (still 5 entries; `assembly` remains the
  storage member). `assembly_generation` is exposed as the canonical alias in the
  view — it is **not** a 6th media category, so 11G's `default_slots_count == 5`
  and `media_categories_defined` assertions still hold.
- `sync_assembly_category_aliases()` merges legacy + canonical into one shared dict
  object (no conflicting duplicate slots).
- Legacy sessions with only an `assembly` slot map safely to `assembly_generation`
  via `get_category_slot()` / `normalize_category_runtime()` — no crash.
- New sessions expose `assembly_generation` in both `category_runtime` and the
  runtime view.

---

## Slot Schema (`assembly_generation`)

```json
{
  "category_name": "assembly_generation",
  "status": "planned",
  "provider": "local_assembly_runtime",
  "validation_status": null,
  "input_summary": null,
  "output_summary": null,
  "assembly_mode": null,
  "subtitle_mode": null,
  "artifacts": [],
  "manifest_path": null,
  "runtime_notes": [],
  "error": null,
  "created_at": null,
  "updated_at": null,
  "executed": false,
  "dry_run": true,
  "assembly_preflight": null,
  "slot_version": "11j2_v1"
}
```

Provider constant: `ASSEMBLY_PROVIDER = "local_assembly_runtime"`.
Artifact category: `ASSEMBLY_ARTIFACT_CATEGORY = "assembly_generation"`.

---

## Models (`assembly_models.py`)

- **`AssemblyInputArtifact`** — `category`, `file_path`, `role`, `exists`,
  `file_name`, `is_manifest` (+ `to_dict()`).
- **`AssemblyPlan`** — `session_id`, `video_inputs`, `audio_inputs`,
  `subtitle_inputs`, `assembly_mode`, `subtitle_mode`, `expected_output`,
  `output_dir`, `validation_status`, `warnings`, `plan_version` (+ `to_dict()`).
  Pure data — the future FFmpeg executor (11J-4) operates exclusively from this.
- **`AssemblyValidationResult`** — `status` (READY/PARTIAL/FAILED), `video_ok`,
  `voice_ok`, `subtitle_ok`, counts, `missing`, `warnings`, `reject_reasons`.
- **`AssemblyManifestSkeleton`** — in-memory `assembly_manifest.json` skeleton
  (matching the 11J-1 manifest schema). **Not written to disk in this phase.**

Modes reserved (design only): `video_voice_subtitle` (V1 target), `video_voice`,
`video_only`, `voice_only`, `multi_language_audio`, `multi_subtitle_track`.
Subtitle modes reserved: `burn_in` (V1 target), `sidecar`, `none`.

---

## Artifact Validator Skeleton

`AssemblyArtifactValidator.validate()` performs **read-only** checks only:

- ≥1 video artifact exists on disk **and** video manifest (if a path is listed) exists.
- ≥1 voice artifact exists **and** voice manifest (if listed) exists.
- ≥1 subtitle artifact (`.srt/.vtt/.ass`) exists **and** subtitle manifest (if listed) exists.

Result mapping:

| Result | Condition |
|--------|-----------|
| `READY` | All required categories valid for the chosen mode (default requires video+voice+subtitle) |
| `PARTIAL` | Video base present, but voice/subtitle (or their manifests) incomplete |
| `FAILED` | No usable video, or video manifest listed-but-missing, or no inputs at all |

No FFmpeg, no `subprocess`, no media decoding — only `Path.is_file()`.

---

## Preflight Behavior (`apply_assembly_preflight_dry_run`)

1. Reads `video_generation`, `voice_generation`, `subtitle_generation` slots and
   `artifacts_by_category` (read-only).
2. Resolves upstream artifacts + manifest paths and runs the validator.
3. Builds `input_summary` (per-category counts + ok flags + `missing`).
4. Maps validation → slot status:
   - `READY` → status `pending` (ready to assemble)
   - `PARTIAL` → status `skipped` (`validation_status: PARTIAL`)
   - `FAILED` → status `skipped` (`validation_status: FAILED`)
5. Writes **only** the `assembly_generation` (+ legacy `assembly` alias) slot and a
   read-only `operations.assembly_preflight_dry_run` summary.
6. Preserves a completed/executed assembly run if one already exists.
7. `executed=false`, `dry_run=true`. No media processing.

Video, voice, and subtitle slot objects are re-assigned by identity from their
pre-evaluation snapshots — never mutated.

---

## Validation Results

Command:

```
python -m project_brain.validate_11j2_assembly_runtime_foundation
```

| # | Test | Result |
|---|------|--------|
| 1 | New sessions expose `assembly_generation` | PASS |
| 2 | Legacy `assembly` alias maps to `assembly_generation` | PASS |
| 3 | No inputs → slot skipped + validation FAILED, no crash | PASS |
| 4 | Video + voice + subtitle → validation READY (status pending) | PASS |
| 5 | Missing one input group → validation PARTIAL | PASS |
| 6 | Missing manifests → PARTIAL (voice) / FAILED (video) | PASS |
| 7 | Preflight updates only `assembly_generation` | PASS |
| 8 | Video slot unchanged | PASS |
| 9 | Voice slot unchanged | PASS |
| 10 | Subtitle slot unchanged | PASS |
| 11 | No FFmpeg import/call | PASS |
| 12 | No `full_video_pipeline` import | PASS |
| 13 | Existing 11G validator still passes | PASS |
| 14 | Existing 11I-8 validator still passes | PASS |
| 15 | Existing 11H-2d validator still passes | PASS |
| + | Models serialize correctly | PASS |

Core foundation logic (tests 1–12 + models) verified directly:

```
view_keys: video_generation, voice_generation, music_generation, subtitle_generation, assembly_generation
empty   -> skipped / FAILED
ready   -> pending / READY
partial -> skipped / PARTIAL   (subtitle missing)
novoice-manifest -> skipped / PARTIAL
novideo-manifest -> skipped / FAILED
video unchanged: True | voice unchanged: True | subtitle unchanged: True
```

Regression commands (all PASS):

```
python -m project_brain.validate_11g_multi_category_runtime_shell          # 20/20 PASS
python -m project_brain.validate_11i8_subtitle_runtime_execution_api        # PASS
python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution # PASS
```

> Note: `validate_11i8` runs a deep chain of nested regression validators and can
> take several minutes; this is pre-existing behavior unchanged by this phase.

---

## Safety Confirmations

- **No FFmpeg.** None of `assembly_models.py`, `assembly_artifact_validator.py`,
  or `assembly_preflight_runtime_slot.py` import or invoke FFmpeg (AST + text scan
  enforced by test 11).
- **No `FINAL_PUBLISH_READY.mp4` generation.** The expected output name appears
  only as a string constant in models/manifest skeleton; no file is written.
- **No subtitle burning, no media processing.** Validator uses `Path.is_file()`
  only.
- **Video / Voice / Subtitle runtimes unchanged.** No execution modules modified;
  preflight isolation enforced by deep-copy comparison (tests 7–10).
- **No legacy pipeline import.** `full_video_pipeline` is banned in the new modules
  (test 12).
- **No Runway/Hailuo changes.**

---

## Next Phase

**PHASE 11J-3 — Assembly Plan Builder Design**

Design `assembly_plan_builder.py` to build a concrete `AssemblyPlan` from a session
(in-memory, no FFmpeg), plus `assembly_run_action_policy` guard design — following
the 11I cadence (design → implement → validate → report).
