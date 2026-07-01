# Topic Identity Drift Report

**Phase:** DELIVERY-QUALITY-RECOVERY — Priority 3  
**Run:** `cb_e2e_20260614_195440_8bf41b6b`  

---

## Symptom

| Expected (user topic) | Delivered story package |
|-----------------------|-------------------------|
| A boy finds a dragon egg in the forest and hides it from everyone | Whiskers the cat, Sage the fox, jungle path, crystal seed |
| Boy + dragon egg narrative | Cat/fox cartoon template dialogue |

Runway **video prompts** correctly reference boy/dragon (from Content Brain E2E). **Story package** and **dialogue plan** use unrelated cartoon cast.

---

## Where topic identity is lost

### Transformation chain

```
User topic (authoritative)
    ↓  [Content Brain E2E — preserved in story brief & Runway prompts]
RunwayStoryBrief + prompts (boy, dragon egg, forest)     ← topic OK here
    ↓  [POST-RUNWAY: audio_post_processing rebuilds story package]
build_and_save_story_package(story_brief from E2E JSON)
    ↓
detect_genre(topic, story_brief)  → "cartoon"              ← DRIFT START
    ↓
build_story_blueprint() → Whiskers/Sage template fields     ← DRIFT AMPLIFIED
    ↓
build_character_profiles() → Whiskers, Sage, Narrator
    ↓
build_dialogue_plan() → cat/fox preset lines
    ↓
Story package JSON saved (wrong cast, wrong setup)
    ↓
Narration uses clip beats from E2E story brief (boy/dragon text)
    ↓
Dialogue/character voices never synthesized
```

**Topic is preserved for Runway generation but replaced in the post-run story package layer.**

---

## Exact files and functions

### 1. Genre misclassification (trigger)

| Item | Detail |
|------|--------|
| **File** | `content_brain/story/story_niche.py` |
| **Function** | `detect_genre(topic, story_brief)` |
| **Mechanism** | Keyword scoring on combined haystack: topic + story_brief fields |
| **This run** | Topic alone → `educational`. Topic + E2E story_brief → **`cartoon`** because keyword **`magical`** matches `GENRE_KEYWORDS["cartoon"]` |
| **Source of "magical"** | E2E story brief (`scene_progression`, mood, concept text — e.g. “magical artifact”, “mystical forest”) |

### 2. Template blueprint overwrite

| Item | Detail |
|------|--------|
| **File** | `content_brain/story/story_architect.py` |
| **Function** | `build_story_blueprint()` → `_templates("cartoon")` |
| **Mechanism** | When genre=cartoon, fills hook/setup/conflict/etc. from hardcoded Whiskers/Sage template unless brief field non-empty |
| **This run** | `setup` = “Whiskers the cat and Sage the fox enter a sunlit jungle path…” |
| **Title** | Rewritten to SEO-style “Why Your A Boy Finds a Dragon Egg…” but body beats remain template |

### 3. Hardcoded cartoon cast

| Item | Detail |
|------|--------|
| **File** | `content_brain/story/character_director.py` |
| **Function** | `build_character_profiles()` → `_cartoon_cast(topic)` |
| **Mechanism** | If `blueprint.genre == "cartoon"` OR topic contains cartoon keywords → always returns Whiskers + Sage + Narrator |
| **This run** | Characters: Whiskers, Sage, Narrator — **no boy, no dragon**

### 4. Preset dialogue (ignores topic)

| Item | Detail |
|------|--------|
| **File** | `content_brain/story/dialogue_engine.py` |
| **Function** | `build_dialogue_plan()` → `_cartoon_scene_dialogue()` |
| **Mechanism** | Fixed 4-scene preset lines (“Whoa! What is THAT?!”, “crystal seed”, “jungle”) — beat label only changes scene title string |
| **Also** | `content_brain/story/dialogue_naturalization_engine.py` — same Whiskers/Sage presets |

### 5. Story package orchestration (invocation point)

| Item | Detail |
|------|--------|
| **File** | `content_brain/story/story_package.py` |
| **Function** | `build_story_package()` / `build_and_save_story_package()` |
| **Caller** | `content_brain/audio/audio_post_processing.py` → `run_audio_post_processing()` (line ~148) |
| **Input** | `story_brief` loaded from E2E JSON `story_generation` step — **does not pass topic authority into blueprint genre override** |

---

## What did NOT drift (for comparison)

| Layer | Topic preserved? | Evidence |
|-------|------------------|----------|
| UI / topic authority trace | YES | `topic_authority_trace.json` — no mismatches |
| Content Brain E2E story brief | YES | `clip_beats` reference boy, dragon egg, forest |
| Runway prompts | YES | `cb_e2e_*_runway_prompts.txt` — boy/dragon beats |
| Runway generated clips | YES | Vision review: boy + dragon egg in forest |
| Narration script (ElevenLabs) | PARTIAL | Boy/dragon beat summaries; includes “Meet our little explorer!” filler |

---

## Root cause (single statement)

**Post-processing rebuilds the story package using genre detection that classifies the E2E story brief as `cartoon` (via the word “magical”), which activates hardcoded Whiskers/Sage templates in `story_architect.py`, `character_director.py`, and `dialogue_engine.py` — decoupled from the authoritative topic and from the Runway prompt story brief.**

---

## Contributing factors

1. **Two story authorities** — E2E `RunwayStoryBrief` for video vs. post-run `StoryPackage` for audio/dialogue.
2. **Genre keyword false positive** — “magical” in fantasy dragon topic triggers cartoon genre.
3. **Template-first blueprint** — `_templates()` defaults override topic semantics.
4. **Dialogue not wired to narration** — Even correct dialogue in package is unused; narrator-only path uses E2E clip beats instead.

---

## Recommended fix direction (design only)

1. Pass **authoritative topic + run_id** into `build_story_package`; lock genre/characters from E2E story brief, not `detect_genre()` alone.
2. Remove or narrow **“magical” → cartoon** keyword mapping for human-protagonist topics.
3. **Single story package source** — build once in E2E, reload in post-processing (no rebuild from templates).
4. Fail closed if story package `topic` field ≠ authoritative topic.

**No implementation in this phase.**
