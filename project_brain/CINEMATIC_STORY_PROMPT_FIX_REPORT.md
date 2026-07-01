# Cinematic Story Prompt Fix — Forensic Report

**Phase:** CRITICAL-FIX — ISSUE 1  
**Date:** 2026-06-03

---

## Problem

Kling Frame story-first prompts read like **prompt metadata**, not movie scenes:

- "The chapter opens…"
- "Conflict level…"
- "Dialogue goal…"
- "Character behavior stays specific to this chapter role…"

Story-first audit passed (length + ratio) but output was unusable for generation.

---

## Root Cause

1. **Local template** (`_build_story_paragraphs`) explicitly emitted planning labels as prose.
2. **OpenAI system prompt** required the phrase `"chapter role"` in output.
3. **OpenAI user prompt** used labeled lines (`Chapter role:`, `Story objective:`, etc.) that the model echoed.
4. **Validation** checked for metadata markers (chapter role) instead of forbidding them.

---

## Fix

### Local template → cinematic prose

`_build_story_paragraphs()` rewritten to present-tense scene description using internal metadata only as writing guidance.

### OpenAI writer v2 (`kling_story_first_openai_writer_v2_cinematic`)

| Before | After |
|--------|-------|
| Labeled user lines | JSON **INTERNAL BRIEFING** with `_instruction: do not copy field names` |
| System: "use the phrase chapter role" | System: **FORBIDDEN** metadata labels list |
| Validates `chapter role` in output | Validates `validate_cinematic_story_body()` |

### Generation gate

`validate_kling_frame_content_plan()` now rejects prompts containing forbidden metadata phrases in the story body.

---

## Forensic Trace (OpenAI path)

Each OpenAI clip stores `composition_trace` in `prompt_authorship`:

```json
{
  "openai_request": {
    "system_prompt": "...",
    "user_prompt": "... INTERNAL BRIEFING json ..."
  },
  "openai_raw_response": "... model prose ...",
  "final_prompt": "... after footer normalize + continuity inject ...",
  "diff_summary": {
    "raw_length": 2400,
    "final_length": 2495,
    "technical_footer_rebuilt": true,
    "metadata_stripped_or_rewritten": true
  }
}
```

### Typical differences

| Stage | Content |
|-------|---------|
| **OpenAI request** | Internal JSON with `chapter_role`, `story_objective`, `conflict_level` — planning only |
| **Raw OpenAI response** | Should be scene prose; may still leak labels on bad attempts |
| **Final Kling prompt** | Normalized length, rebuilt `--- Technical execution ---` footer, continuity injection for clip 2+, metadata validation |

---

## Forbidden in story body

- Chapter role:
- Story objective:
- Dialogue goal:
- Conflict level
- Visual progression:
- Narrative context:
- Emotional temperature:
- The chapter opens
- Dialogue moment:
- (see `FORBIDDEN_STORY_METADATA_PHRASES` in `story_first_prompt_engine.py`)

---

## Validation

```bash
python project_brain/validate_cinematic_story_prompt.py
python project_brain/validate_story_first_prompt_architecture.py
python project_brain/validate_story_first_continuity_language_fix.py
```

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/story/story_first_prompt_engine.py` | Cinematic paragraphs, metadata validation, composition trace |
| `content_brain/story/kling_story_first_openai_writer.py` | v2 cinematic writer + internal briefing |
| `content_brain/execution/kling_frame_to_video_planner.py` | Cinematic validation in content plan |
