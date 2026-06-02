# PHASE E2E-40S — End-to-End Production Pipeline Validation

**Report date:** 2026-06-02  
**Target topic:** Girl in Rain  
**Target duration:** 40 seconds  

---

## Executive summary

| Run | Session | Duration (effective) | Clips | Final MP4 | Verdict |
|-----|---------|----------------------|-------|-----------|---------|
| **40s live attempt** | `exec_uat_20260602_182215` | — | 0 | No | **FAIL** — Content Brain `REJECT` before video |
| **Pipeline evidence** | `exec_uat_20260602_170119` | 10s (smoke guard) | 2 | **Yes** | **PASS** — full stages through `FINAL_PUBLISH_READY.mp4` |

A dedicated **40s** run with real Runway (all clips), ElevenLabs, subtitles, and assembly **did not complete** in this validation pass because the live run was blocked at the story-quality gate. An earlier UAT for the same topic (**girl in rain**) proves the **full production chain** end-to-end at **10s** after the standard live-voice smoke cap.

**40s planning probe (Content Brain only):** `planned_clip_count = 5` at `user_duration_seconds=40`, decision `PROCEED`, `production_ready=true`.

---

## Test configuration (target)

| Field | Value |
|-------|--------|
| Topic | Girl in Rain |
| Video provider | Runway Browser |
| Requested duration | **40s** |
| Voice | ElevenLabs (real) |
| Assembly | Real Assembly |
| Subtitles | Enabled |
| E2E harness | `UAT_E2E_VALIDATION_FULL_DURATION=1` (skips 10s smoke duration cap) |

---

## Metrics — evidence session `exec_uat_20260602_170119`

| Metric | Value |
|--------|--------|
| **planned_clip_count** | 2 |
| **generated_clip_count** | 2 |
| **downloaded_clip_count** | 2 |
| **effective_duration_seconds** | 10 |
| **requested_duration_seconds** (report context) | 40 |
| **total_runtime_seconds** | ~928 (~15.5 min) |

### Downloaded file paths

- `C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\artifacts\exec_uat_20260602_170119\video_generation\clip_01.mp4`
- `C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\artifacts\exec_uat_20260602_170119\video_generation\clip_02.mp4`

### Downstream artifacts

| Artifact | Path |
|----------|------|
| **narration_path** | `...\exec_uat_20260602_170119\voice_generation\narration_001.mp3` |
| **subtitle_path** | `...\exec_uat_20260602_170119\subtitle_generation\subtitles.srt` |
| **assembly_path** | `...\exec_uat_20260602_170119\assembly_generation\assembly_manifest.json` |
| **final_video_path** | `...\exec_uat_20260602_170119\assembly_generation\FINAL_PUBLISH_READY.mp4` |
| **final_video_bytes** | 4,815,185 |

### Clip continuity (Story Intelligence)

| Clip | continuity_notes |
|------|------------------|
| 1 | Follows opening; sets up ESCALATION_BEAT. |
| 2 | Follows HOOK_BEAT; sets up close. |

---

## Objectives — evidence session (2-clip smoke run)

| # | Objective | Result |
|---|-----------|--------|
| 1 | Clip planning | **PASS** — 2 clips planned |
| 2 | All clips generated | **PASS** — 2/2 (Runway browser, real) |
| 3 | All clips downloaded | **PASS** — 2/2 on disk, validated |
| 4 | Clip continuity | **PASS** — continuity notes on both director shots |
| 5 | ElevenLabs narration | **PASS** — `narration_001.mp3` (smoke-merged single segment) |
| 6 | Subtitles | **PASS** — srt / ass / vtt (5 cues) |
| 7 | Assembly | **PASS** — real FFmpeg assembly |
| 8 | FINAL_PUBLISH_READY.mp4 | **PASS** — file exists |

---

## Objectives — 40s target (not met this pass)

| # | Objective | Result |
|---|-----------|--------|
| 1 | Plan ~4–5 clips at 40s | **PLAN OK** — probe shows **5 clips** |
| 2–8 | Full pipeline at 40s | **FAIL** — live run `exec_uat_20260602_182215` rejected before video |

---

## Live 40s run attempt

- **Session:** `exec_uat_20260602_182215`
- **Error:** `Session not ready for UAT video dispatch after supervised approval override: readiness=NOT_READY; Story quality decision is REJECT.; Story quality has critical failures.`
- **Impact:** No Runway clips, no voice, no subtitles, no assembly for the 40s run.

---

## Warnings (evidence session)

- Live voice smoke safety: duration reduced from **15s → 10s** (11H-2d single-segment cap). Not a Content Brain failure.
- Smoke narration merge: **6 → 1** segment for live ElevenLabs smoke.

---

## Failures

- **40s live run:** Content Brain quality `REJECT` (blocks supervised Runway dispatch).
- **40s vs evidence:** Evidence run is **not** a 40s validation; it validates **pipeline wiring** at smoke duration.

---

## Stage summary (evidence session)

```json
{
  "content_brain": { "success": true, "clip_count": 2, "decision": "PROCEED" },
  "video": { "success": true, "video_provider_mode": "real", "queue_bridge": true },
  "voice": { "success": true, "voice_provider_mode": "real", "tts_executed": true },
  "subtitle": { "success": true, "cue_count": 5 },
  "assembly": { "success": true, "real_assembly_executed": true, "output_created": true }
}
```

---

## Validation harness (observability only)

| File | Purpose |
|------|---------|
| `project_brain/e2e_40s_session_collector.py` | Read-only session metrics |
| `project_brain/run_e2e_40s_validation.py` | Run or analyze (`--run` / `--session-id`) |
| `project_brain/validate_e2e_40s_pipeline.py` | Harness checks |

**Re-run 40s (when story gate passes):**

```powershell
$env:UAT_E2E_VALIDATION_FULL_DURATION="1"
python project_brain/run_e2e_40s_validation.py --run
python project_brain/run_e2e_40s_validation.py --session-id <session_id>
```

**Do not stop after first clip:** `RunwayBrowserOrchestrator` loops all prompts; UAT video dispatch uses full `clip_count` from the brief.

---

## Overall

**40s full-pipeline validation:** **INCOMPLETE** (quality gate).  
**End-to-end production path (Runway → voice → subtitles → assembly → final MP4):** **VERIFIED** on session `exec_uat_20260602_170119`.
