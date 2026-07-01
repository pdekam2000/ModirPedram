"""Upload package builder — per-platform folders under versioned run output."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.canonical_delivery import CANONICAL_BRANDED_VIDEO_NAME, resolve_canonical_final_video
from content_brain.platform.final_delivery_registry import resolve_approved_delivery
from content_brain.platform.run_output_versioning import list_run_history
from content_brain.upload.upload_models import PLATFORM_INSTAGRAM, PLATFORM_TIKTOK, PLATFORM_YOUTUBE

UPLOAD_PACKAGE_BUILDER_VERSION = "upload_package_builder_v1"

PLATFORM_FOLDER_NAMES = {
    PLATFORM_YOUTUBE: "youtube",
    PLATFORM_TIKTOK: "tiktok",
    PLATFORM_INSTAGRAM: "instagram",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_run_dir(project_root: str | Path, run_id: str) -> Path:
    root = Path(project_root).resolve()
    run_id_text = str(run_id or "").strip()
    if not run_id_text:
        return root / "outputs" / "runs" / "latest"

    for item in list_run_history(root, limit=100):
        if str(item.get("run_id") or "") == run_id_text and item.get("run_dir"):
            return Path(str(item["run_dir"]))

    runs_root = root / "outputs" / "runs"
    if runs_root.is_dir():
        suffix = run_id_text[-12:] if len(run_id_text) > 12 else run_id_text
        matches = sorted(
            [path for path in runs_root.iterdir() if path.is_dir() and (run_id_text in path.name or path.name.endswith(suffix))],
            reverse=True,
        )
        if matches:
            return matches[0]

    direct = runs_root / run_id_text
    if direct.is_dir():
        return direct
    return direct


def _resolve_video_path(
    *,
    project_root: Path,
    video_path: str,
    publish_package_path: str,
    run_dir: Path,
) -> Path:
    delivery = resolve_approved_delivery(project_root)
    candidates: list[Path] = []
    canonical = resolve_canonical_final_video(project_root, run_dir=run_dir)
    if canonical is not None:
        candidates.append(canonical)
    if delivery:
        candidates.append(Path(str(delivery.get("canonical_final_video_path") or "")))
    if video_path:
        candidates.append(Path(video_path))
    if publish_package_path:
        publish = Path(publish_package_path)
        candidates.extend(
            [
                publish / CANONICAL_BRANDED_VIDEO_NAME,
                publish / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4",
                publish / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4",
            ]
        )
    candidates.extend(
        [
            run_dir / "final" / CANONICAL_BRANDED_VIDEO_NAME,
            run_dir / "final" / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4",
            run_dir / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4",
        ]
    )
    for candidate in candidates:
        resolved = candidate if candidate.is_absolute() else (project_root / candidate)
        if resolved.is_file() and resolved.stat().st_size > 0:
            return resolved.resolve()
    return (project_root / (video_path or "missing.mp4")).resolve()


def _caption_text(platform: str, metadata: dict[str, Any]) -> str:
    if platform == PLATFORM_YOUTUBE:
        body = str(metadata.get("description") or metadata.get("title") or "").strip()
        hashtags = " ".join(metadata.get("hashtags") or [])
        return f"{body}\n\n{hashtags}".strip()
    return str(metadata.get("caption") or metadata.get("description") or metadata.get("title") or "").strip()


def _hashtags_text(metadata: dict[str, Any]) -> str:
    return " ".join(str(item).strip() for item in (metadata.get("hashtags") or []) if str(item).strip())


def _readme(platform: str, metadata: dict[str, Any], *, manual_only: bool) -> str:
    folder = PLATFORM_FOLDER_NAMES.get(platform, platform)
    lines = [
        f"# {folder.title()} Upload Package",
        "",
        f"Generated: {_now()}",
        f"Platform: {platform}",
        f"Source: {metadata.get('source', 'unknown')}",
        "",
    ]
    if manual_only:
        lines.extend(
            [
                "## Status",
                "Manual upload ready — no automatic upload executed in V1.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Status",
                "Package prepared for YouTube upload. Default privacy is private.",
                "Upload requires explicit user confirmation.",
                "",
            ]
        )
    lines.extend(
        [
            "## Files",
            "- video.mp4",
            "- metadata.json",
            "- caption.txt",
            "- hashtags.txt",
            "- pinned comment draft (*.txt)",
            "",
        ]
    )
    return "\n".join(lines)


def build_upload_packages(
    *,
    project_root: str | Path,
    run_id: str,
    topic: str,
    platform_targets: list[str],
    metadata_bundle: dict[str, Any],
    video_path: str = "",
    publish_package_path: str = "",
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run_dir = resolve_run_dir(root, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    upload_root = run_dir / "upload"
    upload_root.mkdir(parents=True, exist_ok=True)

    source_video = _resolve_video_path(
        project_root=root,
        video_path=video_path,
        publish_package_path=publish_package_path,
        run_dir=run_dir,
    )
    platforms_meta = dict(metadata_bundle.get("platforms") or {})
    packages: list[dict[str, Any]] = []

    for platform in platform_targets:
        normalized = str(platform or "").strip().lower()
        folder_name = PLATFORM_FOLDER_NAMES.get(normalized)
        if not folder_name:
            continue
        metadata = dict(platforms_meta.get(normalized) or {})
        platform_dir = upload_root / folder_name
        platform_dir.mkdir(parents=True, exist_ok=True)

        target_video = platform_dir / "video.mp4"
        if source_video.is_file():
            if target_video.exists():
                target_video.unlink()
            shutil.copy2(source_video, target_video)

        caption = _caption_text(normalized, metadata)
        hashtags = _hashtags_text(metadata)
        (platform_dir / "caption.txt").write_text(caption, encoding="utf-8")
        (platform_dir / "hashtags.txt").write_text(hashtags, encoding="utf-8")
        (platform_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        pinned = str(metadata.get("pinned_comment") or "").strip()
        pinned_name = f"{folder_name}_pinned_comment.txt"
        (platform_dir / pinned_name).write_text(pinned, encoding="utf-8")

        manual_only = normalized in {PLATFORM_TIKTOK, PLATFORM_INSTAGRAM}
        (platform_dir / "upload_readme.md").write_text(
            _readme(normalized, metadata, manual_only=manual_only),
            encoding="utf-8",
        )

        status = "manual_upload_ready" if manual_only else "prepared"
        packages.append(
            {
                "platform": normalized,
                "folder_name": folder_name,
                "platform_dir": str(platform_dir),
                "video_path": str(target_video if target_video.is_file() else source_video),
                "metadata_path": str(platform_dir / "metadata.json"),
                "caption_path": str(platform_dir / "caption.txt"),
                "hashtags_path": str(platform_dir / "hashtags.txt"),
                "pinned_comment_path": str(platform_dir / pinned_name),
                "status": status,
                "manual_upload_only": manual_only,
                "auto_upload": False,
            }
        )

    manifest = {
        "version": UPLOAD_PACKAGE_BUILDER_VERSION,
        "run_id": run_id,
        "topic": topic,
        "run_dir": str(run_dir),
        "upload_root": str(upload_root),
        "source_video_path": str(source_video),
        "publish_package_path": publish_package_path,
        "packages": packages,
        "created_at": _now(),
    }
    for package in packages:
        platform = str(package.get("platform") or "")
        folder_name = str(package.get("folder_name") or "")
        pinned_path = Path(str(package.get("pinned_comment_path") or ""))
        if pinned_path.is_file() and folder_name:
            root_pinned = upload_root / f"{folder_name}_pinned_comment.txt"
            root_pinned.write_text(pinned_path.read_text(encoding="utf-8"), encoding="utf-8")
            package["root_pinned_comment_path"] = str(root_pinned)

    manifest_path = upload_root / "upload_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


__all__ = [
    "UPLOAD_PACKAGE_BUILDER_VERSION",
    "build_upload_packages",
    "resolve_run_dir",
]
