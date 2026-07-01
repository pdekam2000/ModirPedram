"""Re-run audio, branding, and publish on an existing run folder — no Runway/browser."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from content_brain.audio.audio_post_processing import run_audio_post_processing
from content_brain.branding.branding_runtime import FINAL_BRANDED_VIDEO_V3_NAME, run_branding_runtime
from content_brain.execution.runway_live_post_processor import (
    ASSEMBLY_ASSEMBLED,
    run_assembly,
    run_publish_package,
)
from content_brain.platform.asset_library import register_published_asset, sha256_file
from content_brain.platform.run_output_versioning import finalize_versioned_run_layout

RECOVERY_VERSION = "post_processing_recovery_v3"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _layout_from_run_dir(run_dir: Path, *, run_id: str, topic: str) -> Any:
    from content_brain.platform.run_output_versioning import VersionedRunLayout

    return VersionedRunLayout(
        run_id=run_id,
        topic=topic,
        run_dir=run_dir,
        final_dir=run_dir / "final",
        publish_dir=run_dir / "publish",
        audio_dir=run_dir / "audio",
        prompts_dir=run_dir / "prompts",
        metadata_dir=run_dir / "metadata",
        vision_dir=run_dir / "vision",
    )


def recover_post_processing_inplace(
    project_root: str | Path,
    *,
    run_dir: str | Path,
    report: dict[str, Any] | None = None,
    reassemble: bool = False,
    branded_video_name: str = FINAL_BRANDED_VIDEO_V3_NAME,
    register_asset: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run_dir_path = Path(run_dir).resolve()
    run_summary = _read_json(run_dir_path / "metadata" / "run_summary.json")
    assembly_manifest = _read_json(run_dir_path / "metadata" / "assembly_manifest.json")
    raw_downloads = _read_json(run_dir_path / "raw_downloads_manifest.json")

    run_id = str(run_summary.get("run_id") or raw_downloads.get("run_id") or "")
    topic = str(run_summary.get("topic") or raw_downloads.get("topic") or "")
    downloaded_paths = [str(item) for item in (raw_downloads.get("downloaded_file_paths") or []) if item]
    clip_count = int(assembly_manifest.get("clip_count") or len(downloaded_paths) or 3)

    final_video = run_dir_path / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
    if reassemble and downloaded_paths:
        assembly_manifest = run_assembly(
            root,
            input_files=downloaded_paths,
            clip_count=clip_count,
            output_path=final_video,
        )
    elif not assembly_manifest and final_video.is_file():
        assembly_manifest = {
            "version": RECOVERY_VERSION,
            "status": ASSEMBLY_ASSEMBLED,
            "clip_count": clip_count,
            "input_files": downloaded_paths,
            "output_path": str(final_video),
        }

    if str(assembly_manifest.get("status") or "") != ASSEMBLY_ASSEMBLED:
        return {
            "ok": False,
            "error": "assembly_not_ready",
            "assembly_status": assembly_manifest.get("status"),
            "run_dir": str(run_dir_path),
        }

    report_payload = dict(report or {})
    report_payload.setdefault("content_brain_run_id", run_id)
    report_payload.setdefault("content_brain_topic", topic)
    report_payload.setdefault("clip_count", clip_count)
    report_payload.setdefault("simulate", False)
    report_payload.setdefault("ok", True)

    audio_post_result = run_audio_post_processing(
        project_root=root,
        report=report_payload,
        assembly_manifest=assembly_manifest,
        run_dir=run_dir_path,
    )
    branding_post_result = run_branding_runtime(
        project_root=root,
        report=report_payload,
        assembly_manifest=assembly_manifest,
        audio_post_result=audio_post_result,
        output_dir=run_dir_path / "final",
        branded_video_name=branded_video_name,
    )
    publish_manifest = run_publish_package(
        root,
        assembly_manifest=assembly_manifest,
        run_id=run_id,
        topic=topic,
        clip_count=clip_count,
        downloaded_file_paths=downloaded_paths,
        audio_post_result=audio_post_result,
        branding_post_result=branding_post_result,
        package_dir=run_dir_path / "publish",
    )

    branded_source = Path(str(branding_post_result.get("final_branded_video_path") or ""))
    package_branded = run_dir_path / "publish" / branded_video_name
    if branded_source.is_file():
        package_branded.parent.mkdir(parents=True, exist_ok=True)
        if not package_branded.is_file() or sha256_file(branded_source) != sha256_file(package_branded):
            shutil.copy2(branded_source, package_branded)
        publish_manifest["branded_video_path"] = str(package_branded.resolve())
        publish_manifest["branded_video_name"] = branded_video_name

    layout = _layout_from_run_dir(run_dir_path, run_id=run_id, topic=topic)
    summary = finalize_versioned_run_layout(
        root,
        layout,
        assembly_manifest=assembly_manifest,
        publish_manifest=publish_manifest,
    )

    asset_result: dict[str, Any] = {"status": "skipped"}
    if register_asset:
        asset_result = register_published_asset(
            root,
            publish_manifest=publish_manifest,
            run_id=run_id,
            topic=topic,
            run_dir=run_dir_path,
            assembly_manifest=assembly_manifest,
        )

    original_v1 = run_dir_path / "publish" / "FINAL_BRANDED_VIDEO.mp4"
    v2_path = run_dir_path / "publish" / "FINAL_BRANDED_VIDEO_v2.mp4"
    v3_path = run_dir_path / "publish" / branded_video_name

    return {
        "ok": True,
        "version": RECOVERY_VERSION,
        "run_id": run_id,
        "run_dir": str(run_dir_path),
        "assembly_status": assembly_manifest.get("status"),
        "audio_status": audio_post_result.get("status"),
        "music_status": branding_post_result.get("music_status") or audio_post_result.get("music_status"),
        "subtitle_status": branding_post_result.get("subtitle_status") or audio_post_result.get("subtitle_status"),
        "ambience_status": audio_post_result.get("ambience_status"),
        "sfx_status": audio_post_result.get("sfx_status"),
        "subtitle_style_status": audio_post_result.get("subtitle_style_status"),
        "character_voice_status": audio_post_result.get("character_voice_status"),
        "branding_status": branding_post_result.get("status"),
        "publish_status": publish_manifest.get("status"),
        "final_branded_video_path": str(branded_source),
        "final_branded_video_v2_path": str(v2_path) if v2_path.is_file() else "",
        "final_branded_video_v3_path": str(v3_path) if v3_path.is_file() else "",
        "original_branded_preserved": original_v1.is_file(),
        "v2_preserved": v2_path.is_file(),
        "asset_registration": asset_result,
        "run_summary": summary,
    }


__all__ = ["RECOVERY_VERSION", "recover_post_processing_inplace"]
