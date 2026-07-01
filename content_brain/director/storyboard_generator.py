"""Director Layer V1 — OpenAI Storyboard Generator."""

from __future__ import annotations

import re
from typing import Any

from content_brain.director.director_models import StoryboardClipPlan, StoryboardPlan
from content_brain.director.openai_director_client import openai_json_completion

STORYBOARD_SYSTEM_PROMPT = """You are a cinematic director planning a short-form multi-clip storyboard.
Return ONLY valid JSON with title, logline, main_character, setting, visual_style, emotional_arc,
and clips[] with clip_index, summary, goal, key_visual, emotion, continuity_anchor, ending_transition.
User topic is authoritative. Never drift to gaming/GPU/tech lab unless topic requires.
Create exactly clip_count clips."""


def _topic_subject(topic: str) -> str:
    return (re.sub(r"\s+", " ", (topic or "subject").strip())[:80]) or "subject"


def _deterministic_storyboard(
    *, topic: str, niche: str, target_platform: str, duration: int, clip_count: int,
    style: str, story_brief: dict[str, Any] | None = None,
) -> StoryboardPlan:
    subject = _topic_subject(topic)
    brief = story_brief or {}
    setting = str(brief.get("setting") or brief.get("environment") or f"natural habitat of {subject}")
    character = str(brief.get("main_subject") or brief.get("character") or subject)
    visual = style or str(brief.get("visual_style") or "documentary cinematic realism")
    templates = [
        (f"Establish {subject} in {setting}", f"Introduce {character} and environment",
         f"Wide shot revealing {subject} context", "wonder",
         f"Same {character} appearance and {setting} palette", f"Camera pushes toward {subject} activity"),
        (f"Follow {subject} through a pivotal moment", f"Show core behavior of {subject}",
         f"Medium tracking shot on {character}", "focus",
         f"Preserve scale and location cues for {subject}", "Action leads into next beat with motion carry-over"),
        (f"Resolve the {subject} story beat", f"Deliver payoff tied to {topic}",
         f"Hero close-up or symbolic final frame of {subject}", "resolution",
         f"Maintain identical {character} and {setting} continuity", "Hold final frame for seamless handoff"),
    ]
    clips = []
    for index in range(1, max(1, clip_count) + 1):
        t = templates[min(index - 1, len(templates) - 1)]
        clips.append(StoryboardClipPlan(clip_index=index, summary=t[0], goal=t[1], key_visual=t[2],
                                        emotion=t[3], continuity_anchor=t[4], ending_transition=t[5]))
    return StoryboardPlan(
        title=str(brief.get("title") or f"{subject.title()} — {niche or 'short'} story"),
        logline=str(brief.get("logline") or f"A {duration}s {target_platform} story about {subject}."),
        main_character=character, setting=setting, visual_style=visual,
        emotional_arc=str(brief.get("emotional_arc") or "curiosity → tension → resolution"),
        clips=clips, source="deterministic_fallback",
    )


def _parse_storyboard_payload(payload: dict[str, Any], *, clip_count: int) -> StoryboardPlan:
    clips: list[StoryboardClipPlan] = []
    for index, item in enumerate((payload.get("clips") or [])[: max(1, clip_count)], start=1):
        if isinstance(item, dict):
            clip = StoryboardClipPlan.from_dict(item, clip_index=index)
            clip.clip_index = index
            clips.append(clip)
    while len(clips) < max(1, clip_count):
        clips.append(StoryboardClipPlan(clip_index=len(clips) + 1, summary=f"Clip {len(clips) + 1} continuation"))
    return StoryboardPlan(
        title=str(payload.get("title") or ""), logline=str(payload.get("logline") or ""),
        main_character=str(payload.get("main_character") or ""), setting=str(payload.get("setting") or ""),
        visual_style=str(payload.get("visual_style") or ""), emotional_arc=str(payload.get("emotional_arc") or ""),
        clips=clips, source="openai", model=str(payload.get("_model") or ""),
    )


def generate_storyboard_plan(
    *, topic: str, niche: str = "", target_platform: str = "shorts", duration: int = 30,
    clip_count: int = 3, style: str = "", audience: str = "", story_brief: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> tuple[StoryboardPlan, list[str]]:
    notes: list[str] = []
    raw, model, client_notes = openai_json_completion(
        system_prompt=STORYBOARD_SYSTEM_PROMPT,
        user_payload={"topic": topic, "niche": niche, "target_platform": target_platform,
                      "duration_seconds": duration, "clip_count": clip_count, "style": style,
                      "audience": audience, "story_brief": story_brief or {}},
        dry_run=dry_run,
    )
    notes.extend(client_notes)
    if raw:
        raw["_model"] = model
        notes.append("storyboard_openai_generated")
        return _parse_storyboard_payload(raw, clip_count=clip_count), notes
    notes.append("storyboard_deterministic_fallback")
    return _deterministic_storyboard(topic=topic, niche=niche, target_platform=target_platform,
                                     duration=duration, clip_count=clip_count, style=style,
                                     story_brief=story_brief), notes
