# Phase I.5 — Story Progression Audit

**Date:** 2026-06-04  
**Scope:** Why Phase I 3-clip outputs looked visually similar; which module owns the fix.

---

## Observed symptom

Operator reported that after a successful Phase I continuity run (starter image → 3 clips → Use Frame chain), **all three clips looked like the same standing pose** — little visible discovery, escalation, or payoff.

Continuity constraints were working (same character, location, wardrobe) but **narrative differentiation was too weak**.

---

## Pipeline traced

```
Operator story
  → RunwayStoryBriefBuilder.build()          # clip_beats[]
  → RunwayPromptBuilder.build()              # starter + clip_prompts[]
  → RunwayContinuitySemiAutoEngine           # fills prompt_input per clip
  → Runway browser Generate (approval-gated)
```

Downloads (separate concern):

```
download_mp4_button (×3, approval-gated)
  → browser saves to downloads/runway/       # catalog default
  → RunwayPhaseIDownloadTracker.verify_clip_download()
  → runway_phase_i_3clip_last_report.json
```

---

## Root cause — why clips became too similar

### 1. Generic clip beat templates (`runway_story_brief_builder.py`)

**Module:** `content_brain/execution/runway_story_brief_builder.py` → `_resolve_clip_beats()`

When the operator story did **not** include explicit `Clip 1:` / `Clip 2:` / `Clip 3:` lines, beats were generated from soft templates:

| Clip | Old template essence |
|------|----------------------|
| 1 | “establishes presence … micro-movement” |
| 2 | “advances through … motivated movement” |
| 3 | “payoff beat … decelerates toward end pose” |

Clip 1 and 2 both read as **standing / subtle motion in the same frame**. Runway interprets “micro-movement” and “same wardrobe and lighting persist” as **minimal pose change**.

### 2. Continuity-heavy prompt expansion (`runway_prompt_builder.py`)

**Module:** `content_brain/execution/runway_prompt_builder.py` → `_build_clip_prompt()` + `_expand_to_soft_target()`

Each clip prompt repeats:

- Continuity lock (character, location, wardrobe)
- Camera / lighting / environment **continuity** libraries (same direction, same atmosphere)
- “End frame must remain in same spatial layout”

These blocks dominate token budget (~800–950 chars). The **primary action beat** from StoryBrief was one line among many identical continuity paragraphs — so all three prompts **felt like the same standing hero shot with minor verb swaps**.

### 3. Weak motion verb differentiation

**Module:** `runway_prompt_builder.py` → `MOTION_VERBS_BY_PHASE`

Phrases like “subtle breathing motion” and “gentle environmental drift” for clip 1 encourage **static compositions**.

### 4. Starter image anchors clip 1

**Module:** `runway_prompt_builder.py` → `_build_starter_image_prompt()`

Starter frame is explicitly **static hold**. Clip 1 opens from Use to Video with that reference — without a strong **discovery action line**, Runway keeps the standing pose.

---

## What was NOT the cause

- Use Frame chaining (working as designed)
- Provider router / `RunwayBrowserProvider` dispatch
- Approval gate count (still 7)
- Assembly / Voice / Subtitle (not in Phase I path)

---

## Recommended fix (implemented in Phase I.5)

| Layer | Module | Change |
|-------|--------|--------|
| Beat semantics | `runway_story_brief_builder.py` | 3-clip default beats = **discovery → escalation → payoff** with explicit camera/environment verbs |
| Prompt roles | `runway_prompt_builder.py` | `CLIP_NARRATIVE_ROLES` block per clip (discovery / escalation / payoff) |
| Motion verbs | `runway_prompt_builder.py` | Stronger phase verbs (push-in discovery, tracking escalation, reveal payoff) |
| Validation | `runway_story_progression_validator.py` | Automated checks for unique beats + role markers + continuity preserved |

**Continuity preserved:** same character, location, wardrobe, Use Frame / Use to Video language — only **story energy, camera path, and environmental progression** increase.

---

## Module responsibility summary

| Concern | Owner module |
|---------|----------------|
| Clip beat narrative arc | `runway_story_brief_builder.py` |
| Prompt text sent to Runway | `runway_prompt_builder.py` |
| Download file verification | `runway_phase_i_download_tracker.py` |
| Live report fields | `runway_live_smoke_test.py` |
| Progression QA gates | `runway_story_progression_validator.py` |

---

## Operator guidance for richer clips

1. Include explicit beats in the story box: `Clip 1: … Clip 2: … Clip 3: …`
2. Clip 1 = **notice / turn / discover**; Clip 2 = **walk / track / intensify**; Clip 3 = **reach / touch / reveal**
3. Do not shorten beats to “standing” or “looking” — use **motivated physical verbs**
4. Re-run from **Runway Live Smoke → 3-Clip Continuity (Phase I)** after updating story text
