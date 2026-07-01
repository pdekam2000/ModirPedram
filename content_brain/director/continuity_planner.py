"""Director Layer V1 — Continuity Planner."""

from __future__ import annotations

from typing import Any

from content_brain.director.director_models import ContinuityPlan, SceneBreakdown, StoryboardPlan
from content_brain.director.openai_director_client import openai_json_completion

CONTINUITY_SYSTEM_PROMPT = """Continuity supervisor JSON:
recurring_subjects[], recurring_objects[], recurring_locations[], continuity_rules[], forbidden_changes[].
Preserve character, environment, palette, object continuity. Block drift."""


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _deterministic_continuity_plan(*, storyboard: StoryboardPlan, scene_breakdown: SceneBreakdown, topic: str) -> ContinuityPlan:
    recurring_objects: list[str] = []
    for clip in scene_breakdown.clips:
        for scene in clip.scenes:
            recurring_objects.extend(scene.continuity_elements)
    return ContinuityPlan(
        recurring_subjects=_dedupe([storyboard.main_character, topic]),
        recurring_objects=_dedupe(recurring_objects),
        recurring_locations=_dedupe([storyboard.setting]),
        continuity_rules=_dedupe([
            f"Maintain consistent appearance for {storyboard.main_character}",
            f"Keep {storyboard.setting} environment palette stable",
            f"Preserve visual style: {storyboard.visual_style}",
            "Match lighting temperature and contrast across clips",
            *[clip.continuity_anchor for clip in storyboard.clips if clip.continuity_anchor],
        ]),
        forbidden_changes=_dedupe([
            "Do not change main character identity", "Do not relocate to unrelated environment",
            "Do not introduce gaming, GPU, or tech lab elements unless topic requires",
            "Do not swap color palette between clips", "Do not remove anchor props introduced in clip 1",
        ]),
        source="deterministic_fallback",
    )


def _parse_continuity_plan(payload: dict[str, Any]) -> ContinuityPlan:
    return ContinuityPlan(
        recurring_subjects=_dedupe([str(v) for v in payload.get("recurring_subjects") or []]),
        recurring_objects=_dedupe([str(v) for v in payload.get("recurring_objects") or []]),
        recurring_locations=_dedupe([str(v) for v in payload.get("recurring_locations") or []]),
        continuity_rules=_dedupe([str(v) for v in payload.get("continuity_rules") or []]),
        forbidden_changes=_dedupe([str(v) for v in payload.get("forbidden_changes") or []]),
        source="openai", model=str(payload.get("_model") or ""),
    )


def generate_continuity_plan(
    *, storyboard: StoryboardPlan, scene_breakdown: SceneBreakdown, topic: str, dry_run: bool = False,
) -> tuple[ContinuityPlan, list[str]]:
    notes: list[str] = []
    if dry_run:
        notes.append("continuity_plan_dry_run")
        return _deterministic_continuity_plan(storyboard=storyboard, scene_breakdown=scene_breakdown, topic=topic), notes
    raw, model, client_notes = openai_json_completion(
        system_prompt=CONTINUITY_SYSTEM_PROMPT,
        user_payload={"topic": topic, "storyboard": storyboard.to_dict(), "scene_breakdown": scene_breakdown.to_dict()},
        dry_run=False,
    )
    notes.extend(client_notes)
    if raw:
        raw["_model"] = model
        notes.append(f"continuity_plan_openai:{model}")
        return _parse_continuity_plan(raw), notes
    notes.append("continuity_plan_deterministic_fallback")
    return _deterministic_continuity_plan(storyboard=storyboard, scene_breakdown=scene_breakdown, topic=topic), notes
