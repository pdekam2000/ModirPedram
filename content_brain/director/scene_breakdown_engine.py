"""Director Layer V1 — Scene Breakdown Engine."""

from __future__ import annotations

from typing import Any

from content_brain.director.director_models import ClipSceneBreakdown, SceneBreakdown, SceneSpec, StoryboardPlan
from content_brain.director.openai_director_client import openai_json_completion

SCENE_BREAKDOWN_SYSTEM_PROMPT = """Convert storyboard to per-clip scene breakdown JSON with clips[].scenes[]
(scene_id, purpose, camera_direction, environment, subject_action, mood, continuity_elements).
One primary scene per clip. Preserve topic authority."""


def _camera_for_clip(index: int) -> str:
    return {1: "Wide establishing shot, slow push-in", 2: "Medium tracking shot, lateral follow",
            3: "Close hero shot, gentle rack focus"}.get(index, "Medium shot, stable framing")


def _deterministic_scene_breakdown(storyboard: StoryboardPlan) -> SceneBreakdown:
    clips = []
    for clip in storyboard.clips:
        clips.append(ClipSceneBreakdown(clip_index=clip.clip_index, scenes=[
            SceneSpec(scene_id=f"clip{clip.clip_index}_scene1", purpose=clip.goal or clip.summary,
                      camera_direction=_camera_for_clip(clip.clip_index), environment=storyboard.setting,
                      subject_action=clip.key_visual or clip.summary, mood=clip.emotion,
                      continuity_elements=[storyboard.main_character, storyboard.setting, clip.continuity_anchor]),
        ]))
    return SceneBreakdown(clips=clips)


def _parse_scene_breakdown(payload: dict[str, Any], storyboard: StoryboardPlan) -> SceneBreakdown:
    clips: list[ClipSceneBreakdown] = []
    for item in payload.get("clips") or []:
        if not isinstance(item, dict):
            continue
        clip_index = int(item.get("clip_index") or 0)
        scenes = [SceneSpec(
            scene_id=str(s.get("scene_id") or f"clip{clip_index}_scene1"),
            purpose=str(s.get("purpose") or ""), camera_direction=str(s.get("camera_direction") or ""),
            environment=str(s.get("environment") or ""), subject_action=str(s.get("subject_action") or ""),
            mood=str(s.get("mood") or ""),
            continuity_elements=[str(v) for v in (s.get("continuity_elements") or []) if str(v).strip()],
        ) for s in (item.get("scenes") or []) if isinstance(s, dict)]
        if scenes:
            clips.append(ClipSceneBreakdown(clip_index=clip_index, scenes=scenes))
    if not clips:
        return _deterministic_scene_breakdown(storyboard)
    expected = {c.clip_index for c in storyboard.clips}
    present = {c.clip_index for c in clips}
    if expected - present:
        fallback = _deterministic_scene_breakdown(storyboard)
        for clip in fallback.clips:
            if clip.clip_index not in present:
                clips.append(clip)
        clips.sort(key=lambda item: item.clip_index)
    return SceneBreakdown(clips=clips)


def generate_scene_breakdown(*, storyboard: StoryboardPlan, topic: str = "", dry_run: bool = False) -> tuple[SceneBreakdown, list[str]]:
    notes: list[str] = []
    if dry_run:
        notes.append("scene_breakdown_dry_run")
        return _deterministic_scene_breakdown(storyboard), notes
    raw, model, client_notes = openai_json_completion(
        system_prompt=SCENE_BREAKDOWN_SYSTEM_PROMPT,
        user_payload={"topic": topic, "storyboard": storyboard.to_dict()}, dry_run=False,
    )
    notes.extend(client_notes)
    if raw:
        notes.append(f"scene_breakdown_openai:{model}")
        return _parse_scene_breakdown(raw, storyboard), notes
    notes.append("scene_breakdown_deterministic_fallback")
    return _deterministic_scene_breakdown(storyboard), notes
