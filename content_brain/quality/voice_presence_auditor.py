"""Voice presence auditor — multiple distinct speakers, not single narration track."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VOICE_PRESENCE_AUDITOR_VERSION = "voice_presence_auditor_v1"


@dataclass
class VoicePresenceAuditResult:
    status: str
    speaker_count: int
    voice_count: int
    character_count: int
    detected_speakers: list[str]
    checks: dict[str, bool]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": VOICE_PRESENCE_AUDITOR_VERSION,
            "status": self.status,
            "speaker_count": self.speaker_count,
            "voice_count": self.voice_count,
            "character_count": self.character_count,
            "detected_speakers": list(self.detected_speakers),
            "checks": dict(self.checks),
            "failures": list(self.failures),
        }


def _speaker_from_filename(name: str) -> str:
    stem = Path(name).stem
    match = re.match(r"^([a-z0-9]+)_\d+$", stem.lower())
    return match.group(1) if match else stem.lower()


def audit_voice_presence(context: dict[str, Any]) -> VoicePresenceAuditResult:
    dialogue_dir = Path(str(context.get("dialogue_dir") or ""))
    speech = dict(context.get("speech_result") or {})
    performance = dict(context.get("performance_plan") or {})

    clip_speakers = {
        str(item.get("speaker") or "").strip()
        for item in (speech.get("clips") or [])
        if isinstance(item, dict) and str(item.get("speaker") or "").strip()
    }
    perf_speakers = {
        str(item.get("speaker") or "").strip()
        for item in (performance.get("lines") or [])
        if isinstance(item, dict) and str(item.get("speaker") or "").strip()
    }
    file_speakers = {_speaker_from_filename(path.name) for path in dialogue_dir.glob("*.mp3")} if dialogue_dir.is_dir() else set()

    detected = sorted({speaker for speaker in clip_speakers | perf_speakers if speaker})
    slug_map = {speaker.lower(): _speaker_from_filename(f"{speaker.lower()}_001.mp3") for speaker in detected}
    detected_slugs = sorted(set(file_speakers) | set(slug_map.values()))

    non_narrator = [speaker for speaker in detected if speaker.lower() != "narrator"]
    speaker_count = len(detected)
    voice_count = len(detected_slugs)
    character_count = len(non_narrator)

    checks = {
        "speaker_count_gt_1": speaker_count > 1,
        "multiple_character_voices": character_count >= 2,
        "narrator_present": any(speaker.lower() == "narrator" for speaker in detected),
        "distinct_voice_files": voice_count >= 2,
        "not_single_narration_track": len(list(dialogue_dir.glob("*.mp3"))) >= 3 if dialogue_dir.is_dir() else False,
    }

    failures = [name for name, ok in checks.items() if not ok]
    return VoicePresenceAuditResult(
        status="PASS" if not failures else "FAIL",
        speaker_count=speaker_count,
        voice_count=voice_count,
        character_count=character_count,
        detected_speakers=detected,
        checks=checks,
        failures=failures,
    )


__all__ = ["VOICE_PRESENCE_AUDITOR_VERSION", "VoicePresenceAuditResult", "audit_voice_presence"]
