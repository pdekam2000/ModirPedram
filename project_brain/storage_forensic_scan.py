"""PHASE STORAGE-FORENSIC-1 — read-only storage audit. Does NOT delete or modify files."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCAN_VERSION = "storage_forensic_scan_v1"

SPECIAL_FOLDERS = (
    "outputs/runs",
    "downloads/runway",
    "assets/videos",
    "storage/backups",
    "project_brain/archive",
    "project_brain/runtime_state",
    "debug",
)

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
JSON_MANIFEST_HINTS = ("manifest", "registry", "index", "report", "metadata")

BRANDED_CHAIN = re.compile(r"FINAL_BRANDED_VIDEO(_v\d+)?\.mp4$", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_bytes(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def _safe_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _hash_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class FileRecord:
    path: Path
    size: int
    mtime: float
    suffix: str

    @property
    def rel(self) -> str:
        return _safe_rel(self.path)


@dataclass
class ScanResult:
    files: list[FileRecord] = field(default_factory=list)
    total_size: int = 0
    folder_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    hash_by_path: dict[str, str] = field(default_factory=dict)
    duplicate_groups: dict[str, list[FileRecord]] = field(default_factory=dict)


def scan_project(root: Path) -> ScanResult:
    result = ScanResult()
    size_groups: dict[int, list[FileRecord]] = defaultdict(list)
    print(f"Scanning {root} ...", flush=True)

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip scanning our own output mid-write if re-run
        current = Path(dirpath)
        for name in filenames:
            path = current / name
            try:
                stat = path.stat()
            except OSError:
                continue
            if not path.is_file():
                continue
            record = FileRecord(path=path, size=int(stat.st_size), mtime=float(stat.st_mtime), suffix=path.suffix.lower())
            result.files.append(record)
            result.total_size += record.size
            if record.size > 0:
                size_groups[record.size].append(record)

    print(f"Indexed {len(result.files):,} files ({_fmt_bytes(result.total_size)})", flush=True)
    print("Hashing duplicate candidates (same-size groups) ...", flush=True)

    candidates = sum(1 for group in size_groups.values() if len(group) > 1)
    done = 0
    for size, group in size_groups.items():
        if len(group) < 2:
            continue
        done += 1
        if done % 500 == 0:
            print(f"  hashed groups {done}/{candidates}", flush=True)
        for record in group:
            rel = record.rel
            if rel in result.hash_by_path:
                continue
            try:
                result.hash_by_path[rel] = _hash_file(record.path)
            except OSError:
                continue
        by_hash: dict[str, list[FileRecord]] = defaultdict(list)
        for record in group:
            digest = result.hash_by_path.get(record.rel)
            if digest:
                by_hash[digest].append(record)
    # Build global duplicate groups from hashed files
    by_hash_global: dict[str, list[FileRecord]] = defaultdict(list)
    for record in result.files:
        digest = result.hash_by_path.get(record.rel)
        if digest:
            by_hash_global[digest].append(record)
    result.duplicate_groups = {
        digest: sorted(records, key=lambda item: item.rel)
        for digest, records in by_hash_global.items()
        if len(records) > 1
    }

    return result


def folder_analysis(root: Path, scan: ScanResult) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for rel in SPECIAL_FOLDERS:
        target = root / rel
        if not target.exists():
            stats[rel] = {
                "exists": False,
                "file_count": 0,
                "folder_count": 0,
                "size_bytes": 0,
                "size_human": "0 B",
                "last_modified": "",
                "estimated_reclaimable_bytes": 0,
            }
            continue
        file_count = 0
        folder_count = 0
        size_bytes = 0
        last_mtime = 0.0
        prefix = str(target.resolve()).lower()
        for record in scan.files:
            if str(record.path.resolve()).lower().startswith(prefix):
                file_count += 1
                size_bytes += record.size
                last_mtime = max(last_mtime, record.mtime)
        for item in target.rglob("*"):
            if item.is_dir():
                folder_count += 1
        stats[rel] = {
            "exists": True,
            "file_count": file_count,
            "folder_count": folder_count,
            "size_bytes": size_bytes,
            "size_human": _fmt_bytes(size_bytes),
            "last_modified": datetime.fromtimestamp(last_mtime, tz=timezone.utc).isoformat() if last_mtime else "",
            "estimated_reclaimable_bytes": 0,
        }
    return stats


def collect_referenced_paths(root: Path) -> set[str]:
    refs: set[str] = set()

    def add_path(value: str | Path) -> None:
        if not value:
            return
        path = Path(str(value))
        if not path.is_absolute():
            path = root / path
        try:
            refs.add(str(path.resolve()).lower())
            if path.is_file():
                refs.add(str(path.parent.resolve()).lower())
            elif path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file():
                        refs.add(str(child.resolve()).lower())
        except OSError:
            refs.add(str(path).lower())

    registry = _read_json(root / "project_brain" / "runtime_state" / "final_delivery_registry.json")
    for key in ("latest_video", "latest_publish_package", "latest_asset"):
        add_path(str(registry.get(key) or ""))
    run_id = str(registry.get("latest_run_id") or "")
    if run_id:
        refs.add(run_id.lower())

    index = _read_json(root / "outputs" / "runs" / "index.json")
    for run in index.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for key in ("run_dir", "final_video_path", "publish_dir", "runway_report_path"):
            add_path(str(run.get(key) or ""))

    # Story packages for indexed runs
    packages = root / "project_brain" / "story_packages"
    if packages.is_dir():
        for item in packages.glob("*.json"):
            refs.add(str(item.resolve()).lower())

    # Active runtime manifests
    runtime = root / "project_brain" / "runtime_state"
    if runtime.is_dir():
        for item in runtime.glob("*.json"):
            refs.add(str(item.resolve()).lower())

    # Core source — never orphan
    for keep in ("content_brain", "ui", "engines", "project_brain", ".env", "assets", "requirements"):
        path = root / keep
        if path.exists():
            refs.add(str(path.resolve()).lower())

    return refs


def classify_path(rel: str, *, is_duplicate_extra: bool = False) -> str:
    lowered = rel.lower().replace("\\", "/")
    if any(
        token in lowered
        for token in (
            "final_delivery_registry.json",
            "project_brain/runtime_state/final_delivery_registry.json",
            "outputs/runs/index.json",
        )
    ):
        return "DO_NOT_DELETE"
    if "__pycache__" in lowered or lowered.endswith(".pyc") or "/.pytest_cache/" in lowered:
        return "SAFE_TO_DELETE"
    if "chrome_mapper_profile" in lowered or "/node_modules/" in lowered:
        return "LIKELY_SAFE"
    if "/debug/" in lowered or lowered.endswith(".png") and "/debug/" in lowered:
        return "LIKELY_SAFE"
    if is_duplicate_extra:
        return "LIKELY_SAFE"
    if "/archive/" in lowered or "/storage/backups/" in lowered:
        return "REVIEW_REQUIRED"
    if "/outputs/runs/" in lowered or "/downloads/runway/" in lowered:
        return "REVIEW_REQUIRED"
    if "/assets/videos/" in lowered:
        return "REVIEW_REQUIRED"
    if lowered.startswith("content_brain/") or lowered.startswith("ui/"):
        return "DO_NOT_DELETE"
    return "REVIEW_REQUIRED"


def detect_branded_chains(scan: ScanResult) -> list[dict[str, Any]]:
    chains: dict[str, list[FileRecord]] = defaultdict(list)
    for record in scan.files:
        if not BRANDED_CHAIN.search(record.path.name):
            continue
        parent = str(record.path.parent.resolve()).lower()
        chains[parent].append(record)
    reports: list[dict[str, Any]] = []
    for parent, records in chains.items():
        ordered = sorted(records, key=lambda item: item.path.name.lower())
        digests = {item.rel: scan.hash_by_path.get(item.rel, "") for item in ordered}
        unique_digests = {digest for digest in digests.values() if digest}
        identical = len(unique_digests) == 1 and len(ordered) > 1
        reports.append(
            {
                "folder": parent,
                "files": [item.rel for item in ordered],
                "sizes": [item.size for item in ordered],
                "identical": identical,
                "unique_hashes": len(unique_digests),
                "superseded_candidates": [item.rel for item in ordered[:-1]] if len(ordered) > 1 else [],
            }
        )
    return sorted(reports, key=lambda item: sum(item["sizes"]), reverse=True)


def estimate_reclaimable(scan: ScanResult, folder_stats: dict[str, dict[str, Any]], refs: set[str]) -> dict[str, Any]:
    reclaimable = 0
    safe = 0
    likely = 0
    review = 0

    for digest, group in scan.duplicate_groups.items():
        if len(group) < 2:
            continue
        keep = sorted(group, key=lambda item: (0 if str(item.path.resolve()).lower() in refs else 1, item.rel))[0]
        for record in group:
            if record.rel == keep.rel:
                continue
            extra = record.size
            category = classify_path(record.rel, is_duplicate_extra=True)
            reclaimable += extra
            if category == "SAFE_TO_DELETE":
                safe += extra
            elif category == "LIKELY_SAFE":
                likely += extra
            else:
                review += extra

    for record in scan.files:
        rel = record.rel
        if rel.startswith("project_brain/TOP_") or rel.startswith("project_brain/STORAGE_"):
            continue
        cat = classify_path(rel)
        if cat == "SAFE_TO_DELETE":
            reclaimable += record.size
            safe += record.size
        elif cat == "LIKELY_SAFE" and "chrome_mapper_profile" in rel:
            likely += record.size
            reclaimable += record.size

    # Orphan runs: run folders not referenced and not latest approved
    runs_root = ROOT / "outputs" / "runs"
    if runs_root.is_dir():
        for run_dir in runs_root.iterdir():
            if not run_dir.is_dir() or run_dir.name == "index.json":
                continue
            run_key = str(run_dir.resolve()).lower()
            if run_key not in refs and not any(run_key in ref for ref in refs):
                size = sum(record.size for record in scan.files if record.rel.startswith(_safe_rel(run_dir) + "/") or record.rel.startswith(_safe_rel(run_dir)))
                if size:
                    review += size

    folder_stats["outputs/runs"]["estimated_reclaimable_bytes"] = review // 3 if review else 0
    folder_stats["debug"]["estimated_reclaimable_bytes"] = sum(
        record.size for record in scan.files if "/debug/" in record.rel.replace("\\", "/")
    )
    chrome_size = sum(record.size for record in scan.files if "chrome_mapper_profile" in record.rel)
    folder_stats.setdefault(
        "chrome_mapper_profile",
        {
            "exists": (ROOT / "chrome_mapper_profile").exists(),
            "file_count": sum(1 for record in scan.files if "chrome_mapper_profile" in record.rel),
            "size_bytes": chrome_size,
            "size_human": _fmt_bytes(chrome_size),
            "estimated_reclaimable_bytes": chrome_size,
        },
    )

    return {
        "total_reclaimable_bytes": reclaimable,
        "safe_to_delete_bytes": safe,
        "likely_safe_bytes": likely,
        "review_required_bytes": review,
        "chrome_mapper_profile_bytes": chrome_size,
    }


def write_csv_files(scan: ScanResult) -> None:
    brain = ROOT / "project_brain"
    top_files = sorted(scan.files, key=lambda item: item.size, reverse=True)[:100]
    with (brain / "TOP_LARGEST_FILES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "path", "size_bytes", "size_human", "modified_utc", "category"])
        for rank, record in enumerate(top_files, start=1):
            writer.writerow(
                [
                    rank,
                    record.rel,
                    record.size,
                    _fmt_bytes(record.size),
                    datetime.fromtimestamp(record.mtime, tz=timezone.utc).isoformat(),
                    classify_path(record.rel),
                ]
            )

    folder_sizes: dict[str, int] = defaultdict(int)
    folder_counts: dict[str, int] = defaultdict(int)
    folder_mtime: dict[str, float] = defaultdict(float)
    for record in scan.files:
        rel_parts = Path(record.rel).parts
        for depth in range(1, min(len(rel_parts) + 1, 6)):
            folder_key = "/".join(rel_parts[:depth])
            folder_sizes[folder_key] += record.size
            folder_counts[folder_key] += 1
            folder_mtime[folder_key] = max(folder_mtime[folder_key], record.mtime)

    top_folders = sorted(folder_sizes.items(), key=lambda item: item[1], reverse=True)[:50]
    with (brain / "TOP_LARGEST_FOLDERS.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "folder", "size_bytes", "size_human", "file_count", "last_modified_utc", "category"])
        for rank, (folder, size) in enumerate(top_folders, start=1):
            writer.writerow(
                [
                    rank,
                    folder,
                    size,
                    _fmt_bytes(size),
                    folder_counts[folder],
                    datetime.fromtimestamp(folder_mtime[folder], tz=timezone.utc).isoformat() if folder_mtime[folder] else "",
                    classify_path(folder),
                ]
            )

    with (brain / "DUPLICATE_FILES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "duplicate_count", "total_wasted_bytes", "paths", "category"])
        for digest, group in sorted(scan.duplicate_groups.items(), key=lambda item: sum(rec.size for rec in item[1]), reverse=True):
            if len(group) < 2:
                continue
            wasted = sum(item.size for item in group[1:])
            paths = " | ".join(item.rel for item in group)
            writer.writerow([digest, len(group), wasted, paths, classify_path(group[-1].rel, is_duplicate_extra=True)])


def count_by_pattern(scan: ScanResult, pattern: str) -> tuple[int, int]:
    count = 0
    size = 0
    needle = pattern.lower()
    for record in scan.files:
        if needle in record.rel.lower():
            count += 1
            size += record.size
    return count, size


def find_orphans(scan: ScanResult, refs: set[str]) -> list[dict[str, Any]]:
    orphans: list[dict[str, Any]] = []
    for record in scan.files:
        path_key = str(record.path.resolve()).lower()
        if path_key in refs:
            continue
        rel = record.rel.replace("\\", "/")
        if rel.startswith("project_brain/storage_forensic") or rel.startswith("project_brain/TOP_") or rel.startswith("project_brain/DUPLICATE_"):
            continue
        if record.size < 1024 * 1024 and not record.suffix in VIDEO_EXTS:
            continue
        if not any(token in rel for token in ("outputs/", "downloads/", "assets/videos/", "archive/", "debug/", "storage/")):
            continue
        orphans.append({"path": rel, "size_bytes": record.size, "size_human": _fmt_bytes(record.size), "category": classify_path(rel)})
    orphans.sort(key=lambda item: item["size_bytes"], reverse=True)
    return orphans[:200]


def render_forensic_report(
    scan: ScanResult,
    folder_stats: dict[str, dict[str, Any]],
    reclaim: dict[str, Any],
    refs: set[str],
    branded_chains: list[dict[str, Any]],
    orphans: list[dict[str, Any]],
) -> str:
    dup_videos = [
        (digest, group)
        for digest, group in scan.duplicate_groups.items()
        if len(group) > 1 and group[0].suffix in VIDEO_EXTS
    ]
    dup_images = [
        (digest, group)
        for digest, group in scan.duplicate_groups.items()
        if len(group) > 1 and group[0].suffix in IMAGE_EXTS
    ]
    dup_json = [
        (digest, group)
        for digest, group in scan.duplicate_groups.items()
        if len(group) > 1 and group[0].suffix == ".json"
    ]

    recovery_count, recovery_size = count_by_pattern(scan, "recover")
    archive_count, archive_size = count_by_pattern(scan, "archive")
    runway_count, runway_size = count_by_pattern(scan, "downloads/runway")
    debug_count, debug_size = count_by_pattern(scan, "/debug/")
    screenshot_count, screenshot_size = count_by_pattern(scan, "screenshot")
    screenshot_count += sum(1 for r in scan.files if r.path.name.startswith("subtitle_frame_") or r.path.name.endswith("_frame.png"))
    screenshot_size += sum(r.size for r in scan.files if r.path.name.startswith("subtitle_frame_") or r.path.name.endswith("_frame.png"))

    top_files = sorted(scan.files, key=lambda item: item.size, reverse=True)[:20]
    top_folders = sorted(
        ((folder, data["size_bytes"]) for folder, data in folder_stats.items() if data.get("exists")),
        key=lambda item: item[1],
        reverse=True,
    )

    lines = [
        "# Storage Forensic Report",
        "",
        f"Generated: {_now()}",
        f"Scanner: `{SCAN_VERSION}`",
        f"Project root: `{ROOT}`",
        "",
        "## Summary",
        "",
        f"- **Total project size:** {_fmt_bytes(scan.total_size)} ({scan.total_size:,} bytes)",
        f"- **Total files:** {len(scan.files):,}",
        f"- **Duplicate SHA256 groups:** {sum(1 for group in scan.duplicate_groups.values() if len(group) > 1):,}",
        f"- **Estimated reclaimable (heuristic):** {_fmt_bytes(reclaim['total_reclaimable_bytes'])}",
        f"- **Potential safe cleanup:** {_fmt_bytes(reclaim['safe_to_delete_bytes'] + reclaim['likely_safe_bytes'])}",
        "",
        "## Largest consumers",
        "",
    ]
    for index, (folder, size) in enumerate(top_folders[:10], start=1):
        lines.append(f"{index}. `{folder}` — {_fmt_bytes(size)}")
    lines.extend(["", "## Special folder analysis", "", "| Folder | Files | Subfolders | Size | Last modified | Est. reclaimable |", "|--------|------:|-----------:|-----:|----------------|-----------------:|"])

    for rel in list(SPECIAL_FOLDERS) + ["chrome_mapper_profile"]:
        data = folder_stats.get(rel, {})
        if not data:
            continue
        lines.append(
            f"| `{rel}` | {data.get('file_count', 0)} | {data.get('folder_count', 0)} | "
            f"{data.get('size_human', '0 B')} | {data.get('last_modified', '')} | "
            f"{_fmt_bytes(int(data.get('estimated_reclaimable_bytes') or 0))} |"
        )

    lines.extend(
        [
            "",
            "## Artifact counts",
            "",
            f"- Recovery outputs: **{recovery_count:,}** files ({_fmt_bytes(recovery_size)})",
            f"- Archived outputs: **{archive_count:,}** files ({_fmt_bytes(archive_size)})",
            f"- Old Runway downloads: **{runway_count:,}** files ({_fmt_bytes(runway_size)})",
            f"- Debug files: **{debug_count:,}** files ({_fmt_bytes(debug_size)})",
            f"- Screenshots / frame captures: **{screenshot_count:,}** files ({_fmt_bytes(screenshot_size)})",
            "",
            "## Duplicate analysis",
            "",
            f"- Duplicate files (SHA256 groups): **{sum(1 for g in scan.duplicate_groups.values() if len(g) > 1):,}** groups",
            f"- Duplicate videos: **{len(dup_videos):,}** groups",
            f"- Duplicate images: **{len(dup_images):,}** groups",
            f"- Duplicate JSON manifests: **{len(dup_json):,}** groups",
            "",
            "## Branded video chains",
            "",
        ]
    )
    for chain in branded_chains[:15]:
        lines.append(f"- `{chain['folder']}`")
        lines.append(f"  - files: {', '.join(chain['files'])}")
        lines.append(f"  - identical: **{chain['identical']}** | unique hashes: {chain['unique_hashes']}")
        if chain["superseded_candidates"]:
            lines.append(f"  - superseded candidates: {', '.join(chain['superseded_candidates'][:5])}")

    lines.extend(["", "## Top 20 largest files", "", "| Rank | Size | Category | Path |", "|-----:|-----:|----------|------|"])
    for rank, record in enumerate(top_files, start=1):
        lines.append(f"| {rank} | {_fmt_bytes(record.size)} | {classify_path(record.rel)} | `{record.rel}` |")

    lines.extend(["", "## Orphan candidates (sample)", "", "Not referenced by registry, run index, or latest approved run.", ""])
    for item in orphans[:25]:
        lines.append(f"- `{item['path']}` — {item['size_human']} ({item['category']})")

    lines.extend(
        [
            "",
            "## Categorization legend",
            "",
            "- **SAFE_TO_DELETE** — caches, bytecode, obvious temp artifacts",
            "- **LIKELY_SAFE** — debug captures, browser profile cache, duplicate extras",
            "- **REVIEW_REQUIRED** — runs, downloads, archives, assets",
            "- **DO_NOT_DELETE** — source code, active registry, approved delivery",
            "",
            "## CSV outputs",
            "",
            "- `project_brain/TOP_LARGEST_FILES.csv`",
            "- `project_brain/TOP_LARGEST_FOLDERS.csv`",
            "- `project_brain/DUPLICATE_FILES.csv`",
            "",
            "## Referenced delivery",
            "",
            f"- Registry latest run: `{_read_json(ROOT / 'project_brain/runtime_state/final_delivery_registry.json').get('latest_run_id', '')}`",
            f"- Registry latest video: `{_read_json(ROOT / 'project_brain/runtime_state/final_delivery_registry.json').get('latest_video', '')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_cleanup_plan(scan: ScanResult, reclaim: dict[str, Any], folder_stats: dict[str, dict[str, Any]], branded_chains: list[dict[str, Any]]) -> str:
    lines = [
        "# Storage Cleanup Plan",
        "",
        f"Generated: {_now()}",
        "",
        "> **DO NOT DELETE YET.** This plan is advisory only.",
        "",
        "## Current project size",
        "",
        f"**{_fmt_bytes(scan.total_size)}** ({scan.total_size:,} bytes)",
        "",
        "## Estimated reclaimable",
        "",
        f"**{_fmt_bytes(reclaim['total_reclaimable_bytes'])}** total heuristic reclaimable",
        "",
        f"- SAFE_TO_DELETE: {_fmt_bytes(reclaim['safe_to_delete_bytes'])}",
        f"- LIKELY_SAFE: {_fmt_bytes(reclaim['likely_safe_bytes'])}",
        f"- REVIEW_REQUIRED (manual): {_fmt_bytes(reclaim['review_required_bytes'])}",
        "",
        "## Largest consumers",
        "",
    ]
    ranked = sorted(
        ((name, data.get("size_bytes", 0)) for name, data in folder_stats.items() if data.get("size_bytes")),
        key=lambda item: item[1],
        reverse=True,
    )
    for index, (name, size) in enumerate(ranked[:10], start=1):
        lines.append(f"{index}. `{name}` — {_fmt_bytes(size)}")

    lines.extend(["", "## Potential safe cleanup (phased)", ""])
    if reclaim["safe_to_delete_bytes"]:
        lines.append(f"1. Remove Python caches and bytecode — est. {_fmt_bytes(reclaim['safe_to_delete_bytes'])}")
    if folder_stats.get("chrome_mapper_profile", {}).get("size_bytes"):
        lines.append(
            f"2. Archive or relocate `chrome_mapper_profile/` browser automation cache — est. "
            f"{_fmt_bytes(folder_stats['chrome_mapper_profile']['size_bytes'])} (**LIKELY_SAFE**, confirm not needed for active sessions)"
        )
    if folder_stats.get("debug", {}).get("estimated_reclaimable_bytes"):
        lines.append(f"3. Prune old `debug/` forensic frames after review — est. {_fmt_bytes(folder_stats['debug']['estimated_reclaimable_bytes'])}")
    dup_waste = sum(sum(item.size for item in group[1:]) for group in scan.duplicate_groups.values() if len(group) > 1)
    if dup_waste:
        lines.append(f"4. Deduplicate exact SHA256 copies (keep registry + latest run copies) — est. {_fmt_bytes(dup_waste)}")

    lines.extend(["", "## Branded video supersession", ""])
    for chain in branded_chains[:10]:
        if chain["superseded_candidates"]:
            lines.append(f"- Folder `{chain['folder']}`")
            lines.append(f"  - Keep newest: `{chain['files'][-1]}`")
            lines.append(f"  - Review for archive: {', '.join(chain['superseded_candidates'])}")

    lines.extend(
        [
            "",
            "## DO NOT DELETE without explicit approval",
            "",
            "- `project_brain/runtime_state/final_delivery_registry.json` targets",
            "- Latest approved run: `outputs/runs/20260613_091042_148bc322/`",
            "- `content_brain/`, `ui/`, active manifests in `project_brain/runtime_state/`",
            "- Only copy of a unique SHA256 artifact",
            "",
            "## Next phase (not executed here)",
            "",
            "1. Human review of REVIEW_REQUIRED buckets",
            "2. Move (not delete) superseded branded videos to `archive/legacy_outputs/`",
            "3. Relocate `chrome_mapper_profile` outside repo if automation allows",
            "4. Re-run this scanner and compare reclaim estimates",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    scan = scan_project(ROOT)
    folder_stats = folder_analysis(ROOT, scan)
    refs = collect_referenced_paths(ROOT)
    branded_chains = detect_branded_chains(scan)
    reclaim = estimate_reclaimable(scan, folder_stats, refs)
    orphans = find_orphans(scan, refs)

    brain = ROOT / "project_brain"
    write_csv_files(scan)
    (brain / "STORAGE_FORENSIC_REPORT.md").write_text(
        render_forensic_report(scan, folder_stats, reclaim, refs, branded_chains, orphans),
        encoding="utf-8",
    )
    (brain / "STORAGE_CLEANUP_PLAN.md").write_text(
        render_cleanup_plan(scan, reclaim, folder_stats, branded_chains),
        encoding="utf-8",
    )

    summary = {
        "total_size": scan.total_size,
        "total_files": len(scan.files),
        "duplicate_groups": sum(1 for group in scan.duplicate_groups.values() if len(group) > 1),
        "estimated_reclaimable": reclaim["total_reclaimable_bytes"],
        "report": str((brain / "STORAGE_FORENSIC_REPORT.md").resolve()),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
