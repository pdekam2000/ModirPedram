"""Director Layer V2 — Prompt Rewriter (Phase 2C)."""

from __future__ import annotations

import re
from typing import Any

from content_brain.director.director_models import (
    CRITIC_ISSUE_CONTINUITY_RISK,
    CRITIC_ISSUE_REPETITION_RISK,
    CRITIC_ISSUE_TOPIC_DRIFT,
    CRITIC_ISSUE_WEAK_ENDING,
    CRITIC_ISSUE_WEAK_HOOK,
    CRITIC_ISSUE_WEAK_VISUALS,
    PromptCriticReport,
)
from content_brain.director.director_topic_authority import DIRECTOR_FORBIDDEN_DRIFT
from content_brain.director.openai_director_client import openai_json_completion

REWRITER_SYSTEM_PROMPT = """Rewrite Runway video prompts to fix critic issues while preserving topic authority.
Return ONLY JSON: { "starter_image_prompt": "...", "clip_prompts": ["...", "..."] }.
No subtitles/logos/watermarks. Keep prompts long and cinematic."""

STRIP_DRIFT = DIRECTOR_FORBIDDEN_DRIFT + ("gpu", "gaming", "technology", "tech lab", "graphics card", "esports", "video game", "server room")


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _strip_drift(text: str) -> str:
    cleaned = text
    for term in STRIP_DRIFT:
        cleaned = re.sub(re.escape(term), "", cleaned, flags=re.I)
    return _norm(re.sub(r"\s{2,}", " ", cleaned))


def _storyboard_clip(storyboard: dict[str, Any] | None, index: int) -> dict[str, Any]:
    if not storyboard:
        return {}
    for clip in storyboard.get("clips") or []:
        if isinstance(clip, dict) and int(clip.get("clip_index") or 0) == index:
            return clip
    clips = storyboard.get("clips") or []
    if len(clips) >= index and isinstance(clips[index - 1], dict):
        return clips[index - 1]
    return {}


def _scene_for_clip(scene_breakdown: dict[str, Any] | None, index: int) -> dict[str, Any]:
    if not scene_breakdown:
        return {}
    for clip in scene_breakdown.get("clips") or []:
        if isinstance(clip, dict) and int(clip.get("clip_index") or 0) == index:
            scenes = clip.get("scenes") or []
            if scenes and isinstance(scenes[0], dict):
                return scenes[0]
    return {}


def _deterministic_rewrite(
    *, topic: str, starter_image_prompt: str, clip_prompts: list[str], report: PromptCriticReport,
    storyboard: dict[str, Any] | None = None, scene_breakdown: dict[str, Any] | None = None,
    continuity_plan: dict[str, Any] | None = None,
) -> tuple[str, list[str], list[str]]:
    notes = ["prompt_rewriter_deterministic"]
    starter = starter_image_prompt
    clips = list(clip_prompts)
    rules = list((continuity_plan or {}).get("continuity_rules") or [])
    forbidden = list((continuity_plan or {}).get("forbidden_changes") or [])

    if CRITIC_ISSUE_TOPIC_DRIFT in report.issues:
        anchor = f"Topic anchor: {topic}. "
        starter = _norm(f"{anchor}{_strip_drift(starter)}")
        clips = [_norm(f"{anchor}{_strip_drift(p)}") for p in clips]
        notes.append("rewrite_topic_drift")

    if CRITIC_ISSUE_WEAK_HOOK in report.issues and clips:
        c1 = _storyboard_clip(storyboard, 1)
        s1 = _scene_for_clip(scene_breakdown, 1)
        hook = c1.get("key_visual") or s1.get("subject_action") or f"Immediate visual hook introducing {topic}"
        if "hook" not in clips[0].lower()[:120]:
            clips[0] = _norm(f"Immediate visual hook: {hook}. {clips[0]}")
            notes.append("rewrite_weak_hook")

    if CRITIC_ISSUE_WEAK_ENDING in report.issues and clips:
        c3 = _storyboard_clip(storyboard, len(clips))
        ending = c3.get("ending_transition") or f"Hold final payoff frame tied to {topic}"
        if not any(w in clips[-1].lower() for w in ("payoff", "resolution", "final", "handoff")):
            clips[-1] = _norm(f"{clips[-1]} Ending payoff: {ending}.")
            notes.append("rewrite_weak_ending")

    if CRITIC_ISSUE_WEAK_VISUALS in report.issues:
        visual = str((storyboard or {}).get("visual_style") or "cinematic realism")
        for i, prompt in enumerate(clips, start=1):
            scene = _scene_for_clip(scene_breakdown, i)
            camera = scene.get("camera_direction") or "motivated cinematic camera movement"
            if "camera" not in prompt.lower()[:300]:
                clips[i - 1] = _norm(f"Cinematic visual direction ({visual}): {camera}. {prompt}")
        notes.append("rewrite_weak_visuals")

    if CRITIC_ISSUE_CONTINUITY_RISK in report.issues:
        lock = rules[0] if rules else f"Maintain consistent {topic} identity across clips"
        for i, prompt in enumerate(clips):
            if "continuity lock" not in prompt.lower():
                clips[i] = _norm(f"Continuity lock: {lock}. {prompt}")
        notes.append("rewrite_continuity_risk")

    if CRITIC_ISSUE_REPETITION_RISK in report.issues:
        for i, prompt in enumerate(clips, start=1):
            clip_data = _storyboard_clip(storyboard, i)
            distinct = clip_data.get("summary") or clip_data.get("goal") or f"Clip {i} unique beat for {topic}"
            marker = f"Clip {i} distinct action:"
            if marker.lower() not in prompt.lower():
                clips[i - 1] = _norm(f"{marker} {distinct}. {prompt}")
        notes.append("rewrite_repetition_risk")

    if forbidden:
        starter = _norm(f"{starter} Forbidden changes: {'; '.join(forbidden[:2])}.")
    return starter, clips, notes


def rewrite_prompts(
    *, topic: str, starter_image_prompt: str, clip_prompts: list[str], report: PromptCriticReport,
    story_brief: dict[str, Any] | None = None, storyboard: dict[str, Any] | None = None,
    scene_breakdown: dict[str, Any] | None = None, continuity_plan: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> tuple[str, list[str], list[str]]:
    notes: list[str] = []
    raw, model, client_notes = openai_json_completion(
        system_prompt=REWRITER_SYSTEM_PROMPT,
        user_payload={
            "topic": topic, "critic_report": report.to_dict(), "story_brief": story_brief or {},
            "storyboard": storyboard or {}, "scene_breakdown": scene_breakdown or {},
            "continuity_plan": continuity_plan or {}, "starter_image_prompt": starter_image_prompt,
            "clip_prompts": list(clip_prompts),
        },
        dry_run=dry_run,
    )
    notes.extend(client_notes)
    if raw and raw.get("clip_prompts"):
        notes.append(f"prompt_rewriter_openai:{model}")
        return str(raw.get("starter_image_prompt") or starter_image_prompt), [str(x) for x in raw.get("clip_prompts")], notes
    return _deterministic_rewrite(
        topic=topic, starter_image_prompt=starter_image_prompt, clip_prompts=clip_prompts, report=report,
        storyboard=storyboard, scene_breakdown=scene_breakdown, continuity_plan=continuity_plan,
    )
