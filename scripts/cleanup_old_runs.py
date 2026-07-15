"""Delete old pwmap agent runs, keeping the newest N and preserving thumbnails."""

from __future__ import annotations

import argparse
import glob
import shutil
from pathlib import Path


def _folder_size_bytes(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _preserve_thumbnails(run_dir: Path, dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    preserved: list[str] = []
    patterns = ("**/*thumb*.jpg", "**/*thumbnail*.jpg", "**/*thumb*.png", "**/*thumbnail*.png")
    seen: set[str] = set()
    for pattern in patterns:
        for thumb in run_dir.glob(pattern):
            key = str(thumb.resolve())
            if key in seen or not thumb.is_file():
                continue
            seen.add(key)
            dest = dest_dir / f"{run_dir.name}_{thumb.name}"
            try:
                shutil.copy2(thumb, dest)
                preserved.append(str(dest))
            except OSError as exc:
                print(f"WARN: failed to preserve {thumb}: {exc}")
    return preserved


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup old pwmap_agent_runs folders")
    parser.add_argument("--keep", type=int, default=5, help="Number of newest runs to keep (default: 5)")
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Project root containing outputs/pwmap_agent_runs",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    runs_root = root / "outputs" / "pwmap_agent_runs"
    keep = max(0, int(args.keep))
    runs = sorted(glob.glob(str(runs_root / "pwmap_*")))
    if keep > 0:
        to_delete = runs[:-keep]
        kept = runs[-keep:]
    else:
        to_delete = runs
        kept = []

    print(f"Found {len(runs)} runs. Keeping {len(kept)}. Deleting {len(to_delete)}.")
    total_freed = 0
    for run in to_delete:
        run_path = Path(run)
        size = _folder_size_bytes(run_path)
        preserved = _preserve_thumbnails(run_path, root / "outputs" / "thumbnails")
        shutil.rmtree(run_path, ignore_errors=True)
        total_freed += size
        print(
            f"Deleted {run_path.name} ({size / 1024 / 1024:.1f} MB)"
            + (f" — preserved {len(preserved)} thumbnail(s)" if preserved else "")
        )

    print(f"Total freed: {total_freed / 1024 / 1024:.1f} MB")
    print(f"Remaining runs: {len(kept)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
