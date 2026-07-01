# Final Media Wiring Map

**Phase:** DELIVERY-QUALITY-RECOVERY — Priority 2  
**Run:** `cb_e2e_20260614_195440_8bf41b6b`  
**Delivery folder:** `outputs/runs/20260614_210353_440_8bf41b6b`  

---

## Flow diagram

```
Story Package
    ↓
Director V2
    ↓
Prompt Builder (Content Brain E2E)
    ↓
Runway (4 clips)
    ↓
Assembly (concat)
    ↓
Narration (ElevenLabs + merge)
    ↓
Environment (ambience + SFX mix)
    ↓
Music (skipped)
    ↓
Subtitles (sidecar + burn attempt)
    ↓
Branding (CTA overlay)
    ↓
Publish (canonical copy)
```

---

## Stage-by-stage wiring

Legend: **In final MP4** = present in `publish/FINAL_BRANDED_VIDEO_CANONICAL.mp4`

| Stage | Produced? | Artifact path(s) | Consumed by next stage? | In final MP4? |
|-------|-----------|------------------|-------------------------|---------------|
| **Story Package** | YES | `project_brain/story_packages/cb_e2e_20260614_195440_8bf41b6b.json` | Audio post (`build_and_save_story_package`), narration script indirectly via E2E story brief | **PARTIAL** — only narrator lines from clip beats; Whiskers/Sage dialogue **not** in audio |
| **Director V2** | YES | `project_brain/runtime_state/ai_director_v2_report_phase_i_live.json`, `shot_graph/phase_i_live/shot_graph.json` | Runway prompts via E2E `runway_prompts.txt` | **YES** (visual content of generated clips only) |
| **Prompt Builder** | YES | `project_brain/content_brain_test_results/cb_e2e_20260614_195440_8bf41b6b.runway_prompts.txt` | Runway browser automation | **YES** (via Runway pixels) |
| **Runway** | YES | `downloads/runway/runway_clip_{1-4}_session_20260614_*.mp4` | Assembly concat | **PARTIAL** — only ~18.5 s of ~40 s survives merge |
| **Assembly** | YES | `final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` (40.17 s, silent) | Narration merge | **PARTIAL** — video truncated before deliverable |
| **Narration** | YES | `outputs/audio/cb_e2e_*_narration.mp3`, `publish/narration/narration.mp3` | Merge → NARRATED | **YES** (mono AAC, quiet ~−34 dB mean) |
| **Environment** | YES | Mixed into `final/FINAL_RUNWAY_PHASE_I_ENV.mp4` | Branding input | **PARTIAL** — merged but likely inaudible |
| **Music** | NO (skipped) | Track exists: `assets/audio/music/whimsical_adventure.mp3`; no `FINAL_RUNWAY_PHASE_I_MUSIC.mp4` | — | **NO** |
| **Subtitles** | YES (sidecar) / FAIL (burn) | `publish/subtitles/subtitles.srt`, `.vtt`, `.ass` | Branding burn step | **NO** — not burned into deliverable |
| **Branding** | YES | `final/branding_staging/cta_overlay.mp4` → `final/FINAL_BRANDED_VIDEO_CANONICAL.mp4` | Publish promote | **YES** — CTA drawtext last ~2 s |
| **Publish** | YES | `publish/FINAL_BRANDED_VIDEO_CANONICAL.mp4` | Upload / UI | **YES** (canonical) |

---

## Intermediate files (same run)

| File | Duration | Role |
|------|----------|------|
| `final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` | 40.17 s | Silent assembled master |
| `final/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | 18.46 s | After narration merge |
| `final/FINAL_RUNWAY_PHASE_I_ENV.mp4` | 18.46 s | After ambience/SFX mix |
| `final/branding_staging/FINAL_RUNWAY_PHASE_I_SUBTITLED.mp4` | 18.46 s | Burn attempt (not used in canonical) |
| `final/branding_staging/cta_overlay.mp4` | 18.46 s | Source of canonical video stream |
| `publish/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` | 40.17 s | Publish copy of **full** assembly (not canonical) |
| `publish/FINAL_RUNWAY_PHASE_I_NARRATED.mp4` | 18.46 s | Publish copy |
| `publish/FINAL_BRANDED_VIDEO_CANONICAL.mp4` | 18.46 s | **Canonical deliverable** |

**Wiring gap:** Publish folder retains the **40 s** silent assembly as `FINAL_RUNWAY_PHASE_I_VIDEO.mp4`, but the **canonical** branded file is the **18 s** truncated version. UI/registry point at canonical.

---

## Orchestrator call order

**File:** `content_brain/execution/runway_live_post_processor.py`

```
run_assembly()              → FINAL_RUNWAY_PHASE_I_VIDEO.mp4
run_audio_post_processing() → NARRATED → ENV
run_branding_runtime()      → CTA → FINAL_BRANDED_VIDEO_CANONICAL.mp4
run_publish_package()         → copies to publish/
write_runway_phase_i_checkpoint(publish_completed)
```

**Fail-open points:**

- Audio post `status: completed` even with music/subtitle warnings
- Branding `status: completed` overwrites earlier `failed` from subtitle step (line 276)
- Post-processor `overall_status: completed` if assembly succeeded, regardless of branding/audio warnings

---

## Stream inventory — canonical deliverable

**File:** `publish/FINAL_BRANDED_VIDEO_CANONICAL.mp4`

| Stream | Present |
|--------|---------|
| h264 video (18.46 s) | YES |
| mono AAC audio | YES |
| Separate narration track | NO (muxed) |
| Music | NO |
| Character dialogue | NO |
| Ambience (distinct track) | NO (may be mixed into AAC) |
| Subtitle track / burned text | NO (burn failed; sidecar files only in publish folder) |

---

## Systems that produced reports but not deliverable content

| System | Artifact | In final MP4 |
|--------|----------|--------------|
| Visual continuity pipeline | `visual_continuity_report.json` | NO |
| Visual repetition detector | `visual_repetition_report_*.json` | NO |
| Story audio auditor | score in audio manifest | NO |
| Scene recall / shot graph | JSON under `runtime_state/` | NO |
| Dialogue plan (Whiskers/Sage) | story package | NO |
