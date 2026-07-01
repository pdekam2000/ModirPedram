# FORENSIC AUDIO PIPELINE REPORT

**Phase:** FORENSIC-AUDIO-1 (read-only)  
**Run ID:** `cb_e2e_20260611_225308_dc20bc1f`  
**Run folder:** `outputs/runs/20260611_235927_308_dc20bc1f`  
**Subject file:** `publish/FINAL_BRANDED_VIDEO_v4.mp4`  
**Date:** 2026-06-13

---

## Executive summary

| User report | Forensic verdict |
|-------------|------------------|
| Two voices speaking over each other | **TRUE on v4** — caused by dialogue clip spill in the cinematic mixer, not by two separate pipeline mixes |
| Subtitles still not visible | **TRUE** — ASS/SRT exist; burned pixels are not human-visible on the MP4 |
| Multiple pipelines running simultaneously | **TRUE at project level** — legacy narrated path, cinematic path, and stale manifests/UI references coexist; **v4 itself uses one cinematic chain only** |

---

## TASK 1 — Complete chain for `FINAL_BRANDED_VIDEO_v4.mp4`

```
Runway clips (3)
  downloads/runway/runway_clip_*.mp4
    ↓ assembly
final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4          (silent assembled video, 12 s used)
    ↓ cinematic video+audio merge
audio/dialogue/*.mp3 (9 clips, reused ElevenLabs)
    ↓ mix (ffmpeg amix duration=longest)
audio/FINAL_CINEMATIC_AUDIO.mp3               (−16.4 dB, 12.0 s)
    ↓ merge audio into video
final/FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4      (SHA256 E3403EA0…, −16.4 dB)
    ↓ subtitle burn (branding staging)
final/branding_staging/FINAL_RUNWAY_PHASE_I_SUBTITLED.mp4
    ↓ CTA overlay (drawtext "Follow for more" @ 10–12 s)
final/branding_staging/cta_overlay.mp4
    ↓ copy
final/FINAL_BRANDED_VIDEO_v4.mp4              (SHA256 1618B280…)
    ↓ copy
publish/FINAL_BRANDED_VIDEO_v4.mp4            (byte-identical to final copy)
```

| Stage | Source file | Role |
|-------|-------------|------|
| **Input video** | `final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` | Assembled Runway footage |
| **Audio source** | `audio/FINAL_CINEMATIC_AUDIO.mp3` | Mixed dialogue + ambience + music |
| **Branding input** | `final/FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4` | **Not** `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` |
| **Subtitle source** | `publish/subtitles/subtitles.ass` → staged `final/burn_subtitles.ass` | ASS burned via ffmpeg `subtitles=` filter |
| **Publish source** | `final/FINAL_BRANDED_VIDEO_v4.mp4` | Copied to `publish/` |

**Branding manifest proof:** `project_brain/runtime_state/runway_phase_i_branding_manifest.json`  
→ `branded_video_name`: `FINAL_BRANDED_VIDEO_v4.mp4`  
→ subtitle step `input_path`: `final/FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4`

---

## TASK 2 — What audio is inside v4?

**Answer: B — `FINAL_CINEMATIC_AUDIO.mp3` audio (via cinematic remux)**

| Comparison | Pearson correlation |
|------------|---------------------|
| v4 extracted audio vs `FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4` | **1.000** |
| v4 vs `FINAL_CINEMATIC_AUDIO.mp3` | **0.996** |
| v4 vs `final/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | **0.002** |
| v4 vs `publish/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | **0.301** |

| File | Mean loudness | Duration |
|------|---------------|----------|
| v4 | −16.4 dB | 12.0 s |
| `FINAL_CINEMATIC_AUDIO.mp3` | −16.4 dB | 12.0 s |
| `FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4` | −16.4 dB | 12.0 s |
| `publish/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` (legacy) | −25.7 dB | 12.0 s |
| `final/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` (legacy) | −23.6 dB | 11.78 s |
| `publish/narration/narration.mp3` (legacy) | −25.7 dB | 12.0 s |

v4 does **not** contain a simultaneous mix of narrated + cinematic tracks. It is a **single** AAC stream derived from the cinematic bed.

---

## TASK 3 — Every audio file contributing to v4

The v4 audio stream is one premixed bed. Constituents baked into `FINAL_CINEMATIC_AUDIO.mp3`:

### Dialogue clips (9 inputs to mixer)

| Path | Duration | Mean loudness |
|------|----------|---------------|
| `audio/dialogue/whiskers_001.mp3` | 1.44 s | −23.2 dB |
| `audio/dialogue/sage_001.mp3` | 1.39 s | −23.4 dB |
| `audio/dialogue/narrator_001.mp3` | 3.30 s | −24.3 dB |
| `audio/dialogue/sage_002.mp3` | 1.58 s | −23.0 dB |
| `audio/dialogue/whiskers_002.mp3` | 1.95 s | −25.6 dB |
| `audio/dialogue/narrator_002.mp3` | 3.20 s | −24.3 dB |
| `audio/dialogue/whiskers_003.mp3` | 1.95 s | −22.7 dB |
| `audio/dialogue/sage_003.mp3` | 1.21 s | −23.6 dB |
| `audio/dialogue/narrator_003.mp3` | 2.88 s | −24.5 dB |

### Environment layers (2 resolved in mix)

| Path | Duration (looped/trimmed) | Volume in mix |
|------|---------------------------|---------------|
| `assets/audio/ambience/forest_birds.mp3` | 12.0 s | 0.14 |
| `assets/audio/ambience/wind_leaves.mp3` | 12.0 s | 0.14 |

### Music (1 input)

| Path | Duration (looped/trimmed) | Volume in mix |
|------|---------------------------|---------------|
| `assets/audio/music/whimsical_adventure.mp3` | 12.0 s | ~0.385 avg |

### Final mixed output (what v4 carries)

| Path | Duration | Mean loudness |
|------|----------|---------------|
| `audio/FINAL_CINEMATIC_AUDIO.mp3` | 12.0 s | −16.4 dB |

**ffmpeg mix proof** (`audio/audio_delivery_report.json`):

```text
[d0..d8] adelay + volume (9 dialogue)
[e9,e10] atrim=0:12 env layers
[m11] atrim=0:12 music with fade
amix=inputs=12:duration=longest → atrim=0:12 → loudnorm
```

---

## TASK 4 — Branding input video

**Branding uses `FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4` — not `FINAL_RUNWAY_PHASE_I_NARRATED.mp4`.**

Evidence:

- `runway_phase_i_branding_manifest.json` → subtitle step `input_path` = cinematic
- `branding_runtime.py` selects `audio_post_result.narrated_video_path`, which for cinematic runs is set to the cinematic video path
- v4 audio correlates 1.0 with cinematic, ~0 with legacy narrated

`FINAL_RUNWAY_PHASE_I_NARRATED.mp4` still exists on disk (two variants: `final/` and `publish/`) from **earlier legacy post-processing** but is **not** in the v4 chain.

---

## TASK 5 — Manifest paths and stale references

**Run ID (consistent):** `cb_e2e_20260611_225308_dc20bc1f`

| Manifest | Path | Points to | Stale? |
|----------|------|-----------|--------|
| **Audio (runtime)** | `project_brain/runtime_state/runway_phase_i_audio_manifest.json` | `narrated_video_path` → **CINEMATIC**; `narration_audio_path` → `FINAL_CINEMATIC_AUDIO.mp3` | Current for cinematic path |
| **Cinematic (run-local)** | `outputs/.../audio/cinematic_audio_manifest.json` | v2 mix + delivery audit | Current |
| **Branding (runtime)** | `project_brain/runtime_state/runway_phase_i_branding_manifest.json` | **`FINAL_BRANDED_VIDEO_v4.mp4`** | Current |
| **Publish (runtime)** | `project_brain/runtime_state/runway_phase_i_publish_manifest.json` | **`FINAL_BRANDED_VIDEO_v3.mp4`** | **STALE** |
| **Publish (run-local)** | `outputs/.../metadata/publish_manifest.json` | **`FINAL_BRANDED_VIDEO_v3.mp4`** | **STALE** |

### UI / asset library resolution (why user may not see v4)

`content_brain/platform/results_run_loader.py` picks the first existing candidate:

1. `publish_manifest.branded_video_path` → **v3** ✓ (wins)
2. `publish/FINAL_BRANDED_VIDEO.mp4`
3. `branding_manifest.final_branded_video_path` → v4 (never reached)

**Result:** Results UI `final_branded_video_path` resolves to **v3**, not v4.

`assets/asset_index.json` — all registered assets reference **`FINAL_BRANDED_VIDEO_v3.mp4`**.

Default `subtitled_video_path` in results loader falls back to **`FINAL_RUNWAY_PHASE_I_NARRATED.mp4`** when unset — a third stale pointer.

### Coexisting deliverables in one run folder

| File | Audio bed | Mean dB | Role |
|------|-----------|---------|------|
| `FINAL_BRANDED_VIDEO.mp4` | legacy | varies | v1 |
| `FINAL_BRANDED_VIDEO_v2.mp4` | legacy | varies | v2 |
| `FINAL_BRANDED_VIDEO_v3.mp4` | broken cinematic (−25.7 dB) | UI default | **what UI/assets show** |
| **`FINAL_BRANDED_VIDEO_v4.mp4`** | fixed cinematic (−16.4 dB) | recovery output | **not wired to UI/publish manifest** |
| `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | legacy narration | −23.6 / −25.7 dB | orphan pipeline artifact |
| `FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4` | cinematic | −16.4 dB | v4 parent |

---

## TASK 6 — Subtitle burn verification (MP4 frames, not ASS)

Lower-third crop (bottom 24% of frame) sampled on **`publish/FINAL_BRANDED_VIDEO_v4.mp4`**:

| Time | Active SRT cue | White pixel ratio (R,G,B > 210) | v4 vs cinematic pixel change | Visible subtitle bbox? |
|------|----------------|----------------------------------|------------------------------|------------------------|
| **1 s** | Sage: "Be careful, Whiskers!" | **0.010%** | 0.007% | **NO** — bbox is scene geometry, not text |
| **3 s** | Narrator: "The adventure had begun…" | **0.029%** | 0.039% | **NO** |
| **5 s** | Whiskers: "I think something is calling us." | **0.004%** | 0.034% | **NO** |
| **8 s** | Whiskers: "I can carry it!…" | **0.029%** | 0.21% | **NO** — large bbox is bright scene content |

Same measurements on `FINAL_RUNWAY_PHASE_I_SUBTITLED.mp4` vs cinematic: **white ratio unchanged** (0.003–0.029%). Subtitle burn step did not add readable white lower-third text.

**ASS file exists and is timed correctly** (`final/burn_subtitles.ass`, font 58, MarginV 179), but **ffmpeg `subtitles=` output is not visually present** on the MP4.

Branding metadata claims `burn_visible_enough: true` (PSNR ≤ 42 dB vs cinematic) — that threshold detects **imperceptible** re-encode drift, not readable subtitles.

At **8 s**, the only visible lower-third addition is the **CTA drawtext** ("Follow for more", orange, 10–12 s) — not dialogue subtitles.

---

## Answers to the three “why” questions

### Why the user hears overlapping voices

**On v4 (cinematic path):** The mixer places clips with `adelay` but **does not trim** each clip to its timeline window. Timeline v3 scaled windows to fit 12 s, but full clip files are longer:

| Handoff | Spill into next line |
|---------|----------------------|
| Whiskers → Sage @ 0.907 s | **0.533 s** overlap |
| Sage → Narrator @ 1.784 s | **0.516 s** overlap |
| Narrator → Sage @ 3.860 s | **1.221 s** overlap |
| (every subsequent handoff) | **0.45–1.22 s** overlap |

At most transitions, **two (sometimes three) dialogue clips play simultaneously** while the previous clip’s tail is still audible. This is a **delivery/mix scheduling defect**, not two pipelines mixed together.

**If the user is playing v3 from UI/assets:** v3 carries the **old truncated mix** (−25.7 dB, effectively one voice then silence) — overlap is less likely; the complaint would instead match v4 or direct cinematic playback.

### Why subtitles are still missing

1. **ASS/SRT are generated** and staged correctly.
2. **ffmpeg subtitle burn does not produce visible text** on the MP4 — white-pixel ratio stays ~0.01% at all dialogue timestamps; subtitled and cinematic frames are nearly identical.
3. **Automated PASS is a false positive** — PSNR-based visibility compares cinematic vs subtitled and passes on negligible pixel drift (~39–41 dB), not on readable text.
4. **UI still points at v3**, which also has no visible dialogue subtitles (same burn issue on shared staging path).

### Whether multiple pipeline generations are mixed together

**Inside v4:** **No.** Single chain: cinematic mix only (correlation 1.0 with cinematic, ~0 with narrated).

**Inside the project/run folder:** **Yes — operationally.**

| Pipeline generation | Artifacts still present | Referenced by |
|--------------------|-------------------------|---------------|
| Legacy narrated | `FINAL_RUNWAY_PHASE_I_NARRATED.mp4`, `publish/narration/narration.mp3` | publish manifest `narrated_video_path`, results loader fallback |
| Cinematic v1 (broken mix) | `FINAL_BRANDED_VIDEO_v3.mp4` | **publish manifest, asset index, UI primary path** |
| Cinematic v2 (fixed mix) | `FINAL_BRANDED_VIDEO_v4.mp4`, `FINAL_CINEMATIC_AUDIO.mp3` | branding manifest only |

The user can simultaneously have:

- UI opening **v3** (broken audio, one voice)
- Recovery output **v4** on disk (fixed level, overlap bug)
- Stale **narrated** files suggesting a second pipeline
- Manifests disagreeing on which branded file is canonical

This is **reference fragmentation**, not literal dual-audio muxing in one file.

---

## Forensic conclusions

1. **v4 audio = `FINAL_CINEMATIC_AUDIO.mp3`** remuxed once. Not narrated. Not dual-pipeline.
2. **Overlapping voices on v4** = dialogue clips untrimmed after timeline scaling; predictable at every speaker handoff.
3. **Subtitles absent on MP4** = burn step fails visually despite ASS existing; audit PASS is misleading.
4. **Multiple pipelines coexist in manifests/UI**, with **v3 still canonical** for publish/UI/assets while **v4 exists only from manual recovery**.

---

## Recommended viewing path for verification

To hear/see what this forensic report analyzed:

```
outputs/runs/20260611_235927_308_dc20bc1f/publish/FINAL_BRANDED_VIDEO_v4.mp4
```

Do **not** use the Results UI default path (resolves to v3) or asset library copies (also v3).

---

*Read-only forensic pass. No code changes. No fixes applied.*
