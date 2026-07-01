# Kling Native Audio Preflight API P4 Report

**Phase:** `KLING-NATIVE-AUDIO-PREFLIGHT-API-P4`  
**Status:** PASS  
**Date:** 2026-06-03

## Goal

Wire Kling Native Audio planning into Product Studio preflight so GUI/API can preview the resolved Kling plan before generation — preview only, no browser, no Generate, no credits.

---

## Files Modified

| File | Changes |
|------|---------|
| `ui/api/product_studio_service.py` | Extended `create_video_preflight()` — router + duration + content planner + Kling preview payload |
| `ui/api/schemas/product_studio.py` | Extended request/response DTOs with `audio_strategy` and Kling preflight fields |
| `content_brain/execution/kling_native_audio_planner.py` | Added `build_kling_clip_prompts_preview`, `collect_kling_preflight_warnings`, `build_kling_preflight_api_payload` |

## Files Created

| File | Purpose |
|------|---------|
| `project_brain/validate_kling_native_audio_preflight_api_p4.py` | P4 validation (15 test groups + P0–P3 regression) |
| `project_brain/KLING_NATIVE_AUDIO_PREFLIGHT_API_P4_REPORT.md` | This report |

---

## Preflight Behavior

### Kling path activation

Preflight builds full Kling preview when any of:

- `audio_strategy = auto` and router resolves `kling_native_audio`
- `audio_strategy = kling_native_audio` (explicit)
- `provider = kling_3_0_pro_native_audio` (or Kling alias)

### Response fields (Kling path)

| Field | Description |
|-------|-------------|
| `audio_strategy_route` | Full router output from P2 |
| `kling_duration_plan` | Duration/clip tier metadata from P1 |
| `kling_native_audio_plan` | Full `KlingNativeAudioPlan` from P3 |
| `kling_clip_count` | Number of 15s clips |
| `kling_shot_mode` | `two_shot_continuity` |
| `kling_clip_prompts` | Per-clip shot preview list |
| `use_elevenlabs` | `false` |
| `use_external_music` | `false` |
| `native_audio_required` | `true` |
| `subtitle_required` | `true` |
| `preflight_mode` | `preview_only` |
| `warnings` | Duration round/cap, prompt length, missing story fields |

### Per-clip prompt preview shape

```json
{
  "clip_index": 1,
  "shot_1_duration_seconds": 12,
  "shot_1_prompt": "...",
  "shot_2_duration_seconds": 3,
  "shot_2_prompt": "...",
  "continuity_anchor": "...",
  "next_clip_reference_hint": "..."
}
```

### Safety

`create_video_preflight()` does **not**:

- Open browser / CDP
- Click Runway Generate
- Call Kling API
- Spend credits

---

## Sample Preflight Response (excerpt)

**Request:**

```json
{
  "topic_mode": "custom",
  "custom_topic": "A young boy discovers an injured baby dragon under twisted forest roots in a fantasy cinematic story",
  "duration_seconds": 30,
  "audio_strategy": "auto",
  "provider": "auto"
}
```

**Response (key fields):**

```json
{
  "ok": true,
  "preflight_mode": "preview_only",
  "provider": "kling_3_0_pro_native_audio",
  "audio_strategy": "kling_native_audio",
  "kling_clip_count": 2,
  "kling_shot_mode": "two_shot_continuity",
  "use_elevenlabs": false,
  "use_external_music": false,
  "native_audio_required": true,
  "subtitle_required": true,
  "kling_clip_prompts": [
    {
      "clip_index": 1,
      "shot_1_duration_seconds": 12,
      "shot_2_duration_seconds": 3,
      "continuity_anchor": "young boy and baby dragon held at the edge of glowing path deeper in the forest...",
      "next_clip_reference_hint": "Same young boy and baby dragon continue toward glowing path deeper in the forest..."
    }
  ]
}
```

Full plan available under `kling_native_audio_plan`; duration metadata under `kling_duration_plan`.

---

## Validation Results

```text
python project_brain/validate_kling_native_audio_preflight_api_p4.py
→ All Kling Native Audio preflight API P4 checks passed
```

| # | Test | Result |
|---|------|--------|
| 1 | auto + dragon topic → Kling route | PASS |
| 2 | explicit `kling_native_audio` | PASS |
| 3 | explicit Kling provider | PASS |
| 4 | 30s → 2 clips | PASS |
| 5 | 40s → 45s / 3 clips + warning | PASS |
| 6 | per-clip shot prompts exist | PASS |
| 7 | each prompt ≤ 512 chars | PASS |
| 8 | continuity fields exist | PASS |
| 9 | ElevenLabs disabled | PASS |
| 10 | external music disabled | PASS |
| 11 | `native_audio_required` true | PASS |
| 12 | no browser automation in preflight | PASS |
| 13 | Runway narrator unchanged | PASS |
| 14 | music_only unchanged | PASS |
| 15 | P0/P1/P2/P3 regressions | PASS |

---

## Compatibility Notes

- Runway narrator and music_only preflight paths unchanged — no `kling_native_audio_plan` when not on Kling route
- Uses existing P2 router, P1 duration planner, P3 content planner — no duplicate pipelines
- API schema extended so FastAPI response preserves Kling fields (previously stripped by strict DTO)
- Optional payload fields supported: `story_package`, `story_summary`, `characters`, `environment`, `mood`
- `require_story_package=true` adds missing-story warnings when package absent

---

## Next Recommended Phase

**PHASE KLING-NATIVE-AUDIO-GUI-P5**

- Product Studio UI: Audio Strategy (Auto / Music / Narrator / Kling), Provider picker, duration 15/30/45/60
- Render `kling_clip_prompts` preview panel from preflight response
- Still no Generate click without approval gate
