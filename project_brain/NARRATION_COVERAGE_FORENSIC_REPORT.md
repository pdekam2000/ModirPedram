# Narration Coverage — Forensic Report

**Phase:** NARRATION-COVERAGE-FORENSIC  
**Run ID:** `cb_e2e_20260614_195440_8bf41b6b`  
**Run folder:** `outputs/runs/20260614_210353_440_8bf41b6b`  
**Deliverable analyzed:** `publish/FINAL_BRANDED_VIDEO_CANONICAL_AUDIO_FIXED.mp4`  
**Analysis date:** 2026-06-15  
**Runway:** not started (analysis only)

---

## Executive Summary

Narration **does not cover the full 40.17 s video**. Speech ends at **18.55 s**; the remaining **21.62 s** is padded silence plus ambience/music beds. This is **not** because clips 3–4 were left out of the script or because ElevenLabs failed mid-run. All five script segments were synthesized into **one continuous 18.55 s MP3**. The failure is **timing and architecture**: narration is compressed into the first half of the timeline, while clips 3–4 play **without any narrator lines in their time windows**.

**Root cause classification: A + C + D + E** (not B)

| Code | Verdict |
|------|---------|
| **A** Script/audio too short for video duration | **Yes** — 18.55 s speech vs 40.17 s video |
| **B** Synthesis incomplete | **No** — full script present in `narration.mp3` |
| **C** Timing planner broken | **Yes** — subtitles/timing use audio length, merge uses `apad` |
| **D** Clip beats not mapped to clip windows | **Yes** — beats 3–4 spoken at 9–17 s, not at 20–40 s |
| **E** Other (architectural bypass) | **Yes** — per-clip `dialogue_timeline` exists but was not used |

---

## 1. Measured Narration Coverage

### Core durations

| Asset | Duration |
|-------|----------|
| Video (4 clips assembled) | **40.167 s** |
| Narration MP3 (`publish/narration/narration.mp3`) | **18.553 s** |
| Narration in final mix (speech, not silence) | **0.000 → 18.553 s** |
| Silent pad after narration (`apad`) | **18.553 → 40.167 s** (**21.62 s**) |

### Narration window

| Field | Value |
|-------|-------|
| **Narration start** | **0.00 s** |
| **Narration end** | **18.55 s** |
| **Post-narration gap** | **18.55 s – 40.17 s** (no speech; ambience/music only) |

### Per-clip speech presence (final deliverable, volumedetect)

| Clip window | Time range | Mean level | Narration? |
|-------------|------------|------------|------------|
| Clip 1 | 0.00 – 10.04 s | **−16.4 dB** | **Yes** — full clip |
| Clip 2 | 10.04 – 20.08 s | **−16.7 dB** | **Partial** — speech until 18.55 s, then ~1.5 s fade to beds only |
| Clip 3 | 20.08 – 30.12 s | **−40.5 dB** | **No** — ambience only |
| Clip 4 | 30.12 – 40.17 s | **−40.9 dB** | **No** — ambience only |

User report of “~12 seconds” likely reflects **perceived story coverage** (first beat + part of second) or subtitle visibility ending at 18.55 s, not the exact ffprobe speech end. **Measured speech end is 18.55 s**, not 12 s.

### Speech segments (from original script + proportional timing)

Source: `outputs/audio/cb_e2e_20260614_195440_8bf41b6b_narration_script.txt`  
Timing model: `subtitle_timing_engine.generate_timed_subtitles()` — proportional by segment character weight over **audio duration only** (18.55 s).

| Seg | Start | End | Text (abbreviated) |
|-----|-------|-----|------------------|
| 1 | 0.00 s | 5.80 s | Meet our little explorer! … discovery of the dragon egg in the forest |
| 2 | 5.80 s | 9.46 s | The boy hides the egg and faces challenges keeping it secret |
| 3 | 9.46 s | 13.18 s | The dragon egg hatches and the boy bonds with the baby dragon |
| 4 | 13.18 s | 16.90 s | The dragon egg hatches… (duplicate of seg 3) |
| 5 | 16.90 s | 18.55 s | Follow for more adventures. |

### Silent gaps

| Gap | Range | Cause |
|-----|-------|-------|
| **Primary post-speech gap** | 18.55 – 40.17 s | `merge_narration_into_video()` → `apad=whole_dur=40.17` pads silence to preserve video duration |
| Intra-speech micro-pauses | ~0.3–0.95 s between phrases | Natural TTS pacing / breath gaps (silencedetect on MP3) |
| Clip 3–4 windows | 20.08 – 40.17 s | No narration scheduled; only ambience/music |

---

## 2. Comparison: Coverage vs Story / Clips

### Video structure

| Clip | File | Duration | Cumulative end |
|------|------|----------|----------------|
| 1 | `runway_clip_1_session_20260614_201432.mp4` | 10.042 s | 10.04 s |
| 2 | `runway_clip_2_session_20260614_203102.mp4` | 10.042 s | 20.08 s |
| 3 | `runway_clip_3_session_20260614_204752.mp4` | 10.042 s | 30.12 s |
| 4 | `runway_clip_4_session_20260614_210318.mp4` | 10.042 s | 40.17 s |

**Expected narration coverage if one line per clip:** ~10 s per beat → **~40 s total** (or at least one cue per 10 s window).

**Actual narration coverage:** **18.55 s** (~46% of video).

### E2E story brief (`clip_beats` × 4)

From `project_brain/content_brain_test_results/cb_e2e_20260614_195440_8bf41b6b.json`:

1. Boy discovers glowing dragon egg in forest  
2. Boy hides egg from villagers / obstacles  
3. Egg cracks; baby dragon emerges  
4. Boy bonds with hatchling; village suspicion  

### Narration script (canonical copy on disk)

`outputs/audio/cb_e2e_20260614_195440_8bf41b6b_narration_script.txt`:

```
Meet our little explorer! Introduction to the boy and discovery of the dragon egg in the forest
The boy hides the egg and faces challenges keeping it secret
The dragon egg hatches and the boy bonds with the baby dragon
The dragon egg hatches and the boy bonds with the baby dragon
Follow for more adventures.
```

| Clip beat (E2E) | Text in script? | Spoken in clip’s time window? |
|-----------------|-----------------|-------------------------------|
| Beat 1 — discovery | Yes (seg 1) | **Yes** (0–5.8 s, clip 1) |
| Beat 2 — hiding | Yes (seg 2) | **Mostly** (5.8–9.5 s, spans clip 1–2) |
| Beat 3 — hatching | Yes (seg 3) | **Mis-timed** — spoken at 9.5–13.2 s (clip 1–2), **not** during clip 3 (20–30 s) |
| Beat 4 — bonding | Duplicated seg 4 | **Mis-timed** — spoken at 13.2–16.9 s (clip 2), **not** during clip 4 (30–40 s) |

### Story package `dialogue_timeline` (unused for delivery)

`project_brain/story_packages/cb_e2e_20260614_195440_8bf41b6b.json` defines **correct per-clip narrator timing** across 40.17 s:

| Clip | Narrator line start | Text |
|------|---------------------|------|
| 1 | 1.90 s | A boy discovers a glowing dragon egg beneath forest leaves. |
| 2 | 11.94 s | He wraps the egg and hides it from passing travelers. |
| 3 | 21.98 s | Footsteps approach as the egg begins to warm. |
| 4 | 32.03 s | He escapes deeper into the trees clutching the secret. |

This timeline **was not used** for the shipped narration MP3. The delivery path used monolithic `NarrationEngine` + reused MP3, not `run_cinematic_audio_pipeline()`.

---

## 3. Clips 1–2 Only vs Synthesis Failure?

### Answer: Neither in the simple form

| Question | Finding |
|----------|---------|
| Is narration generated **only** for clips 1–2? | **Textually no** — segments 3–4 exist in script and MP3 |
| Is narration **audible** during clips 3–4? | **No** — nothing scheduled after 18.55 s |
| Did synthesis fail for clips 3–4? | **No** — one TTS pass; hatching/bonding lines appear at 9–17 s, not missing from audio file |

**Conclusion:** Clips 3–4 lack narration **at the correct time**, not because TTS skipped them, but because **all lines were read back-to-back in the first 18.5 s** and the merge **padded silence** for the rest.

---

## 4. Artifact Inspection

### `publish/narration/narration_script.txt` (current on run folder)

```
# Narration script unavailable for run cb_e2e_20260614_195440_8bf41b6b
```

**Status:** Corrupted placeholder from a later reprocess/publish step. **Not authoritative.**

### `publish/narration/narration_plan.json` (current)

```json
{
  "narration_audio_path": "",
  "segments": [],
  "narration_script_path": ".../narration_script.txt"
}
```

**Status:** Empty segments / missing audio path — manifest drift after reprocess. **Not authoritative.**

### Authoritative sources

| Artifact | Path | Status |
|----------|------|--------|
| Original script | `outputs/audio/cb_e2e_20260614_195440_8bf41b6b_narration_script.txt` | Valid — 5 segments |
| Narration audio | `publish/narration/narration.mp3` | Valid — 18.553 s |
| Merge metadata | `project_brain/runtime_state/runway_phase_i_audio_manifest.json` | Warns `narration_shorter_than_video_padded_with_silence` |
| Subtitles (latest) | `publish/subtitles/subtitles.srt` | Single cue 0–18.553 s (placeholder text after reprocess) |
| Subtitles (original burn) | `metadata/publish_manifest.json` | Burn window `between(t,0.000,18.553)` with full script prefix |

---

## 5. Per-Clip Verification Matrix

| Clip | Visual time | Narration text exists? | Narration audio in window? | Subtitle timing in window? | Beat aligned? |
|------|-------------|------------------------|----------------------------|----------------------------|---------------|
| **1** | 0 – 10.04 s | Yes | **Yes** | Yes (seg 1–2 start) | **Partial** — discovery OK |
| **2** | 10.04 – 20.08 s | Yes | **Yes** until 18.55 s | Yes until 18.55 s | **Partial** — hiding OK; tail silent |
| **3** | 20.08 – 30.12 s | Yes (in script) | **No** | **No** | **No** — hatching spoken too early (~9–13 s) |
| **4** | 30.12 – 40.17 s | Yes (duplicate) | **No** | **No** | **No** — bonding spoken too early (~13–17 s) |

Each clip **should** have narration text, timing, and audio **per 10 s window**. Only clips 1–2 receive speech; clips 3–4 receive **none in their windows**.

---

## 6. Timeline Diagram

```
Video:     |---- Clip 1 ----|---- Clip 2 ----|---- Clip 3 ----|---- Clip 4 ----|
Time (s):  0              10.04           20.08           30.12           40.17

Narration: [seg1][seg2][seg3][seg4][CTA]
           0    5.8  9.5  13.2  16.9  18.55
Speech:    ████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Silence:   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██████████████████████████████████████
           |<------ 18.55 s speech ------>|<------ 21.62 s padded silence ---->|

Expected   [ beat1 ][ beat2 ][ beat3 ][ beat4 ]
(per clip): 0-10s    10-20s   20-30s   30-40s
Actual:     overlap   overlap   MISSING  MISSING
```

---

## 7. Root Cause Chain (files / functions)

| Step | What happens | Responsible component |
|------|--------------|---------------------|
| 1 | Script builds **5 segments** joined into **one string** | `narration_script_builder.build_narration_script()` |
| 2 | ElevenLabs generates **one MP3** (~18.5 s) for entire script | `NarrationEngine.run()` |
| 3 | Subtitle timing spans cues over **audio duration only** (18.55 s), not video (40.17 s) | `subtitle_timing_engine.generate_timed_subtitles()` — `duration = _probe_audio_duration_seconds()` |
| 4 | Merge pads narration with **`apad=whole_dur=40.17`** — preserves video, adds silence | `audio_merge_engine.merge_narration_into_video()` |
| 5 | Reprocess **reused** original MP3; no per-clip regen | `project_brain/reprocess_audio_final_polish.py` |
| 6 | **Bypass:** `dialogue_timeline` has per-clip 40 s plan but cinematic pipeline not used | `audio_post_processing.run_audio_post_processing()` — `use_cinematic = story_audit.status == "PASS" and run_dir_path` (cinematic path not taken for original delivery / reprocess) |

Merge warning already recorded:

```json
"narration_shorter_than_video_padded_with_silence"
"narration_duration_seconds": 18.552744
"assembled_duration_seconds": 40.166667
```

---

## 8. Root Cause Classification (detailed)

### A) Narration script too short — **YES (duration sense)**

- Script contains all four beats but is read in **~18.5 s total** for a **~40 s** video.
- No pacing rule ties segment duration to `clip_duration × clip_count`.
- CTA segment consumes time without visual counterpart.

### B) Narration synthesis incomplete — **NO**

- `narration.mp3` is 18.553 s with continuous speech; silencedetect shows speech through ~18.2 s.
- Segments 3–4 **are present in the audio**, not missing from synthesis.

### C) Narration timing planner broken — **YES**

- `generate_timed_subtitles()` uses **narration MP3 length** as timeline authority, not assembled video duration or clip boundaries.
- Subtitle burn on latest reprocess: **one cue 0–18.553 s** only.
- No stretch, slot, or per-clip scheduling to 10 s windows.

### D) Clip beats not mapped to narration — **YES**

- `_clip_story_lines()` pulls four beats into segments but **does not assign 10 s windows**.
- Beats 3–4 play during clips 1–2 time range; clips 3–4 play **silent** for narration.
- E2E `clip_beats` and story package `dialogue_timeline` **disagree with delivered timing**.

### E) Other — **YES (architectural bypass)**

- **Duration preservation fix** correctly prioritized video length over `-shortest`, but **`apad` exposes the narration gap** as audible silence.
- **Cinematic multi-voice timeline** (40 s, per-clip offsets) exists in story package but was **not used** for final MP3.
- **Reprocess scripts** reuse monolithic narration to avoid new TTS credits, perpetuating the gap.
- **Publish artifacts** (`narration_script.txt`, `narration_plan.json`, `subtitles.srt`) degraded to placeholders on latest reprocess.

---

## 9. Recommended Fix Direction (analysis only — no implementation)

1. **Time authority:** Subtitles and narration scheduling must use **assembled video duration** and **clip boundaries** (10.04 s × 4), not raw MP3 length alone.
2. **Per-clip synthesis or stretch:** Either generate **four timed narration segments** (one per clip) or time-stretch/pad each segment to fill its 10 s slot before merge.
3. **Use existing `dialogue_timeline`:** Wire cinematic / dialogue timeline offsets (1.9, 11.9, 22.0, 32.0 s) into narration generation when `clip_count == 4`.
4. **Merge strategy:** Replace blind `apad` tail silence with **distributed clip beds** or **segment-level placement** on the 40 s timeline.
5. **Artifact integrity:** Stop overwriting `narration_script.txt` / `narration_plan.json` with placeholders during reprocess.

---

## 10. Conclusion

The video is **40.17 s** with **four 10 s clips**, but narration **ends at 18.55 s**. Clips 3 and 4 play **without narrator speech in their windows** because beats 3–4 were **spoken too early** in a single compressed MP3, then the pipeline **padded 21.6 s of silence** to preserve duration. This is primarily **A + C + D + E**, not failed partial synthesis (**B**).

**No implementation performed in this phase.**
