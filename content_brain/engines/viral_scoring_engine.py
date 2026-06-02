"""
Viral Scoring Engine V1 for the Viral Content Brain.

Aggregates upstream engine outputs into a weighted viral scorecard and
production gate decision. Rule-based only in V1 (no LLM).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import statistics
from typing import Any, Optional

from content_brain.schemas.content_brief import (
    HookPackage,
    ProductionTier,
    RetentionMap,
    ScoreDimension,
    StoryBlueprint,
    TrendSignal,
    UniquenessReport,
    ViralScorecard,
)

DEFAULT_DIMENSION_WEIGHTS: dict[str, float] = {
    "hook_strength": 0.2,
    "retention_architecture": 0.25,
    "emotional_intensity_curve": 0.15,
    "specificity": 0.1,
    "uniqueness": 0.15,
    "platform_fit": 0.1,
    "loop_potential": 0.05,
}

DEFAULT_DIMENSION_MINIMUMS: dict[str, float] = {
    "hook_strength": 65.0,
    "retention_architecture": 65.0,
    "emotional_intensity_curve": 55.0,
    "specificity": 60.0,
    "uniqueness": 65.0,
    "platform_fit": 55.0,
    "loop_potential": 45.0,
}

VAGUE_WORDS = {
    "something",
    "someone",
    "anything",
    "everything",
    "very",
    "really",
    "interesting",
    "amazing",
    "incredible",
    "stuff",
    "things",
}


@dataclass
class ViralScoringResult:
    scorecard: ViralScorecard
    failed_dimensions: list[str]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scorecard": self.scorecard.to_dict(),
            "failed_dimensions": self.failed_dimensions,
            "reasoning": self.reasoning,
        }


class ViralScoringEngine:
    """
    Score a content brief candidate across viral dimensions and assign a gate.

    Usage:
        engine = ViralScoringEngine()
        result = engine.score(
            profile,
            trend_signal,
            hook_package,
            story_blueprint,
            retention_map,
            uniqueness_report=uniqueness_result.report,
        )
    """

    def score(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
        retention_map: RetentionMap,
        uniqueness_report: Optional[UniquenessReport] = None,
    ) -> ViralScoringResult:
        thresholds = profile.get("scoring_thresholds", {})
        weights = self._resolve_weights(thresholds)
        minimums = self._resolve_minimums(thresholds)
        gate_minimum = float(thresholds.get("viral_gate_minimum", ViralScorecard.VIRAL_GATE_SCORE))

        dimension_scores = self._score_dimensions(
            trend_signal=trend_signal,
            hook_package=hook_package,
            story_blueprint=story_blueprint,
            retention_map=retention_map,
            uniqueness_report=uniqueness_report,
        )

        dimensions = [
            ScoreDimension(
                name=name,
                score=round(score, 2),
                weight=weights[name],
                notes=self._dimension_note(name, score, minimums.get(name, 0.0)),
            )
            for name, score in dimension_scores.items()
        ]

        composite_score = round(
            sum(item.score * item.weight for item in dimensions),
            2,
        )
        production_tier = self._assign_production_tier(
            composite_score,
            thresholds.get("production_tiers", {}),
        )

        failed_dimensions = [
            dimension.name
            for dimension in dimensions
            if dimension.score < minimums.get(dimension.name, 0.0)
        ]
        passed_gate = composite_score >= gate_minimum and not failed_dimensions

        scorecard = ViralScorecard(
            dimensions=dimensions,
            composite_score=composite_score,
            production_tier=production_tier,
            passed_gate=passed_gate,
            minimum_gate_score=gate_minimum,
        )

        validation = scorecard.validate()
        if not validation.is_valid:
            raise ValueError(
                "ViralScorecard validation failed: "
                + "; ".join(validation.errors)
            )

        reasoning = self._build_reasoning(
            scorecard=scorecard,
            failed_dimensions=failed_dimensions,
            uniqueness_report=uniqueness_report,
        )

        return ViralScoringResult(
            scorecard=scorecard,
            failed_dimensions=failed_dimensions,
            reasoning=reasoning,
        )

    def score_brief(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
        retention_map: RetentionMap,
        uniqueness_report: Optional[UniquenessReport] = None,
    ) -> ViralScorecard:
        return self.score(
            profile=profile,
            trend_signal=trend_signal,
            hook_package=hook_package,
            story_blueprint=story_blueprint,
            retention_map=retention_map,
            uniqueness_report=uniqueness_report,
        ).scorecard

    def _resolve_weights(self, thresholds: dict[str, Any]) -> dict[str, float]:
        configured = thresholds.get("dimension_weights", {})
        weights = dict(DEFAULT_DIMENSION_WEIGHTS)
        for name, value in configured.items():
            if name in weights:
                weights[name] = float(value)

        total = sum(weights.values())
        if total <= 0:
            return dict(DEFAULT_DIMENSION_WEIGHTS)

        return {name: round(value / total, 4) for name, value in weights.items()}

    def _resolve_minimums(self, thresholds: dict[str, Any]) -> dict[str, float]:
        configured = thresholds.get("dimension_minimums", {})
        minimums = dict(DEFAULT_DIMENSION_MINIMUMS)
        for name, value in configured.items():
            if name in minimums:
                minimums[name] = float(value)
        return minimums

    def _score_dimensions(
        self,
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
        retention_map: RetentionMap,
        uniqueness_report: Optional[UniquenessReport],
    ) -> dict[str, float]:
        return {
            "hook_strength": self._score_hook_strength(hook_package),
            "retention_architecture": self._score_retention_architecture(retention_map),
            "emotional_intensity_curve": self._score_emotional_curve(story_blueprint),
            "specificity": self._score_specificity(hook_package, story_blueprint),
            "uniqueness": self._score_uniqueness(uniqueness_report),
            "platform_fit": self._score_platform_fit(trend_signal),
            "loop_potential": self._score_loop_potential(story_blueprint, retention_map),
        }

    def _score_hook_strength(self, hook_package: HookPackage) -> float:
        if hook_package.composite_score > 0:
            return min(100.0, hook_package.composite_score)

        if not hook_package.variants:
            return 0.0

        best_variant = hook_package.variants[0]
        for variant in hook_package.variants:
            if variant.variant_id == hook_package.selected_variant_id:
                best_variant = variant
                break

        return round(
            min(
                100.0,
                (
                    best_variant.curiosity_gap_score * 0.35
                    + best_variant.interrupt_power * 0.35
                    + best_variant.specificity_score * 0.30
                ),
            ),
            2,
        )

    def _score_retention_architecture(self, retention_map: RetentionMap) -> float:
        base = retention_map.retention_score_estimate
        if base <= 0 and retention_map.beats:
            base = min(
                100.0,
                len(retention_map.beats) * 12.0
                + retention_map.pattern_break_count * 8.0
                + (10.0 if retention_map.loop_seed_present else 0.0),
            )
        return round(min(100.0, max(0.0, base)), 2)

    def _score_emotional_curve(self, story_blueprint: StoryBlueprint) -> float:
        curve = list(story_blueprint.emotional_curve)
        if not curve:
            curve = self._infer_emotional_curve(story_blueprint)

        if not curve:
            return 55.0

        peak = max(curve)
        mean = statistics.mean(curve)
        variance = statistics.pvariance(curve) if len(curve) > 1 else 0.0
        progression = curve[-1] - curve[0] if len(curve) >= 2 else 0.0

        peak_score = peak * 50.0
        mean_score = mean * 20.0
        variance_score = min(25.0, variance * 160.0)
        progression_score = max(0.0, min(15.0, progression * 45.0 + 8.0))

        return round(min(100.0, peak_score + mean_score + variance_score + progression_score), 2)

    def _infer_emotional_curve(self, story_blueprint: StoryBlueprint) -> list[float]:
        inferred: list[float] = []
        pattern = re.compile(r"\((\d+(?:\.\d+)?)\)")

        for beat in story_blueprint.beats:
            match = pattern.search(beat.emotional_tone or "")
            if match:
                inferred.append(min(1.0, max(0.0, float(match.group(1)))))

        return inferred

    def _score_specificity(
        self,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
    ) -> float:
        hook_text = hook_package.best_hook_text.strip()
        if not hook_text and hook_package.variants:
            hook_text = hook_package.variants[0].text

        variant_score = 0.0
        for variant in hook_package.variants:
            if variant.variant_id == hook_package.selected_variant_id or not variant_score:
                variant_score = variant.specificity_score

        concrete_bonus = 12.0 if _contains_concrete_detail(hook_text.lower()) else 0.0
        anchor_bonus = 15.0 if story_blueprint.sensory_anchor.strip() else 0.0
        vague_penalty = min(
            20.0,
            sum(1 for word in VAGUE_WORDS if f" {word} " in f" {hook_text.lower()} ") * 4.0,
        )

        score = variant_score * 0.75 + concrete_bonus + anchor_bonus - vague_penalty
        return round(min(100.0, max(0.0, score)), 2)

    def _score_uniqueness(self, uniqueness_report: Optional[UniquenessReport]) -> float:
        if uniqueness_report is None:
            return 60.0
        return round(min(100.0, max(0.0, uniqueness_report.uniqueness_score)), 2)

    def _score_platform_fit(self, trend_signal: TrendSignal) -> float:
        fit_values = list(trend_signal.platform_fit.values())
        if fit_values:
            return round(min(100.0, sum(fit_values) / len(fit_values)), 2)

        platform_key = trend_signal.platform.value
        if platform_key in trend_signal.platform_fit:
            return round(min(100.0, trend_signal.platform_fit[platform_key]), 2)

        trend_bonus = min(20.0, trend_signal.virality_score * 0.2)
        velocity_bonus = min(15.0, trend_signal.velocity * 0.15)
        saturation_penalty = min(25.0, trend_signal.saturation * 0.25)
        fallback = 50.0 + trend_bonus + velocity_bonus - saturation_penalty
        return round(min(100.0, max(0.0, fallback)), 2)

    def _score_loop_potential(
        self,
        story_blueprint: StoryBlueprint,
        retention_map: RetentionMap,
    ) -> float:
        score = 35.0
        loop_seed = story_blueprint.loop_seed.strip()

        if loop_seed:
            score += 25.0
        if "?" in loop_seed:
            score += 10.0
        if retention_map.loop_seed_present:
            score += 20.0
        if retention_map.pattern_break_count >= 2:
            score += 5.0
        if any(token in loop_seed.lower() for token in ("why", "what", "who", "next")):
            score += 5.0

        return round(min(100.0, score), 2)

    def _assign_production_tier(
        self,
        composite_score: float,
        production_tiers: dict[str, Any],
    ) -> ProductionTier:
        s_min = float(production_tiers.get("S", {}).get("min_score", 85))
        a_min = float(production_tiers.get("A", {}).get("min_score", 75))
        b_min = float(production_tiers.get("B", {}).get("min_score", 65))

        if composite_score >= s_min:
            return ProductionTier.S
        if composite_score >= a_min:
            return ProductionTier.A
        if composite_score >= b_min:
            return ProductionTier.B
        return ProductionTier.F

    def _dimension_note(self, name: str, score: float, minimum: float) -> str:
        status = "pass" if score >= minimum else "below minimum"
        return f"{name} scored {score:.1f}; minimum {minimum:.1f}; {status}."

    def _build_reasoning(
        self,
        scorecard: ViralScorecard,
        failed_dimensions: list[str],
        uniqueness_report: Optional[UniquenessReport],
    ) -> str:
        status = "passed" if scorecard.passed_gate else "failed"
        uniqueness_clause = ""
        if uniqueness_report is None:
            uniqueness_clause = " Uniqueness used neutral fallback (no report supplied)."
        elif not uniqueness_report.passed:
            uniqueness_clause = " Uniqueness gate had previously failed."

        failed_clause = ""
        if failed_dimensions:
            failed_clause = f" Failed dimensions: {', '.join(failed_dimensions)}."

        return (
            f"Viral score gate {status} with composite {scorecard.composite_score:.1f} "
            f"and tier {scorecard.production_tier.value}.{uniqueness_clause}{failed_clause}"
        )


def _contains_concrete_detail(lower_text: str) -> bool:
    return bool(
        re.search(
            r"\b\d+\b|"
            r"\b(january|february|march|april|may|june|july|august|september|"
            r"october|november|december|monday|tuesday|wednesday|thursday|friday|"
            r"saturday|sunday)\b|"
            r"\b(room|door|floor|camera|phone|video|replay|minute|second|angle)\b",
            lower_text,
        )
    )


__all__ = [
    "ViralScoringEngine",
    "ViralScoringResult",
]


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from content_brain.engines.hook_engineering_engine import HookEngineeringEngine
    from content_brain.engines.retention_map_engine import RetentionMapEngine
    from content_brain.engines.story_architecture_engine import StoryArchitectureEngine
    from content_brain.engines.trend_discovery_engine import TrendDiscoveryEngine
    from content_brain.engines.uniqueness_engine import UniquenessEngine
    from content_brain.engines.video_format_planner import VideoFormatPlanner
    from content_brain.profiles.profile_loader import ProfileLoader
    from content_brain.schemas.content_brief import Platform

    loader = ProfileLoader()
    trend_engine = TrendDiscoveryEngine()
    hook_engine = HookEngineeringEngine()
    story_engine = StoryArchitectureEngine()
    format_planner = VideoFormatPlanner()
    retention_engine = RetentionMapEngine()
    scoring_engine = ViralScoringEngine()

    cases = [
        ("football", 30, "hailuo", 6),
        ("horror", 60, "runway", 10),
        ("dark_mystery", 45, "runway", 10),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        memory_path = Path(tmp_dir) / "content_history.json"
        uniqueness_engine = UniquenessEngine(memory_path=memory_path)

        for niche, duration, provider, clip_duration in cases:
            profile = loader.resolve(niche=niche)
            trend = trend_engine.discover_best_signal(
                profile,
                niche=niche,
                topic=f"{niche} viral scoring test",
            )
            hooks = hook_engine.generate_hook_package(profile, topic=trend.topic)
            format_plan = format_planner.plan(
                profile,
                platform=Platform.TIKTOK,
                user_duration_seconds=duration,
                provider_name=provider,
                provider_clip_duration_seconds=clip_duration,
            )
            story = story_engine.build_blueprint(profile, trend, hooks)
            story.total_duration_seconds = format_plan.target_duration_seconds
            retention = retention_engine.build(profile, story, format_plan)
            uniqueness = uniqueness_engine.evaluate(profile, trend, hooks, story)

            result = scoring_engine.score(
                profile=profile,
                trend_signal=trend,
                hook_package=hooks,
                story_blueprint=story,
                retention_map=retention.retention_map,
                uniqueness_report=uniqueness.report,
            )

            print("\n" + "=" * 72)
            print(
                f"{niche.upper()} | composite {result.scorecard.composite_score} | "
                f"tier {result.scorecard.production_tier.value} | "
                f"gate {'PASS' if result.scorecard.passed_gate else 'FAIL'}"
            )
            for dimension in result.scorecard.dimensions:
                print(
                    f"  - {dimension.name}: {dimension.score:.1f} "
                    f"(weight {dimension.weight:.2f})"
                )
            print("REASONING:", result.reasoning)
            print("VALID:", result.scorecard.validate().is_valid)
