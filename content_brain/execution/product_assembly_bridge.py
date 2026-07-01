"""Product Studio assembly bridge — stitch pwmap clips into publish-ready output."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.pwmap_runway_agent_adapter import validate_mp4_path
from content_brain.execution.runway_live_post_processor import collect_valid_download_paths
from utils.ffmpeg_stitcher import FFmpegStitcher

PRODUCT_ASSEMBLY_BRIDGE_VERSION = "product_assembly_bridge_v1"
FINAL_PUBLISH_READY_NAME = "FINAL_PUBLISH_READY.mp4"
ASSEMBLY_MANIFEST_NAME = "assembly_manifest.json"
PUBLISH_METADATA_NAME = "publish_metadata.json"

ASSEMBLY_STATUS_COMPLETED = "completed"
ASSEMBLY_STATUS_FAILED = "assembly_failed"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe_duration_seconds(video_path: Path) -> float | None:
    if not video_path.is_file():
        return None
    try:
        import shutil
        import subprocess

        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return None
        return float(completed.stdout.strip())
    except (OSError, ValueError):
        return None


def _clip_path(run_dir: Path, index: int) -> Path:
    return run_dir / f"clip_{index}.mp4"


def discover_product_studio_clips(
    run_dir: Path,
    *,
    expected_clip_count: int,
) -> dict[str, Any]:
    """Validate sequential clip_N.mp4 inputs under a pwmap Product Studio run folder."""
    run_dir = run_dir.resolve()
    expected = max(1, min(6, int(expected_clip_count)))
    available: list[dict[str, Any]] = []
    missing_indices: list[int] = []
    seen_paths: set[str] = set()

    for index in range(1, expected + 1):
        path = _clip_path(run_dir, index)
        verify = validate_mp4_path(path)
        resolved = str(path.resolve()).replace("\\", "/")
        if verify["valid"]:
            if resolved in seen_paths:
                return {
                    "ok": False,
                    "expected_clip_count": expected,
                    "available_clips": available,
                    "missing_clip_indices": missing_indices,
                    "input_clips": [],
                    "recovery_possible": len(available) > 0,
                    "error": f"duplicate_clip_path:{index}",
                }
            seen_paths.add(resolved)
            available.append(
                {
                    "clip_index": index,
                    "path": resolved,
                    "size_bytes": verify["size_bytes"],
                }
            )
        else:
            missing_indices.append(index)

    if expected == 1 and not available:
        fallback = run_dir / "video.mp4"
        verify = validate_mp4_path(fallback)
        if verify["valid"]:
            resolved = str(fallback.resolve()).replace("\\", "/")
            available.append(
                {
                    "clip_index": 1,
                    "path": resolved,
                    "size_bytes": verify["size_bytes"],
                    "source": "video.mp4_fallback",
                }
            )
            missing_indices = []

    input_clips = [item["path"] for item in sorted(available, key=lambda row: int(row["clip_index"]))]
    ok = len(available) == expected and not missing_indices
    recovery_possible = len(available) > 0 and bool(missing_indices)

    return {
        "ok": ok,
        "expected_clip_count": expected,
        "available_clips": available,
        "missing_clip_indices": missing_indices,
        "input_clips": input_clips,
        "recovery_possible": recovery_possible,
        "error": "" if ok else f"missing_clips:{missing_indices}",
    }


def _write_failure_artifacts(
    *,
    publish_dir: Path,
    run_id: str,
    topic: str,
    discovery: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    publish_dir.mkdir(parents=True, exist_ok=True)
    available_indices = [int(item["clip_index"]) for item in discovery.get("available_clips") or []]
    assembly_manifest = {
        "version": PRODUCT_ASSEMBLY_BRIDGE_VERSION,
        "run_id": run_id,
        "topic": topic,
        "clip_count": int(discovery.get("expected_clip_count") or 0),
        "source_clip_count": len(available_indices),
        "input_clips": list(discovery.get("input_clips") or []),
        "assembly_status": ASSEMBLY_STATUS_FAILED,
        "output_video": "",
        "missing_clip_indices": list(discovery.get("missing_clip_indices") or []),
        "available_clip_indices": available_indices,
        "recovery_possible": bool(discovery.get("recovery_possible")),
        "error": error,
        "created_at": _now_iso(),
    }
    publish_metadata = {
        "version": PRODUCT_ASSEMBLY_BRIDGE_VERSION,
        "run_id": run_id,
        "topic": topic,
        "clip_count": assembly_manifest["clip_count"],
        "source_clip_count": assembly_manifest["source_clip_count"],
        "publish_package_ready": False,
        "assembly_status": ASSEMBLY_STATUS_FAILED,
        "final_publish_video": "",
        "publish_folder": str(publish_dir.resolve()).replace("\\", "/"),
        "missing_clip_index": (assembly_manifest["missing_clip_indices"] or [None])[0],
        "available_clips": available_indices,
        "recovery_possible": bool(discovery.get("recovery_possible")),
        "downstream_ready": [],
        "error": error,
        "created_at": _now_iso(),
    }
    (publish_dir / ASSEMBLY_MANIFEST_NAME).write_text(
        json.dumps(assembly_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (publish_dir / PUBLISH_METADATA_NAME).write_text(
        json.dumps(publish_metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "ok": False,
        "assembly_status": ASSEMBLY_STATUS_FAILED,
        "publish_package_ready": False,
        "publish_package_path": str(publish_dir.resolve()).replace("\\", "/"),
        "final_publish_video_path": "",
        "source_clip_count": assembly_manifest["source_clip_count"],
        "clip_count": assembly_manifest["clip_count"],
        "missing_clip_indices": assembly_manifest["missing_clip_indices"],
        "missing_clip_index": publish_metadata["missing_clip_index"],
        "available_clip_indices": available_indices,
        "recovery_possible": bool(discovery.get("recovery_possible")),
        "assembly_manifest": assembly_manifest,
        "publish_metadata": publish_metadata,
        "error": error,
    }


def run_product_assembly_bridge(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    run_id: str,
    topic: str,
    expected_clip_count: int,
    preflight: dict[str, Any] | None = None,
    invoke_youtube_metadata: bool = True,
) -> dict[str, Any]:
    """Bridge pwmap clip artifacts into publish/FINAL_PUBLISH_READY.mp4."""
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve()
    publish_dir = run_path / "publish"
    preflight = dict(preflight or {})

    discovery = discover_product_studio_clips(run_path, expected_clip_count=expected_clip_count)
    if not discovery["ok"]:
        return _write_failure_artifacts(
            publish_dir=publish_dir,
            run_id=run_id,
            topic=topic,
            discovery=discovery,
            error=str(discovery.get("error") or "assembly_input_invalid"),
        )

    input_clips = list(discovery["input_clips"])
    valid_paths, missing = collect_valid_download_paths(input_clips)
    if missing or len(valid_paths) != len(input_clips):
        discovery["ok"] = False
        discovery["missing_clip_indices"] = discovery.get("missing_clip_indices") or []
        discovery["recovery_possible"] = len(valid_paths) > 0
        return _write_failure_artifacts(
            publish_dir=publish_dir,
            run_id=run_id,
            topic=topic,
            discovery=discovery,
            error="invalid_or_empty_clip_files",
        )

    publish_dir.mkdir(parents=True, exist_ok=True)
    output_video = publish_dir / FINAL_PUBLISH_READY_NAME

    try:
        if len(valid_paths) == 1:
            src = Path(valid_paths[0])
            if src.resolve() != output_video.resolve():
                shutil.copy2(src, output_video)
        else:
            FFmpegStitcher().stitch_clips(valid_paths, str(output_video))
    except (OSError, RuntimeError, ValueError) as exc:
        discovery["ok"] = False
        discovery["recovery_possible"] = True
        return _write_failure_artifacts(
            publish_dir=publish_dir,
            run_id=run_id,
            topic=topic,
            discovery=discovery,
            error=str(exc),
        )

    if not output_video.is_file() or output_video.stat().st_size <= 0:
        discovery["ok"] = False
        discovery["recovery_possible"] = True
        return _write_failure_artifacts(
            publish_dir=publish_dir,
            run_id=run_id,
            topic=topic,
            discovery=discovery,
            error="final_publish_ready_missing_or_empty",
        )

    final_path = str(output_video.resolve()).replace("\\", "/")
    duration_seconds = _probe_duration_seconds(output_video)

    assembly_manifest = {
        "version": PRODUCT_ASSEMBLY_BRIDGE_VERSION,
        "run_id": run_id,
        "topic": topic,
        "clip_count": int(discovery["expected_clip_count"]),
        "source_clip_count": len(valid_paths),
        "input_clips": valid_paths,
        "assembly_status": ASSEMBLY_STATUS_COMPLETED,
        "output_video": final_path,
        "missing_clip_indices": [],
        "available_clip_indices": [int(item["clip_index"]) for item in discovery["available_clips"]],
        "recovery_possible": False,
        "error": "",
        "duration_seconds": duration_seconds,
        "created_at": _now_iso(),
    }
    publish_metadata = {
        "version": PRODUCT_ASSEMBLY_BRIDGE_VERSION,
        "run_id": run_id,
        "topic": topic,
        "clip_count": assembly_manifest["clip_count"],
        "source_clip_count": assembly_manifest["source_clip_count"],
        "publish_package_ready": True,
        "assembly_status": ASSEMBLY_STATUS_COMPLETED,
        "final_publish_video": final_path,
        "publish_folder": str(publish_dir.resolve()).replace("\\", "/"),
        "missing_clip_index": None,
        "available_clips": assembly_manifest["available_clip_indices"],
        "recovery_possible": False,
        "downstream_ready": [
            "subtitle_runtime",
            "branding_runtime",
            "youtube_metadata",
            "youtube_upload",
            "tiktok_upload",
            "instagram_upload",
        ],
        "duration_seconds": duration_seconds,
        "created_at": _now_iso(),
    }
    (publish_dir / ASSEMBLY_MANIFEST_NAME).write_text(
        json.dumps(assembly_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (publish_dir / PUBLISH_METADATA_NAME).write_text(
        json.dumps(publish_metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    result: dict[str, Any] = {
        "ok": True,
        "assembly_status": ASSEMBLY_STATUS_COMPLETED,
        "assembly_complete": True,
        "publish_package_ready": True,
        "publish_package_path": str(publish_dir.resolve()).replace("\\", "/"),
        "final_publish_video_path": final_path,
        "source_clip_count": len(valid_paths),
        "clip_count": int(discovery["expected_clip_count"]),
        "missing_clip_indices": [],
        "missing_clip_index": None,
        "available_clip_indices": assembly_manifest["available_clip_indices"],
        "recovery_possible": False,
        "assembly_manifest": assembly_manifest,
        "publish_metadata": publish_metadata,
        "duration_seconds": duration_seconds,
        "error": "",
    }

    if invoke_youtube_metadata:
        from content_brain.publish.youtube_metadata_generator import ensure_product_studio_publish_metadata

        publish_info = ensure_product_studio_publish_metadata(
            project_root=root,
            run_dir=run_path,
            topic=topic,
            video_path=final_path,
            preflight=preflight,
            duration_seconds=duration_seconds,
            clip_count=int(discovery["expected_clip_count"]),
        )
        result["youtube_metadata"] = publish_info.get("youtube_metadata")
        result["youtube_metadata_path"] = publish_info.get("youtube_metadata_path")

    return result


def load_product_assembly_state(run_dir: str | Path) -> dict[str, Any]:
    """Load assembly/publish state from a Product Studio run folder."""
    run_path = Path(run_dir).resolve()
    publish_dir = run_path / "publish"
    assembly_manifest = {}
    publish_metadata = {}
    assembly_path = publish_dir / ASSEMBLY_MANIFEST_NAME
    publish_meta_path = publish_dir / PUBLISH_METADATA_NAME
    if assembly_path.is_file():
        try:
            assembly_manifest = json.loads(assembly_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            assembly_manifest = {}
    if publish_meta_path.is_file():
        try:
            publish_metadata = json.loads(publish_meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            publish_metadata = {}

    assembly_status = str(
        publish_metadata.get("assembly_status")
        or assembly_manifest.get("assembly_status")
        or ""
    )
    final_video = str(
        publish_metadata.get("final_publish_video")
        or assembly_manifest.get("output_video")
        or ""
    )
    publish_ready = bool(publish_metadata.get("publish_package_ready")) and bool(final_video)
    if publish_ready:
        verify = validate_mp4_path(final_video)
        publish_ready = verify["valid"]

    return {
        "assembly_status": assembly_status,
        "assembly_complete": assembly_status == ASSEMBLY_STATUS_COMPLETED and publish_ready,
        "publish_package_ready": publish_ready,
        "publish_package_path": str(publish_dir.resolve()).replace("\\", "/") if publish_dir.is_dir() else "",
        "final_publish_video_path": final_video if publish_ready else "",
        "source_clip_count": int(
            publish_metadata.get("source_clip_count")
            or assembly_manifest.get("source_clip_count")
            or 0
        ),
        "clip_count": int(publish_metadata.get("clip_count") or assembly_manifest.get("clip_count") or 0),
        "missing_clip_index": publish_metadata.get("missing_clip_index"),
        "missing_clip_indices": list(assembly_manifest.get("missing_clip_indices") or []),
        "available_clip_indices": list(
            publish_metadata.get("available_clips")
            or assembly_manifest.get("available_clip_indices")
            or []
        ),
        "recovery_possible": bool(publish_metadata.get("recovery_possible")),
        "assembly_manifest": assembly_manifest,
        "publish_metadata": publish_metadata,
    }


__all__ = [
    "ASSEMBLY_MANIFEST_NAME",
    "ASSEMBLY_STATUS_COMPLETED",
    "ASSEMBLY_STATUS_FAILED",
    "FINAL_PUBLISH_READY_NAME",
    "PRODUCT_ASSEMBLY_BRIDGE_VERSION",
    "PUBLISH_METADATA_NAME",
    "discover_product_studio_clips",
    "load_product_assembly_state",
    "run_product_assembly_bridge",
]
