"""Story & Audio Quality Auditor — fail closed on missing cinematic elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

STORY_AUDIO_AUDITOR_VERSION = "story_audio_auditor_v1"


class _StoryPackageLike(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class StoryAudioAuditResult:
    status: str
    story_score: int
    dialogue_score: int
    emotion_score: int
    character_count: int
    voice_count: int
    checks: dict[str, bool]
    failures: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STORY_AUDIO_AUDITOR_VERSION,
            "status": self.status,
            "story_score": self.story_score,
            "dialogue_score": self.dialogue_score,
            "emotion_score": self.emotion_score,
            "character_count": self.character_count,
            "voice_count": self.voice_count,
            "checks": dict(self.checks),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
        }


def _has_story_arc(blueprint: dict[str, Any]) -> bool:
    required = ("hook", "setup", "conflict", "climax", "resolution")
    return all(str(blueprint.get(key) or "").strip() for key in required)


def _dialogue_lines(dialogue_plan: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for scene in dialogue_plan.get("scenes") or []:
        if isinstance(scene, dict):
            lines.extend(scene.get("dialogue_lines") or [])
    return lines


def audit_story_package(package: _StoryPackageLike | dict[str, Any]) -> StoryAudioAuditResult:
    payload = (
        package.to_dict()
        if hasattr(package, "to_dict") and callable(package.to_dict)
        else dict(package or {})
    )
    blueprint = dict(payload.get("story_blueprint") or {})
    characters = [item for item in (payload.get("character_profiles") or []) if isinstance(item, dict)]
    dialogue_plan = dict(payload.get("dialogue_plan") or {})
    emotion_plan = dict(payload.get("emotion_plan") or {})
    voice_cast = dict(payload.get("voice_cast_plan") or {})
    environment = dict(payload.get("environment_plan") or {})
    music = dict(payload.get("music_plan") or {})
    timeline = dict(payload.get("dialogue_timeline") or {})

    dialogue_lines = _dialogue_lines(dialogue_plan)
    quoted = [line for line in dialogue_lines if str(line.get("line") or "").strip()]
    non_narrator_chars = [c for c in characters if str(c.get("role") or "") != "narrator"]
    emotion_scenes = [s for s in (emotion_plan.get("scenes") or []) if isinstance(s, dict)]
    voice_rows = list(voice_cast.get("characters") or [])
    if voice_cast.get("narrator"):
        voice_rows = [voice_cast.get("narrator"), *voice_rows]

    checks = {
        "story_arc_exists": _has_story_arc(blueprint),
        "dialogue_exists": len(quoted) >= 2,
        "multiple_characters_exist": len(non_narrator_chars) >= 2,
        "emotion_progression_exists": len(emotion_scenes) >= 2 and bool(emotion_plan.get("arc_summary")),
        "ambience_exists": len(environment.get("ambience") or []) >= 1,
        "music_exists": bool(music.get("mood")) and len(music.get("intensity_curve") or []) >= 1,
        "voice_casting_exists": len(voice_rows) >= 2,
        "timeline_exists": len(timeline.get("tracks") or []) >= 2,
    }
    failures = [name for name, ok in checks.items() if not ok]
    warnings = list(voice_cast.get("warnings") or []) + list(environment.get("warnings") or [])

    story_score = sum(
        [
            25 if checks["story_arc_exists"] else 0,
            15 if len(blueprint.get("scene_progression") or []) >= 2 else 0,
            10 if str(blueprint.get("title") or "").strip() else 0,
        ]
    )
    dialogue_score = min(100, 20 * len(quoted) + (20 if checks["multiple_characters_exist"] else 0))
    emotion_score = min(100, 15 * len(emotion_scenes) + (25 if checks["emotion_progression_exists"] else 0))

    character_count = len(non_narrator_chars)
    voice_count = len({str(row.get("character") or row.get("speaker") or "").lower() for row in voice_rows if row})

    status = "PASS" if not failures else "FAIL"
    return StoryAudioAuditResult(
        status=status,
        story_score=min(100, story_score),
        dialogue_score=dialogue_score,
        emotion_score=emotion_score,
        character_count=character_count,
        voice_count=voice_count,
        checks=checks,
        failures=failures,
        warnings=warnings,
    )


def audit_story_package_dict(payload: dict[str, Any]) -> StoryAudioAuditResult:
    return audit_story_package(payload)


__all__ = [
    "STORY_AUDIO_AUDITOR_VERSION",
    "StoryAudioAuditResult",
    "audit_story_package",
    "audit_story_package_dict",
]
