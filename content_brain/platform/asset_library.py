"""Asset Library — permanent vault for publish-ready final branded videos."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.canonical_delivery import (
    CANONICAL_BRANDED_VIDEO_NAME,
    resolve_canonical_final_video,
)
from content_brain.platform.final_delivery_registry import resolve_approved_delivery
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

ASSET_LIBRARY_VERSION = "asset_library_v1"
ASSET_INDEX_FILENAME = "asset_index.json"
ASSET_ROOT = Path("assets")
BRANDED_VIDEO_NAME = CANONICAL_BRANDED_VIDEO_NAME
PUBLISH_STATUS_CREATED = "PUBLISHED_PACKAGE_CREATED"

CATEGORY_CHOICES = ("cartoon", "wildlife", "technology", "history", "other")

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cartoon": ("cartoon", "animated", "animation", "anime", "cat explorer", "cute orange"),
    "wildlife": ("wildlife", "lion", "tiger", "scorpion", "animal", "nature", "forest", "ocean"),
    "technology": ("technology", "tech", "gpu", "rtx", "computer", "pc", "software", "ai ", "robot"),
    "history": ("history", "historical", "ancient", "war", "empire", "century", "documentary"),
}

VAULT_SUBDIRS = (
    ASSET_ROOT / "videos",
    ASSET_ROOT / "youtube_shorts",
    ASSET_ROOT / "tiktok",
    ASSET_ROOT / "instagram",
    ASSET_ROOT / "cartoon",
    ASSET_ROOT / "wildlife",
    ASSET_ROOT / "technology",
    ASSET_ROOT / "history",
    ASSET_ROOT / "archive",
    *(ASSET_ROOT / "videos" / category for category in CATEGORY_CHOICES),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def asset_index_path(project_root: Path) -> Path:
    return project_root / ASSET_ROOT / ASSET_INDEX_FILENAME


def asset_library_root(project_root: Path) -> Path:
    return project_root / ASSET_ROOT


def ensure_asset_library_structure(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    library_root = asset_library_root(root)
    library_root.mkdir(parents=True, exist_ok=True)
    for rel in VAULT_SUBDIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)
    index_path = asset_index_path(root)
    if not index_path.is_file():
        index_path.write_text(
            json.dumps({"version": ASSET_LIBRARY_VERSION, "assets": [], "updated_at": _now_iso()}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return library_root


def load_asset_index(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_asset_library_structure(root)
    path = asset_index_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("version", ASSET_LIBRARY_VERSION)
    payload.setdefault("assets", [])
    return payload


def save_asset_index(project_root: str | Path, payload: dict[str, Any]) -> None:
    root = Path(project_root).resolve()
    ensure_asset_library_structure(root)
    payload = dict(payload)
    payload["version"] = ASSET_LIBRARY_VERSION
    payload["updated_at"] = _now_iso()
    asset_index_path(root).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify_topic(topic: str, *, max_len: int = 48) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(topic or "untitled").strip().lower()).strip("_")
    if not text:
        text = "untitled"
    return text[:max_len].strip("_") or "untitled"


def classify_asset_category(topic: str, profile: dict[str, Any] | None = None) -> str:
    profile = dict(profile or {})
    haystack = " ".join(
        [
            str(topic or ""),
            str(profile.get("channel_topic") or ""),
            str(profile.get("main_niche") or ""),
            str(profile.get("sub_niche") or ""),
            str(profile.get("visual_style") or ""),
        ]
    ).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "other"


def resolve_unique_vault_filename(base_name: str, target_dir: Path) -> str:
    candidate = f"{base_name}.mp4"
    if not (target_dir / candidate).exists():
        return candidate
    version = 2
    while (target_dir / f"{base_name}_v{version}.mp4").exists():
        version += 1
    return f"{base_name}_v{version}.mp4"


def find_asset_by_checksum(index: dict[str, Any], checksum: str) -> dict[str, Any] | None:
    for item in list(index.get("assets") or []):
        if isinstance(item, dict) and str(item.get("checksum_sha256") or "") == checksum:
            return item
    return None


def _probe_duration_seconds(path: Path) -> float | None:
    try:
        import subprocess

        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            return None
        return float((proc.stdout or "").strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _read_publish_metadata(publish_dir: Path) -> dict[str, Any]:
    metadata_path = publish_dir / "metadata.json"
    if not metadata_path.is_file():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def register_published_asset(
    project_root: str | Path,
    *,
    publish_manifest: dict[str, Any],
    run_id: str,
    topic: str,
    run_dir: str | Path,
    assembly_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    profile = ProductChannelProfileStore(root).load()
    if not bool(profile.get("asset_vault_enabled", True)):
        return {"status": "skipped_disabled", "asset_id": ""}

    publish_status = str(publish_manifest.get("status") or "")
    if publish_status != PUBLISH_STATUS_CREATED:
        return {"status": "skipped_publish_not_ready", "publish_status": publish_status, "asset_id": ""}

    run_dir_path = Path(run_dir).resolve()
    delivery = resolve_approved_delivery(root, run_id=run_id)
    source_video = resolve_canonical_final_video(root, run_dir=run_dir_path, run_id=run_id)
    if source_video is None and delivery:
        candidate = Path(str(delivery.get("canonical_final_video_path") or ""))
        if candidate.is_file() and candidate.stat().st_size > 0:
            source_video = candidate.resolve()
    if source_video is None:
        return {"status": "skipped_branded_missing", "asset_id": ""}

    ensure_asset_library_structure(root)
    index = load_asset_index(root)
    checksum = sha256_file(source_video)
    existing = find_asset_by_checksum(index, checksum)
    if existing:
        return {
            "status": "duplicate_skipped",
            "asset_id": str(existing.get("asset_id") or ""),
            "final_video_path": str(existing.get("final_video_path") or ""),
            "checksum_sha256": checksum,
        }

    category = classify_asset_category(topic, profile)
    vault_dir = root / ASSET_ROOT / "videos" / category
    vault_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify_topic(topic)
    short_run = slugify_topic(run_id or "run", max_len=16)
    base_name = f"{_now_stamp()}_{slug}" if slug else f"{_now_stamp()}_{short_run}"
    vault_filename = resolve_unique_vault_filename(base_name, vault_dir)
    vault_path = vault_dir / vault_filename

    copy_mode = str(profile.get("asset_copy_mode") or "copy").strip().lower()
    shutil.copy2(source_video, vault_path)

    publish_metadata = _read_publish_metadata(run_dir_path / "publish")
    assembly_manifest = dict(assembly_manifest or {})
    duration = publish_manifest.get("duration_seconds")
    if duration is None:
        duration = publish_metadata.get("duration_seconds")
    if duration is None:
        duration = _probe_duration_seconds(vault_path)

    narration_provider = str(publish_manifest.get("narration_provider") or publish_metadata.get("narration_provider") or "")
    music_status = str(publish_metadata.get("music_status") or "")
    music_provider = str(publish_metadata.get("music_provider") or profile.get("music_provider") or "")

    asset_id = f"asset_{vault_path.stem}_{uuid.uuid4().hex[:8]}"
    record = {
        "asset_id": asset_id,
        "run_id": str(run_id or ""),
        "topic": str(topic or ""),
        "category": category,
        "creation_time": _now_iso(),
        "source_run_folder": str(run_dir_path),
        "source_video_path": str(source_video),
        "final_video_path": str(vault_path.resolve()),
        "checksum_sha256": checksum,
        "duration": duration,
        "duration_seconds": duration,
        "clip_count": int((assembly_manifest or {}).get("clip_count") or publish_metadata.get("clip_count") or 0),
        "branding_enabled": bool(publish_metadata.get("branding_enabled", profile.get("branding_enabled", True))),
        "narration_enabled": narration_provider not in {"", "none", "disabled"},
        "music_enabled": music_status == "PASS" or music_provider not in {"", "none", "disabled"},
        "copy_mode": copy_mode,
        "thumbnail_path": "",
    }

    assets = [item for item in list(index.get("assets") or []) if isinstance(item, dict)]
    assets.insert(0, record)
    index["assets"] = assets[:500]
    save_asset_index(root, index)

    return {
        "status": "registered",
        "asset_id": asset_id,
        "final_video_path": str(vault_path.resolve()),
        "category": category,
        "checksum_sha256": checksum,
        "copy_mode": copy_mode,
    }


def list_latest_assets(project_root: str | Path, *, limit: int = 12) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    delivery = resolve_approved_delivery(root)
    if delivery and delivery.get("latest_asset"):
        asset_path = Path(str(delivery["latest_asset"]))
        if asset_path.is_file():
            return [
                {
                    "asset_id": f"approved_{delivery.get('latest_run_id') or 'latest'}",
                    "run_id": delivery.get("latest_run_id") or "",
                    "topic": "",
                    "final_video_path": str(asset_path.resolve()),
                    "source_video_path": str(delivery.get("canonical_final_video_path") or ""),
                    "approved": True,
                }
            ]
    index = load_asset_index(project_root)
    assets = [item for item in list(index.get("assets") or []) if isinstance(item, dict)]
    approved_only = [item for item in assets if item.get("approved") is not False]
    return approved_only[: max(1, int(limit))]


__all__ = [
    "ASSET_LIBRARY_VERSION",
    "ASSET_ROOT",
    "BRANDED_VIDEO_NAME",
    "asset_library_root",
    "classify_asset_category",
    "ensure_asset_library_structure",
    "find_asset_by_checksum",
    "list_latest_assets",
    "load_asset_index",
    "register_published_asset",
    "resolve_unique_vault_filename",
    "sha256_file",
    "slugify_topic",
]
