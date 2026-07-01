# Story-First Continuity Language Fix — Report

**Phase:** STORY-FIRST-CONTINUITY-LANGUAGE-FIX  
**Status:** FIXED — validation PASS  
**Date:** 2026-06-03

---

## Failure

```
clip 2: prompt must include prior-clip continuity language
```

Observed when OpenAI authorship path was active:

- `story_first_audit` passed (`story_percent` > 85%, `prompt_length` ~2500)
- Failure occurred in `validate_kling_frame_content_plan()` — **after** story-first ratio checks

---

## Root Cause

Two validators checked **different phrases** for clip 2+ handoff:

| Layer | Location | Required markers |
|-------|----------|------------------|
| OpenAI writer | `kling_story_first_openai_writer._validate_openai_prompt()` | `"continuing immediately from"` OR `"resumes without reset"` |
| Content planner | `validate_kling_frame_content_plan()` line 376 | `"previous"` OR `"resumes"` |

OpenAI often produced valid handoff prose with **"continuing immediately from …"** but **without** the substrings `"previous"` or `"resumes"`.

Example failing clip 2 opening:

> Character behavior stays specific to this chapter role (Payoff). The young woman and wounded robot dog sprint forward, **continuing immediately from** the glowing path deeper into the scene. Native in-scene audio …

- `"continuing immediately from"` present → OpenAI writer OK  
- `"previous"` absent, `"resumes"` absent → **planner continuity validator FAIL**

`validate_kling_frame_plan_story_first()` only checks length and story ratio — it does **not** check continuity language. That is why story-first audit passed while continuity validation failed.

Local template path was unaffected because `_build_story_paragraphs()` always opens clip 2+ with:

> The story **resumes** without reset, continuing immediately from … **previous** ending frame …

---

## Fix

Added automatic injection in `content_brain/story/story_first_prompt_engine.py`:

| Function | Role |
|----------|------|
| `has_prior_clip_continuity_language()` | Matches planner rule: `"previous"` or `"resumes"` |
| `build_prior_clip_continuity_opener()` | Canonical handoff paragraph (includes all markers) |
| `ensure_prior_clip_continuity_language()` | Prepends opener to story body when markers missing; refits 2300–2500 length |

Wiring:

1. `compose_story_first_frame_prompt_primary()` — safety net on OpenAI and local returns  
2. `try_write_story_first_prompt_openai()` — inject before OpenAI acceptance validation  
3. OpenAI writer validation aligned to planner rule via `has_prior_clip_continuity_language()`

Validation logic in `validate_kling_frame_content_plan()` was **not** weakened or bypassed.

---

## Required Markers (unchanged)

Clip index > 1 must satisfy **at least one**:

- `"previous"` (case-insensitive substring)
- `"resumes"` (case-insensitive substring)

Injected opener also includes `"continuing immediately from"` for architecture / use-frame handoff tests.

---

## Validation

```bash
python project_brain/validate_story_first_continuity_language_fix.py
python project_brain/validate_story_first_prompt_architecture.py
python project_brain/validate_kling_prompt_openai_authorship.py
python project_brain/validate_story_progression_engine_p5.py
```

Mock OpenAI clip 2 (missing markers before fix):

| Check | Before | After injection |
|-------|--------|-----------------|
| `previous` | absent | present |
| `resumes` | absent | present |
| `continuing immediately from` | present | present |
| story_percent | ~90% | ≥ 80% |
| prompt_length | 2500 | ≥ 2300 |
| `validate_kling_frame_content_plan` | FAIL | PASS |

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/story/story_first_prompt_engine.py` | Continuity detection + injection helpers; wired in primary composer |
| `content_brain/story/kling_story_first_openai_writer.py` | Inject before validate; align validation with planner |
| `project_brain/validate_story_first_continuity_language_fix.py` | **New** validation suite |

---

## use-frame Chain

No changes to `kling_use_frame_runtime.py`, `kling_frame_continuity_runtime.py`, or frame handoff logic. Prompt text only — runtime chain unchanged.
