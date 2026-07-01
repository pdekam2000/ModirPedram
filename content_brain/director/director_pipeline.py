"""Director Layer V1 — orchestrates storyboard → scene breakdown → continuity planning."""

from __future__ import annotations

from typing import Any

from content_brain.director.continuity_planner import generate_continuity_plan
from content_brain.director.director_models import DirectorLayerOutput
from content_brain.director.director_topic_authority import audit_director_topic_authority
from content_brain.director.scene_breakdown_engine import generate_scene_breakdown
from content_brain.director.storyboard_generator import generate_storyboard_plan
from content_brain.director.visual_subject_lock import extract_visual_subject_lock


def build_director_layer(
    *, topic: str, story_brief: dict[str, Any] | None = None, niche: str = "", target_platform: str = "shorts",
    duration: int = 30, clip_count: int = 3, style: str = "", audience: str = "", mood: str = "", dry_run: bool = False,
) -> DirectorLayerOutput:
    notes: list[str] = []
    warnings: list[str] = []
    storyboard, storyboard_notes = generate_storyboard_plan(
        topic=topic, niche=niche, target_platform=target_platform, duration=duration, clip_count=clip_count,
        style=style or mood, audience=audience, story_brief=story_brief, dry_run=dry_run,
    )
    notes.extend(storyboard_notes)
    scene_breakdown, scene_notes = generate_scene_breakdown(storyboard=storyboard, topic=topic, dry_run=dry_run)
    notes.extend(scene_notes)
    continuity_plan, continuity_notes = generate_continuity_plan(
        storyboard=storyboard, scene_breakdown=scene_breakdown, topic=topic, dry_run=dry_run,
    )
    notes.extend(continuity_notes)
    authority = audit_director_topic_authority(topic=topic, storyboard=storyboard.to_dict(),
                                                scene_breakdown=scene_breakdown.to_dict())
    if not authority.get("pass"):
        warnings.append("director_topic_authority_soft_fail")
        storyboard, _ = generate_storyboard_plan(
            topic=topic, niche=niche, target_platform=target_platform, duration=duration, clip_count=clip_count,
            style=style or mood, audience=audience, story_brief=story_brief, dry_run=True,
        )
        scene_breakdown, _ = generate_scene_breakdown(storyboard=storyboard, topic=topic, dry_run=True)
        continuity_plan, _ = generate_continuity_plan(storyboard=storyboard, scene_breakdown=scene_breakdown, topic=topic, dry_run=True)
        authority = audit_director_topic_authority(topic=topic, storyboard=storyboard.to_dict(),
                                                    scene_breakdown=scene_breakdown.to_dict())
        notes.append("director_topic_authority_regenerated_deterministic")
    visual_subject_lock = extract_visual_subject_lock(
        topic=topic,
        story_brief=dict(story_brief or {}),
        storyboard=storyboard.to_dict(),
        scene_breakdown=scene_breakdown.to_dict(),
    )
    notes.append("visual_subject_lock_extracted")
    return DirectorLayerOutput(
        storyboard=storyboard,
        scene_breakdown=scene_breakdown,
        continuity_plan=continuity_plan,
        visual_subject_lock=visual_subject_lock,
        topic_authority_score=float(authority.get("score") or 0.0),
        topic_authority_pass=bool(authority.get("pass")),
        warnings=warnings,
        notes=notes,
    )
