# Content Brain — Dyatlov SEO Rule Fix Report

**Date:** 2026-06-03  
**Scope:** Mystery SEO malformed-title rejection + OpenAI quality enhancer guardrails  
**Status:** Fixed and validated

---

## Problem

`validate_content_brain_professional_upgrade.py` failed on Dyatlov E2E:

- **Bad title:** `Why the mystery of dyatlov pass Matters`
- **Expected style:** documentary/mystery titles such as:
  - The Untold Story of Dyatlov Pass
  - What Really Happened at Dyatlov Pass?
  - The Most Disturbing Clue From Dyatlov Pass
  - Why Dyatlov Pass Still Has No Simple Answer

### Root cause

SEO Director already produced good titles (`The Untold Story of Dyatlov Pass`), but the **OpenAI Quality Enhancement layer** overwrote them:

1. Dry-run fallback used generic template `Why {topic} Matters` with the full raw topic string.
2. Cached bad SEO payloads were reused (`project_brain/content_brain_quality_cache/`).
3. Enhancement apply path did not reject malformed mystery titles before replacing the local SEO Director output.

---

## Fix summary

### 1. SEO Director V3 (`content_brain_seo_director.py`)

- Bumped version to `seo_director_v3`.
- Added `MYSTERY_MALFORMED_SEO_PATTERNS` and exported `is_malformed_seo_title()`.
- Reject mystery-topic titles matching patterns such as:
  - `why the mystery`
  - `why the mystery of`
  - `why your mystery`
  - `mystery ... never works`
  - `how to mystery` / `how to the mystery`
  - `stop making this mystery mistake`
  - `why {full mystery topic} matters`
- Scoped aggressive topic-overlap rejection to **mystery topics only** (avoids rejecting valid instructional titles like `The Zander Fishing Method That Actually Works`).
- Added mystery title templates:
  - `Why {subject} Still Has No Simple Answer`
  - `The Most Disturbing Clue From {subject}`

### 2. OpenAI Quality Enhancer (`content_brain_openai_quality_enhancer.py`)

- Reuses `is_malformed_seo_title()` when applying SEO enhancements — malformed candidates are skipped; original good title is preserved if all candidates fail.
- Mystery-specific dry-run SEO titles use `{subject}` (e.g. Dyatlov Pass) instead of full topic string.
- Generic fallback uses `{subject}` instead of `{topic}` for non-mystery cases.
- Cache key version bumped to `seo_rules_v3` to invalidate stale bad entries.

### 3. Validation updates

- `validate_content_brain_professional_upgrade.py` — uses `is_malformed_seo_title()` for Dyatlov unit + E2E checks; adds explicit rejection tests for bad mystery patterns.

---

## Before / after

| Stage | Before | After |
|-------|--------|-------|
| SEO Director (unit) | The Untold Story of Dyatlov Pass | The Untold Story of Dyatlov Pass |
| E2E final SEO (with enhancement) | Why the mystery of dyatlov pass Matters | The Untold Story of Dyatlov Pass |
| Dyatlov malformed check | FAIL | PASS |

---

## Validation results

All three validators pass with dry-run env:

```powershell
$env:OPENAI_QUALITY_DRY_RUN="1"
$env:OPENAI_CLASSIFICATION_DRY_RUN="1"
python project_brain/validate_content_brain_professional_upgrade.py
python project_brain/validate_content_brain_openai_quality_enhancement.py
python project_brain/validate_content_brain_end_to_end_micro_test.py
```

| Validator | Result |
|-----------|--------|
| `validate_content_brain_professional_upgrade.py` | PASS |
| `validate_content_brain_openai_quality_enhancement.py` | PASS |
| `validate_content_brain_end_to_end_micro_test.py` | PASS |

---

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/content_brain_seo_director.py` | Mystery malformed rules, templates, `is_malformed_seo_title()` |
| `content_brain/execution/content_brain_openai_quality_enhancer.py` | Malformed filter on apply, mystery dry-run titles, cache v3 |
| `project_brain/validate_content_brain_professional_upgrade.py` | Stronger Dyatlov SEO assertions |

---

## Design rule (preserved)

- **Local SEO Director** remains primary title generator for mystery topics.
- **OpenAI enhancement** may refine SEO only when candidates pass malformed-title audit.
- Mystery topics must never receive instructional/generic templates like `Why {topic} matters` when `{topic}` contains `the mystery of ...`.

---

## Notes

- Old cache files under `project_brain/content_brain_quality_cache/` with pre-v3 keys are ignored automatically.
- Restart API server after deploy: `python -m ui.api.main`
