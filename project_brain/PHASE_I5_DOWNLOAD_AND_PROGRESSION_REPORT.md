# Phase I.5 — Download Validation + Story Progression Report

**Date:** 2026-06-04  
**Scope:** Audit-only deliverable — no Assembly, Voice, Subtitle, or FFmpeg.

---

## Executive summary

| Area | Finding | Action taken |
|------|---------|--------------|
| **Downloads** | Runway saves to `downloads/runway/` but Phase I report did not verify files on disk; last live report showed `download_attempted=false` despite download approval | Added `RunwayPhaseIDownloadTracker` + report fields |
| **Story progression** | Clips looked identical because brief beats and prompt expansion prioritized static continuity over discovery/escalation/payoff | Updated brief beats + prompt narrative roles + progression validator |

---

## Part A — Download validation audit

### Where files are saved

| Item | Value |
|------|--------|
| **Catalog default** | `downloads/runway/` (from `ProviderModeCatalog` / browser preflight) |
| **Preflight check** | `DOWNLOAD_PATH_READY` in browser probe |
| **Last live report probe** | `C:\Users\kaman\Desktop\ModirAgentOS\downloads\runway` writable |
| **Physical files at audit time** | **0 files** in `downloads/runway/` (downloads not verified on disk from prior run) |

### Prior report gap (`runway_phase_i_3clip_last_report.json`)

- `download_mp4_button` approval granted for clip 1
- Report still had: `download_attempted=false`, `downloads_approved_count=0`, no per-clip paths
- Run stopped at clip 2 prompt — download pipeline never fully verified end-to-end on disk

### New report fields (Phase I live smoke)

| Field | Type | Meaning |
|-------|------|---------|
| `clip_1_downloaded` | bool | Clip 1 MP4 verified (size > 0) |
| `clip_2_downloaded` | bool | Clip 2 MP4 verified |
| `clip_3_downloaded` | bool | Clip 3 MP4 verified |
| `downloaded_file_paths` | list[str] | Unique absolute paths |
| `total_downloads_completed` | int | Count of verified downloads |
| `download_dir` | str | Scanned directory |
| `download_records` | list[dict] | Per-clip verification audit trail |

### Verification behavior

After each `download_mp4_clip_N` / `final_download_clip_N` step:

1. `RunwayPhaseIDownloadTracker.verify_clip_download(N)` polls `download_dir` for **new** video files (`.mp4`, `.webm`, `.mov`)
2. Requires `file_size_bytes > 0`
3. Assigns one file per clip index (no duplicate paths)
4. `simulate=True` writes placeholder files for rehearsal without CDP

---

## Part B — Story progression audit

See full analysis: [`PHASE_I5_STORY_PROGRESSION_AUDIT.md`](PHASE_I5_STORY_PROGRESSION_AUDIT.md)

**Root cause:** `runway_story_brief_builder._resolve_clip_beats()` used low-motion templates; `runway_prompt_builder._build_clip_prompt()` filled prompts with continuity libraries that overpowered beat differentiation.

**Fix owner modules:**

- `content_brain/execution/runway_story_brief_builder.py` — discovery / escalation / payoff beats for 3-clip default arc
- `content_brain/execution/runway_prompt_builder.py` — `CLIP_NARRATIVE_ROLES` + stronger motion verbs
- `content_brain/execution/runway_story_progression_validator.py` — automated QA

**Continuity preserved:** same character, location, wardrobe, Use to Video / Use Frame language.

---

## Files changed

| File | Role |
|------|------|
| `content_brain/execution/runway_phase_i_download_tracker.py` | **New** — download dir verification |
| `content_brain/execution/runway_story_progression_validator.py` | **New** — progression QA |
| `content_brain/execution/runway_story_brief_builder.py` | 3-clip narrative beat templates |
| `content_brain/execution/runway_prompt_builder.py` | Narrative role blocks per clip |
| `content_brain/execution/runway_live_smoke_test.py` | Report fields + tracker wiring + progression audit |
| `project_brain/validate_phase_i5_download_and_progression.py` | **New** validator |
| `project_brain/PHASE_I5_STORY_PROGRESSION_AUDIT.md` | Story progression audit |
| `project_brain/PHASE_I5_DOWNLOAD_AND_PROGRESSION_REPORT.md` | This report |

**Not changed:** provider router, Assembly, Voice, Subtitle, approval gate semantics.

---

## Validation results

```bash
python project_brain/validate_phase_i5_download_and_progression.py   # 32/32 PASS
python project_brain/validate_runway_story_brief_builder.py          # 34/34 PASS
python project_brain/validate_runway_phase_i_3clip_live_continuity.py # 26/26 PASS
```

Key checks:

- 3 unique clip beats with discovery / escalation / payoff markers
- Continuity preserved in all clip prompts
- Download tracker: unique paths, size > 0, report fields populated
- Simulate 3-clip rehearsal: `total_downloads_completed=3`, all clip flags true
- 7 approval gates unchanged

---

## Operator instructions — next live re-run

### Downloads

1. Run **Execution Center → Runway Live Smoke → 3-Clip Continuity (Phase I)**
2. After each **Download MP4** approval, confirm a new file appears in `downloads/runway/`
3. On completion, check `project_brain/runway_phase_i_3clip_last_report.json`:
   - `total_downloads_completed` should be **3**
   - `downloaded_file_paths` should list **3 unique** `.mp4` paths with size > 0

### Story progression

1. Use explicit beats in the story field when possible:
   - **Clip 1:** discovery / turn / notice
   - **Clip 2:** walk / track / intensify
   - **Clip 3:** reach / touch / reveal payoff
2. Review `story_progression_audit.all_pass` in the report — should be `true`
3. Do **not** proceed to Assembly / Voice / Subtitle until downloads and progression audit pass

---

## Out of scope (confirmed not started)

- Assembly Runtime
- Voice Runtime
- Subtitle Runtime
- `FINAL_PUBLISH_READY.mp4`
- FFmpeg stitching
