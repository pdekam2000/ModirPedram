"""
Content Decision Engine V1 for the Viral Content Brain.

Turns viral scoring and upstream artifacts into a production decision.
Rule-based only in V1 (no LLM, no external APIs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from content_brain.schemas.content_brief import (
    HookPackage,
    ProductionTier,
    RetentionMap,
    StoryBlueprint,
    UniquenessReport,
    ViralScorecard,
)

DEFAULT_DIMENSION_MINIMUMS: dict[str, float] = {
    "hook_strength": 65.0,
    "retention_architecture": 65.0,
    "emotional_intensity_curve": 55.0,
    "specificity": 60.0,
    "uniqueness": 65.0,
    "platform_fit": 55.0,
    "loop_potential": 45.0,
}

DIMENSION_REVISION_TARGETS: dict[str, list[str]] = {
    "hook_strength": ["hook"],
    "specificity": ["hook", "story_beats"],
    "retention_architecture": ["retention_map", "story_beats"],
    "emotional_intensity_curve": ["story_beats"],
    "platform_fit": ["video_format"],
    "loop_potential": ["loop_seed", "retention_map"],
    "uniqueness": ["hook", "story_beats", "trend_context"],
}

DIMENSION_PRIORITY_FIXES: dict[str, str] = {
    "hook_strength": "Strengthen the opening hook with a sharper curiosity gap or interrupt.",
    "specificity": "Add concrete details, numbers, or a sensory anchor to reduce vagueness.",
    "retention_architecture": "Add pattern breaks and tighter beat spacing across the retention map.",
    "emotional_intensity_curve": "Increase emotional variance and peak intensity across story beats.",
    "platform_fit": "Adjust duration, pacing, and format choices for the target platform.",
    "loop_potential": "Add a loop or replay hook that invites comments, saves, or rewatch.",
    "uniqueness": "Change topic angle, hook structure, or story twist to reduce similarity.",
}

CRITICAL_DIMENSIONS = {
    "hook_strength",
    "retention_architecture",
    "uniqueness",
}


class ContentDecision(str, Enum):
    PROCEED = "PROCEED"
    REVISE = "REVISE"
    REGENERATE = "REGENERATE"
    REJECT = "REJECT"


@dataclass
class DecisionPackage:
    decision: ContentDecision
    confidence: float
    reasons: list[str] = field(default_factory=list)
    weak_dimensions: list[str] = field(default_factory=list)
    revision_targets: list[str] = field(default_factory=list)
    regeneration_required: bool = False
    priority_fixes: list[str] = field(default_factory=list)
    production_ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "confidence": round(self.confidence, 4),
            "reasons": list(self.reasons),
            "weak_dimensions": list(self.weak_dimensions),
            "revision_targets": list(self.revision_targets),
            "regeneration_required": self.regeneration_required,
            "priority_fixes": list(self.priority_fixes),
            "production_ready": self.production_ready,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionPackage:
        if not isinstance(data, dict):
            raise ValueError("DecisionPackage.from_dict() expects a dict.")

        return cls(
            decision=ContentDecision(str(data.get("decision", ContentDecision.REJECT.value))),
            confidence=float(data.get("confidence", 0.0)),
            reasons=list(data.get("reasons", [])),
            weak_dimensions=list(data.get("weak_dimensions", [])),
            revision_targets=list(data.get("revision_targets", [])),
            regeneration_required=bool(data.get("regeneration_required", False)),
            priority_fixes=list(data.get("priority_fixes", [])),
            production_ready=bool(data.get("production_ready", False)),
        )


@dataclass
class ContentDecisionResult:
    package: DecisionPackage
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package.to_dict(),
            "reasoning": self.reasoning,
        }


class ContentDecisionEngine:
    """
    Decide the next production action from viral scoring and upstream artifacts.

    Usage:
        engine = ContentDecisionEngine()
        result = engine.decide(
            viral_scorecard=scorecard,
            uniqueness_report=uniqueness_report,
            retention_map=retention_map,
            story_blueprint=story_blueprint,
            hook_package=hook_package,
        )
    """

    REJECT_COMPOSITE_THRESHOLD = 50.0
    REGENERATE_UNIQUENESS_SCORE = 55.0
    REJECT_UNIQUENESS_SCORE = 40.0
    REJECT_SIMILARITY_THRESHOLD = 0.85

    def decide(
        self,
        viral_scorecard: ViralScorecard,
        uniqueness_report: UniquenessReport,
        retention_map: RetentionMap,
        story_blueprint: StoryBlueprint,
        hook_package: HookPackage,
        dimension_minimums: Optional[dict[str, float]] = None,
    ) -> ContentDecisionResult:
        minimums = dict(DEFAULT_DIMENSION_MINIMUMS)
        if dimension_minimums:
            minimums.update(dimension_minimums)

        dimension_map = {item.name: item for item in viral_scorecard.dimensions}
        weak_dimensions = self._find_weak_dimensions(dimension_map, minimums)
        weak_dimensions = self._enrich_weak_dimensions(
            weak_dimensions=weak_dimensions,
            hook_package=hook_package,
            retention_map=retention_map,
            story_blueprint=story_blueprint,
            minimums=minimums,
        )
        critical_weaknesses = [
            name for name in weak_dimensions if name in CRITICAL_DIMENSIONS
        ]

        reasons: list[str] = []
        revision_targets: list[str] = []
        priority_fixes: list[str] = []

        if not uniqueness_report.passed:
            decision, confidence = self._decide_uniqueness_failure(uniqueness_report, reasons)
            regeneration_required = decision == ContentDecision.REGENERATE
            production_ready = decision == ContentDecision.PROCEED

            package = DecisionPackage(
                decision=decision,
                confidence=confidence,
                reasons=reasons,
                weak_dimensions=["uniqueness"],
                revision_targets=["hook", "story_beats", "trend_context"],
                regeneration_required=regeneration_required,
                priority_fixes=[
                    uniqueness_report.regeneration_directive.strip()
                    or DIMENSION_PRIORITY_FIXES["uniqueness"]
                ],
                production_ready=production_ready,
            )
            return ContentDecisionResult(
                package=package,
                reasoning=self._build_reasoning(package),
            )

        if self._should_reject(viral_scorecard, weak_dimensions, reasons):
            package = DecisionPackage(
                decision=ContentDecision.REJECT,
                confidence=0.92,
                reasons=reasons,
                weak_dimensions=weak_dimensions,
                revision_targets=[],
                regeneration_required=False,
                priority_fixes=["Discard this brief and start a new concept."],
                production_ready=False,
            )
            return ContentDecisionResult(
                package=package,
                reasoning=self._build_reasoning(package),
            )

        if self._should_proceed(viral_scorecard, weak_dimensions, reasons):
            package = DecisionPackage(
                decision=ContentDecision.PROCEED,
                confidence=self._confidence_for_proceed(viral_scorecard),
                reasons=reasons,
                weak_dimensions=[],
                revision_targets=[],
                regeneration_required=False,
                priority_fixes=[],
                production_ready=True,
            )
            return ContentDecisionResult(
                package=package,
                reasoning=self._build_reasoning(package),
            )

        if self._should_regenerate(viral_scorecard, weak_dimensions, critical_weaknesses, reasons):
            revision_targets = self._collect_revision_targets(weak_dimensions)
            priority_fixes = self._collect_priority_fixes(weak_dimensions)
            package = DecisionPackage(
                decision=ContentDecision.REGENERATE,
                confidence=0.78,
                reasons=reasons,
                weak_dimensions=weak_dimensions,
                revision_targets=revision_targets,
                regeneration_required=True,
                priority_fixes=priority_fixes,
                production_ready=False,
            )
            return ContentDecisionResult(
                package=package,
                reasoning=self._build_reasoning(package),
            )

        revision_targets = self._collect_revision_targets(weak_dimensions)
        priority_fixes = self._collect_priority_fixes(weak_dimensions)
        reasons.extend(self._build_revision_reasons(weak_dimensions, dimension_map, minimums))

        package = DecisionPackage(
            decision=ContentDecision.REVISE,
            confidence=self._confidence_for_revise(weak_dimensions, viral_scorecard),
            reasons=reasons,
            weak_dimensions=weak_dimensions,
            revision_targets=revision_targets,
            regeneration_required=False,
            priority_fixes=priority_fixes,
            production_ready=False,
        )
        return ContentDecisionResult(
            package=package,
            reasoning=self._build_reasoning(package),
        )

    def decide_package(
        self,
        viral_scorecard: ViralScorecard,
        uniqueness_report: UniquenessReport,
        retention_map: RetentionMap,
        story_blueprint: StoryBlueprint,
        hook_package: HookPackage,
        dimension_minimums: Optional[dict[str, float]] = None,
    ) -> DecisionPackage:
        return self.decide(
            viral_scorecard=viral_scorecard,
            uniqueness_report=uniqueness_report,
            retention_map=retention_map,
            story_blueprint=story_blueprint,
            hook_package=hook_package,
            dimension_minimums=dimension_minimums,
        ).package

    def _find_weak_dimensions(
        self,
        dimension_map: dict[str, Any],
        minimums: dict[str, float],
    ) -> list[str]:
        weak: list[tuple[int, str, float]] = []

        for name, minimum in minimums.items():
            dimension = dimension_map.get(name)
            if dimension is None:
                continue
            gap = minimum - dimension.score
            if gap > 0:
                weak.append((gap, name, dimension.score))

        weak.sort(key=lambda item: (-item[0], item[1]))
        return [name for _, name, _ in weak]

    def _enrich_weak_dimensions(
        self,
        weak_dimensions: list[str],
        hook_package: HookPackage,
        retention_map: RetentionMap,
        story_blueprint: StoryBlueprint,
        minimums: dict[str, float],
    ) -> list[str]:
        enriched = list(weak_dimensions)

        if (
            hook_package.composite_score < minimums.get("hook_strength", 65.0)
            or not hook_package.best_hook_text.strip()
        ) and "hook_strength" not in enriched:
            enriched.insert(0, "hook_strength")

        if (
            retention_map.retention_score_estimate < minimums.get("retention_architecture", 65.0)
            or len(retention_map.beats) < 3
        ) and "retention_architecture" not in enriched:
            enriched.append("retention_architecture")

        loop_dimension_weak = "loop_potential" in weak_dimensions
        if loop_dimension_weak or (
            not story_blueprint.loop_seed.strip()
            and not retention_map.loop_seed_present
        ):
            if "loop_potential" not in enriched:
                enriched.append("loop_potential")

        return enriched

    def _decide_uniqueness_failure(
        self,
        uniqueness_report: UniquenessReport,
        reasons: list[str],
    ) -> tuple[ContentDecision, float]:
        if (
            uniqueness_report.uniqueness_score <= self.REJECT_UNIQUENESS_SCORE
            or uniqueness_report.max_similarity >= self.REJECT_SIMILARITY_THRESHOLD
        ):
            reasons.append(
                "Uniqueness failed with critically high similarity or very low uniqueness score."
            )
            return ContentDecision.REJECT, 0.9

        reasons.append("Uniqueness gate failed; content is too similar to recent output.")
        if uniqueness_report.uniqueness_score <= self.REGENERATE_UNIQUENESS_SCORE:
            reasons.append("Similarity is broad enough that a full regeneration is safer than a patch.")
            return ContentDecision.REGENERATE, 0.82

        reasons.append("Targeted regeneration is recommended before production.")
        return ContentDecision.REGENERATE, 0.76

    def _should_reject(
        self,
        viral_scorecard: ViralScorecard,
        weak_dimensions: list[str],
        reasons: list[str],
    ) -> bool:
        if viral_scorecard.composite_score <= self.REJECT_COMPOSITE_THRESHOLD:
            reasons.append(
                f"Composite viral score {viral_scorecard.composite_score:.1f} is below the "
                f"reject threshold ({self.REJECT_COMPOSITE_THRESHOLD:.1f})."
            )
            return True

        if (
            viral_scorecard.production_tier == ProductionTier.F
            and viral_scorecard.composite_score < viral_scorecard.minimum_gate_score
        ):
            reasons.append(
                f"Production tier {viral_scorecard.production_tier.value} with composite "
                f"{viral_scorecard.composite_score:.1f} is not recoverable by revision."
            )
            return True

        critical_failures = [name for name in weak_dimensions if name in CRITICAL_DIMENSIONS]
        if len(critical_failures) >= 2 and viral_scorecard.composite_score < viral_scorecard.minimum_gate_score:
            reasons.append(
                "Multiple critical dimensions failed while the composite score remains below gate minimum."
            )
            return True

        return False

    def _should_proceed(
        self,
        viral_scorecard: ViralScorecard,
        weak_dimensions: list[str],
        reasons: list[str],
    ) -> bool:
        if weak_dimensions:
            return False

        if viral_scorecard.production_tier not in {ProductionTier.S, ProductionTier.A}:
            return False

        if not viral_scorecard.passed_gate:
            return False

        reasons.append(
            f"Viral tier {viral_scorecard.production_tier.value} with composite "
            f"{viral_scorecard.composite_score:.1f} and no critical weaknesses."
        )
        return True

    def _should_regenerate(
        self,
        viral_scorecard: ViralScorecard,
        weak_dimensions: list[str],
        critical_weaknesses: list[str],
        reasons: list[str],
    ) -> bool:
        if len(weak_dimensions) >= 4:
            reasons.append("Too many weak dimensions for a narrow revision pass.")
            return True

        if len(critical_weaknesses) >= 2:
            reasons.append("Multiple critical dimensions need more than a single-target revision.")
            return True

        if (
            "uniqueness" in weak_dimensions
            and viral_scorecard.composite_score < viral_scorecard.minimum_gate_score
        ):
            reasons.append("Uniqueness and composite score both need a fresh concept pass.")
            return True

        return False

    def _collect_revision_targets(self, weak_dimensions: list[str]) -> list[str]:
        targets: list[str] = []
        for name in weak_dimensions:
            for target in DIMENSION_REVISION_TARGETS.get(name, []):
                if target not in targets:
                    targets.append(target)
        return targets

    def _collect_priority_fixes(self, weak_dimensions: list[str]) -> list[str]:
        fixes: list[str] = []
        for name in weak_dimensions:
            fix = DIMENSION_PRIORITY_FIXES.get(name)
            if fix and fix not in fixes:
                fixes.append(fix)
        return fixes

    def _build_revision_reasons(
        self,
        weak_dimensions: list[str],
        dimension_map: dict[str, Any],
        minimums: dict[str, float],
    ) -> list[str]:
        reasons: list[str] = []
        for name in weak_dimensions:
            dimension = dimension_map.get(name)
            minimum = minimums.get(name, 0.0)
            if dimension is None:
                continue
            reasons.append(
                f"{name} scored {dimension.score:.1f}, below minimum {minimum:.1f}."
            )
        return reasons

    def _confidence_for_proceed(self, viral_scorecard: ViralScorecard) -> float:
        if viral_scorecard.production_tier == ProductionTier.S:
            return 0.95
        if viral_scorecard.composite_score >= 80.0:
            return 0.9
        return 0.84

    def _confidence_for_revise(
        self,
        weak_dimensions: list[str],
        viral_scorecard: ViralScorecard,
    ) -> float:
        base = 0.72
        if len(weak_dimensions) == 1:
            base += 0.08
        if viral_scorecard.composite_score >= viral_scorecard.minimum_gate_score:
            base += 0.05
        return min(0.88, base)

    def _build_reasoning(self, package: DecisionPackage) -> str:
        target_clause = ""
        if package.revision_targets:
            target_clause = f" Targets: {', '.join(package.revision_targets)}."
        return (
            f"Decision {package.decision.value} with confidence {package.confidence:.2f}. "
            f"Production ready: {package.production_ready}.{target_clause}"
        )


__all__ = [
    "ContentDecision",
    "ContentDecisionEngine",
    "ContentDecisionResult",
    "DecisionPackage",
]


if __name__ == "__main__":
    import json
    import tempfile
    from pathlib import Path

    from content_brain.engines.hook_engineering_engine import HookEngineeringEngine
    from content_brain.engines.retention_map_engine import RetentionMapEngine
    from content_brain.engines.story_architecture_engine import StoryArchitectureEngine
    from content_brain.engines.trend_discovery_engine import TrendDiscoveryEngine
    from content_brain.engines.uniqueness_engine import UniquenessEngine
    from content_brain.engines.video_format_planner import VideoFormatPlanner
    from content_brain.engines.viral_scoring_engine import ViralScoringEngine
    from content_brain.profiles.profile_loader import ProfileLoader
    from content_brain.schemas.content_brief import (
        HookClass,
        HookVariant,
        Platform,
        RetentionBeat,
        ScoreDimension,
        StoryBeat,
        StoryMode,
        UniquenessLayer,
    )

    loader = ProfileLoader()
    trend_engine = TrendDiscoveryEngine()
    hook_engine = HookEngineeringEngine()
    story_engine = StoryArchitectureEngine()
    format_planner = VideoFormatPlanner()
    retention_engine = RetentionMapEngine()
    scoring_engine = ViralScoringEngine()
    decision_engine = ContentDecisionEngine()

    cases = [
        ("football", 30, "hailuo", 6),
        ("perfume", 30, "hailuo", 8),
        ("dark_mystery", 45, "runway", 10),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        memory_path = Path(tmp_dir) / "content_history.json"
        uniqueness_engine = UniquenessEngine(memory_path=memory_path)

        for niche, duration, provider, clip_duration in cases:
            profile = loader.resolve(niche=niche)
            thresholds = profile.get("scoring_thresholds", {})
            dimension_minimums = thresholds.get("dimension_minimums")

            trend = trend_engine.discover_best_signal(
                profile,
                niche=niche,
                topic=f"{niche} decision engine test",
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
            scorecard = scoring_engine.score_brief(
                profile=profile,
                trend_signal=trend,
                hook_package=hooks,
                story_blueprint=story,
                retention_map=retention.retention_map,
                uniqueness_report=uniqueness.report,
            )
            decision = decision_engine.decide(
                viral_scorecard=scorecard,
                uniqueness_report=uniqueness.report,
                retention_map=retention.retention_map,
                story_blueprint=story,
                hook_package=hooks,
                dimension_minimums=dimension_minimums,
            )

            payload = decision.package.to_dict()
            roundtrip = DecisionPackage.from_dict(payload)

            print("\n" + "=" * 72)
            print(
                f"{niche.upper()} | {decision.package.decision.value} | "
                f"confidence {decision.package.confidence:.2f} | "
                f"ready {decision.package.production_ready}"
            )
            print("REASONS:", "; ".join(decision.package.reasons) or "none")
            print("WEAK:", ", ".join(decision.package.weak_dimensions) or "none")
            print("TARGETS:", ", ".join(decision.package.revision_targets) or "none")
            print("FIXES:", "; ".join(decision.package.priority_fixes) or "none")
            print("JSON OK:", json.dumps(payload)[:120] + "...")
            print("ROUNDTRIP:", roundtrip.decision.value)

    def _demo_scorecard(
        composite: float,
        tier: ProductionTier,
        scores: dict[str, float],
        passed_gate: bool = True,
    ) -> ViralScorecard:
        weights = {
            "hook_strength": 0.2,
            "retention_architecture": 0.25,
            "emotional_intensity_curve": 0.15,
            "specificity": 0.1,
            "uniqueness": 0.15,
            "platform_fit": 0.1,
            "loop_potential": 0.05,
        }
        return ViralScorecard(
            dimensions=[
                ScoreDimension(name=name, score=score, weight=weights[name])
                for name, score in scores.items()
            ],
            composite_score=composite,
            production_tier=tier,
            passed_gate=passed_gate,
            minimum_gate_score=65.0,
        )

    def _demo_story(loop_seed: str = "") -> StoryBlueprint:
        return StoryBlueprint(
            story_mode=StoryMode.CONFESSION,
            beats=[
                StoryBeat(
                    beat_id="HOOK_BEAT",
                    act=1,
                    start_second=0.0,
                    end_second=3.0,
                    description="PURPOSE: Hook",
                    emotional_tone="hook (0.80)",
                    retention_mechanic="pattern_interrupt",
                )
            ],
            reveal_type="comparison_reveal",
            loop_seed=loop_seed,
            total_duration_seconds=30,
        )

    def _demo_hooks(score: float) -> HookPackage:
        return HookPackage(
            variants=[
                HookVariant(
                    variant_id="hook_1",
                    hook_class=HookClass.INCOMPLETE_TRUTH,
                    text="Sample hook text for decision testing.",
                    specificity_score=score,
                )
            ],
            selected_variant_id="hook_1",
            best_hook_text="Sample hook text for decision testing.",
            hook_class=HookClass.INCOMPLETE_TRUTH,
            composite_score=score,
        )

    def _demo_retention(score: float, loop_present: bool = False) -> RetentionMap:
        return RetentionMap(
            beats=[
                RetentionBeat(
                    block_label="HOOK",
                    start_second=0.0,
                    end_second=3.0,
                    mechanic="pattern_interrupt",
                    implementation_note="Open strong.",
                )
            ],
            retention_score_estimate=score,
            loop_seed_present=loop_present,
        )

    edge_cases = [
        (
            "REVISE hook",
            _demo_scorecard(
                68.0,
                ProductionTier.B,
                {
                    "hook_strength": 58.0,
                    "retention_architecture": 72.0,
                    "emotional_intensity_curve": 62.0,
                    "specificity": 64.0,
                    "uniqueness": 70.0,
                    "platform_fit": 68.0,
                    "loop_potential": 60.0,
                },
                passed_gate=False,
            ),
            UniquenessReport(passed=True, layers=[], max_similarity=0.2, uniqueness_score=78.0),
            _demo_hooks(58.0),
            RetentionMap(
                beats=[
                    RetentionBeat(
                        block_label=f"BEAT_{index}",
                        start_second=float(index * 3),
                        end_second=float(index * 3 + 3),
                        mechanic="pattern_interrupt",
                        implementation_note="Beat present.",
                    )
                    for index in range(4)
                ],
                retention_score_estimate=72.0,
                loop_seed_present=True,
            ),
            _demo_story(loop_seed="What did the replay miss?"),
        ),
        (
            "REGENERATE uniqueness",
            _demo_scorecard(
                62.0,
                ProductionTier.B,
                {
                    "hook_strength": 66.0,
                    "retention_architecture": 67.0,
                    "emotional_intensity_curve": 58.0,
                    "specificity": 62.0,
                    "uniqueness": 52.0,
                    "platform_fit": 60.0,
                    "loop_potential": 50.0,
                },
                passed_gate=False,
            ),
            UniquenessReport(
                passed=False,
                layers=[
                    UniquenessLayer(
                        layer_name="hook_fingerprint",
                        similarity_score=0.74,
                        threshold=0.68,
                        passed=False,
                    )
                ],
                max_similarity=0.74,
                uniqueness_score=52.0,
                regeneration_directive="hook_collision",
            ),
        ),
        (
            "REJECT low score",
            _demo_scorecard(
                42.0,
                ProductionTier.F,
                {
                    "hook_strength": 40.0,
                    "retention_architecture": 38.0,
                    "emotional_intensity_curve": 35.0,
                    "specificity": 42.0,
                    "uniqueness": 45.0,
                    "platform_fit": 40.0,
                    "loop_potential": 30.0,
                },
                passed_gate=False,
            ),
            UniquenessReport(passed=True, layers=[], max_similarity=0.3, uniqueness_score=55.0),
        ),
    ]

    print("\n" + "#" * 72)
    print("EDGE CASES")
    for label, scorecard, uniqueness, *artifacts in edge_cases:
        hooks = artifacts[0] if artifacts else _demo_hooks(scorecard.dimensions[0].score)
        retention = (
            artifacts[1]
            if len(artifacts) > 1
            else _demo_retention(
                next(item.score for item in scorecard.dimensions if item.name == "retention_architecture"),
                loop_present=scorecard.dimensions[-1].score >= 50,
            )
        )
        story = (
            artifacts[2]
            if len(artifacts) > 2
            else _demo_story(
                loop_seed="What happened after the replay?"
                if scorecard.dimensions[-1].score >= 50
                else ""
            )
        )
        decision = decision_engine.decide(
            viral_scorecard=scorecard,
            uniqueness_report=uniqueness,
            retention_map=retention,
            story_blueprint=story,
            hook_package=hooks,
        )
        print("\n" + "-" * 72)
        print(f"{label} -> {decision.package.decision.value}")
        print("TARGETS:", ", ".join(decision.package.revision_targets) or "none")
        print("FIXES:", "; ".join(decision.package.priority_fixes) or "none")
