# FINAL VIDEO FORENSIC AUDIT

**Phase:** FINAL-VIDEO-FORENSIC-AUDIT  
**Mode:** Inspection only — no code changes  
**Date:** 2026-06-14  

---

## Run Under Audit

| Field | Value |
|-------|-------|
| **Run ID** | `cb_e2e_20260614_195440_8bf41b6b` |
| **Topic** | A boy finds a dragon egg in the forest and hides it from everyone |
| **Run folder (delivery)** | `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260614_210353_440_8bf41b6b` |
| **Final video** | `publish\FINAL_BRANDED_VIDEO_CANONICAL.mp4` |
| **Runtime status** | SUCCESS / `publish_completed` |
| **Observed quality** | Poor — incomplete story, missing expected audio layers, no visible subtitles |

---

## Executive Summary

The pipeline reports **SUCCESS** because each stage reached a terminal state (`completed`, `MERGED`, `PUBLISHED_PACKAGE_CREATED`) with **fail-open** behavior on subtitle burn, music, and character voices. The delivered MP4 is **not equivalent** to the assembled Runway output.

**Primary root cause:** Narration merge used FFmpeg **`shortest`**, cutting the **40.17 s** assembled video down to **18.46 s** (narration length). **Clips 3 and 4 are absent** from the final deliverable (~54% of generated video discarded).

**Secondary root causes:**

1. Character dialogue was **planned but never synthesized** (`character voices skipped: mode off`).
2. Background music was **never merged** (`music_provider: none`).
3. Subtitle burn **ran but failed visibility validation** (missing `numpy`); branding continued without visible burned subs.
4. Environment ambience/SFX were mixed at **very low perceived loudness** (~−34 dB mean) — likely inaudible to viewers.
5. Story package contains **template drift** (Whiskers cat / Sage fox / jungle) while narration uses generic beat summaries, not dialogue.
6. AI Director V2 injected **repetitive, garbled shot language** into all clip prompts.

---

## 1. Narration Audit

### Files inspected

| Artifact | Path | Exists | Duration |
|----------|------|--------|----------|
| Narration MP3 (publish) | `publish\narration\narration.mp3` | YES | **18.55 s** |
| Narration MP3 (source) | `outputs\audio\cb_e2e_20260614_195440_8bf41b6b_narration.mp3` | YES | 18.55 s |
| Narration script | `publish\narration\narration_script.txt` | YES | 5 segments |

### Waveform / silence

| Check | Result |
|-------|--------|
| Generated? | **YES** — ElevenLabs, status `completed` |
| Silent file? | **NO** — mean −23.4 dB, max −3.9 dB |
| Audible in final MP4? | **YES but quiet** — final branded mean −33.9 dB |

### Merge into final video

| Stage | Input | Output | Duration |
|-------|-------|--------|----------|
| Assembly | 4 Runway clips | `FINAL_RUNWAY_PHASE_I_VIDEO.mp4` | **40.17 s**, video only |
| Narration merge | assembled + narration.mp3 | `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | **18.46 s** |
| Environment mix | narrated + ambience/SFX | `FINAL_RUNWAY_PHASE_I_ENV.mp4` | **18.46 s** |
| Branding | ENV + CTA | `FINAL_BRANDED_VIDEO_CANONICAL.mp4` | **18.46 s** |

**Where attached:** `metadata.narration.merge` in `runway_phase_i_audio_manifest.json` — FFmpeg args: `copy_video_aac_audio_shortest`.

### Verdict

| Question | Answer |
|----------|--------|
| Generated? | **YES** |
| Merged? | **YES** |
| Audible? | **YES** (narrator present but overall mix quiet) |
| Pipeline stage | ElevenLabs merge → environment mix → branding |

### Critical defect

Narration is **18.55 s** while assembled Runway video is **40.17 s** (4 × ~10.04 s clips). **`shortest` truncated ~21.7 s of video**, removing clips 3–4 from the deliverable. This is the single largest explanation for “incomplete” and “weak story progression.”

---

## 2. Character Voice Audit

### Story package dialogue (generated, not used in audio)

From `story_packages\cb_e2e_20260614_195440_8bf41b6b.json`:

| Scene | Speakers | Sample lines |
|-------|----------|--------------|
| 0 | Whiskers, Sage | "Whoa! What is THAT?!" / "Easy, Whiskers... stay close!" |
| 1 | Sage, Whiskers | "Did you see that?!" / "Whoa! Did you hear that?!" |
| 2 | Whiskers, Sage | "Come on! Let's go see!" / "Okay... I'm right beside you." |
| 3 | Whiskers, Sage | "We DID it! Look at that!" / "The whole jungle is glowing for us!" |

**Note:** Characters are **cat/fox in a jungle** — mismatched to the user topic (boy + dragon egg).

### Runtime decision

From `runway_phase_i_audio_manifest.json` and `publish\metadata.json`:

```
character_voice_status: "Character voices skipped: mode off."
```

Voice cast plan only assigns **`narrator`** role. No per-character ElevenLabs clips were generated.

### Verdict

| Question | Answer |
|----------|--------|
| Dialogue lines generated? | **YES** (in story package) |
| Voice clips generated? | **NO** |
| Merged into final MP4? | **NO** |
| Why skipped? | **Explicit runtime flag: character voice mode off** |

---

## 3. Environment Audio Audit

### Planned layers

From `runway_phase_i_audio_manifest.json`:

| Layer | Tags | Resolved files |
|-------|------|----------------|
| Ambience | forest_birds, wind_leaves, magical_chimes | `forest_birds.mp3`, `wind_leaves.mp3`, `forest_birds.mp3` (duplicate) |
| SFX | sparkle, discovery_chime, footsteps_soft | **All resolved to `sparkle.mp3`** |

### Asset reality (ffprobe + volumedetect)

| Asset | Duration | Mean volume |
|-------|----------|-------------|
| `forest_birds.mp3` | 18.0 s | −40.8 dB |
| `wind_leaves.mp3` | 18.0 s | −38.9 dB |
| `sparkle.mp3` (all SFX) | **0.20 s** | −32.1 dB |

`magical_chimes` asset **missing** (warning in story_audio_audit).

### Merge step

`environment_mix.status: completed`  
Input: `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` → Output: `FINAL_RUNWAY_PHASE_I_ENV.mp4`  
Manifest claims: `output_audio_stream_detected: true`

### Audibility in final deliverable

| File | Mean volume |
|------|-------------|
| NARRATED (narration only) | −23.5 dB |
| ENV (narration + ambience/SFX) | **−33.9 dB** |
| FINAL_BRANDED | **−33.9 dB** |

Environment mix **lowered** overall loudness by ~10 dB vs narration-only. Ambience may be present in the bitstream but is **likely inaudible** at normal playback volume.

### Verdict

| Question | Answer |
|----------|--------|
| Generated/planned? | **YES** |
| Merged? | **YES** (ENV step) |
| Audible? | **NO / barely** — quiet assets + low mix level |
| Skipped? | **NO** — marked PASS despite poor audibility |

---

## 4. Music Audit

### Runtime manifest

```json
"music_provider": "none",
"music_status_code": "skipped_provider_disabled",
"music_status": "Music: FAILED — music source silent / merge failed"
```

### Music file

| File | Exists | Duration | Mean volume |
|------|--------|----------|-------------|
| `assets\audio\music\whimsical_adventure.mp3` | YES | 30.0 s | −27.1 dB |

Music file **exists and is not silent**, but merge was **never attempted** because provider is disabled.

### Output artifact

`FINAL_RUNWAY_PHASE_I_MUSIC.mp4` — **does not exist on disk**.

### Root cause

**Configuration, not merge failure:** `music_provider: none` → `skipped_provider_disabled`. The UI-facing label “music source silent / merge failed” is **misleading**; the actual decision was **skip**, not a failed FFmpeg merge.

### Verdict

| Question | Answer |
|----------|--------|
| Music generated? | **NO** (static asset only, not synthesized) |
| Music file available? | **YES** |
| Merge attempted? | **NO** |
| In final MP4? | **NO** |

---

## 5. Subtitle Audit

### Sidecar files (publish package)

| File | Exists | Content |
|------|--------|---------|
| `publish\subtitles\subtitles.srt` | YES | 5 cues, valid timestamps (0.000 → 18.553 s) |
| `publish\subtitles\subtitles.vtt` | YES | Same content |
| `publish\subtitles\subtitles_styled.ass` | YES | Styled ASS |

**Duplicate narration text:** cues 3 and 4 both say “The dragon egg hatches and the boy bonds.”

### Burn step

From `runway_phase_i_branding_manifest.json`:

| Field | Value |
|-------|-------|
| FFmpeg executed | **YES** |
| Method | `drawtext` |
| Output | `final\branding_staging\FINAL_RUNWAY_PHASE_I_SUBTITLED.mp4` |
| Error | **`subtitle_burn_not_visible`** |
| burn_visible_enough | **false** |
| burn_psnr_avg | 14.39 |

### Visibility validation failure

All sample frames report:

```
"error": "No module named 'numpy'"
```

Burn ran, but **post-burn visibility QA could not run** (missing dependency). Pipeline marked FAIL yet **continued** to branding.

### Used in final deliverable?

**NO.** `FINAL_BRANDED_VIDEO_CANONICAL.mp4` hash matches `cta_overlay.mp4` (built from `FINAL_RUNWAY_PHASE_I_ENV.mp4`), **not** the subtitled staging file.

Final MP4 has **no subtitle track** — only burned-in drawtext would apply, and that step was rejected.

### Verdict

| Question | Answer |
|----------|--------|
| subtitles.srt exists? | **YES** |
| Content valid? | **YES** (5 cues) |
| Burn executed? | **YES** |
| Burn succeeded? | **NO** — visibility check failed |
| Visible in final MP4? | **NO** |
| Exact failure point | Branding subtitle step → `subtitle_burn_not_visible` + numpy missing for QA |

---

## 6. Final Assembly Audit — Stream Inventory

### `publish\FINAL_BRANDED_VIDEO_CANONICAL.mp4` (deliverable)

| Stream | Codec | Details |
|--------|-------|---------|
| **Video** | h264 | 18.46 s, ~3.13 Mbps |
| **Audio** | aac | 1 channel, 44.1 kHz, ~69 kbps, 18.44 s |
| Subtitle track | — | **NONE** |
| Separate narration track | — | **NONE** (muxed into single AAC) |
| Character audio track | — | **NONE** |
| Music track | — | **NONE** |
| Ambience track | — | **NONE** (may be mixed into single AAC at low level) |

### Pipeline duration comparison

| File | Duration | Audio streams |
|------|----------|---------------|
| `FINAL_RUNWAY_PHASE_I_VIDEO.mp4` | **40.17 s** | **0** (silent video) |
| `FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | 18.46 s | 1 (narration) |
| `FINAL_RUNWAY_PHASE_I_ENV.mp4` | 18.46 s | 1 (narration + env mix) |
| `FINAL_BRANDED_VIDEO_CANONICAL.mp4` | 18.46 s | 1 (+ CTA drawtext on video) |

### Assembly chain (actual)

```
4 Runway clips (40.17 s, silent)
  → concat → FINAL_RUNWAY_PHASE_I_VIDEO.mp4
  → + narration.mp3 (shortest) → FINAL_RUNWAY_PHASE_I_NARRATED.mp4  ⚠ truncates video
  → + ambience/SFX → FINAL_RUNWAY_PHASE_I_ENV.mp4
  → subtitle burn (FAIL, not used)
  → + CTA drawtext → cta_overlay.mp4
  → copy → FINAL_BRANDED_VIDEO_CANONICAL.mp4
```

**Only one audio stream** in the deliverable: mono AAC containing narration ± quiet ambience. No music, no character voices, no subtitle track.

---

## 7. Story Director Audit

### Story Score = 50 — interpretation

From `content_brain/quality/story_audio_auditor.py`, `story_score` is **not a percentage quality grade**. Maximum from the formula:

- +25 story arc exists  
- +15 scene_progression ≥ 2  
- +10 title exists  
- **Ceiling = 50**

So **50 = perfect score for that narrow metric**, not “half quality.” The audit status is **PASS**.

Separate Content Brain quality audit reports `story_quality_score: 0.83` in E2E results — much higher.

### Story package vs topic (drift)

| Expected (user topic) | Story package content |
|-----------------------|----------------------|
| Boy, dragon egg, forest | Hook mentions “orange explorer”, “Whiskers the cat”, “Sage the fox”, “jungle path”, “crystal seed” |
| 4 distinct beats | scene_progression clips 3–4 both labeled **“Reward”** |
| Character voices | Whiskers + Sage dialogue — **never reaches narration or audio** |

### AI Director V2 (`ai_director_v2_report_phase_i_live.json`)

| Clip | Shot type | Emotional beat | Issue |
|------|-----------|----------------|-------|
| 1 | establishing_shot | fear → forward motion | Garbled scene text, domain `wildlife` |
| 2 | medium_shot | **same beat** | Repetitive |
| 3 | tracking_shot | **same beat** | Clip 3 objective duplicates clip 4 in prompts |
| 4 | reveal_shot | **same beat** | Payoff language repeated |

Director V2 **was used** (DIRECTOR CAMERA PLAN in Runway prompts) but produced **low-diversity, template-heavy** language.

### Clip-by-clip story progression

| Clip | Runway prompt story beat | Narration segment | In final video? |
|------|--------------------------|-------------------|-----------------|
| 1 | Boy discovers glowing egg in forest | “Meet our little explorer! … discovery …” (0–5.8 s) | **YES** (~full clip) |
| 2 | Boy hides egg, nervous glances | “The boy hides the egg…” (5.8–9.5 s) | **PARTIAL** (~4 s of ~10 s clip) |
| 3 | Egg cracks, baby dragon emerges | “The dragon egg hatches…” (9.5–13.2 s) | **NO** — video truncated before this clip |
| 4 | Boy bonds with baby dragon | **Duplicate** hatch/bond line (13.2–16.9 s) | **NO** — video truncated |

Narration **describes** clips 3–4 but the **video never shows them** in the deliverable.

---

## 8. Visual Diversity Audit

### Automated reports (runtime)

| Report | Score | Pass |
|--------|-------|------|
| `visual_repetition_report` | repetition_score 78 | pass_visual_diversity: true |
| `visual_continuity_report` | overall 99.25 | overall_pass: true |
| scene_diversity_score | 100 | — |

Reports **pass** — they measure continuity lock and template diversity, not viewer-perceived variety.

### Per-clip Runway output (vision review)

| Clip | Detected subject | Unique? |
|------|------------------|---------|
| 1 | Boy + glowing dragon egg in forest | Discovery |
| 2 | Boy hiding egg in hollow tree | **Distinct action** |
| 3 | Egg hatching, baby dragon | **Distinct action** |
| 4 | Boy holding blue baby dragon | Payoff (vision: `matches_expected: false`) |

**Runway clips themselves show progression** — but clips 3–4 **never appear in the 18 s deliverable**.

### Repetition findings (within prompts/plan)

| Category | Finding |
|----------|---------|
| Prompt objectives | Clips 3 & 4 share identical `visual_objective` text |
| Narration | Segments 3 & 4 identical |
| Camera | Clips 2–4 all “subject in lower two-thirds with habitat depth” |
| Location | Single locked forest environment all clips (by design) |
| Director emotional beat | Same phrase all 4 clips |

**Real diversity in generated Runway files:** moderate (4 distinct actions).  
**Real diversity in delivered MP4:** **low** — viewer sees ~1.8 clips worth of content.

---

## 9. Runtime Wiring Audit

| Subsystem | Ran? | Artifact produced? | Used in FINAL_BRANDED_VIDEO? |
|-----------|------|--------------------|------------------------------|
| **Story Package** | YES | `story_packages\cb_e2e_…json` | **PARTIAL** — beats used for narration; dialogue/characters **NO** |
| **Director V2** | YES | shot graph, camera plan in prompts | **YES** in Runway generation; **NO** in final edit beyond generated pixels |
| **Narration (ElevenLabs)** | YES | narration.mp3 | **YES** — but truncated video via shortest |
| **Character Voices** | NO | — | **NO** — skipped (mode off) |
| **Ambience / SFX** | YES | mixed into ENV | **PARTIAL** — merged but likely inaudible |
| **Music** | NO | track exists, not mixed | **NO** — provider disabled |
| **Subtitles** | YES (sidecar) / FAIL (burn) | .srt/.vtt in publish | **NO** in MP4 |
| **Branding (CTA)** | YES | drawtext last 2 s | **YES** — “Follow for more” |
| **Branding (Logo)** | SKIP | logo_missing | **NO** |
| **Assembly (concat)** | YES | 40.17 s silent video | **PARTIAL** — only ~46% of duration survives merge |

### Systems that only generated reports

These ran and logged PASS/completed but **did not materially improve the deliverable**:

- Visual continuity pipeline (99.25 score)
- Visual repetition detector (pass)
- Story audio auditor (PASS at story_score ceiling 50)
- AI Director V2 rhythm score (95)
- Scene recall / shot graph (planning artifacts only)

---

## Root Cause Matrix

| # | Symptom | Root cause | Severity |
|---|---------|------------|----------|
| 1 | Story feels incomplete | Narration merge **`shortest`** cut 40 s → 18 s; clips 3–4 dropped | **CRITICAL** |
| 2 | No character voices | `character_voice_status: mode off`; only narrator synthesized | **HIGH** |
| 3 | No background music | `music_provider: none` → skipped, never merged | **HIGH** |
| 4 | No visible subtitles | Burn failed visibility QA (numpy missing); fail-open used ENV base | **HIGH** |
| 5 | No audible environment | Quiet assets + low mix; 0.2 s sparkle used for all SFX | **MEDIUM** |
| 6 | Repetitive feel | Duplicate narration beats 3–4; locked forest; director same emotional beat | **MEDIUM** |
| 7 | SUCCESS vs quality gap | Stages fail-open; publish completes with known FAIL warnings | **MEDIUM** |
| 8 | Story package drift | Cat/fox jungle template vs boy/dragon topic | **MEDIUM** |

---

## Missing Media Components (deliverable checklist)

| Component | Expected | In final MP4 |
|-----------|----------|--------------|
| Full 4-clip video (40 s) | YES | **NO** (18.5 s) |
| Narration | YES | YES (quiet) |
| Character dialogue audio | YES (per story package) | **NO** |
| Background music | YES | **NO** |
| Environment ambience | YES | **NO / inaudible** |
| SFX | YES | **NO / inaudible** |
| Burned-in subtitles | YES | **NO** |
| Sidecar subtitles | YES | YES (files only, not in MP4) |
| Logo | optional | **NO** (skipped) |
| CTA overlay | YES | YES (last ~2 s) |

---

## Failed / Degraded Pipeline Stages

| Stage | Status | Impact on deliverable |
|-------|--------|----------------------|
| Runway generation (4 clips) | SUCCESS | Clips exist but 2 lost at merge |
| Video concat | SUCCESS | 40 s silent master |
| Narration merge | MERGED (with shortest) | **Truncated video** |
| Environment mix | completed | Barely audible |
| Music runtime | skipped_provider_disabled | No music |
| Subtitle burn | FAIL | No visible subs |
| Character voices | skipped | No dialogue audio |
| Branding | completed (fail-open) | CTA only |
| Publish | PUBLISHED_PACKAGE_CREATED | Canonical MP4 is degraded |

---

## Exact Recommendations (audit only — no implementation)

1. **Block publish when final duration < assembled duration** — narration merge must not use `shortest` against a longer video without explicit clip-aware timing.
2. **Fail closed on subtitle burn FAIL** — do not ship `FINAL_BRANDED_VIDEO_CANONICAL` when `burn_visible_enough: false`.
3. **Install / require `numpy` for subtitle visibility QA** — current false-negative path rejects valid burns or masks real failures.
4. **Enable music provider or remove “FAILED” label when status is `skipped_provider_disabled`** — avoid misleading success reporting.
5. **Enable character voice mode when story package contains multi-character dialogue** — or strip dialogue from package to avoid false expectations.
6. **Raise ambience/SFX mix levels and validate audibility** — post-mix volumedetect gate before ENV → branding.
7. **Replace 0.2 s sparkle placeholder for all SFX tags** — footsteps/discovery need distinct assets.
8. **Fix story package template selection** — boy/dragon topic must not produce Whiskers/Sage jungle blueprint.
9. **Deduplicate narration segments 3–4** — align narration timing to full 40 s video (4 × 10 s).
10. **Separate “pipeline SUCCESS” from “delivery QUALITY PASS”** — require delivery gate: full duration, audible mix, visible subs (if enabled), music (if enabled).

---

## Evidence Sources

- `project_brain/runtime_state/runway_phase_i_audio_manifest.json`
- `project_brain/runtime_state/runway_phase_i_publish_manifest.json`
- `project_brain/runtime_state/runway_phase_i_branding_manifest.json`
- `outputs/runs/20260614_210353_440_8bf41b6b/publish/metadata.json`
- `outputs/runs/20260614_210353_440_8bf41b6b/metadata/assembly_manifest.json`
- `project_brain/story_packages/cb_e2e_20260614_195440_8bf41b6b.json`
- `project_brain/runtime_state/visual_continuity_report.json`
- `project_brain/runtime_state/visual_repetition_report_cb_e2e_20260614_195440_8bf41b6b.json`
- `project_brain/runtime_state/ai_director_v2_report_phase_i_live.json`
- ffprobe / ffmpeg volumedetect on deliverable and intermediates (2026-06-14)

---

**Next step per project rule:** Review this audit → approve remediation scope → implement fixes in a separate phase.
