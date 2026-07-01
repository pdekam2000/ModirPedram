"""Canonical delivery — one run, one final video, one truth."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_DELIVERY_VERSION = "canonical_delivery_v1"
CANONICAL_BRANDED_VIDEO_NAME = "FINAL_BRANDED_VIDEO_CANONICAL.mp4"

SUPERSEDED_BRANDED_NAMES: tuple[str, ...] = (
    "FINAL_BRANDED_VIDEO.mp4",
    "FINAL_BRANDED_VIDEO_v1.mp4",
    "FINAL_BRANDED_VIDEO_v2.mp4",
    "FINAL_BRANDED_VIDEO_v3.mp4",
    "FINAL_BRANDED_VIDEO_v4.mp4",
    "FINAL_BRANDED_VIDEO_subtitle_fixed.mp4",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_publish_path(run_dir: str | Path) -> Path:
    base = Path(run_dir).resolve()
    publish = base if base.name.lower() == "publish" else base / "publish"
    return publish / CANONICAL_BRANDED_VIDEO_NAME


def is_superseded_branded_name(name: str) -> bool:
    return str(name or "").strip() in SUPERSEDED_BRANDED_NAMES


def list_superseded_branded_files(*roots: str | Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        base = Path(root).resolve()
        if not base.is_dir():
            continue
        for name in SUPERSEDED_BRANDED_NAMES:
            candidate = base / name
            if candidate.is_file() and candidate.stat().st_size > 0:
                key = str(candidate.resolve())
                if key not in seen:
                    seen.add(key)
                    found.append(candidate)
    return sorted(found)


def archive_superseded_branded_variants(
    *,
    publish_dir: str | Path,
    final_dir: str | Path | None = None,
    archive_root: str | Path | None = None,
    run_id: str = "",
) -> list[str]:
    """Move superseded branded MP4 variants out of active publish/final folders."""
    publish = Path(publish_dir).resolve()
    final = Path(final_dir).resolve() if final_dir else publish.parent / "final"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_suffix = slugify_run_id(run_id) if run_id else publish.parent.name
    dest_root = Path(
        archive_root
        or publish.parent.parent.parent.parent / "storage" / "archive" / "delivery_canonical_1" / run_suffix / stamp
    )
    archived: list[str] = []
    for src in list_superseded_branded_files(publish, final):
        if src.name == CANONICAL_BRANDED_VIDEO_NAME:
            continue
        bucket = "publish" if "publish" in src.parts else "final"
        dest = dest_root / bucket / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = dest.with_name(f"{dest.stem}_{stamp}{dest.suffix}")
        shutil.move(str(src), str(dest))
        archived.append(str(dest.resolve()))
    manifest = {
        "version": CANONICAL_DELIVERY_VERSION,
        "archived_at": _now(),
        "run_id": run_id,
        "publish_dir": str(publish),
        "files": archived,
    }
    dest_root.mkdir(parents=True, exist_ok=True)
    (dest_root / "archive_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return archived


def slugify_run_id(run_id: str) -> str:
    text = str(run_id or "run").strip()
    return text.replace("/", "_").replace("\\", "_") or "run"


def promote_canonical_final_video(
    source_video: str | Path,
    *,
    publish_dir: str | Path,
    archive_superseded: bool = True,
    run_id: str = "",
) -> Path:
    """Write the one approved branded deliverable and optionally archive legacy variants."""
    publish = Path(publish_dir).resolve()
    publish.mkdir(parents=True, exist_ok=True)
    source = Path(source_video).resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"canonical_source_missing:{source}")

    canonical = canonical_publish_path(publish)
    if source.resolve() != canonical.resolve():
        shutil.copy2(source, canonical)

    if archive_superseded:
        archive_superseded_branded_variants(
            publish_dir=publish,
            final_dir=publish.parent / "final",
            run_id=run_id,
        )
    return canonical.resolve()


def resolve_canonical_final_video(
    project_root: str | Path,
    *,
    run_dir: str | Path = "",
    run_id: str = "",
) -> Path | None:
    """Resolve the single canonical branded MP4 for a run."""
    root = Path(project_root).resolve()
    from content_brain.platform.final_delivery_registry import load_final_delivery_registry

    registry = load_final_delivery_registry(root)
    registry_run_id = str(registry.get("latest_run_id") or "")
    canonical_from_registry = str(registry.get("canonical_final_video_path") or registry.get("latest_video") or "")

    if run_id and registry_run_id and run_id != registry_run_id:
        canonical_from_registry = ""

    if canonical_from_registry:
        path = Path(canonical_from_registry)
        if path.is_file() and path.stat().st_size > 0:
            return path.resolve()

    run_dir_path = Path(run_dir).resolve() if run_dir else None
    if run_dir_path is None and registry_run_id:
        from content_brain.platform.canonical_run import load_canonical_run

        canonical = load_canonical_run(root)
        if not run_id or str(canonical.get("run_id") or "") == run_id:
            run_dir_text = str(canonical.get("run_dir") or "")
            if run_dir_text:
                run_dir_path = Path(run_dir_text)

    if run_dir_path is not None:
        candidate = canonical_publish_path(run_dir_path)
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate.resolve()
    return None


__all__ = [
    "CANONICAL_BRANDED_VIDEO_NAME",
    "CANONICAL_DELIVERY_VERSION",
    "SUPERSEDED_BRANDED_NAMES",
    "archive_superseded_branded_variants",
    "canonical_publish_path",
    "is_superseded_branded_name",
    "list_superseded_branded_files",
    "promote_canonical_final_video",
    "resolve_canonical_final_video",
]
