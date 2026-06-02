"""
E2E-40S — Uniqueness memory isolation for validation/planning probes only.

Production UAT and operator briefs use the default path:
  storage/content_brain/memory/uniqueness/content_history.json

E2E planning probes must never write there.
"""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from content_brain.engines.uniqueness_engine import DEFAULT_MEMORY_PATH


@dataclass(frozen=True)
class UniquenessMemorySnapshot:
    exists: bool
    record_count: int
    mtime_ns: int | None
    raw_text: str

    def equals(self, other: UniquenessMemorySnapshot) -> bool:
        return (
            self.exists == other.exists
            and self.record_count == other.record_count
            and self.raw_text == other.raw_text
        )


def production_uniqueness_memory_path(project_root: Path | str) -> Path:
    root = Path(project_root).resolve()
    return (root / DEFAULT_MEMORY_PATH).resolve()


def snapshot_uniqueness_memory(path: Path) -> UniquenessMemorySnapshot:
    if not path.is_file():
        return UniquenessMemorySnapshot(False, 0, None, "")
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    records = payload.get("records", []) if isinstance(payload, dict) else []
    count = len(records) if isinstance(records, list) else 0
    return UniquenessMemorySnapshot(True, count, path.stat().st_mtime_ns, text)


@contextmanager
def isolated_probe_memory_file() -> Iterator[Path]:
    """Temporary uniqueness history file for E2E planning probes only."""
    with tempfile.TemporaryDirectory(prefix="e2e_40s_uniqueness_probe_") as tmp:
        yield Path(tmp) / "content_history.json"


def count_records(memory_path: Path) -> int:
    return snapshot_uniqueness_memory(memory_path).record_count
