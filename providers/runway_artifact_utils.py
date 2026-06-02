"""
Phase 11E-d — shared Runway artifact metadata normalization.

Used by API and browser download paths; compatible with 10J-e ArtifactValidationEngine.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.runway_config import RUNWAY_API_ROUTER_KEY, RUNWAY_BROWSER_ROUTER_KEY
from providers.runway_api_errors import RunwayProviderError
from providers.runway_output_url_classifier import assert_real_runway_output_source

ARTIFACT_UTILS_VERSION = "11e_d_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
MIN_ARTIFACT_BYTES = 100_000

MODE_API = "api"
MODE_BROWSER = "browser"
CAPABILITY_TEXT_TO_VIDEO = "text_to_video"

VALIDATION_PENDING = "pending"
VALIDATION_VALID = "valid"
VALIDATION_INVALID_TOO_SMALL = "invalid_too_small"
VALIDATION_PARTIAL = "partial"


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def compute_sha256(path: str | Path) -> str | None:
    target = Path(path)
    if not target.exists() or not target.is_file():
        return None
    try:
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            while chunk := handle.read(65536):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"
    except OSError:
        return None


def require_file_path(file_path: str | None, *, clip_index: int | None = None) -> str:
    if not file_path or not str(file_path).strip():
        raise RunwayProviderError(
            "Artifact file_path is missing",
            code="ARTIFACT_NULL_PATH",
            details={"clip_index": clip_index},
        )
    return str(file_path)


def normalize_artifact_record(
    *,
    file_path: str,
    mode: str,
    provider_id: str,
    capability: str = CAPABILITY_TEXT_TO_VIDEO,
    clip_index: int | None = None,
    task_id: str | None = None,
    job_id: str | None = None,
    source_url: str | None = None,
    size_bytes: int | None = None,
    sha256: str | None = None,
    downloaded_at: str | None = None,
    validation_status: str | None = None,
    partial: bool = False,
    metadata: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    path = require_file_path(file_path, clip_index=clip_index)
    resolved_size = size_bytes
    if resolved_size is None:
        try:
            resolved_size = Path(path).stat().st_size if Path(path).exists() else None
        except OSError:
            resolved_size = None

    checksum = sha256
    if checksum is None and resolved_size and resolved_size > 0 and Path(path).exists():
        checksum = compute_sha256(path)

    status = validation_status or VALIDATION_PENDING
    if partial and status == VALIDATION_PENDING:
        status = VALIDATION_PARTIAL

    record: dict[str, Any] = {
        "artifact_utils_version": ARTIFACT_UTILS_VERSION,
        "file_path": path,
        "provider": provider_id,
        "provider_id": provider_id,
        "mode": mode,
        "capability": capability,
        "clip_index": clip_index,
        "task_id": task_id,
        "job_id": job_id or task_id,
        "source_url": source_url,
        "size_bytes": resolved_size,
        "sha256": checksum,
        "downloaded_at": downloaded_at or _now(),
        "validation_status": status,
        "partial": bool(partial),
        "metadata": dict(metadata or {}),
    }
    for key, value in extra.items():
        if value is not None and key not in record:
            record[key] = value
    return record


def finalize_download_artifact(
    file_path: str | Path,
    *,
    mode: str,
    provider_id: str,
    capability: str = CAPABILITY_TEXT_TO_VIDEO,
    clip_index: int | None = None,
    task_id: str | None = None,
    source_url: str | None = None,
    partial: bool = False,
    metadata: dict[str, Any] | None = None,
    min_bytes: int = MIN_ARTIFACT_BYTES,
    **extra: Any,
) -> dict[str, Any]:
    path = Path(require_file_path(str(file_path), clip_index=clip_index))
    if not path.exists():
        raise RunwayProviderError(
            f"Artifact path does not exist: {path}",
            code="ARTIFACT_PATH_MISSING",
            details={"clip_index": clip_index, "file_path": str(path)},
        )

    assert_real_runway_output_source(
        source_url,
        file_path=path,
        clip_index=clip_index,
    )

    size_bytes = path.stat().st_size
    validation_status = VALIDATION_PENDING
    if size_bytes < min_bytes:
        validation_status = VALIDATION_INVALID_TOO_SMALL
        raise RunwayProviderError(
            f"Downloaded file too small, probably invalid: {size_bytes} bytes",
            code="ARTIFACT_TOO_SMALL",
            details={
                "clip_index": clip_index,
                "file_path": str(path),
                "size_bytes": size_bytes,
                "min_artifact_bytes": min_bytes,
                "artifact_preserved": True,
            },
        )

    validation_status = VALIDATION_VALID if not partial else VALIDATION_PARTIAL
    return normalize_artifact_record(
        file_path=str(path),
        mode=mode,
        provider_id=provider_id,
        capability=capability,
        clip_index=clip_index,
        task_id=task_id,
        source_url=source_url,
        size_bytes=size_bytes,
        sha256=compute_sha256(path),
        validation_status=validation_status,
        partial=partial,
        metadata=metadata,
        **extra,
    )


def mark_clip_results_partial(clip_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    marked: list[dict[str, Any]] = []
    for item in clip_results:
        updated = dict(item)
        updated["partial"] = True
        if updated.get("validation_status") in {None, VALIDATION_PENDING, VALIDATION_VALID}:
            updated["validation_status"] = VALIDATION_PARTIAL
        marked.append(updated)
    return marked


def partial_artifact_bundle(
    clip_results: list[dict[str, Any]],
    partial_paths: list[str],
) -> dict[str, Any]:
    return {
        "partial": True,
        "partial_paths": list(partial_paths),
        "clip_results": mark_clip_results_partial(list(clip_results)),
        "clip_count": len(clip_results),
    }


def provider_id_for_mode(mode: str) -> str:
    return RUNWAY_BROWSER_ROUTER_KEY if str(mode).lower() == MODE_BROWSER else RUNWAY_API_ROUTER_KEY


__all__ = [
    "ARTIFACT_UTILS_VERSION",
    "MIN_ARTIFACT_BYTES",
    "MODE_API",
    "MODE_BROWSER",
    "CAPABILITY_TEXT_TO_VIDEO",
    "VALIDATION_PENDING",
    "VALIDATION_VALID",
    "VALIDATION_INVALID_TOO_SMALL",
    "VALIDATION_PARTIAL",
    "compute_sha256",
    "require_file_path",
    "normalize_artifact_record",
    "finalize_download_artifact",
    "mark_clip_results_partial",
    "partial_artifact_bundle",
    "provider_id_for_mode",
    "RUNWAY_API_ROUTER_KEY",
    "RUNWAY_BROWSER_ROUTER_KEY",
]
