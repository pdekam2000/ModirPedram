"""
Phase 11J-2 — Assembly artifact validator skeleton (no FFmpeg, no media probing).

Read-only existence checks over already-produced video, voice, and subtitle
artifacts plus their manifests. Returns READY / PARTIAL / FAILED. This module
never decodes media, never calls FFmpeg, and never mutates any slot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.assembly_models import (
    AssemblyValidationResult,
    VALIDATION_FAILED,
    VALIDATION_PARTIAL,
    VALIDATION_READY,
)

VALIDATION_VERSION = "11j2_v1"

_SUBTITLE_EXTENSIONS = frozenset({".srt", ".vtt", ".ass"})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _artifact_path(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("file_path") or raw.get("path") or "").strip()
    if isinstance(raw, str):
        return raw.strip()
    return ""


def _existing_paths(artifacts: list[Any]) -> list[str]:
    found: list[str] = []
    for raw in artifacts:
        path_text = _artifact_path(raw)
        if path_text and Path(path_text).is_file():
            found.append(path_text)
    return found


def _manifest_exists(manifest_path: Any) -> bool:
    path_text = str(manifest_path or "").strip()
    return bool(path_text) and Path(path_text).is_file()


class AssemblyArtifactValidator:
    """Validate presence of upstream artifacts/manifests without media probing."""

    def validate(
        self,
        *,
        video_artifacts: list[Any] | None = None,
        voice_artifacts: list[Any] | None = None,
        subtitle_artifacts: list[Any] | None = None,
        video_manifest_path: str | None = None,
        voice_manifest_path: str | None = None,
        subtitle_manifest_path: str | None = None,
        require_subtitles: bool = True,
    ) -> AssemblyValidationResult:
        missing: list[str] = []
        warnings: list[str] = []
        reject_reasons: list[str] = []

        video_files = _existing_paths(_list(video_artifacts))
        voice_files = _existing_paths(_list(voice_artifacts))
        subtitle_files = [
            path
            for path in _existing_paths(_list(subtitle_artifacts))
            if Path(path).suffix.lower() in _SUBTITLE_EXTENSIONS
        ]

        video_manifest_ok = video_manifest_path is None or _manifest_exists(video_manifest_path)
        voice_manifest_ok = voice_manifest_path is None or _manifest_exists(voice_manifest_path)
        subtitle_manifest_ok = subtitle_manifest_path is None or _manifest_exists(subtitle_manifest_path)

        if video_manifest_path is not None and not video_manifest_ok:
            warnings.append("video_manifest.json listed but not found")
        if voice_manifest_path is not None and not voice_manifest_ok:
            warnings.append("voice_manifest.json listed but not found")
        if subtitle_manifest_path is not None and not subtitle_manifest_ok:
            warnings.append("subtitle_manifest.json listed but not found")

        video_ok = bool(video_files) and video_manifest_ok
        voice_ok = bool(voice_files) and voice_manifest_ok
        subtitle_ok = bool(subtitle_files) and subtitle_manifest_ok

        if not video_files:
            missing.append("video")
        if not voice_files:
            missing.append("voice")
        if not subtitle_files:
            missing.append("subtitle")

        status = self._resolve_status(
            video_ok=video_ok,
            voice_ok=voice_ok,
            subtitle_ok=subtitle_ok,
            require_subtitles=require_subtitles,
            has_any=bool(video_files or voice_files or subtitle_files),
            reject_reasons=reject_reasons,
        )

        return AssemblyValidationResult(
            status=status,
            video_ok=video_ok,
            voice_ok=voice_ok,
            subtitle_ok=subtitle_ok,
            video_count=len(video_files),
            voice_count=len(voice_files),
            subtitle_count=len(subtitle_files),
            missing=missing,
            warnings=warnings,
            reject_reasons=reject_reasons,
        )

    def _resolve_status(
        self,
        *,
        video_ok: bool,
        voice_ok: bool,
        subtitle_ok: bool,
        require_subtitles: bool,
        has_any: bool,
        reject_reasons: list[str],
    ) -> str:
        # No usable video → FAILED (assembly cannot proceed without a base video track).
        if not video_ok:
            if not has_any:
                reject_reasons.append("No video, voice, or subtitle artifacts available.")
            else:
                reject_reasons.append("No usable video artifacts or video manifest missing.")
            return VALIDATION_FAILED

        required = [video_ok, voice_ok]
        if require_subtitles:
            required.append(subtitle_ok)

        if all(required):
            return VALIDATION_READY

        return VALIDATION_PARTIAL


__all__ = [
    "VALIDATION_VERSION",
    "AssemblyArtifactValidator",
]
