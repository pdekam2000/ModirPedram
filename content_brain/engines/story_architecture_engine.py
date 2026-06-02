"""
Story Architecture Engine for the Viral Content Brain.

Turns TrendSignal + HookPackage into a structured StoryBlueprint
for any resolved profile/niche.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional

from content_brain.schemas.content_brief import (
    HookClass,
    HookPackage,
    Platform,
    StoryBeat,
    StoryBlueprint,
    StoryMode,
    TrendSignal,
)


BEAT_ORDER = [
    "HOOK_BEAT",
    "CONTEXT_BEAT",
    "ESCALATION_BEAT",
    "PATTERN_BREAK",
    "PAYOFF_BEAT",
    "LOOP_SEED",
]

BEAT_ACT_MAP = {
    "HOOK_BEAT": 1,
    "CONTEXT_BEAT": 1,
    "ESCALATION_BEAT": 2,
    "PATTERN_BREAK": 2,
    "PAYOFF_BEAT": 3,
    "LOOP_SEED": 3,
}

PROFILE_MODE_TO_SCHEMA: dict[str, StoryMode] = {
    "found_footage": StoryMode.FOUND_FOOTAGE,
    "confession": StoryMode.CONFESSION,
    "missing_person": StoryMode.MISSING_PERSON,
    "wrong_house": StoryMode.WRONG_HOUSE,
    "psychological_unraveling": StoryMode.PSYCHOLOGICAL_UNRAVELING,
    "lore_episode": StoryMode.LORE_EPISODE,
    "quick_tip": StoryMode.CONFESSION,
    "storytime": StoryMode.FOUND_FOOTAGE,
    "comparison": StoryMode.PSYCHOLOGICAL_UNRAVELING,
    "myth_busting": StoryMode.CONFESSION,
    "before_after": StoryMode.WRONG_HOUSE,
}

HOOK_CLASS_MODE_AFFINITY: dict[HookClass, list[str]] = {
    HookClass.VIOLATION: ["storytime", "found_footage", "wrong_house", "psychological_unraveling"],
    HookClass.INCOMPLETE_TRUTH: ["confession", "missing_person", "myth_busting", "storytime"],
    HookClass.PERSONAL_THREAT: ["quick_tip", "myth_busting", "confession"],
    HookClass.MORAL_DISCOMFORT: ["confession", "comparison", "psychological_unraveling"],
    HookClass.FALSE_SAFETY: ["before_after", "found_footage", "wrong_house"],
    HookClass.OPEN_LOOP_SEED: ["lore_episode", "storytime", "missing_person"],
}

GLOBAL_SAFETY_BANNED = [
    "guaranteed cure",
    "guaranteed to work",
    "100% guaranteed",
    "you will die",
    "stop taking your medication",
    "ignore your doctor",
    "proven fact that",
    "scientists confirm",
    "officially confirmed",
]

GLOBAL_CLICKBAIT = [
    "you won't believe",
    "what happened next will shock you",
    "doctors hate",
]


@dataclass
class StoryBeatPlan:
    beat_id: str
    start_second: float
    end_second: float
    purpose: str
    narration: str
    visual_prompt_hint: str
    emotional_intensity: float
    retention_function: str
    act: int = 1

    def to_story_beat(self) -> StoryBeat:
        return StoryBeat(
            beat_id=self.beat_id,
            act=self.act,
            start_second=self.start_second,
            end_second=self.end_second,
            description=(
                f"PURPOSE: {self.purpose} | "
                f"NARRATION: {self.narration} | "
                f"VISUAL: {self.visual_prompt_hint}"
            ),
            emotional_tone=f"{self.purpose.lower()} ({self.emotional_intensity:.2f})",
            retention_mechanic=self.retention_function,
        )


@dataclass
class StoryArchitectureResult:
    blueprint: StoryBlueprint
    beat_plans: list[StoryBeatPlan]
    profile_story_mode: str
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_story_mode": self.profile_story_mode,
            "schema_story_mode": self.blueprint.story_mode.value,
            "reasoning": self.reasoning,
            "blueprint": self.blueprint.to_dict(),
            "beat_plans": [
                {
                    "beat_id": beat.beat_id,
                    "start_second": beat.start_second,
                    "end_second": beat.end_second,
                    "purpose": beat.purpose,
                    "narration": beat.narration,
                    "visual_prompt_hint": beat.visual_prompt_hint,
                    "emotional_intensity": beat.emotional_intensity,
                    "retention_function": beat.retention_function,
                }
                for beat in self.beat_plans
            ],
        }


class StoryArchitectureEngine:
    """
    Build short-form story blueprints from trend + hook inputs.

    Usage:
        engine = StoryArchitectureEngine()
        result = engine.build(profile, trend_signal, hook_package)
        blueprint = result.blueprint
    """

    NICHE_VISUAL_HINTS: dict[str, dict[str, str]] = {
        "football": {
            "anchor": "slow-motion replay on the stadium monitor",
            "context": "wide shot of the crowd reacting before the close-up",
            "escalation": "split-screen between live play and VAR screen",
            "pattern_break": "hard cut to referee earpiece close-up",
            "payoff": "freeze-frame on the contested frame line",
            "loop": "scoreboard clock held one second longer than expected",
        },
        "perfume": {
            "anchor": "macro shot of scent on skin in warm light",
            "context": "hand applying fragrance with label visible",
            "escalation": "side-by-side paper strip vs skin test",
            "pattern_break": "cut to twenty-minute later close-up",
            "payoff": "reaction shot noticing the scent shift",
            "loop": "bottle cap left open beside the worn test strip",
            "sensory": "warm vanilla turning slightly powdery on the wrist",
        },
        "horror": {
            "anchor": "single hallway bulb flicker in an empty corridor",
            "context": "handheld shot entering the room mentioned in the hook",
            "escalation": "slow push toward the object that should not be there",
            "pattern_break": "sudden silence with one off-screen sound",
            "payoff": "partial reveal that implies a worse unseen detail",
            "loop": "door left ajar with light spilling the wrong direction",
            "sensory": "cold draft under the door with a faint humming sound",
        },
        "dark_mystery": {
            "anchor": "single hallway bulb flicker in an empty corridor",
            "context": "handheld shot entering the room mentioned in the hook",
            "escalation": "slow push toward the object that should not be there",
            "pattern_break": "sudden silence with one off-screen sound",
            "payoff": "partial reveal that implies a worse unseen detail",
            "loop": "door left ajar with light spilling the wrong direction",
            "sensory": "cold draft under the door with a faint humming sound",
        },
        "education": {
            "anchor": "notebook page with one step circled in red",
            "context": "student attempt shown in real time",
            "escalation": "common mistake highlighted beside corrected method",
            "pattern_break": "switch to visual memory diagram",
            "payoff": "final answer with the hidden assumption exposed",
            "loop": "question mark card held up for part two",
        },
        "music": {
            "anchor": "waveform close-up on the transition point",
            "context": "producer screen showing the bridge section",
            "escalation": "before-and-after audio layer toggle",
            "pattern_break": "mute all layers except one hidden element",
            "payoff": "full drop with the added transition effect",
            "loop": "cursor hovering over an unsaved project file",
        },
    }

    GENERIC_VISUAL_HINTS = {
        "anchor": "tight close-up on the subject tied to the hook",
        "context": "medium shot establishing the niche setting",
        "escalation": "detail shot revealing new information",
        "pattern_break": "camera angle or scene shift",
        "payoff": "clear visual proof or story turn",
        "loop": "unfinished detail held in frame for the sequel cue",
        "sensory": "one concrete texture, sound, or object in frame",
    }

    def build(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        hook_text: str = "",
    ) -> StoryArchitectureResult:
        context = self._build_context(profile, trend_signal, hook_package, hook_text)
        profile_mode = self._select_story_mode(context)
        schema_mode = self._resolve_schema_mode(profile_mode)
        duration = self._resolve_duration(profile, trend_signal)
        beat_windows = self._build_beat_windows(duration)

        beat_plans = self._build_beat_plans(context, profile_mode, beat_windows)
        beat_plans = self._apply_safety_filters(beat_plans, profile)

        reveal_type = self._select_reveal_type(profile, profile_mode, context)
        loop_seed = next(
            (beat.narration for beat in beat_plans if beat.beat_id == "LOOP_SEED"),
            "Open question for the next episode.",
        )
        sensory_anchor = self._resolve_sensory_anchor(context)

        blueprint = StoryBlueprint(
            story_mode=schema_mode,
            beats=[beat.to_story_beat() for beat in beat_plans],
            reveal_type=reveal_type,
            loop_seed=loop_seed,
            total_duration_seconds=duration,
            emotional_curve=[beat.emotional_intensity for beat in beat_plans],
            lore_refs=[f"profile_story_mode:{profile_mode}"],
            sensory_anchor=sensory_anchor,
        )

        reasoning = (
            f"Selected profile mode '{profile_mode}' mapped to schema mode "
            f"'{schema_mode.value}' for {context['niche_label']}. "
            f"Duration {duration}s on {context['platform'].value}. "
            f"Reveal type '{reveal_type}'."
        )

        return StoryArchitectureResult(
            blueprint=blueprint,
            beat_plans=beat_plans,
            profile_story_mode=profile_mode,
            reasoning=reasoning,
        )

    def build_blueprint(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        hook_text: str = "",
    ) -> StoryBlueprint:
        return self.build(
            profile=profile,
            trend_signal=trend_signal,
            hook_package=hook_package,
            hook_text=hook_text,
        ).blueprint

    def _build_context(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        hook_text: str,
    ) -> dict[str, Any]:
        topic = trend_signal.topic.strip()
        hook = hook_text.strip() or hook_package.best_hook_text.strip()
        if not hook and hook_package.variants:
            hook = hook_package.variants[0].text

        niche = str(profile.get("niche", "general"))
        niche_label = str(
            profile.get("niche_label", niche.replace("_", " ").title())
        )
        hook_class = hook_package.hook_class
        if hook_class is None and hook_package.variants:
            hook_class = hook_package.variants[0].hook_class

        visuals = self.NICHE_VISUAL_HINTS.get(niche, self.GENERIC_VISUAL_HINTS)

        return {
            "profile": profile,
            "topic": topic,
            "hook": hook,
            "hook_class": hook_class,
            "niche": niche,
            "niche_label": niche_label,
            "platform": trend_signal.platform,
            "visuals": visuals,
            "emotional_vector": trend_signal.emotional_vector,
        }

    def _select_story_mode(self, context: dict[str, Any]) -> str:
        profile = context["profile"]
        enabled = profile.get("story_modes", {}).get("enabled_modes", [])
        if not enabled:
            enabled = ["storytime"]

        scores: dict[str, float] = {}
        topic_lower = context["topic"].lower()
        hook_class = context["hook_class"]

        for mode in enabled:
            score = 50.0
            definition = profile.get("story_modes", {}).get("mode_definitions", {}).get(mode, "")
            definition_lower = str(definition).lower()

            if hook_class:
                affinity = HOOK_CLASS_MODE_AFFINITY.get(hook_class, [])
                if mode in affinity:
                    score += 20.0 - affinity.index(mode) * 3.0

            if any(token in topic_lower for token in re.findall(r"[a-zA-Z']+", mode.replace("_", " "))):
                score += 8.0

            for emotion, weight in context["emotional_vector"].items():
                if emotion in definition_lower:
                    score += min(10.0, float(weight) * 10.0)

            if mode == "lore_episode" and "part" in topic_lower:
                score += 6.0
            if mode in {"quick_tip", "myth_busting"} and any(
                token in topic_lower for token in ("mistake", "tip", "why", "how")
            ):
                score += 8.0
            if mode in {"found_footage", "confession", "storytime"} and any(
                token in topic_lower for token in ("story", "footage", "recording", "happened")
            ):
                score += 8.0

            scores[mode] = score

        return max(scores, key=scores.get)

    def _resolve_schema_mode(self, profile_mode: str) -> StoryMode:
        if profile_mode in PROFILE_MODE_TO_SCHEMA:
            return PROFILE_MODE_TO_SCHEMA[profile_mode]
        try:
            return StoryMode(profile_mode)
        except ValueError:
            return StoryMode.CONFESSION

    def _resolve_duration(self, profile: dict[str, Any], trend_signal: TrendSignal) -> int:
        content_format = profile.get("content_format", {})
        default_duration = int(content_format.get("default_duration_seconds", 30))
        min_duration = int(content_format.get("min_duration_seconds", 15))
        max_duration = int(content_format.get("max_duration_seconds", 58))

        platform_rules = profile.get("platform_rules", {}).get(
            trend_signal.platform.value,
            {},
        )
        ideal = platform_rules.get("ideal_duration_seconds", {})
        if isinstance(ideal, dict) and ideal.get("sweet_spot"):
            duration = int(ideal["sweet_spot"])
        else:
            duration = default_duration

        return max(min_duration, min(max_duration, duration))

    def _build_beat_windows(self, total_duration: int) -> dict[str, tuple[float, float]]:
        ratios = {
            "HOOK_BEAT": (0.0, 0.09),
            "CONTEXT_BEAT": (0.09, 0.20),
            "ESCALATION_BEAT": (0.20, 0.42),
            "PATTERN_BREAK": (0.42, 0.54),
            "PAYOFF_BEAT": (0.54, 0.82),
            "LOOP_SEED": (0.82, 1.0),
        }

        windows: dict[str, tuple[float, float]] = {}
        for beat_id, (start_ratio, end_ratio) in ratios.items():
            start = round(total_duration * start_ratio, 1)
            end = round(total_duration * end_ratio, 1)
            if end <= start:
                end = start + 0.5
            windows[beat_id] = (start, end)

        return windows

    def _build_beat_plans(
        self,
        context: dict[str, Any],
        profile_mode: str,
        beat_windows: dict[str, tuple[float, float]],
    ) -> list[StoryBeatPlan]:
        builders = {
            "HOOK_BEAT": self._build_hook_beat,
            "CONTEXT_BEAT": self._build_context_beat,
            "ESCALATION_BEAT": self._build_escalation_beat,
            "PATTERN_BREAK": self._build_pattern_break_beat,
            "PAYOFF_BEAT": self._build_payoff_beat,
            "LOOP_SEED": self._build_loop_seed_beat,
        }

        plans: list[StoryBeatPlan] = []
        for beat_id in BEAT_ORDER:
            start, end = beat_windows[beat_id]
            plan = builders[beat_id](context, profile_mode, start, end)
            plan.act = BEAT_ACT_MAP[beat_id]
            plans.append(plan)

        return plans

    def _build_hook_beat(
        self,
        context: dict[str, Any],
        profile_mode: str,
        start: float,
        end: float,
    ) -> StoryBeatPlan:
        del profile_mode
        return StoryBeatPlan(
            beat_id="HOOK_BEAT",
            start_second=start,
            end_second=end,
            purpose="Pattern interrupt and immediate stakes",
            narration=context["hook"],
            visual_prompt_hint=context["visuals"]["anchor"],
            emotional_intensity=0.85,
            retention_function="pattern_interrupt",
        )

    def _build_context_beat(
        self,
        context: dict[str, Any],
        profile_mode: str,
        start: float,
        end: float,
    ) -> StoryBeatPlan:
        narration = self._mode_narration(
            profile_mode,
            context,
            beat_key="context",
            fallback=(
                f"Set up the {context['niche_label']} situation behind the hook: "
                f"{context['topic']}."
            ),
        )
        return StoryBeatPlan(
            beat_id="CONTEXT_BEAT",
            start_second=start,
            end_second=end,
            purpose="Establish context without over-explaining",
            narration=narration,
            visual_prompt_hint=context["visuals"]["context"],
            emotional_intensity=0.55,
            retention_function="curiosity_gap",
        )

    def _build_escalation_beat(
        self,
        context: dict[str, Any],
        profile_mode: str,
        start: float,
        end: float,
    ) -> StoryBeatPlan:
        narration = self._mode_narration(
            profile_mode,
            context,
            beat_key="escalation",
            fallback=(
                f"Raise the stakes in {context['niche_label']} with one new detail "
                f"that changes how the viewer reads {context['topic']}."
            ),
        )
        return StoryBeatPlan(
            beat_id="ESCALATION_BEAT",
            start_second=start,
            end_second=end,
            purpose="Increase tension or value",
            narration=narration,
            visual_prompt_hint=context["visuals"]["escalation"],
            emotional_intensity=0.72,
            retention_function="stakes_increase",
        )

    def _build_pattern_break_beat(
        self,
        context: dict[str, Any],
        profile_mode: str,
        start: float,
        end: float,
    ) -> StoryBeatPlan:
        del profile_mode
        return StoryBeatPlan(
            beat_id="PATTERN_BREAK",
            start_second=start,
            end_second=end,
            purpose="Shift angle before the payoff",
            narration=(
                f"Shift perspective: the obvious read on {context['topic']} is incomplete."
            ),
            visual_prompt_hint=context["visuals"]["pattern_break"],
            emotional_intensity=0.78,
            retention_function="perspective_shift",
        )

    def _build_payoff_beat(
        self,
        context: dict[str, Any],
        profile_mode: str,
        start: float,
        end: float,
    ) -> StoryBeatPlan:
        narration = self._mode_narration(
            profile_mode,
            context,
            beat_key="payoff",
            fallback=(
                f"Deliver the payoff for {context['niche_label']} without fake certainty: "
                f"show what changes after {context['topic']}."
            ),
        )
        return StoryBeatPlan(
            beat_id="PAYOFF_BEAT",
            start_second=start,
            end_second=end,
            purpose="Payoff that matches the hook promise",
            narration=narration,
            visual_prompt_hint=context["visuals"]["payoff"],
            emotional_intensity=0.92,
            retention_function="peak_moment",
        )

    def _build_loop_seed_beat(
        self,
        context: dict[str, Any],
        profile_mode: str,
        start: float,
        end: float,
    ) -> StoryBeatPlan:
        del profile_mode
        return StoryBeatPlan(
            beat_id="LOOP_SEED",
            start_second=start,
            end_second=end,
            purpose="Open loop for comments or next episode",
            narration=(
                f"Leave one unanswered detail about {context['topic']} so "
                f"{context['niche_label']} viewers comment or wait for part two."
            ),
            visual_prompt_hint=context["visuals"]["loop"],
            emotional_intensity=0.66,
            retention_function="open_loop",
        )

    def _mode_narration(
        self,
        profile_mode: str,
        context: dict[str, Any],
        beat_key: str,
        fallback: str,
    ) -> str:
        niche = context["niche"]
        topic = context["topic"]
        niche_label = context["niche_label"]

        templates: dict[str, dict[str, str]] = {
            "football": {
                "context": f"Before the whistle, the play looked routine — then {topic} started to look different on replay.",
                "escalation": "The wide angle and the referee monitor do not tell the same story.",
                "payoff": "One frame line decides how fans will argue about this clip all week.",
            },
            "perfume": {
                "context": f"On paper, {topic} sounds simple — the test only gets interesting on skin.",
                "escalation": "The opening note fades, and the dry-down tells a different story.",
                "payoff": "This is why the same bottle can feel completely different by minute twenty.",
            },
            "horror": {
                "context": f"The room seemed ordinary until {topic} stopped matching the layout they remembered.",
                "escalation": "Each detail is small alone; together they feel wrong.",
                "payoff": "The camera catches enough to disturb, not enough to explain.",
            },
            "dark_mystery": {
                "context": f"The room seemed ordinary until {topic} stopped matching the layout they remembered.",
                "escalation": "Each detail is small alone; together they feel wrong.",
                "payoff": "The camera catches enough to disturb, not enough to explain.",
            },
            "education": {
                "context": f"Most students approach {topic} the same way — that is where the mistake starts.",
                "escalation": "One skipped step makes the final answer look correct for the wrong reason.",
                "payoff": "Fix the hidden assumption and the solution becomes much simpler.",
            },
            "music": {
                "context": f"The transition in {topic} sounds obvious until the underlying layer is removed.",
                "escalation": "One muted element reveals why the drop hits harder than expected.",
                "payoff": "The bridge works because of a detail most listeners never isolate.",
            },
        }

        generic_by_mode = {
            "quick_tip": {
                "context": f"Here is the setup most {niche_label} viewers miss around {topic}.",
                "escalation": f"One practical detail makes the tip worth saving.",
                "payoff": f"Apply this once in {niche_label} and compare the result yourself.",
            },
            "myth_busting": {
                "context": f"A common {niche_label} belief breaks down when you test {topic}.",
                "escalation": "The popular version skips the part that changes the outcome.",
                "payoff": "The safer read is less dramatic — and more useful.",
            },
            "comparison": {
                "context": f"Two {niche_label} paths look similar until {topic} separates them.",
                "escalation": "The difference is subtle early and obvious later.",
                "payoff": "Choose based on the tradeoff, not the headline.",
            },
            "before_after": {
                "context": f"Before: the usual {niche_label} result. The turn starts at {topic}.",
                "escalation": "The middle step is the part most clips skip.",
                "payoff": "After: the visible change and what likely caused it.",
            },
            "storytime": {
                "context": f"The story starts normally for {niche_label}, then {topic} becomes the turn.",
                "escalation": "The situation gets harder to explain with each new detail.",
                "payoff": "The ending reframes everything shown in the first seconds.",
            },
            "found_footage": {
                "context": f"The recording begins like normal {niche_label} footage until {topic} appears.",
                "escalation": "The camera lingers on what the subject tries not to show.",
                "payoff": "The clip ends before full answers arrive — on purpose.",
            },
            "confession": {
                "context": f"I thought I understood {topic} until one detail stopped making sense.",
                "escalation": "The part I left out at the start changes the whole story.",
                "payoff": "I still cannot tell whether the scariest part already happened.",
            },
        }

        if niche in templates and beat_key in templates[niche]:
            return templates[niche][beat_key]
        if profile_mode in generic_by_mode and beat_key in generic_by_mode[profile_mode]:
            return generic_by_mode[profile_mode][beat_key]
        return fallback

    def _select_reveal_type(
        self,
        profile: dict[str, Any],
        profile_mode: str,
        context: dict[str, Any],
    ) -> str:
        allowed = profile.get("story_modes", {}).get("reveal_types_allowed", [])
        if not allowed:
            allowed = ["open_loop_reveal"]

        mode_defaults = {
            "comparison": "comparison_reveal",
            "myth_busting": "proof_reveal",
            "before_after": "result_reveal",
            "quick_tip": "result_reveal",
            "found_footage": "partial_reveal",
            "confession": "implied_reveal",
            "missing_person": "temporal_reveal",
            "wrong_house": "spatial_reveal",
            "psychological_unraveling": "moral_reveal",
            "lore_episode": "open_loop_reveal",
            "storytime": "twist_reveal",
        }

        preferred = mode_defaults.get(profile_mode)
        if preferred and preferred in allowed:
            return preferred

        if context["hook_class"] == HookClass.INCOMPLETE_TRUTH and "implied_reveal" in allowed:
            return "implied_reveal"
        if context["hook_class"] == HookClass.OPEN_LOOP_SEED and "open_loop_reveal" in allowed:
            return "open_loop_reveal"

        return allowed[0]

    def _resolve_sensory_anchor(self, context: dict[str, Any]) -> str:
        visuals = context["visuals"]
        if visuals.get("sensory"):
            return str(visuals["sensory"])

        must_include = context["profile"].get("tone_rules", {}).get("must_include", [])
        for rule in must_include:
            if "sensory" in str(rule).lower() or "anchor" in str(rule).lower():
                return f"One concrete sensory anchor tied to {context['topic']}."

        return f"One niche-specific detail that makes {context['topic']} feel real on screen."

    def _apply_safety_filters(
        self,
        beat_plans: list[StoryBeatPlan],
        profile: dict[str, Any],
    ) -> list[StoryBeatPlan]:
        cleaned: list[StoryBeatPlan] = []
        banned = profile.get("banned_generic_patterns", {}).get("banned_phrases", [])

        for beat in beat_plans:
            narration = self._sanitize_text(beat.narration, banned)
            purpose = self._sanitize_text(beat.purpose, banned)
            visual = self._sanitize_text(beat.visual_prompt_hint, banned)

            cleaned.append(
                StoryBeatPlan(
                    beat_id=beat.beat_id,
                    start_second=beat.start_second,
                    end_second=beat.end_second,
                    purpose=purpose,
                    narration=narration,
                    visual_prompt_hint=visual,
                    emotional_intensity=beat.emotional_intensity,
                    retention_function=beat.retention_function,
                    act=beat.act,
                )
            )

        return cleaned

    def _sanitize_text(self, text: str, profile_banned: list[str]) -> str:
        cleaned = text
        lower = cleaned.lower()

        for phrase in GLOBAL_SAFETY_BANNED + GLOBAL_CLICKBAIT + profile_banned:
            if phrase.lower() in lower:
                cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        cleaned = cleaned.replace("guaranteed", "likely")
        cleaned = cleaned.replace("proven fact", "visible detail")
        cleaned = cleaned.replace("officially confirmed", "shown on screen")

        if not cleaned:
            return "Focus on what can be shown, not absolute claims."
        return cleaned


__all__ = [
    "StoryArchitectureEngine",
    "StoryArchitectureResult",
    "StoryBeatPlan",
]


if __name__ == "__main__":
    from content_brain.engines.hook_engineering_engine import HookEngineeringEngine
    from content_brain.engines.trend_discovery_engine import TrendDiscoveryEngine
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    trend_engine = TrendDiscoveryEngine()
    hook_engine = HookEngineeringEngine()
    story_engine = StoryArchitectureEngine()

    test_cases = [
        ("football", "VAR decisions in the 89th minute"),
        ("perfume", "Vanilla skin chemistry after twenty minutes"),
        ("horror", "The hallway light flickered once before the door opened"),
    ]

    for niche, topic in test_cases:
        profile = loader.resolve(niche=niche)
        trend_result = trend_engine.discover(profile, niche=niche, topic=topic, max_results=3)
        trend_signal = trend_result.best_signal
        hook_package = hook_engine.generate_hook_package(profile, topic=trend_signal.topic)

        result = story_engine.build(profile, trend_signal, hook_package)

        print("\n" + "=" * 72)
        print(f"NICHE: {niche}")
        print(f"MODE: {result.profile_story_mode} -> {result.blueprint.story_mode.value}")
        print(f"DURATION: {result.blueprint.total_duration_seconds}s")
        print(f"REVEAL: {result.blueprint.reveal_type}")
        print(f"BEATS: {len(result.blueprint.beats)}")
        print(f"VALID: {result.blueprint.validate().is_valid}")
        print(f"HOOK BEAT: {result.beat_plans[0].narration[:90]}...")
