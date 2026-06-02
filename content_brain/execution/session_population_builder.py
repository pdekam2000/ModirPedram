"""
Phase 10D — populate execution session JSON from ContentBriefOrchestrator output.

No provider execution, no queue, no approval writes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import uuid

from content_brain.engines.content_decision_engine import ContentDecision
from content_brain.orchestrators.content_brief_orchestrator import ContentBriefResult

SESSION_SCHEMA_VERSION = "10d_v1"
POPULATION_VERSION = "10d_v1"
POPULATION_SOURCE = "content_brief_orchestrator"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

TIER_TO_PRIORITY_BAND = {
    "S": "critical",
    "A": "high",
    "B": "medium",
    "F": "low",
}

# Rough per-clip credit estimate for approval/budget seeds (not billing truth).
PROVIDER_CREDIT_PER_CLIP: dict[str, float] = {
    "hailuo": 1.0,
    "hailuo_browser": 1.0,
    "runway": 2.0,
    "runway_browser": 2.0,
    "generic": 1.0,
}


def generate_execution_session_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"exec_{stamp}_{short}"


def _now_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _estimate_credits(provider_name: str, clip_count: int) -> float:
    key = provider_name.lower().strip()
    per_clip = PROVIDER_CREDIT_PER_CLIP.get(key, PROVIDER_CREDIT_PER_CLIP["generic"])
    for candidate, rate in PROVIDER_CREDIT_PER_CLIP.items():
        if candidate in key:
            per_clip = rate
            break
    return round(max(clip_count, 1) * per_clip, 2)


def _merge_story_decision(content_decision: str, memory_decision: str) -> str:
    strict = {ContentDecision.REJECT.value, ContentDecision.REGENERATE.value, ContentDecision.REVISE.value}
    if content_decision in strict:
        return content_decision
    if memory_decision in strict:
        return memory_decision
    return content_decision or memory_decision or ContentDecision.PROCEED.value


def _build_story_quality(brief: ContentBriefResult, brief_snapshot: dict[str, Any]) -> dict[str, Any]:
    run_context = _dict(brief.run_context)
    story_intelligence = _dict(run_context.get("story_intelligence"))
    intelligence_blueprint = _dict(story_intelligence.get("story_blueprint"))
    quality_scores = _dict(intelligence_blueprint.get("story_quality_score"))
    memory = _dict(story_intelligence.get("memory"))

    viral = brief.viral_scorecard
    decision = brief.decision_package

    composite = quality_scores.get("composite")
    if composite is None:
        composite = run_context.get("story_intelligence_composite_score")
    if composite is None:
        composite = viral.composite_score

    merged_decision = _merge_story_decision(
        decision.decision.value,
        str(memory.get("memory_decision", "")),
    )

    warnings: list[str] = []
    warnings.extend(str(item) for item in decision.weak_dimensions if str(item).strip())
    warnings.extend(str(item) for item in decision.priority_fixes if str(item).strip())
    warnings.extend(str(item) for item in brief.title_thumbnail_package.warnings if str(item).strip())
    if memory.get("suggested_variations"):
        warnings.extend(
            f"Memory: {item}"
            for item in memory.get("suggested_variations", [])
            if str(item).strip()
        )
    if not viral.passed_gate:
        warnings.append("Viral score gate not passed.")

    critical_failures: list[str] = []
    if decision.decision == ContentDecision.REJECT:
        critical_failures.extend(decision.reasons or ["Content decision: REJECT"])

    cost_risk = memory.get("repeated_risk_score")
    if cost_risk is not None:
        try:
            cost_risk = float(cost_risk)
        except (TypeError, ValueError):
            cost_risk = None

    story_quality: dict[str, Any] = {
        "composite_score": composite,
        "score": composite,
        "decision": merged_decision,
        "critical_failures": critical_failures,
        "warnings": warnings,
        "cost_risk_score": cost_risk,
        "metadata": {
            "viral_composite": viral.composite_score,
            "production_tier": viral.production_tier.value,
            "memory_decision": memory.get("memory_decision"),
            "story_intelligence_applied": bool(story_intelligence),
            "source_engines": [
                name
                for name, present in (
                    ("story_intelligence", bool(story_intelligence)),
                    ("story_memory", bool(memory)),
                    ("content_decision", True),
                    ("viral_scoring", True),
                )
                if present
            ],
        },
    }

    if quality_scores:
        for key, value in quality_scores.items():
            if key not in story_quality and key != "composite":
                story_quality[key] = value

    if not story_intelligence:
        story_quality["metadata"]["placeholder_note"] = (
            "Story Intelligence payload absent — scores derived from viral scorecard."
        )

    return story_quality


class SessionPopulationBuilder:
    """Convert ContentBriefResult into a Phase 10D execution session document."""

    def build(
        self,
        brief_result: ContentBriefResult,
        *,
        source_session_uuid: Optional[str] = None,
        execution_session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        brief_snapshot = brief_result.to_dict()
        brief_id = brief_result.brief_id or str(brief_snapshot.get("brief_id", ""))
        run_context = _dict(brief_result.run_context)
        format_plan = brief_result.video_format_plan
        provider_name = (
            format_plan.provider_name
            or str(run_context.get("provider_name", ""))
            or "hailuo"
        ).lower()

        timestamp = _now_timestamp()
        session_uuid = str(uuid.uuid4())
        exec_id = execution_session_id or generate_execution_session_id()

        story_quality = _build_story_quality(brief_result, brief_snapshot)
        score = story_quality.get("composite_score") or story_quality.get("score")

        viral = brief_result.viral_scorecard
        priority_band = TIER_TO_PRIORITY_BAND.get(viral.production_tier.value, "medium")

        clip_count = int(format_plan.clip_count or 1)
        target_duration = int(format_plan.target_duration_seconds or 30)
        estimated_credits = _estimate_credits(provider_name, clip_count)
        estimated_runtime_minutes = round(target_duration / 60.0, 2)

        production_ready = bool(brief_result.production_ready)
        decision_value = brief_result.decision_package.decision.value

        if decision_value == ContentDecision.REJECT.value:
            state = "REJECTED"
        else:
            state = "PLANNED"

        approval_state = "pending" if production_ready else "blocked"
        channel_id = str(run_context.get("channel_id", "")).strip()

        session: dict[str, Any] = {
            "session_schema_version": SESSION_SCHEMA_VERSION,
            "session_uuid": session_uuid,
            "source_session_uuid": source_session_uuid,
            "execution_session_id": exec_id,
            "brief_id": brief_id,
            "state": state,
            "created_at": timestamp,
            "updated_at": timestamp,
            "channel_id": channel_id or None,
            "provider": provider_name,
            "brief_snapshot": brief_snapshot,
            "story_quality": story_quality,
            "story_quality_score": score,
            "priority_band": priority_band,
            "priority_decision": {
                "priority_band": priority_band,
                "priority_score": viral.composite_score,
                "queue_position": None,
                "decision_source": "viral_scorecard_seed",
            },
            "provider_selection": {
                "primary_provider": provider_name,
                "alternatives": [],
                "expected_retry_risk": None,
            },
            "execution_confidence_score": None,
            "execution_confidence": None,
            "approval_state": approval_state,
            "approval_request": {
                "status": approval_state,
                "brief_id": brief_id,
                "recommended_title": brief_result.title_thumbnail_package.recommended_title or None,
                "estimated_credits": estimated_credits,
                "estimated_runtime_minutes": estimated_runtime_minutes,
                "provider_selection": {"primary_provider": provider_name},
                "content_decision": decision_value,
                "production_ready": production_ready,
            },
            "approval_decision": None,
            "budget_state": "unknown",
            "budget_decision": {
                "estimated_credits": estimated_credits,
                "budget_allowed": None,
                "budget_warnings": ["Budget governance engine not run — estimate only."],
            },
            "simulation_report": None,
            "simulation_report_id": None,
            "state_history": [
                {
                    "at": timestamp,
                    "state": state,
                    "reason": "populated from content brief",
                }
            ],
            "metadata": {
                "population_version": POPULATION_VERSION,
                "population_source": POPULATION_SOURCE,
                "lineage_type": None,
                "production_ready": production_ready,
                "niche": run_context.get("niche"),
                "topic": run_context.get("topic"),
                "platform": run_context.get("platform"),
            },
        }

        return session


def build_session_from_brief(
    brief_result: ContentBriefResult,
    **kwargs: Any,
) -> dict[str, Any]:
    return SessionPopulationBuilder().build(brief_result, **kwargs)


__all__ = [
    "SessionPopulationBuilder",
    "SESSION_SCHEMA_VERSION",
    "build_session_from_brief",
    "generate_execution_session_id",
]


if __name__ == "__main__":
    from pathlib import Path

    from content_brain.execution.session_store import ExecutionSessionStore
    from content_brain.orchestrators.content_brief_orchestrator import (
        ContentBriefOrchestrator,
        ContentBriefRunRequest,
    )
    from content_brain.schemas.content_brief import Platform

    root = Path(__file__).resolve().parent.parent.parent
    orchestrator = ContentBriefOrchestrator(project_root=root)
    result = orchestrator.run(
        ContentBriefRunRequest(
            niche="dark_mystery",
            topic="the room that was not on the blueprint",
            platform=Platform.TIKTOK,
            user_duration_seconds=30,
            provider_name="hailuo",
            record_uniqueness_on_success=False,
            record_story_memory_on_success=False,
        )
    )

    builder = SessionPopulationBuilder()
    session = builder.build(result)
    store = ExecutionSessionStore(root)
    path = store.save_session(session, overwrite=True)

    print("Saved:", path)
    print("execution_session_id:", session["execution_session_id"])
    print("session_uuid:", session["session_uuid"])
    print("session_schema_version:", session["session_schema_version"])
    print("source_session_uuid:", session["source_session_uuid"])
    print("state:", session["state"])
    print("story_quality_score:", session.get("story_quality_score"))
    print("brief_id:", session.get("brief_id"))
