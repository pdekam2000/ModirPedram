"""
E2E-40S — Content Brain planning probe (40s clip plan) with isolated uniqueness memory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.orchestrators.content_brief_orchestrator import (
    ContentBriefOrchestrator,
    ContentBriefRunRequest,
)
from content_brain.schemas.content_brief import Platform

from project_brain.e2e_40s_uniqueness_memory import (
    isolated_probe_memory_file,
    production_uniqueness_memory_path,
    snapshot_uniqueness_memory,
)

_PLATFORM_MAP: dict[str, Platform] = {
    "tiktok": Platform.TIKTOK,
    "youtube_shorts": Platform.YOUTUBE_SHORTS,
    "instagram_reels": Platform.INSTAGRAM_REELS,
}


def resolve_platform(platform: str) -> Platform:
    key = str(platform or "youtube_shorts").strip().lower()
    return _PLATFORM_MAP.get(key, Platform.YOUTUBE_SHORTS)


def run_e2e_40s_planning_probe(
    project_root: Path | str,
    *,
    topic: str,
    platform: str = "youtube_shorts",
    user_duration_seconds: int = 40,
    provider_name: str = "runway_browser",
    niche: str = "general",
) -> dict[str, Any]:
    """
    Run a one-shot brief for E2E validation reporting.

    Uses a temporary uniqueness memory path and never records to production history.
    """
    root = Path(project_root).resolve()
    production_path = production_uniqueness_memory_path(root)
    before_production = snapshot_uniqueness_memory(production_path)

    with isolated_probe_memory_file() as isolated_memory_path:
        orchestrator = ContentBriefOrchestrator(
            project_root=root,
            memory_path=isolated_memory_path,
        )
        brief = orchestrator.run(
            ContentBriefRunRequest(
                niche=niche,
                topic=topic,
                platform=resolve_platform(platform),
                user_duration_seconds=int(user_duration_seconds),
                provider_name=provider_name,
                record_uniqueness_on_success=False,
                record_story_memory_on_success=False,
            )
        )
        isolated_records = isolated_memory_path
        isolated_count = 0
        if isolated_records.is_file():
            isolated_count = snapshot_uniqueness_memory(isolated_records).record_count

    after_production = snapshot_uniqueness_memory(production_path)

    return {
        "topic": topic,
        "platform": platform,
        "user_duration_seconds": int(user_duration_seconds),
        "provider_name": provider_name,
        "decision": brief.decision_package.decision.value,
        "production_ready": bool(brief.production_ready),
        "planned_clip_count": int(brief.video_format_plan.clip_count),
        "uniqueness_passed": bool(brief.uniqueness_report.passed),
        "uniqueness_score": float(brief.uniqueness_report.uniqueness_score),
        "max_similarity": float(brief.uniqueness_report.max_similarity),
        "isolated_memory_record_count": isolated_count,
        "production_memory_unchanged": before_production.equals(after_production),
        "production_memory_path": str(production_path),
        "production_memory_record_count_before": before_production.record_count,
        "production_memory_record_count_after": after_production.record_count,
    }
