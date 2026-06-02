# Phase 11J-4 — Assembly Plan Builder Implementation Report

**Status:** Implemented — pure planning layer (no FFmpeg, no assembly execution, no `FINAL_PUBLISH_READY.mp4`)
**Date:** 2026-05-31
**Prerequisites:** 11J-1 (architecture), 11J-2 (foundation), 11J-3 (plan builder design)
**Next phase:** **11J-5 — Assembly FFmpeg Executor Design**

---

## Executive Summary

Phase 11J-4 implements the **`AssemblyPlanBuilder`** — the planning layer between
`video_generation` / `voice_generation` / `subtitle_generation` and the future
FFmpeg executor.

`build(session) -> AssemblyPlan` reads existing artifacts and manifests (read-only),
selects inputs deterministically, resolves assembly/subtitle modes, runs the 11J-2
`AssemblyArtifactValidator`, and returns a pure-data `AssemblyPlan`.

No media is processed. No FFmpeg is imported or invoked. No final video is written.
Upstream slots are never mutated. The legacy `full_video_pipeline.py` is not imported.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/assembly_plan_builder.py` | `AssemblyPlanBuilder.build(session) -> AssemblyPlan` (pure planning) |
| `project_brain/validate_11j4_assembly_plan_builder.py` | 19-test validator (16 builder + 3 regressions) |
| `project_brain/PHASE_11J4_ASSEMBLY_PLAN_BUILDER_REPORT.md` | This report |

## Files Modified

| File | Change (additive only) |
|------|------------------------|
| `content_brain/execution/assembly_models.py` | Added future-safe fields to `AssemblyPlan` (`output_variant`, `output_targets`, `music_inputs`, `music_mode`, `language`) and `AssemblyInputArtifact` (`language`); added `ROLE_MUSIC`, `OUTPUT_VARIANT_*`, `MUSIC_MODE_*` constants + exports. All defaults are backward-compatible (existing `to_dict` keys preserved). |

---

## Planning Behavior

`build()` is a pure, deterministic function over a session:

1. Resolve `video_generation`, `voice_generation`, `subtitle_generation` slots via
   `get_category_slot` (read-only) + `artifacts_by_category`.
2. Select + order + dedupe input artifacts (rules below).
3. Read upstream manifests (read-only JSON) for ordering/validation.
4. Run `AssemblyArtifactValidator` → `READY` / `PARTIAL` / `FAILED`.
5. Resolve `assembly_mode` + `subtitle_mode`.
6. Plan output (`output_dir`, `expected_output`) — **no directory or file creation**.
7. Collect warnings; return `AssemblyPlan`.

`build()` never raises on missing/partial data — it degrades to `PARTIAL`/`FAILED`
with descriptive `warnings`.

---

## Input Selection Rules

| Group | Source | Filter | Order | Dedupe |
|-------|--------|--------|-------|--------|
| **Video** | `artifacts_by_category.video_generation` + slot artifacts | video extensions (`.mp4/.mov/.mkv/.webm`) that exist | by clip index parsed from filename (`clip_001` < `clip_010`) | by resolved absolute path |
| **Voice** | `voice_manifest.json` `files[]` (authoritative), then raw artifacts | audio extensions (`.mp3/.wav/...`) | by `segment_index`, then `beat_id` | by resolved absolute path |
| **Subtitle** | `subtitle_manifest.json` `files[]`, then raw artifacts | `.ass/.srt/.vtt` that exist | priority **ass → srt → vtt** (one chosen) | n/a (single primary track) |

- Manifests (`video_manifest.json`, `voice_manifest.json`, `subtitle_manifest.json`)
  are recorded as `role="manifest"` inputs (never concatenated).
- All artifacts carry `exists` (re-verifiable by the future executor).

---

## Subtitle Mode Behavior

| Condition | `subtitle_mode` |
|-----------|-----------------|
| `.ass` available | `burn_in` |
| only `.srt` / `.vtt` available | `sidecar` |
| no subtitles | `none` |

An explicit `subtitle_mode` argument overrides auto-detection.

## Assembly Mode Behavior

Auto-detected from available groups (explicit `assembly_mode` overrides):

| Available | `assembly_mode` |
|-----------|-----------------|
| video + voice + subtitle | `video_voice_subtitle` |
| video + voice | `video_voice` |
| video only | `video_only` |
| voice only / none | `voice_only` / `video_only` |

> **Naming note:** the spec listed `video_voice_subtitles` (plural) and a `partial`
> mode. To stay consistent with the 11J-2 foundation constants already used by the
> slot/preflight, the canonical mode value is `video_voice_subtitle` (singular,
> `MODE_VIDEO_VOICE_SUBTITLE`), and `partial` is represented as
> `validation_status = PARTIAL` rather than an assembly mode (it is a readiness
> state, not a structural composition).

## Output Planning

- `expected_output = FINAL_PUBLISH_READY.mp4`
- `output_dir = storage/content_brain/execution/artifacts/{session_id}/assembly_generation/`
  (computed as a path string; **the builder does not create the directory or file**)
- `output_targets = [{ "variant": <output_variant>, "file_name": FINAL_PUBLISH_READY.mp4 }]`

## Validation Status Mapping

| `validation_status` | Condition |
|---------------------|-----------|
| `READY` | video + voice + subtitle (and listed manifests) present/valid |
| `PARTIAL` | base video present but a required group/manifest missing |
| `FAILED` | no usable video, or video manifest listed-but-missing |

Warnings include: missing manifests, clip/narration count mismatch, SRT/VTT-only
sidecar fallback, and each missing input group.

## Future-Safe Fields (reserved, defaults)

`output_variant="primary"`, `output_targets=[…]`, `music_inputs=[]`,
`music_mode="none"`, `language=None`, plus per-artifact `language=None`. All additive
with safe defaults so `AssemblyPlan.to_dict()` stays backward-compatible.

---

## Validation Results

Command:

```
python -m project_brain.validate_11j4_assembly_plan_builder
```

| # | Test | Result |
|---|------|--------|
| 1 | Builds plan with video + voice + ass subtitle | PASS |
| 2 | Picks ASS before SRT/VTT | PASS |
| 3 | Falls back to SRT (sidecar) when ASS missing | PASS |
| 4 | `subtitle_mode=none` when no subtitles | PASS |
| 5 | Orders video clips by clip index | PASS |
| 6 | Orders voice inputs by `segment_index` | PASS |
| 7 | Dedupes duplicate artifact paths | PASS |
| 8 | READY when required artifacts/manifests exist | PASS |
| 9 | PARTIAL when one input group missing | PASS |
| 10 | FAILED when no usable video | PASS |
| 11 | Video slot unchanged | PASS |
| 12 | Voice slot unchanged | PASS |
| 13 | Subtitle slot unchanged | PASS |
| 14 | Does not write `FINAL_PUBLISH_READY.mp4` | PASS |
| 15 | No FFmpeg import/call | PASS |
| 16 | No `full_video_pipeline` import | PASS |
| 17 | Existing 11J-2 validator still passes | PASS |
| 18 | Existing 11I-8 validator still passes | PASS |
| 19 | Existing 11H-2d validator still passes | PASS |

Builder tests (1–16) verified directly: **16/16 PASS**.

Regression commands (all PASS):

```
python -m project_brain.validate_11j2_assembly_runtime_foundation
python -m project_brain.validate_11i8_subtitle_runtime_execution_api
python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution
```

> Note: the regression chain (11J-2 → 11I-8 → …) spawns deeply nested validator
> subprocesses, so the full `validate_11j4` run takes several minutes. This is
> pre-existing behavior, unchanged by this phase.

---

## Safety Confirmations

- **No FFmpeg.** `assembly_plan_builder.py` contains no ffmpeg import/attribute/call
  (AST + literal scan enforced by test 15).
- **No `FINAL_PUBLISH_READY.mp4` generation.** The name is a planned string only;
  test 14 confirms no file is written to the planned output path.
- **No subtitle burning, no media processing.** Existence via `Path.is_file()` and
  read-only manifest JSON parsing only.
- **Upstream slots unchanged.** Builder returns data and writes nothing; deep-copy
  comparison confirms `video_generation` / `voice_generation` /
  `subtitle_generation` slots are untouched (tests 11–13).
- **No legacy pipeline import.** `full_video_pipeline` banned (test 16).
- **No Runway/Hailuo changes.**

---

## Next Phase

**PHASE 11J-5 — Assembly FFmpeg Executor Design**

Design the isolated `assembly_ffmpeg_executor.py` that consumes an `AssemblyPlan`
and produces `FINAL_PUBLISH_READY.mp4` (reusing proven leaf FFmpeg engines as
libraries, never the legacy pipeline orchestrator), plus the
`assembly_run_action_policy` guard and `AssemblyRuntimeEngine` orchestration design.
