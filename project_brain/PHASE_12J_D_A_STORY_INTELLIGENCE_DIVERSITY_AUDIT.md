# PHASE 12J-D-A — Story Intelligence Diversity Audit

**Date:** 2026-06-02  
**Status:** Audit only — no implementation, no code changes  
**Context:** Runway generation and prompt injection are confirmed working. Controlled-tab confusion is a UX issue. **Content diversity** (near-identical scene grammar across unrelated topics such as dog vs cat) is the primary quality bottleneck.

**Evidence sessions:** `exec_uat_20260602_080026` (dog), `exec_uat_20260602_110110` (cat) — ~85–90% shared camera/action/beat skeleton.

**Primary file:** `content_brain/engines/story_intelligence_engine.py`

---

## Executive Summary

Story Intelligence does **not** select camera or action from topic semantics, Content Brief creative decisions, or semantic universe clusters. It applies **fixed per-beat lookup tables** in `VisualOriginalityEngine` (`_camera_for_beat`, `_motion_for_beat`, `_action_for_beat`) after `SceneProgressionEngine` picks beats by **global priority** (for 2-clip UAT: always **HOOK_BEAT + ESCALATION_BEAT**).

**Topic influence today** is mostly **lexical substitution** (`anchor` / `topic_tokens[0]` / topic string in `visual_description`). **Niche influence** is limited to **lighting base** (3 branches) and **NICHE_VISUAL_LEXICON** word list (4 keyed niches + `general` fallback). **Semantic universe** only appends cluster names to the lexicon list — it does **not** change camera grammar.

| Question | Short answer |
|----------|----------------|
| Are camera patterns fixed by beat? | **Yes** — `_camera_for_beat(beat_id)` only |
| Are actions fixed by beat? | **Yes** — template per beat; only `{anchor}` token swaps |
| Why dog ≈ cat? | Same niche (`general`), same 2 beats, same tables |
| % topic-independent structure | **~85–90%** for typical 2-clip UAT (audit estimate) |
| Main bottleneck | `VisualOriginalityEngine` + `SceneProgressionEngine._select_beats_for_clips` |

---

## Current Story Intelligence Flow

```text
ContentBriefOrchestrator.run()
  ├─ profile (niche, optional semantic_universe on profile dict)
  ├─ StoryArchitectureEngine.build_blueprint()     → StoryBlueprint (6 beats, narration, hints)
  ├─ VideoFormatPlanner.plan()                     → clip_count, clip_duration, target_duration
  ├─ StoryIntelligenceEngine.enhance()  ◄── DIVERSITY BOTTLENECK
  │     ├─ _build_context()                          → NarrativeContext
  │     ├─ NarrativeStrategyEngine.build()           → niche_visual_language[] (lexicon only)
  │     ├─ EmotionalArcEngine.build()                → emotion per beat_id (fixed EMOTIONAL_TARGETS)
  │     ├─ SceneProgressionEngine.build()            → scene shells + beat selection
  │     ├─ VisualOriginalityEngine.enrich_scenes()   → camera, motion, action, subject, lighting
  │     ├─ AntiGenericSceneEngine.audit()            → keyword trope check (not structural diversity)
  │     ├─ CinematicBeatEngine.build_director_shots()
  │     └─ CinematicBeatEngine.to_schema_director_shots()  → schema_director_shots
  ├─ RetentionMapEngine.build()                      → platform notes (parallel; not camera grammar)
  └─ brief_snapshot.run_context.story_intelligence stored on session

Later (dispatch):
  SessionPromptAdapter.build() → concatenates schema_director_shots fields → Runway prompts
  [optional] RunwayPromptComposer if flag ON — merges hook/retention; does not replace beat camera tables
```

**Content Brief influences Story Intelligence indirectly:**

| Brief input | Influences SI? | How |
|-------------|----------------|-----|
| `trend_signal.topic` | Yes (weak) | `topic_tokens`, anchor strings |
| `profile.niche` | Yes (weak) | lighting branch, lexicon list |
| `profile.semantic_universe.clusters` | Yes (weak) | extra lexicon strings only |
| `story_blueprint.beats` | Yes (medium) | which beat_ids exist and timing |
| `video_format_plan.clip_count` | Yes (strong) | `_select_beats_for_clips` → scene count & beat mix |
| `hook_package` | Yes (weak) | hook_class, narrative premise text |
| `story_blueprint.story_mode` / `reveal_type` | Yes (weak) | VO intents, twist text |
| Story Architecture `visual_prompt_hint` | **No** | Not read by Story Intelligence engines |
| Retention map | **No** | Built after SI; composer may fold later |

---

## Camera Selection Flow

### 1. How are camera movements selected?

**Single function, beat-only:**

```375:384:content_brain/engines/story_intelligence_engine.py
    def _camera_for_beat(self, beat_id: str) -> str:
        cameras = {
            "HOOK_BEAT": "Tight macro on evidence detail, shallow depth of field",
            "CONTEXT_BEAT": "Medium-wide establishing with subject in lower third",
            "ESCALATION_BEAT": "Slow push-in on contradicting detail",
            ...
        }
        return cameras.get(beat_id, "Purposeful medium shot")
```

**Motion** (separate field, also beat-only):

```400:408:content_brain/engines/story_intelligence_engine.py
    def _motion_for_beat(self, beat_id: str) -> str:
        motions = {
            "HOOK_BEAT": "Snap focus rack to evidence detail",
            "ESCALATION_BEAT": "Controlled push-in as tension builds",
            ...
        }
```

**No inputs:** topic, niche (except lighting), semantic universe, story_mode, or Content Brief.

### 2. Mapping to `schema_director_shots`

`CinematicBeatEngine.to_schema_director_shots()` splits `camera_direction` on **first comma**:

```563:567:content_brain/engines/story_intelligence_engine.py
            camera_parts = camera.split(",", 1)
            camera_shot = camera_parts[0].strip()
            camera_movement = (
                camera_parts[1].strip() if len(camera_parts) > 1 else "Static hold"
            )
```

| Beat | `camera_shot` (Runway-facing) | `camera_movement` |
|------|------------------------------|-------------------|
| HOOK | `Tight macro on evidence detail` | `shallow depth of field` |
| ESCALATION | `Slow push-in on contradicting detail` | `Static hold` (no comma in string) |

This matches observed dog/cat outputs: hook = macro + shallow DOF; escalation = push-in + static hold.

### 3. User hypothesis vs actual mapping

| Operator shorthand | Actual beat assignment in code |
|--------------------|--------------------------------|
| HOOK → push-in | **Incorrect for HOOK** — push-in is **ESCALATION** camera string; HOOK is **macro + shallow DOF** |
| ESCALATION → reveal | **Partially** — action is `Contrast two readings of {anchor}`; camera is push-in, not “reveal” framing |
| PAYOFF → close up | **Would apply if PAYOFF selected** — `Locked-off hero frame...` (not used in 2-clip UAT) |

---

## Action Selection Flow

### How are actions selected?

```422:431:content_brain/engines/story_intelligence_engine.py
    def _action_for_beat(self, beat_id: str, anchor: str) -> str:
        actions = {
            "HOOK_BEAT": f"Reveal {anchor} detail entering frame",
            "ESCALATION_BEAT": f"Contrast two readings of {anchor}",
            ...
        }
```

- `anchor` = `context.topic_tokens[0]` (first significant topic token, e.g. `dog` / `cat`).
- **Grammar is fixed** per beat; only the token changes.
- **Subject** is similarly templated: `f"{anchor} evidence element"`.

### Dog vs cat (clip 1 / clip 2 actions)

| Clip | Beat | Dog | Cat |
|------|------|-----|-----|
| 1 | HOOK | Reveal **dog** detail entering frame | Reveal **cat** detail entering frame |
| 2 | ESCALATION | Contrast two readings of **dog** | Contrast two readings of **cat** |

---

## Scene Grammar / Scene Structure Flow

### Scene structures — who builds what?

| Stage | Engine | Output |
|-------|--------|--------|
| Beat timeline | `StoryArchitectureEngine` | 6 beats with narration, `visual_prompt_hint` (not consumed by SI camera logic) |
| Beat → scene selection | `SceneProgressionEngine` | `scene_id`, `beat_id`, `narrative_purpose`, `connects_from/to`, `story_advance` |
| Visual grammar | `VisualOriginalityEngine` | camera, motion, action, lighting, subject, environment, `visual_description` |
| Director payload | `CinematicBeatEngine` | `prompt_intent`, continuity notes |
| Final schema | `to_schema_director_shots` | `DirectorShot` for adapter |

### Beat-to-scene mapping (`SceneProgressionEngine`)

```270:292:content_brain/engines/story_intelligence_engine.py
        priority = ["HOOK_BEAT", "ESCALATION_BEAT", "PAYOFF_BEAT", "LOOP_SEED"]
        ...
        return selected[:clip_count]
```

For **`clip_count == 2`** (common UAT / short plan):

- **Always** HOOK_BEAT scene 1 + ESCALATION_BEAT scene 2.
- CONTEXT, PATTERN_BREAK, PAYOFF, LOOP_SEED **dropped** unless clip_count ≥ 3.
- **Topic does not affect** which beats are chosen — only count does.

### `visual_description` (lexicon layer)

```352:355:content_brain/engines/story_intelligence_engine.py
        visual_description = (
            f"{lexicon} highlighting {anchor} during {scene['beat_role']} — "
            f"specific to {context.topic}, not generic stock footage."
        )
```

`lexicon` = `visual_language[index % len(visual_language)]` — rotates list position by scene index, not by topic class.

---

## Answers to Required Questions

### 1–2. Camera and actions

See **Camera Selection Flow** and **Action Selection Flow** above. Selection is **deterministic lookup on `beat_id`**.

### 3. Scene structures

Scene **structure** = beat role + fixed cinematic fields + templated continuity (`Follows HOOK_BEAT; sets up close.`). Not derived from topic category.

### 4. Are camera patterns fixed by beat type?

**Yes.** Full table:

| beat_id | camera_direction | motion_direction |
|---------|------------------|------------------|
| HOOK_BEAT | Tight macro on evidence detail, shallow depth of field | Snap focus rack to evidence detail |
| CONTEXT_BEAT | Medium-wide establishing... | Gentle lateral slide... |
| ESCALATION_BEAT | Slow push-in on contradicting detail | Controlled push-in as tension builds |
| PATTERN_BREAK | Whip-pan or split-diopter... | Abrupt perspective shift... |
| PAYOFF_BEAT | Locked-off hero frame... | Hold steady... |
| LOOP_SEED | Pull-back reveal... | Slow drift away... |

### 5. Are actions fixed by beat type?

**Yes** — templates with `{anchor}` substitution only (see `_action_for_beat`).

### 6. Which functions create the repeated grammar?

| Function | File | Role in repetition |
|----------|------|---------------------|
| **`VisualOriginalityEngine._camera_for_beat`** | `story_intelligence_engine.py` | **Primary** — identical camera per beat across topics |
| **`VisualOriginalityEngine._motion_for_beat`** | same | **Primary** — identical motion per beat |
| **`VisualOriginalityEngine._action_for_beat`** | same | **Primary** — same action structure |
| **`VisualOriginalityEngine._build_visual`** | same | subject/environment/description templates |
| **`SceneProgressionEngine._select_beats_for_clips`** | same | **Forces HOOK+ESCALATION** for 2 clips |
| **`SceneProgressionEngine._narrative_purpose`** | same | Same purpose templates per beat |
| **`CinematicBeatEngine.build_director_shots`** | same | Assembles same fields into `prompt_intent` |
| **`CinematicBeatEngine.to_schema_director_shots`** | same | Splits camera string → `camera_shot` / `camera_movement` |
| **`NarrativeStrategyEngine._resolve_visual_language`** | same | Lexicon variety only (not camera) |
| **`AntiGenericSceneEngine.audit`** | same | Does **not** enforce cross-topic camera diversity |

**Not primary for visual grammar:** `StoryArchitectureEngine` (narration/hints), `RetentionMapEngine`, `RunwayPromptComposer` (when off).

### 7. Does topic category influence scene grammar today?

**No.** There is **no** `topic_category`, `topic_class`, or animal/vertical taxonomy in Content Brain engines.

Only `topic`, `topic_tokens` from `_topic_anchor_tokens(topic)` — used as **string insertions**, not to select grammar tables.

### 8. Does niche influence scene grammar today?

**Partially — lighting and lexicon only.**

| Niche key in `NICHE_VISUAL_LEXICON` | Lighting base (`_lighting_for_beat`) | Camera/action |
|-------------------------------------|--------------------------------------|---------------|
| `football` | Broadcast monitor glow... | **Same beat tables** |
| `dark_mystery`, `storytelling` (profile) | Low-key practical | **Same beat tables** |
| `general` (UAT default) | Natural motivated light... | **Same beat tables** |
| horror / mystery / science / etc. (no key) | **Falls back to general** | **Same beat tables** |

Registry maps `horror` → `dark_mystery_profile.json` for **profile load**, but camera/action tables do not read horror-specific shot grammar.

### 9. Does semantic universe influence scene grammar today?

**Minimal.** `_build_context` copies cluster **names** into `NarrativeContext.semantic_clusters`. `_resolve_visual_language` may **append** cluster names to `niche_visual_language[]`.

**Does not:** select camera, motion, action, or beat mix. Semantic Universe Engine is not invoked inside `StoryIntelligenceEngine.enhance()` directly; it depends on profile being pre-populated on the brief path.

### 10. Does Content Brief influence camera/action selection?

**No direct path.** Content Brief supplies:

- Profile + topic + blueprint beats + format plan clip count.

Story Intelligence **does not** read:

- `retention_map` (built after SI),
- `visual_prompt_hint` from Story Architecture beat plans,
- `decision_package`, scorecard, or trend enrichment fields for cinematography.

**Indirect:** `clip_count` controls beat subset; `niche` controls lighting/lexicon branch.

### 11. What percentage of final scene structure is topic-independent?

**Audit estimate for 2-clip UAT (HOOK + ESCALATION), `general` niche:**

| Field group | Topic-independent share | Notes |
|-------------|-------------------------|-------|
| `beat_id` sequence | **100%** | Always HOOK → ESCALATION for clip_count=2 |
| `camera_shot` / `camera_movement` | **100%** | Pure `beat_id` lookup |
| `motion_direction` | **100%** | Pure `beat_id` lookup |
| `lighting` (general niche) | **100%** | Same general branch + beat accent |
| `action` / `subject` grammar | **~90%** | Fixed template; ~1 token varies |
| `visual_description` / lexicon line | **~60–70%** | Lexicon phrase + topic name |
| `narrative_purpose` / continuity | **~85%** | Template + beat names in continuity |
| **Overall cinematic grammar** | **~85–90%** | Aligns with operator observation |

### 12. Why do dog and cat produce nearly identical scenes?

1. **Same UAT niche:** `general` for both sessions.  
2. **Same beat pair:** 2 clips → `HOOK_BEAT` + `ESCALATION_BEAT` only.  
3. **Same lookup tables:** `_camera_for_beat`, `_motion_for_beat`, `_action_for_beat`.  
4. **Same subject pattern:** `{token} evidence element`.  
5. **Same emotional targets:** `EMOTIONAL_TARGETS` per beat.  
6. **Composer off** on cat session — no material change to camera grammar; dog session with composer on still inherited SI camera lines.  
7. **Anti-generic audit** passed — it checks trope **keywords**, not structural diversity between topics.

### 13. Which files/functions would need to change for true diversity?

| Priority | File / component | Change type |
|----------|----------------|-------------|
| P0 | `VisualOriginalityEngine` (`_camera_for_beat`, `_motion_for_beat`, `_action_for_beat`, `_build_visual`) | Topic-class or niche grammar tables |
| P0 | `SceneProgressionEngine._select_beats_for_clips` | Topic-aware beat mix (e.g. animals → HOOK+CONTEXT+PAYOFF) |
| P1 | `NarrativeStrategyEngine` | Topic taxonomy → visual grammar profile selection |
| P1 | `content_brain/profiles/*.json` | `scene_grammar` blocks per vertical (declarative config) |
| P2 | `StoryArchitectureEngine` | Optional beat-specific `visual_prompt_hint` consumed by SI |
| P2 | `AntiGenericSceneEngine` | Structural fingerprint: reject repeated camera grammar across memory |
| P3 | `runway_prompt_composer.py` | Diversity audit gate (12J-D design) — after SI fix, not instead of |
| Out of scope | Runway browser / `SessionPromptAdapter` alone | Cannot fix upstream identical `schema_director_shots` |

---

## Diversity Category Evaluation

**Method:** Trace code paths for `niche` profile resolution + `NICHE_VISUAL_LEXICON` + `_lighting_for_beat`. No LLM; no topic_class.

| Category | Typical profile / niche | Lexicon vs general | Lighting vs general | Camera/action vs general (2-clip) |
|----------|-------------------------|--------------------|---------------------|-----------------------------------|
| **animals** (dog, cat) | `general` (UAT) | Token-appended frames only | Same | **Identical** HOOK macro + ESCALATION push-in |
| **football** | Needs `niche=football` profile* | Broadcast replay, VAR, etc. | Stadium/broadcast base | **Identical** beat cameras |
| **mystery** | `dark_mystery` if selected | Blueprint floor plan, cold draft, etc. | Low-key | **Identical** beat cameras |
| **horror** | Registry → `dark_mystery` | Same as mystery pack | Low-key | **Identical** beat cameras |
| **history** | `general` (no pack) | General evidence lexicon | Natural motivated | **Identical** |
| **science** | `general` | General + token frames | Natural motivated | **Identical** |
| **self-care** | `general` | General | Natural motivated | **Identical** |
| **finance** | `general` | General | Natural motivated | **Identical** |
| **technology** | `general` | General | Natural motivated | **Identical** |
| **travel** | `general` | General | Natural motivated | **Identical** |

\*Football has lexicon entries in code but **no** `football_profile.json` in `config/content_brain/profiles/` — only `default` and `dark_mystery` packs exist; football lexicon applies only if `profile.niche == "football"`.

**Conclusion:** Changing **topic word** or **niche label** without new grammar tables does **not** produce materially different **camera/action structure** for short 2-clip plans. Mystery/horror changes **lighting words** and **lexicon nouns**, not shot grammar.

---

## Dog vs Cat Prompt Comparison (Final Runway Path)

**Source:** `schema_director_shots` → `SessionPromptAdapter` → `prompt_bundle.prompts`

| Dimension | Dog (`080026`) | Cat (`110110`) | Same? |
|-----------|----------------|----------------|-------|
| Beat 1 | HOOK | HOOK | Yes |
| Beat 2 | ESCALATION | ESCALATION | Yes |
| camera_shot clip 1 | Tight macro on evidence detail | Tight macro on evidence detail | **Yes** |
| camera_movement clip 1 | shallow depth of field | shallow depth of field | **Yes** |
| camera_shot clip 2 | Slow push-in on contradicting detail | Slow push-in on contradicting detail | **Yes** |
| camera_movement clip 2 | Static hold | Static hold | **Yes** |
| lighting | Natural motivated + accents | Same | **Yes** |
| action pattern | Reveal {token} / Contrast two readings | Same templates | **Yes** (token only) |
| subject pattern | {token} evidence element | Same | **Yes** |
| Opening lexicon line | Different (composer on dog) | Different | No (surface text only) |

**RunwayPromptComposer:** OFF on cat; ON on dog — changes **hook/retention wording** in prompt string, **not** `camera_shot` / `camera_movement` from SI tables.

---

## Exact Source of Repetitive Structure

```text
clip_count == 2
  → SceneProgressionEngine._select_beats_for_clips
       → [HOOK_BEAT, ESCALATION_BEAT]
  → VisualOriginalityEngine._build_visual (per scene)
       → _camera_for_beat(beat_id)      ← FIXED STRING
       → _motion_for_beat(beat_id)      ← FIXED STRING
       → _action_for_beat(beat_id, anchor) ← FIXED TEMPLATE
       → subject = f"{anchor} evidence element"
  → CinematicBeatEngine.to_schema_director_shots
       → SessionPromptAdapter._compose_prompt
```

**Root architectural bottleneck:** Story Intelligence treats **beat_id** as the sole cinematography key. **Topic** and **vertical** are copy layers, not grammar selectors.

---

## Diversity Limitations (Systemic)

| Limitation | Detail |
|------------|--------|
| No topic taxonomy | `_topic_anchor_tokens` only; no animal/person/place/event classes |
| Beat-first cinematography | One global short-form evidence-investigation grammar |
| 2-clip collapse | Drops PAYOFF/CONTEXT/PATTERN_BREAK → same two-shot arc every time |
| Lexicon ≠ grammar | Rotating phrases in `visual_description` do not change Runway camera fields |
| Niche packs underused | Only lighting + lexicon; no profile-driven camera tables |
| Semantic universe peripheral | Cluster names appended to list; no shot selection |
| Story Architecture hints ignored | `visual_prompt_hint` not wired to SI |
| Anti-generic shallow | Keyword deny list; no cross-run grammar memory enforcement |
| Memory engine | Compares fingerprints of descriptions; does not block template reuse |
| Composer default off | UAT does not enable; even when on, does not override SI camera |

---

## Candidate Architecture Options (Future — No Implementation)

### Option A — Topic-class grammar matrix (recommended P0)

Introduce `TopicClass` (animal, sports, mystery, explainer, product, travel, …) inferred from topic + niche.

```text
grammar = SCENE_GRAMMAR[topic_class][beat_id]
camera_shot, camera_movement, action = grammar.pick(variant_seed)
```

**Pros:** Deterministic, testable, explicit dog vs cat differences.  
**Cons:** Requires taxonomy rules and maintenance.

### Option B — Profile-declared `scene_grammar` in JSON

Extend `config/content_brain/profiles/*.json` with per-beat camera/action pools; loader passes into SI.

**Pros:** Operator-tunable per vertical without code deploy for wording.  
**Cons:** Profile proliferation; still need beat selection logic.

### Option C — Beat selection policy engine

Separate from camera: `BeatSelectionPolicy(topic_class, clip_count, platform)` → beat sequence (e.g. animals: HOOK+CONTEXT+PAYOFF).

**Pros:** Fixes 2-clip sameness.  
**Cons:** Must align with retention map windows.

### Option D — Wire Story Architecture `visual_prompt_hint`

Map architecture hints → SI camera override when hint confidence high.

**Pros:** Uses existing blueprint field.  
**Cons:** Hints today are not grammar-rich; architecture must be extended first.

### Option E — Semantic universe → grammar (not just lexicon)

Map clusters to shot families (e.g. football cluster → broadcast replay grammar).

**Pros:** Uses existing universe investment.  
**Cons:** Requires cluster→grammar mapping layer.

### Option F — Post-SI diversity audit (12J-D / VisualOriginality refactor)

`enrich(composed_prompt)` + reject if `visual_fingerprint` matches prior run grammar.

**Pros:** Safety net for production.  
**Cons:** Does not fix root; may only rephrase.

### Option G — LLM scene director (high risk)

Replace rule tables with model-generated shots per topic.

**Pros:** Maximum variety.  
**Cons:** Cost, drift, harder QA; conflicts with rule-based brain design.

**Recommended sequencing:** **A + B** (grammar tables + profiles) → **C** (beat policy) → **F** (audit gate). Defer **G**.

---

## RunwayPromptComposer Status (UAT)

| Item | Status |
|------|--------|
| Default enabled? | **No** — `enable_runway_prompt_composer()` default false |
| UAT auto-enable? | **No** |
| Changes camera when on? | **No** — reads `schema_director_shots` camera fields from SI |
| Cat session `110110` | Composer off; `lineage: null` |
| Dog session `080026` | Composer on; still same SI camera lines in schema |

---

## Success Criteria Check

| Criterion | Met? |
|-----------|------|
| Understand why different topics → same structure | **Yes** — beat-locked tables + 2-clip HOOK/ESCALATION |
| Identify architectural bottlenecks | **Yes** — `VisualOriginalityEngine` + `_select_beats_for_clips` |
| No fixes / no implementation | **Yes** — audit document only |

---

## Recommended Next Step (Implementation — Separate Approval)

**Phase 12J-D-B (proposed):** Implement **Option A + B** — `TopicClass` resolver + `scene_grammar` in profiles + replace `_camera_for_beat` / `_action_for_beat` indirection; add validator comparing dog vs cat `camera_shot` inequality.

**Do not:** Patch diversity only in Runway automation or `SessionPromptAdapter` string trimming.

---

## Related Documents

| Document | Relationship |
|----------|--------------|
| `PHASE_12J_C2B_C_REVISED_TAB_DURATION_CONTENT_AUDIT.md` | Operator context; dog/cat comparison |
| `PHASE_12J_C_RUNWAY_PROMPT_COMPOSER_DESIGN_LOCK.md` | Composer vs 12J-D boundaries |
| `PHASE_12J_C2B_B_RUNWAY_PROMPT_INJECTION_TRACE.md` | Downstream adapter path |

---

## Appendix — Key Constants

**`NICHE_VISUAL_LEXICON` keys:** `football`, `dark_mystery`, `storytelling`, `general` only.

**`EMOTIONAL_TARGETS`:** Fixed per beat (curiosity 0.88 hook, tension 0.78 escalation, …).

**Profiles on disk:** `default_profile.json`, `dark_mystery_profile.json` — all other verticals resolve to general unless registry maps to dark_mystery.
