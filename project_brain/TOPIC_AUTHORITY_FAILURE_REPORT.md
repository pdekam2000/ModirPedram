# TOPIC AUTHORITY FAILURE REPORT

**Phase:** TOPIC-AUTHORITY-REPAIR-1  
**Date:** 2026-06-03  
**Status:** Repaired

---

## Observed failure

**Error:** `Topic authority mismatch in Prompt Builder handoff`

| Field | Value |
|-------|--------|
| **Authoritative topic** | `how to be legende in boxing` |
| **Prompt Builder `story_idea`** | *(was replaced)* narrative seed containing `Character: a knowledgeable presenter...` |
| **Story package topic** | Should match authoritative topic when run isolation creates package |
| **Visual subject** | Drifted to generic presenter instead of boxer / boxing gym |

---

## Where drift occurred

```text
Create Video (authoritative_topic)
  → Content Brain E2E (topic preserved)
  → Runway Prompt Builder.build()
       ✗ story_brief.rich_story_text() overwrote bundle.story_idea
       ✗ resolve_domain() returned "general" for boxing topic
       ✗ build_character() fell back to default_role_en = "a knowledgeable presenter"
       ✗ TopicAuthorityTrace.validate_topic("prompt_builder", bundle.story_idea) FAILED
  → Product Studio generate endpoint blocked (guard correct)
```

### Root cause chain

1. **`RunwayPromptBuilder.build()`** assigned `story_idea=story_brief.rich_story_text()` instead of preserving the user topic string.
2. **`resolve_domain()`** had no boxing/sports mapping → `"general"` domain.
3. **`DomainKnowledgeProfile.general.default_role_en`** = `"a knowledgeable presenter"`.
4. **`build_character()`** used presenter for instructional topics without domain-specific boxing role.
5. **Mismatch guard** correctly rejected the drift — validator was not the bug.

---

## Repair summary

| Layer | Fix |
|-------|-----|
| `runway_prompt_builder.py` | Preserve `authoritative_topic` in `story_idea`; use `narrative_story` only for prompt expansion; emit `topic`, `subject`, `visual_subject`, `topic_fidelity_score`; fail if score < 80 |
| `content_brain_topic_authority.py` | Added `score_topic_fidelity()`, `assert_topic_fidelity()`, generic presenter detection, sports domain hints |
| `domain_knowledge_layer.py` | Added `sports` domain; map boxing keywords → `sports` |
| `content_brain_character_builder.py` | Boxing/sports → `a dedicated young boxer` (not presenter) |
| `runway_story_brief_builder.py` | Always use `build_character()` when no explicit character; reject generic subject leakage |

---

## Post-repair alignment (expected)

| Topic | `story_idea` | `subject` (example) | `visual_subject` | Fidelity |
|-------|--------------|---------------------|------------------|----------|
| `how to be legende in boxing` | exact topic | young boxer / dedicated young boxer | boxer training subject | ≥ 80 |
| Cartoon cat topic | exact topic | cat / Whiskers | cat visual lock | ≥ 80 |
| Park couple topic | exact topic | girl/man/park markers | park-aligned subject | ≥ 80 |

---

## Validation

```bash
python project_brain/validate_topic_authority_alignment.py
```

Checks:

1. Boxing topic remains boxing  
2. Cat topic remains cat  
3. Park topic remains park  
4. No generic presenter replacement  
5. Topic fidelity ≥ 80  
6. Prompt Builder passes `TopicAuthorityTrace.validate_topic`

---

## Rule enforcement

- **Rule 1:** `authoritative_topic` is source of truth — Prompt Builder enriches prompts, not replaces topic string.  
- **Rule 2:** Generic presenter/host/expert blocked unless topic explicitly requests it.  
- **Rule 3:** `topic_fidelity_score` computed 0–100; build fails if < 80.  
- **Rule 4:** Output includes aligned `subject`, `topic`, `visual_subject`.  
- **Rule 5:** This report documents drift path and repair.  
- **Rule 6:** `validate_topic_authority_alignment.py` guards regression.

**Important:** Mismatch protection in `ProductStudioService.create_video_generate()` was **not** disabled.
