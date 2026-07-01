# PHASE — Channel Topic Diversity and Story Ideation Repair

**Phase:** CHANNEL-TOPIC-DIVERSITY-AND-STORY-IDEATION-REPAIR  
**Date:** 2026-06-20  
**No provider calls. No credits spent. No live generation.**

---

## Problem

The system treated the channel topic as the story itself, causing repeated dragon/forest/boy motifs and near-identical narrative seeds across runs.

## Solution

Introduced a **Channel Story Ideation** layer before prompt building:

```
channel_topic (niche / creative direction)
        ↓
channel_story_ideation
        ↓
RunwayStoryBrief + story_package
        ↓
Kling Frame-to-Video planner / Prompt Builder
        ↓
clip prompts
```

---

## Files created

| File | Purpose |
|------|---------|
| `content_brain/execution/channel_story_ideation.py` | Ideation engine, anti-repetition, memory, brief conversion |
| `data/story_memory/.gitkeep` | Memory directory scaffold |
| `project_brain/validate_channel_story_ideation_diversity.py` | 19-test validation suite |
| `project_brain/PHASE_CHANNEL_TOPIC_DIVERSITY_STORY_IDEATION_REPORT.md` | This report |

## Files modified

| File | Change |
|------|--------|
| `ui/api/product_studio_service.py` | Preflight calls ideation; passes `story_package` to Kling planner |
| `ui/api/schemas/product_studio.py` | `specific_story_override`, ideation response fields |
| `ui/web/src/pages/CreateVideoPage.tsx` | Labels + optional story override field |

**Not modified:** pwmap runner, Runway/Kling browser automation, download logic, credit guards.

---

## Channel topic vs story override

| Input | Behavior |
|-------|----------|
| **Channel Topic / Niche** | Creative direction only — ideation generates a fresh `ChannelStoryIdea` each run |
| **Specific Story Override** (optional) | Exact story used when filled; repetition warning still emitted if too similar to memory |
| Empty override | Auto ideation with `safe_variety` default |

Preflight fields:
- `channel_topic` — original niche string
- `authoritative_topic` — generated rich story text used by prompt planner (not raw niche alone)
- `channel_story_idea`, `runway_story_brief`, `story_package`

---

## Anti-repetition rules

| Rule | Threshold / action |
|------|-------------------|
| Exact repeated title | Reject |
| Same core object + same setting | Reject |
| Logline Jaccard similarity | Reject if > **0.72** |
| Prompt/text similarity | Reject if > **0.78** |
| Same character archetype | Reject if **3** consecutive runs |
| Dragon egg / boy / forest pattern | Reject after first use in memory |

Up to **16** regeneration attempts per ideation call.

---

## Diversity modes

| Mode | Behavior |
|------|----------|
| `safe_variety` (default) | Stays in niche, rotates settings/characters/objects |
| `high_variety` | Expanded setting pool, more experimental combinations |
| `episodic_series` | Same world tone, new episode plot per run |

---

## Story memory format

**Path:** `data/story_memory/channel_story_history.jsonl`  
**Mode:** append-only JSONL (no auto-delete)

Each line:
```json
{
  "timestamp": "ISO-8601",
  "channel_topic": "...",
  "unique_story_id": "...",
  "title": "...",
  "logline": "...",
  "main_character": "...",
  "setting": "...",
  "conflict": "...",
  "visual_hook": "...",
  "ending_beat": "...",
  "novelty_tags": ["..."],
  "prompt_hash": "sha256…",
  "story_hash": "sha256…",
  "diversity_mode": "safe_variety"
}
```

No credentials, cookies, or tokens stored.

---

## Validation results

```text
python project_brain/validate_channel_story_ideation_diversity.py  → 19/19 PASS
python project_brain/validate_pwmap_30s_two_clip_duplicate_guard.py  → 15/15 PASS
python project_brain/validate_results_run_truth_consistency.py       → 19/19 PASS
```

Coverage includes:
- Different titles/settings/characters from same channel topic
- Dragon-egg pattern rejection
- Logline/prompt similarity rejection
- Append-only memory
- Preflight receives `runway_story_brief`
- Story override path
- UI labels
- No provider calls in ideation module
- Duration planner + duplicate guard + results truth regressions

---

## Confirmations

- No provider/browser automation changes  
- No Runway/Kling live calls  
- No credits spent  
- No video generation performed  

---

## Next recommended phase

**PHASE PWMAP-30S-TWO-CLIP-LIVE-RETEST**

Prerequisites now in place:
1. Fresh story ideation per channel topic (this phase)
2. Duplicate/stale-download guards (prior phase)
3. Free-credit-first safety rule (prior phase)

Live retest should use:
- `free_credit_mode: true` or confirmed free quota
- Empty story override (auto ideation)
- 30s / 2-clip duration
- Verify distinct clip outputs and non-repeated story concepts before any paid run
