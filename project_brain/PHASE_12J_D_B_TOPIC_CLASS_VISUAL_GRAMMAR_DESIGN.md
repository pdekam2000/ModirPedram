# PHASE 12J-D-B — Topic-Class Visual Grammar Design

**Date:** 2026-06-02  
**Status:** Design freeze — no implementation, no code changes  
**Inputs:** `PHASE_12J_D_A_STORY_INTELLIGENCE_DIVERSITY_AUDIT.md`, `PHASE_12J_C_RUNWAY_PROMPT_COMPOSER_DESIGN_LOCK.md`, `PHASE_12J_C2B_C_REVISED_TAB_DURATION_CONTENT_AUDIT.md`

---

## Purpose

Replace beat-only cinematography (one global “evidence investigation” grammar) with a **Topic-Class Visual Grammar System** so unrelated topics (dog, cat, football, history, …) produce **structurally different** `schema_director_shots` while **preserving** the narrative beat model (HOOK, ESCALATION, PAYOFF, etc.).

**In scope (design):** taxonomy, grammar matrix, beat × class interaction, integration architecture, phased roadmap.  
**Out of scope:** code, Runway browser, voice/subtitle/assembly, LLM scene director.

---

## Design Principles

1. **Beats are narrative roles; topic class is cinematography** — `beat_id` never removed; visualization varies by class.
2. **Deterministic & testable** — rule-based matrix + profile overrides; no LLM in v1.
3. **Backward compatible** — `general_investigation` class reproduces current tables for regression.
4. **Single source of truth** — one grammar resolver consumed by Story Intelligence (not duplicated in composer or adapter).
5. **Provider-neutral output** — grammar populates `schema_director_shots` fields consumed by `SessionPromptAdapter` / Runway unchanged.
6. **Niche + topic class compose** — `niche` adjusts lighting/lexicon; `topic_class` adjusts camera/motion/action/framing.

---

## 1. Topic Class Taxonomy

### 1.1 Canonical classes (v1)

| `topic_class` | Description | Typical topics |
|---------------|-------------|--------------|
| `animal` | Living creatures, behavior, empathy, observation | dog, cat, wildlife, pet science |
| `football` | Sports action, broadcast, crowd, match moments | goals, VAR, transfers, match analysis |
| `mystery` | Investigation, clues, ambiguity (non-supernatural) | unsolved case, missing detail, conspiracy-lite |
| `horror` | Dread, body horror, psychological unease | dark mystery profile topics, creepypasta-adjacent |
| `history` | Documentary, archival, timeline, testimony | historical event, figure, artifact |
| `science` | Demonstration, mechanism, data, lab/process | experiment, discovery, explainer science |
| `finance` | Markets, charts, stakes, numbers-as-story | crash, scam, personal finance twist |
| `self_care` | Wellness, routine, before/after, intimate domestic | habits, mental health, skincare routine |
| `travel` | Place, journey, scale, cultural texture | city, road trip, hidden location |
| `technology` | Product, UI, hands-on, spec reveal | gadget, app, AI tool, teardown |
| `general_investigation` | **Fallback** — current 12J-D-A evidence-macro grammar | default UAT, unknown vertical |

**Total v1:** 11 keys (10 verticals + 1 fallback).

### 1.2 Class resolution (deterministic precedence)

```text
resolve_topic_class(context) -> topic_class

1. explicit: profile.topic_class OR brief.run_context.topic_class (if valid enum)
2. niche_map:
     dark_mystery, storytelling -> horror (unless topic overrides to mystery)
     football -> football
3. topic_rules (token + phrase heuristics):
     animal: dog, cat, bird, wildlife, pet, ...
     football: goal, VAR, premier league, ...
     ... (maintained rule table)
4. semantic_universe.domain (if present): football, horror, education -> map
5. fallback: general_investigation
```

**Conflict policy:** explicit > niche_map > topic_rules > semantic > fallback.  
**Logging:** `topic_class`, `resolution_source` in `story_intelligence.explainability`.

### 1.3 Relationship to `profile.niche`

| Concept | Owns |
|---------|------|
| `niche` | Audience, tone, lighting base, lexicon pack, story_modes, registry profile JSON |
| `topic_class` | Camera, motion, action, framing, reveal/escalation/payoff **styles** per beat |

**Both apply:** e.g. `horror` niche + `animal` topic_class → horror lighting + animal camera grammar (composition rule in §4).

---

## 2. Grammar Dimensions (Per Class)

Each **beat × topic_class** cell defines:

| Dimension | Maps to `schema_director_shots` / scene |
|-----------|----------------------------------------|
| **camera_style** | `camera_shot` (primary framing language) |
| **motion_style** | `camera_movement` + `motion_direction` |
| **framing_style** | Compositional intent (embedded in camera + visual_description) |
| **pacing_style** | `pacing` / mood wording (aligns with `EMOTIONAL_TARGETS` intensity) |
| **reveal_style** | HOOK / PAYOFF-specific reveal mechanic (action + visual_description bias) |
| **escalation_style** | ESCALATION-specific tension mechanic |
| **payoff_style** | PAYOFF-specific closure mechanic |
| **action_template** | `action` field (`{anchor}`, `{topic}`, `{environment}` placeholders) |
| **subject_template** | `subject` field |
| **environment_template** | `environment` field |
| **visual_lexicon_bias** | Preferred lexicon slots for `visual_description` |

---

## 3. Grammar Matrix (Beat × Topic Class)

**Legend:** Beats = narrative roles (unchanged). Cells describe **preferred** grammar (v1 primary variant). Implementation may expose 2–3 variants per cell and rotate by `scene_index` / fingerprint.

### 3.1 `animal`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Eye-level close on subject, shallow DOF | Slow approach, subject notices lens | Intimate observer | Behavioral surprise — ear flick, freeze, direct look | — | — |
| CONTEXT | Wide habitat establishing, subject small in frame | Gentle pan across environment | Naturalistic documentary | — | — | — |
| ESCALATION | Tracking medium, subject moves through space | Follow-cam at subject pace | Motion-led | — | Behavior contradicts expectation (aggression, fear, play) | — |
| PATTERN_BREAK | Over-shoulder POV alternate angle | Whip to new angle | Subjective switch | — | Reframe behavior meaning | — |
| PAYOFF | Close on decisive behavior moment | Hold, micro-expressions | Emotional beat | — | — | Single clear behavior “tells the story” |
| LOOP_SEED | Subject exits frame or looks away | Slow pull-back | Open ending | — | — | Unresolved behavior cue |

**Pacing:** curious → tense → tender/release. **Lexicon bias:** fur texture, paw detail, breath vapor, natural light.

---

### 3.2 `football`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Broadcast tight on ball/player contact | Fast cut-in from wide | TV sports | Instant incident — foul, save, deflection | — | — |
| CONTEXT | Wide stadium / tunnel establishing | Crane or steadicam sweep | Epic scale | — | — | — |
| ESCALATION | Sideline track parallel to play | High-speed lateral tracking | Action tracking | — | Replay angle shows controversy | — |
| PATTERN_BREAK | Split-screen or angle swap | Hard cut motion | Multi-cam | — | VAR / referee frame reframes incident | — |
| PAYOFF | Goal-line / net cam hero frame | Snap zoom settle | Decisive sports | — | — | Ball crosses line / celebration peak |
| LOOP_SEED | Crowd reaction wide | Slow mo crowd rise | Social proof | — | — | One fan reaction unanswered |

**Pacing:** hype → dispute → catharsis. **Lexicon bias:** pitch texture, kit detail, stadium lights, replay monitor.

---

### 3.3 `mystery`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Macro on anomalous object / document edge | Rack focus to clue | Clue-forward | Partial clue visible, meaning withheld | — | — |
| CONTEXT | Medium office / scene establishing | Slow dolly in | Noir practical | — | — | — |
| ESCALATION | Over-shoulder examining evidence | Push-in on contradicting detail | Investigation | — | Two clues cannot both be true | — |
| PATTERN_BREAK | Mirror / reflection reveal | Perspective flip | Uncanny reframe | — | New witness angle | — |
| PAYOFF | Locked evidence board / object center | Static hold | Deduction frame | — | — | Clue connection made visible |
| LOOP_SEED | Door ajar / redacted line | Drift off evidence | Open case | — | — | One label still blurred |

**Pacing:** curiosity → unease → revelation. **Lexicon bias:** annotated photo, timestamp, fingerprint card, map pin.

---

### 3.4 `horror`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Low angle, subject off-center, negative space | Slow creep-in | Dread frame | Wrong detail in normal room (shadow, reflection) | — | — |
| CONTEXT | Corridor / doorway depth | Stalking dolly | Vulnerable space | — | — | — |
| ESCALATION | Handheld micro-shake close | Jitter push-in | Subjective fear | — | Space violates prior logic (door, geometry) | — |
| PATTERN_BREAK | Sudden wide after tight | Violent perspective jump | Jump-cut dread | — | Impossible presence | — |
| PAYOFF | Extreme close on disturbing detail | Freeze | Aftershock | — | — | Horror implication, not explanation |
| LOOP_SEED | Light source dies / figure edge | Slow retreat | Unresolved threat | — | — | Sound continues off-screen |

**Pacing:** dread → panic → aftershock. **Lighting:** always low-key branch. **Lexicon bias:** flicker, breath fog, door gap, stain texture.

---

### 3.5 `history`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Archival photo / artifact macro | Ken Burns slow zoom | Documentary | Date or inscription legible, context withheld | — | — |
| CONTEXT | Map / timeline graphic physical | Pan across timeline | Educational doc | — | — | — |
| ESCALATION | Split-era comparison frame | Dissolve or wipe transition | Temporal contrast | — | Two sources disagree on same event | — |
| PATTERN_BREAK | Modern location match old photo | Match cut | Then-and-now | — | Geography proves new reading | — |
| PAYOFF | Primary source document hero | Hold on underline | Verdict frame | — | — | Letter/photo confirms claim |
| LOOP_SEED | Unlabeled archive box | Pull-back from archive | Sequel hook | — | — | Missing page corner |

**Pacing:** authoritative → tension → clarity. **Lexicon bias:** yellowed paper, stamp, museum placard, reel-to-reel.

---

### 3.6 `science`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Macro on phenomenon (liquid, crystal, graph) | Focus pull to phenomenon | Lab/demo | Effect visible before mechanism named | — | — |
| CONTEXT | Bench / apparatus wide | Steady slide along setup | Clean explainer | — | — | — |
| ESCALATION | Side-by-side control vs test | Split dolly | Comparative proof | — | Control fails vs test succeeds | — |
| PATTERN_BREAK | Microscope / monitor insert | Cut to new scale | Scale shift | — | Micro structure explains macro | — |
| PAYOFF | Graph / reaction peak hero | Locked chart anim | QED frame | — | — | Data line crosses threshold |
| LOOP_SEED | Experiment still running | Time-lapse hint | Open question | — | — | Unread measurement |

**Pacing:** wonder → rigor → satisfaction. **Lexicon bias:** beaker meniscus, LED readout, gloved hand, grid paper.

---

### 3.7 `finance`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Screen macro on red candle / balance | Snap scroll stop | Data hook | Number or alert visible, story untold | — | — |
| CONTEXT | Desk / trading floor medium | Slow push across monitors | Stakes establishing | — | — | — |
| ESCALATION | Chart comparison wipe | Accelerated timeline scrub | Volatility | — | Correlation breaks assumption | — |
| PATTERN_BREAK | Receipt / contract flash | Hard cut insert | Paper trail | — | Hidden fee or clause | — |
| PAYOFF | Portfolio / account hero number | Hold on final figure | Consequence | — | — | Gain/loss realized on screen |
| LOOP_SEED | Notification ping unresolved | Pull to black | Cliffhanger | — | — | Pending transfer |

**Pacing:** urgency → anxiety → resolution. **Lexicon bias:** ticker tape, card chip, invoice highlight, wallet empty.

---

### 3.8 `self_care`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Bathroom mirror / morning routine close | Soft handheld | Relatable intimate | Small visible change (skin, posture, breath) | — | — |
| CONTEXT | Room-wide lifestyle establishing | Slow lifestyle pan | Aspirational calm | — | — | — |
| ESCALATION | Before/after split or time-of-day match | Gentle morph cut | Transformation tension | — | Routine fails without key step | — |
| PATTERN_BREAK | POV hands performing ritual | Top-down hands | Tutorial intimacy | — | Technique reframe | — |
| PAYOFF | Calm hero portrait post-routine | Stable hold | Relief | — | — | Visible calm payoff |
| LOOP_SEED | Alarm / calendar next day | Drift to window light | Habit loop | — | — | Tomorrow’s challenge teased |

**Pacing:** gentle → friction → calm. **Lexicon bias:** steam, water drop, fabric texture, natural window light.

---

### 3.9 `travel`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Landmark tease through foreground occlusion | Reveal dolly forward | Destination hook | Location almost recognizable | — | — |
| CONTEXT | Aerial or road approach wide | Drone-like sweep | Scale | — | — | — |
| ESCALATION | Street-level culture contrast | Walking steadicam | Immersion | — | Expectation vs reality mismatch | — |
| PATTERN_BREAK | Local detail vs tourist cliché | Whip pan | Cultural reframe | — | Hidden spot locals use | — |
| PAYOFF | Golden hour hero vista | Slow orbit | Awe payoff | — | — | Definitive “worth it” view |
| LOOP_SEED | Departure gate / suitcase | Pull away from place | Next journey | — | — | Ticket stub unread |

**Pacing:** wanderlust → surprise → awe. **Lexicon bias:** cobblestone, signage foreign script, transit blur, horizon line.

---

### 3.10 `technology`

| Beat | camera_style | motion_style | framing | reveal | escalation | payoff |
|------|--------------|------------|---------|--------|------------|--------|
| HOOK | Product silhouette / LED edge | Snap light-on reveal | Product hook | Device powers on / UI wakes | — | — |
| CONTEXT | Desk ecosystem wide | Slider past peripherals | Setup context | — | — | — |
| ESCALATION | Stress test montage (drop, load, heat) | Fast insert cuts | Torture test | — | Competitor / old gen fails same test | — |
| PATTERN_BREAK | X-ray / teardown slice | Cutaway interior | Insider view | — | Hidden component justifies claim | — |
| PAYOFF | Hero product 360 or UI win state | Locked hero orbit | Spec payoff | — | — | Benchmark number on screen |
| LOOP_SEED | Notification “firmware pending” | Pull to cable port | Upgrade tease | — | — | Feature gated |

**Pacing:** hype → skepticism → proof. **Lexicon bias:** brushed aluminum, RGB edge, screen pixel grid, cable plug.

---

### 3.11 `general_investigation` (fallback = current behavior)

| Beat | camera_style | motion_style | Notes |
|------|--------------|------------|-------|
| HOOK | Tight macro on evidence detail | shallow depth of field / snap focus rack | **Matches 12J-D-A production** |
| ESCALATION | Slow push-in on contradicting detail | Controlled push-in | **Matches 12J-D-A production** |
| Others | Same as current `_camera_for_beat` / `_motion_for_beat` tables | | Regression anchor |

---

## 4. Beat Interaction Model

### 4.1 Separation of concerns

```text
beat_id          → WHAT narrative job (hook, escalate, pay off, loop)
topic_class      → HOW that job is shot
niche            → lighting base + tone lexicon + profile rules
topic_tokens     → lexical anchor substitution only
```

**Invariant:** Full blueprint still contains six beats from `StoryArchitectureEngine`. `SceneProgressionEngine` still selects a **subset** by `clip_count` (unchanged in 12J-D-B; beat **selection policy** is 12J-D-C).

### 4.2 Lookup formula (design)

```text
grammar_cell = TOPIC_CLASS_GRAMMAR[topic_class][beat_id][variant_index]

scene.camera_direction  = compose_camera(grammar_cell.camera_style, grammar_cell.motion_style)
scene.camera_movement   = grammar_cell.motion_style.movement_phrase
scene.motion_direction  = grammar_cell.motion_style.motion_phrase
scene.action            = format(grammar_cell.action_template, anchor, topic)
scene.pacing            = grammar_cell.pacing_style or EMOTIONAL_TARGETS[beat_id]
scene.visual_description = lexicon_pick(grammar_cell.visual_lexicon_bias, scene_index, topic)
```

**HOOK** uses `reveal_style`; **ESCALATION** uses `escalation_style`; **PAYOFF** uses `payoff_style` — merged into `action` + `visual_description`, not separate beat_ids.

### 4.3 Example: same beats, different classes (2-clip UAT)

| clip | beat_id | `animal` (cat) | `football` | `history` |
|------|---------|----------------|------------|-----------|
| 1 | HOOK | Eye-level close, behavioral reveal | Broadcast tight on contact | Archival macro Ken Burns |
| 2 | ESCALATION | Tracking follow, behavior contradicts | Sideline track, replay controversy | Split-era dissolve disagreement |

**Narrative arc unchanged** (hook → escalate); **visual grammar diverges**.

### 4.4 Composer & adapter (downstream)

- `RunwayPromptComposer` (optional): may enrich prose; **must not** overwrite `camera_shot` / `camera_movement` unless 12J-D-D diversity audit allows.
- `SessionPromptAdapter`: continues to append Camera/Movement/Lighting from `schema_director_shots` — fields now class-specific.

---

## 5. Integration Point Analysis

### Option 1 — Inside `VisualOriginalityEngine` only

| Pros | Cons |
|------|------|
| Smallest diff; direct replacement of `_camera_for_beat` | Engine already large; mixes lexicon + grammar + anti-generic |
| Fast path to fix dog/cat sameness | Harder to unit test grammar in isolation |

### Option 2 — Inside `SceneProgressionEngine`

| Pros | Cons |
|------|------|
| Could couple beat selection + grammar | Violates SRP; scene engine should not own cinematography |
| | Grammar needed before scenes exist only at enrich time |

### Option 3 — New `TopicClassGrammarEngine` (recommended)

| Pros | Cons |
|------|------|
| Single source of truth; JSON-loadable matrix | New module + resolver |
| Pure functions: `resolve_class()`, `get_grammar(beat, class, variant)` | One more import in SI pipeline |
| Profile overrides natural (`grammar_overrides`) | |
| Testable: `assert grammar(animal, HOOK) != grammar(football, HOOK)` | |
| `VisualOriginalityEngine` becomes thin delegate | |

### Recommendation

```text
StoryIntelligenceEngine.enhance()
  ├─ _build_context()
  ├─ topic_class = TopicClassResolver.resolve(context)     [NEW]
  ├─ NarrativeStrategyEngine.build()
  ├─ EmotionalArcEngine.build()
  ├─ SceneProgressionEngine.build()                        [unchanged in D-B]
  ├─ VisualOriginalityEngine.enrich_scenes()
  │     └─ TopicClassGrammarEngine.apply(scene, beat_id, topic_class, context)
  ├─ AntiGenericSceneEngine.audit()                        [extend in D-C]
  └─ CinematicBeatEngine...
```

**Store in payload:**

```json
"explainability": {
  "topic_class": "animal",
  "topic_class_resolution": "topic_rules:cat",
  "grammar_version": "12j_d_b_v1"
}
```

---

## 6. Data Model (Implementation Reference)

### 6.1 `GrammarCell` (per beat × class)

```python
@dataclass
class GrammarCell:
    camera_style: str
    motion_style: str
    framing_style: str
    pacing_style: str
    reveal_style: str | None = None
    escalation_style: str | None = None
    payoff_style: str | None = None
    action_template: str
    subject_template: str
    environment_template: str
    visual_lexicon_bias: list[str]
    variants: list[GrammarCell] | None = None  # optional alternates
```

### 6.2 Storage options

| Store | Use |
|-------|-----|
| `content_brain/grammar/topic_class_grammar_v1.json` | Canonical matrix (versioned) |
| `config/content_brain/profiles/*.json` → `topic_class_overrides` | Per-niche deltas |
| Code enum | `TopicClass` + resolver rules only |

---

## 7. Migration Roadmap

### Phase 12J-D-B — Topic class grammar core (this design)

| Deliverable | Description |
|-------------|-------------|
| `TopicClassResolver` | Taxonomy + precedence rules |
| `topic_class_grammar_v1.json` | Full matrix §3 |
| `TopicClassGrammarEngine` | Lookup + format to scene fields |
| Wire SI | `VisualOriginalityEngine` delegates; `explainability` fields |
| Validator | `validate_12j_d_b_topic_class_grammar.py` — dog vs football HOOK camera inequality |
| Regression | `general_investigation` matches 12J-D-A strings |
| Report | `PHASE_12J_D_B_IMPLEMENTATION_REPORT.md` (after approval) |

**Explicitly not in D-B:** beat selection policy, composer changes, profile UI, Runway.

---

### Phase 12J-D-C — Beat policy + profile overrides + structural anti-repeat

| Deliverable | Description |
|-------------|-------------|
| `BeatSelectionPolicyEngine` | topic_class-aware beat subsets (e.g. animal 2-clip: HOOK+PAYOFF or HOOK+CONTEXT) |
| Profile `scene_grammar` / `topic_class_overrides` | Operator tuning without code |
| `AntiGenericSceneEngine` v2 | Structural fingerprint: reject same `camera_shot`+`motion` across memory for different topics |
| Niche registry expansion | Optional `football_profile.json`, etc. |
| UAT default niche | Topic-appropriate profile suggestion (design from 12J-C2B-C revised) |

---

### Phase 12J-D-D — Composer diversity gate + production hooks

| Deliverable | Description |
|-------------|-------------|
| `VisualOriginalityEngine.enrich` post-composer | 12J-D design lock — audit prose, not re-author camera |
| Composer quality gate | Fail if grammar fields drift from `schema_director_shots` |
| `enable_runway_prompt_composer` UAT flag policy | Document when safe to enable |
| Story memory | Block repeated grammar fingerprint across channel |
| Optional A/B | `topic_class` in UAT UI read-only for operator education |

---

### Dependency graph

```text
12J-D-A (audit) ✓
    ↓
12J-D-B (grammar matrix + resolver + SI wire)  ← THIS DESIGN
    ↓
12J-D-C (beat policy + profiles + anti-repeat)
    ↓
12J-D-D (composer gate + memory)
```

**Parallel allowed:** 12J-C2B-C tab observability (Runway UX) — independent of Content Brain grammar.

---

## 8. Validation Plan (Post-Implementation)

| Test | Pass condition |
|------|----------------|
| Class resolution | `cat` → `animal`; `VAR controversy` → `football` |
| Grammar inequality | `animal` HOOK camera ≠ `football` HOOK camera ≠ `history` HOOK |
| Beat preservation | All six beats still producible when clip_count=6 |
| 2-clip UAT | HOOK+ESCALATION still default selection in D-B; grammar differs by class |
| Fallback | Unknown topic → `general_investigation` matches legacy strings |
| Session payload | `explainability.topic_class` present |
| Runway E2E | Same pipeline; only prompt strings change |

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Wrong class inference | Explicit override on profile; log `resolution_source` |
| Runway prompt length | Keep templates concise; adapter truncation unchanged |
| Horror vs mystery overlap | Precedence: niche `dark_mystery` → horror; investigative topic → mystery |
| Overfitting templates | 2 variants per cell + memory anti-repeat in D-C |
| Breaking stable UAT | `general_investigation` regression suite |

---

## 10. Success Criteria (Design)

| Criterion | Met in this design |
|-----------|-------------------|
| Topic taxonomy defined | §1 — 10 classes + fallback |
| Per-class camera/motion/pacing/framing/reveal/escalation/payoff | §2–§3 matrix |
| Beats remain; visualization varies | §4 |
| Integration analyzed | §5 — recommend `TopicClassGrammarEngine` |
| Migration B/C/D | §7 |
| No implementation | §7 references future work only |

---

## Summary

**12J-D-B** introduces a **Topic-Class Visual Grammar** layer: `topic_class` + `beat_id` → cinematography cell, replacing beat-only tables in `VisualOriginalityEngine`. Dog and cat both map to **`animal`** but differ from **`football`**, **`history`**, etc. at the **camera/action structure** level, not just token swap. **`general_investigation`** preserves today’s evidence-macro grammar for regression. Implement via new **`TopicClassGrammarEngine`** in phase **12J-D-B** after approval; beat selection and composer gates follow in **C** and **D**.
