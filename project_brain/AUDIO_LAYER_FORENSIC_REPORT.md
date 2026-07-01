# Audio Layer Forensic Report

**Phase:** DELIVERY-QUALITY-RECOVERY — Priority 5  
**Run:** `cb_e2e_20260614_195440_8bf41b6b`  
**Canonical deliverable:** `publish/FINAL_BRANDED_VIDEO_CANONICAL.mp4`  

Measurements: `ffmpeg -af volumedetect` (2026-06-14 inspection).

---

## Layer summary

| Layer | Generated | Skipped | Merged | Audible in deliverable | Mean dB |
|-------|-----------|---------|--------|------------------------|---------|
| **Narration** | YES | NO | YES | YES (primary) | **−33.9** (final branded) |
| **Environment / ambience** | Planned YES | NO | YES | **NO / barely** | (contributes to −33.9 combined) |
| **SFX** | Planned YES | NO | YES | **NO / barely** | same mix |
| **Music** | Asset exists | **YES** | NO | NO | N/A in deliverable |
| **Character voices** | Dialogue in package only | **YES** | NO | NO | N/A |

---

## 1. Narration

| Field | Value |
|-------|-------|
| **Generated?** | YES |
| **Provider** | ElevenLabs (`narration_engine_v2`, status `completed`) |
| **File** | `publish/narration/narration.mp3` (298 KB) |
| **Duration** | 18.552 s |
| **Waveform** | Not silent |
| **Mean volume (MP3)** | **−23.4 dB** |
| **Max volume (MP3)** | **−3.9 dB** |
| **Merged?** | YES — `merge_narration_into_video()` → `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` |
| **Pipeline stage** | `audio_post_processing` → merge step |
| **Attached how** | Single mono AAC stream muxed with `-shortest` (truncated video to match) |

**After merge:**

| File | Mean dB | Max dB |
|------|---------|--------|
| `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | −23.5 | −4.1 |

**In deliverable:** YES — narration is the dominant audible content.

---

## 2. Character voices

| Field | Value |
|-------|-------|
| **Dialogue generated?** | YES in story package (Whiskers/Sage lines) |
| **Voice clips generated?** | NO |
| **Merged?** | NO |
| **Runtime decision** | `character_voice_status: "Character voices skipped: mode off."` |

**Exact logic:** `content_brain/audio/audio_post_processing.py` lines 247–253:

- Profile has `character_voice_mode: "multi_voice"`.
- `voice_cast_plan.character_assignments` contains **only narrator** (1 entry).
- Condition requires `len(character_assignments) > 1` for “multi-voice active”.
- Falls through to **else** branch → misleading **“mode off”** message.

**Cinematic multi-voice path:** Not taken (`cinematic_completed` false — requires `run_dir_path` + story audit PASS in specific layout).

**In deliverable:** NO.

---

## 3. Environment / ambience

| Field | Value |
|-------|-------|
| **Planned?** | YES — 3 ambience tags: forest_birds, wind_leaves, magical_chimes |
| **Resolved files** | `forest_birds.mp3`, `wind_leaves.mp3`, `forest_birds.mp3` (duplicate) |
| **magical_chimes asset** | Missing (warning in story_audio_audit) |
| **Merged?** | YES — `mix_environment_and_sfx()` → `FINAL_RUNWAY_PHASE_I_ENV.mp4` |
| **Manifest** | `ambience_status: "Ambience: PASS — 3 layer(s)"`, `output_audio_stream_detected: true` |

**Asset levels:**

| Asset | Duration | Mean dB |
|-------|----------|---------|
| `forest_birds.mp3` | 18.0 s | −40.8 |
| `wind_leaves.mp3` | 18.0 s | −38.9 |

**Mix engine:** `content_brain/audio/audio_mix_engine.py`

- `ambience_volume: 0.14` (14%)
- `amix=...:duration=first` + output **`-shortest`**
- Input already 18.46 s after narration truncate

**After env mix:**

| File | Mean dB | vs NARRATED |
|------|---------|-------------|
| `FINAL_RUNWAY_PHASE_I_ENV.mp4` | **−33.9** | ~10 dB quieter than narration-only |

**In deliverable:** Merged into single AAC stream but **likely inaudible** at normal playback (very low bed + loudness drop vs narration-only).

---

## 4. SFX

| Field | Value |
|-------|-------|
| **Planned?** | YES — sparkle, discovery_chime, footsteps_soft |
| **Resolved path** | **All three → `assets/audio/sfx/sparkle.mp3`** |
| **sparkle.mp3 duration** | **0.20 s** |
| **sparkle mean dB** | −32.1 |
| **Merged?** | YES (same env mix as ambience) |
| **Manifest** | `sfx_status: "SFX: PASS — 3 cue(s)"` |

**In deliverable:** Technically mixed; **functionally ineffective** (0.2 s placeholder for all tags).

---

## 5. Music

| Field | Value |
|-------|-------|
| **Generated?** | NO (static file, not synthesized) |
| **Track** | `assets/audio/music/whimsical_adventure.mp3` (30 s, mean **−27.1 dB**) |
| **Merged?** | NO |
| **Skipped why** | `channel_profile.json` → **`music_provider: "none"`** |
| **Runtime status** | `skipped_provider_disabled` |
| **UI label** | `"Music: FAILED — music source silent / merge failed"` (misleading — actually **skipped**) |
| **Output file** | `FINAL_RUNWAY_PHASE_I_MUSIC.mp4` — **does not exist** |

**Logic:** `content_brain/audio/music_runtime.py` → early return at line 235 when provider is `none`.

**In deliverable:** NO.

---

## Audio timeline vs video timeline

| Reference | Duration |
|-----------|----------|
| Assembled silent video | 40.17 s |
| Narration MP3 | 18.55 s |
| All post-merge video | 18.46 s |
| Subtitle cues | 0 – 18.553 s |

All audio layers timed to **~18.5 s world**, not 40 s assembly.

---

## dB measurement table (deliverable chain)

| File | Mean dB | Max dB | Notes |
|------|---------|--------|-------|
| `narration.mp3` | −23.4 | −3.9 | Source narration |
| `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | −23.5 | −4.1 | After narration merge |
| `FINAL_RUNWAY_PHASE_I_ENV.mp4` | −33.9 | −13.7 | After env/SFX mix |
| `FINAL_BRANDED_VIDEO_CANONICAL.mp4` | −33.9 | −13.7 | Same as ENV + CTA (video only change) |

---

## Root causes (audio)

1. **Narration `-shortest` merge** — defines 18 s audio timeline; truncates video.
2. **Music disabled in profile** — provider `none`.
3. **Character voices** — voice cast plan has narrator only; multi-voice branch never activates.
4. **Env mix too quiet** — low asset levels + 0.14 volume + re-mix reduces mean by ~10 dB.
5. **SFX placeholder** — single 0.2 s sparkle file reused for all cues.

**No implementation in this phase.**
