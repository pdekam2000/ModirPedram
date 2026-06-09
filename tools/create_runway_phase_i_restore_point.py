"""One-shot restore-point backup for Runway Phase I success state."""
from __future__ import annotations

import fnmatch
import os
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "storage" / "backups"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
ZIP_NAME = f"RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_{STAMP}.zip"
ZIP_PATH = BACKUP_DIR / ZIP_NAME

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
}

EXCLUDE_PATH_PREFIXES = (
    "storage/backups/",
)

EXCLUDE_GLOBS = (
    "*.pyc",
    "*.pyo",
    "*.mp4",
    "*.webm",
    "*.mov",
    "*.mkv",
    "*.zip",
)

IMPORTANT_FILES = [
    "project_brain/PHASE_IA_FIRST_SUCCESSFUL_3CLIP_RUN_REPORT.md",
    "project_brain/runway_phase_i_3clip_last_report.json",
    "project_brain/runway_ui_mapping/runway_ui_map.json",
    "project_brain/content_brain_test_results/latest.runway_prompts.txt",
    "content_brain/execution/runway_phase_i_strict_completion_gate.py",
    "content_brain/execution/runway_phase_i_artifact_tracker.py",
    "content_brain/execution/runway_phase_i_last_frame_use_frame.py",
    "content_brain/execution/runway_ui_navigator.py",
    "content_brain/execution/runway_live_smoke_test.py",
    "ui/api/runway_live_smoke_service.py",
    "ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx",
]


def _norm_rel(path: Path) -> str | None:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return None


def should_skip_dir(rel_parts: tuple[str, ...]) -> bool:
    for part in rel_parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    rel = "/".join(rel_parts)
    if rel.startswith(EXCLUDE_PATH_PREFIXES):
        return True
    return False


def should_skip_file(rel_path: str, name: str) -> bool:
    for pat in EXCLUDE_GLOBS:
        if fnmatch.fnmatch(name, pat):
            return True
    if rel_path.startswith(EXCLUDE_PATH_PREFIXES):
        return True
    return False


def create_backup() -> dict[str, object]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    raw_bytes = 0
    skipped = 0

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
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
                and not ((_norm_rel(rel_dir / d) or "").startswith(EXCLUDE_PATH_PREFIXES))
            ]

            for fn in filenames:
                fp = Path(dirpath) / fn
                rel = _norm_rel(fp)
                if rel is None:
                    skipped += 1
                    continue
                if should_skip_file(rel, fn):
                    skipped += 1
                    continue
                if fp.resolve() == ZIP_PATH.resolve():
                    continue
                try:
                    zf.write(fp, rel)
                    count += 1
                    raw_bytes += fp.stat().st_size
                except (OSError, PermissionError):
                    skipped += 1

    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = set(zf.namelist())
        missing = [p.replace("\\", "/") for p in IMPORTANT_FILES if p.replace("\\", "/") not in names]

    return {
        "zip_path": str(ZIP_PATH),
        "zip_name": ZIP_NAME,
        "files": count,
        "skipped": skipped,
        "raw_bytes": raw_bytes,
        "zip_size": ZIP_PATH.stat().st_size,
        "missing_important": missing,
        "stamp": STAMP,
    }


if __name__ == "__main__":
    result = create_backup()
    for key, value in result.items():
        print(f"{key}={value}")
