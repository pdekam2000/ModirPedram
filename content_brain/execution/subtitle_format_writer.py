"""
Phase 11I-6 — subtitle format writers (SRT / VTT / ASS + manifest).

No FFmpeg, no legacy subtitle_engine imports, no video modification.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.category_runtime_compat import SUBTITLE_ARTIFACT_CATEGORY
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.subtitle_artifact_validator import SubtitleArtifactValidator
from content_brain.execution.subtitle_cue_validator import SubtitleCueValidator
from content_brain.execution.subtitle_models import SubtitleCue, SubtitleCueBatch

WRITER_VERSION = "11i6_v1"
MANIFEST_VERSION = "11i_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

SUPPORTED_FORMATS = frozenset({"srt", "ass", "vtt"})
DEFAULT_FORMATS = ("srt", "ass", "vtt")
DEFAULT_FILENAMES = {
    "srt": "subtitles.srt",
    "ass": "subtitles.ass",
    "vtt": "subtitles.vtt",
}
MANIFEST_FILENAME = "subtitle_manifest.json"

ASS_HEADER = """[Script Info]
Title: ModirAgentOS Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,4,0,2,80,80,220,1
Style: Emphasis,Arial,72,&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,110,110,0,0,1,4,0,2,80,80,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clamp_seconds(seconds: float) -> float:
    return max(0.0, float(seconds))


def format_srt_timestamp(seconds: float) -> str:
    total_ms = int(round(_clamp_seconds(seconds) * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def format_vtt_timestamp(seconds: float) -> str:
    total_ms = int(round(_clamp_seconds(seconds) * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{ms:03}"


def format_ass_timestamp(seconds: float) -> str:
    total_cs = int(round(_clamp_seconds(seconds) * 100))
    hours, rem = divmod(total_cs, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"


def render_srt(batch: SubtitleCueBatch) -> str:
    blocks: list[str] = []
    for cue in batch.cues:
        blocks.append(str(cue.index))
        blocks.append(
            f"{format_srt_timestamp(cue.start_time)} --> {format_srt_timestamp(cue.end_time)}"
        )
        blocks.append(cue.text)
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def render_vtt(batch: SubtitleCueBatch) -> str:
    lines = ["WEBVTT", ""]
    for cue in batch.cues:
        lines.append(
            f"{format_vtt_timestamp(cue.start_time)} --> {format_vtt_timestamp(cue.end_time)}"
        )
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def apply_ass_highlights(text: str, highlight_terms: list[str]) -> str:
    styled = str(text or "")
    for term in highlight_terms:
        cleaned = str(term or "").strip()
        if not cleaned:
            continue
        pattern = re.compile(re.escape(cleaned), re.IGNORECASE)
        styled = pattern.sub(
            lambda match: (
                r"{\c&H00FFFF&\b1\fscx110\fscy110}"
                + match.group(0)
                + r"{\r}"
            ),
            styled,
            count=1,
        )
    return r"{\fad(80,80)}" + styled


def render_ass(batch: SubtitleCueBatch, profile: dict[str, Any] | None = None) -> str:
    _ = _dict(profile)
    events: list[str] = []
    for cue in batch.cues:
        styled = apply_ass_highlights(cue.text, cue.highlight_terms)
        events.append(
            "Dialogue: 0,"
            f"{format_ass_timestamp(cue.start_time)},"
            f"{format_ass_timestamp(cue.end_time)},"
            "Default,,0,0,0,,"
            f"{styled}"
        )
    return ASS_HEADER + "\n".join(events) + "\n"


def _render_format(batch: SubtitleCueBatch, fmt: str, profile: dict[str, Any] | None) -> str:
    if fmt == "srt":
        return render_srt(batch)
    if fmt == "vtt":
        return render_vtt(batch)
    if fmt == "ass":
        return render_ass(batch, profile)
    raise ValueError(f"Unsupported format: {fmt}")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


@dataclass
class SubtitleWriteRequest:
    batch: SubtitleCueBatch
    session_id: str
    artifact_dir: Path | None = None
    formats: list[str] | None = None
    overwrite: bool = False
    profile: dict[str, Any] | None = None
    voice_manifest_ref: str | None = None
    narration_source_path: str | None = None


@dataclass
class SubtitleFileRecord:
    format: str
    file_name: str
    file_path: str
    size_bytes: int
    cue_count: int
    validation_status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "cue_count": self.cue_count,
            "validation_status": self.validation_status,
        }


@dataclass
class SubtitleWriteResult:
    passed: bool
    written_at: str
    writer_version: str = WRITER_VERSION
    session_id: str = ""
    artifact_dir: str = ""
    formats_written: list[str] = field(default_factory=list)
    files: list[SubtitleFileRecord] = field(default_factory=list)
    manifest_path: str | None = None
    manifest: dict[str, Any] | None = None
    validation_status: str = "invalid"
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "written_at": self.written_at,
            "writer_version": self.writer_version,
            "session_id": self.session_id,
            "artifact_dir": self.artifact_dir,
            "formats_written": list(self.formats_written),
            "files": [item.to_dict() for item in self.files],
            "manifest_path": self.manifest_path,
            "manifest": dict(self.manifest or {}),
            "validation_status": self.validation_status,
            "reject_code": self.reject_code,
            "reject_reasons": list(self.reject_reasons),
            "warnings": list(self.warnings),
        }


class SubtitleFormatWriter:
    """Write subtitle sidecar files from a validated cue batch."""

    def __init__(
        self,
        store: ExecutionSessionStore | None = None,
        project_root: str | Path = ".",
    ):
        self.project_root = Path(project_root).resolve()
        self.store = store or ExecutionSessionStore(self.project_root)
        self.cue_validator = SubtitleCueValidator()
        self.artifact_validator = SubtitleArtifactValidator()

    def write(self, request: SubtitleWriteRequest) -> SubtitleWriteResult:
        written_at = _now()
        session_id = str(request.session_id or "").strip()
        if not session_id:
            return SubtitleWriteResult(
                passed=False,
                written_at=written_at,
                reject_code="SESSION_ID_REQUIRED",
                reject_reasons=["session_id is required."],
            )

        batch = request.batch
        cue_validation = self.cue_validator.validate(batch)
        if not cue_validation.passed:
            return SubtitleWriteResult(
                passed=False,
                written_at=written_at,
                session_id=session_id,
                reject_code="CUE_BATCH_INVALID",
                reject_reasons=list(cue_validation.reject_reasons),
                warnings=list(cue_validation.warnings),
            )

        formats = [str(fmt).lower().strip() for fmt in (request.formats or list(DEFAULT_FORMATS))]
        unsupported = [fmt for fmt in formats if fmt not in SUPPORTED_FORMATS]
        if unsupported:
            return SubtitleWriteResult(
                passed=False,
                written_at=written_at,
                session_id=session_id,
                reject_code="UNSUPPORTED_FORMAT",
                reject_reasons=[f"Unsupported format(s): {', '.join(unsupported)}"],
            )

        artifact_dir = request.artifact_dir or self.store.artifact_dir(
            session_id,
            SUBTITLE_ARTIFACT_CATEGORY,
        )
        artifact_dir = Path(artifact_dir).resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)

        target_paths = {fmt: artifact_dir / DEFAULT_FILENAMES[fmt] for fmt in formats}
        manifest_path = artifact_dir / MANIFEST_FILENAME

        if not request.overwrite:
            existing = [path for path in (*target_paths.values(), manifest_path) if path.is_file()]
            if existing:
                return SubtitleWriteResult(
                    passed=False,
                    written_at=written_at,
                    session_id=session_id,
                    artifact_dir=str(artifact_dir),
                    reject_code="FILE_EXISTS",
                    reject_reasons=[f"File exists: {path.name}" for path in existing],
                )

        written_paths: list[Path] = []
        file_records: list[SubtitleFileRecord] = []
        artifact_payloads: list[dict[str, Any]] = []

        try:
            for fmt in formats:
                path = target_paths[fmt]
                content = _render_format(batch, fmt, request.profile)
                atomic_write_text(path, content)
                written_paths.append(path)
                size_bytes = path.stat().st_size
                record = SubtitleFileRecord(
                    format=fmt,
                    file_name=path.name,
                    file_path=str(path.resolve()),
                    size_bytes=size_bytes,
                    cue_count=batch.cue_count,
                    validation_status="pending",
                )
                file_records.append(record)
                artifact_payloads.append(
                    {
                        "format": fmt,
                        "file_name": path.name,
                        "file_path": str(path.resolve()),
                        "cue_count": batch.cue_count,
                    }
                )

            manifest = self._build_manifest(
                request=request,
                batch=batch,
                artifact_dir=artifact_dir,
                file_records=file_records,
                validation_status="pending",
                generated_at=written_at,
            )
            atomic_write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
            written_paths.append(manifest_path)

            validation = self.artifact_validator.validate(artifact_payloads)
            if not validation.passed:
                _cleanup_paths(written_paths)
                return SubtitleWriteResult(
                    passed=False,
                    written_at=written_at,
                    session_id=session_id,
                    artifact_dir=str(artifact_dir),
                    formats_written=formats,
                    reject_code=validation.reject_code or "ARTIFACT_VALIDATION_FAILED",
                    reject_reasons=list(validation.reject_reasons),
                )

            for record in file_records:
                record.validation_status = "valid"

            manifest["validation_status"] = "valid"
            manifest["files"] = [record.to_dict() for record in file_records]
            atomic_write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

            return SubtitleWriteResult(
                passed=True,
                written_at=written_at,
                session_id=session_id,
                artifact_dir=str(artifact_dir),
                formats_written=formats,
                files=file_records,
                manifest_path=str(manifest_path.resolve()),
                manifest=manifest,
                validation_status="valid",
            )
        except OSError as exc:
            _cleanup_paths(written_paths)
            return SubtitleWriteResult(
                passed=False,
                written_at=written_at,
                session_id=session_id,
                artifact_dir=str(artifact_dir),
                reject_code="WRITE_FAILED",
                reject_reasons=[str(exc)],
            )

    def _build_manifest(
        self,
        *,
        request: SubtitleWriteRequest,
        batch: SubtitleCueBatch,
        artifact_dir: Path,
        file_records: list[SubtitleFileRecord],
        validation_status: str,
        generated_at: str,
    ) -> dict[str, Any]:
        metadata = dict(batch.metadata or {})
        formats_written = [record.format for record in file_records]
        return {
            "manifest_version": MANIFEST_VERSION,
            "writer_version": WRITER_VERSION,
            "session_id": request.session_id,
            "category": SUBTITLE_ARTIFACT_CATEGORY,
            "provider": "local_subtitle_runtime",
            "provider_mode": "local",
            "source_type": batch.source_type,
            "timing_strategy": batch.timing_strategy,
            "language": batch.language,
            "cue_count": batch.cue_count,
            "segment_count": metadata.get("segment_count"),
            "formats_written": formats_written,
            "format_list": formats_written,
            "files": [record.to_dict() for record in file_records],
            "total_duration_seconds": round(batch.total_duration, 3),
            "total_duration": round(batch.total_duration, 3),
            "validation_status": validation_status,
            "generated_at": generated_at,
            "batch_version": batch.batch_version,
            "voice_manifest_ref": request.voice_manifest_ref,
            "narration_source_path": request.narration_source_path,
            "execution_status": "completed",
            "partial": False,
            "real_provider_called": False,
            "artifact_dir": str(artifact_dir.resolve()),
            "warnings": list(batch.warnings),
        }

    def write_to_dict(self, request: SubtitleWriteRequest) -> dict[str, Any]:
        return self.write(request).to_dict()


__all__ = [
    "WRITER_VERSION",
    "MANIFEST_VERSION",
    "SUPPORTED_FORMATS",
    "DEFAULT_FILENAMES",
    "MANIFEST_FILENAME",
    "format_srt_timestamp",
    "format_vtt_timestamp",
    "format_ass_timestamp",
    "render_srt",
    "render_vtt",
    "render_ass",
    "apply_ass_highlights",
    "atomic_write_text",
    "SubtitleWriteRequest",
    "SubtitleFileRecord",
    "SubtitleWriteResult",
    "SubtitleFormatWriter",
]
