"""Dialogue naturalization — cartoon speech, reactions, child-friendly excitement."""

from __future__ import annotations

import re
from typing import Any

from content_brain.story.character_director import CharacterProfile
from content_brain.story.dialogue_engine import DialoguePlan, SceneDialogue

DIALOGUE_NATURALIZATION_VERSION = "dialogue_naturalization_engine_v1"

STIFF_TO_NATURAL: dict[str, str] = {
    "I think something is calling us.": "Whoa! Did you hear that?!",
    "We should investigate.": "Come on! Let's go see!",
    "Be careful, Whiskers!": "Whiskers, wait! That looks tricky!",
    "That stone is moving!": "Did you see that?! The stone just moved!",
    "Wow! What is that?": "Whoa! What is THAT?!",
    "I can carry it! I know I can!": "I can do it! Watch me!",
    "Then I am with you.": "Okay... I'm right beside you.",
    "We did it!": "We DID it! Look at that!",
    "The jungle remembers us now.": "The whole jungle is glowing for us!",
}

CARTOON_SCENE_PRESETS: list[dict[str, Any]] = [
    {
        "scene_title": "The Glowing Path",
        "dialogue_lines": [
            {"speaker": "Whiskers", "line": "Whoa! What is THAT?!", "emotion": "surprise"},
            {"speaker": "Sage", "line": "Easy, Whiskers... stay close!", "emotion": "tension"},
        ],
        "narration": "Something magical was waiting just beyond the vines.",
        "emotional_intent": "wonder and playful discovery",
    },
    {
        "scene_title": "Split in the Trail",
        "dialogue_lines": [
            {"speaker": "Sage", "line": "Did you see that?! The stone just moved!", "emotion": "fear"},
            {"speaker": "Whiskers", "line": "Whoa! Did you hear that?!", "emotion": "surprise"},
        ],
        "narration": "The path twisted, and the jungle held its breath.",
        "emotional_intent": "surprise turning into brave curiosity",
    },
    {
        "scene_title": "The Hidden Spark",
        "dialogue_lines": [
            {"speaker": "Whiskers", "line": "Come on! Let's go see!", "emotion": "excitement"},
            {"speaker": "Sage", "line": "Okay... I'm right beside you.", "emotion": "relief"},
        ],
        "narration": "A tiny spark pulsed like a heartbeat of light.",
        "emotional_intent": "excitement and courage",
    },
    {
        "scene_title": "Bridge of Light",
        "dialogue_lines": [
            {"speaker": "Whiskers", "line": "We DID it! Look at that!", "emotion": "joy"},
            {"speaker": "Sage", "line": "The whole jungle is glowing for us!", "emotion": "relief"},
        ],
        "narration": "Warm light spilled across the mossy stones like sunrise.",
        "emotional_intent": "joy and reward",
    },
]


def _naturalize_line(text: str, *, speaker: str = "") -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return cleaned
    if cleaned in STIFF_TO_NATURAL:
        return STIFF_TO_NATURAL[cleaned]
    lowered = cleaned.lower()
    if lowered.startswith("i think ") and "calling" in lowered:
        return "Whoa! Did you hear that?!"
    if lowered.startswith("we should "):
        return "Come on! Let's go see!"
    if speaker.lower() == "whiskers" and cleaned.endswith("."):
        if "!" not in cleaned and len(cleaned.split()) <= 8:
            return cleaned[:-1] + "!"
    return cleaned


def _speaker_names(characters: list[CharacterProfile]) -> tuple[str, str]:
    cat = next((c.name for c in characters if c.role == "protagonist"), "Whiskers")
    friend = next((c.name for c in characters if c.role == "mentor"), "Sage")
    return cat, friend


def naturalize_dialogue_plan(
    *,
    dialogue_plan: DialoguePlan,
    characters: list[CharacterProfile],
    genre: str = "cartoon",
) -> DialoguePlan:
    if genre != "cartoon" and dialogue_plan.genre != "cartoon":
        scenes: list[SceneDialogue] = []
        for scene in dialogue_plan.scenes:
            lines = []
            for item in scene.dialogue_lines:
                speaker = str(item.get("speaker") or "")
                lines.append(
                    {
                        "speaker": speaker,
                        "line": _naturalize_line(str(item.get("line") or ""), speaker=speaker),
                        "emotion": str(item.get("emotion") or "neutral"),
                    }
                )
            scenes.append(
                SceneDialogue(
                    scene_index=scene.scene_index,
                    scene_title=scene.scene_title,
                    dialogue_lines=lines,
                    narration=_naturalize_line(scene.narration, speaker="Narrator"),
                    emotional_intent=scene.emotional_intent,
                )
            )
        return DialoguePlan(scenes=scenes, genre=dialogue_plan.genre)

    cat, friend = _speaker_names(characters)
    scenes: list[SceneDialogue] = []
    for index, scene in enumerate(dialogue_plan.scenes):
        preset = CARTOON_SCENE_PRESETS[min(index, len(CARTOON_SCENE_PRESETS) - 1)]
        lines = []
        for item in preset["dialogue_lines"]:
            speaker = str(item["speaker"])
            if speaker.lower() == "whiskers":
                speaker = cat
            elif speaker.lower() == "sage":
                speaker = friend
            lines.append(
                {
                    "speaker": speaker,
                    "line": _naturalize_line(str(item["line"]), speaker=speaker),
                    "emotion": str(item.get("emotion") or "neutral"),
                }
            )
        scenes.append(
            SceneDialogue(
                scene_index=scene.scene_index,
                scene_title=str(preset.get("scene_title") or scene.scene_title),
                dialogue_lines=lines,
                narration=str(preset.get("narration") or scene.narration),
                emotional_intent=str(preset.get("emotional_intent") or scene.emotional_intent),
            )
        )
    return DialoguePlan(scenes=scenes, genre="cartoon")


__all__ = [
    "DIALOGUE_NATURALIZATION_VERSION",
    "CARTOON_SCENE_PRESETS",
    "naturalize_dialogue_plan",
]
