"""
Phase 10J-e — post-provider artifact validation before COMPLETED.

Validates file paths, sizes, extensions, and clip counts. Enriches artifact metadata.
Does not delete files on failure — valid clips remain for inspection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib
from typing import Any

from content_brain.execution.failure_taxonomy import CATEGORY_ARTIFACT_REJECT, classify_failure
from content_brain.execution.provider_categories import CATEGORY_VIDEO

VALIDATION_VERSION = "10j_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

VALID_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mov"})
DRY_RUN_EXTENSIONS = frozenset({".mock"})

CHECK_REJECT_CODES: dict[str, str] = {
    "NON_NULL": "ARTIFACT_NULL_PATH",
    "PATH_EXISTS": "ARTIFACT_PATH_MISSING",
    "EXTENSION": "ARTIFACT_INVALID_TYPE",
    "MIN_SIZE": "ARTIFACT_TOO_SMALL",
    "COUNT_MATCH": "ARTIFACT_COUNT_MISMATCH",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _check(check_id: str, passed: bool, message: str = "", *, artifact_index: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"id": check_id, "passed": passed, "message": message}
    if artifact_index is not None:
        payload["artifact_index"] = artifact_index
    return payload


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(65536):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"
    except OSError:
        return None


@dataclass
class ArtifactValidationResult:
    passed: bool
    validated_at: str
    clip_target: int | None = None
    clip_count: int = 0
    clip_valid: int = 0
    clip_invalid: int = 0
    invalid_clips: list[int] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    enriched_artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_operations_block(self) -> dict[str, Any]:
        return {
            "validated_at": self.validated_at,
            "passed": self.passed,
            "validation_version": VALIDATION_VERSION,
            "clip_target": self.clip_target,
            "clip_valid": self.clip_valid,
            "clip_invalid": self.clip_invalid,
            "invalid_clips": self.invalid_clips,
            "checks": self.checks,
            "reject_code": self.reject_code,
            "reject_reasons": self.reject_reasons,
        }

    def failure_details(self) -> dict[str, Any]:
        return {
            "clip_target": self.clip_target,
            "clip_valid": self.clip_valid,
            "clip_invalid": self.clip_invalid,
            "invalid_clips": self.invalid_clips,
            "reasons": self.reject_reasons,
            "category": CATEGORY_ARTIFACT_REJECT,
        }


class ArtifactValidationEngine:
    """Validate provider artifacts after execution, before terminal COMPLETED."""

    def validate(
        self,
        artifacts: list[dict[str, Any]],
        *,
        clip_target: int | None,
        min_artifact_bytes: int = 100_000,
        dry_run: bool = False,
        provider_execution: dict[str, Any] | None = None,
        compute_checksum: bool = True,
    ) -> ArtifactValidationResult:
        validated_at = _now()
        checks: list[dict[str, Any]] = []
        enriched: list[dict[str, Any]] = []
        invalid_clips: list[int] = []
        reject_reasons: list[str] = []
        reject_code: str | None = None

        allowed_extensions = set(VALID_VIDEO_EXTENSIONS)
        if dry_run:
            allowed_extensions |= DRY_RUN_EXTENSIONS

        provider_execution = dict(provider_execution or {})

        for index, artifact in enumerate(artifacts or [], start=1):
            if not isinstance(artifact, dict):
                checks.append(_check("NON_NULL", False, "Artifact entry is not a dict", artifact_index=index))
                invalid_clips.append(index)
                reject_reasons.append(f"Clip {index}: artifact entry invalid")
                if not reject_code:
                    reject_code = "ARTIFACT_VALIDATION_FAILED"
                enriched.append({"clip_number": index, "validation_status": "invalid"})
                continue

            clip_number = int(artifact.get("clip_number") or index)
            file_path_raw = artifact.get("file_path")
            source_path = artifact.get("source_path")
            record = dict(artifact)
            record["validated_at"] = validated_at
            record["provider_execution"] = dict(provider_execution)
            artifact_ok = True

            if file_path_raw is None or str(file_path_raw).strip() == "":
                checks.append(
                    _check(
                        "NON_NULL",
                        False,
                        f"Clip {clip_number}: file_path is null or empty",
                        artifact_index=clip_number,
                    )
                )
                record["validation_status"] = "invalid"
                record["validation_error"] = "ARTIFACT_NULL_PATH"
                invalid_clips.append(clip_number)
                reject_reasons.append(f"Clip {clip_number}: null file_path")
                if not reject_code:
                    reject_code = "ARTIFACT_NULL_PATH"
                artifact_ok = False
                enriched.append(record)
                continue

            path = Path(str(file_path_raw))
            if not path.exists():
                checks.append(
                    _check(
                        "PATH_EXISTS",
                        False,
                        f"Clip {clip_number}: path missing ({path})",
                        artifact_index=clip_number,
                    )
                )
                record["validation_status"] = "invalid"
                record["validation_error"] = "ARTIFACT_PATH_MISSING"
                record["size_bytes"] = None
                invalid_clips.append(clip_number)
                reject_reasons.append(f"Clip {clip_number}: path missing")
                if not reject_code:
                    reject_code = "ARTIFACT_PATH_MISSING"
                artifact_ok = False
                enriched.append(record)
                continue

            suffix = path.suffix.lower()
            if suffix not in allowed_extensions:
                checks.append(
                    _check(
                        "EXTENSION",
                        False,
                        f"Clip {clip_number}: invalid extension {suffix!r}",
                        artifact_index=clip_number,
                    )
                )
                record["validation_status"] = "invalid"
                record["validation_error"] = "ARTIFACT_INVALID_TYPE"
                invalid_clips.append(clip_number)
                reject_reasons.append(f"Clip {clip_number}: invalid extension {suffix!r}")
                if not reject_code:
                    reject_code = "ARTIFACT_INVALID_TYPE"
                artifact_ok = False

            try:
                size_bytes = path.stat().st_size
            except OSError as exc:
                checks.append(
                    _check(
                        "PATH_EXISTS",
                        False,
                        f"Clip {clip_number}: stat failed ({exc})",
                        artifact_index=clip_number,
                    )
                )
                record["validation_status"] = "invalid"
                record["validation_error"] = "ARTIFACT_PATH_MISSING"
                invalid_clips.append(clip_number)
                reject_reasons.append(f"Clip {clip_number}: stat failed")
                if not reject_code:
                    reject_code = "ARTIFACT_PATH_MISSING"
                artifact_ok = False
                enriched.append(record)
                continue

            record["size_bytes"] = size_bytes
            if source_path:
                record["source_path"] = str(source_path)

            min_bytes = 1 if dry_run and suffix in DRY_RUN_EXTENSIONS else min_artifact_bytes
            if size_bytes < min_bytes:
                checks.append(
                    _check(
                        "MIN_SIZE",
                        False,
                        f"Clip {clip_number}: size {size_bytes} < min {min_bytes}",
                        artifact_index=clip_number,
                    )
                )
                record["validation_status"] = "invalid"
                record["validation_error"] = "ARTIFACT_TOO_SMALL"
                invalid_clips.append(clip_number)
                reject_reasons.append(f"Clip {clip_number}: too small ({size_bytes} bytes)")
                if not reject_code:
                    reject_code = "ARTIFACT_TOO_SMALL"
                artifact_ok = False
            else:
                checks.append(
                    _check(
                        "MIN_SIZE",
                        True,
                        f"Clip {clip_number}: size {size_bytes} OK",
                        artifact_index=clip_number,
                    )
                )

            if artifact_ok:
                checks.append(
                    _check(
                        "PATH_EXISTS",
                        True,
                        f"Clip {clip_number}: path exists",
                        artifact_index=clip_number,
                    )
                )
                checks.append(
                    _check(
                        "EXTENSION",
                        True,
                        f"Clip {clip_number}: extension {suffix!r} OK",
                        artifact_index=clip_number,
                    )
                )
                record["validation_status"] = "valid"
                record["validation_error"] = None
                if compute_checksum:
                    checksum = _sha256_file(path)
                    if checksum:
                        record["sha256"] = checksum

            enriched.append(record)

        clip_count = len(enriched)
        clip_valid = sum(1 for item in enriched if item.get("validation_status") == "valid")
        clip_invalid = clip_count - clip_valid

        if clip_target is not None and clip_target > 0 and clip_count != clip_target:
            checks.append(
                _check(
                    "COUNT_MATCH",
                    False,
                    f"Artifact count {clip_count} != expected {clip_target}",
                )
            )
            reject_reasons.append(f"Expected {clip_target} clips, got {clip_count}")
            if not reject_code:
                reject_code = "ARTIFACT_COUNT_MISMATCH"
            elif reject_code != "ARTIFACT_COUNT_MISMATCH":
                reject_code = "ARTIFACT_COUNT_MISMATCH"

        elif clip_target is not None and clip_target > 0 and clip_valid != clip_target:
            checks.append(
                _check(
                    "COUNT_MATCH",
                    False,
                    f"Valid clip count {clip_valid} != expected {clip_target}",
                )
            )
            reject_reasons.append(f"Expected {clip_target} valid clips, got {clip_valid}")
            if not reject_code:
                reject_code = "ARTIFACT_COUNT_MISMATCH"

        if clip_valid == clip_count and clip_count > 0:
            checks.append(
                _check(
                    "COUNT_MATCH",
                    True,
                    f"Clip count {clip_count} matches target {clip_target}",
                )
            )

        passed = clip_invalid == 0
        if clip_target is not None and clip_target > 0:
            passed = passed and clip_count == clip_target and clip_valid == clip_target

        if not passed and reject_code is None:
            reject_code = "ARTIFACT_VALIDATION_FAILED"

        return ArtifactValidationResult(
            passed=passed,
            validated_at=validated_at,
            clip_target=clip_target,
            clip_count=clip_count,
            clip_valid=clip_valid,
            clip_invalid=clip_invalid,
            invalid_clips=invalid_clips,
            checks=checks,
            reject_code=reject_code,
            reject_reasons=reject_reasons,
            enriched_artifacts=enriched,
        )


def build_artifact_failure(
    result: ArtifactValidationResult,
    *,
    dispatch_id: str | None = None,
    failed_at: str | None = None,
) -> dict[str, Any]:
    """Build failure object with ARTIFACT_REJECT category."""
    code = result.reject_code or "ARTIFACT_VALIDATION_FAILED"
    meta = classify_failure(code)
    return {
        "code": code,
        "category": meta["category"],
        "message": "; ".join(result.reject_reasons) if result.reject_reasons else code,
        "retriable": meta["retriable"],
        "failed_at": failed_at or _now(),
        "dispatch_id": dispatch_id,
        "details": result.failure_details(),
    }


__all__ = [
    "VALIDATION_VERSION",
    "ArtifactValidationEngine",
    "ArtifactValidationResult",
    "build_artifact_failure",
    "VALID_VIDEO_EXTENSIONS",
    "DRY_RUN_EXTENSIONS",
]
