"""Versioned run output folders — never overwrite prior generated runs."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNS_ROOT = Path("outputs") / "runs"
RUNS_INDEX = RUNS_ROOT / "index.json"
LATEST_FINAL = Path("outputs") / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
LATEST_PUBLISH = Path("outputs") / "publish" / "runway_phase_i"


@dataclass
class VersionedRunLayout:
    run_id: str
    topic: str
    run_dir: Path
    final_dir: Path
    publish_dir: Path
    audio_dir: Path
    prompts_dir: Path
    metadata_dir: Path
    vision_dir: Path

    @property
    def final_video_path(self) -> Path:
        return self.final_dir / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"

    @property
    def downloads_manifest_path(self) -> Path:
        return self.run_dir / "raw_downloads_manifest.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "topic": self.topic,
            "run_dir": str(self.run_dir),
            "final_dir": str(self.final_dir),
            "publish_dir": str(self.publish_dir),
            "audio_dir": str(self.audio_dir),
            "prompts_dir": str(self.prompts_dir),
            "metadata_dir": str(self.metadata_dir),
            "vision_dir": str(self.vision_dir),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_run_id(run_id: str) -> str:
    text = (run_id or "run").strip().replace(" ", "_")
    if len(text) <= 12:
        return text or "run"
    return text[-12:]


def create_versioned_run_layout(project_root: str | Path, *, run_id: str, topic: str) -> VersionedRunLayout:
    root = Path(project_root).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{stamp}_{_short_run_id(run_id)}"
    run_dir = root / RUNS_ROOT / folder_name
    layout = VersionedRunLayout(
        run_id=str(run_id or ""),
        topic=str(topic or ""),
        run_dir=run_dir,
        final_dir=run_dir / "final",
        publish_dir=run_dir / "publish",
        audio_dir=run_dir / "audio",
        prompts_dir=run_dir / "prompts",
        metadata_dir=run_dir / "metadata",
        vision_dir=run_dir / "vision",
    )
    for path in (
        layout.final_dir,
        layout.publish_dir,
        layout.audio_dir,
        layout.prompts_dir,
        layout.metadata_dir,
        layout.vision_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return layout


def write_raw_downloads_manifest(layout: VersionedRunLayout, downloaded_paths: list[str]) -> None:
    payload = {
        "run_id": layout.run_id,
        "topic": layout.topic,
        "downloaded_file_paths": list(downloaded_paths),
        "created_at": _now(),
    }
    layout.downloads_manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _copy_file(source: Path, target: Path) -> None:
    if not source.is_file() or source.stat().st_size <= 0:
        return
    if source.resolve() == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if source.resolve() == target.resolve():
        return
    if source.is_file():
        _copy_file(source, target)
        return
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target)


def finalize_versioned_run_layout(
    project_root: str | Path,
    layout: VersionedRunLayout,
    *,
    assembly_manifest: dict[str, Any],
    publish_manifest: dict[str, Any],
    visual_continuity_report: dict[str, Any] | None = None,
    runway_report_path: str = "",
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    final_source = Path(str(assembly_manifest.get("output_path") or layout.final_video_path))
    publish_source = Path(str(publish_manifest.get("package_folder") or layout.publish_dir))

    if final_source.is_file():
        _copy_file(final_source, layout.final_video_path)
        _copy_file(final_source, root / LATEST_FINAL)

    if publish_source.is_dir():
        _copy_tree(publish_source, layout.publish_dir)
        latest_publish = root / LATEST_PUBLISH
        if latest_publish.exists():
            shutil.rmtree(latest_publish, ignore_errors=True)
        _copy_tree(layout.publish_dir, latest_publish)

    if visual_continuity_report:
        (layout.metadata_dir / "visual_continuity_report.json").write_text(
            json.dumps(visual_continuity_report, indent=2),
            encoding="utf-8",
        )

    (layout.metadata_dir / "assembly_manifest.json").write_text(json.dumps(assembly_manifest, indent=2), encoding="utf-8")
    (layout.metadata_dir / "publish_manifest.json").write_text(json.dumps(publish_manifest, indent=2), encoding="utf-8")

    summary = {
        "run_id": layout.run_id,
        "topic": layout.topic,
        "run_dir": str(layout.run_dir),
        "final_video_path": str(layout.final_video_path if layout.final_video_path.is_file() else final_source),
        "publish_dir": str(layout.publish_dir if layout.publish_dir.exists() else publish_source),
        "assembly_status": str(assembly_manifest.get("status") or ""),
        "publish_status": str(publish_manifest.get("status") or ""),
        "created_at": _now(),
        "runway_report_path": runway_report_path,
    }
    (layout.metadata_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    index_path = root / RUNS_INDEX
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {"version": "platform_run_index_v1", "runs": []}
    if index_path.is_file():
        try:
            loaded = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                index = loaded
        except (OSError, json.JSONDecodeError):
            pass
    runs = [item for item in list(index.get("runs") or []) if item.get("run_dir") != str(layout.run_dir)]
    runs.insert(0, summary)
    index["runs"] = runs[:100]
    index["updated_at"] = _now()
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    try:
        from content_brain.platform.asset_library import register_published_asset

        asset_result = register_published_asset(
            root,
            publish_manifest=publish_manifest,
            run_id=layout.run_id,
            topic=layout.topic,
            run_dir=layout.run_dir,
            assembly_manifest=assembly_manifest,
        )
        summary["asset_registration"] = asset_result
    except Exception as exc:
        summary["asset_registration"] = {"status": "failed", "error": str(exc)}

    return summary


def list_run_history(project_root: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    index_path = root / RUNS_INDEX
    if not index_path.is_file():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    runs = list(payload.get("runs") or [])
    return runs[: max(1, int(limit))]
