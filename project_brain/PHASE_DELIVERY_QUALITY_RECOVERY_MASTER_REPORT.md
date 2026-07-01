# PHASE DELIVERY-QUALITY-RECOVERY — Master Report

**Phase:** DELIVERY-QUALITY-RECOVERY — Architecture-first remediation  
**Mode:** Analysis only — no code changes, no fixes, no new features  
**Run:** `cb_e2e_20260614_195440_8bf41b6b`  
**Date:** 2026-06-14  

---

## Executive summary

Runway generation **succeeded** (4 clips, 40.17 s assembly). Delivery **failed quality expectations** because post-processing:

1. **Truncated video** at narration merge (`-shortest`) — **critical**
2. **Skipped music** (profile `music_provider: none`) while reporting misleading FAIL label
3. **Failed subtitle burn QA** (missing `numpy`) then **fail-open** to non-subtitled base
4. **Skipped character voices** (voice cast plan has narrator only)
5. **Mixed ambience at inaudible levels**
6. **Rebuilt story package** with Whiskers/Sage template decoupled from authoritative topic

Runtime reports **SUCCESS** / `publish_completed` because stages fail-open and branding overwrites `failed` → `completed`.

---

## 1. Duration root cause

**Primary:** `content_brain/audio/audio_merge_engine.py` → `merge_narration_into_video()` uses FFmpeg **`-shortest`**, cutting **40.17 s → 18.46 s** when narration MP3 is 18.55 s.

**Secondary:** `content_brain/audio/audio_mix_engine.py` also uses `-shortest` but cannot restore lost video.

**Impact:** Clips 3–4 never appear in canonical deliverable.

**Detail:** [`DURATION_PRESERVATION_ANALYSIS.md`](DURATION_PRESERVATION_ANALYSIS.md)

---

## 2. Media wiring map

Full stage table, artifact paths, and “used in final MP4” matrix:

**[`FINAL_MEDIA_WIRING_MAP.md`](FINAL_MEDIA_WIRING_MAP.md)**

**Key wiring breaks:**

| Connection | Expected | Actual |
|------------|----------|--------|
| Assembly → Narration | Full 40 s + audio | 18 s truncated |
| Subtitles → Branding | Burn → canonical | FAIL → ENV base |
| Story package dialogue → Audio | Character voices | Not synthesized |
| Music asset → Mix | Background bed | Provider disabled, skip |
| Publish → Canonical | Best quality | 18 s branded, while 40 s silent copy also in publish folder |

---

## 3. Topic drift root cause

**Where:** Post-run `run_audio_post_processing()` → `build_and_save_story_package()`

**Chain:**

1. `detect_genre(topic, story_brief)` — keyword **`magical`** → genre **`cartoon`**
2. `build_story_blueprint()` — Whiskers/Sage **hardcoded template**
3. `build_character_profiles()` — `_cartoon_cast()`
4. `build_dialogue_plan()` — preset cat/fox lines

**Topic preserved in:** E2E story brief, Runway prompts, generated clips.  
**Topic lost in:** `project_brain/story_packages/cb_e2e_*.json`

**Detail:** [`TOPIC_IDENTITY_DRIFT_REPORT.md`](TOPIC_IDENTITY_DRIFT_REPORT.md)

---

## 4. Subtitle failure root cause

1. Subtitles **generated** (SRT/VTT/ASS) — PASS  
2. Burn **executed** (drawtext) — output file exists  
3. Visibility QA **failed** — `No module named 'numpy'` in `subtitle_format_engine.py`  
4. `burn_subtitles()` → status **FAILED** (`subtitle_burn_not_visible`)  
5. `branding_runtime` keeps **ENV** as base (not subtitled file)  
6. Branding sets **`status: completed`** anyway (line 276)  
7. Publish copies sidecar subs + **non-subtitled** canonical MP4  

**Detail:** [`SUBTITLE_PIPELINE_FAILURE_REPORT.md`](SUBTITLE_PIPELINE_FAILURE_REPORT.md)

---

## 5. Audio layer status

| Layer | Generated | Merged | Audible (deliverable) | Mean dB |
|-------|-----------|--------|------------------------|---------|
| Narration | YES | YES | YES | −33.9 (branded) |
| Environment | YES | YES | NO/barely | (contributes to mix) |
| SFX | YES (placeholder) | YES | NO | sparkle 0.2 s |
| Music | Asset only | NO | NO | skipped |
| Character voices | Dialogue only | NO | NO | skipped |

**Detail:** [`AUDIO_LAYER_FORENSIC_REPORT.md`](AUDIO_LAYER_FORENSIC_REPORT.md)

---

## 6. Quality gate design

Proposed **`delivery_status: PASS | WARNING | FAIL`** gate before `publish_completed`:

- **FAIL** on duration truncation, subtitle burn fail when enabled, missing audio, etc.
- **WARNING** on logo skip, low ambience, intentional music skip
- **PASS** requires duration preservation + enabled features actually in deliverable

**Detail:** [`DELIVERY_QUALITY_GATE_DESIGN.md`](DELIVERY_QUALITY_GATE_DESIGN.md)

---

## 7. Recommended implementation order

After approval — **repair existing systems only**, no new providers/phases:

| Order | Fix | Files (primary) | Rationale |
|-------|-----|-----------------|-----------|
| **1** | **Duration preservation** — remove/replace `-shortest` in narration merge; align narration length to `clip_count × 10s` | `audio_merge_engine.py`, `narration_engine` / script builder | Unblocks story completeness — highest user impact |
| **2** | **Delivery quality gate** — fail closed before `publish_completed` | `runway_live_post_processor.py`, new `delivery_quality_gate.py` | Prevents false SUCCESS |
| **3** | **Subtitle fail-closed** — fix numpy dep OR explicit QA; don't overwrite branding status; require visible burn when enabled | `subtitle_format_engine.py`, `branding_runtime.py` | Subtitles promised in UI |
| **4** | **Story package authority** — reuse E2E story brief; fix genre false positive; stop Whiskers template on dragon topics | `story_package.py`, `story_niche.py`, `story_architect.py` | Aligns audio planning with video |
| **5** | **Music wiring** — honor `music_provider: local` in profile OR accurate SKIPPED status (not FAILED) | `music_runtime.py`, `channel_profile.json`, status labels | Correct background bed |
| **6** | **Character voice wiring** — fix multi_voice condition (`>1` assignments); wire dialogue OR narrator_only mode explicitly | `audio_post_processing.py`, voice cast engine | Dialogue in package today is dead |
| **7** | **Environment audibility** — raise mix gain; fix SFX asset resolution (not all → sparkle 0.2s) | `audio_mix_engine.py`, `environment_sound_engine.py` | Audible world sound |
| **8** | **Publish clarity** — canonical must reference full-duration branded file; don't leave misleading 40s silent as “final” in metadata | `run_publish_package`, `canonical_delivery.py` | Operator confusion |

---

## Supporting documents

| Document | Priority |
|----------|----------|
| [`DURATION_PRESERVATION_ANALYSIS.md`](DURATION_PRESERVATION_ANALYSIS.md) | 1 |
| [`FINAL_MEDIA_WIRING_MAP.md`](FINAL_MEDIA_WIRING_MAP.md) | 2 |
| [`TOPIC_IDENTITY_DRIFT_REPORT.md`](TOPIC_IDENTITY_DRIFT_REPORT.md) | 3 |
| [`SUBTITLE_PIPELINE_FAILURE_REPORT.md`](SUBTITLE_PIPELINE_FAILURE_REPORT.md) | 4 |
| [`AUDIO_LAYER_FORENSIC_REPORT.md`](AUDIO_LAYER_FORENSIC_REPORT.md) | 5 |
| [`DELIVERY_QUALITY_GATE_DESIGN.md`](DELIVERY_QUALITY_GATE_DESIGN.md) | 6 |
| [`FINAL_VIDEO_FORENSIC_AUDIT.md`](FINAL_VIDEO_FORENSIC_AUDIT.md) | Prior forensic pass |

---

## Approval checkpoint

Per project rule: **Analyze → Report → Approve → Implement**

This package completes **Analyze + Report**. No code was modified.

**Awaiting approval** to implement in order above (starting with duration preservation + delivery gate).
