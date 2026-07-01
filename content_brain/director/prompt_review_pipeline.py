"""Director Layer V2 — critic + auto rewrite pipeline (max 2 cycles)."""

from __future__ import annotations

from typing import Any

from content_brain.director.director_models import (
    CRITIC_DECISION_PASS,
    PromptQualityThresholds,
    PromptReviewMetadata,
    PromptReviewResult,
)
from content_brain.director.prompt_critic import critique_prompts, decide_critic_action
from content_brain.director.prompt_rewriter import rewrite_prompts

DEFAULT_MAX_REWRITE_CYCLES = 2


def _context_dicts(*, story_brief: Any | None, director_layer: Any | None) -> tuple[dict, dict, dict, dict, Any | None]:
    brief: dict = dict(story_brief.to_dict()) if story_brief is not None and hasattr(story_brief, "to_dict") else (dict(story_brief) if isinstance(story_brief, dict) else {})
    storyboard: dict = {}
    scene_breakdown: dict = {}
    continuity_plan: dict = {}
    visual_subject_lock = None
    if director_layer is not None:
        if hasattr(director_layer, "storyboard"):
            storyboard = director_layer.storyboard.to_dict()
        if hasattr(director_layer, "scene_breakdown"):
            scene_breakdown = director_layer.scene_breakdown.to_dict()
        if hasattr(director_layer, "continuity_plan"):
            continuity_plan = director_layer.continuity_plan.to_dict()
        visual_subject_lock = getattr(director_layer, "visual_subject_lock", None)
    return brief, storyboard, scene_breakdown, continuity_plan, visual_subject_lock


def review_and_rewrite_prompts(
    *, topic: str, starter_image_prompt: str, clip_prompts: list[str],
    story_brief: Any | None = None, director_layer: Any | None = None,
    thresholds: PromptQualityThresholds | None = None, dry_run: bool = False,
    max_rewrite_cycles: int = DEFAULT_MAX_REWRITE_CYCLES,
) -> PromptReviewResult:
    limits = thresholds or PromptQualityThresholds()
    brief, storyboard, scene_breakdown, continuity_plan, visual_subject_lock = _context_dicts(
        story_brief=story_brief, director_layer=director_layer,
    )
    notes: list[str] = []
    reports: list[dict] = []
    rewrite_count = 0
    starter = starter_image_prompt
    clips = list(clip_prompts)

    initial_report, initial_notes = critique_prompts(
        topic=topic, starter_image_prompt=starter, clip_prompts=clips,
        story_brief=brief, storyboard=storyboard, scene_breakdown=scene_breakdown,
        continuity_plan=continuity_plan, visual_subject_lock=visual_subject_lock,
        thresholds=limits, dry_run=dry_run,
    )
    notes.extend(initial_notes)
    reports.append({"cycle": 0, "phase": "initial", **initial_report.to_dict()})
    current = initial_report

    while rewrite_count < max(0, max_rewrite_cycles):
        if current.decision == CRITIC_DECISION_PASS:
            break
        starter, clips, rewrite_notes = rewrite_prompts(
            topic=topic, starter_image_prompt=starter, clip_prompts=clips, report=current,
            story_brief=brief, storyboard=storyboard, scene_breakdown=scene_breakdown,
            continuity_plan=continuity_plan, dry_run=dry_run,
        )
        rewrite_count += 1
        notes.extend(rewrite_notes)
        notes.append(f"rewrite_cycle_{rewrite_count}")
        rescored, rescore_notes = critique_prompts(
            topic=topic, starter_image_prompt=starter, clip_prompts=clips,
            story_brief=brief, storyboard=storyboard, scene_breakdown=scene_breakdown,
            continuity_plan=continuity_plan, visual_subject_lock=visual_subject_lock,
            thresholds=limits, dry_run=dry_run,
        )
        notes.extend(rescore_notes)
        rescored.decision = decide_critic_action(rescored, limits)
        reports.append({"cycle": rewrite_count, "phase": "rescore", **rescored.to_dict()})
        current = rescored
        if current.decision == CRITIC_DECISION_PASS:
            break

    metadata = PromptReviewMetadata(
        score=current.overall_score, decision=current.decision, issues=list(current.issues),
        rewrite_count=rewrite_count, topic=topic, thresholds=limits.to_dict(),
        reports=reports, final_report=current.to_dict(), notes=notes,
    )
    return PromptReviewResult(
        starter_image_prompt=starter, clip_prompts=clips, metadata=metadata,
        initial_report=initial_report, final_report=current,
    )
