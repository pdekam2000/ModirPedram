"""
Phase 11J-4 — Assembly Plan Builder (pure planning layer, no FFmpeg).

Reads existing video/voice/subtitle artifacts + manifests (read-only) and produces
an ``AssemblyPlan`` describing *what* to assemble. It never decodes media, never
runs FFmpeg, never writes the final video, and never mutates upstream slots.

The future FFmpeg executor (11J-5) consumes the plan to decide *how* to assemble.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_artifact_validator import AssemblyArtifactValidator
from content_brain.execution.assembly_models import (
    EXPECTED_OUTPUT,
    MODE_VIDEO_ONLY,
    MODE_VIDEO_VOICE,
    MODE_VIDEO_VOICE_SUBTITLE,
    MODE_VOICE_ONLY,
    MUSIC_MODE_NONE,
    OUTPUT_VARIANT_PRIMARY,
    ROLE_CLIP,
    ROLE_MANIFEST,
    ROLE_NARRATION,
    ROLE_SUBTITLE_ASS,
    ROLE_SUBTITLE_SRT,
    ROLE_SUBTITLE_VTT,
    SUBTITLE_MODE_BURN_IN,
    SUBTITLE_MODE_NONE,
    SUBTITLE_MODE_SIDECAR,
    AssemblyInputArtifact,
    AssemblyPlan,
)
from content_brain.execution.category_runtime_compat import (
    ASSEMBLY_ARTIFACT_CATEGORY,
    get_category_slot,
)
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)

BUILDER_VERSION = "11j4_v1"

_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm"})
_AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".aac"})
_SUBTITLE_ROLE_BY_EXT = {
    ".ass": ROLE_SUBTITLE_ASS,
    ".srt": ROLE_SUBTITLE_SRT,
    ".vtt": ROLE_SUBTITLE_VTT,
}
# Subtitle format priority: ass > srt > vtt.
_SUBTITLE_PRIORITY = (".ass", ".srt", ".vtt")

_INDEX_RE = re.compile(r"(\d+)")


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


def _abs(path_text: str) -> str:
    try:
        return str(Path(path_text).resolve())
    except (OSError, ValueError):
        return path_text


def _clip_index(name: str) -> tuple[int, str]:
    match = _INDEX_RE.search(name)
    index = int(match.group(1)) if match else 1_000_000
    return index, name.lower()


def _read_json(path_text: str | None) -> dict[str, Any] | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_manifest_path(slot: dict[str, Any], artifacts: list[Any], hint: str, *fields: str) -> str | None:
    for field_name in fields:
        value = str(slot.get(field_name) or "").strip()
        if value:
            return value
    for raw in artifacts:
        path_text = _artifact_path(raw)
        if path_text and Path(path_text).name.lower() == hint.lower():
            return path_text
    return None


class AssemblyPlanBuilder:
    """Build a pure-data ``AssemblyPlan`` from a session (read-only, no FFmpeg)."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self._project_root = Path(project_root).resolve()
        self._validator = AssemblyArtifactValidator()

    def build(
        self,
        session: dict[str, Any],
        *,
        assembly_mode: str | None = None,
        subtitle_mode: str | None = None,
        require_subtitles: bool = True,
        output_variant: str = OUTPUT_VARIANT_PRIMARY,
        language: str | None = None,
    ) -> AssemblyPlan:
        session = _dict(session)
        session_id = str(
            session.get("execution_session_id") or session.get("session_id") or "unknown"
        )
        runtime = _dict(session.get("execution_runtime"))
        by_category = _dict(runtime.get("artifacts_by_category"))

        video_slot = get_category_slot(session, CATEGORY_VIDEO)
        voice_slot = get_category_slot(session, CATEGORY_VOICE)
        subtitle_slot = get_category_slot(session, CATEGORY_SUBTITLE_GENERATION)

        warnings: list[str] = []

        # ---- Video selection (ordered by clip index, deduped by abs path) ----
        video_raw = _list(by_category.get(CATEGORY_VIDEO)) + _list(video_slot.get("artifacts"))
        video_inputs = self._select_video(video_raw)
        video_manifest_path = _resolve_manifest_path(
            video_slot, video_raw, "video_manifest.json", "video_manifest_path", "manifest_path"
        )

        # ---- Voice selection (ordered by segment_index/beat_id, deduped) ----
        voice_manifest_path = _resolve_manifest_path(
            voice_slot,
            _list(by_category.get(CATEGORY_VOICE)) + _list(voice_slot.get("artifacts")),
            "voice_manifest.json",
            "voice_manifest_path",
            "manifest_path",
        )
        voice_manifest = _read_json(voice_manifest_path)
        voice_raw = _list(by_category.get(CATEGORY_VOICE)) + _list(voice_slot.get("artifacts"))
        audio_inputs = self._select_voice(voice_raw, voice_manifest)

        # ---- Subtitle selection (priority ass > srt > vtt) ----
        subtitle_manifest_path = _resolve_manifest_path(
            subtitle_slot,
            _list(by_category.get(CATEGORY_SUBTITLE_GENERATION))
            + _list(by_category.get("subtitles"))
            + _list(subtitle_slot.get("artifacts")),
            "subtitle_manifest.json",
            "manifest_path",
        )
        subtitle_manifest = _read_json(subtitle_manifest_path)
        subtitle_raw = (
            _list(by_category.get(CATEGORY_SUBTITLE_GENERATION))
            + _list(by_category.get("subtitles"))
            + _list(subtitle_slot.get("artifacts"))
        )
        chosen_subtitle, available_exts = self._select_subtitle(subtitle_raw, subtitle_manifest)

        # ---- Subtitle mode ----
        resolved_subtitle_mode = self._resolve_subtitle_mode(
            subtitle_mode, chosen_subtitle, available_exts
        )

        # ---- Validation (full-pipeline readiness) ----
        result = self._validator.validate(
            video_artifacts=video_raw,
            voice_artifacts=voice_raw,
            subtitle_artifacts=subtitle_raw,
            video_manifest_path=video_manifest_path,
            voice_manifest_path=voice_manifest_path,
            subtitle_manifest_path=subtitle_manifest_path,
            require_subtitles=require_subtitles,
        )

        has_video = result.video_count > 0
        has_voice = result.voice_count > 0
        has_subtitle = chosen_subtitle is not None

        # ---- Assembly mode ----
        resolved_mode = self._resolve_assembly_mode(
            assembly_mode, has_video=has_video, has_voice=has_voice, has_subtitle=has_subtitle
        )

        # ---- Warnings ----
        if video_manifest_path is None or not Path(str(video_manifest_path)).is_file():
            warnings.append("video_manifest.json missing or not listed")
        if has_voice and (voice_manifest_path is None or not Path(str(voice_manifest_path)).is_file()):
            warnings.append("voice_manifest.json missing or not listed")
        if has_subtitle and (
            subtitle_manifest_path is None or not Path(str(subtitle_manifest_path)).is_file()
        ):
            warnings.append("subtitle_manifest.json missing or not listed")

        clip_count = sum(1 for item in video_inputs if item.role == ROLE_CLIP)
        narration_count = sum(1 for item in audio_inputs if item.role == ROLE_NARRATION)
        if has_video and has_voice and clip_count and narration_count and clip_count != narration_count:
            warnings.append(
                f"clip/narration count mismatch (clips={clip_count}, narration={narration_count})"
            )
        if resolved_subtitle_mode == SUBTITLE_MODE_SIDECAR and chosen_subtitle is not None:
            warnings.append("ASS subtitle unavailable; planning sidecar mux for SRT/VTT")
        for category in result.missing:
            warnings.append(f"missing input group: {category}")
        for warn in result.warnings:
            if warn not in warnings:
                warnings.append(warn)

        # ---- Subtitle inputs (chosen file + manifest) ----
        subtitle_inputs: list[AssemblyInputArtifact] = []
        if chosen_subtitle is not None:
            subtitle_inputs.append(chosen_subtitle)
        if subtitle_manifest_path and Path(subtitle_manifest_path).is_file():
            subtitle_inputs.append(
                self._manifest_input(CATEGORY_SUBTITLE_GENERATION, subtitle_manifest_path)
            )

        if video_manifest_path and Path(video_manifest_path).is_file():
            video_inputs.append(self._manifest_input(CATEGORY_VIDEO, video_manifest_path))
        if voice_manifest_path and Path(voice_manifest_path).is_file():
            audio_inputs.append(self._manifest_input(CATEGORY_VOICE, voice_manifest_path))

        # ---- Output planning (no directory/file creation) ----
        output_dir = str(
            self._project_root
            / "storage"
            / "content_brain"
            / "execution"
            / "artifacts"
            / session_id
            / ASSEMBLY_ARTIFACT_CATEGORY
        )

        return AssemblyPlan(
            session_id=session_id,
            video_inputs=video_inputs,
            audio_inputs=audio_inputs,
            subtitle_inputs=subtitle_inputs,
            assembly_mode=resolved_mode,
            subtitle_mode=resolved_subtitle_mode,
            expected_output=EXPECTED_OUTPUT,
            output_dir=output_dir,
            validation_status=result.status,
            warnings=warnings,
            output_variant=output_variant,
            output_targets=[{"variant": output_variant, "file_name": EXPECTED_OUTPUT}],
            music_inputs=[],
            music_mode=MUSIC_MODE_NONE,
            language=language,
        )

    # ------------------------------------------------------------------ #

    def _select_video(self, raw: list[Any]) -> list[AssemblyInputArtifact]:
        seen: set[str] = set()
        selected: list[AssemblyInputArtifact] = []
        for entry in raw:
            path_text = _artifact_path(entry)
            if not path_text:
                continue
            path = Path(path_text)
            if path.suffix.lower() not in _VIDEO_EXTENSIONS:
                continue
            key = _abs(path_text)
            if key in seen:
                continue
            seen.add(key)
            selected.append(
                AssemblyInputArtifact(
                    category=CATEGORY_VIDEO,
                    file_path=key,
                    role=ROLE_CLIP,
                    exists=path.is_file(),
                    file_name=path.name,
                )
            )
        selected.sort(key=lambda item: _clip_index(item.file_name or ""))
        return selected

    def _select_voice(
        self, raw: list[Any], manifest: dict[str, Any] | None
    ) -> list[AssemblyInputArtifact]:
        ordered_paths: list[str] = []
        if manifest:
            files = _list(manifest.get("files"))

            def _seg_key(record: Any) -> tuple[int, str]:
                rec = _dict(record)
                seg = rec.get("segment_index")
                seg_index = int(seg) if isinstance(seg, (int, float)) else 1_000_000
                return seg_index, str(rec.get("beat_id") or "")

            for record in sorted(files, key=_seg_key):
                path_text = _artifact_path(record)
                if path_text:
                    ordered_paths.append(path_text)

        # Append any raw artifacts not already represented (preserves order).
        for entry in raw:
            path_text = _artifact_path(entry)
            if path_text:
                ordered_paths.append(path_text)

        seen: set[str] = set()
        selected: list[AssemblyInputArtifact] = []
        for path_text in ordered_paths:
            path = Path(path_text)
            if path.suffix.lower() not in _AUDIO_EXTENSIONS:
                continue
            key = _abs(path_text)
            if key in seen:
                continue
            seen.add(key)
            selected.append(
                AssemblyInputArtifact(
                    category=CATEGORY_VOICE,
                    file_path=key,
                    role=ROLE_NARRATION,
                    exists=path.is_file(),
                    file_name=path.name,
                )
            )
        return selected

    def _select_subtitle(
        self, raw: list[Any], manifest: dict[str, Any] | None
    ) -> tuple[AssemblyInputArtifact | None, set[str]]:
        by_ext: dict[str, str] = {}

        if manifest:
            for record in _list(manifest.get("files")):
                rec = _dict(record)
                path_text = _artifact_path(rec)
                if not path_text:
                    continue
                ext = Path(path_text).suffix.lower()
                if ext in _SUBTITLE_ROLE_BY_EXT and ext not in by_ext:
                    by_ext[ext] = path_text

        for entry in raw:
            path_text = _artifact_path(entry)
            if not path_text:
                continue
            ext = Path(path_text).suffix.lower()
            if ext in _SUBTITLE_ROLE_BY_EXT and ext not in by_ext:
                by_ext[ext] = path_text

        available = {ext for ext, p in by_ext.items() if Path(p).is_file()}

        for ext in _SUBTITLE_PRIORITY:
            path_text = by_ext.get(ext)
            if path_text and Path(path_text).is_file():
                path = Path(path_text)
                return (
                    AssemblyInputArtifact(
                        category=CATEGORY_SUBTITLE_GENERATION,
                        file_path=_abs(path_text),
                        role=_SUBTITLE_ROLE_BY_EXT[ext],
                        exists=True,
                        file_name=path.name,
                    ),
                    available,
                )
        return None, available

    def _resolve_subtitle_mode(
        self,
        requested: str | None,
        chosen: AssemblyInputArtifact | None,
        available_exts: set[str],
    ) -> str:
        if requested in (SUBTITLE_MODE_BURN_IN, SUBTITLE_MODE_SIDECAR, SUBTITLE_MODE_NONE):
            return requested
        if chosen is None:
            return SUBTITLE_MODE_NONE
        if ".ass" in available_exts:
            return SUBTITLE_MODE_BURN_IN
        return SUBTITLE_MODE_SIDECAR

    def _resolve_assembly_mode(
        self,
        requested: str | None,
        *,
        has_video: bool,
        has_voice: bool,
        has_subtitle: bool,
    ) -> str:
        if requested:
            return requested
        if has_video and has_voice and has_subtitle:
            return MODE_VIDEO_VOICE_SUBTITLE
        if has_video and has_voice:
            return MODE_VIDEO_VOICE
        if has_video:
            return MODE_VIDEO_ONLY
        if has_voice:
            return MODE_VOICE_ONLY
        return MODE_VIDEO_ONLY

    def _manifest_input(self, category: str, path_text: str) -> AssemblyInputArtifact:
        path = Path(path_text)
        return AssemblyInputArtifact(
            category=category,
            file_path=_abs(path_text),
            role=ROLE_MANIFEST,
            exists=path.is_file(),
            file_name=path.name,
            is_manifest=True,
        )


__all__ = [
    "BUILDER_VERSION",
    "AssemblyPlanBuilder",
]
