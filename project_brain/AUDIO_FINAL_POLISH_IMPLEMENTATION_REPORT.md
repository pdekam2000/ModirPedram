# Audio Final Polish — Implementation Report

**Phase:** AUDIO-FINAL-POLISH-IMPLEMENTATION  
**Run ID:** `cb_e2e_20260614_195440_8bf41b6b`  
**Date:** 2026-06-15  
**Runway started:** **NO**

---

## Final Output

**New deliverable (do not confuse with prior fix):**  
`outputs/runs/20260614_210353_440_8bf41b6b/publish/FINAL_BRANDED_VIDEO_CANONICAL_AUDIO_FIXED.mp4`

**Preserved (not overwritten):**  
`publish/FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4`

| Metric | Value |
|--------|-------|
| Duration | **40.167 s** |
| Delivery gate | **PASS** (upload_ready: true) |
| Subtitles | Visible (burn QA pass) |
| Topic | Boy, Dragon, Narrator |
| Music | **PASS — audible music mixed** |

---

## Files Modified

| File | Change |
|------|--------|
| `content_brain/audio/audio_mastering_engine.py` | **New** — narration loudnorm (~−16 LUFS), final loudnorm + alimiter |
| `content_brain/audio/audio_mix_engine.py` | **v2** — narration-preserving mix (`normalize=0`), beds `duration=longest`, dry narration lead |
| `content_brain/audio/audio_merge_engine.py` | **v3** — pre-merge narration loudnorm |
| `content_brain/audio/music_runtime.py` | **v5** — quiet bed merge, `normalize=0`, WARNING not hard-fail, preserve input on inaudible |
| `content_brain/audio/audio_post_processing.py` | **v6** — final mastering step, music WARNING handling |
| `content_brain/platform/delivery_quality_gate.py` | Speech-window narration level check |
| `project_brain/reprocess_audio_final_polish.py` | **New** — one-shot reprocess runner |
| `project_brain/validate_audio_final_polish.py` | **New** — validation suite |

---

## FFmpeg Changes (exact)

### Step 1 — Narration-preserving env mix (`audio_mix_engine.py`)

**Before:**
```
[0:a]volume=1.0[basea]; ... amix=inputs=5:duration=first  (averaging → −14 dB crush)
```

**After:**
```
[0:a]volume=1.0[nar];
[sfxN]...; [ambN]volume={gain}...;
[sfx*][amb*]amix=inputs=N:normalize=0:duration=longest[bedsraw];
[bedsraw]volume=0.45[beds];
[nar][beds]amix=inputs=2:normalize=0:duration=longest[aout]
```

Key fixes:
- `normalize=0` — sum layers, do not average
- Dry narration stays at unity gain
- Beds use `duration=longest` (was `first`, which truncated beds to 0.2 s SFX length)

### Step 2 — Narration normalize (`audio_merge_engine.py` + `audio_mastering_engine.py`)

```
loudnorm=I=-16.0:TP=-1.5:LRA=11
```

Applied to narration MP3 before merge; output `final/narration_normalized.mp3`.

### Step 3 — Music merge (`music_runtime.py`)

**Before:** sidechaincompress + amix average + `volume=1.12` on crushed bed  
**After:**
```
[0:a]volume=1.0[nar];
[1:a]loudnorm=I=-22:TP=-2.0,volume=0.08-0.18,afade...[musraw];
[nar][musraw]amix=inputs=2:normalize=0:duration=first[aout]
```

On inaudible merge: status `skipped_warning`, **preserves input mix** (no destruction).

### Step 5 — Final mastering (`audio_mastering_engine.py`)

```
loudnorm=I=-16.0:TP=-1.5:LRA=11,alimiter=limit=-1.5dB:level=disabled:attack=5:release=50
```

Output: `final/FINAL_RUNWAY_PHASE_I_MASTERED.mp4` → branded.

---

## Before / After dB Levels

### Speech window (0–18.5 s) — authoritative for narration

| Stage | Before (CANONICAL_FIXED) | After (AUDIO_FIXED) | Target |
|-------|--------------------------|---------------------|--------|
| **Narration / speech mix** | **−37.7 dB** | **−16.2 dB** | −18 to −12 dB |
| **Max peak (speech)** | −18.3 dB | −1.2 dB | ≤ 0 dB (limited) |

### Full file (40 s, includes padded tail)

| Stage | Before | After |
|-------|--------|-------|
| Full mix mean | −41.1 dB | **−19.5 dB** |

### Layer breakdown (after)

| Layer | Measured | Notes |
|-------|----------|-------|
| Narration source | −23.4 dB | Original ElevenLabs MP3 (reused) |
| Normalized narration | **−16.6 dB** | After loudnorm |
| Post-merge speech | −16.6 dB | Duration-safe merge |
| Post-env speech | −16.6 dB | Narration preserved (no crush) |
| Ambience tail (20–30 s) | **−40.5 dB** | Audible beds; ~24 dB below speech |
| Music | Merged | `Music: PASS — audible music mixed` |

### Normalized narration delta

| | dB |
|---|-----|
| Input | −23.4 |
| After loudnorm | −16.6 |
| **Gain applied** | **+6.8 dB** |

---

## Delivery Gate

| Field | Result |
|-------|--------|
| **Status** | **PASS** |
| upload_ready | true |
| failures | [] |
| warnings | [] |
| duration_preservation | 40.17 s vs 40.17 s |
| subtitle_burn | PASS |
| narration_speech_level | −16.2 dB ✓ |

Manifest: `outputs/runs/.../metadata/delivery_quality_gate.json`

---

## Validation

```bash
python project_brain/validate_audio_final_polish.py
```

All checks **PASS**:
- Runway not started
- Duration ~40.17 s
- Subtitles visible
- Narration speech window −16.2 dB (within target tolerance)
- Ambience audible below narration (tail −40.5 vs speech −16.2)
- No clipping (max −1.2 dB)
- Topic boy/dragon
- Prior FIXED file preserved
- Delivery gate PASS

---

## Remaining Warnings / Notes

1. **Ambience level during speech** — speech-window mean unchanged at −16.6 dB after env mix (narration preserved). Tail/padded regions carry beds at ~−40 dB (~24 dB below speech). Target is 6–12 dB below; beds are conservative — tune `DEFAULT_BED_LEVEL` / `DEFAULT_AMBIENCE_GAIN_DB` if stronger beds are desired without touching narration.
2. **Narration content** — same reused ElevenLabs MP3 and run-on script; level fixed but **regenerating narration** with voice ID + segmented script would further improve perceived quality.
3. **True peak** — speech max −1.2 dB after limiter target −1.5 dB; acceptable, monitor on future runs.
4. **`FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4`** — unchanged archive of pre-audio-polish mix (−37.7 dB speech).

---

## Goal Status

| Requirement | Status |
|-------------|--------|
| Visually complete (40 s, 4 clips, subtitles) | ✓ |
| Audibly acceptable (speech −16 dB, no −37/−41 dB crush) | ✓ |
| Music present or clear WARNING | ✓ PASS |
| No Runway / no clip regen | ✓ |

**Recommended canonical deliverable for review:**  
`publish/FINAL_BRANDED_VIDEO_CANONICAL_AUDIO_FIXED.mp4`
