"""
Phase 11F-c — shared Hailuo artifact metadata normalization.

Mirrors Runway 11E-d; compatible with 10J-e ArtifactValidationEngine.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from content_brain.execution.hailuo_config import HAILUO_BROWSER_ROUTER_KEY
from providers.hailuo_api_errors import HailuoProviderError

ARTIFACT_UTILS_VERSION = "11f_c_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
MIN_ARTIFACT_BYTES = 100_000

MODE_BROWSER = "browser"
CAPABILITY_TEXT_TO_VIDEO = "text_to_video"

VALIDATION_PENDING = "pending"
VALIDATION_VALID = "valid"
VALIDATION_INVALID_TOO_SMALL = "invalid_too_small"
VALIDATION_PARTIAL = "partial"

REQUIRED_ARTIFACT_FIELDS = frozenset({
    "file_path",
    "provider",
    "provider_id",
    "mode",
    "capability",
    "clip_index",
    "size_bytes",
    "downloaded_at",
    "validation_status",
    "partial",
    "artifact_preserved",
})


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def build_job_id(*, clip_index: int | None = None, prefix: str = "hailuo_clip") -> str:
    if clip_index is not None:
        return f"{prefix}_{clip_index:02d}"
    return prefix


def is_valid_source_url(url: str | None) -> bool:
    if not url or not str(url).strip():
        return False
    parsed = urlparse(str(url).strip())
    if parsed.scheme == "blob":
        return bool(parsed.path or parsed.netloc or str(url).strip().startswith("blob:"))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
        raise HailuoProviderError(
            "Artifact file_path is missing",
            code="ARTIFACT_NULL_PATH",
            details={"clip_index": clip_index, "artifact_preserved": False},
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
    artifact_preserved: bool = True,
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

    resolved_job_id = job_id or task_id or build_job_id(clip_index=clip_index)
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
        "task_id": task_id or resolved_job_id,
        "job_id": resolved_job_id,
        "source_url": source_url,
        "size_bytes": resolved_size,
        "sha256": checksum,
        "downloaded_at": downloaded_at or _now(),
        "validation_status": status,
        "partial": bool(partial),
        "artifact_preserved": bool(artifact_preserved),
        "metadata": dict(metadata or {}),
    }
    for key, value in extra.items():
        if value is not None and key not in record:
            record[key] = value
    return record


def finalize_download_artifact(
    file_path: str | Path,
    *,
    mode: str = MODE_BROWSER,
    provider_id: str = HAILUO_BROWSER_ROUTER_KEY,
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
        raise HailuoProviderError(
            f"Artifact path does not exist: {path}",
            code="ARTIFACT_PATH_MISSING",
            details={
                "clip_index": clip_index,
                "file_path": str(path),
                "artifact_preserved": False,
            },
        )

    if source_url is not None and not is_valid_source_url(source_url):
        raise HailuoProviderError(
            f"Invalid Hailuo download source URL: {source_url!r}",
            code="DOWNLOAD_FAILED",
            details={
                "clip_index": clip_index,
                "source_url": source_url,
                "artifact_preserved": path.exists(),
                "file_path": str(path) if path.exists() else None,
            },
        )

    size_bytes = path.stat().st_size
    if size_bytes < min_bytes:
        raise HailuoProviderError(
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
        artifact_preserved=True,
        metadata=metadata,
        **extra,
    )


def clip_result_paths(clip_results: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for index, item in enumerate(clip_results):
        path = item.get("file_path")
        if not path:
            raise HailuoProviderError(
                "clip_results entry missing file_path",
                code="ARTIFACT_NULL_PATH",
                details={"clip_index": item.get("clip_index", index + 1)},
            )
        paths.append(str(path))
    return paths


def mark_clip_results_partial(clip_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    marked: list[dict[str, Any]] = []
    for item in clip_results:
        updated = dict(item)
        updated["partial"] = True
        updated["artifact_preserved"] = True
        if updated.get("validation_status") in {None, VALIDATION_PENDING, VALIDATION_VALID}:
            updated["validation_status"] = VALIDATION_PARTIAL
        marked.append(updated)
    return marked


def partial_artifact_bundle(
    clip_results: list[dict[str, Any]],
    partial_paths: list[str],
) -> dict[str, Any]:
    marked = mark_clip_results_partial(list(clip_results))
    return {
        "partial": True,
        "artifact_preserved": True,
        "partial_paths": list(partial_paths),
        "clip_results": marked,
        "clip_count": len(marked),
    }


def provider_id_for_mode(mode: str) -> str:
    return HAILUO_BROWSER_ROUTER_KEY if str(mode).lower() == MODE_BROWSER else "hailuo_api"


__all__ = [
    "ARTIFACT_UTILS_VERSION",
    "MIN_ARTIFACT_BYTES",
    "MODE_BROWSER",
    "CAPABILITY_TEXT_TO_VIDEO",
    "HAILUO_BROWSER_ROUTER_KEY",
    "REQUIRED_ARTIFACT_FIELDS",
    "VALIDATION_PENDING",
    "VALIDATION_VALID",
    "VALIDATION_INVALID_TOO_SMALL",
    "VALIDATION_PARTIAL",
    "build_job_id",
    "is_valid_source_url",
    "compute_sha256",
    "require_file_path",
    "normalize_artifact_record",
    "finalize_download_artifact",
    "clip_result_paths",
    "mark_clip_results_partial",
    "partial_artifact_bundle",
    "provider_id_for_mode",
]
