# UAT Smoke Segment Cap Fix Report

**Session:** `exec_uat_20260601_212111`  
**Date:** 2026-06-01  
**Fix:** Option A — UAT-only duration auto-reduction before segment planning

---

## Root Cause

The UAT run failed at **Voice Runtime** with:

```
Smoke segment count exceeds cap (1).
```

This is **not** a Content Brain failure. Content Brain completed successfully and produced a valid brief/plan.

The failure came from the **11H-2d live ElevenLabs smoke guard** (`voice_live_tts_smoke_profile.py`), which enforces `SMOKE_MAX_SEGMENTS = 1` before any real TTS HTTP call.

### Why it triggered

| Input | Effect |
|-------|--------|
| Duration **20s** | Runway clip duration = 10s → `ceil(20/10) = 2` clips |
| 2 clips | → 2 narration/voice segments |
| Live voice + ElevenLabs | Smoke cap allows **max 1 segment** → blocked |

Provider stack: `runway_browser / elevenlabs / real_assembly`

---

## Fix Applied (Option A — Preferred)

**UAT-only** duration guard runs **before** `ContentBriefOrchestrator` segment planning when live voice is requested:

- If `voice_provider=elevenlabs` and `confirm_real_voice=true`
- Reduce duration to provider-safe single-segment target:
  - **Runway Browser:** 10s
  - **Hailuo Browser:** 6s
- Record original duration + adjustment in `operations.uat_run.smoke_duration_guard`
- Emit warning: *smoke safety limit, not Content Brain failure*

**No changes** to:

- Runway / Hailuo provider runtime
- Content Brain orchestrators/engines
- `SMOKE_MAX_SEGMENTS` in production smoke profile

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/execution/uat_runtime_profile.py` | `apply_live_voice_smoke_duration_guard()`, safe duration map, smoke min duration |
| `content_brain/execution/uat_runtime_engine.py` | Apply guard in `run_uat_pipeline()`; clarify smoke error messages in voice stage |
| `project_brain/validate_12b_uat_supervised_pipeline.py` | +4 validation tests for smoke duration guard |
| `ui/web/src/utils/uatRuntimeEligibility.ts` | Preflight warning before Generate when duration > safe |
| `ui/web/src/pages/UatRuntimePage.tsx` | Display preflight warnings |
| `ui/web/src/styles/uat-runtime.css` | Preflight warning styling |

---

## Smoke Duration Behavior

| Scenario | Result |
|----------|--------|
| Live voice + Runway + **20s** | Auto-reduced to **10s** + warning |
| Live voice + Runway + **10s** (smoke-safe) | Unchanged |
| Live voice + Runway + **8s** (smoke-safe) | Unchanged |
| Mock voice + **20s** | Unchanged (no guard) |

**Cap adjusted?** No — production `SMOKE_MAX_SEGMENTS` remains **1**. Only UAT duration is auto-reduced.

---

## Validation

```
python -m project_brain.validate_12b_uat_supervised_pipeline --core-only
```

New core tests:

- `live_voice_smoke_reduces_20s_to_10s`
- `live_voice_smoke_warning_not_content_brain`
- `live_voice_smoke_10s_unchanged`
- `live_voice_smoke_8s_passes_cap`
- `mock_voice_skips_smoke_duration_guard`

---

## Confirmation

- Real provider execution logic **unchanged**
- Content Brain logic **unchanged**
- Fix scoped to **UAT config + pipeline wrapper only**

---

## Follow-up: POST `/uat/run` 422 (API schema alignment)

After the UI allowed 10s duration, FastAPI still rejected requests at validation time because `UatRunRequest.duration_seconds` had `ge=15`.

| Layer | Fix |
|-------|-----|
| `ui/api/schemas/uat_runtime.py` | `ge=UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS` (6), `le=UAT_MAX_DURATION_SECONDS` (90) |
| `ui/web/src/api/uatRuntimeClient.ts` | `Number()` coercion on `duration_seconds`; 422 responses show FastAPI validation detail |
| Validators | `validate_12d`: `schema_accepts_10s_live_voice`, `post_uat_run_10s_live_voice_not_422`; `validate_12e`: `uat_api_422_error_parser` |

Frontend payload field names were already correct (`duration_seconds`, `confirm_real_voice`, `confirm_real_assembly`); no `assembly_provider` or `one_run_only` in backend schema.

**Restart the backend** after pulling this change so the updated Pydantic schema is loaded.

---

## Operator Note

When using **real ElevenLabs voice** in UAT with Runway, expect duration to auto-adjust to **10s** if you request longer (e.g. 20s). The UI shows a yellow preflight warning before Generate. This keeps the run inside the first-live-voice smoke safety envelope.
