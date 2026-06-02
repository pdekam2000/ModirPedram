# PHASE 12J-D-B — Topic-Class Visual Grammar Implementation Report

**Date:** 2026-05-31  
**Status:** Implemented and validated  
**Design input:** `PHASE_12J_D_B_TOPIC_CLASS_VISUAL_GRAMMAR_DESIGN.md`  
**Audit input:** `PHASE_12J_D_A_STORY_INTELLIGENCE_DIVERSITY_AUDIT.md`

---

## Summary

Story Intelligence no longer selects camera, motion, and action from beat-only tables shared across all topics. A **TopicClassGrammarEngine** resolves a `topic_class` (animal, football, history, …) and applies beat-level grammar from `topic_class_grammar_v1.json`. The legacy evidence-macro behavior is preserved under `general_investigation` for regression. Runway automation, prompt composer defaults, and `schema_director_shots` shape are unchanged; only field **values** and new metadata differ.

---

## Problem (recap)

`VisualOriginalityEngine` used identical `_camera_for_beat` / `_motion_for_beat` / `_action_for_beat` lookups keyed only by `beat_id`. Dog, cat, football, history, and finance UAT sessions produced ~85–90% identical Runway prompt bodies after adapter truncation.

---

## Deliverables

| Artifact | Path |
|----------|------|
| Grammar config | `content_brain/config/topic_class_grammar_v1.json` |
| Resolver engine | `content_brain/engines/topic_class_grammar_engine.py` |
| Story Intelligence wiring | `content_brain/engines/story_intelligence_engine.py` |
| Validator | `project_brain/validate_12j_d_b_topic_class_visual_grammar.py` |
| This report | `project_brain/PHASE_12J_D_B_TOPIC_CLASS_VISUAL_GRAMMAR_IMPLEMENTATION_REPORT.md` |

**Not modified (per scope):** `RunwayBrowserOrchestrator`, Runway browser provider, `VideoProviderRouter`, browser launcher, voice/subtitle/assembly runtimes, UAT queue/dispatch, `runway_prompt_composer.py` (composer flag still off by default).

---

## 1. Grammar config (`topic_class_grammar_v1.json`)

- **Version:** `12j_d_b_v1` (constant `GRAMMAR_VERSION` in engine).
- **Classes (11):** `animal`, `football`, `mystery`, `horror`, `history`, `science`, `finance`, `self_care`, `travel`, `technology`, `general_investigation`.
- **Beats per class:** `HOOK_BEAT`, `CONTEXT_BEAT`, `ESCALATION_BEAT`, `PATTERN_BREAK`, `PAYOFF_BEAT`, `LOOP_SEED` (and `LOOP_SEED_BEAT` alias where builder normalizes).
- **Fields per beat:** `camera`, `motion`, `framing`, `action`, `reveal_style`, `escalation_style`, `payoff_style`, `visual_texture`, `pacing`.
- **`general_investigation`:** mirrors pre-12J-D-B legacy strings (e.g. HOOK: tight macro on evidence; ESCALATION: slow push-in on contradicting detail).

---

## 2. TopicClassGrammarEngine

**File:** `content_brain/engines/topic_class_grammar_engine.py`

**Responsibilities:**

| API | Behavior |
|-----|----------|
| `resolve_topic_class(topic, niche, profile, semantic_domain)` | Returns `(topic_class, resolution_source)` |
| `load_grammar_config()` | Reads JSON from `content_brain/config/topic_class_grammar_v1.json` |
| `get_grammar(topic_class, beat_id)` | Beat entry for class; unknown class → `general_investigation` |
| `apply_beat_grammar(...)` | Merges grammar into scene visual fields with `{anchor}` substitution |
| `LEGACY_GENERAL_INVESTIGATION` | Static legacy beat tables for tests and fallback |

**Resolution priority:**

1. `profile.topic_class` (explicit)
2. `NICHE_CLASS_MAP` (e.g. `football` niche → `football`, `dark_mystery` → `horror`)
3. `TOPIC_HEURISTIC_RULES` (token/phrase match on topic)
4. `SEMANTIC_DOMAIN_CLASS_MAP`
5. Fallback `general_investigation` (`fallback:general_investigation`)

**Metadata exposed:** `resolved_topic_class`, `resolution_source`, `grammar_version`, `beat_grammar_used` (per enrich pass).

---

## 3. Story Intelligence wiring

**File:** `content_brain/engines/story_intelligence_engine.py`

- `VisualOriginalityEngine` constructs `TopicClassGrammarEngine` (injectable for tests).
- On `enrich_scenes`, resolves topic class once per session context.
- `_camera_for_beat`, `_motion_for_beat`, `_action_for_beat` delegate to grammar engine when class ≠ legacy-only path; `general_investigation` uses legacy-compatible strings from config.
- Scene enrichment adds grammar-driven fields (`framing_style`, `reveal_style`, `escalation_style`, `payoff_style`, `visual_texture`, `pacing`) without changing `DirectorShot` / `schema_director_shots` keys.
- `StoryIntelligenceEngine.enhance()` adds top-level **`visual_grammar_metadata`** and explainability fields (`topic_class`, `topic_class_resolution`, `grammar_version`).

**Output shape preserved:** `schema_director_shots`, `scene_plan`, `visual_description`, `camera`, `motion`, `action`, `continuity_notes` — same keys; values topic-differentiated.

---

## 4. Example differentiation (validator excerpts)

| Pair | HOOK camera (prefix) |
|------|----------------------|
| animal vs football | `Eye-level close on {anchor}…` vs `Broadcast tight on ball and player…` |
| animal ESCALATION vs mystery ESCALATION | `Tracking medium shot following {anchor}…` vs `Over-shoulder examining evidence on {anchor}…` |

| Topic | Resolved class | Source |
|-------|----------------|--------|
| dog / cat | `animal` | `topic_heuristics:animal` |
| football | `football` | `topic_heuristics:football` |
| history / science / finance / travel | respective class | topic heuristics |
| unknown gibberish topic | `general_investigation` | `fallback:general_investigation` |

---

## 5. Validation

### Commands run

```text
python project_brain/validate_12j_d_b_topic_class_visual_grammar.py
python project_brain/validate_12j_c_runway_prompt_composer.py
```

### Results

| Suite | Result |
|-------|--------|
| `validate_12j_d_b_topic_class_visual_grammar.py` | **25/25 passed** |
| `validate_12j_c_runway_prompt_composer.py` | **22/22 passed** |

**12J-D-B checks include:** resolution matrix (dog/cat/football/history/science/finance/travel/unknown), animal vs football HOOK inequality, animal vs mystery ESCALATION inequality, legacy `general_investigation` HOOK/ESCALATION cameras, metadata payload, `schema_director_shots` schema unchanged, Story Intelligence imports/wiring, Runway orchestrator file hash unchanged, composer subprocess pass.

**Fix applied during validation:** `NarrativeContext` in validator required `sensory_anchor` — added for full Story Intelligence enhance path test.

---

## 6. Architecture flow (post-implementation)

```text
Content brief / UAT topic
  → StoryIntelligenceEngine.enhance()
       → TopicClassGrammarEngine.resolve_topic_class()
       → VisualOriginalityEngine.enrich_scenes()
            → apply_beat_grammar(topic_class, beat_id)
       → schema_director_shots (unchanged shape)
       → visual_grammar_metadata
  → SessionPromptAdapter → Runway (unchanged automation)
```

Optional `RunwayPromptComposer` (flag off) still consumes the same shot schema; richer grammar increases prompt diversity when composer is enabled later.

---

## 7. Success criteria (operator UAT)

For the same 2-clip UAT pattern:

| Topic | Expected grammar |
|-------|------------------|
| dog / cat | `animal` — eye-level / tracking pet-native camera |
| football | `football` — broadcast / sports action |
| history | `history` — archival / documentary |
| finance | `finance` — market / data visual texture |

Runway prompt bodies should no longer cluster at ~85–90% token overlap across unrelated verticals (measure on next UAT run with composer flag or diff tool).

---

## 8. Regression and rollback

- Set `profile.topic_class` to `general_investigation` or use unknown topics to force legacy evidence-macro grammar.
- Remove or bypass `TopicClassGrammarEngine` in `VisualOriginalityEngine` only if rolling back — config file can remain inert.

---

## 9. Follow-ups (out of scope)

- **12J-D-C:** beat selection policy (which beats fire per clip count).
- **12J-D-D:** composer diversity gate when flag on.
- **12J-C2B-C:** UAT tab selector + default 10s duration (Runway ops).

---

## 10. Files touched (implementation scope)

**Created:** `content_brain/config/topic_class_grammar_v1.json`, `content_brain/engines/topic_class_grammar_engine.py`, `project_brain/validate_12j_d_b_topic_class_visual_grammar.py`, this report.

**Modified:** `content_brain/engines/story_intelligence_engine.py`, `project_brain/validate_12j_d_b_topic_class_visual_grammar.py` (sensory_anchor fix).

**Verified unchanged:** Runway browser orchestrator/provider paths (validator hash check), composer module and dispatch wiring.

---

*End of PHASE 12J-D-B implementation report.*
