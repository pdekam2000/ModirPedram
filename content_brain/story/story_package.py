"""StoryPackage orchestrator — cinematic story + audio director bundle."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.audio.dialogue_timeline_builder import DialogueTimeline, build_dialogue_timeline
from content_brain.audio.environment_designer import EnvironmentPlan, build_environment_plan
from content_brain.audio.environment_presence_engine import enhance_environment_presence
from content_brain.audio.music_mood_selector import select_music_mood
from content_brain.audio.music_director import MusicPlan, build_music_plan
from content_brain.audio.scene_sync_engine import build_scene_sync_plan
from content_brain.audio.voice_casting_director import VoiceCastPlan, build_voice_cast_plan
from content_brain.audio.voice_identity_registry import apply_voice_identity_registry
from content_brain.story.character_director import CharacterProfile, build_character_profiles
from content_brain.story.character_performance_engine import build_character_performance_profiles
from content_brain.story.dialogue_engine import DialoguePlan, build_dialogue_plan
from content_brain.story.dialogue_naturalization_engine import naturalize_dialogue_plan
from content_brain.story.emotion_engine import EmotionPlan, build_emotion_plan
from content_brain.story.story_emotion_engine import StoryEmotionArc, build_story_emotion_arc
from content_brain.story.story_architect import StoryBlueprint, build_story_blueprint
from content_brain.story.story_visual_orchestrator import build_story_visual_bundle, save_story_visual_artifacts

STORY_PACKAGE_VERSION = "story_package_v3"


@dataclass
class StoryPackage:
    run_id: str
    topic: str
    story_blueprint: StoryBlueprint
    character_profiles: list[CharacterProfile]
    dialogue_plan: DialoguePlan
    emotion_plan: EmotionPlan
    voice_cast_plan: VoiceCastPlan
    environment_plan: EnvironmentPlan
    music_plan: MusicPlan
    dialogue_timeline: DialogueTimeline
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STORY_PACKAGE_VERSION,
            "run_id": self.run_id,
            "topic": self.topic,
            "created_at": self.created_at,
            "story_blueprint": self.story_blueprint.to_dict(),
            "character_profiles": [profile.to_dict() for profile in self.character_profiles],
            "dialogue_plan": self.dialogue_plan.to_dict(),
            "emotion_plan": self.emotion_plan.to_dict(),
            "voice_cast_plan": self.voice_cast_plan.to_dict(),
            "environment_plan": self.environment_plan.to_dict(),
            "music_plan": self.music_plan.to_dict(),
            "dialogue_timeline": self.dialogue_timeline.to_dict(),
            "metadata": dict(self.metadata),
        }


def story_package_path(project_root: str | Path, run_id: str) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(run_id or "latest")).strip("_") or "latest"
    return Path(project_root).resolve() / "project_brain" / "story_packages" / f"{slug}.json"


def save_story_package(project_root: str | Path, package: StoryPackage) -> Path:
    path = story_package_path(project_root, package.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(package.to_dict(), indent=2), encoding="utf-8")
    return path


def load_story_package(project_root: str | Path, run_id: str) -> dict[str, Any]:
    path = story_package_path(project_root, run_id)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_story_package(
    *,
    project_root: str | Path,
    topic: str,
    run_id: str = "",
    clip_count: int = 3,
    duration_seconds: float = 12.0,
    story_brief: dict[str, Any] | None = None,
    narration_provider: str = "elevenlabs",
) -> StoryPackage:
    root = Path(project_root).resolve()
    brief = dict(story_brief or {})
    blueprint = build_story_blueprint(topic=topic, clip_count=clip_count, story_brief=story_brief)
    characters = build_character_profiles(blueprint=blueprint, topic=topic, story_brief=brief)
    performance_profiles = build_character_performance_profiles(characters)
    dialogue = naturalize_dialogue_plan(
        dialogue_plan=build_dialogue_plan(blueprint=blueprint, characters=characters, clip_count=clip_count),
        characters=characters,
        genre=blueprint.genre,
    )
    visual_bundle = build_story_visual_bundle(
        blueprint=blueprint,
        dialogue_plan=dialogue,
        clip_count=clip_count,
        story_brief=brief,
    )
    blueprint.scene_progression = list(visual_bundle.scene_progression)
    if run_id:
        save_story_visual_artifacts(project_root=root, run_id=str(run_id), bundle=visual_bundle)
    story_emotion: StoryEmotionArc = build_story_emotion_arc(blueprint=blueprint, dialogue_plan=dialogue)
    emotion = story_emotion.emotion_plan
    voice_cast_payload = apply_voice_identity_registry(
        project_root=root,
        voice_cast_plan=build_voice_cast_plan(
            project_root=root,
            characters=characters,
            dialogue_plan=dialogue,
            provider=narration_provider,
        ).to_dict(),
        provider=narration_provider,
        run_id=str(run_id or ""),
        topic=str(topic or ""),
    )
    voice_cast = VoiceCastPlan(
        narrator=dict(voice_cast_payload.get("narrator") or {}),
        characters=[dict(item) for item in (voice_cast_payload.get("characters") or []) if isinstance(item, dict)],
        provider=str(voice_cast_payload.get("provider") or narration_provider),
        multi_track=bool(voice_cast_payload.get("multi_track")),
        warnings=list(voice_cast_payload.get("warnings") or []),
    )
    environment_base = build_environment_plan(project_root=root, blueprint=blueprint, topic=topic)
    presence = enhance_environment_presence(environment_base)
    environment = presence.environment_plan
    music_base = build_music_plan(blueprint=blueprint, emotion_plan=emotion, duration_seconds=duration_seconds)
    mood = select_music_mood(project_root=root, blueprint=blueprint, emotion_plan=emotion)
    music = MusicPlan(
        mood=mood.mood,
        track_hint=mood.track_path or music_base.track_hint,
        intensity_curve=music_base.intensity_curve,
        scene_transitions=music_base.scene_transitions,
        climax_boost_db=music_base.climax_boost_db,
        ending_fade_seconds=music_base.ending_fade_seconds,
        ducking_under_dialogue=music_base.ducking_under_dialogue,
        metadata={
            **dict(music_base.metadata),
            "music_mood_selector": mood.to_dict(),
            "style_label": mood.style_label,
            "asset_quality": mood.asset_quality,
        },
    )
    sync_plan = build_scene_sync_plan(
        blueprint=blueprint,
        dialogue_plan=dialogue,
        duration_seconds=duration_seconds,
        emotion_beats=story_emotion.beats,
    )
    timeline = build_dialogue_timeline(
        dialogue_plan=dialogue,
        voice_cast_plan=voice_cast,
        duration_seconds=duration_seconds,
    )
    return StoryPackage(
        run_id=str(run_id or ""),
        topic=str(topic or ""),
        story_blueprint=blueprint,
        character_profiles=characters,
        dialogue_plan=dialogue,
        emotion_plan=emotion,
        voice_cast_plan=voice_cast,
        environment_plan=environment,
        music_plan=music,
        dialogue_timeline=timeline,
        metadata={
            "clip_count": clip_count,
            "duration_seconds": duration_seconds,
            "character_performance": [item.to_dict() for item in performance_profiles],
            "story_emotion_arc": story_emotion.to_dict(),
            "scene_sync_plan": sync_plan.to_dict(),
            "environment_presence_warnings": list(environment.warnings),
            "environment_mix_gain": presence.mix_gain,
            "environment_presence_score": presence.presence_score,
            "music_mood_warnings": list(mood.warnings),
            "story_visual_quality": visual_bundle.results_panel(),
            "story_visual_plan": visual_bundle.to_dict(),
        },
    )


def build_and_save_story_package(
    *,
    project_root: str | Path,
    topic: str,
    run_id: str = "",
    clip_count: int = 3,
    duration_seconds: float = 12.0,
    story_brief: dict[str, Any] | None = None,
    narration_provider: str = "elevenlabs",
    run_dir: str | Path | None = None,
) -> tuple[StoryPackage, Path]:
    package = build_story_package(
        project_root=project_root,
        topic=topic,
        run_id=run_id,
        clip_count=clip_count,
        duration_seconds=duration_seconds,
        story_brief=story_brief,
        narration_provider=narration_provider,
    )
    path = save_story_package(project_root, package)
    if run_id and run_dir:
        from content_brain.story.story_visual_orchestrator import build_story_visual_bundle, save_story_visual_artifacts

        visual_bundle = build_story_visual_bundle(
            blueprint=package.story_blueprint,
            dialogue_plan=package.dialogue_plan,
            clip_count=clip_count,
            story_brief=dict(story_brief or {}),
        )
        artifact_paths = save_story_visual_artifacts(
            project_root=project_root,
            run_id=str(run_id),
            bundle=visual_bundle,
            run_dir=run_dir,
        )
        package.metadata["story_visual_artifact_paths"] = artifact_paths
        save_story_package(project_root, package)
    return package, path


__all__ = [
    "STORY_PACKAGE_VERSION",
    "StoryPackage",
    "build_and_save_story_package",
    "build_story_package",
    "load_story_package",
    "save_story_package",
    "story_package_path",
]
