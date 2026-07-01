"""Create a verified clean restore point for ModirAgentOS (BACKUP-CLEANUP-1)."""
from __future__ import annotations

import fnmatch
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "storage" / "backups"
REGISTRY_PATH = ROOT / "project_brain" / "runtime_state" / "final_delivery_registry.json"

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "chrome_mapper_profile",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cursor",
    ".idea",
    ".vscode",
    "backup_temp",
    "backup_validation",
    "real_chrome_profile",
    "browser_session",
}

EXCLUDE_PATH_PREFIXES = (
    "storage/backups/",
    "storage/backup_validation/",
    "debug/",
)

EXCLUDE_REL_GLOBS = (
    "*.pyc",
    "*.pyo",
    "*.zip",
    "outputs/runs/*/debug/*",
    "outputs/runs/*/debug/**",
)

MEDIA_GLOBS = ("*.mp4", "*.webm", "*.mov", "*.mkv", "*.avi")

REQUIRED_PATHS = [
    "project_brain/runtime_state/final_delivery_registry.json",
    "project_brain/RUNWAY_PHASE_I_RESTORE_INSTRUCTIONS.md",
    "content_brain/execution/runway_ui_navigator.py",
    "ui/api/main.py",
]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _norm_rel(path: Path) -> str | None:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return None


def _load_include_media() -> set[str]:
    included: set[str] = set()
    if not REGISTRY_PATH.exists():
        return included
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return included
    for key in ("latest_video", "latest_publish_package"):
        raw = str(payload.get(key) or "").strip()
        if not raw:
            continue
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        try:
            rel = str(candidate.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        except ValueError:
            continue
        if candidate.is_file():
            included.add(rel)
        elif candidate.is_dir():
            for child in candidate.rglob("*"):
                if child.is_file():
                    rel_child = _norm_rel(child)
                    if rel_child:
                        included.add(rel_child)
    return included


def should_skip_dir(rel_parts: tuple[str, ...]) -> bool:
    for part in rel_parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    rel = "/".join(rel_parts)
    return rel.startswith(EXCLUDE_PATH_PREFIXES) or rel == "debug"


def should_skip_file(rel_path: str, name: str, include_media: set[str]) -> bool:
    if rel_path in include_media:
        return False
    if rel_path.startswith(EXCLUDE_PATH_PREFIXES):
        return True
    for pat in EXCLUDE_REL_GLOBS:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(name, pat):
            return True
    for pat in MEDIA_GLOBS:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def create_clean_restore_point(*, stamp: str | None = None) -> dict[str, object]:
    stamp = stamp or _now_stamp()
    zip_name = f"RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_CLEAN_{stamp}.zip"
    zip_path = BACKUP_DIR / zip_name
    include_media = _load_include_media()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    raw_bytes = 0
    skipped = 0

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            try:
                rel_dir = Path(dirpath).relative_to(ROOT)
            except ValueError:
                dirnames[:] = []
                continue
            parts = rel_dir.parts
            if should_skip_dir(parts):
                dirnames[:] = []
                continue

            dirnames[:] = [
                d
                for d in dirnames
                if d not in EXCLUDE_DIR_NAMES
                and not should_skip_dir((*parts, d))
            ]

            for fn in filenames:
                fp = Path(dirpath) / fn
                rel = _norm_rel(fp)
                if rel is None:
                    skipped += 1
                    continue
                if should_skip_file(rel, fn, include_media):
                    skipped += 1
                    continue
                if fp.resolve() == zip_path.resolve():
                    continue
                try:
                    zf.write(fp, rel)
                    count += 1
                    raw_bytes += fp.stat().st_size
                except (OSError, PermissionError):
                    skipped += 1

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        missing = [p for p in REQUIRED_PATHS if p not in names]
        missing_media = sorted(include_media - names)

    return {
        "zip_path": str(zip_path),
        "zip_name": zip_name,
        "zip_rel": str(zip_path.relative_to(ROOT)).replace("\\", "/"),
        "files": count,
        "skipped": skipped,
        "raw_bytes": raw_bytes,
        "zip_size": zip_path.stat().st_size,
        "missing_required": missing,
        "missing_included_media": missing_media,
        "included_media": sorted(include_media),
        "stamp": stamp,
    }


if __name__ == "__main__":
    result = create_clean_restore_point()
    for key, value in result.items():
        print(f"{key}={value}")
