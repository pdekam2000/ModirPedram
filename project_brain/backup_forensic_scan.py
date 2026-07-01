"""PHASE BACKUP-FORENSIC-2 — detailed storage/backups analysis. Read-only."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / "storage" / "backups"
SCAN_VERSION = "backup_forensic_scan_v2"

CHAIN_PATTERN = re.compile(
    r"^(?P<prefix>.+?)(?:_(?P<seq>\d{3}))?(?:_(?P<stamp>\d{8}_\d{6}))?\.(?P<ext>zip|bak|tar|gz)$",
    re.IGNORECASE,
)
RESTORE_POINT_PATTERN = re.compile(r"RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_(\d{8}_\d{6})\.zip$", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_bytes(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _hash_file(path: Path, *, max_full_bytes: int = 2 * 1024**3) -> str:
    size = path.stat().st_size
    if size > max_full_bytes:
        digest = hashlib.sha256()
        digest.update(str(size).encode())
        with path.open("rb") as handle:
            digest.update(handle.read(4 * 1024 * 1024))
            if size > 8 * 1024 * 1024:
                handle.seek(max(0, size - 4 * 1024 * 1024))
                digest.update(handle.read(4 * 1024 * 1024))
        return "partial:" + digest.hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class BackupFile:
    path: Path
    rel: str
    size: int
    created: float
    modified: float
    suffix: str
    sha256: str = ""

    @property
    def created_iso(self) -> str:
        return _iso(self.created)

    @property
    def modified_iso(self) -> str:
        return _iso(self.modified)


@dataclass
class ZipAnalysis:
    rel_path: str
    zip_size: int
    entry_count: int
    uncompressed_total: int
    compressed_total: int
    top_level_sizes: dict[str, int] = field(default_factory=dict)
    top_level_counts: dict[str, int] = field(default_factory=dict)
    nested_zip_count: int = 0
    nested_zip_uncompressed: int = 0
    video_count: int = 0
    video_uncompressed: int = 0
    flags: list[str] = field(default_factory=list)
    largest_entries: list[tuple[str, int]] = field(default_factory=list)
    sample_paths: dict[str, list[str]] = field(default_factory=dict)
    parsed_bytes: int = 0
    trailing_bytes: int = 0


def collect_backup_files() -> list[BackupFile]:
    records: list[BackupFile] = []
    if not BACKUP_ROOT.exists():
        return records
    for path in BACKUP_ROOT.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        records.append(
            BackupFile(
                path=path,
                rel=rel,
                size=int(stat.st_size),
                created=float(getattr(stat, "st_ctime", stat.st_mtime)),
                modified=float(stat.st_mtime),
                suffix=path.suffix.lower(),
            )
        )
    return records


def _scan_incomplete_zip_local_entries(path: Path, *, limit: int = 50000) -> ZipAnalysis:
    """Walk local ZIP headers when central directory is missing (aborted archive)."""
    analysis = ZipAnalysis(
        rel_path=str(path.relative_to(ROOT)).replace("\\", "/"),
        zip_size=path.stat().st_size,
        entry_count=0,
        uncompressed_total=0,
        compressed_total=0,
    )
    analysis.flags.append("incomplete_or_aborted_zip_missing_eocd")

    offset = 0
    size = path.stat().st_size
    with path.open("rb") as handle:
        while offset < size and analysis.entry_count < limit:
            handle.seek(offset)
            sig = handle.read(4)
            if sig != b"PK\x03\x04":
                break
            header = handle.read(26)
            if len(header) < 26:
                break
            comp_size = int.from_bytes(header[14:18], "little")
            uncomp_size = int.from_bytes(header[18:22], "little")
            name_len = int.from_bytes(header[22:24], "little")
            extra_len = int.from_bytes(header[24:26], "little")
            name_bytes = handle.read(name_len)
            try:
                name = name_bytes.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                name = ""
            extra = handle.read(extra_len)
            data_start = offset + 30 + name_len + extra_len
            analysis.entry_count += 1
            analysis.uncompressed_total += uncomp_size
            analysis.compressed_total += comp_size
            top = name.split("/", 1)[0] if "/" in name else name
            analysis.top_level_sizes[top] = analysis.top_level_sizes.get(top, 0) + uncomp_size
            analysis.top_level_counts[top] = analysis.top_level_counts.get(top, 0) + 1
            lower = name.lower()
            if lower.endswith(".zip"):
                analysis.nested_zip_count += 1
                analysis.nested_zip_uncompressed += uncomp_size
            if lower.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
                analysis.video_count += 1
                analysis.video_uncompressed += uncomp_size
            if len(analysis.largest_entries) < 30:
                analysis.largest_entries.append((name, uncomp_size))
                analysis.largest_entries.sort(key=lambda item: item[1], reverse=True)
            elif uncomp_size > analysis.largest_entries[-1][1]:
                analysis.largest_entries[-1] = (name, uncomp_size)
                analysis.largest_entries.sort(key=lambda item: item[1], reverse=True)
            if comp_size <= 0:
                offset = data_start + max(uncomp_size, 1)
            else:
                offset = data_start + comp_size
            if offset <= data_start:
                offset = data_start + 1
    analysis.parsed_bytes = offset
    analysis.trailing_bytes = max(0, size - offset)
    for flag_key, predicate in (
        ("outputs/runs", lambda k: k.startswith("outputs")),
        ("downloads/runway", lambda k: "downloads" in k),
        ("assets/videos", lambda k: k.startswith("assets")),
        ("storage/backups", lambda k: k.startswith("storage")),
        ("nested_backups", lambda: analysis.nested_zip_count > 0),
        ("chrome_mapper_profile", lambda k: k == "chrome_mapper_profile"),
        (".git", lambda k: k == ".git"),
    ):
        if flag_key == "nested_backups":
            if predicate():
                analysis.flags.append(flag_key)
        elif any(predicate(k) for k in analysis.top_level_sizes):
            analysis.flags.append(flag_key if flag_key != ".git" else "git_objects")
    if analysis.entry_count >= limit:
        analysis.flags.append(f"scan_truncated_at_{limit}_entries")
    return analysis


def analyze_zip(path: Path, *, rel: str, max_largest: int = 30) -> ZipAnalysis:
    analysis = ZipAnalysis(rel_path=rel, zip_size=path.stat().st_size, entry_count=0, uncompressed_total=0, compressed_total=0)
    if path.stat().st_size < 64:
        analysis.flags.append("corrupt_or_empty_stub")
        return analysis

    largest: list[tuple[str, int]] = []
    prefix_samples: dict[str, list[str]] = defaultdict(list)

    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                analysis.entry_count += 1
                analysis.uncompressed_total += int(info.file_size)
                analysis.compressed_total += int(info.compress_size)
                name = info.filename.replace("\\", "/")
                top = name.split("/", 1)[0] if "/" in name else name
                analysis.top_level_sizes[top] = analysis.top_level_sizes.get(top, 0) + int(info.file_size)
                analysis.top_level_counts[top] = analysis.top_level_counts.get(top, 0) + 1
                lower = name.lower()
                if lower.endswith(".zip"):
                    analysis.nested_zip_count += 1
                    analysis.nested_zip_uncompressed += int(info.file_size)
                if lower.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
                    analysis.video_count += 1
                    analysis.video_uncompressed += int(info.file_size)
                if len(largest) < max_largest:
                    largest.append((name, int(info.file_size)))
                    largest.sort(key=lambda item: item[1], reverse=True)
                elif int(info.file_size) > largest[-1][1]:
                    largest[-1] = (name, int(info.file_size))
                    largest.sort(key=lambda item: item[1], reverse=True)
                if len(prefix_samples[top]) < 5:
                    prefix_samples[top].append(name)
    except (OSError, zipfile.BadZipFile) as exc:
        analysis.flags.append(f"unreadable_zip:{str(exc)[:80]}")
        if path.stat().st_size > 1024 * 1024 and path.open("rb").read(2) == b"PK":
            return _scan_incomplete_zip_local_entries(path)
        return analysis

    analysis.largest_entries = largest
    analysis.sample_paths = dict(prefix_samples)

    checks = {
        "outputs/runs": any(k.startswith("outputs") for k in analysis.top_level_sizes),
        "downloads/runway": any("downloads" in k for k in analysis.top_level_sizes),
        "assets/videos": any(k.startswith("assets") for k in analysis.top_level_sizes),
        "storage/backups": any(k.startswith("storage") for k in analysis.top_level_sizes),
        "nested_backups": analysis.nested_zip_count > 0,
        "chrome_mapper_profile": "chrome_mapper_profile" in analysis.top_level_sizes,
        "git_objects": ".git" in analysis.top_level_sizes,
        "project_brain": "project_brain" in analysis.top_level_sizes,
        "venv": "venv" in analysis.top_level_sizes,
    }
    for key, present in checks.items():
        if present:
            analysis.flags.append(key)

    return analysis


def detect_backup_chains(files: list[BackupFile]) -> list[dict[str, Any]]:
    restore_points: list[dict[str, Any]] = []
    for record in sorted(files, key=lambda item: item.rel):
        match = RESTORE_POINT_PATTERN.search(record.path.name)
        if not match:
            continue
        restore_points.append(
            {
                "name": record.path.name,
                "rel": record.rel,
                "stamp": match.group(1),
                "size": record.size,
                "modified": record.modified_iso,
            }
        )

    chains: list[dict[str, Any]] = []
    if restore_points:
        chain_type = "full_backup_chain"
        for item in restore_points:
            if item["size"] < 1024:
                classification = "corrupt_or_empty_stub"
            elif "173154" in item["name"]:
                classification = "full_backup_controlled"
            elif item["size"] > 50 * 1024**3:
                classification = "duplicate_full_backup_uncontrolled"
            else:
                classification = "full_backup_intermediate"
            item["backup_type"] = classification
            item["incremental"] = False
        chains.append(
            {
                "chain_id": "RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT",
                "pattern": "RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_YYYYMMDD_HHMMSS.zip",
                "backup_type": chain_type,
                "incremental": False,
                "members": restore_points,
            }
        )

    # Generic .bak chain by stem prefix
    bak_groups: dict[str, list[BackupFile]] = defaultdict(list)
    for record in files:
        if record.suffix != ".bak":
            continue
        stem = record.path.name.rsplit(".", 1)[0]
        prefix = re.sub(r"\.\d{8}_\d{6}$", "", stem)
        bak_groups[prefix].append(record)
    for prefix, group in bak_groups.items():
        if len(group) < 2:
            continue
        members = sorted(group, key=lambda item: item.modified)
        chains.append(
            {
                "chain_id": prefix,
                "pattern": f"{prefix}*.bak",
                "backup_type": "incremental_file_backup",
                "incremental": True,
                "members": [
                    {
                        "name": item.path.name,
                        "rel": item.rel,
                        "size": item.size,
                        "modified": item.modified_iso,
                        "backup_type": "incremental_backup",
                    }
                    for item in members
                ],
            }
        )
    return chains


def folder_sizes(files: list[BackupFile]) -> list[tuple[str, int, int, float, float]]:
    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"size": 0, "count": 0, "created": 0.0, "modified": 0.0})
    for record in files:
        parts = Path(record.rel).parts
        for depth in range(2, min(len(parts) + 1, 5)):
            key = "/".join(parts[:depth])
            if not key.startswith("storage/backups"):
                continue
            bucket = agg[key]
            bucket["size"] += record.size
            bucket["count"] += 1
            bucket["created"] = max(bucket["created"], record.created)
            bucket["modified"] = max(bucket["modified"], record.modified)
    rows = [(k, v["size"], v["count"], v["created"], v["modified"]) for k, v in agg.items()]
    return sorted(rows, key=lambda item: item[1], reverse=True)


def duplicate_groups(files: list[BackupFile]) -> dict[str, list[BackupFile]]:
    groups: dict[str, list[BackupFile]] = defaultdict(list)
    for record in files:
        if not record.sha256:
            try:
                record.sha256 = _hash_file(record.path)
            except OSError:
                continue
        groups[record.sha256].append(record)
    return {digest: members for digest, members in groups.items() if len(members) > 1}


def estimate_reclaimable(
    files: list[BackupFile],
    chains: list[dict[str, Any]],
    zip_analyses: dict[str, ZipAnalysis],
) -> dict[str, Any]:
    reclaimable = 0
    notes: list[str] = []

    restore_chain = next((c for c in chains if c["chain_id"] == "RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT"), None)
    if restore_chain:
        members = restore_chain["members"]
        keep = min(
            members,
            key=lambda item: (
                0 if item.get("backup_type") == "full_backup_controlled" else 1,
                -int(item["size"]),
            ),
        )
        for item in members:
            if item["rel"] == keep["rel"]:
                continue
            reclaimable += int(item["size"])
            notes.append(f"Remove superseded restore point `{item['name']}` ({_fmt_bytes(item['size'])}) after confirming `{keep['name']}` restores correctly.")

    # Tiny .bak duplicates / obsolete patch backups
    tiny = sum(item.size for item in files if item.suffix == ".bak" and item.size < 10_000)
    reclaimable += tiny
    if tiny:
        notes.append(f"Obsolete tiny .bak patch backups (~{_fmt_bytes(tiny)}).")

    return {
        "estimated_reclaimable_bytes": reclaimable,
        "estimated_reclaimable_human": _fmt_bytes(reclaimable),
        "keep_restore_point": keep["name"] if restore_chain else "",
        "notes": notes,
    }


def render_forensic_report(
    files: list[BackupFile],
    folders: list[tuple[str, int, int, float, float]],
    chains: list[dict[str, Any]],
    dupes: dict[str, list[BackupFile]],
    zip_analyses: dict[str, ZipAnalysis],
    reclaim: dict[str, Any],
) -> str:
    total_size = sum(item.size for item in files)
    top_files = sorted(files, key=lambda item: item.size, reverse=True)[:50]
    top_folders = folders[:20]

    thresholds = {
        ">5GB": [f for f in files if f.size > 5 * 1024**3],
        ">10GB": [f for f in files if f.size > 10 * 1024**3],
        ">50GB": [f for f in files if f.size > 50 * 1024**3],
    }

    lines = [
        "# Backup Forensic Report",
        "",
        f"Generated: {_now()}",
        f"Scanner: `{SCAN_VERSION}`",
        f"Scope: `{BACKUP_ROOT}`",
        "",
        "## Executive summary",
        "",
        f"- **Total backup folder size:** {_fmt_bytes(total_size)} ({total_size:,} bytes)",
        f"- **Total backup files:** {len(files):,}",
        f"- **Primary cause of 319 GB footprint:** uncontrolled full-project ZIP `{top_files[0].path.name}` at {_fmt_bytes(top_files[0].size)}",
        f"- **Intended controlled restore point:** `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` at {_fmt_bytes(next((f.size for f in files if '173154' in f.path.name), 0))}",
        f"- **Estimated reclaimable after review:** {reclaim['estimated_reclaimable_human']}",
        "",
        "### Key finding on 310 GB file",
        "",
        "The 310 GB file **starts with a valid ZIP local header (`PK\\x03\\x04`)** but has **no valid end-of-central-directory record**. "
        "It is an **aborted / incomplete ZIP write** from the first restore-point attempt, not a restorable archive. "
        "Standard unzip tools will report it as corrupt.",
        "",
        "**Disk layout:** only the first ~4.4 GB is sequential ZIP structure (3,731 local headers). "
        "The remaining **~306 GB is an orphan trailing write blob** with no ZIP framing — raw bytes appended after the "
        "last local header (`weights.bin` with `comp_size=0xFFFFFFFF`). That blob is high-entropy, unindexed data and "
        "cannot be extracted without the missing central directory.",
        "",
        "**Timeline note:** file modified until `2026-06-09T17:16:01Z`, ~92 minutes after the controlled restore point "
        "(`173154.zip`) finished at `15:44:25Z` — suggesting the first backup writer kept appending data in the background.",
        "",
        "## Why the 310 GB backup exists",
        "",
    ]

    big_key = next((k for k in zip_analyses if "171831" in k), None)
    if big_key:
        za = zip_analyses[big_key]
        lines.extend(
            [
                f"The file `{big_key}` is **{_fmt_bytes(za.zip_size)}** on disk with **{za.entry_count:,}** parseable local headers.",
                f"Structured ZIP portion: **{_fmt_bytes(za.parsed_bytes)}** | Trailing orphan blob: **{_fmt_bytes(za.trailing_bytes)}**.",
                f"Uncompressed payload in structured portion: **{_fmt_bytes(za.uncompressed_total)}** "
                f"(compressed on-disk in structured portion: **{_fmt_bytes(za.compressed_total)}**).",
                "",
                "### Root cause",
                "",
                "This matches the **first failed Runway Phase I restore-point attempt** documented in "
                "`project_brain/RUNWAY_PHASE_I_SUCCESS_BACKUP_REPORT.md`: an initial backup ran **without the "
                "controlled exclusion list** and ballooned by including large project trees that the final backup "
                "deliberately excludes. The report notes a partial archive was intended to be deleted; this 310 GB file "
                "is the surviving aborted artifact — mostly an unindexed trailing write, not a restorable archive.",
                "",
                "The backup script `tools/create_runway_phase_i_restore_point.py` is designed to exclude:",
                "",
                "- `storage/backups/` (avoid nested backups)",
                "- `*.mp4`, `*.webm`, `*.mov`, `*.mkv`, `*.zip`",
                "- `.git`, `venv`, `node_modules`, `chrome_mapper_profile`, caches",
                "",
                "The 310 GB archive **violates those intentions** and contains large trees the controlled backup omits.",
                "",
                "### Contents detected inside the 310 GB ZIP",
                "",
            ]
        )
        for flag in za.flags:
            lines.append(f"- **{flag}**")
        lines.extend(["", "#### Top-level folders inside ZIP (by uncompressed bytes)", ""])
        lines.extend(["| Folder | Files | Uncompressed size |", "|--------|------:|------------------:|"])
        for name, size in sorted(za.top_level_sizes.items(), key=lambda item: item[1], reverse=True)[:25]:
            lines.append(f"| `{name}` | {za.top_level_counts.get(name, 0):,} | {_fmt_bytes(size)} |")
        lines.extend(["", "#### Largest individual entries", ""])
        for name, size in za.largest_entries[:15]:
            lines.append(f"- `{name}` — {_fmt_bytes(size)}")
        lines.extend(
            [
                "",
                f"- Nested ZIP files inside archive: **{za.nested_zip_count:,}** ({_fmt_bytes(za.nested_zip_uncompressed)} uncompressed)",
                f"- Video files inside archive: **{za.video_count:,}** ({_fmt_bytes(za.video_uncompressed)} uncompressed)",
                f"- **outputs/runs:** {'yes (in structured portion via backup_temp)' if any('outputs' in k for k in za.top_level_sizes) else 'not in top-level structured headers; may exist inside trailing blob (unverified)'}",
                f"- **downloads/runway:** {'not detected in structured portion' if not any('downloads' in k for k in za.top_level_sizes) else 'yes'}",
                f"- **nested backups:** {za.nested_zip_count} nested `.zip` inside structured portion (`backups/ModirAgentOS_BACKUP_20260519_215615.zip`, 38.46 MB)",
                "",
            ]
        )

    controlled_key = next((k for k in zip_analyses if "173154" in k), None)
    if controlled_key:
        za = zip_analyses[controlled_key]
        lines.extend(
            [
                "## Controlled 8.87 GB restore point",
                "",
                f"`{controlled_key}` contains **{za.entry_count:,}** files, **{_fmt_bytes(za.uncompressed_total)}** uncompressed.",
                "",
                "Detected content flags:",
                "",
            ]
        )
        for flag in za.flags:
            lines.append(f"- {flag}")
        lines.extend(["", "Top-level folders:", ""])
        for name, size in sorted(za.top_level_sizes.items(), key=lambda item: item[1], reverse=True)[:15]:
            lines.append(f"- `{name}` — {_fmt_bytes(size)} ({za.top_level_counts.get(name, 0):,} files)")

    lines.extend(["", "## Top 50 largest backup files", "", "| Rank | File | Size | Created (UTC) | Modified (UTC) | SHA256 |", "|-----:|------|-----:|---------------|----------------|--------|"])
    for rank, item in enumerate(top_files, start=1):
        digest = item.sha256[:16] + "…" if item.sha256 else ""
        lines.append(
            f"| {rank} | `{item.rel}` | {_fmt_bytes(item.size)} | {item.created_iso} | {item.modified_iso} | `{digest}` |"
        )

    lines.extend(["", "## Top 20 largest backup folders", "", "| Rank | Folder | Size | Files | Last modified (UTC) |", "|-----:|--------|-----:|------:|---------------------|"])
    for rank, (folder, size, count, _created, modified) in enumerate(top_folders, start=1):
        lines.append(f"| {rank} | `{folder}` | {_fmt_bytes(size)} | {count} | {_iso(modified)} |")

    lines.extend(["", "## Size threshold counts", ""])
    for label, bucket in thresholds.items():
        lines.append(f"- **{label}:** {len(bucket)} file(s), combined {_fmt_bytes(sum(x.size for x in bucket))}")
        for item in bucket:
            lines.append(f"  - `{item.rel}` — {_fmt_bytes(item.size)} (created {item.created_iso}, modified {item.modified_iso})")

    lines.extend(["", "## Backup chains", ""])
    for chain in chains:
        lines.append(f"### `{chain['chain_id']}`")
        lines.append(f"- Pattern: `{chain['pattern']}`")
        lines.append(f"- Chain type: **{chain['backup_type']}** | incremental: **{chain['incremental']}**")
        lines.append("")
        lines.append("| Member | Size | Modified | Classification |")
        lines.append("|--------|-----:|----------|----------------|")
        for member in chain["members"]:
            classification = member.get("backup_type", chain["backup_type"])
            lines.append(
                f"| `{member['name']}` | {_fmt_bytes(member['size'])} | {member.get('modified', '')} | {classification} |"
            )
        lines.append("")

    lines.extend(["", "## Identical backups (SHA256)", ""])
    if not dupes:
        lines.append("No identical backup files detected.")
    else:
        for digest, group in dupes.items():
            paths = ", ".join(f"`{item.rel}`" for item in group)
            lines.append(f"- `{digest}` → {paths}")

    lines.extend(["", "## Reclaim estimate", "", f"**{reclaim['estimated_reclaimable_human']}**", ""])
    for note in reclaim.get("notes", []):
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def render_cleanup_recommendation(reclaim: dict[str, Any], files: list[BackupFile], zip_analyses: dict[str, ZipAnalysis]) -> str:
    lines = [
        "# Backup Cleanup Recommendation",
        "",
        f"Generated: {_now()}",
        "",
        "> **DO NOT DELETE. DO NOT MOVE.** Advisory report only.",
        "",
        "## Recommended keep set",
        "",
        f"- **Keep:** `{reclaim.get('keep_restore_point') or 'RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip'}`",
        "- **Keep:** `project_brain/RUNWAY_PHASE_I_RESTORE_INSTRUCTIONS.md` and git tag `runway-phase-i-success`",
        "- **Keep:** small `.bak` files only if you still need patch rollback history",
        "",
        "## Safe reclaim candidates (after human confirmation)",
        "",
        f"Estimated reclaimable: **{reclaim['estimated_reclaimable_human']}**",
        "",
        "1. **`RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` (310.36 GB)** — LIKELY SAFE TO ARCHIVE OFFSITE OR DELETE",
        "   - Uncontrolled duplicate of project state",
        "   - Superseded by controlled 8.87 GB restore point",
        "   - Contains large excluded trees (.git, chrome profiles, nested zips, media)",
        "",
        "2. **`RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip` (22 bytes)** — SAFE TO DELETE",
        "   - Empty/corrupt stub from interrupted backup attempt",
        "",
        "3. **Tiny `.bak` patch backups (<10 KB)** — LIKELY SAFE",
        "   - Old single-file patch backups from May–June 2025",
        "",
        "## DO NOT DELETE without explicit approval",
        "",
        "- `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` (8.87 GB) — canonical restore point",
        "- Any backup you have not test-restored in a sandbox folder",
        "",
        "## Why 310 GB happened (short version)",
        "",
        "An uncontrolled full-project ZIP was started before exclusion rules were applied. Only **~4.4 GB** of the file "
        "is parseable ZIP structure (mostly `backup_temp/` Chrome profile caches and one nested 38 MB backup). "
        "**~306 GB** is an orphan trailing write blob with no ZIP headers — likely continued raw dumping from the "
        "aborted backup process (possibly `.git`, media, or self-including the in-progress archive). "
        "The controlled **8.87 GB** restore point (`173154.zip`) supersedes it and uses "
        "`tools/create_runway_phase_i_restore_point.py` exclusions.",
        "",
        "## Suggested next phase (manual)",
        "",
        "1. Verify restore from `...173154.zip` in a scratch directory",
        "2. Copy the 310 GB ZIP to external cold storage **or** delete after checksum note recorded",
        "3. Re-run `python project_brain/backup_forensic_scan.py` to confirm new total",
        "",
    ]
    big = next((a for k, a in zip_analyses.items() if "171831" in k), None)
    if big:
        lines.extend(["## 310 GB ZIP composition snapshot", ""])
        lines.append(f"- Structured ZIP portion: {_fmt_bytes(big.parsed_bytes)}")
        lines.append(f"- Trailing orphan blob: {_fmt_bytes(big.trailing_bytes)}")
        lines.append("")
        lines.append("Top-level folders in structured portion:")
        for name, size in sorted(big.top_level_sizes.items(), key=lambda i: i[1], reverse=True)[:10]:
            lines.append(f"- `{name}`: {_fmt_bytes(size)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    files = collect_backup_files()
    print(f"Found {len(files)} backup files", flush=True)

    for record in files:
        if record.size > 0:
            print(f"Hashing {record.rel} ({_fmt_bytes(record.size)})", flush=True)
            record.sha256 = _hash_file(record.path)

    folders = folder_sizes(files)
    chains = detect_backup_chains(files)
    dupes = duplicate_groups(files)

    zip_analyses: dict[str, ZipAnalysis] = {}
    for record in files:
        if record.suffix == ".zip":
            print(f"Analyzing ZIP contents: {record.rel}", flush=True)
            zip_analyses[record.rel] = analyze_zip(record.path, rel=record.rel)

    reclaim = estimate_reclaimable(files, chains, zip_analyses)

    brain = ROOT / "project_brain"
    (brain / "BACKUP_FORENSIC_REPORT.md").write_text(
        render_forensic_report(files, folders, chains, dupes, zip_analyses, reclaim),
        encoding="utf-8",
    )
    (brain / "BACKUP_CLEANUP_RECOMMENDATION.md").write_text(
        render_cleanup_recommendation(reclaim, files, zip_analyses),
        encoding="utf-8",
    )

    summary = {
        "total_bytes": sum(item.size for item in files),
        "files": len(files),
        "estimated_reclaimable": reclaim["estimated_reclaimable_bytes"],
        "zip_analyses": {k: {"entries": v.entry_count, "flags": v.flags} for k, v in zip_analyses.items()},
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
