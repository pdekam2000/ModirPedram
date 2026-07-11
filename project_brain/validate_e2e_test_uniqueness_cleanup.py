"""
Validate cleanup_e2e_test_uniqueness_record.py safety and behavior.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_brain.cleanup_e2e_test_uniqueness_record import (
    cleanup_e2e_test_records,
    load_history,
    should_remove_e2e_test_record,
    write_history,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _fixture_payload() -> dict:
    return {
        "records": [
            {
                "record_id": "uniq_e792a4abf5",
                "created_at": "2026-06-02 18:16:43",
                "niche": "general",
                "topic": "Girl in Rain",
                "hook_fingerprint": "moral_discomfort:74b3a30f54",
                "beat_fingerprint": "abdde4490f43",
            },
            {
                "record_id": "uniq_keep_production_01",
                "created_at": "2026-06-01 10:00:00",
                "niche": "general",
                "topic": "operator production brief topic alpha",
                "hook_fingerprint": "open_loop:abc123",
                "beat_fingerprint": "ffffffff0001",
            },
            {
                "record_id": "uniq_other_girl_rain",
                "created_at": "2026-06-03 12:00:00",
                "niche": "general",
                "topic": "Girl in Rain",
                "hook_fingerprint": "other:0000000001",
                "beat_fingerprint": "bbbbbbbb0002",
            },
        ]
    }


def main() -> int:
    _pass("targets_only_corroborated_probe_row", should_remove_e2e_test_record(_fixture_payload()["records"][0]))
    _pass(
        "preserves_girl_in_rain_without_probe_signals",
        not should_remove_e2e_test_record(_fixture_payload()["records"][2]),
    )
    _pass(
        "preserves_unrelated_record",
        not should_remove_e2e_test_record(_fixture_payload()["records"][1]),
    )

    with tempfile.TemporaryDirectory() as tmp:
        memory_path = Path(tmp) / "content_history.json"
        write_history(memory_path, _fixture_payload())

        result = cleanup_e2e_test_records(memory_path, dry_run=False, project_root=ROOT)
        _pass("backup_created", result.get("backup_path") is not None, str(result.get("backup_path")))
        _pass("only_target_removed", result["removed_count"] == 1, f"removed={result['removed_count']}")
        _pass("unrelated_records_preserved", result["remaining_count"] == 2, f"remaining={result['remaining_count']}")

        payload = load_history(memory_path)
        json.dumps(payload, ensure_ascii=False)
        _pass("json_remains_valid", isinstance(payload.get("records"), list))
        remaining_ids = {r.get("record_id") for r in payload["records"]}
        _pass("kept_production_row", "uniq_keep_production_01" in remaining_ids)
        _pass("kept_other_girl_in_rain", "uniq_other_girl_rain" in remaining_ids)
        _pass("removed_probe_row", "uniq_e792a4abf5" not in remaining_ids)

    with tempfile.TemporaryDirectory() as tmp:
        empty_path = Path(tmp) / "content_history.json"
        write_history(empty_path, {"records": []})
        missing = cleanup_e2e_test_records(empty_path, dry_run=False, project_root=ROOT)
        _pass("safe_when_record_missing", missing["removed_count"] == 0)
        _pass("safe_missing_no_backup", missing.get("backup_path") is None)

    with tempfile.TemporaryDirectory() as tmp:
        only_keep = Path(tmp) / "content_history.json"
        write_history(only_keep, {"records": [_fixture_payload()["records"][1]]})
        dry = cleanup_e2e_test_records(only_keep, dry_run=True, project_root=ROOT)
        after = load_history(only_keep)
        _pass("dry_run_leaves_file_unchanged", len(after["records"]) == 1 and dry["removed_count"] == 0)

    print("\nE2E test uniqueness cleanup validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
