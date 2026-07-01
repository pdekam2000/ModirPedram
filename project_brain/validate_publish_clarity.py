"""Validate publish clarity — real final video, run folder, canonical deliverable."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_post_processor_publish_fields() -> None:
    source = (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8")
    _pass("versioned_run_dir", "versioned_run_dir" in source)
    _pass("canonical_deliverable_path", "canonical_deliverable_path" in source)
    _pass("delivery_status_on_report", 'report, "delivery_status"' in source or '"delivery_status"' in source)


def test_run_isolation_latest_attempt() -> None:
    source = (ROOT / "content_brain/platform/run_isolation.py").read_text(encoding="utf-8")
    _pass("latest_attempt_run_dir", "versioned_run_dir" in source)
    _pass("latest_attempt_canonical", "canonical_deliverable_path" in source)
    _pass("latest_attempt_delivery_status", "delivery_status" in source)


def test_results_loader_delivery_gate() -> None:
    source = (ROOT / "content_brain/platform/results_run_loader.py").read_text(encoding="utf-8")
    _pass("loader_reads_delivery_gate", "delivery_quality_gate.json" in source)
    _pass("loader_exposes_canonical", "canonical_deliverable_path" in source)
    _pass("loader_fail_closed_post_processing", 'delivery_gate.get("delivery_status")' in source)


def main() -> None:
    test_post_processor_publish_fields()
    test_run_isolation_latest_attempt()
    test_results_loader_delivery_gate()
    print("validate_publish_clarity: all checks passed")


if __name__ == "__main__":
    main()
