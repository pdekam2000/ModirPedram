"""
Phase 11J-2 — Assembly Runtime data models (no FFmpeg, no media processing).

Pure dataclasses describing *what* an assembly run would consume and produce.
The future FFmpeg executor (11J-4) operates exclusively from an ``AssemblyPlan``,
keeping this foundation testable without any media binaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

PLAN_VERSION = "11j2_v1"
MANIFEST_VERSION = "11j_v1"
ASSEMBLY_VERSION = "11j2_v1"
ASSEMBLY_PROVIDER = "local_assembly_runtime"
EXPECTED_OUTPUT = "FINAL_PUBLISH_READY.mp4"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Assembly modes (design-only; only video_voice_subtitle is the V1 target).
MODE_VIDEO_VOICE_SUBTITLE = "video_voice_subtitle"
MODE_VIDEO_VOICE = "video_voice"
MODE_VIDEO_ONLY = "video_only"
MODE_VOICE_ONLY = "voice_only"
MODE_MULTI_LANGUAGE_AUDIO = "multi_language_audio"
MODE_MULTI_SUBTITLE_TRACK = "multi_subtitle_track"

ASSEMBLY_MODES = (
    MODE_VIDEO_VOICE_SUBTITLE,
    MODE_VIDEO_VOICE,
    MODE_VIDEO_ONLY,
    MODE_VOICE_ONLY,
    MODE_MULTI_LANGUAGE_AUDIO,
    MODE_MULTI_SUBTITLE_TRACK,
)

# Subtitle sub-modes.
SUBTITLE_MODE_BURN_IN = "burn_in"
SUBTITLE_MODE_SIDECAR = "sidecar"
SUBTITLE_MODE_NONE = "none"

SUBTITLE_MODES = (SUBTITLE_MODE_BURN_IN, SUBTITLE_MODE_SIDECAR, SUBTITLE_MODE_NONE)

# Validation status values (read-only artifact checks).
VALIDATION_READY = "READY"
VALIDATION_PARTIAL = "PARTIAL"
VALIDATION_FAILED = "FAILED"

# Artifact roles.
ROLE_CLIP = "clip"
ROLE_NARRATION = "narration"
ROLE_SUBTITLE_SRT = "subtitle_srt"
ROLE_SUBTITLE_VTT = "subtitle_vtt"
ROLE_SUBTITLE_ASS = "subtitle_ass"
ROLE_MANIFEST = "manifest"
ROLE_MUSIC = "music"

# Output variants (design-only; primary is the V1 target).
OUTPUT_VARIANT_PRIMARY = "primary"
OUTPUT_VARIANT_VERTICAL = "vertical"
OUTPUT_VARIANT_HORIZONTAL = "horizontal"

# Music layer modes (future).
MUSIC_MODE_NONE = "none"
MUSIC_MODE_BED = "bed"
MUSIC_MODE_DUCKED = "ducked"


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


@dataclass
class AssemblyInputArtifact:
    """A single upstream artifact (read-only) considered for assembly."""

    category: str
    file_path: str
    role: str
    exists: bool = False
    file_name: str | None = None
    is_manifest: bool = False
    # Future-safe (multi-language audio / subtitle tracks). Additive, default None.
    language: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "role": self.role,
            "exists": bool(self.exists),
            "is_manifest": bool(self.is_manifest),
            "language": self.language,
        }


@dataclass
class AssemblyPlan:
    """Pure description of an assembly run — consumed by the future executor."""

    session_id: str
    video_inputs: list[AssemblyInputArtifact] = field(default_factory=list)
    audio_inputs: list[AssemblyInputArtifact] = field(default_factory=list)
    subtitle_inputs: list[AssemblyInputArtifact] = field(default_factory=list)
    assembly_mode: str = MODE_VIDEO_VOICE_SUBTITLE
    subtitle_mode: str = SUBTITLE_MODE_BURN_IN
    expected_output: str = EXPECTED_OUTPUT
    output_dir: str | None = None
    validation_status: str = VALIDATION_FAILED
    warnings: list[str] = field(default_factory=list)
    plan_version: str = PLAN_VERSION
    # Future-safe fields (additive, safe defaults — see 11J-3 design §7).
    output_variant: str = OUTPUT_VARIANT_PRIMARY
    output_targets: list[dict[str, Any]] = field(default_factory=list)
    music_inputs: list[AssemblyInputArtifact] = field(default_factory=list)
    music_mode: str = MUSIC_MODE_NONE
    language: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_version": self.plan_version,
            "session_id": self.session_id,
            "assembly_mode": self.assembly_mode,
            "subtitle_mode": self.subtitle_mode,
            "expected_output": self.expected_output,
            "output_dir": self.output_dir,
            "validation_status": self.validation_status,
            "video_inputs": [item.to_dict() for item in self.video_inputs],
            "audio_inputs": [item.to_dict() for item in self.audio_inputs],
            "subtitle_inputs": [item.to_dict() for item in self.subtitle_inputs],
            "warnings": list(self.warnings),
            "output_variant": self.output_variant,
            "output_targets": list(self.output_targets),
            "music_inputs": [item.to_dict() for item in self.music_inputs],
            "music_mode": self.music_mode,
            "language": self.language,
        }


@dataclass
class AssemblyValidationResult:
    """Outcome of read-only upstream artifact validation (no FFmpeg)."""

    status: str = VALIDATION_FAILED
    video_ok: bool = False
    voice_ok: bool = False
    subtitle_ok: bool = False
    video_count: int = 0
    voice_count: int = 0
    subtitle_count: int = 0
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reject_reasons: list[str] = field(default_factory=list)
    validated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "video_ok": bool(self.video_ok),
            "voice_ok": bool(self.voice_ok),
            "subtitle_ok": bool(self.subtitle_ok),
            "video_count": int(self.video_count),
            "voice_count": int(self.voice_count),
            "subtitle_count": int(self.subtitle_count),
            "missing": list(self.missing),
            "warnings": list(self.warnings),
            "reject_reasons": list(self.reject_reasons),
            "validated_at": self.validated_at,
        }


@dataclass
class AssemblyManifestSkeleton:
    """In-memory ``assembly_manifest.json`` skeleton — not written in 11J-2."""

    session_id: str
    assembly_mode: str = MODE_VIDEO_VOICE_SUBTITLE
    subtitle_mode: str = SUBTITLE_MODE_BURN_IN
    input_artifacts: dict[str, list[str]] = field(
        default_factory=lambda: {"video": [], "voice": [], "subtitle": []}
    )
    output_artifacts: list[dict[str, Any]] = field(default_factory=list)
    validation_status: str = VALIDATION_FAILED
    warnings: list[str] = field(default_factory=list)
    provider: str = ASSEMBLY_PROVIDER
    real_assembly_executed: bool = False
    generated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": MANIFEST_VERSION,
            "assembly_version": ASSEMBLY_VERSION,
            "session_id": self.session_id,
            "category": "assembly_generation",
            "provider": self.provider,
            "assembly_mode": self.assembly_mode,
            "subtitle_mode": self.subtitle_mode,
            "input_artifacts": {
                "video": list(self.input_artifacts.get("video", [])),
                "voice": list(self.input_artifacts.get("voice", [])),
                "subtitle": list(self.input_artifacts.get("subtitle", [])),
            },
            "output_artifacts": list(self.output_artifacts),
            "validation_status": self.validation_status,
            "duration_seconds": None,
            "started_at": None,
            "completed_at": None,
            "generated_at": self.generated_at,
            "real_assembly_executed": bool(self.real_assembly_executed),
            "warnings": list(self.warnings),
        }


__all__ = [
    "PLAN_VERSION",
    "MANIFEST_VERSION",
    "ASSEMBLY_VERSION",
    "ASSEMBLY_PROVIDER",
    "EXPECTED_OUTPUT",
    "MODE_VIDEO_VOICE_SUBTITLE",
    "MODE_VIDEO_VOICE",
    "MODE_VIDEO_ONLY",
    "MODE_VOICE_ONLY",
    "MODE_MULTI_LANGUAGE_AUDIO",
    "MODE_MULTI_SUBTITLE_TRACK",
    "ASSEMBLY_MODES",
    "SUBTITLE_MODE_BURN_IN",
    "SUBTITLE_MODE_SIDECAR",
    "SUBTITLE_MODE_NONE",
    "SUBTITLE_MODES",
    "VALIDATION_READY",
    "VALIDATION_PARTIAL",
    "VALIDATION_FAILED",
    "ROLE_CLIP",
    "ROLE_NARRATION",
    "ROLE_SUBTITLE_SRT",
    "ROLE_SUBTITLE_VTT",
    "ROLE_SUBTITLE_ASS",
    "ROLE_MANIFEST",
    "ROLE_MUSIC",
    "OUTPUT_VARIANT_PRIMARY",
    "OUTPUT_VARIANT_VERTICAL",
    "OUTPUT_VARIANT_HORIZONTAL",
    "MUSIC_MODE_NONE",
    "MUSIC_MODE_BED",
    "MUSIC_MODE_DUCKED",
    "AssemblyInputArtifact",
    "AssemblyPlan",
    "AssemblyValidationResult",
    "AssemblyManifestSkeleton",
]
