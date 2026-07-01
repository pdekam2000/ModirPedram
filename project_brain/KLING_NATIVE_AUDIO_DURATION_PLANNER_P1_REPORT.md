# Kling Native Audio Duration Planner P1 Report

**Phase:** KLING-NATIVE-AUDIO-DURATION-PLANNER-P1  
**Status:** Complete  
**Date:** 2026-06-16  
**Scope:** Duration planner + preflight API — no UI, Generate, credits, or browser automation

---

## Summary

Kling Native Audio duration planning is wired into `duration_planner` and `create_video_preflight`. Runway and Hailuo behavior is unchanged. Preflight returns a `kling_duration_plan` metadata block when Kling is selected.

**Note:** Each Kling shot prompt is capped at **512 characters** (`KLING_SHOT_PROMPT_MAX_CHARS`) — exposed in preflight metadata for downstream planners.

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/scheduling/duration_planner.py` | Kling branch, extended `DurationPlan`, preflight metadata helpers |
| `content_brain/scheduling/__init__.py` | Export new helpers |
| `content_brain/execution/kling_native_audio_models.py` | Added `KLING_SHOT_PROMPT_MAX_CHARS = 512` |
| `ui/api/product_studio_service.py` | Preflight accepts `audio_strategy`; returns `kling_duration_plan` |

## Files Created

| File | Purpose |
|------|---------|
| `project_brain/validate_kling_native_audio_duration_planner_p1.py` | 12-test P1 validation suite |
| `project_brain/KLING_NATIVE_AUDIO_DURATION_PLANNER_P1_REPORT.md` | This report |

---

## Duration Behavior

### Kling Native Audio (provider or `audio_strategy=kling_native_audio`)

| Requested | Planned | Clips | Notes |
|-----------|---------|-------|-------|
| 15s | 15s | 1 | Exact tier |
| 30s | 30s | 2 | Exact tier |
| 45s | 45s | 3 | Exact tier |
| 60s | 60s | 4 | Exact tier |
| 40s | **45s** | **3** | Round up + warning |
| 75s | **60s** | **4** | Cap at 60s + warning |

**Per clip:** 15s total — Shot 1 = 12s, Shot 2 = 3s (`two_shot_continuity`)

### Runway (unchanged)

| Example | Duration | Clips |
|---------|----------|-------|
| 40s | 40s | 4 (10s limit) |

### Hailuo (unchanged)

| Example | Duration | Clips |
|---------|----------|-------|
| 40s | 40s | 5 (8s limit) |
| 24s | 24s | 3 |

---

## Preflight API — Kling Metadata

When Kling route is active, response includes:

```json
{
  "provider": "kling_3_0_pro_native_audio",
  "audio_strategy": "kling_native_audio",
  "kling_duration_plan": {
    "provider": "kling_3_0_pro_native_audio",
    "audio_strategy": "kling_native_audio",
    "requested_duration_seconds": 40,
    "planned_duration_seconds": 45,
    "clip_count": 3,
    "shot_mode": "two_shot_continuity",
    "shot_1_duration_seconds": 12,
    "shot_2_duration_seconds": 3,
    "clip_duration_seconds": 15,
    "native_audio_required": true,
    "use_elevenlabs": false,
    "use_external_music": false,
    "subtitle_required": true,
    "shot_prompt_max_chars": 512,
    "warnings": ["requested_duration_seconds=40 rounded up to planned_duration_seconds=45"]
  },
  "duration_plan": { "... enriched kling fields ..." }
}
```

**Trigger conditions:**

- `provider` ∈ `{kling_3_0_pro_native_audio, kling_3_pro_native, kling, …}`  
- **OR** `audio_strategy` = `kling_native_audio`

---

## Validation Results

```text
python project_brain/validate_kling_native_audio_duration_planner_p1.py
→ All 12 checks passed
```

| # | Test | Result |
|---|------|--------|
| 1 | Kling 15 → 1 clip | PASS |
| 2 | Kling 30 → 2 clips | PASS |
| 3 | Kling 45 → 3 clips | PASS |
| 4 | Kling 60 → 4 clips | PASS |
| 5 | Kling 40 → 45 / 3 + warning | PASS |
| 6 | Kling 75 → 60 cap + warning | PASS |
| 7 | Runway 40 unchanged | PASS |
| 8 | Hailuo unchanged | PASS |
| 9 | Preflight shot mode | PASS |
| 10 | Preflight native provider | PASS |
| 11 | ElevenLabs disabled for Kling | PASS |
| 12 | External music disabled for Kling | PASS |

**Regression:** `validate_ui_pro_2_create_video_scheduling.py` — core duration/clip tests **PASS** (Runway 40→4, Hailuo 24→3). Unrelated downstream regression in `validate_director_layer_v2_prompt_critic.py` pre-exists this phase.

**P0 schema:** `validate_kling_native_audio_schema_p0.py` — still PASS.

---

## Compatibility with Existing Providers

| Provider | Changed? | Verification |
|----------|----------|--------------|
| Runway | **No** | `plan_duration(40, runway)` → 4 clips, not Kling |
| Hailuo | **No** | `plan_duration(40, hailuo)` → 5 clips |
| Kling | **New branch** | Isolated via `is_kling_native_audio_route()` |

Kling logic delegates to `normalize_kling_duration()` from P0 schema — single source of truth.

---

## Safety Confirmations

- No UI changes  
- No Generate  
- No credits spent  
- No browser automation changes  

---

## Next Recommended Phase

**PHASE KLING-NATIVE-AUDIO-ROUTER-P2**

- Extend Audio Strategy Router v2 with `kling_native_audio` class  
- Auto-resolve provider when strategy = Kling  
- Wire Create Video payload `audio_strategy: auto` → resolved strategy in preflight  
- Still no UI surface changes until P4  

---

## References

- `content_brain/scheduling/duration_planner.py`
- `content_brain/execution/kling_native_audio_models.py`
- `ui/api/product_studio_service.py`
- `project_brain/KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md`
