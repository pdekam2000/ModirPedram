# Phase RUNWAY-I — 3-Clip Live Continuity Validation Report

**Date:** 2026-06-03  
**Phase:** `runway_starter_to_video_i_3clip_v1`  
**Scope:** Controlled validation only — no Runway automation / approval gate / provider router changes  
**Live CDP operator run:** Pending (operator must execute from UI)

---

## Executive summary

| Gate | Status | Notes |
|------|--------|-------|
| Pre-check validators | **PASS** | Story brief + Phase I structural/simulate |
| Controlled simulate rehearsal (validation story) | **PASS** | 7 approvals · 3 clips · 3 downloads · story brief traced |
| Live CDP 3-clip run (UI) | **PENDING** | Requires Chrome CDP + operator Approve at each gate |
| Recommendation | **Approve Phase I for live operator run** | After one content-layer fix applied (see Bugs) |

---

## Pre-check validators

```bash
python project_brain/validate_runway_story_brief_builder.py
python project_brain/validate_runway_phase_i_3clip_live_continuity.py
```

| Validator | Result | Count |
|-----------|--------|-------|
| `validate_runway_story_brief_builder.py` | **PASS** | 34/34 |
| `validate_runway_phase_i_3clip_live_continuity.py` | **PASS** | 26/26 |

No browser. No Runway. No credits.

---

## Validation story (live test input)

> A mysterious astronaut stands alone on a rain-soaked neon platform above a futuristic city. A glowing signal appears beneath the water on the floor, guiding the astronaut across the platform while distant drones search through the storm. At the edge, the signal rises into the sky and reveals a massive symbol above the city. Cinematic, emotional, tense but hopeful, realistic cyberpunk atmosphere.

**UI path:** Execution Center → Runway Live Smoke → **3-Clip Continuity (Phase I)** → **Start 3-Clip Live (CDP)**

---

## Controlled simulate rehearsal (same story)

Simulate rehearsal executed with `RunwayLiveSmokeRunner(clip_count=3, simulate=True)` — validates workflow without credits.

| Check | Result |
|-------|--------|
| Run completed | `final_status=completed` |
| StoryBrief in bundle | **Yes** |
| StoryBrief character | `A mysterious astronaut` |
| Starter prompt expanded | **1644 chars** (raw story 398 chars) |
| Clip beats from story | 3 sentence-derived beats preserved |
| Approvals granted | **7** (1 image + 3 generate + 3 download) |
| Video generates approved | 3 |
| Downloads approved | 3 |
| Clips completed | 3 |
| Use Frame after clips | `[1, 2]` |
| Remove image (final) | **Yes** |
| Video transition (Use to Video) | **Verified** (simulate) |

### Story brief traceability

| Field | Value |
|-------|-------|
| `story_brief_present` | true |
| `story_brief_title` | A mysterious astronaut — rain-soaked neon platform… |
| `story_brief_character` | A mysterious astronaut |
| `story_brief_setting` | rain-soaked neon platform above a futuristic city |
| `starter_prompt_chars` | 1644 |

### Clip continuity (prompt-level)

| Clip | continuity lock | Use to Video / Use Frame | no scene jump | character anchor |
|------|-----------------|--------------------------|---------------|------------------|
| 1 | present | Use to Video / starter reference | present | present |
| 2 | present | Use Frame | present | present |
| 3 | present | Use Frame | present | present |

Continuity anchors locked across clips:

- **Character:** A mysterious astronaut  
- **Wardrobe:** weathered EVA suit with scuffed helmet visor (when inferred)  
- **Location:** rain-soaked neon platform above a futuristic city  
- **Lighting:** rain-soaked reflective neon practicals and volumetric fog  
- **Palette:** teal, magenta, and amber neon color grade  
- **Camera:** wide anamorphic with neon edge bloom  

### Approval gate behavior (simulate)

Gates fire in order before credit-spending actions:

1. `image_generate_button`
2. `generate_button` (clip 1)
3. `download_mp4_button` (clip 1)
4. `generate_button` (clip 2)
5. `download_mp4_button` (clip 2)
6. `generate_button` (clip 3)
7. `download_mp4_button` (clip 3)

No autonomous Generate/Download without approval callback.

---

## Live CDP run status

| Item | Status |
|------|--------|
| Browser CDP attached | Not run in this validation session |
| Operator UI approvals | Pending |
| Real MP4 downloads | Pending |
| Real Use Frame clicks | Pending |
| Post-run JSON | Will write to `project_brain/runway_phase_i_3clip_last_report.json` |

**Operator checklist for live run:**

1. Chrome CDP on `http://127.0.0.1:9222`, logged into Runway  
2. Paste validation story in Phase I tab  
3. Start **3-Clip Live (CDP)**  
4. Approve each of 7 gates; click **Image Ready** when prompted  
5. Confirm real downloads per clip  
6. Review `runway_phase_i_3clip_last_report.json` for `story_brief_present`, `clips_completed`, `downloads_approved_count`

---

## Bugs found

### BUG-1 — StoryBrief character inferred as `"on"` (fixed)

**Symptom:** For validation story, `main_character` became `"on"` because regex used `match.lastindex` and matched preposition `on` as a verb group.

**Impact:** Weak starter/clip continuity language (`Subject: on`).

**Fix:** `content_brain/execution/runway_story_brief_builder.py` — keyword-first astronaut detection; explicit capture groups; removed `on|in|at` from verb alternation.

**Re-test:** Character now `A mysterious astronaut`; validators still PASS.

### BUG-2 — Live report missing story brief fields (fixed)

**Symptom:** Phase I JSON report did not record `story_brief_present` or continuity traceability.

**Fix:** `content_brain/execution/runway_live_smoke_test.py` — `_capture_prompt_bundle_diagnostics()` + report fields (reporting only; no automation change).

---

## Files changed (validation session)

| File | Change |
|------|--------|
| `content_brain/execution/runway_story_brief_builder.py` | Fix character inference for astronaut-led stories |
| `content_brain/execution/runway_live_smoke_test.py` | Story brief + continuity diagnostics in Phase I report |
| `project_brain/PHASE_RUNWAY_I_3CLIP_LIVE_VALIDATION_REPORT.md` | This report |

**Not changed:** Runway semi-auto engine, approval gates, provider router, Prompt Builder logic (beyond existing auto-brief default).

---

## Downloads result

| Mode | Result |
|------|--------|
| Simulate | 3/3 download steps approved and marked in report |
| Live CDP | Pending operator run |

---

## Recommendation

**Approve Phase I for live operator validation.**

Rationale:

- All structural pre-checks PASS  
- Controlled simulate rehearsal with the exact validation story PASS  
- StoryBrief auto-expansion produces rich starter + 3 clip prompts with continuity locks  
- Approval model remains 7 explicit gates — no credits without operator Approve  
- One content-layer bug fixed before live run  

**Next step:** Operator runs live from UI with validation story; attach `runway_phase_i_3clip_last_report.json` outcome to close live CDP section of this report.

---

## Commands reference

```bash
# Pre-check (required before live)
python project_brain/validate_runway_story_brief_builder.py
python project_brain/validate_runway_phase_i_3clip_live_continuity.py

# Optional live CDP (operator approvals, spends credits)
python project_brain/validate_runway_phase_i_3clip_live_continuity.py --live

# Or CLI with UI bridge
python project_brain/run_runway_live_smoke_test.py --clip-count 3 --ui-approval --story-file validation_story.txt
```
