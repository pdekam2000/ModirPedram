# Audio Final Polish — Forensic Report

**Phase:** AUDIO-FINAL-POLISH-FORENSIC  
**Deliverable analyzed:** `outputs/runs/20260614_210353_440_8bf41b6b/publish/FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4`  
**Run ID:** `cb_e2e_20260614_195440_8bf41b6b`  
**Duration:** 40.17 s (narration active ~18.5 s; remainder silence-padded)  
**Analysis date:** 2026-06-03  
**Method:** `ffmpeg -af volumedetect` on full file and speech-only segments (0–18.5 s)

---

## Executive Summary (60-second read)

The fixed video **preserves full duration**, but audio is **unacceptable** because the **environment mix crushes narration by ~14 dB** during the speech window. The final branded file inherits that crushed mix unchanged. **Music never reaches the deliverable** — merge ran, failed audibility, and the pipeline kept the env-mixed path.

Root cause is **not a single bug**. It is **E) all of the above**, dominated by **B) bad mix** and **D) wrong volume coefficients**, with contributing **A) weak narration source** and **C) no mastering stage**.

| Priority | Finding |
|----------|---------|
| **#1 blocker** | `amix` in `mix_environment_and_sfx()` averages 5 inputs → narration drops **-23.5 → -37.7 dB** in speech |
| **#2** | Narration source already **-23.4 dB** (below -18 dB target); no normalization anywhere |
| **#3** | Music merge fails (`failed_inaudible`); final uses ENV file without music |
| **#4** | Ambience assets very quiet (-39 to -41 dB) + `ambience_volume=0.22` + same `amix` → barely audible |
| **#5** | No limiter / loudnorm / mastering pass in branding or publish |

---

## 1. Measured Audio Levels

### Full-file measurements (misleading for narration due to 21.5 s silence tail)

| Stage | File | Mean dB | Max dB |
|-------|------|---------|--------|
| Narration source | `publish/narration/narration.mp3` | **-23.4** | -3.9 |
| After narration merge | `final/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | -26.8 | -4.1 |
| After env/SFX mix | `final/FINAL_RUNWAY_PHASE_I_ENV.mp4` | **-41.1** | -18.3 |
| After music merge (not used in final) | `final/FINAL_RUNWAY_PHASE_I_MUSIC.mp4` | -46.0 | -23.2 |
| **Final deliverable** | `publish/FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4` | **-41.1** | -18.3 |

Whole-file mean on the 40 s file is **diluted by apad silence** (~-91 dB on tail 19–40 s). Speech-region analysis below is authoritative for narration.

### Speech-region measurements (0–18.5 s — where narration exists)

| Layer | Mean dB | Max dB | Notes |
|-------|---------|--------|-------|
| **Narration (source MP3)** | **-23.4** | -3.9 | ElevenLabs output, reused from first run |
| **Narration (after merge, pre-env)** | **-23.5** | -4.1 | Merge preserves speech level; padding does not affect this window |
| **Narration in final mix (speech window)** | **-37.7** | -18.3 | Same as env-mixed + branded — **−14.2 dB crush** |
| **Ambience (asset: forest_birds)** | -40.8 | -28.8 | Source file, pre-mix |
| **Ambience (asset: wind_leaves)** | -38.9 | -25.1 | Source file, pre-mix |
| **Ambience (effective in deliverable)** | **~buried** | — | Not separable; mid-body (20–30 s) mean **-62.0 dB** |
| **Music (asset: whimsical_adventure)** | -27.1 | -23.7 | Source usable; **not present in final** |
| **Music (failed merge output)** | -46.0 | -23.2 | Rejected; pipeline kept ENV path |
| **Final mix (speech window)** | **-37.7** | -18.3 | Matches env mix — branding did not alter audio |

### Reported layer summary (for targets comparison)

| Layer | Measured (speech window where applicable) | Target | Delta |
|-------|-------------------------------------------|--------|-------|
| **Narration** | **-23.4 dB** (source) / **-37.7 dB** (in final) | -18 to -12 dB | Source: **5.4 dB too quiet**. In final: **19.7–25.7 dB too quiet** |
| **Ambience** | Assets -39 to -41 dB; effective **inaudible vs narration** | 6–12 dB **below** narration | If narration were -15 dB → ambience target **-21 to -27 dB**. Actual: assets quieter than target narration; post-mix ambience not perceptually separable |
| **Music** | **Absent in deliverable** (merge failed at -46 dB) | 8–14 dB below narration | **Missing entirely** in `FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4` |
| **Final mix** | **-41.1 dB** full / **-37.7 dB** speech | Narration-led, layers balanced | **Failed** — narration crushed, music missing, ambience buried |

---

## 2. Pipeline Stage Forensics

```
narration.mp3 (-23.4 dB)
    │
    ▼ merge_narration_into_video()  [audio_merge_engine.py]
    │  apad to 40.17 s + AAC encode
    ▼ FINAL_RUNWAY_PHASE_I_NARRATED (-23.5 dB speech / -26.8 full)
    │
    ▼ mix_environment_and_sfx()  [audio_mix_engine.py]  ◄── PRIMARY DAMAGE
    │  5-input amix (narration + 3 SFX + 2 ambience loops @ 0.22)
    ▼ FINAL_RUNWAY_PHASE_I_ENV (-37.7 dB speech / -41.1 full)
    │
    ▼ run_music_runtime()  [music_runtime.py]  ◄── SECONDARY FAILURE
    │  sidechaincompress + amix → failed_inaudible (-46 dB)
    │  NOT adopted (status ≠ completed + audibility_pass)
    ▼
    ▼ run_branding_runtime()  [branding_runtime.py]
    │  video copy only — no audio filters
    ▼ FINAL_BRANDED_VIDEO_CANONICAL_FIXED (-37.7 / -41.1 dB)
```

### Stage-by-stage delta

| Transition | Δ mean (speech window) | Responsible code |
|------------|----------------------|------------------|
| Source → narrated | **−0.1 dB** | `merge_narration_into_video()` — OK |
| Narrated → env mixed | **−14.2 dB** | `mix_environment_and_sfx()` — **critical** |
| Env → music output | **−8.3 dB** (full file) | `run_music_runtime()` — worsens; output discarded |
| Env → final branded | **0 dB** | Branding — passthrough |

---

## 3. Root Cause Analysis

### A) Bad narration source — **CONTRIBUTING**

| Evidence | Detail |
|----------|--------|
| Level | -23.4 dB mean — **below -18 dB target floor by 5.4 dB** |
| Voice config | `channel_profile.json` → `default_narrator_voice: ""` (empty) |
| Script quality | `narration_script.txt` is one run-on paragraph with duplicated beat and CTA baked in |
| Generation path | Original ElevenLabs run; reprocess **reused** MP3 without regeneration |
| Normalization | **None** in `NarrationEngine.run()` or `elevenlabs_provider.py` post-export |

**Files:** `content_brain/audio/narration_engine.py`, `providers/audio/elevenlabs_provider.py`, `project_brain/product_settings/channel_profile.json`, `publish/narration/narration_script.txt`

User perception (“narration sounds bad”) aligns with weak level + poor script pacing + default/unknown voice.

---

### B) Bad mix — **PRIMARY**

**Smoking gun:** speech-region narration drops **-23.5 → -37.7 dB** at env mix.

`mix_environment_and_sfx()` builds:

```121:122:content_brain/audio/audio_mix_engine.py
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[aout]"
```

For this run, **5 inputs** are averaged:

1. Base narration `[0:a]volume=1.0`
2. SFX × 3 (`sparkle.mp3` at 0.18–0.24 gain, same 0.2 s file)
3. Ambience × 2 (looped `forest_birds`, `wind_leaves` at **0.22** gain)

FFmpeg `amix` **without `normalize=0`** divides energy across inputs (~−14 dB for 5 comparable streams). Quiet ambience loops still participate in the average and **pull narration down** even when beds are faint.

**File:** `content_brain/audio/audio_mix_engine.py` → `mix_environment_and_sfx()`

---

### C) Bad mastering — **CONTRIBUTING**

| Check | Result |
|-------|--------|
| `loudnorm` / `alimiter` in merge | **None** |
| Mastering in music runtime | Only `volume=1.12` on amix output — applied to already-crushed bed |
| Branding / publish | **Video copy only** — no audio pass |
| Delivery gate | Flags `ambience_weak_or_quiet_mix` at -41.1 dB — symptom, not fix |

**Files:** `content_brain/audio/audio_merge_engine.py`, `content_brain/branding/branding_runtime.py`, `content_brain/platform/delivery_quality_gate.py`

---

### D) Wrong volume coefficients — **PRIMARY (with B)**

| Coefficient | Configured | Effect |
|-------------|------------|--------|
| `ambience_volume` | **0.22** (reprocess; was 0.14) | ~−13 dB linear on already −40 dB assets → ~−53 dB beds |
| SFX `volume` | 0.18–0.24 | Same file (`sparkle.mp3`) for all cues — wrong asset + low gain |
| `music_volume` | 0.30 (clamped 0.25–0.35) | Applied to −27 dB music then **sidechain-ducked against −41 dB bed** |
| `ducking_strength` | 0.18 | Feeds ratio 3.5:1 — ducks music under already-crushed narration |
| `amix` default | normalize=1 (average) | **Dominates** — wrong paradigm for “narration-led” mix |

**Files:** `content_brain/audio/audio_mix_engine.py`, `content_brain/audio/music_runtime.py`, `project_brain/reprocess_latest_run_after_quality_fixes.py` (line 235: `ambience_volume=0.22`), `project_brain/product_settings/channel_profile.json`

---

### Music missing — **CONFIRMED**

From `publish/audio/music_debug_manifest.json`:

- Status: **`failed_inaudible`**
- Input to music merge: ENV file at **-41.1 dB**
- Output: **-46.0 dB** (`mixed_output_too_quiet`)
- Reprocess logic only adopts music output when `status == completed` and `audibility_pass` → **final stays ENV-only**

**File:** `content_brain/audio/music_runtime.py` → `run_music_runtime()`; `project_brain/reprocess_latest_run_after_quality_fixes.py` lines 247–248

---

## 4. Problem Classification

**Answer: E) all of the above**

| Code | Verdict | Weight |
|------|---------|--------|
| **A** Bad narration source | Yes — quiet, poor script, empty voice_id, no normalization | Medium |
| **B** Bad mix | Yes — `amix` averaging destroys narration headroom | **Critical** |
| **C** Bad mastering | Yes — no final loudnorm/limiter anywhere | Medium |
| **D** Wrong volume coefficients | Yes — ambience 0.22 into amix, music ducking on crushed bed | **Critical** |
| **E** All of the above | **Confirmed** | — |

---

## 5. Volume Filters & Dynamics Inventory

| Location | Filter | Purpose | Issue |
|----------|--------|---------|-------|
| `audio_merge_engine.py` | `apad=whole_dur` | Pad narration to video length | Creates 21.5 s silence tail → whole-file metrics misleading |
| `audio_merge_engine.py` | AAC encode | Container merge | Minor encode loss (~0.1 dB speech) |
| `audio_mix_engine.py` | `volume=1.0` on base | Narration gain | No boost to target |
| `audio_mix_engine.py` | `volume=0.18–0.24` SFX | Spot effects | Wrong asset; still enters amix average |
| `audio_mix_engine.py` | `volume=0.22` ambience | Bed level | Too low on −40 dB sources |
| `audio_mix_engine.py` | **`amix=inputs=5`** | Combine layers | **Averages → −14 dB narration crush** |
| `music_runtime.py` | `sidechaincompress` | Duck music under voice | Ducking a −41 dB bed makes music inaudible |
| `music_runtime.py` | `amix` + `volume=1.12` | Music bed merge | Cannot recover from crushed input |
| Branding | *(none)* | — | Audio passthrough |

**No limiter or loudnorm exists anywhere in the delivery chain.**

---

## 6. Recommended Implementation Order

*Analysis only — no implementation in this phase.*

| Order | Fix | File(s) | Expected impact |
|-------|-----|---------|-----------------|
| **1** | Replace `amix` averaging with **narration-preserving mix** (`normalize=0`, or duck ambience under dry narration stem) | `content_brain/audio/audio_mix_engine.py` | Restore narration to ~−23 dB in speech window immediately; largest perceptual win |
| **2** | Add **narration loudnorm** to target **−16 dBFS mean** before merge | `content_brain/audio/narration_engine.py` or new pre-merge step in `audio_post_processing.py` | Hit −18 to −12 dB target |
| **3** | **Regenerate narration** with configured `default_narrator_voice`, segmented script per clip beat | `narration_engine.py`, `narration_script_builder.py`, `channel_profile.json` | Fix “sounds bad” quality + pacing |
| **4** | Re-level ambience: boost source gain or use **send/return** (ambience −24 to −30 dB relative to narration, not linear 0.22 into amix) | `audio_mix_engine.py`, `environment_sound_engine.py` | Audible beds without crushing voice |
| **5** | Run music merge **after** narration level restored; fix ducking thresholds for Shorts bed | `music_runtime.py` | Music present at 8–14 dB below narration |
| **6** | Add **final mastering** (`loudnorm` I=-16 LUFS, TP=-1.5) before branding copy | New step in `audio_post_processing.py` or `branding_runtime.py` | Consistent export level |
| **7** | Fail closed if music/ambience inaudible **after** mix fix (gate already partially wired) | `delivery_quality_gate.py` | Prevent shipping quiet mixes |

---

## 7. Artifacts Referenced

| Artifact | Path |
|----------|------|
| Final deliverable | `outputs/runs/20260614_210353_440_8bf41b6b/publish/FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4` |
| Narration source | `.../publish/narration/narration.mp3` |
| Env mix intermediate | `.../final/FINAL_RUNWAY_PHASE_I_ENV.mp4` |
| Music debug | `.../publish/audio/music_debug_manifest.json` |
| Env plan | `.../publish/audio/environment_sound_plan.json` |
| Channel profile | `project_brain/product_settings/channel_profile.json` |

---

## 8. Conclusion

The duration fix worked. Audio failed **downstream of narration merge**, primarily in **`mix_environment_and_sfx()`** where a **5-input `amix` average reduces narration by ~14 dB** during speech. The branded final is a **passthrough** of that crushed mix. Music **never lands** because `run_music_runtime()` receives the crushed bed and fails audibility.

Until the mix architecture changes from **averaging** to **narration-led summing/ducking**, raising `ambience_volume` or enabling local music will not produce an acceptable Shorts mix.

**No implementation was performed in this phase.**
