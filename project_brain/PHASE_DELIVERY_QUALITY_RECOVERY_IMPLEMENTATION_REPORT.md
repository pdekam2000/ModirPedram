# PHASE DELIVERY-QUALITY-RECOVERY — Implementation Report

**Phase:** DELIVERY-QUALITY-RECOVERY-IMPLEMENTATION  
**Run reference:** `cb_e2e_20260614_195440_8bf41b6b`  
**Topic:** A boy finds a dragon egg in the forest and hides it from everyone  
**Date:** 2026-06-03  

---

## Summary

Six approved recovery steps were implemented in order. The root truncation bug (`-shortest` in narration merge) is eliminated. A delivery quality gate now blocks `publish_completed` when FAIL conditions exist. Subtitle QA no longer hard-depends on numpy. Topic identity is preserved for human narratives. Audio layers are wired with stronger ambience, local music fallback, and corrected character-voice detection. Runtime surfaces real run folder, canonical deliverable, and delivery status.

---

## Files Modified

| File | Step | Change |
|------|------|--------|
| `content_brain/platform/media_probe.py` | 1 | **New** — ffprobe duration/audio/volume helpers |
| `content_brain/audio/audio_merge_engine.py` | 1 | Video-authoritative merge (`apad` + `-t`), no `-shortest` |
| `content_brain/audio/audio_mix_engine.py` | 1, 5 | `-t` video duration, post-mix duration validation |
| `content_brain/platform/delivery_quality_gate.py` | 2 | **New** — FAIL/WARNING evaluation + manifest writer |
| `content_brain/execution/runway_live_post_processor.py` | 1, 2, 6 | Assembly duration probe, `run_dir`, delivery gate, blocked checkpoint |
| `content_brain/branding/branding_runtime.py` | 3 | Fail-closed subtitles; preserve `failed` status |
| `content_brain/branding/subtitle_format_engine.py` | 3 | PIL fallback when numpy missing |
| `content_brain/story/story_niche.py` | 4 | Human narrative markers override cartoon genre |
| `content_brain/story/story_architect.py` | 4 | Topic + `clip_beats` authoritative |
| `content_brain/story/character_director.py` | 4 | Human cast from brief; block Whiskers/Sage leak |
| `content_brain/story/story_package.py` | 4 | Pass `story_brief` to character director |
| `content_brain/audio/voice_casting_engine.py` | 5 | Detect boy/dragon from brief |
| `content_brain/audio/audio_post_processing.py` | 1, 5 | Probe assembly duration, `run_dir`, voice status, ambience 0.22 |
| `content_brain/audio/music_runtime.py` | 5 | Local track fallback when provider `none`; `-t` not `-shortest` |
| `content_brain/platform/run_isolation.py` | 6 | Latest attempt includes run folder + delivery fields |
| `content_brain/platform/results_run_loader.py` | 6 | Read delivery gate; fail-closed post-processing status |

---

## Validations Created

| Script | Purpose |
|--------|---------|
| `project_brain/validate_duration_preservation.py` | No `-shortest`; video-authoritative merge |
| `project_brain/validate_delivery_quality_gate.py` | Gate module + blocked publish checkpoint |
| `project_brain/validate_subtitle_pipeline.py` | numpy fallback + fail-closed branding |
| `project_brain/validate_topic_identity_authority.py` | Dragon Egg story stays human |
| `project_brain/validate_audio_layer_wiring.py` | Voices, ambience, music, mix |
| `project_brain/validate_publish_clarity.py` | Run folder + canonical deliverable exposure |

Run all:

```bash
python project_brain/validate_duration_preservation.py
python project_brain/validate_delivery_quality_gate.py
python project_brain/validate_subtitle_pipeline.py
python project_brain/validate_topic_identity_authority.py
python project_brain/validate_audio_layer_wiring.py
python project_brain/validate_publish_clarity.py
```

---

## Before / After Metrics

| Metric | Before (broken run) | After (expected on re-run) |
|--------|---------------------|----------------------------|
| **Assembly duration** | 40.17 s (4 clips) | 40.17 s preserved |
| **Canonical final duration** | 18.46 s (truncated) | ≈ assembly ± 0.5 s |
| **Duration loss** | ~54% | ≤ 5% or FAIL |
| **Clips visible** | 2 of 4 | 4 of 4 |
| **Merge strategy** | `copy_video_aac_audio_shortest` | `copy_video_aac_apad_video_authoritative` |
| **Subtitle QA** | Failed (`No module named 'numpy'`) | PIL fallback; burn only if visible |
| **Branding on subtitle fail** | Fail-open → `completed` | Fail-closed → `failed` |
| **Topic in story package** | Whiskers/Sage cartoon | Boy / dragon from E2E topic |
| **Character voices status** | "mode off" (wrong logic) | Active when cast > narrator |
| **Music** | Skipped (`provider: none`) | Local track fallback when file exists |
| **Ambience mix level** | 0.14 (barely audible) | 0.22 |
| **Publish checkpoint** | `publish_completed` always | `delivery_gate_failed` on FAIL |
| **Runtime deliverable path** | Stale / truncated canonical | Run-scoped canonical + gate manifest |

---

## Final Status (reference run — pre re-run)

These values describe the **last broken delivery** before this fix lands. Re-run post-processing to regenerate artifacts.

| Field | Status |
|-------|--------|
| **Final duration** | 18.46 s → **must become ~40.17 s** after re-run |
| **Subtitle status** | QA failed (numpy); burn fail-open |
| **Audio status** | Narration only; music skipped; ambience weak |
| **Topic identity** | Drifted to cartoon templates |
| **Delivery gate** | Not present → now enforced |

---

## Delivery Gate Rules (implemented)

**FAIL (blocks `publish_completed`):**

- Duration loss > 5%
- Subtitle failure (when enabled)
- Missing final video
- Assembly failure

**WARNING (upload not ready, checkpoint not `publish_completed`):**

- Music missing
- Ambience weak
- Character voices disabled

---

## Architecture Preservation

- No new pipelines or providers
- Extended existing engines (`audio_merge_engine`, `branding_runtime`, `runway_live_post_processor`)
- New modules limited to shared probes (`media_probe`) and gate (`delivery_quality_gate`)
- Runtime Studio, event bus, and handoff paths unchanged

---

## Next Step

Re-run live post-processing on run `cb_e2e_20260614_195440_8bf41b6b` (or equivalent E2E) to produce a **complete publishable video** with full 4-clip duration, visible subtitles, audible layers, and `delivery_status: PASS` or explicit FAIL with no false `publish_completed`.
