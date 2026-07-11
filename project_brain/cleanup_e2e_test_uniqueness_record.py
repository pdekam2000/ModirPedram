"""
Remove E2E planning-probe test rows from production uniqueness memory (safe, selective).

Does not delete content_history.json — only removes matching records after backup.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_brain.e2e_40s_uniqueness_memory import production_uniqueness_memory_path

# Known probe row from pre-isolation E2E 40s planning probe (2026-06-02).
KNOWN_PROBE_RECORD_ID = "uniq_e792a4abf5"
KNOWN_PROBE_TOPIC = "Girl in Rain"
KNOWN_PROBE_CREATED_PREFIX = "2026-06-02 18:16:"
KNOWN_PROBE_HOOK_FP = "moral_discomfort:74b3a30f54"
KNOWN_PROBE_BEAT_FP = "abdde4490f43"

E2E_METADATA_SOURCES = {
    "e2e_40s_planning_probe",
    "e2e_planning_probe",
    "e2e_40s_planning_probe_v1",
}


def _normalize_topic(value: Any) -> str:
    return str(value or "").strip().casefold()


def _record_metadata(record: dict[str, Any]) -> dict[str, Any]:
    meta = record.get("metadata")
    return meta if isinstance(meta, dict) else {}


def _is_e2e_probe_metadata(record: dict[str, Any]) -> bool:
    meta = _record_metadata(record)
    if not meta:
        return False
    source = str(meta.get("source", "")).strip().casefold()
    if source in {s.casefold() for s in E2E_METADATA_SOURCES}:
        return True
    if meta.get("e2e_planning_probe") is True:
        return True
    if str(meta.get("created_by", "")).casefold() in {"e2e", "e2e_40s", "e2e_planning_probe"}:
        return True
    return False


def _is_probe_timestamp(created_at: Any) -> bool:
    text = str(created_at or "").strip()
    return text.startswith(KNOWN_PROBE_CREATED_PREFIX)


def _is_known_probe_fingerprints(record: dict[str, Any]) -> bool:
    return (
        str(record.get("hook_fingerprint", "")) == KNOWN_PROBE_HOOK_FP
        and str(record.get("beat_fingerprint", "")) == KNOWN_PROBE_BEAT_FP
        and _is_probe_timestamp(record.get("created_at"))
    )


def should_remove_e2e_test_record(record: dict[str, Any]) -> bool:
    """
    Remove only the known E2E test row — topic plus at least one corroborating signal.
    """
    if not isinstance(record, dict):
        return False
    if _normalize_topic(record.get("topic")) != _normalize_topic(KNOWN_PROBE_TOPIC):
        return False

    if str(record.get("record_id", "")) == KNOWN_PROBE_RECORD_ID:
        return True
    if _is_e2e_probe_metadata(record):
        return True
    if _is_probe_timestamp(record.get("created_at")):
        return True
    if _is_known_probe_fingerprints(record):
        return True
    return False


def load_history(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"records": []}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {"records": []}
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError(f"Expected 'records' array in {path}")
    return payload


def write_history(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create_backup(path: Path, *, project_root: Path) -> Path:
    backups_dir = project_root / "storage" / "content_brain" / "memory" / "uniqueness" / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"content_history.backup_{stamp}.json"
    if path.is_file():
        shutil.copy2(path, backup_path)
    else:
        backup_path.write_text(json.dumps({"records": []}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return backup_path


def cleanup_e2e_test_records(
    memory_path: Path,
    *,
    dry_run: bool = False,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or ROOT).resolve()
    memory_path = memory_path.resolve()
    payload = load_history(memory_path)
    records = list(payload.get("records", []))
    original_count = len(records)

    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, dict) and should_remove_e2e_test_record(record):
            removed.append(record)
        else:
            kept.append(record)

    backup_path: Path | None = None
    if removed and not dry_run:
        backup_path = create_backup(memory_path, project_root=root)
        payload["records"] = kept
        write_history(memory_path, payload)
    elif removed and dry_run:
        backup_path = None

    return {
        "memory_path": str(memory_path),
        "dry_run": dry_run,
        "original_count": original_count,
        "removed_count": len(removed),
        "remaining_count": len(kept) if removed else original_count,
        "backup_path": str(backup_path) if backup_path else None,
        "removed_records": removed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove E2E test-only uniqueness records (selective).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matches without writing backup or editing content_history.json.",
    )
    parser.add_argument(
        "--memory-path",
        help="Override uniqueness memory file (for tests only).",
    )
    args = parser.parse_args(argv)

    memory_path = (
        Path(args.memory_path).resolve()
        if args.memory_path
        else production_uniqueness_memory_path(ROOT)
    )

    if not memory_path.is_file():
        print(f"[cleanup] No uniqueness memory file at {memory_path} — nothing to do.")
        return 0

    result = cleanup_e2e_test_records(memory_path, dry_run=args.dry_run, project_root=ROOT)

    print(f"[cleanup] memory_path={result['memory_path']}")
    print(f"[cleanup] dry_run={result['dry_run']}")
    print(f"[cleanup] original_count={result['original_count']}")
    print(f"[cleanup] removed_count={result['removed_count']}")
    print(f"[cleanup] remaining_count={result['remaining_count']}")
    if result["backup_path"]:
        print(f"[cleanup] backup_path={result['backup_path']}")
    elif result["removed_count"] and result["dry_run"]:
        print("[cleanup] backup_path=(skipped — dry-run)")

    if result["removed_count"] == 0:
        print("[cleanup] No matching E2E test record found — exited safely with no changes.")
        return 0

    for row in result["removed_records"]:
        print(
            f"[cleanup] removed record_id={row.get('record_id')} "
            f"topic={row.get('topic')!r} created_at={row.get('created_at')}"
        )

    if args.dry_run:
        print("[cleanup] Dry-run complete — production file not modified.")
    else:
        print("[cleanup] Cleanup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
