# Kling Native Audio Content Planner P3 Report

**Phase:** `KLING-NATIVE-AUDIO-CONTENT-PLANNER-P3`  
**Status:** PASS  
**Date:** 2026-06-03

## Goal

Add a Kling-specific Content Planner that converts topic/story inputs into `KlingNativeAudioPlan` with populated 2-shot continuity clip plans (12s + 3s per 15s clip).

No UI, Generate, credits, or browser automation changes in this phase.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/kling_native_audio_planner.py` | Main planner — story context extraction, beat allocation, shot prompt composition, continuity linking |
| `project_brain/validate_kling_native_audio_content_planner_p3.py` | P3 validation (14 test groups + P0/P1/P2 regression) |
| `project_brain/KLING_NATIVE_AUDIO_CONTENT_PLANNER_P3_REPORT.md` | This report |

---

## Planner Behavior

### Inputs (`plan_kling_native_audio_content`)

- `topic`
- `story_package` or `story_summary`
- `platform`
- `planned_duration_seconds`
- `clip_count` (optional override)
- `mood` / `style`
- `characters`
- `environment`

### Output

Returns a populated `KlingNativeAudioPlan` using existing P0 schema models:

- Provider: `kling_3_0_pro_native_audio`
- Strategy: `two_shot_continuity`
- `use_elevenlabs = false`
- `use_external_music = false`
- `native_audio_required = true`

### Per-clip structure

| Shot | Duration | Role | Content |
|------|----------|------|---------|
| Shot 1 | 12s | `main_action` | Main story beat, characters, emotion, environment, native audio cues, cinematic style |
| Shot 2 | 3s | `transition_bridge` | Continuity bridge, next-scene setup, final-frame hold, native audio cues |

### Beat allocation

| Duration | Clips | Beat arc |
|----------|-------|----------|
| 15s | 1 | setup |
| 30s | 2 | setup → escalation |
| 45s | 3 | setup → conflict → discovery |
| 60s | 4 | hook → conflict → discovery → resolution |

When `story_package.story_blueprint.scene_progression` is present, beats are taken from that list first.

### Continuity

- Clip N Shot 2 sets `continuity_anchor` and `next_clip_reference_hint`
- Clip N+1 Shot 1 opens with `Continuing from the previous bridge, same {characters} move toward {prior_bridge_hint}`
- First frame source: `user_upload` (clip 1) / `prior_clip_shot2_final_frame` (clip 2+)

### Prompt enforcement

- Max **512 chars** per shot prompt (truncation preserves native audio suffix)
- Forbidden tokens: ElevenLabs, external music, voiceover narrator, TTS dub
- Required native audio cues: breathing, ambience, voices, native cinematic audio, etc.
- Structured `NativeAudioDirectives` on each shot (dialogue, ambience, foley, voice_acting)

### Router integration

`plan_kling_from_audio_route()` reads `kling_native_audio` metadata from `route_audio_strategy()` and passes duration/clip_count into the planner.

---

## Example Generated Plan (15s dragon/boy benchmark)

**Topic:** A young boy discovers an injured baby dragon under twisted forest roots

**Clip 1 — Shot 1 (12s):**

> A young boy kneels beside an injured baby dragon under twisted forest roots. young boy and baby dragon express tender wonder within twisted fantasy forest with mossy roots and drifting mist. Cinematic tender wonder, emotional fantasy framing. Don't worry... I won't hurt you. soft breathing, leaves moving, forest ambience, natural voices, native cinematic audio.

**Clip 1 — Shot 2 (3s):**

> young boy and baby dragon gently transition toward glowing path deeper in the forest, setting up the next scene. Hold final frame facing glowing path deeper in the forest. Cinematic tender wonder, emotional fantasy framing. soft breathing, forest ambience, natural voices, native cinematic audio.

**Continuity anchor:** young boy and baby dragon held at the edge of glowing path deeper in the forest… final frame ready for handoff

---

## Validation Results

```text
python project_brain/validate_kling_native_audio_content_planner_p3.py
→ All Kling Native Audio content planner P3 checks passed
```

| # | Test | Result |
|---|------|--------|
| 1 | 15s → 1 clip | PASS |
| 2 | 30s → 2 clips | PASS |
| 3 | 45s → 3 clips | PASS |
| 4 | Every shot_1 = 12s | PASS |
| 5 | Every shot_2 = 3s | PASS |
| 6 | Every prompt ≤ 512 chars | PASS |
| 7 | Native audio cues in prompts | PASS |
| 8 | No ElevenLabs | PASS |
| 9 | No external music | PASS |
| 10 | Continuity anchors exist | PASS |
| 11 | Clip N Shot 2 → Clip N+1 Shot 1 link | PASS |
| 12 | Dragon/boy 2-character prompts | PASS |
| 13 | Router output feeds planner | PASS |
| 14 | P0/P1/P2 regressions | PASS |

---

## Compatibility Notes

- Builds on `kling_native_audio_models.py` (P0) — no schema changes required
- Uses `normalize_kling_duration()` from models + `duration_planner.py` tier rules
- Compatible with `audio_strategy_router.py` (P2) via `plan_kling_from_audio_route()`
- Does **not** modify Runway/Hailuo paths, UI, or browser automation
- `validate_kling_content_plan()` extends P0 `validate_kling_native_audio_plan()` with content rules
- `build_kling_native_audio_plan()` skeleton builder still available for empty plans; planner fills prompts

---

## Next Recommended Phase

**PHASE KLING-NATIVE-AUDIO-PREFLIGHT-API-P4**

Wire planner output into Product Studio preflight API response:

- Return full `kling_native_audio_plan` when router selects Kling path
- Expose clip/shot prompts for downstream shadow/live runners
- Keep Generate approval-gated and credit-safe
