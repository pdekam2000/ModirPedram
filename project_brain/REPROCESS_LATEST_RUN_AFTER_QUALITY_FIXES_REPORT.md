# Reprocess Latest Run After Quality Fixes

**Generated:** 2026-06-14 20:08:46 UTC
**Run ID:** `cb_e2e_20260614_195440_8bf41b6b`
**Run folder:** `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260614_210353_440_8bf41b6b`

## Runway Started

**NO** — post-processing only on existing downloaded clips.

## Output

- **Final path:** `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260614_210353_440_8bf41b6b\publish\FINAL_BRANDED_VIDEO_CANONICAL_FIXED.mp4`
- **Backups preserved under:** `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260614_210353_440_8bf41b6b\publish\archive\pre_quality_fix_reprocess`

## Duration

| Stage | Before | After |
|-------|--------|-------|
| Assembly | 40.166667 s | 40.166667 s |
| Canonical / fixed final | 18.458333 s | 40.167007 s |
| Narration audio | 18.552744 s | (reused, padded to video) |

## Delivery Gate

- **Status:** `WARNING`
- **Upload ready:** `False`
- **Failures:** []
- **Warnings:** ['ambience_weak_or_quiet_mix']

## Subtitle Status

- **Status:** Subtitle: PASS — visible lower-third subtitles burned
- **Visible on burn:** `True`

## Audio Status

- **Merge:** MERGED
- **Ambience:** Ambience: PASS — 3 layer(s)
- **Music:** Music: FAILED — music source silent / merge failed
- **Narration stream present:** True
- **Mean volume (dB):** -41.1

## Topic Status

- **Topic:** A boy finds a dragon egg in the forest and hides it from everyone
- **Story genre:** educational
- **Characters:** Boy, Dragon, Narrator
- **Whiskers/Sage leak:** False

## Validation Checklist

| Check | Result |
|-------|--------|
| Final duration ~40 s | **PASS** — 40.17 s (was 18.46 s) |
| 4 clips preserved (no truncation) | **PASS** — assembly 40.17 s, zero duration loss |
| Subtitles visible | **PASS** — burn QA visible |
| Narration audible | **PASS** — audio stream present |
| Ambience / music status | **WARNING** — ambience mixed but quiet (-41.1 dB); music merge failed |
| Delivery gate | **WARNING** — no FAIL; reason: `ambience_weak_or_quiet_mix` |
| Topic boy/dragon | **PASS** — Boy, Dragon, Narrator; no Whiskers/Sage |
| Runway started | **NO** |
| Old canonical preserved | **YES** — archived under `publish/archive/pre_quality_fix_reprocess/` |

## Overall

- **OK:** True
- **Branding status:** completed
- **Publish status:** PUBLISHED_PACKAGE_CREATED
