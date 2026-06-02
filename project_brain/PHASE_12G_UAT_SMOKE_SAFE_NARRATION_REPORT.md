# Phase 12G — UAT Smoke-Safe Narration Report

**Date:** 2026-06-01  
**Status:** Implemented  
**Scope:** UAT-only live ElevenLabs smoke narration merge

---

## Problem

Live voice smoke cap (`SMOKE_MAX_SEGMENTS = 1`) checks **narration segment count**, not video clip count.

Content Brain can produce **6 story beats** for a 10s UAT run. Video completes with 2 clips, but voice fails:

```
Smoke segment count exceeds cap (1)
```

The Phase 12F duration guard reduced video duration but did not reduce narration beats.

---

## Solution

**UAT-only narration adapter** (`content_brain/execution/uat_smoke_narration_adapter.py`):

Before voice preflight and `LiveVoiceTtsEngine`, when:

- `operations.uat_run.mode == user_acceptance_test`
- `voice_provider == elevenlabs`
- `confirm_real_voice == true`

…the adapter:

1. Reads narration via `SessionNarrationAdapter` (unchanged production adapter)
2. Merges multi-beat text into **one concise narration** (hook + payoff, char-capped for ~10s / smoke limit)
3. Patches `brief_snapshot.story_blueprint.beats` and `run_context.story_intelligence.story_architecture.beat_plans` to a single beat
4. Stores metadata on `operations.uat_run.smoke_narration`:
   - `original_narration_segment_count`
   - `smoke_narration_segment_count` (1)
   - `merged_text_length`, `merged_text_preview`
5. Logs: `[UAT_SMOKE_NARRATION] original_narration_segment_count=… smoke_narration_segment_count=…`

Wiring: `uat_runtime_engine._run_voice_stage()` calls `apply_uat_smoke_narration_session()` **before** `apply_voice_preflight_dry_run()`.

---

## What Did NOT Change

| Area | Change |
|------|--------|
| Content Brain orchestrators/engines | None |
| `LiveVoiceTtsEngine` core logic | None (reads patched brief via existing adapter) |
| `SMOKE_MAX_SEGMENTS` | Still 1 |
| Runway / Hailuo providers | None |
| Mock voice / non-smoke UAT | Skips merge |
| Full production voice runs | Skips merge (not UAT + not live smoke guard) |

---

## UI: `failed_stage` Fix (retained)

- `normalizeStageKey("failed")` no longer defaults to `content_brain`
- Backend persists `failed_stage` (e.g. `"voice"`) when run fails
- Content Brain shows **Complete** when brief succeeded; failing stage shows **Failed**

---

## Validation

| Check | Result |
|-------|--------|
| `validate_12b --core-only` | 6→1 merge, smoke cap pass, mock/dry skip |
| `validate_12d --core-only` | Module wired, `failed_stage` persisted |
| `validate_12e --core-only` | Stage mapping + npm build |

**Expected live UAT (Runway + ElevenLabs + Real Assembly + 10s):**

- POST `/uat/run` → 202
- Content Brain + Video complete
- Voice preflight `segment_count = 1`
- No smoke segment cap error
- Logs include original/smoke segment counts

---

## Files

| File | Role |
|------|------|
| `content_brain/execution/uat_smoke_narration_adapter.py` | Merge + brief patch + metadata |
| `content_brain/execution/uat_runtime_engine.py` | Wire before voice preflight; `failed_stage` |
| `ui/web/src/utils/uatRuntimeLabels.ts` | Failed stage UI mapping |
| `project_brain/validate_12b_uat_supervised_pipeline.py` | Merge + cap tests |
| `project_brain/validate_12d_uat_runtime_backend_api.py` | Wiring checks |

---

## Operator Note

For supervised live-voice smoke UAT, narration is automatically merged to one segment. Original beat count is recorded in `operations.uat_run.smoke_narration`. This is a smoke safety envelope only — full UAT with mock voice or non-confirmed live voice is unchanged.
