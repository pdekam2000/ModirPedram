"""PHASE ASSET-LIBRARY-1 — Asset vault validation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.platform.asset_library import (
    BRANDED_VIDEO_NAME,
    CATEGORY_CHOICES,
    classify_asset_category,
    ensure_asset_library_structure,
    load_asset_index,
    register_published_asset,
    resolve_unique_vault_filename,
    sha256_file,
)
from content_brain.platform.results_run_loader import load_run_results
from content_brain.platform.run_output_versioning import finalize_versioned_run_layout
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_publish_run(tmp: Path, *, run_id: str, topic: str, video_bytes: bytes) -> Path:
    run_dir = tmp / "outputs" / "runs" / f"20260612_120000_{run_id[-8:]}"
    publish_dir = run_dir / "publish"
    publish_dir.mkdir(parents=True, exist_ok=True)
    branded = publish_dir / BRANDED_VIDEO_NAME
    branded.write_bytes(video_bytes)
    _write_json(
        publish_dir / "metadata.json",
        {
            "run_id": run_id,
            "topic": topic,
            "clip_count": 3,
            "branding_enabled": True,
            "music_status": "PASS",
            "narration_provider": "elevenlabs",
        },
    )
    return run_dir


def main() -> None:
    print("=== PHASE ASSET-LIBRARY-1 Asset Vault ===")

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        profile_path = tmp / "project_brain" / "product_settings" / "channel_profile.json"
        _write_json(
            profile_path,
            {
                "channel_topic": "cartoon cat explorer adventures",
                "main_niche": "cartoon",
                "asset_vault_enabled": True,
                "asset_copy_mode": "copy",
            },
        )

        library_root = ensure_asset_library_structure(tmp)
        _pass("asset_folder_created", library_root.is_dir())
        for sub in ("videos", "youtube_shorts", "tiktok", "instagram", "cartoon", "wildlife", "technology", "history", "archive"):
            _pass(f"asset_subdir_{sub}", (library_root / sub).is_dir())

        run_dir = _seed_publish_run(tmp, run_id="run_asset_001", topic="Cartoon Cat Explorer", video_bytes=b"branded-video-v1")
        source_video = run_dir / "publish" / BRANDED_VIDEO_NAME
        source_checksum = sha256_file(source_video)
        publish_manifest = {
            "status": "PUBLISHED_PACKAGE_CREATED",
            "branded_video_path": str(source_video),
            "duration_seconds": 42,
        }
        assembly_manifest = {"clip_count": 3, "status": "ASSEMBLED"}

        first = register_published_asset(
            tmp,
            publish_manifest=publish_manifest,
            run_id="run_asset_001",
            topic="Cartoon Cat Explorer",
            run_dir=run_dir,
            assembly_manifest=assembly_manifest,
        )
        _pass("final_video_copied", first.get("status") == "registered", str(first))
        vault_path = Path(str(first.get("final_video_path") or ""))
        _pass("vault_file_exists", vault_path.is_file() and vault_path.stat().st_size > 0)

        index = load_asset_index(tmp)
        assets = list(index.get("assets") or [])
        _pass("asset_index_updated", len(assets) == 1, str(len(assets)))
        record = assets[0]
        required_fields = (
            "asset_id",
            "run_id",
            "topic",
            "category",
            "creation_time",
            "source_run_folder",
            "final_video_path",
            "duration",
            "clip_count",
            "branding_enabled",
            "narration_enabled",
            "music_enabled",
            "checksum_sha256",
        )
        _pass("asset_metadata_valid", all(record.get(field) not in (None, "") for field in required_fields if field != "duration"))
        _pass("asset_metadata_duration", record.get("duration") == 42 or record.get("duration_seconds") == 42)

        duplicate = register_published_asset(
            tmp,
            publish_manifest=publish_manifest,
            run_id="run_asset_001",
            topic="Cartoon Cat Explorer",
            run_dir=run_dir,
            assembly_manifest=assembly_manifest,
        )
        _pass("duplicate_detection_works", duplicate.get("status") == "duplicate_skipped", str(duplicate))
        index_after_dup = load_asset_index(tmp)
        _pass("duplicate_does_not_add_row", len(list(index_after_dup.get("assets") or [])) == 1)

        target_dir = library_root / "videos" / "cartoon"
        base_name = "20260612_120000_cartoon_cat_explorer"
        first_name = resolve_unique_vault_filename(base_name, target_dir)
        (target_dir / first_name).write_bytes(b"x")
        second_name = resolve_unique_vault_filename(base_name, target_dir)
        _pass("no_overwrite_suffix", second_name.endswith("_v2.mp4"), second_name)
        _pass("original_file_preserved", (target_dir / first_name).is_file())

        recovery = register_published_asset(
            tmp,
            publish_manifest=publish_manifest,
            run_id="run_asset_001_recovery",
            topic="Cartoon Cat Explorer recovery rerun",
            run_dir=run_dir,
            assembly_manifest=assembly_manifest,
        )
        _pass("recovery_does_not_duplicate", recovery.get("status") == "duplicate_skipped", str(recovery))
        _pass("recovery_checksum_match", recovery.get("checksum_sha256") == source_checksum)

        category = classify_asset_category("Wildlife lion documentary", {"main_niche": "nature"})
        _pass("category_assignment_works", category in CATEGORY_CHOICES and category == "wildlife", category)

        results = load_run_results(tmp, run_dir=str(run_dir))
        _pass("results_panel_reads_assets", bool(results.get("asset_library_path")) and isinstance(results.get("latest_assets"), list))
        _pass("results_latest_asset_topic", (results.get("latest_assets") or [{}])[0].get("topic") == "Cartoon Cat Explorer")

        _pass("existing_run_folder_unchanged", source_video.is_file() and source_video.read_bytes() == b"branded-video-v1")
        run_publish_dir = run_dir / "publish"
        _pass("outputs_runs_structure_intact", run_publish_dir.is_dir() and (run_publish_dir / "metadata.json").is_file())

        from content_brain.platform.run_output_versioning import create_versioned_run_layout

        tech_layout = create_versioned_run_layout(tmp, run_id="run_asset_finalize", topic="Technology GPU review")
        tech_layout.publish_dir.mkdir(parents=True, exist_ok=True)
        (tech_layout.publish_dir / BRANDED_VIDEO_NAME).write_bytes(b"tech-final")
        summary = finalize_versioned_run_layout(
            tmp,
            tech_layout,
            assembly_manifest={"status": "ASSEMBLED", "clip_count": 2},
            publish_manifest={
                "status": "PUBLISHED_PACKAGE_CREATED",
                "branded_video_path": str(tech_layout.publish_dir / BRANDED_VIDEO_NAME),
            },
        )
        _pass("finalize_hook_registers_asset", summary.get("asset_registration", {}).get("status") in {"registered", "duplicate_skipped"})

    results_page = (ROOT / "ui/web/src/pages/ResultsPage.tsx").read_text(encoding="utf-8")
    settings_page = (ROOT / "ui/web/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    _pass("results_ui_asset_library", "Asset Library" in results_page and "Open Asset Library" in results_page)
    _pass("settings_ui_asset_vault", "asset_vault_enabled" in settings_page and "Asset copy mode" in settings_page)

    service = ProductStudioService(ROOT)
    library = service.get_asset_library(limit=5)
    _pass("asset_library_api", bool(library.get("library_path")) and isinstance(library.get("assets"), list))

    cartoon_run = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"
    branded_real = cartoon_run / "publish" / BRANDED_VIDEO_NAME
    if branded_real.is_file():
        publish_manifest_path = cartoon_run / "metadata" / "publish_manifest.json"
        publish_manifest = {}
        if publish_manifest_path.is_file():
            try:
                publish_manifest = json.loads(publish_manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                publish_manifest = {}
        if str(publish_manifest.get("status") or "") != "PUBLISHED_PACKAGE_CREATED":
            publish_manifest["status"] = "PUBLISHED_PACKAGE_CREATED"
        publish_manifest["branded_video_path"] = str(branded_real.resolve())
        assembly_manifest_path = cartoon_run / "metadata" / "assembly_manifest.json"
        assembly_manifest = {}
        if assembly_manifest_path.is_file():
            try:
                assembly_manifest = json.loads(assembly_manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                assembly_manifest = {}
        backfill = register_published_asset(
            ROOT,
            publish_manifest=publish_manifest,
            run_id=str(publish_manifest.get("run_id") or "cb_e2e_20260611_225308_dc20bc1f"),
            topic=str(publish_manifest.get("topic") or "Cartoon Cat Explorer"),
            run_dir=cartoon_run,
            assembly_manifest=assembly_manifest,
        )
        _pass("real_run_backfill", backfill.get("status") in {"registered", "duplicate_skipped"}, str(backfill))
        _pass("real_run_source_preserved", branded_real.is_file())

    print("\n=== PHASE ASSET-LIBRARY-1 complete ===")


if __name__ == "__main__":
    main()
