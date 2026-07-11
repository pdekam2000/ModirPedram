"""Archive stale delivery artifacts — move only, never delete."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARCHIVE_ROOT = ROOT / "storage" / "archive" / "delivery_truth_1"

STALE_RUN_IDS = {
    "cb_sv1_20260613_095159_5fdbc1ce",
    "cb_e2e_20260611_225308_dc20bc1f",
}

STALE_RUN_FOLDER_MARKERS = (
    "20260613_095159_f2d7ab07",
    "20260611_235927_308_dc20bc1f",
    "story_visual_1",
    "story_quality_1",
)

STALE_REGISTRY_FILES = (
    ROOT / "project_brain" / "runtime_state" / "final_delivery_registry.json",
    ROOT / "project_brain" / "runtime_state" / "voice_identity_registry.json",
)

STALE_STORY_PACKAGES = (
    "cb_sv1_20260613_095159_5fdbc1ce.json",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _move_path(source: Path, dest_root: Path) -> dict[str, str]:
    if not source.exists():
        return {"source": str(source), "status": "missing"}
    rel = source.relative_to(ROOT) if source.is_relative_to(ROOT) else Path(source.name)
    target = dest_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target = target.with_name(f"{target.stem}_{_stamp()}{target.suffix}")
    shutil.move(str(source), str(target))
    return {"source": str(source), "target": str(target), "status": "archived"}


def archive_stale_delivery_artifacts(project_root: Path | None = None) -> dict[str, object]:
    root = Path(project_root or ROOT).resolve()
    archive_dir = ARCHIVE_ROOT / _stamp()
    archive_dir.mkdir(parents=True, exist_ok=True)
    log: list[dict[str, str]] = []

    runs_root = root / "outputs" / "runs"
    if runs_root.is_dir():
        for folder in runs_root.iterdir():
            if not folder.is_dir():
                continue
            if any(marker in folder.name for marker in STALE_RUN_FOLDER_MARKERS):
                log.append(_move_path(folder, archive_dir))

    packages_dir = root / "project_brain" / "story_packages"
    for name in STALE_STORY_PACKAGES:
        log.append(_move_path(packages_dir / name, archive_dir))

    runtime_state = root / "project_brain" / "runtime_state"
    for rel_name in ("final_delivery_registry.json", "voice_identity_registry.json"):
        source = runtime_state / rel_name
        if source.is_file():
            snapshot = archive_dir / "runtime_state_snapshots" / rel_name
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, snapshot)
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["approved"] = False
            payload["delivery_reality_passed"] = False
            payload["archived_snapshot"] = str(snapshot)
            source.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            log.append({"source": str(source), "status": "reset_unapproved", "snapshot": str(snapshot)})

    report = {
        "archive_dir": str(archive_dir),
        "moved": [item for item in log if item.get("status") == "archived"],
        "reset": [item for item in log if item.get("status") != "archived"],
    }
    (archive_dir / "ARCHIVE_LOG.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = archive_stale_delivery_artifacts()
    print(json.dumps(result, indent=2, ensure_ascii=False))
