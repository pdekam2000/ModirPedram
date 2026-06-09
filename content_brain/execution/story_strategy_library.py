"""
Story Strategy Library — strategy-specific hook, beats, conflict, and visual language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STRATEGY_INSTRUCTIONAL = "instructional"
STRATEGY_TUTORIAL = "tutorial"
STRATEGY_DOCUMENTARY = "documentary"
STRATEGY_MYSTERY = "mystery"
STRATEGY_HORROR = "horror"
STRATEGY_CHALLENGE = "challenge"
STRATEGY_COMPARISON = "comparison"
STRATEGY_REVIEW = "review"
STRATEGY_CASE_STUDY = "case_study"
STRATEGY_NEWS = "news_explainer"
STRATEGY_EXPERIMENT = "experiment"
STRATEGY_LIFESTYLE = "lifestyle"
STRATEGY_PRODUCT_DEMO = "product_demo"

CONTENT_STRATEGY_MAP: dict[str, str] = {
    "instructional_fishing": STRATEGY_INSTRUCTIONAL,
    "instructional_general": STRATEGY_INSTRUCTIONAL,
    "recipe_tutorial": STRATEGY_TUTORIAL,
    "educational_tech": STRATEGY_TUTORIAL,
    "educational_lifestyle": STRATEGY_LIFESTYLE,
    "documentary": STRATEGY_DOCUMENTARY,
    "narrative_mystery": STRATEGY_MYSTERY,
    "historical_investigation": STRATEGY_DOCUMENTARY,
    "horror_storytelling": STRATEGY_HORROR,
    "journalistic": STRATEGY_NEWS,
    "business_case_study": STRATEGY_CASE_STUDY,
    "future_analysis": STRATEGY_DOCUMENTARY,
    "business_debate": STRATEGY_CASE_STUDY,
    "technology_forecast": STRATEGY_DOCUMENTARY,
    "scientific_explanation": STRATEGY_TUTORIAL,
    "cinematic_narrative": STRATEGY_DOCUMENTARY,
}


@dataclass
class StoryStrategyProfile:
    strategy_id: str
    label: str
    hook_structure: str
    clip_beat_structure: tuple[str, ...]
    conflict_type: str
    payoff_type: str
    visual_language: str
    prompt_rules: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "label": self.label,
            "hook_structure": self.hook_structure,
            "clip_beat_structure": list(self.clip_beat_structure),
            "conflict_type": self.conflict_type,
            "payoff_type": self.payoff_type,
            "visual_language": self.visual_language,
            "prompt_rules": list(self.prompt_rules),
        }


STORY_STRATEGIES: dict[str, StoryStrategyProfile] = {
    STRATEGY_INSTRUCTIONAL: StoryStrategyProfile(
        strategy_id=STRATEGY_INSTRUCTIONAL,
        label="Instructional",
        hook_structure="Common mistake or setup gap that the viewer recognizes immediately.",
        clip_beat_structure=(
            "Clip 1 — setup / common mistake / preparation",
            "Clip 2 — method / hands-on demonstration",
            "Clip 3 — result / proof / takeaway",
        ),
        conflict_type="Will this method work before conditions change?",
        payoff_type="Clear takeaway the viewer can replicate.",
        visual_language="Hands-on detail, readable steps, documentary close-ups.",
        prompt_rules=(
            "Show domain tools and technique clearly.",
            "Avoid generic emotional walking shots unless they teach the method.",
        ),
    ),
    STRATEGY_TUTORIAL: StoryStrategyProfile(
        strategy_id=STRATEGY_TUTORIAL,
        label="Tutorial",
        hook_structure="Promise a repeatable outcome in one short sequence.",
        clip_beat_structure=(
            "Clip 1 — ingredients/tools/setup",
            "Clip 2 — core steps demonstrated",
            "Clip 3 — finished result and tip",
        ),
        conflict_type="Can the viewer follow these steps and get the same result?",
        payoff_type="Finished outcome plus one pro tip.",
        visual_language="Step-by-step clarity, labeled actions, clean progression.",
        prompt_rules=("Use numbered visual progression.", "Keep hands and tools readable."),
    ),
    STRATEGY_DOCUMENTARY: StoryStrategyProfile(
        strategy_id=STRATEGY_DOCUMENTARY,
        label="Documentary",
        hook_structure="Context that frames why this matters now.",
        clip_beat_structure=(
            "Clip 1 — context",
            "Clip 2 — evidence / escalation",
            "Clip 3 — conclusion",
        ),
        conflict_type="What is the most important unanswered question?",
        payoff_type="Evidence-backed conclusion.",
        visual_language="Observational framing, evidence inserts, grounded realism.",
        prompt_rules=("Prioritize evidence over spectacle.",),
    ),
    STRATEGY_MYSTERY: StoryStrategyProfile(
        strategy_id=STRATEGY_MYSTERY,
        label="Mystery",
        hook_structure="Strange clue or contradiction that demands explanation.",
        clip_beat_structure=(
            "Clip 1 — strange clue",
            "Clip 2 — investigation / escalation",
            "Clip 3 — reveal / open loop",
        ),
        conflict_type="What really happened and what detail does not fit?",
        payoff_type="Reveal or compelling open loop.",
        visual_language="Clue-first framing, tension through detail, controlled reveal.",
        prompt_rules=("Every clip must advance the mystery.", "No unrelated spectacle."),
    ),
    STRATEGY_REVIEW: StoryStrategyProfile(
        strategy_id=STRATEGY_REVIEW,
        label="Review",
        hook_structure="Bold claim or product reveal tied to viewer need.",
        clip_beat_structure=(
            "Clip 1 — claim / product reveal",
            "Clip 2 — test / comparison",
            "Clip 3 — verdict",
        ),
        conflict_type="Does the product live up to the claim?",
        payoff_type="Clear verdict and audience fit.",
        visual_language="Product-first, test evidence, comparison inserts.",
        prompt_rules=("Show the product being tested.", "Verdict must reference test evidence."),
    ),
    STRATEGY_CHALLENGE: StoryStrategyProfile(
        strategy_id=STRATEGY_CHALLENGE,
        label="Challenge",
        hook_structure="State the challenge rules immediately.",
        clip_beat_structure=(
            "Clip 1 — challenge setup",
            "Clip 2 — attempt / pressure",
            "Clip 3 — result / reaction",
        ),
        conflict_type="Can the challenge be completed under the stated rules?",
        payoff_type="Pass/fail result with reaction.",
        visual_language="Rule card energy, attempt montage, result beat.",
        prompt_rules=("State rules visually early.",),
    ),
    STRATEGY_NEWS: StoryStrategyProfile(
        strategy_id=STRATEGY_NEWS,
        label="News explainer",
        hook_structure="Lead with what happened and why it matters.",
        clip_beat_structure=(
            "Clip 1 — what happened",
            "Clip 2 — why it matters",
            "Clip 3 — impact / what changes",
        ),
        conflict_type="What is still unknown or disputed?",
        payoff_type="Impact summary.",
        visual_language="Headline clarity, fact-first inserts.",
        prompt_rules=("Lead with facts.",),
    ),
}


def resolve_story_strategy(content_strategy_id: str) -> StoryStrategyProfile:
    mapped = CONTENT_STRATEGY_MAP.get(content_strategy_id, STRATEGY_DOCUMENTARY)
    return STORY_STRATEGIES.get(mapped, STORY_STRATEGIES[STRATEGY_DOCUMENTARY])


def build_strategy_clip_beats(
    topic: str,
    strategy: StoryStrategyProfile,
    *,
    domain_beats: tuple[str, ...] = (),
    clip_count: int = 3,
) -> list[str]:
    if domain_beats:
        return [beat.format(topic=topic) for beat in domain_beats[:clip_count]]
    beats = list(strategy.clip_beat_structure)
    if len(beats) < clip_count:
        beats.extend([f"Clip {index + 1} beat for {topic}" for index in range(len(beats), clip_count)])
    return [item.replace("{topic}", topic) for item in beats[:clip_count]]


__all__ = [
    "STORY_STRATEGIES",
    "StoryStrategyProfile",
    "build_strategy_clip_beats",
    "resolve_story_strategy",
]
