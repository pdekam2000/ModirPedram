# Duration Preservation Analysis

**Phase:** DELIVERY-QUALITY-RECOVERY — Priority 1  
**Mode:** Analysis only — no implementation  
**Run reference:** `cb_e2e_20260614_195440_8bf41b6b`  

---

## Observed duration loss

| Stage | File | Duration |
|-------|------|----------|
| Runway clips (×4) | `downloads/runway/runway_clip_*_session_20260614_*.mp4` | ~10.04 s each |
| Assembly | `final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` | **40.17 s** (video only, no audio) |
| Narration merge | `final/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | **18.46 s** |
| Environment mix | `final/FINAL_RUNWAY_PHASE_I_ENV.mp4` | **18.46 s** |
| Canonical deliverable | `publish/FINAL_BRANDED_VIDEO_CANONICAL.mp4` | **18.46 s** |
| Narration MP3 | `publish/narration/narration.mp3` | **18.55 s** |

**Loss:** ~21.7 s of video (~54%) removed at narration merge.

---

## Every FFmpeg `-shortest` location

### A. Active Phase I post-processing path (this run)

| # | File | Function | FFmpeg command pattern | Used this run? |
|---|------|----------|------------------------|----------------|
| **1** | `content_brain/audio/audio_merge_engine.py` | `merge_narration_into_video()` | `ffmpeg -y -i {video} -i {narration} -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac **-shortest** {output}` | **YES — root cause** |
| **2** | `content_brain/audio/audio_mix_engine.py` | `mix_environment_and_sfx()` | `... -filter_complex ... amix=...:duration=first ... -map 0:v:0 -map [aout] -c:v copy -c:a aac **-shortest** {output}` | **YES** (preserves already-truncated length) |
| **3** | `content_brain/audio/music_runtime.py` | `run_music_runtime()` | `ffmpeg -y -i {video} -i {music} -filter_complex ... -map 0:v:0 -map [aout] -c:v copy -c:a aac **-shortest** {output}` | **NO** (`music_provider: none`) |

**Caller chain (run):**

```
runway_live_post_processor.run_live_post_processing()
  → run_assembly()                    # no -shortest; produces 40.17 s silent video
  → run_audio_post_processing()
       → merge_narration_into_video() # -shortest truncates to narration length
       → mix_environment_and_sfx()    # -shortest on already-short video
       → run_music_runtime()           # skipped
  → run_branding_runtime()
  → run_publish_package()
```

**Manifest evidence:** `runway_phase_i_audio_manifest.json` → `metadata.merge.ffmpeg_args: "copy_video_aac_audio_shortest"`.

---

### B. Alternate / legacy pipelines (not used in Phase I live post-processor)

| # | File | Function | Command | Notes |
|---|------|----------|---------|-------|
| 4 | `content_brain/execution/assembly_ffmpeg_executor.py` | `_merge_audio()` | `-map 0:v:0 -map 1:a:0 -c:v copy -c:a aac **-shortest**` | Full assembly executor path (session export); separate from `run_assembly()` |
| 5 | `utils/ffmpeg_audio_merger.py` | `FFmpegAudioMerger.merge_audio()` | `-c:v copy -c:a aac **-shortest**` | Legacy utility |
| 6 | `engines/audio_finish_engine.py` | `smooth_audio_finish()` | `-c:v copy -c:a aac **-shortest**` | Legacy fade-out helper |
| 7 | `engines/music_engine.py` | `add_background_music()` | includes **-shortest** | Legacy music engine |

---

### C. Validation / test scripts (non-production)

| File | Purpose |
|------|---------|
| `project_brain/validate_music_real_audibility.py` | Test harness |
| `project_brain/validate_quality_fix_2_recovery_v1.py` | Recovery validation |

---

## Why `-shortest` is used

**Stated intent (inferred from code pattern):**

1. **Avoid A/V length mismatch** — When narration/audio is shorter than video, `-shortest` ends the output when the shortest stream ends, preventing a silent video tail after narration ends.
2. **Safe mux default** — Common FFmpeg recipe for “drop video tail if audio ends first.”
3. **Music/ambience mixes** — Same pattern to bound output when looping ambience or mixing beds.

**Metadata label:** `merge_narration_into_video()` records `ffmpeg_args: "copy_video_aac_audio_shortest"` explicitly.

**Design mismatch for this product:**

- Runway assembly target = `clip_count × 10 s` ≈ **40 s**
- Narration script = **5 segments** timed to ~**18.5 s** (proportional to text, not clip count)
- `-shortest` **always chooses narration length**, discarding clips 3–4 video

---

## Impact map (this run)

```
40.17 s  FINAL_RUNWAY_PHASE_I_VIDEO.mp4     [4 clips concatenated, silent]
   │
   │  merge_narration_into_video()  ← -shortest
   ▼
18.46 s  FINAL_RUNWAY_PHASE_I_NARRATED.mp4  [narration AAC muxed; clips 3–4 gone]
   │
   │  mix_environment_and_sfx()      ← -shortest (no extension)
   ▼
18.46 s  FINAL_RUNWAY_PHASE_I_ENV.mp4       [ambience/SFX mixed; still 18.46 s]
   │
   │  run_music_runtime()            ← skipped (provider disabled)
   │
   │  burn_subtitles()               ← FAIL; base unchanged
   │  apply_cta_overlay()            ← CTA on 18.46 s base
   ▼
18.46 s  FINAL_BRANDED_VIDEO_CANONICAL.mp4  [canonical deliverable]
```

| Clip | Video in assembly | Video in deliverable |
|------|-------------------|----------------------|
| 1 | 0–10 s | 0–10 s (full) |
| 2 | 10–20 s | 10–18.46 s (**partial**) |
| 3 | 20–30 s | **absent** |
| 4 | 30–40 s | **absent** |

---

## Secondary duration coupling

| System | Behavior | Effect |
|--------|----------|--------|
| `generate_timed_subtitles()` | Times cues to **narration audio** duration (~18.55 s) | Subtitles align to truncated timeline, not 40 s video |
| `assembly_manifest` | No `duration_seconds` field written | Downstream uses subtitle/narration duration, not assembled video duration |
| `audio_post_processing` | `duration_seconds` from subtitle generator | Reinforces 18 s as “truth” after merge |

---

## Recommended fix direction (design only — not implemented)

1. **Video-authoritative merge** for multi-clip Runway assembly: mux narration to full video length (pad/loop/attenuate tail), not `-shortest`.
2. **Narration timing** must span `clip_count × clip_duration` before merge, or merge must use `-t` / `apad` aligned to video duration.
3. **Gate:** fail publish if `duration(final) < duration(assembled) - tolerance`.
4. Audit legacy paths (#4–7) if any can still feed production.

---

**Next step:** Approve duration-preservation fix scope before changing `audio_merge_engine.py`.
