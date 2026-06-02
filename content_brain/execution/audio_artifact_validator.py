"""
Phase 11H-1a — safe audio artifact validation (no FFmpeg).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

VALIDATION_VERSION = "11h1a_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

VALID_AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a"})
DRY_RUN_EXTENSIONS = frozenset({".mock"})


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class AudioArtifactValidationResult:
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


class AudioArtifactValidator:
    """Validate narration audio artifacts by path, extension, and size."""

    def validate(
        self,
        artifacts: list[dict[str, Any]],
        *,
        dry_run: bool = False,
        min_artifact_bytes: int = 1,
    ) -> AudioArtifactValidationResult:
        validated_at = _now()
        checks: list[dict[str, Any]] = []
        reject_reasons: list[str] = []
        enriched: list[dict[str, Any]] = []
        valid_count = 0
        invalid_count = 0

        allowed_extensions = VALID_AUDIO_EXTENSIONS | (DRY_RUN_EXTENSIONS if dry_run else frozenset())

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
            ext_ok = extension in allowed_extensions
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
                reject_reasons.append(f"Artifact {index + 1}: file too small ({size_bytes} bytes)")
                continue

            artifact["size_bytes"] = size_bytes
            artifact["validation_status"] = "valid"
            artifact["validated_at"] = validated_at
            enriched.append(artifact)
            valid_count += 1

        if not artifacts:
            return AudioArtifactValidationResult(
                passed=False,
                validated_at=validated_at,
                artifact_count=0,
                valid_count=0,
                invalid_count=0,
                checks=checks,
                reject_code="ARTIFACT_MISSING",
                reject_reasons=["No audio artifacts provided."],
            )

        passed = invalid_count == 0 and valid_count == len(artifacts)
        return AudioArtifactValidationResult(
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
    "VALID_AUDIO_EXTENSIONS",
    "AudioArtifactValidator",
    "AudioArtifactValidationResult",
]
