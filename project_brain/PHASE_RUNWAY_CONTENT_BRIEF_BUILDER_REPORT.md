# Phase RUNWAY-CONTENT-BRIEF — Story Brief Builder Report

**Version:** `runway_story_brief_v1`  
**Layer:** Content Brain → Runway Prompt Builder (pre-automation)  
**Status:** Validated (no browser · no Runway · no credits)

---

## Problem

Runway runtime and UI approval flow work, but operators often enter **weak or short story ideas**. A one-line topic does not give Prompt Builder enough character, setting, conflict, or clip beats to produce strong starter/clip prompts.

## Solution

Add a **content layer** before `runway_prompt_builder.py`:

```
User topic / idea
    ↓
runway_story_brief_builder.py  →  RunwayStoryBrief
    ↓
runway_prompt_builder.py       →  starter_image_prompt + clip_prompts[]
    ↓
(existing Runway semi-auto / live smoke — unchanged)
```

---

## RunwayStoryBrief output

| Field | Purpose |
|-------|---------|
| `title` | Short working title |
| `logline` | Expanded narrative seed |
| `main_character` | Continuity subject |
| `setting` | Locked environment |
| `conflict_tension` | Story pressure |
| `visual_hook` | Scroll-stopping opening detail |
| `emotional_arc` | Mood progression |
| `ending_beat` | Final clip payoff |
| `style_direction` | Platform + niche visual direction |
| `continuity_anchors` | Character / location / lighting / camera / palette |
| `clip_beats` | Per-clip action outline (default 3) |

### Inputs

- `topic` / story idea
- `target_platform` (e.g. `youtube_shorts`, `tiktok`, `instagram_reels`)
- `niche_style` (e.g. `cinematic`, `cyberpunk`, `documentary`, `mystery`)
- `mood`
- `clip_count` / duration context

---

## Prompt Builder integration

- `build_continuity_prompts(..., auto_story_brief=True)` — default ON; builds brief then prompts
- `build_continuity_prompts(..., auto_story_brief=False)` — legacy raw-sentence path
- `build_continuity_prompts_from_brief(brief)` — explicit brief → prompts
- Bundle includes optional `story_brief` in `to_dict()` for traceability

**Not changed:** Runway automation, approval gates, provider router, browser provider.

---

## Validation

```bash
python project_brain/validate_runway_story_brief_builder.py
```

Checks:

- Story brief fields populated (character, setting, conflict, hook, ending)
- 3 clip beats for default 3-clip flow
- Prompt builder receives rich brief
- Short topic → longer starter prompt with hook/tension language
- Clip prompts preserve continuity lock + Use Frame / Use to Video language

Regression (Prompt Builder F):

```bash
python project_brain/validate_runway_starter_to_video_prompt_builder.py
```

---

## Example — short topic

**Input:**

```text
astronaut alone on neon platform in rain
```

**Brief expands to:** character, rain-soaked neon setting, tension, visual hook, 3 clip beats, cyberpunk anchors.

**Result:** richer `starter_image_prompt` and continuity-aware clip prompts vs raw one-liner.

---

## Files

| File | Role |
|------|------|
| `content_brain/execution/runway_story_brief_builder.py` | Story brief builder |
| `content_brain/execution/runway_prompt_builder.py` | Brief-aware prompt builder |
| `project_brain/validate_runway_story_brief_builder.py` | Validator |
| `project_brain/PHASE_RUNWAY_CONTENT_BRIEF_BUILDER_REPORT.md` | This report |

---

## Usage before Phase I live run

```python
from content_brain.execution.runway_story_brief_builder import build_runway_story_brief
from content_brain.execution.runway_prompt_builder import build_continuity_prompts_from_brief

brief = build_runway_story_brief(
    "astronaut on neon platform in rain",
    target_platform="youtube_shorts",
    niche_style="cyberpunk",
    mood="tense hopeful",
    clip_count=3,
)
bundle = build_continuity_prompts_from_brief(brief, project_id="phase_i_live")
plan = bundle.to_continuity_plan()
```

Or let live smoke auto-expand (default):

```python
build_continuity_prompts(
    user_story_text,
    clip_count=3,
    niche_style="cyberpunk",
    mood="tense hopeful",
)
```

---

_Last validated by `validate_runway_story_brief_builder.py`._
