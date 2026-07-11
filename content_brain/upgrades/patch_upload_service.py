"""Safe patch package upload for Upgrade Center — store only, never auto-apply."""

from __future__ import annotations

import json
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any

UPLOAD_SUBDIR = Path("project_brain") / "upgrades" / "uploaded"
ALLOWED_EXTENSIONS = {".zip", ".json", ".patch"}
BLOCKED_EXTENSIONS = {".exe", ".bat", ".ps1", ".cmd", ".com", ".scr", ".vbs", ".js", ".msi"}
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class PatchUploadError(Exception):
    """Raised when patch upload validation fails."""


def _sanitize_filename(name: str) -> str:
    stem = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return cleaned or f"patch_{uuid.uuid4().hex[:8]}"


def _validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in BLOCKED_EXTENSIONS:
        raise PatchUploadError(f"Blocked file extension: {ext}")
    if ext not in ALLOWED_EXTENSIONS:
        raise PatchUploadError(f"Unsupported file extension: {ext or '(none)'}")
    return ext


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            target = (dest_dir / member.filename).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise PatchUploadError(f"Path traversal blocked: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)


def _validate_manifest_if_present(folder: Path) -> None:
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatchUploadError(f"Invalid manifest.json: {exc}") from exc
    if not isinstance(payload, dict):
        raise PatchUploadError("manifest.json must be a JSON object")


def upload_patch_package(
    *,
    project_root: str | Path,
    filename: str,
    content: bytes,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> dict[str, Any]:
    if not content:
        raise PatchUploadError("Empty upload")
    if len(content) > max_bytes:
        raise PatchUploadError(f"File exceeds max size ({max_bytes} bytes)")

    ext = _validate_extension(filename)
    safe_name = _sanitize_filename(filename)
    root = Path(project_root).resolve()
    upload_root = root / UPLOAD_SUBDIR
    upload_root.mkdir(parents=True, exist_ok=True)

    upgrade_id = f"{Path(safe_name).stem}_{uuid.uuid4().hex[:8]}"
    target_dir = upload_root / upgrade_id
    target_dir.mkdir(parents=True, exist_ok=False)

    stored_path = target_dir / safe_name
    stored_path.write_bytes(content)

    extracted = False
    if ext == ".zip":
        _safe_extract_zip(stored_path, target_dir)
        extracted = True
        _validate_manifest_if_present(target_dir)
    elif ext == ".json":
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PatchUploadError(f"Invalid JSON upload: {exc}") from exc
        if not isinstance(payload, dict):
            raise PatchUploadError("JSON patch upload must be an object")
        manifest_path = target_dir / "manifest.json"
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "ok": True,
        "upgrade_id": upgrade_id,
        "filename": safe_name,
        "stored_path": str(stored_path.relative_to(root)).replace("\\", "/"),
        "extracted": extracted,
        "auto_applied": False,
    }


def list_uploaded_patches(project_root: str | Path) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    upload_root = root / UPLOAD_SUBDIR
    if not upload_root.is_dir():
        return []

    items: list[dict[str, Any]] = []
    for entry in sorted(upload_root.iterdir()):
        if not entry.is_dir():
            continue
        manifest = entry / "manifest.json"
        label = entry.name
        patch_type = "uploaded_folder"
        if manifest.is_file():
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
                if isinstance(meta, dict):
                    label = str(meta.get("name") or meta.get("title") or label)
                    patch_type = str(meta.get("type") or patch_type)
            except (OSError, json.JSONDecodeError):
                pass
        items.append(
            {
                "upgrade_id": entry.name,
                "label": label,
                "type": patch_type,
                "path": str(entry.relative_to(root)).replace("\\", "/"),
                "status": "uploaded",
            }
        )
    return items
