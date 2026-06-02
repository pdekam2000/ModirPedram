"""
Phase 11I-2 — safe subtitle artifact validation (no FFmpeg).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

VALIDATION_VERSION = "11i2_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

VALID_SUBTITLE_EXTENSIONS = frozenset({".srt", ".ass", ".vtt"})

_SRT_TIMESTAMP = re.compile(
    r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}",
    re.MULTILINE,
)
_VTT_TIMESTAMP = re.compile(
    r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}",
    re.MULTILINE,
)
_ASS_EVENT = re.compile(r"^Dialogue:\s*\d", re.MULTILINE | re.IGNORECASE)


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_placeholder_cues(content: str, extension: str) -> bool:
    text = content.strip()
    if not text:
        return False

    if extension == ".vtt":
        if not text.upper().startswith("WEBVTT"):
            return False
        return bool(_VTT_TIMESTAMP.search(text))

    if extension == ".ass":
        return bool(_ASS_EVENT.search(text))

    if extension == ".srt":
        return bool(_SRT_TIMESTAMP.search(text))

    return False


@dataclass
class SubtitleArtifactValidationResult:
    passed: bool
    validated_at: str
    artifact_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    checks: list[dict[str, Any]] = field(default_factory=list)
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    enriched_artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_version": VALIDATION_VERSION,
            "passed": self.passed,
            "validated_at": self.validated_at,
            "artifact_count": self.artifact_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "checks": list(self.checks),
            "reject_code": self.reject_code,
            "reject_reasons": list(self.reject_reasons),
        }


class SubtitleArtifactValidator:
    """Validate subtitle artifacts by path, extension, size, and placeholder cue checks."""

    def validate(
        self,
        artifacts: list[dict[str, Any]],
        *,
        min_artifact_bytes: int = 1,
    ) -> SubtitleArtifactValidationResult:
        validated_at = _now()
        checks: list[dict[str, Any]] = []
        reject_reasons: list[str] = []
        enriched: list[dict[str, Any]] = []
        valid_count = 0
        invalid_count = 0

        for index, raw in enumerate(artifacts):
            artifact = dict(_dict(raw))
            path_text = str(artifact.get("file_path") or "").strip()
            if not path_text:
                invalid_count += 1
                checks.append({"id": "PATH_PRESENT", "passed": False, "artifact_index": index})
                reject_reasons.append(f"Artifact {index + 1}: missing file_path")
                continue

            path = Path(path_text)
            exists = path.is_file()
            checks.append({"id": "PATH_EXISTS", "passed": exists, "artifact_index": index, "path": path_text})
            if not exists:
                invalid_count += 1
                reject_reasons.append(f"Artifact {index + 1}: file not found")
                continue

            extension = path.suffix.lower()
            ext_ok = extension in VALID_SUBTITLE_EXTENSIONS
            checks.append({"id": "EXTENSION", "passed": ext_ok, "artifact_index": index, "extension": extension})
            if not ext_ok:
                invalid_count += 1
                reject_reasons.append(f"Artifact {index + 1}: invalid extension {extension}")
                continue

            size_bytes = path.stat().st_size
            size_ok = size_bytes >= min_artifact_bytes
            checks.append({"id": "MIN_SIZE", "passed": size_ok, "artifact_index": index, "size_bytes": size_bytes})
            if not size_ok:
                invalid_count += 1
                reject_reasons.append(f"Artifact {index + 1}: file empty or too small ({size_bytes} bytes)")
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                invalid_count += 1
                checks.append({"id": "READABLE", "passed": False, "artifact_index": index, "error": str(exc)})
                reject_reasons.append(f"Artifact {index + 1}: unreadable ({exc})")
                continue

            cue_ok = _has_placeholder_cues(content, extension)
            checks.append({"id": "CUE_TIMESTAMPS", "passed": cue_ok, "artifact_index": index, "extension": extension})
            if not cue_ok:
                invalid_count += 1
                reject_reasons.append(f"Artifact {index + 1}: missing placeholder cue/timestamp structure")
                continue

            artifact["size_bytes"] = size_bytes
            artifact["validation_status"] = "valid"
            artifact["validated_at"] = validated_at
            enriched.append(artifact)
            valid_count += 1

        if not artifacts:
            return SubtitleArtifactValidationResult(
                passed=False,
                validated_at=validated_at,
                artifact_count=0,
                valid_count=0,
                invalid_count=0,
                checks=checks,
                reject_code="ARTIFACT_MISSING",
                reject_reasons=["No subtitle artifacts provided."],
            )

        passed = invalid_count == 0 and valid_count == len(artifacts)
        return SubtitleArtifactValidationResult(
            passed=passed,
            validated_at=validated_at,
            artifact_count=len(artifacts),
            valid_count=valid_count,
            invalid_count=invalid_count,
            checks=checks,
            reject_code=None if passed else "ARTIFACT_VALIDATION_FAILED",
            reject_reasons=[] if passed else reject_reasons,
            enriched_artifacts=enriched,
        )


__all__ = [
    "VALIDATION_VERSION",
    "VALID_SUBTITLE_EXTENSIONS",
    "SubtitleArtifactValidator",
    "SubtitleArtifactValidationResult",
]
