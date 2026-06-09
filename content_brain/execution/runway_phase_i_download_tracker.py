"""
Phase I.5 — Runway browser download verification for 3-clip continuity runs.

Tracks MP4 files under downloads/runway after operator-approved Download gates.
Does not invoke Assembly, Voice, or Subtitle pipelines.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_RELATIVE_DOWNLOAD_DIR = Path("downloads") / "runway"
VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov")


def default_runway_download_dir(project_root: Path | str) -> Path:
    return Path(project_root).resolve() / DEFAULT_RELATIVE_DOWNLOAD_DIR


@dataclass
class ClipDownloadRecord:
    clip_index: int
    downloaded: bool = False
    file_path: str = ""
    file_size_bytes: int = 0
    verified_at: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "downloaded": self.downloaded,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "verified_at": self.verified_at,
            "notes": list(self.notes),
        }


@dataclass
class RunwayPhaseIDownloadTracker:
    """Snapshot download dir at run start; verify new files after each clip download gate."""

    download_dir: Path
    simulate: bool = False
    project_id: str = "phase_i"
    wait_seconds: float = 8.0
    poll_interval_seconds: float = 0.5
    _baseline: dict[str, tuple[int, float]] = field(default_factory=dict, init=False)
    _assigned_paths: set[str] = field(default_factory=set, init=False)
    records: list[ClipDownloadRecord] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.download_dir = Path(self.download_dir).resolve()
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._baseline = self._scan_files()

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime(TIMESTAMP_FORMAT)

    def _scan_files(self) -> dict[str, tuple[int, float]]:
        snapshot: dict[str, tuple[int, float]] = {}
        if not self.download_dir.is_dir():
            return snapshot
        for path in self.download_dir.iterdir():
            if not path.is_file():
                continue
            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path.resolve())] = (int(stat.st_size), float(stat.st_mtime))
        return snapshot

    def _new_video_files(self) -> list[Path]:
        current = self._scan_files()
        fresh: list[Path] = []
        for path_str, (size, mtime) in current.items():
            if size <= 0:
                continue
            baseline = self._baseline.get(path_str)
            if baseline is None or baseline != (size, mtime):
                if path_str not in self._assigned_paths:
                    fresh.append(Path(path_str))
        fresh.sort(key=lambda item: item.stat().st_mtime if item.exists() else 0.0)
        return fresh

    def verify_clip_download(self, clip_index: int) -> ClipDownloadRecord:
        record = ClipDownloadRecord(clip_index=max(1, int(clip_index)))

        if self.simulate:
            simulated_path = self.download_dir / f"{self.project_id}_clip_{clip_index}_simulate.mp4"
            try:
                simulated_path.write_bytes(b"simulate")
            except OSError as exc:
                record.notes.append(f"simulate_write_failed: {exc}")
            else:
                record.downloaded = True
                record.file_path = str(simulated_path.resolve())
                record.file_size_bytes = simulated_path.stat().st_size
                record.notes.append("simulate=True placeholder file")
            record.verified_at = self._now()
            self.records.append(record)
            if record.file_path:
                self._assigned_paths.add(record.file_path)
            return record

        deadline = time.monotonic() + max(0.5, self.wait_seconds)
        chosen: Path | None = None
        while time.monotonic() <= deadline:
            candidates = self._new_video_files()
            if candidates:
                chosen = candidates[0]
                break
            time.sleep(self.poll_interval_seconds)

        if chosen is None:
            record.notes.append(
                f"no new video file detected in {self.download_dir} within {self.wait_seconds}s"
            )
            record.verified_at = self._now()
            self.records.append(record)
            return record

        try:
            size = int(chosen.stat().st_size)
        except OSError as exc:
            record.notes.append(f"stat_failed: {exc}")
            record.verified_at = self._now()
            self.records.append(record)
            return record

        if size <= 0:
            record.notes.append("file size is zero")
            record.verified_at = self._now()
            self.records.append(record)
            return record

        path_str = str(chosen.resolve())
        record.downloaded = True
        record.file_path = path_str
        record.file_size_bytes = size
        record.verified_at = self._now()
        record.notes.append("new_file_detected_after_download_gate")
        self._assigned_paths.add(path_str)
        self._baseline[path_str] = (size, float(chosen.stat().st_mtime))
        self.records.append(record)
        return record

    def report_fields(self, clip_count: int = 3) -> dict[str, Any]:
        by_index = {record.clip_index: record for record in self.records}
        paths: list[str] = []
        total = 0
        clip_flags: dict[str, bool] = {}

        for index in range(1, max(1, clip_count) + 1):
            record = by_index.get(index)
            downloaded = bool(record and record.downloaded and record.file_size_bytes > 0)
            clip_flags[f"clip_{index}_downloaded"] = downloaded
            if downloaded and record and record.file_path:
                paths.append(record.file_path)
                total += 1

        unique_paths = list(dict.fromkeys(paths))
        return {
            **clip_flags,
            "downloaded_file_paths": unique_paths,
            "total_downloads_completed": total,
            "download_dir": str(self.download_dir),
            "download_records": [record.to_dict() for record in self.records],
        }


__all__ = [
    "ClipDownloadRecord",
    "DEFAULT_RELATIVE_DOWNLOAD_DIR",
    "RunwayPhaseIDownloadTracker",
    "default_runway_download_dir",
]
