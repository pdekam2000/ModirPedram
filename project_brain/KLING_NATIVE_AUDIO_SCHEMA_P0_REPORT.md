# Kling Native Audio Schema P0 Report

**Phase:** KLING-NATIVE-AUDIO-SCHEMA-P0  
**Status:** Complete  
**Date:** 2026-06-16  
**Scope:** Schema/model foundation only — no UI, automation, Generate, credits, or provider execution

---

## Summary

P0 adds typed dataclass models for Kling Native Audio planning and continuity metadata, plus duration normalization helpers aligned with `KLING_STORY_ARCHITECTURE_DESIGN.md` and `KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md`.

All **12** validation checks pass.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/kling_native_audio_models.py` | Core models, builders, duration mapping, validators |
| `project_brain/validate_kling_native_audio_schema_p0.py` | P0 validation suite (12 tests) |
| `project_brain/KLING_NATIVE_AUDIO_SCHEMA_P0_REPORT.md` | This report |

## Files Modified

None.

---

## Schema Summary

### Model hierarchy

```
KlingNativeAudioPlan
├── version: kling_native_audio_plan_v1
├── provider: kling_3_0_pro_native_audio
├── strategy: two_shot_continuity
├── audio_strategy: kling_native_audio
├── native_audio_required: true
├── use_elevenlabs: false
├── use_external_music: false
├── subtitle_required: true
└── clips[]: KlingClipPlan
    ├── clip_duration_seconds: 15
    ├── shot_1: KlingShotPlan (12s, main_action)
    ├── shot_2: KlingShotPlan (3s, transition_bridge)
    ├── first_frame_source / prior_clip_index
    ├── next_clip_reference_hint
    ├── continuity_bridge
    └── expected_native_audio

KlingContinuityChain
├── version: kling_continuity_chain_v1
├── run_id / clip_count
├── links[]: clip N → clip N+1
├── frame_sources[]: per-clip first frame metadata
└── continuity_notes[]
```

### Supporting types

| Type | Role |
|------|------|
| `NativeAudioDirectives` | dialogue_lines, ambience, foley, voice_acting |
| `KlingContinuityLink` | from_clip_index → to_clip_index handoff |
| `KlingFrameSource` | first frame source per clip |

### Key helpers

| Function | Role |
|----------|------|
| `normalize_kling_duration()` | Map requested → planned duration + clip count + warnings |
| `build_kling_native_audio_plan()` | Skeleton plan for a duration tier |
| `build_continuity_chain_from_plan()` | Derive N→N+1 links from clip plans |
| `validate_kling_native_audio_plan()` | Structural invariant checks |

All models support `to_dict()` / `from_dict()` for JSON-safe persistence.

---

## Duration Mapping Behavior

| Requested | Planned | Clips | Warning |
|-----------|---------|-------|---------|
| **15s** | 15s | 1 | — |
| **30s** | 30s | 2 | — |
| **45s** | 45s | 3 | — |
| **60s** | 60s | 4 | — |
| **40s** | **45s** | **3** | `requested_duration_seconds=40 rounded up to planned_duration_seconds=45` |

**Formula:** `clip_count = planned_duration_seconds / 15`

**Shot mode (every clip):**

| Shot | Duration | Role |
|------|----------|------|
| Shot 1 | 12s | `main_action` |
| Shot 2 | 3s | `transition_bridge` |

**Unsupported > 60s:** Rounds up then caps at 60s with additional warning.

---

## Validation Results

```text
python project_brain/validate_kling_native_audio_schema_p0.py
→ All 12 checks passed
```

| # | Test | Result |
|---|------|--------|
| 1 | 15s → 1 clip | PASS |
| 2 | 30s → 2 clips | PASS |
| 3 | 45s → 3 clips | PASS |
| 4 | 60s → 4 clips | PASS |
| 5 | 40s → 45s + warning | PASS |
| 6 | Every clip shot_1 = 12s | PASS |
| 7 | Every clip shot_2 = 3s | PASS |
| 8 | `use_elevenlabs` false | PASS |
| 9 | `use_external_music` false | PASS |
| 10 | `native_audio_required` true | PASS |
| 11 | `subtitle_required` true | PASS |
| 12 | Continuity chain clip N → N+1 | PASS |

---

## Safety Confirmations

- No UI changes  
- No Runway/Kling automation changes  
- No Generate  
- No credits spent  
- No provider execution  

---

## Design Alignment

| Design doc | P0 coverage |
|------------|-------------|
| `KLING_STORY_ARCHITECTURE_DESIGN.md` | 12+3 shots, 15/30/45/60 tiers, continuity fields |
| `KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md` | Plan + continuity chain schema, audio flags |
| `PHASE_KLING_NATIVE_AUDIO_GUI_INTEGRATION_REPORT.md` | P0 listed as first implementation phase |

---

## Next Recommended Phase

**PHASE KLING-NATIVE-AUDIO-DURATION-PLANNER-P1**

- Extend `content_brain/scheduling/duration_planner.py` with `kling_3_pro_native` provider key  
- Wire `product_studio_service.py` preflight to use `normalize_kling_duration()`  
- Return Kling duration warnings in preflight API  
- Still no UI or Generate — backend duration authority only  

---

## References

- `content_brain/execution/kling_native_audio_models.py`
- `content_brain/execution/kling_multishot_config.py`
- `project_brain/validate_kling_native_audio_schema_p0.py`
