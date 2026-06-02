# PHASE 12J-C — Runway Prompt Composer Design Lock

**Date:** 2026-05-31  
**Status:** Design freeze — no implementation, no code changes  
**Inputs:** `PHASE_12J_A_CONTENT_BRAIN_TRACE_AUDIT.md`, `PHASE_12J_B_VISUAL_INTELLIGENCE_RESTORATION_DESIGN.md`  
**Decisions locked (from 12J-B acceptance):**

| Decision | Lock |
|----------|------|
| Content Brain orchestration | Unchanged |
| Runway browser automation | Unchanged |
| `SessionPromptAdapter` | Formatter + intelligent truncation + lineage passthrough only |
| `VisualOriginalityEngine` | Enrichment + audit only (12J-D) |
| `NICHE_VISUAL_LEXICON` | Fallback only |
| New component | `RunwayPromptComposer` between `brief_snapshot` and `SessionPromptAdapter` |

**Purpose:** Freeze the `RunwayPromptComposer` contract, merge precedence, beat-collapse rules, quality gates, adapter boundary, and phased rollout **before** any 12J-D+ implementation.

---

## 1. `ComposedClipPrompt` — Exact Schema

### 1.1 Top-level contract

One `ComposedClipPrompt` per output clip (`clip_index` = 1..N). Composer emits `list[ComposedClipPrompt]` stored at:

- **Primary (runtime):** `brief_snapshot.run_context.runway_composed_clips[]`
- **Mirror (optional):** updates `schema_director_shots[].prompt` from `composed_prompt` for adapter compatibility

**Version field (container, not per clip):** `run_context.runway_composer_version` = `"12j_c_v1"`

### 1.2 Required fields (frozen)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `clip_index` | `int` | yes | 1-based clip index; must match `video_format_plan.clip_count` ordering |
| `hook_payload` | `HookPayload` | yes | Hook-derived visual seed for this clip (may be empty object on clip 2+) |
| `retention_payload` | `RetentionPayload` | yes | Retention-map visuals aligned to this clip window |
| `architecture_payload` | `ArchitecturePayload` | yes | Story-architecture beat visuals folded into this clip |
| `thumbnail_payload` | `ThumbnailPayload` | yes | Thumbnail-engine hero/tension visuals for this clip |
| `continuity_payload` | `ContinuityPayload` | yes | Between-clip and in-clip continuity directives |
| `emotional_arc` | `EmotionalArcSlice` | yes | Intensity/tone slice for this clip |
| `payoff_payload` | `PayoffPayload` | yes | Payoff / pattern-break / loop-seed compressed content |
| `composed_prompt` | `string` | yes | Pre-adapter merged prose (pre-truncation); authoritative scene text |
| `lineage` | `LineageRecord` | yes | Source paths, merge order, collapse map |
| `quality_score` | `QualityScore` | yes | Post-merge audit scores |

### 1.3 Nested type definitions

#### `HookPayload`

```json
{
  "applies": true,
  "beat_ids": ["HOOK_BEAT"],
  "best_hook_text_excerpt": "string (max 120 chars, extracted nouns/actions)",
  "hook_class": "string | null",
  "visual_seed": "string (condensed visual clause, not full hook sentence)",
  "specificity_score": 0.0,
  "source_paths": ["hook_package.best_hook_text", "..."]
}
```

- Clip 1: `applies` = true; populate from `hook_package`.
- Clip 2+: `applies` = false; `visual_seed` = `""`; `beat_ids` = `[]`.

#### `RetentionPayload`

```json
{
  "clip_window_seconds": [0.0, 10.0],
  "blocks": [
    {
      "block_label": "string",
      "story_beat_id": "HOOK_BEAT | ESCALATION_BEAT | ...",
      "visual_clause": "string (parsed VISUAL: segment only)",
      "clip_tag": "CLIP: 0 [0.0-10.0]",
      "intensity": 0.0,
      "source_path": "retention_map.beats[i].implementation_note"
    }
  ],
  "primary_visual": "string (merged VISUAL clauses for this clip, precedence winner base)"
}
```

#### `ArchitecturePayload`

```json
{
  "primary_beat_id": "HOOK_BEAT | ESCALATION_BEAT | ...",
  "secondary_beat_ids": ["PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"],
  "visual_hints": [
    {
      "beat_id": "string",
      "visual_prompt_hint": "string",
      "description_visual_line": "string (VISUAL: from beat description if present)",
      "source_path": "story_blueprint.beats[] | story_architecture"
    }
  ],
  "sensory_anchor": "string | null",
  "primary_visual": "string (merged architecture hints for clip)"
}
```

#### `ThumbnailPayload`

```json
{
  "applies": true,
  "concept_id": "string | null",
  "focal_subject": "string",
  "visual_prompt": "string",
  "tension_element": "string",
  "composition_note": "string",
  "role": "hero_frame | payoff_object | none",
  "source_paths": ["title_thumbnail_package.recommended_thumbnail_concept", "..."]
}
```

- Clip 1: `role` = `hero_frame` (recommended concept).
- Clip 2: `role` = `payoff_object` (tension / focal from best payoff-aligned concept).

#### `ContinuityPayload`

```json
{
  "continuity_in": "string",
  "continuity_out": "string",
  "director_notes": "string",
  "retention_clip_notes": ["string"],
  "between_clip_directive": "string | null",
  "source_paths": ["schema_director_shots[].continuity_notes", "retention_map...", "..."]
}
```

#### `EmotionalArcSlice`

```json
{
  "clip_index": 1,
  "beat_ids": ["HOOK_BEAT", "CONTEXT_BEAT"],
  "intensity_start": 0.0,
  "intensity_peak": 1.0,
  "intensity_end": 0.95,
  "tones": ["curiosity", "tension"],
  "curve_sample": [1.0, 0.95, 0.72],
  "source_path": "story_blueprint.emotional_curve | story_intelligence.emotional_arc"
}
```

#### `PayoffPayload`

```json
{
  "applies": true,
  "folded_beat_ids": ["PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"],
  "pattern_break_visual": "string",
  "payoff_visual": "string",
  "loop_seed_visual": "string",
  "compressed_clause": "string (single merged payoff act phrase)",
  "source_paths": ["retention_map...", "story_blueprint.beats[]", "..."]
}
```

- Clip 1: `applies` = false; folded beats empty; fields empty strings.
- Clip 2 (N=2): `applies` = true; must include PATTERN_BREAK + PAYOFF + LOOP_SEED when present in brief.

#### `LineageRecord`

```json
{
  "composer_version": "12j_c_v1",
  "clip_index": 1,
  "merge_pass": "prose_v1",
  "precedence_applied": ["retention", "architecture", "director_shots", "thumbnail", "lexicon_fallback"],
  "beat_collapse": {
    "primary_beats": ["HOOK_BEAT"],
    "folded_beats": ["CONTEXT_BEAT"],
    "clip_count": 2
  },
  "sources_used": [
    {
      "path": "retention_map.beats[3].implementation_note",
      "field": "VISUAL",
      "weight": 1.0,
      "used_in": "primary_visual"
    }
  ],
  "director_shot_id": "string | null",
  "lexicon_fallback_used": false,
  "truncation_applied_by": "none | adapter"
}
```

#### `QualityScore`

```json
{
  "genericity_score": 0.0,
  "specificity_score": 0.0,
  "visual_richness_score": 0.0,
  "prompt_entropy_score": 0.0,
  "composite_score": 0.0,
  "pass": true,
  "failure_reasons": [],
  "audit_flags": ["LEXICON_ONLY", "LOW_ENTROPY"]
}
```

### 1.4 Container schema

```json
{
  "runway_composer_version": "12j_c_v1",
  "composed_at": "YYYY-MM-DD HH:MM:SS",
  "topic": "dog",
  "clip_count": 2,
  "clips": [ "ComposedClipPrompt × N" ]
}
```

### 1.5 Validation rules (composer output)

| Rule | Enforcement |
|------|-------------|
| `len(clips) == clip_count` | Hard fail `COMPOSER_CLIP_COUNT_MISMATCH` |
| `composed_prompt` non-empty per clip | Hard fail `COMPOSER_EMPTY_PROMPT` |
| `lineage.precedence_applied` order fixed | Must match §2 |
| Clip 2 `payoff_payload.applies` when N=2 | Hard fail if folded beats missing from brief |
| `quality_score.pass` | Soft warn by default; hard fail if `RUNWAY_PROMPT_COMPOSER_STRICT_QUALITY=true` (12J-D config) |

---

## 2. Precedence Rules — Exact Merge Logic

### 2.1 Precedence stack (highest → lowest)

```text
1. Retention      (retention_payload.primary_visual base)
2. Architecture   (architecture_payload.primary_visual)
3. Director shots (schema_director_shots cinematic structure)
4. Thumbnail      (thumbnail_payload visual_prompt / focal_subject)
5. Lexicon fallback (NICHE_VISUAL_LEXICON — only if layers 1–4 fail genericity gate)
```

**Important:** Precedence governs **prose scene description** (`composed_prompt` body). **Director shots** supply **structured suffix fields** (camera, movement, lighting, pacing) that are **appended after** prose merge, not overwritten by lower layers.

### 2.2 Layer extraction (per clip)

```text
INPUT: brief_snapshot, clip_index i, clip_count N, beat_collapse_map(i)

R_i  := retention_payload.primary_visual     # VISUAL clauses for clip window i
A_i  := architecture_payload.primary_visual  # hints for primary + folded beats
D_i  := director_shots[i].prompt_intent       # or schema_director_shots[i].prompt pre-composer
T_i  := thumbnail visual clause               # hero_frame (i=1) or payoff_object (i=N)
L_i  := lexicon_fallback(i)                   # only if §4 genericity fails
```

### 2.3 Prose merge algorithm (`merge_prose_v1`)

For each non-empty layer, normalize: trim, collapse whitespace, strip duplicate periods.

```text
function merge_prose_v1(R, A, D, T, L, hook, payoff, continuity):
    sections = []

    # --- Clip 1 opening ---
    if clip_index == 1 and hook.visual_seed non-empty:
        sections.append(hook.visual_seed)   # hook seeds clip 1 only; NOT precedence stack

    # --- Payoff fold (clip 2+ / last clip) ---
    if payoff.applies and payoff.compressed_clause non-empty:
        sections.append(payoff.compressed_clause)  # pattern_break + payoff + loop_seed

    # --- Precedence stack (prose body) ---
    body = ""
    for layer in [R, A, D, T]:
        if layer is empty:
            continue
        if body is empty:
            body = layer
        else:
            body = augment(body, layer)   # see augment() below

    if body is empty and L non-empty:
        body = L
        lineage.lexicon_fallback_used = true

    if body is empty:
        FAIL COMPOSER_EMPTY_PROMPT

    sections.insert(hook ? 1 : 0, body)  # body after hook seed on clip 1

    # --- Continuity (always last in composer prose) ---
    if continuity.between_clip_directive:
        sections.append(continuity.between_clip_directive)
    elif continuity.continuity_out:
        sections.append(continuity.continuity_out)

    composed_prompt = join(sections, ". ")
    return composed_prompt
```

#### `augment(base, overlay)` — higher precedence wins conflicts

```text
function augment(base, overlay):
    # Retention wins on operational directives (motion, clip timing, contrast).
    # Architecture wins on beat-specific hint nouns if retention is generic.
    # Director wins on cinematic vocabulary if retention+architecture lack camera nouns.
    # Thumbnail wins on focal subject / composition if prior layers lack a concrete subject.

    if is_generic(base) and not is_generic(overlay):
        return overlay

    if concrete_subject(overlay) and not concrete_subject(base):
        return overlay + ". " + base

    if len(overlay) > len(base) * 1.5 and specificity(overlay) > specificity(base):
        return overlay + ". " + compress(base, max_chars=120)

    return base + ". " + overlay
```

**Conflict resolution summary:**

| Conflict type | Winner |
|---------------|--------|
| Retention VISUAL vs architecture hint (both specific) | Retention |
| Retention generic vs architecture specific | Architecture |
| Architecture vs director template (`topic-specific object…`) | Architecture + director augment |
| Thumbnail focal subject vs vague body | Thumbnail focal subject injected into base via `concrete_subject` rule |
| All layers generic | Lexicon fallback `L_i` replaces body |

### 2.4 Director shot structured append (composer → adapter handoff)

Composer writes **full** `composed_prompt` including optional inline camera hints from retention. Director fields are **also** stored separately for adapter formatting:

```json
{
  "camera_shot": "from schema_director_shots",
  "camera_movement": "...",
  "lighting": "...",
  "pacing": "...",
  "continuity_notes": "continuity_payload.continuity_out (short)"
}
```

Adapter appends `Camera: … Movement: …` per 10I contract **only if** not already present in `composed_prompt` (dedupe by keyword check).

### 2.5 `VisualOriginalityEngine` position (12J-D — not composer)

After `merge_prose_v1`, **before** `quality_score`:

```text
enriched = VisualOriginalityEngine.enrich(composed_prompt, profile.visual_dna, topic)
audited  = AntiGenericSceneEngine.audit(enriched)
composed_prompt = audited.text
```

Composer **records** enrichment in `lineage.sources_used` but does **not** call lexicon as primary author.

---

## 3. Beat-Collapse Rules (6 → 2 Clips)

### 3.1 Story beats (full blueprint)

| Beat ID | Role |
|---------|------|
| `HOOK_BEAT` | Hook |
| `CONTEXT_BEAT` | Grounding (optional fold) |
| `ESCALATION_BEAT` | Escalation |
| `PATTERN_BREAK` | Pattern break |
| `PAYOFF_BEAT` | Payoff |
| `LOOP_SEED` | Loop seed |

`SceneProgressionEngine` still selects **2 primary scenes** (HOOK + ESCALATION) for `schema_director_shots` count. Composer **does not** change scene count; it **folds** dropped beats into `ComposedClipPrompt` payloads.

### 3.2 Collapse map for `clip_count = 2`

| Clip | `clip_index` | Primary beat (scene) | Folded beats (must appear in payloads) |
|------|------------|----------------------|------------------------------------------|
| 1 | 1 | `HOOK_BEAT` | `CONTEXT_BEAT` (excerpt, optional) |
| 2 | 2 | `ESCALATION_BEAT` | `PATTERN_BREAK`, `PAYOFF_BEAT`, `LOOP_SEED` |

**Mandatory preservation checklist (N=2):**

| Element | Clip | Where preserved |
|---------|------|-----------------|
| Hook | 1 | `hook_payload`, retention hook window, architecture HOOK |
| Escalation | 2 | `architecture_payload.primary_beat_id`, retention escalation VISUAL |
| Payoff | 2 | `payoff_payload.payoff_visual`, retention payoff VISUAL |
| Pattern break | 2 | `payoff_payload.pattern_break_visual` |
| Loop seed | 2 | `payoff_payload.loop_seed_visual` |

### 3.3 `payoff_payload.compressed_clause` construction

```text
parts = []
if pattern_break_visual: parts.append(pattern_break_visual)
if payoff_visual:         parts.append(payoff_visual)
if loop_seed_visual:      parts.append(loop_seed_visual)
compressed_clause = join(parts, " then ")
```

### 3.4 Retention alignment

Map `retention_map.beats[]` to clip by parsing `CLIP: k [t0-t1]`:

- `k == 0` or `t0 < 10` → clip 1
- `k == 1` or `t0 >= 10` → clip 2

When multiple retention blocks hit one clip, merge VISUAL segments in `start_second` order.

### 3.5 Worked example — topic `dog`, N=2

**Inputs (abbreviated from UAT session pattern):**

| Beat | Architecture hint | Retention VISUAL |
|------|-------------------|------------------|
| HOOK | tight close-up on the subject tied to the hook | Motion, contrast, or subject focus in frame 0 |
| ESCALATION | detail shot revealing new information | detail shot revealing new information |
| PATTERN_BREAK | camera angle or scene shift | camera angle or scene shift |
| PAYOFF | clear visual proof or story turn | clear visual proof or story turn |
| LOOP_SEED | unfinished detail held in frame… | unfinished detail held in frame for the sequel cue |

**Clip 1 `composed_prompt` (conceptual):**

```text
Close-up: golden retriever paw on worn leash, hook tension visible. Motion and contrast in frame 0 — subject sharp in first second. tight close-up on the subject tied to the hook. Hero frame: dog eyes in shallow depth, partial shadow hiding context. Continuity: Match cool motivated light; sets up escalation.
```

**Clip 2 `composed_prompt` (conceptual):**

```text
camera angle or scene shift then clear visual proof or story turn then unfinished detail held in frame for the sequel cue. detail shot revealing new information — contrasting collar tag vs missing nameplate. Slow push-in on contradicting detail. Payoff object: same dog, reveal tag text. Clip 2 opens with immediate motion continuing prior lighting.
```

**Lineage snippet clip 2:**

```json
{
  "beat_collapse": {
    "primary_beats": ["ESCALATION_BEAT"],
    "folded_beats": ["PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"],
    "clip_count": 2
  }
}
```

### 3.6 Generalization for `clip_count = N`

| N | Clip 1 | Middle clips | Clip N |
|---|--------|--------------|--------|
| 1 | All beats folded into single payoff-heavy prompt | — | — |
| 2 | HOOK (+CONTEXT) | — | ESCALATION + PATTERN_BREAK + PAYOFF + LOOP_SEED |
| 3 | HOOK (+CONTEXT) | ESCALATION (+PATTERN_BREAK partial) | PAYOFF + LOOP_SEED |
| 4+ | HOOK | Escalation ladder | PAYOFF + LOOP_SEED on last |

Priority list for **primary** scene selection remains: `HOOK_BEAT`, `ESCALATION_BEAT`, `PAYOFF_BEAT`, `LOOP_SEED` (existing engine). Composer only adjusts **folded** sets.

---

## 4. Quality Checks (Design Definitions)

All scores are **0.0–1.0** (higher = better except genericity, where higher = worse). Computed on final `composed_prompt` after enrichment, before adapter truncation.

### 4.1 Genericity detection (`genericity_score`)

**Goal:** Detect lexicon-template and stock-footage language.

| Signal | Weight | Example trigger |
|--------|--------|-----------------|
| Lexicon template regex match | 0.40 | `topic-specific object in sharp focus` |
| Placeholder token | 0.25 | `{topic}`, literal `"topic"` without topic |
| Stock phrase list | 0.20 | `generic stock footage`, `evidence element` without domain noun |
| No concrete noun in first 40 tokens | 0.15 | — |

```text
genericity_score = min(1.0, sum(signal_weights))
pass_genericity = genericity_score <= 0.35
```

If fail and layers 1–4 empty → allow `lexicon_fallback` once; flag `LEXICON_ONLY` in `audit_flags`.

### 4.2 Specificity score (`specificity_score`)

```text
specificity_score = clamp01(
    0.35 * topic_token_present(topic, prompt) +
    0.25 * proper_noun_or_domain_noun_count(prompt) / 4 +
    0.20 * hook_overlap(hook_payload.visual_seed, prompt) +
    0.20 * sensory_anchor_present(architecture_payload.sensory_anchor, prompt)
)
```

Pass threshold: `>= 0.55` (configurable `RUNWAY_PROMPT_SPECIFICITY_MIN`).

### 4.3 Visual richness score (`visual_richness_score`)

Counts distinct visual dimensions present (case-insensitive keyword + structured field detection):

| Dimension | Detection |
|-----------|-----------|
| Subject | noun phrase / `focal_subject` / thumbnail |
| Action | verb phrase; `Action:` segment |
| Environment | setting words; `Environment:` |
| Camera | `Camera:`, shot type words |
| Lighting | `Lighting:`, palette/DNA terms |
| Motion | movement verbs; retention motion cues |
| Mood | mood adjectives; `Mood:` / pacing |

```text
visual_richness_score = (dimensions_present / 7.0)
```

Pass threshold: `>= 0.50`.

### 4.4 Prompt entropy score (`prompt_entropy_score`)

Character-level Shannon entropy on normalized prompt (letters only), normalized against target ~4.2 bits for rich English prose:

```text
H = shannon_entropy(prompt_chars)
prompt_entropy_score = clamp01(H / 4.5)
```

Pass threshold: `>= 0.40`. Flags `LOW_ENTROPY` if below 0.35 (repetitive template).

### 4.5 Composite and pass gate

```text
composite_score = clamp01(
    0.30 * specificity_score +
    0.30 * visual_richness_score +
    0.25 * prompt_entropy_score +
    0.15 * (1.0 - genericity_score)
)

quality_score.pass = (
    pass_genericity AND
    specificity_score >= SPECIFICITY_MIN AND
    visual_richness_score >= RICHNESS_MIN AND
    prompt_entropy_score >= ENTROPY_MIN
)
```

Default: warn-only on fail; store `failure_reasons[]` in `quality_score` and `prompt_bundle.metadata.quality_warnings[]`.

---

## 5. `SessionPromptAdapter` Boundary

### 5.1 `RunwayPromptComposer` OWNS

| Responsibility | Detail |
|----------------|--------|
| Beat-collapse mapping | 6 → N folded beat assignment |
| Retention ↔ clip alignment | Parse `CLIP:` windows |
| Precedence merge | `merge_prose_v1` + `payoff_payload` / `hook_payload` |
| `ComposedClipPrompt` construction | Full schema §1 |
| `composed_prompt` authoring | Pre-truncation authoritative prose |
| `lineage` + `quality_score` | Full provenance and audit |
| Director shot prompt field update | Write `schema_director_shots[i].prompt = composed_prompt` when composer enabled |
| Enrichment orchestration | Invoke `VisualOriginalityEngine` enrich+audit (12J-D); not adapter |
| Lexicon fallback decision | Only composer may set `lineage.lexicon_fallback_used` |

### 5.2 `SessionPromptAdapter` OWNS

| Responsibility | Detail |
|----------------|--------|
| Provider formatting | `Camera:`, `Movement:`, `Lighting:`, `Pacing:`, `Continuity:` suffix layout |
| Shot resolution | Read `schema_director_shots` (post-composer prompts) |
| Intelligent truncation | Runway 950 char — **section-priority truncate** (design: prefer drop thumbnail echo → director duplicate → architecture repeat → never drop continuity tail) |
| `PromptBundle` emission | `prompts[]`, `clip_metadata`, hashes |
| Lineage passthrough | Copy `runway_composed_clips[i].lineage` → `clip_metadata[i].lineage` and `prompt_bundle.metadata.prompt_lineage[]` |
| Quality warn passthrough | Surface `quality_score` warnings; no re-audit |
| Provider normalization | `normalize_provider_key`, clip count trim guard |
| Fallback path | If `RUNWAY_PROMPT_COMPOSER_ENABLED=false` or missing `runway_composed_clips`, current 10I behavior unchanged |

### 5.3 Explicit non-ownership

| Module | Does NOT |
|--------|----------|
| Composer | Browser automation, queue dispatch, provider API |
| Adapter | Beat collapse, retention parsing, precedence merge, lexicon fallback |
| Composer | 950-byte cut (adapter only) |
| Adapter | Re-merge retention/architecture/hook |

### 5.4 Call sequence (frozen)

```text
ProviderRuntimeEngine.dispatch()
  → RunwayPromptComposer.compose(session)      # if enabled & not idempotent skip
  → SessionPromptAdapter.build(session, provider)
  → prompt_bundle.json
  → RunwayBrowserProvider.fill_prompt()        # unchanged
```

**Idempotent skip:** if `run_context.runway_composer_version == "12j_c_v1"` and `lineage.merge_pass == "prose_v1"` for all clips, composer returns cached `runway_composed_clips`.

---

## 6. Rollout Plan (Implementation Phases)

### Phase 12J-C — Composer core (this lock)

| Deliverable | Scope |
|-------------|-------|
| `RunwayPromptComposer` | `content_brain/execution/runway_prompt_composer.py` |
| Schema types | Dataclasses mirroring §1 (or TypedDict + validator) |
| Unit fixtures | Golden tests from `exec_uat_20260602_055459` brief shape |
| Feature flag | `RUNWAY_PROMPT_COMPOSER_ENABLED` default `false` |
| Wiring | `ProviderRuntimeEngine.dispatch()` pre-adapter call |
| Report | `PHASE_12J_C_IMPLEMENTATION_REPORT.md` |

**Exit criteria:** With flag on, `prompt_bundle.json` shows non-template prose, `prompt_lineage` per clip, clip 2 includes payoff fold; Runway automation unchanged.

### Phase 12J-D — Visual originality refactor

| Deliverable | Scope |
|-------------|-------|
| `VisualOriginalityEngine` | Remove primary `_build_visual()` lexicon template; enrich+audit only |
| `NICHE_VISUAL_LEXICON` | Callable only from composer fallback path |
| `RUNWAY_PROMPT_COMPOSER_STRICT_QUALITY` | Optional hard fail on `quality_score.pass` |
| Anti-generic | Shared patterns with §4.1 |
| Report | `PHASE_12J_D_IMPLEMENTATION_REPORT.md` |

**Exit criteria:** No default `"topic-specific object in sharp focus"` in `schema_director_shots` without fallback flag; UAT topic `dog` specificity ≥ 0.55.

### Phase 12J-E — Semantic topic binding

| Deliverable | Scope |
|-------------|-------|
| `ContentBriefOrchestrator.run()` | Pass `pipeline_topic` into semantic universe / trend context |
| Profile load | Stop literal `"topic"` seed pool for runtime UAT |
| Composer | Consume `semantic_universe` clusters as enrichment hints (not precedence layer) |
| Report | `PHASE_12J_E_IMPLEMENTATION_REPORT.md` |

**Exit criteria:** `semantic_universe` contains runtime topic tokens; lineage may cite `semantic_universe.clusters`.

### Phase 12J-F — UI lineage & observability

| Deliverable | Scope |
|-------------|-------|
| Runtime Studio / UAT UI | Per-clip lineage viewer, quality_score badges |
| `prompt_bundle.metadata` | Full `prompt_lineage`, `quality_warnings` |
| Optional preview API | `run_context.runway_prompt_preview` from orchestrator dry-run |
| Report | `PHASE_12J_F_IMPLEMENTATION_REPORT.md` |

**Exit criteria:** Operator can see which of 5 precedence layers supplied each clip without opening raw session JSON.

### Cross-phase constraints (all phases)

- Do not modify `RunwayBrowserOrchestrator`, `RunwayBrowserProvider`, `browser_launcher.py`
- Do not modify `ContentBriefOrchestrator` engine order (except 12J-E topic injection)
- Do not modify voice / subtitle / assembly paths
- Backward compatible: flag off = 12J-A behavior

---

## 7. Configuration Keys (Frozen Names)

| Key | Default | Phase |
|-----|---------|-------|
| `RUNWAY_PROMPT_COMPOSER_ENABLED` | `false` | 12J-C |
| `RUNWAY_PROMPT_COMPOSER_VERSION` | `12j_c_v1` | 12J-C |
| `RUNWAY_PROMPT_MERGE_PAYOFF_INTO_LAST_CLIP` | `true` | 12J-C |
| `RUNWAY_PROMPT_MAX_CHARS` | `950` | 12J-C (adapter) |
| `RUNWAY_PROMPT_SPECIFICITY_MIN` | `0.55` | 12J-C |
| `RUNWAY_PROMPT_LEXICON_FALLBACK_MIN_SCORE` | `0.35` genericity | 12J-D |
| `RUNWAY_PROMPT_COMPOSER_STRICT_QUALITY` | `false` | 12J-D |

---

## 8. Acceptance Tests (Design — for 12J-C implementation)

| ID | Test |
|----|------|
| T1 | N=2, topic `dog` → clip 2 `payoff_payload.folded_beat_ids` contains PATTERN_BREAK, PAYOFF, LOOP_SEED |
| T2 | `lineage.precedence_applied` order matches §2.1 |
| T3 | Retention VISUAL present in clip 1 `retention_payload.primary_visual` when map has hook window |
| T4 | Flag off → byte-identical adapter behavior vs pre-12J-C |
| T5 | `composed_prompt` length > 950 → adapter truncates; `metadata.pre_truncation_prompt` retains full text |
| T6 | `genericity_score` > 0.35 on lexicon-only input → `lexicon_fallback_used` or enrich recovery |

---

## 9. Design Freeze Checklist

- [x] `ComposedClipPrompt` exact schema with 11 required top-level fields
- [x] Precedence: Retention → Architecture → Director → Thumbnail → Lexicon
- [x] Exact `merge_prose_v1` + `augment()` rules
- [x] Beat-collapse 6→2 with worked `dog` example
- [x] Quality: genericity, specificity, visual richness, entropy
- [x] SessionPromptAdapter vs composer boundary
- [x] Rollout 12J-C through 12J-F

**Next step:** Implementation of 12J-C only after explicit approval. No code in this phase.

---

## References

- `project_brain/PHASE_12J_A_CONTENT_BRAIN_TRACE_AUDIT.md`
- `project_brain/PHASE_12J_B_VISUAL_INTELLIGENCE_RESTORATION_DESIGN.md`
- `content_brain/execution/session_prompt_adapter.py` (10I adapter contract)
- UAT reference session: `exec_uat_20260602_055459`
