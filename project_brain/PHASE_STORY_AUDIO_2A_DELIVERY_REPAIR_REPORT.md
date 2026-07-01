# PHASE STORY-AUDIO-2A — Delivery Layer Repair Report

**Run:** `cb_e2e_20260611_225308_dc20bc1f`  
**Run folder:** `outputs/runs/20260611_235927_308_dc20bc1f`  
**Deliverable:** `publish/FINAL_BRANDED_VIDEO_v4.mp4`  
**Date:** 2026-06-13

---

## Executive summary

Generation was succeeding; **delivery was failing**. The primary root cause was an ffmpeg `amix` filter using `duration=first`, which truncated the cinematic mix to the length of the first dialogue input (~1.4 s) and left ~10.5 s of near-silence (−91 dB) in the final MP4.

Repairs were limited to the **delivery layer** (mix, timeline fit, verification, subtitle burn, recovery). No Runway, browser, provider router, or story-planning engines were modified.

**Reality validation on v4: PASS** — Whiskers, Sage, and Narrator are audible across the full 12 s bed; music and ambience are measurable; subtitles are visibly burned into the final MP4.

---

## Root causes

### 1. Audio mix truncation (`duration=first`)

**Proof (broken v3 chain):** legacy mix ended with:

```text
amix=inputs=N:duration=first:...
```

**Effect:** Mix length locked to first delayed dialogue clip (~1.44 s). Subsequent clips, music, and ambience were generated on disk but **never reached** `FINAL_CINEMATIC_AUDIO.mp3` after `apad`/`atrim` padded silence to 12 s.

**Proof (repaired chain):** `audio/audio_delivery_report.json` now records:

```text
amix=inputs=12:duration=longest:dropout_transition=0:normalize=0,atrim=0:12.000,loudnorm=...
```

### 2. Timeline overflow without scaling (secondary)

Nine dialogue clips exceeded 12 s at natural pacing. Runtime timeline now scales clip lengths and gaps (`dialogue_timeline_builder_v3`) so all lines fit within video duration.

### 3. Subtitle burn verification mismatch

ASS/SRT existed and branding metadata claimed `burn_visible_enough: true`, but the delivery auditor used a **bright-pixel-only** probe on the final MP4 that did not match the burn engine’s before/after PSNR method. Subtitle burn itself was repaired (`subtitle_burn_engine_v5`, `\c` highlight tags, `original_size` + `force_style`); the auditor now uses `compare_subtitle_burn_visibility` against the cinematic reference video.

---

## Files fixed / added

| File | Change |
|------|--------|
| `content_brain/audio/cinematic_audio_mixer.py` | v2 — `duration=longest`, env `atrim` to full duration, writes `audio_delivery_report.json` |
| `content_brain/audio/dialogue_timeline_builder.py` | v3 — scale clips/gaps to fit video duration |
| `content_brain/audio/audio_delivery_verifier.py` | **NEW** — per-line placement + spectral music/env checks |
| `content_brain/quality/delivery_reality_auditor.py` | **NEW** — fail-closed MP4 reality audit (no metadata-only PASS) |
| `content_brain/audio/cinematic_audio_runtime.py` | v2 — delivery audit wired; audio-only check during mix stage |
| `content_brain/audio/dialogue_to_speech_engine.py` | Reuse existing dialogue clips (no credits on recovery) |
| `content_brain/branding/subtitle_format_engine.py` | `\1c` → `\c`, multi-sample visibility |
| `content_brain/branding/subtitle_burn_engine.py` | v5 — `original_size`, `force_style`, visibility proof |
| `content_brain/branding/branding_runtime.py` | `FINAL_BRANDED_VIDEO_V4_NAME` |
| `content_brain/audio/audio_post_processing.py` | `delivery_reality_audit` field |
| `project_brain/recover_story_audio_delivery.py` | **NEW** — remix + subtitle burn + branding → v4 |

---

## Before / after metrics (v3 vs v4)

| Metric | Before (v3 / broken mix) | After (v4 / repaired) |
|--------|--------------------------|------------------------|
| **Mix duration** | 12.0 s (container) | 12.0 s |
| **Audible speech window** | ~0–1.5 s only | 0–11.9 s (9 lines placed) |
| **Tail segment mean dB** | −91.0 (silent) | −16.6 (active bed) |
| **Speakers audible** | 1 (Whiskers only) | 3 (Whiskers, Sage, Narrator) |
| **Dialogue lines audible** | 1 / 9 | 9 / 9 |
| **Music contribution (4.2–9.0 s)** | −91.0 dB (inaudible) | −16.2 dB (audible) |
| **Ambience spectral ratio** | 0.28 (present early only) | 0.25 across full bed |
| **ffmpeg mix mode** | `duration=first` | `duration=longest` |
| **Subtitles on final MP4** | Not visible (bright-ratio probe) | Visible (PSNR vs cinematic ref ≤ 42 dB) |

---

## Task completion

| Task | Status | Artifact |
|------|--------|----------|
| 1 — Trace clips → mix → report | ✅ | `audio/audio_delivery_report.json` |
| 2 — Timeline speaker verification | ✅ | 3 planned / 3 audible |
| 3 — Fix audio duration logic | ✅ | 12.0 s ±0 s, no silent tail |
| 4 — Environment delivery verification | ✅ | spectral ratio 0.25, −14.8 dB |
| 5 — Music delivery verification | ✅ | −16.2 dB in music window |
| 6 — Subtitle delivery verification | ✅ | MP4 before/after PSNR check |
| 7 — `delivery_reality_auditor.py` | ✅ | fail-closed, perceptual checks |
| 8 — `recover_story_audio_delivery.py` | ✅ | v4 created; v1–v3 preserved |
| 9 — Reality validation | ✅ | `delivery_reality_auditor` PASS on v4 |

---

## Recovery

```powershell
python project_brain/recover_story_audio_delivery.py
```

**Outputs:**

- `audio/FINAL_CINEMATIC_AUDIO.mp3` (remixed)
- `final/FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4` (remuxed)
- `final/FINAL_BRANDED_VIDEO_v4.mp4`
- `publish/FINAL_BRANDED_VIDEO_v4.mp4`
- `audio/audio_delivery_report.json`

**Preserved (not overwritten):** `FINAL_BRANDED_VIDEO.mp4`, `_v2.mp4`, `_v3.mp4`

---

## Reality audit results (v4)

```json
{
  "status": "PASS",
  "checks": {
    "dialogue_delivered": true,
    "whiskers_audible": true,
    "sage_audible": true,
    "narrator_audible": true,
    "voices_delivered": true,
    "music_delivered": true,
    "ambience_delivered": true,
    "subtitles_delivered": true,
    "duration_match": true,
    "tail_not_silent": true
  }
}
```

---

## Success criterion

**Final MP4 now matches the Story Package perceptually**, not merely on disk as generated assets. v4 carries all three character voices, music, ambience, and visible subtitles through the full 12 s runtime.
