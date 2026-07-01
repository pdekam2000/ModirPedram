"""PHASE BACKUP-CLEANUP-1 — validate, delete corrupt backups, create clean restore point."""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAIN = ROOT / "project_brain"
BACKUP_DIR = ROOT / "storage" / "backups"
VALIDATION_DIR = ROOT / "storage" / "backup_validation"
NEW_VALIDATION_DIR = ROOT / "storage" / "new_backup_validation"

KEEP_ZIP = BACKUP_DIR / "RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip"
DELETE_CORRUPT = BACKUP_DIR / "RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip"
DELETE_STUB = BACKUP_DIR / "RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip"

REQUIRED_IN_ARCHIVE = [
    "project_brain/PHASE_IA_FIRST_SUCCESSFUL_3CLIP_RUN_REPORT.md",
    "project_brain/runway_phase_i_3clip_last_report.json",
    "project_brain/runtime_state/final_delivery_registry.json",
    "content_brain/execution/runway_ui_navigator.py",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_bytes(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def validate_zip(path: Path, extract_to: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "status": "FAIL",
        "verdict": "UNSAFE",
        "errors": [],
        "warnings": [],
    }
    if not path.exists():
        result["errors"] = ["Archive missing"]
        return result

    try:
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
            if bad:
                result["errors"] = [f"Corrupt entry: {bad}"]
                return result
            names = zf.namelist()
            result["entry_count"] = len(names)
            missing = [req for req in REQUIRED_IN_ARCHIVE if req not in names]
            if missing:
                result["warnings"].append(f"Missing recommended paths: {missing}")
    except (OSError, zipfile.BadZipFile) as exc:
        result["errors"] = [f"ZIP integrity failed: {exc}"]
        return result

    if extract_to.exists():
        shutil.rmtree(extract_to, ignore_errors=True)
    extract_to.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(extract_to)
    except (OSError, zipfile.BadZipFile) as exc:
        result["errors"] = [f"Extraction failed: {exc}"]
        return result

    extracted_files = sum(1 for _ in extract_to.rglob("*") if _.is_file())
    result["extracted_files"] = extracted_files
    if extracted_files == 0:
        result["errors"] = ["Extraction produced zero files"]
        return result

    result["status"] = "PASS"
    result["verdict"] = "SAFE_TO_KEEP"
    return result


def write_validation_report(path: Path, validation: dict[str, object], *, title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"Generated: {_now()}",
        "",
        f"- **Archive:** `{validation['path']}`",
        f"- **Size:** {_fmt_bytes(int(validation.get('size_bytes', 0)))}",
        f"- **Verdict:** `{validation.get('verdict', 'UNKNOWN')}`",
        f"- **Status:** `{validation.get('status', 'UNKNOWN')}`",
        "",
    ]
    if validation.get("entry_count") is not None:
        lines.append(f"- **ZIP entries:** {validation['entry_count']:,}")
    if validation.get("extracted_files") is not None:
        lines.append(f"- **Extracted files:** {validation['extracted_files']:,}")
    lines.append("")
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    if errors:
        lines.extend(["## Errors", ""])
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")
    if warnings:
        lines.extend(["## Warnings", ""])
        for warn in warnings:
            lines.append(f"- {warn}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def append_deletion_log(entries: list[dict[str, object]]) -> None:
    log_path = BRAIN / "BACKUP_DELETION_LOG.md"
    header = [
        "# Backup Deletion Log",
        "",
        f"Phase: BACKUP-CLEANUP-1",
        f"Timestamp: {_now()}",
        "",
        "| File | Size | Reason | Result |",
        "|------|-----:|--------|--------|",
    ]
    rows = []
    for entry in entries:
        rows.append(
            f"| `{entry['path']}` | {_fmt_bytes(int(entry['size_bytes']))} | {entry['reason']} | {entry['result']} |"
        )
    log_path.write_text("\n".join(header + rows) + "\n", encoding="utf-8")


def main() -> int:
    space_before = _dir_size(BACKUP_DIR)

    print("STEP 1 — Safety check", flush=True)
    keep_validation = validate_zip(KEEP_ZIP, VALIDATION_DIR)
    write_validation_report(BRAIN / "BACKUP_VALIDATION_REPORT.md", keep_validation, title="Backup Validation Report")

    if keep_validation.get("verdict") != "SAFE_TO_KEEP":
        print("VALIDATION FAILED — STOPPING. No deletions performed.", flush=True)
        print(json.dumps(keep_validation, indent=2))
        return 1

    print("STEP 2-3 — Delete corrupt backup and stub", flush=True)
    deletion_entries: list[dict[str, object]] = []
    deleted: list[dict[str, object]] = []

    for target, reason in (
        (DELETE_CORRUPT, "Corrupt archive; not restorable; superseded; orphan trailing blob"),
        (DELETE_STUB, "Corrupt stub file"),
    ):
        size_bytes = target.stat().st_size if target.exists() else 0
        entry = {
            "path": str(target.relative_to(ROOT)).replace("\\", "/"),
            "size_bytes": size_bytes,
            "reason": reason,
            "result": "SKIPPED",
        }
        if target.exists():
            try:
                target.unlink()
                entry["result"] = "DELETED"
                deleted.append(entry)
            except OSError as exc:
                entry["result"] = f"FAILED: {exc}"
        else:
            entry["result"] = "NOT_FOUND"
        deletion_entries.append(entry)

    append_deletion_log(deletion_entries)

    print("STEP 4 — Clean temp validation data", flush=True)
    if VALIDATION_DIR.exists():
        shutil.rmtree(VALIDATION_DIR, ignore_errors=True)

    print("STEP 5 — Create new clean restore point", flush=True)
    sys.path.insert(0, str(ROOT / "tools"))
    from create_clean_restore_point import create_clean_restore_point  # noqa: WPS433

    create_result = create_clean_restore_point()
    new_zip = Path(create_result["zip_path"])
    if create_result.get("missing_required"):
        print(f"WARNING missing required: {create_result['missing_required']}", flush=True)

    print("STEP 6 — Verify new backup", flush=True)
    new_validation = validate_zip(new_zip, NEW_VALIDATION_DIR)
    new_validation["missing_required"] = create_result.get("missing_required", [])
    new_validation["included_media"] = create_result.get("included_media", [])
    write_validation_report(
        BRAIN / "NEW_BACKUP_VALIDATION_REPORT.md",
        new_validation,
        title="New Backup Validation Report",
    )

    if NEW_VALIDATION_DIR.exists():
        shutil.rmtree(NEW_VALIDATION_DIR, ignore_errors=True)

    space_after = _dir_size(BACKUP_DIR)
    reclaimed = max(0, space_before - space_after)

    completion = [
        "# Backup Cleanup Completion Report",
        "",
        f"Generated: {_now()}",
        f"Phase: BACKUP-CLEANUP-1",
        "",
        "## Summary",
        "",
        f"- **Validation of keep archive:** `{keep_validation.get('verdict')}`",
        f"- **New backup validation:** `{new_validation.get('verdict')}`",
        "",
        "## Space",
        "",
        f"- **Backup folder before cleanup:** {_fmt_bytes(space_before)} ({space_before:,} bytes)",
        f"- **Backup folder after cleanup:** {_fmt_bytes(space_after)} ({space_after:,} bytes)",
        f"- **Space reclaimed:** {_fmt_bytes(reclaimed)} ({reclaimed:,} bytes)",
        "",
        "## Deleted files",
        "",
    ]
    for entry in deletion_entries:
        completion.append(
            f"- `{entry['path']}` — {_fmt_bytes(int(entry['size_bytes']))} — **{entry['result']}** — {entry['reason']}"
        )
    completion.extend(
        [
            "",
            "## New restore point",
            "",
            f"- **Path:** `{create_result['zip_rel']}`",
            f"- **Size:** {_fmt_bytes(int(create_result['zip_size']))} ({int(create_result['zip_size']):,} bytes)",
            f"- **Files archived:** {create_result['files']:,}",
            f"- **Included approved media:** {', '.join(f'`{p}`' for p in create_result.get('included_media', [])) or 'none'}",
            "",
            "## Remaining backups in storage/backups/",
            "",
        ]
    )
    for item in sorted(BACKUP_DIR.iterdir(), key=lambda p: p.stat().st_size if p.is_file() else 0, reverse=True):
        if item.is_file():
            completion.append(f"- `{item.name}` — {_fmt_bytes(item.stat().st_size)}")
        elif item.is_dir():
            completion.append(f"- `{item.name}/` (directory)")

    (BRAIN / "BACKUP_CLEANUP_COMPLETION_REPORT.md").write_text("\n".join(completion) + "\n", encoding="utf-8")

    print(json.dumps({"reclaimed_bytes": reclaimed, "new_zip": create_result["zip_rel"]}, indent=2))
    return 0 if new_validation.get("verdict") == "SAFE_TO_KEEP" else 2


if __name__ == "__main__":
    raise SystemExit(main())
