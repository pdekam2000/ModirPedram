# KLING Native Audio Router P2 Report

**Phase:** `KLING-NATIVE-AUDIO-ROUTER-P2`  
**Status:** PASS  
**Date:** 2026-06-03

## Goal

Upgrade the Audio Strategy Router to resolve `kling_native_audio` automatically for suitable content, with preflight integration and no UI / Generate / credits / browser automation changes.

## Deliverables

| Item | Path | Status |
|------|------|--------|
| Audio Strategy Router v2 | `content_brain/audio/audio_strategy_router.py` | ✅ |
| Package init | `content_brain/audio/__init__.py` | ✅ |
| Preflight wiring | `ui/api/product_studio_service.py` | ✅ |
| Validation | `project_brain/validate_kling_native_audio_router_p2.py` | ✅ 28/28 |
| Report | `project_brain/KLING_NATIVE_AUDIO_ROUTER_P2_REPORT.md` | ✅ |

## Supported Strategies

1. `music_only` — luxury / aesthetic / travel / fashion / visual loop / no dialogue
2. `narrator` — mystery / documentary / educational / faceless storytelling
3. `cinematic` — scored alongside Kling for dialogue-heavy cinematic content
4. `kling_native_audio` — fantasy / animals / children / mini movie / dialogue / creatures / foley cues

When `kling_native_audio` is selected:

- `provider_recommendation` = `kling_3_0_pro_native_audio`
- `use_elevenlabs` = `false`
- `use_external_music` = `false`
- `native_audio_required` = `true`
- `shot_prompt_max_chars` = `512`
- `kling_native_audio` metadata includes duration plan and `two_shot_continuity` shot mode

## Auto-Routing Rules

| Signal | Route |
|--------|-------|
| fantasy, dragon, creature, monster, animal, children, mini movie, cinematic story, dialogue, multiple characters, breathing, growling, footsteps, emotional | `kling_native_audio` |
| mystery, documentary, educational, explainer, faceless | `narrator` |
| luxury, aesthetic, travel, motivation quote, fashion, visual loop, no dialogue | `music_only` |
| Low confidence (score gap &lt; 8) | `narrator` (safe fallback) |

Hard overrides:

- Explicit `audio_strategy` request
- `narration_provider_disabled` → `music_only`
- `block_kling_native` → suppress Kling
- Visual-first tokens (`aesthetic reel`, `product showcase`, `timelapse`, `visual loop`) → `music_only` when music score wins

## Router Output Shape

`route_audio_strategy()` and `audio_strategy_route` in preflight include:

- `audio_strategy`
- `provider_recommendation`
- `confidence`
- `class_label`
- `reasoning`
- `scores`
- `hard_overrides`
- `platform_bias`
- `recommended_pipeline`
- `kling_native_audio` (when applicable)
- `use_elevenlabs`, `use_external_music`, `native_audio_required`, `shot_prompt_max_chars`

## Preflight Integration

`ProductStudioService.create_video_preflight()` now:

1. Calls `route_audio_strategy()` with topic, niche, platform, style, duration, character/dialogue counts, and profile flags.
2. When `audio_strategy == "auto"`, resolves provider from router recommendation.
3. Plans duration with resolved strategy/provider.
4. Returns `audio_strategy_route`, `kling_duration_plan` (when Kling path), and updated `provider` / `audio_strategy`.

## Validation Results

```text
python project_brain/validate_kling_native_audio_router_p2.py
→ All Kling Native Audio router P2 checks passed (28 assertions)
```

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 1 | Dragon/boy fantasy story | `kling_native_audio` | PASS |
| 2 | Animal story | `kling_native_audio` | PASS |
| 3 | Two-character emotional scene | `kling_native_audio` | PASS |
| 4 | Horror creature scene | `kling_native_audio` | PASS |
| 5 | Educational explainer | `narrator` | PASS |
| 6 | Documentary mystery | `narrator` | PASS |
| 7 | Luxury aesthetic reel | `music_only` | PASS |
| 8 | Low confidence | `narrator` | PASS |
| 9 | Kling provider | `kling_3_0_pro_native_audio` | PASS |
| 10 | Kling duration plan | present + shot mode | PASS |
| 11 | Kling disables ElevenLabs | `use_elevenlabs=false` | PASS |
| 12 | Explicit narrator/music unchanged | PASS | PASS |

P1 regression:

```text
python project_brain/validate_kling_native_audio_duration_planner_p1.py
→ All P1 checks passed
```

## Out of Scope (This Phase)

- UI controls for Audio Strategy / Provider
- Generate clicks or credit spend
- Browser automation / CDP changes
- Content planner (Story / Clip / Shot) — deferred to P3

## Next Phase

**PHASE KLING-NATIVE-AUDIO-CONTENT-PLANNER-P3**

- Kling Story Planner
- Clip Planner
- Shot Planner wired to router + duration plan output
