# Phase 11I-2B — Hardcoded Niche Term Fixes Report

**Status:** COMPLETE  
**Date:** 2026-05-28  
**Scope:** Minimal CRITICAL fixes only — legacy `subtitle_engine` and `seo_package_engine`

---

## Summary

Phase 11I-2B removes skincare-biased hardcoded defaults from the two CRITICAL legacy modules identified in 11I-2A. Generic usage now uses topic-neutral fallbacks. Explicit skincare/selfcare profiles and custom keyword lists still work when provided.

**Content Brain Runtime, Voice Runtime, Video Runtime, Runway/Hailuo, and 11I-2 Subtitle Runtime foundation were not modified.**

---

## Files Changed

| File | Change |
|------|--------|
| `engines/subtitle_engine.py` | Optional `highlight_keywords`; topic-neutral default list |
| `engines/seo_package_engine.py` | Profile-aware SEO; generic neutral pools; skincare pools gated by profile |
| `project_brain/validate_11i2b_hardcoded_niche_fixes.py` | **Created** — 12 automated tests |

**Not modified:** `content_brain/execution/*`, voice/video runtime, `pipelines/full_video_pipeline.py` (call signatures unchanged).

---

## Fix 1 — `subtitle_engine.py`

### Before

- Fixed `highlight_words` list included `glow`, `skin`, `mask`, `radiant`, `hydrated`, `beautiful`, `healthy`, etc.
- Applied to **every** ASS caption via `style_word()` regardless of topic.

### After

| Behavior | Detail |
|----------|--------|
| `SubtitleEngine(highlight_keywords=[...])` | Uses caller-supplied words (lowercased) for emphasis |
| `SubtitleEngine()` (legacy callers) | Topic-neutral fallback: `secret`, `hidden`, `important`, `never`, `always`, `stop`, `watch` |
| Skincare terms | **Removed** from default fallback |
| API compatibility | `create_subtitles()`, `generate_srt()`, `generate_ass()` unchanged |

---

## Fix 2 — `seo_package_engine.py`

### Before

- All packages used skincare hashtags (`#skincare`, `#glowup`, …), skincare CTAs, and titles like `"Your Skin Needs This {topic}"`.
- `generate_keywords()` always appended skincare keyword strings.

### After

| Context | Hashtags | Titles / description / CTAs |
|---------|----------|-------------------------------|
| **No profile** (generic) | `#shorts`, `#reels`, `#viral`, `#fyp`, … | Topic-neutral templates; no skin/glow/mask copy |
| **Profile `seo_keywords` / `seo_rules.hashtags`** | Uses explicit list first | Respects profile when set |
| **Profile niche `selfcare` / `skincare` / `beauty`** | Skincare hashtag pool | Skincare titles/CTAs allowed (intentional) |
| **Optional `profile` on `build_package()`** | Backward compatible — `profile=None` → generic | Legacy callers unchanged |

### Profile fields supported

- `seo_keywords` — hashtag/keyword list
- `seo_rules.hashtags` / `seo_rules.keywords` — alternate profile paths
- `niche` / `niche_label` — skincare context detection for intentional beauty output

---

## Validation Results

```bash
python -m project_brain.validate_11i2b_hardcoded_niche_fixes   # 12/12 PASS
python -m project_brain.validate_11i2_subtitle_runtime_foundation  # 17/17 PASS
python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution  # 17/17 PASS
```

### 11I-2B test matrix

| # | Test | Result |
|---|------|--------|
| 1 | Subtitle default fallback — no skincare terms | PASS |
| 2 | Subtitle accepts custom `highlight_keywords` | PASS |
| 3 | Subtitle legacy caller signature (no crash) | PASS |
| 4 | SEO generic — no skincare hashtags | PASS |
| 5 | SEO generic title — no skin/glow/mask/radiant | PASS |
| 6 | SEO skincare profile — skincare terms allowed | PASS |
| 7 | 11G regression | PASS |
| 8 | 11I-2 subtitle foundation regression | PASS |
| 9 | 11H-2d voice regression | PASS |

---

## Confirmations

| Requirement | Status |
|-------------|--------|
| Generic output no longer forces skincare | ✅ Neutral subtitle highlights + neutral SEO defaults |
| Explicit skincare still works via profile | ✅ `niche: selfcare` + `seo_keywords` produce skincare tags/titles |
| Content Brain Runtime unchanged | ✅ No `content_brain/` execution changes |
| Voice / Video runtime unchanged | ✅ 11H-2d regression PASS |
| Subtitle Runtime foundation unchanged | ✅ 11I-2 regression PASS |
| Legacy pipeline call signatures preserved | ✅ `SubtitleEngine()`, `build_package(...)` without profile still work |

### Legacy pipeline note

`full_video_pipeline.py` still calls `SubtitleEngine()` and `SEOPackageEngine().build_package(...)` without a profile. SEO/subtitle emphasis is now **topic-neutral** unless callers pass `highlight_keywords` or `profile`. Skincare **content** in timeline/narration is unchanged; only generic metadata/styling bias was removed.

---

## Next Recommended Phase

**PHASE 11I-3 — Subtitle Cue Generation Engine Design**

Design-only deliverable:

- Cue generation for `narration_text_only` and `narration_with_timing`
- Per-session `highlight_keywords` from channel profile / semantic universe
- SRT/ASS/VTT writer interfaces
- **Do not import** legacy `SubtitleEngine.highlight_words` pattern into 11I-3 implementation

Optional follow-up (not 11I-2B scope): migrate Content Brain WARNING items (profile-driven hook/visual dicts) from 11I-2A audit.
