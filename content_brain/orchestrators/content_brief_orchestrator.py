"""
Content Brief Orchestrator V1 for the Viral Content Brain.

Wires the completed profile-driven pipeline into one orchestrator-ready module.
Rule-based only in V1 (no LLM, no external APIs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json

from content_brain.profiles.profile_loader import ProfileLoader
from content_brain.schemas.content_brief import (
    HookPackage,
    Platform,
    RetentionMap,
    StoryBlueprint,
    TrendSignal,
    UniquenessReport,
    ViralScorecard,
    generate_brief_id,
)

try:
    from content_brain.profiles.channel_identity_store import ChannelIdentityStore
except ImportError:  # pragma: no cover - defensive fallback
    ChannelIdentityStore = None  # type: ignore[assignment,misc]

try:
    from content_brain.engines.content_decision_engine import (
        ContentDecision,
        ContentDecisionEngine,
        DecisionPackage,
    )
except ImportError as exc:  # pragma: no cover - defensive fallback
    raise ImportError(
        "ContentBriefOrchestrator requires content_brain.engines.content_decision_engine."
    ) from exc

try:
    from content_brain.engines.hook_engineering_engine import HookEngineeringEngine
    from content_brain.engines.retention_map_engine import RetentionMapEngine
    from content_brain.engines.story_architecture_engine import StoryArchitectureEngine
    from content_brain.engines.title_thumbnail_engine import (
        TitleThumbnailEngine,
        TitleThumbnailPackage,
    )
    from content_brain.engines.trend_discovery_engine import TrendDiscoveryEngine
    from content_brain.engines.uniqueness_engine import UniquenessEngine
    from content_brain.engines.video_format_planner import VideoFormatPlan, VideoFormatPlanner
    from content_brain.engines.viral_scoring_engine import ViralScoringEngine
except ImportError as exc:  # pragma: no cover - defensive fallback
    raise ImportError(
        "ContentBriefOrchestrator requires the Content Brain engine modules."
    ) from exc

try:
    from content_brain.engines.story_intelligence_engine import StoryIntelligenceEngine
except ImportError:  # pragma: no cover - optional Phase 9A layer
    StoryIntelligenceEngine = None  # type: ignore[assignment,misc]

try:
    from content_brain.engines.story_memory_engine import StoryMemoryEngine
except ImportError:  # pragma: no cover - optional Phase 9B layer
    StoryMemoryEngine = None  # type: ignore[assignment,misc]


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

NEXT_ACTION_BY_DECISION = {
    ContentDecision.PROCEED: "proceed_to_title_thumbnail",
    ContentDecision.REVISE: "revise_targets",
    ContentDecision.REGENERATE: "regenerate_concept",
    ContentDecision.REJECT: "discard_brief",
}


class ContentBriefOrchestratorError(Exception):
    """Raised when the content brief pipeline cannot complete."""


@dataclass
class ContentBriefRunRequest:
    niche: str = "general"
    topic: str = ""
    platform: Platform | str = Platform.TIKTOK
    user_duration_seconds: Optional[int] = 30
    provider_name: Optional[str] = None
    provider_clip_duration_seconds: Optional[int] = None
    profile_name: Optional[str] = None
    channel_id: Optional[str] = None
    record_uniqueness_on_success: bool = True
    record_story_memory_on_success: bool = True


@dataclass
class ContentBriefResult:
    profile: dict[str, Any]
    trend_signal: TrendSignal
    hook_package: HookPackage
    video_format_plan: VideoFormatPlan
    story_blueprint: StoryBlueprint
    retention_map: RetentionMap
    uniqueness_report: UniquenessReport
    viral_scorecard: ViralScorecard
    decision_package: DecisionPackage
    title_thumbnail_package: TitleThumbnailPackage
    production_ready: bool
    next_action: str
    brief_id: str = ""
    run_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief_id": self.brief_id,
            "profile": self.profile,
            "trend_signal": self.trend_signal.to_dict(),
            "hook_package": self.hook_package.to_dict(),
            "video_format_plan": self.video_format_plan.to_dict(),
            "story_blueprint": self.story_blueprint.to_dict(),
            "retention_map": self.retention_map.to_dict(),
            "uniqueness_report": self.uniqueness_report.to_dict(),
            "viral_scorecard": self.viral_scorecard.to_dict(),
            "decision_package": self.decision_package.to_dict(),
            "title_thumbnail_package": self.title_thumbnail_package.to_dict(),
            "production_ready": self.production_ready,
            "next_action": self.next_action,
            "run_context": dict(self.run_context),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentBriefResult:
        if not isinstance(data, dict):
            raise ValueError("ContentBriefResult.from_dict() expects a dict.")

        decision_payload = data.get("decision_package", {})
        title_thumbnail_payload = data.get("title_thumbnail_package", {})
        return cls(
            brief_id=str(data.get("brief_id", "")),
            profile=dict(data.get("profile", {})),
            trend_signal=TrendSignal.from_dict(data["trend_signal"]),
            hook_package=HookPackage.from_dict(data["hook_package"]),
            video_format_plan=_video_format_plan_from_dict(data["video_format_plan"]),
            story_blueprint=StoryBlueprint.from_dict(data["story_blueprint"]),
            retention_map=RetentionMap.from_dict(data["retention_map"]),
            uniqueness_report=UniquenessReport.from_dict(data["uniqueness_report"]),
            viral_scorecard=ViralScorecard.from_dict(data["viral_scorecard"]),
            decision_package=DecisionPackage.from_dict(decision_payload),
            title_thumbnail_package=TitleThumbnailPackage.from_dict(title_thumbnail_payload),
            production_ready=bool(data.get("production_ready", False)),
            next_action=str(data.get("next_action", "")),
            run_context=dict(data.get("run_context", {})),
        )


class ContentBriefOrchestrator:
    """
    Run the full Viral Content Brain pipeline and return one JSON-safe result.

    Pipeline:
        Profile
        -> TrendDiscoveryEngine
        -> HookEngineeringEngine
        -> VideoFormatPlanner
        -> StoryArchitectureEngine
        -> RetentionMapEngine
        -> UniquenessEngine
        -> ViralScoringEngine
        -> ContentDecisionEngine
        -> TitleThumbnailEngine
    """

    def __init__(
        self,
        project_root: str | Path = ".",
        memory_path: str | Path | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.profile_loader = ProfileLoader(self.project_root)
        self.channel_store = (
            ChannelIdentityStore(self.project_root)
            if ChannelIdentityStore is not None
            else None
        )
        self.trend_engine = TrendDiscoveryEngine(self.project_root)
        self.hook_engine = HookEngineeringEngine()
        self.format_planner = VideoFormatPlanner()
        self.story_engine = StoryArchitectureEngine()
        self.retention_engine = RetentionMapEngine()
        self.uniqueness_engine = UniquenessEngine(memory_path=memory_path)
        self.scoring_engine = ViralScoringEngine()
        self.decision_engine = ContentDecisionEngine()
        self.title_thumbnail_engine = TitleThumbnailEngine()
        self.story_memory_engine = (
            StoryMemoryEngine() if StoryMemoryEngine is not None else None
        )
        self.story_intelligence_engine = (
            StoryIntelligenceEngine(memory_engine=self.story_memory_engine)
            if StoryIntelligenceEngine is not None
            else None
        )

    def run(self, request: ContentBriefRunRequest | None = None) -> ContentBriefResult:
        request = request or ContentBriefRunRequest()
        brief_id = generate_brief_id()
        started_at = datetime.now().strftime(TIMESTAMP_FORMAT)

        channel_identity, channel_identity_applied = self._load_channel_identity(
            request.channel_id
        )
        effective = self._apply_channel_defaults(request, channel_identity)

        if channel_identity_applied and channel_identity is not None:
            profile = self.profile_loader.resolve_from_channel_identity(channel_identity)
        else:
            profile = self.profile_loader.resolve(
                niche=effective["niche"],
                profile_name=request.profile_name,
            )

        resolved_niche = str(profile.get("niche", effective["niche"] or "general"))
        resolved_platform = self._resolve_platform(effective["platform"])
        user_topic = str(effective["topic"])
        user_topic_explicit = bool(user_topic.strip())
        trend_query_topic = user_topic.strip() if user_topic_explicit else ""

        trend_signal = self.trend_engine.discover_best_signal(
            profile=profile,
            niche=resolved_niche,
            topic=trend_query_topic,
        )
        if trend_signal is None:
            raise ContentBriefOrchestratorError(
                f"No trend signal could be resolved for niche {resolved_niche!r}."
            )

        if user_topic_explicit:
            trend_signal = self._preserve_user_topic(trend_signal, user_topic.strip())

        pipeline_topic = user_topic.strip() if user_topic_explicit else trend_signal.topic
        resolved_channel_id = (
            channel_identity.channel_id if channel_identity is not None else ""
        )

        hook_package = self.hook_engine.generate_hook_package(
            profile=profile,
            topic=pipeline_topic,
            platforms=[resolved_platform],
        )
        if not hook_package.variants:
            raise ContentBriefOrchestratorError(
                f"No hook variants generated for topic {pipeline_topic!r}."
            )

        provider_name = self._resolve_provider_name(profile, effective["provider_name"])
        video_format_plan = self.format_planner.plan(
            profile=profile,
            platform=resolved_platform,
            user_duration_seconds=effective["user_duration_seconds"],
            provider_name=provider_name,
            provider_clip_duration_seconds=request.provider_clip_duration_seconds,
        )

        story_blueprint = self.story_engine.build_blueprint(
            profile=profile,
            trend_signal=self._with_pipeline_topic(trend_signal, pipeline_topic),
            hook_package=hook_package,
        )
        story_blueprint.total_duration_seconds = video_format_plan.target_duration_seconds

        story_intelligence_payload = self._maybe_enhance_story_intelligence(
            profile=profile,
            trend_signal=self._with_pipeline_topic(trend_signal, pipeline_topic),
            hook_package=hook_package,
            story_blueprint=story_blueprint,
            video_format_plan=video_format_plan,
            channel_id=resolved_channel_id,
        )

        retention_result = self.retention_engine.build(
            profile=profile,
            story_blueprint=story_blueprint,
            format_plan=video_format_plan,
        )
        retention_map = retention_result.retention_map

        uniqueness_result = self.uniqueness_engine.evaluate(
            profile=profile,
            trend_signal=trend_signal,
            hook_package=hook_package,
            story_blueprint=story_blueprint,
        )
        uniqueness_report = uniqueness_result.report

        dimension_minimums = profile.get("scoring_thresholds", {}).get("dimension_minimums")
        viral_scorecard = self.scoring_engine.score_brief(
            profile=profile,
            trend_signal=trend_signal,
            hook_package=hook_package,
            story_blueprint=story_blueprint,
            retention_map=retention_map,
            uniqueness_report=uniqueness_report,
        )

        decision_package = self.decision_engine.decide_package(
            viral_scorecard=viral_scorecard,
            uniqueness_report=uniqueness_report,
            retention_map=retention_map,
            story_blueprint=story_blueprint,
            hook_package=hook_package,
            dimension_minimums=dimension_minimums,
        )

        title_thumbnail_package = self.title_thumbnail_engine.generate_package(
            profile=profile,
            decision_package=decision_package,
            story_blueprint=story_blueprint,
            hook_package=hook_package,
            trend_signal=self._with_pipeline_topic(trend_signal, pipeline_topic),
            platform=resolved_platform,
        )

        production_ready = bool(decision_package.production_ready)
        next_action = self._build_next_action(decision_package)

        if (
            request.record_uniqueness_on_success
            and production_ready
            and uniqueness_report.passed
        ):
            self.uniqueness_engine.record(uniqueness_result.fingerprint)

        if (
            request.record_story_memory_on_success
            and production_ready
            and decision_package.decision == ContentDecision.PROCEED
            and story_intelligence_payload is not None
            and self.story_memory_engine is not None
        ):
            try:
                self.story_memory_engine.record(
                    story_intelligence_payload,
                    profile,
                    brief_id=brief_id,
                    channel_id=resolved_channel_id,
                    topic=pipeline_topic,
                )
            except Exception:
                pass

        completed_at = datetime.now().strftime(TIMESTAMP_FORMAT)
        run_context = {
            "brief_id": brief_id,
            "niche": resolved_niche,
            "topic": pipeline_topic,
            "user_topic": user_topic.strip() if user_topic_explicit else "",
            "user_topic_authoritative": user_topic_explicit,
            "platform": resolved_platform.value,
            "provider_name": provider_name,
            "channel_id": resolved_channel_id,
            "channel_name": (
                channel_identity.channel_name.strip()
                if channel_identity is not None
                else ""
            ),
            "channel_identity_applied": channel_identity_applied,
            "pipeline_version": "content_brief_orchestrator_v1",
            "started_at": started_at,
            "completed_at": completed_at,
            "decision": decision_package.decision.value,
            "composite_score": viral_scorecard.composite_score,
            "production_tier": viral_scorecard.production_tier.value,
            "recommended_title": title_thumbnail_package.recommended_title,
            "packaging_warning_count": len(title_thumbnail_package.warnings),
            "story_intelligence_applied": story_intelligence_payload is not None,
        }
        if story_intelligence_payload is not None:
            run_context["story_intelligence"] = story_intelligence_payload
            quality = story_intelligence_payload.get("story_blueprint", {}).get(
                "story_quality_score", {}
            )
            run_context["story_intelligence_composite_score"] = quality.get("composite")
            memory = story_intelligence_payload.get("memory", {})
            run_context["story_memory_decision"] = memory.get("memory_decision")
            run_context["story_memory_repeated_risk_score"] = memory.get(
                "repeated_risk_score"
            )
            run_context["story_memory_recent_score"] = memory.get(
                "recent_repetition_score"
            )
            run_context["story_memory_lifetime_score"] = memory.get(
                "lifetime_repetition_score"
            )

        return ContentBriefResult(
            brief_id=brief_id,
            profile=profile,
            trend_signal=self._with_pipeline_topic(trend_signal, pipeline_topic),
            hook_package=hook_package,
            video_format_plan=video_format_plan,
            story_blueprint=story_blueprint,
            retention_map=retention_map,
            uniqueness_report=uniqueness_report,
            viral_scorecard=viral_scorecard,
            decision_package=decision_package,
            title_thumbnail_package=title_thumbnail_package,
            production_ready=production_ready,
            next_action=next_action,
            run_context=run_context,
        )

    def run_to_dict(self, request: ContentBriefRunRequest | None = None) -> dict[str, Any]:
        return self.run(request=request).to_dict()

    def _load_channel_identity(
        self,
        channel_id: Optional[str],
    ) -> tuple[Any | None, bool]:
        cleaned = str(channel_id or "").strip()
        if not cleaned:
            return None, False

        if self.channel_store is None:
            raise ContentBriefOrchestratorError(
                "Channel identity support requires content_brain.profiles.channel_identity_store."
            )

        try:
            channel = self.channel_store.load(cleaned)
        except Exception as exc:
            raise ContentBriefOrchestratorError(
                f"Could not load channel identity {cleaned!r}: {exc}"
            ) from exc

        return channel, True

    def _apply_channel_defaults(
        self,
        request: ContentBriefRunRequest,
        channel_identity: Any | None,
    ) -> dict[str, Any]:
        niche = request.niche.strip()
        topic = request.topic.strip()
        platform = request.platform
        provider_name = request.provider_name
        user_duration_seconds = request.user_duration_seconds

        if channel_identity is not None:
            overrides = channel_identity.to_run_request_overrides(topic=topic)

            if not niche or niche == "general":
                niche = str(overrides.get("niche") or niche or "general")

            if not provider_name or not str(provider_name).strip():
                provider_name = str(overrides.get("provider_name") or "hailuo")

            if user_duration_seconds is None:
                user_duration_seconds = int(
                    overrides.get("user_duration_seconds") or 30
                )

            platform = overrides.get("platform") or platform

        return {
            "niche": niche or "general",
            "topic": topic,
            "platform": platform,
            "provider_name": provider_name,
            "user_duration_seconds": user_duration_seconds,
        }

    def _maybe_enhance_story_intelligence(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
        video_format_plan: VideoFormatPlan,
        channel_id: str = "",
    ) -> dict[str, Any] | None:
        if self.story_intelligence_engine is None:
            return None

        try:
            return self.story_intelligence_engine.enhance(
                profile=profile,
                trend_signal=trend_signal,
                hook_package=hook_package,
                story_blueprint=story_blueprint,
                video_format_plan=video_format_plan,
                channel_id=channel_id,
            )
        except Exception:
            return None

    def _preserve_user_topic(
        self,
        trend_signal: TrendSignal,
        authoritative_topic: str,
    ) -> TrendSignal:
        return TrendSignal(
            topic=authoritative_topic,
            velocity=trend_signal.velocity,
            saturation=trend_signal.saturation,
            virality_score=trend_signal.virality_score,
            platform=trend_signal.platform,
            source="user_topic",
            emotional_vector=dict(trend_signal.emotional_vector),
            platform_fit=dict(trend_signal.platform_fit),
            expiry_window_hours=trend_signal.expiry_window_hours,
        )

    @staticmethod
    def _with_pipeline_topic(
        trend_signal: TrendSignal,
        pipeline_topic: str,
    ) -> TrendSignal:
        if trend_signal.topic == pipeline_topic:
            return trend_signal

        return TrendSignal(
            topic=pipeline_topic,
            velocity=trend_signal.velocity,
            saturation=trend_signal.saturation,
            virality_score=trend_signal.virality_score,
            platform=trend_signal.platform,
            source=trend_signal.source,
            emotional_vector=dict(trend_signal.emotional_vector),
            platform_fit=dict(trend_signal.platform_fit),
            expiry_window_hours=trend_signal.expiry_window_hours,
        )

    def _resolve_platform(self, platform: Platform | str) -> Platform:
        if isinstance(platform, Platform):
            return platform
        return Platform(str(platform))

    def _resolve_provider_name(
        self,
        profile: dict[str, Any],
        provider_name: Optional[str],
    ) -> str:
        if provider_name:
            return provider_name

        production_defaults = profile.get("production_defaults", {})
        configured = production_defaults.get("default_provider")
        if configured:
            return str(configured)

        return "hailuo"

    def _build_next_action(self, decision_package: DecisionPackage) -> str:
        base_action = NEXT_ACTION_BY_DECISION.get(
            decision_package.decision,
            "review_required",
        )

        if (
            decision_package.decision == ContentDecision.REVISE
            and decision_package.revision_targets
        ):
            return f"{base_action}:{','.join(decision_package.revision_targets)}"

        if (
            decision_package.decision == ContentDecision.REGENERATE
            and decision_package.priority_fixes
        ):
            return f"{base_action}:{decision_package.priority_fixes[0]}"

        return base_action


def _video_format_plan_from_dict(data: dict[str, Any]) -> VideoFormatPlan:
    if not isinstance(data, dict):
        raise ValueError("video_format_plan must be a dict.")

    from content_brain.engines.video_format_planner import (
        ContentType,
        FormatType,
        PacingProfile,
        RecommendedStoryBeat,
    )

    return VideoFormatPlan(
        target_duration_seconds=int(data["target_duration_seconds"]),
        clip_count=int(data["clip_count"]),
        clip_duration_seconds=int(data["clip_duration_seconds"]),
        format_type=FormatType(str(data["format_type"])),
        pacing_profile=PacingProfile(str(data["pacing_profile"])),
        content_type=ContentType(str(data["content_type"])),
        platform=Platform(str(data["platform"])),
        platform_limits=dict(data.get("platform_limits", {})),
        provider_name=str(data.get("provider_name", "hailuo")),
        provider_limits=dict(data.get("provider_limits", {})),
        recommended_story_beats=[
            RecommendedStoryBeat(
                beat_id=str(item["beat_id"]),
                start_second=float(item["start_second"]),
                end_second=float(item["end_second"]),
                act=int(item["act"]),
                goal=str(item.get("goal", "")),
            )
            for item in data.get("recommended_story_beats", [])
        ],
        selection_reason=str(data.get("selection_reason", "")),
        user_duration_requested=data.get("user_duration_requested"),
        metadata=dict(data.get("metadata", {})),
    )


__all__ = [
    "ContentBriefOrchestrator",
    "ContentBriefOrchestratorError",
    "ContentBriefResult",
    "ContentBriefRunRequest",
]


if __name__ == "__main__":
    import tempfile

    orchestrator = ContentBriefOrchestrator(project_root=".")

    cases = [
        ContentBriefRunRequest(
            niche="football",
            topic="late VAR decision changed the result",
            platform=Platform.TIKTOK,
            user_duration_seconds=30,
            provider_name="hailuo",
            provider_clip_duration_seconds=6,
        ),
        ContentBriefRunRequest(
            niche="perfume",
            topic="the scent everyone asked about at the airport",
            platform=Platform.TIKTOK,
            user_duration_seconds=30,
            provider_name="hailuo",
            provider_clip_duration_seconds=8,
        ),
        ContentBriefRunRequest(
            niche="dark_mystery",
            topic="the room that was not on the blueprint",
            platform=Platform.TIKTOK,
            user_duration_seconds=45,
            provider_name="runway",
            provider_clip_duration_seconds=10,
            record_uniqueness_on_success=False,
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        isolated_orchestrator = ContentBriefOrchestrator(
            project_root=".",
            memory_path=Path(tmp_dir) / "content_history.json",
        )

        for request in cases:
            result = isolated_orchestrator.run(request)

            payload = result.to_dict()
            roundtrip = ContentBriefResult.from_dict(payload)

            print("\n" + "=" * 72)
            print(
                f"{request.niche.upper()} | {result.decision_package.decision.value} | "
                f"tier {result.viral_scorecard.production_tier.value} | "
                f"composite {result.viral_scorecard.composite_score:.1f}"
            )
            print("TOPIC:", result.trend_signal.topic)
            print("NEXT ACTION:", result.next_action)
            print("PRODUCTION READY:", result.production_ready)
            print("FORMAT:", f"{result.video_format_plan.clip_count}x{result.video_format_plan.clip_duration_seconds}s")
            print("RECOMMENDED TITLE:", result.title_thumbnail_package.recommended_title or "none")
            print(
                "THUMBNAIL CONCEPT:",
                result.title_thumbnail_package.recommended_thumbnail_concept.get(
                    "concept_id",
                    "none",
                ),
            )
            print(
                "PACKAGING WARNINGS:",
                "; ".join(result.title_thumbnail_package.warnings) or "none",
            )
            print(
                "TITLE COUNT:",
                len(result.title_thumbnail_package.titles),
                "| ROUNDTRIP TITLES:",
                len(roundtrip.title_thumbnail_package.titles),
            )
            print("JSON OK:", json.dumps(payload)[:140] + "...")
            print("ROUNDTRIP:", roundtrip.brief_id[:18], roundtrip.next_action)

        print("\n" + "=" * 72)
        print("DEFAULT ORCHESTRATOR SMOKE TEST")
        smoke = orchestrator.run(
            ContentBriefRunRequest(
                niche="general",
                topic="quick orchestrator smoke test",
                record_uniqueness_on_success=False,
            )
        )
        print(
            f"GENERAL | {smoke.decision_package.decision.value} | "
            f"ready={smoke.production_ready} | action={smoke.next_action} | "
            f"title={(smoke.title_thumbnail_package.recommended_title or 'none')[:40]}"
        )

        if ChannelIdentityStore is not None:
            from content_brain.profiles.channel_identity_store import ChannelIdentity

            channel_store = ChannelIdentityStore(project_root=".")
            channel = ChannelIdentity(
                channel_name="VAR Decisions Daily",
                main_niche="football VAR controversy",
                audience="Football fans who debate referee calls",
                tone_story_style="documentary_style",
                platform="TikTok",
                language="English",
                visual_style="broadcast replay frames, stadium close-ups",
            )
            channel_store.save(channel, set_active=True)

            channel_orchestrator = ContentBriefOrchestrator(
                project_root=".",
                memory_path=Path(tmp_dir) / "channel_content_history.json",
            )

            print("\n" + "=" * 72)
            print("CHANNEL IDENTITY ORCHESTRATOR SMOKE TEST")

            explicit_topic = channel_orchestrator.run(
                ContentBriefRunRequest(
                    channel_id=channel.channel_id,
                    topic="late VAR decision changed the result",
                    record_uniqueness_on_success=False,
                )
            )
            auto_topic = channel_orchestrator.run(
                ContentBriefRunRequest(
                    channel_id=channel.channel_id,
                    topic="",
                    record_uniqueness_on_success=False,
                )
            )

            print(
                "CHANNEL EXPLICIT TOPIC:",
                explicit_topic.run_context.get("topic"),
                "| applied=",
                explicit_topic.run_context.get("channel_identity_applied"),
            )
            print(
                "CHANNEL AUTO TOPIC:",
                auto_topic.run_context.get("topic"),
                "| authoritative=",
                auto_topic.run_context.get("user_topic_authoritative"),
            )
            print("CHANNEL NAME:", explicit_topic.run_context.get("channel_name"))
            print(
                "PROFILE APPLIED:",
                explicit_topic.profile.get("metadata", {}).get(
                    "channel_identity_applied"
                ),
            )
