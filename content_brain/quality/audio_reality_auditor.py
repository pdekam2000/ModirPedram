"""Real audio quality auditor — verifies files on disk, not metadata-only PASS."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.audio.music_runtime import probe_mean_volume_db

AUDIO_REALITY_AUDITOR_VERSION = "audio_reality_auditor_v1"
MIN_AUDIO_BYTES = 800
MIN_MEAN_DB = -45.0


@dataclass
class AudioRealityAuditResult:
    status: str
    quality_score: int
    checks: dict[str, bool]
    failures: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": AUDIO_REALITY_AUDITOR_VERSION,
            "status": self.status,
            "quality_score": self.quality_score,
            "checks": dict(self.checks),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
        }


def _file_ok(path_text: str, *, min_bytes: int = MIN_AUDIO_BYTES) -> bool:
    path = Path(str(path_text or ""))
    return path.is_file() and path.stat().st_size >= min_bytes


def audit_audio_reality(context: dict[str, Any]) -> AudioRealityAuditResult:
    dialogue_dir = Path(str(context.get("dialogue_dir") or ""))
    timeline_dir = Path(str(context.get("timeline_dir") or ""))
    speech = dict(context.get("speech_result") or {})
    clips = [item for item in (speech.get("clips") or []) if isinstance(item, dict)]
    speaker_files = dict(speech.get("speaker_files") or {})

    dialogue_mp3s = sorted(dialogue_dir.glob("*.mp3")) if dialogue_dir.is_dir() else []
    unique_speakers = len(speaker_files) if speaker_files else len({path.name.split("_")[0] for path in dialogue_mp3s})

    cinematic_audio = str(context.get("cinematic_audio_path") or "")
    cinematic_video = str(context.get("cinematic_video_path") or "")
    dialogue_timeline_path = timeline_dir / "dialogue_timeline.json"
    environment_timeline_path = timeline_dir / "environment_timeline.json"
    music_timeline_path = timeline_dir / "music_timeline.json"

    dialogue_timeline = dict(context.get("dialogue_timeline") or {})
    environment_timeline = dict(context.get("environment_timeline") or {})
    music_timeline = dict(context.get("music_timeline") or {})

    env_layers_with_files = [
        layer
        for layer in (environment_timeline.get("layers") or [])
        if isinstance(layer, dict) and _file_ok(str(layer.get("audio_path") or ""), min_bytes=400)
    ]
    music_track = str(music_timeline.get("track_path") or "")

    cinematic_mean = probe_mean_volume_db(Path(cinematic_audio)) if _file_ok(cinematic_audio) else None

    checks = {
        "dialogue_generated": len(clips) >= 2 and len(dialogue_mp3s) >= 2,
        "multiple_speakers_generated": unique_speakers >= 2,
        "multiple_voice_files_exist": len(dialogue_mp3s) >= 3,
        "environment_audio_exists": len(env_layers_with_files) >= 1,
        "music_exists": _file_ok(music_track, min_bytes=1000),
        "dialogue_timeline_exists": dialogue_timeline_path.is_file() and len(dialogue_timeline.get("lines") or []) >= 2,
        "environment_timeline_exists": environment_timeline_path.is_file(),
        "music_timeline_exists": music_timeline_path.is_file(),
        "final_cinematic_audio_exists": _file_ok(cinematic_audio),
        "final_cinematic_audio_audible": cinematic_mean is not None and cinematic_mean > MIN_MEAN_DB,
        "final_cinematic_video_exists": _file_ok(cinematic_video, min_bytes=5000),
    }

    failures = [name for name, ok in checks.items() if not ok]
    warnings: list[str] = []
    if cinematic_mean is not None and cinematic_mean <= MIN_MEAN_DB:
        warnings.append(f"cinematic_audio_quiet:{cinematic_mean:.1f}dB")

    passed = sum(1 for ok in checks.values() if ok)
    quality_score = int(round(100 * passed / max(1, len(checks))))

    return AudioRealityAuditResult(
        status="PASS" if not failures else "FAIL",
        quality_score=quality_score,
        checks=checks,
        failures=failures,
        warnings=warnings,
    )


__all__ = ["AUDIO_REALITY_AUDITOR_VERSION", "AudioRealityAuditResult", "audit_audio_reality"]
