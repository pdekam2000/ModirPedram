"""Lock final delivery — archive stale artifacts, rebuild approved v4, set registry SSOT."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from content_brain.branding.branding_runtime import FINAL_BRANDED_VIDEO_V4_NAME  # noqa: E402
from content_brain.platform.asset_library import register_published_asset, sha256_file  # noqa: E402
from content_brain.platform.final_delivery_registry import update_final_delivery_registry  # noqa: E402
from content_brain.quality.delivery_reality_auditor import audit_delivery_reality  # noqa: E402
from project_brain.recover_story_audio_delivery import recover_story_audio_delivery  # noqa: E402

LOCK_VERSION = "lock_final_delivery_v1"
DEFAULT_RUN_ID = "cb_e2e_20260611_225308_dc20bc1f"
DEFAULT_RUN_DIR = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"
CANONICAL_RUN_ID = DEFAULT_RUN_ID

SCAN_ROOTS = [
    "outputs",
    "project_brain/runtime_state",
    "assets",
    "archive",
]

LEGACY_BRANDED_NAMES = (
    "FINAL_BRANDED_VIDEO.mp4",
    "FINAL_BRANDED_VIDEO_v2.mp4",
    "FINAL_BRANDED_VIDEO_v3.mp4",
)

STALE_RUNTIME_MANIFESTS = (
    "runway_phase_i_publish_manifest.json",
    "runway_phase_i_audio_manifest.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_move(src: Path, dest: Path) -> str:
    if not src.exists():
        return ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dest.with_name(f"{dest.stem}_{stamp}{dest.suffix}")
    shutil.move(str(src), str(dest))
    return str(dest.resolve())


def _count_tree(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    files = sum(1 for item in path.rglob("*") if item.is_file())
    folders = sum(1 for item in path.rglob("*") if item.is_dir())
    return files, folders


def build_forensic_inventory(project_root: Path) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    for rel in SCAN_ROOTS:
        target = project_root / rel
        files, folders = _count_tree(target)
        classification = "ACTIVE" if target.exists() else "ORPHANED"
        if rel == "outputs" and (project_root / "outputs" / "publish" / "runway_phase_i").exists():
            classification = "DUPLICATE"
        sections[rel] = {
            "classification": classification,
            "path": str(target),
            "file_count": files,
            "folder_count": folders,
            "exists": target.exists(),
        }
    stale_manifests = []
    runtime_dir = project_root / "project_brain" / "runtime_state"
    branding = _read_json(runtime_dir / "runway_phase_i_branding_manifest.json")
    publish = _read_json(runtime_dir / "runway_phase_i_publish_manifest.json")
    if branding.get("branded_video_name") != publish.get("branded_video_name"):
        stale_manifests.append(
            {
                "reason": "branded_video_name_mismatch",
                "branding": branding.get("branded_video_name"),
                "publish": publish.get("branded_video_name"),
            }
        )
    return {
        "version": LOCK_VERSION,
        "generated_at": _now(),
        "sections": sections,
        "duplicate_manifests": stale_manifests,
        "orphaned_outputs": [
            str(project_root / "outputs" / "publish" / "runway_phase_i"),
            str(project_root / "outputs" / "audio"),
        ],
    }


def archive_stale_manifests(project_root: Path, *, run_id: str) -> dict[str, Any]:
    archive_dir = project_root / "project_brain" / "archive" / "stale_manifests"
    archive_dir.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, Any]] = []
    runtime_dir = project_root / "project_brain" / "runtime_state"
    for name in STALE_RUNTIME_MANIFESTS:
        src = runtime_dir / name
        if not src.is_file():
            continue
        payload = _read_json(src)
        branded = str(payload.get("branded_video_path") or payload.get("branded_video_name") or "")
        manifest_run_id = str(payload.get("run_id") or "")
        stale = "v4" not in branded.lower() and FINAL_BRANDED_VIDEO_V4_NAME not in branded
        if manifest_run_id and manifest_run_id != run_id:
            stale = True
        if not stale:
            continue
        dest = archive_dir / f"{src.stem}_{run_id[-8:]}{src.suffix}"
        moved_path = _safe_move(src, dest)
        if moved_path:
            moved.append({"source": str(src), "archived_to": moved_path, "branded_ref": branded})
    run_publish = project_root / "outputs" / "runs" / DEFAULT_RUN_DIR.name / "metadata" / "publish_manifest.json"
    if run_publish.is_file():
        payload = _read_json(run_publish)
        branded_path = str(payload.get("branded_video_path") or "")
        if "v4" not in branded_path.lower() and FINAL_BRANDED_VIDEO_V4_NAME not in branded_path:
            dest = archive_dir / f"run_publish_manifest_{run_id[-8:]}.json"
            moved_path = _safe_move(run_publish, dest)
            if moved_path:
                moved.append({"source": str(run_publish), "archived_to": moved_path})
    report = {"version": LOCK_VERSION, "archived_at": _now(), "run_id": run_id, "moved": moved}
    report_path = archive_dir / "stale_manifest_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def archive_legacy_outputs(project_root: Path, *, run_dir: Path) -> dict[str, Any]:
    legacy_root = project_root / "archive" / "legacy_outputs" / run_dir.name
    legacy_root.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, str]] = []
    for folder in (run_dir / "publish", run_dir / "final"):
        for name in LEGACY_BRANDED_NAMES:
            src = folder / name
            if src.is_file():
                dest = legacy_root / folder.name / name
                archived = _safe_move(src, dest)
                if archived:
                    moved.append({"source": str(src), "archived_to": archived})
    narrated_candidates = [
        run_dir / "final" / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4",
        run_dir / "publish" / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4",
    ]
    for src in narrated_candidates:
        if src.is_file():
            dest = legacy_root / src.parent.name / src.name
            archived = _safe_move(src, dest)
            if archived:
                moved.append({"source": str(src), "archived_to": archived})
    return {"archived_at": _now(), "legacy_root": str(legacy_root), "moved": moved}


def sync_publish_manifest(run_dir: Path, *, video_path: Path, run_id: str) -> None:
    publish_dir = run_dir / "publish"
    metadata_path = publish_dir / "metadata.json"
    manifest_path = run_dir / "metadata" / "publish_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_json(manifest_path) if manifest_path.is_file() else _read_json(metadata_path)
    payload.update(
        {
            "branded_video_path": str(video_path.resolve()),
            "branded_video_name": video_path.name,
            "status": "PUBLISHED_PACKAGE_CREATED",
            "run_id": run_id,
        }
    )
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if metadata_path.parent.exists():
        meta = _read_json(metadata_path)
        meta.update({"branded_video_path": str(video_path.resolve()), "branded_video_name": video_path.name})
        metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    runtime_publish = ROOT / "project_brain" / "runtime_state" / "runway_phase_i_publish_manifest.json"
    runtime_publish.parent.mkdir(parents=True, exist_ok=True)
    runtime_publish.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def lock_final_delivery(*, project_root: Path | None = None, run_dir: Path | None = None, run_id: str = "") -> dict[str, Any]:
    root = Path(project_root or ROOT).resolve()
    run_path = Path(run_dir or DEFAULT_RUN_DIR).resolve()
    run_id = str(run_id or _read_json(run_path / "metadata" / "run_summary.json").get("run_id") or CANONICAL_RUN_ID)

    inventory = build_forensic_inventory(root)
    inventory_md = root / "project_brain" / "PROJECT_FORENSIC_INVENTORY.md"
    inventory_md.write_text(_render_inventory_md(inventory), encoding="utf-8")

    stale_report = archive_stale_manifests(root, run_id=run_id)
    legacy_report = archive_legacy_outputs(root, run_dir=run_path)

    recovery = recover_story_audio_delivery(project_root=root, run_dir=run_path, run_id=run_id)
    publish_v4 = run_path / "publish" / FINAL_BRANDED_VIDEO_V4_NAME
    latest_video = publish_v4 if publish_v4.is_file() else Path(str(recovery.get("after", {}).get("publish_v4_path") or ""))

    asset_result: dict[str, Any] = {"status": "skipped"}
    if latest_video.is_file():
        asset_result = register_published_asset(
            root,
            publish_manifest={
                "status": "PUBLISHED_PACKAGE_CREATED",
                "branded_video_path": str(latest_video.resolve()),
                "branded_video_name": latest_video.name,
            },
            run_id=run_id,
            topic=str(_read_json(run_path / "metadata" / "run_summary.json").get("topic") or "Cute orange cartoon cat explorer"),
            run_dir=run_path,
            assembly_manifest=_read_json(run_path / "metadata" / "assembly_manifest.json"),
        )
        sync_publish_manifest(run_path, video_path=latest_video, run_id=run_id)

    audit = {}
    if latest_video.is_file():
        timeline = _read_json(run_path / "timeline" / "dialogue_timeline.json")
        mix_path = run_path / "audio" / "FINAL_CINEMATIC_AUDIO.mp3"
        cinematic = run_path / "final" / "FINAL_RUNWAY_PHASE_I_CINEMATIC.mp4"
        audit = audit_delivery_reality(
            {
                "final_video_path": str(latest_video),
                "cinematic_audio_path": str(mix_path),
                "cinematic_video_path": str(cinematic),
                "duration_seconds": 12.0,
                "dialogue_timeline": timeline,
            }
        ).to_dict()

    final_approved = bool(latest_video.is_file() and audit.get("status") == "PASS")
    registry = update_final_delivery_registry(
        root,
        run_id=run_id,
        latest_video=latest_video,
        latest_publish_package=run_path / "publish",
        latest_asset=str(asset_result.get("final_video_path") or ""),
        branded_video_name=latest_video.name if latest_video.is_file() else FINAL_BRANDED_VIDEO_V4_NAME,
        approved=final_approved,
    )

    cleanup_report = {
        "version": LOCK_VERSION,
        "completed_at": _now(),
        "run_id": run_id,
        "registry_path": str(root / "project_brain" / "runtime_state" / "final_delivery_registry.json"),
        "inventory_path": str(inventory_md),
        "stale_manifest_report": stale_report,
        "legacy_outputs": legacy_report,
        "recovery": recovery,
        "asset_registration": asset_result,
        "registry": registry,
        "reality_audit": audit,
        "approved": bool(registry.get("approved") and audit.get("status") == "PASS"),
    }
    report_md = root / "project_brain" / "PROJECT_CLEANUP_REPORT.md"
    report_md.write_text(_render_cleanup_md(cleanup_report), encoding="utf-8")
    return cleanup_report


def _render_inventory_md(inventory: dict[str, Any]) -> str:
    lines = [
        "# Project Forensic Inventory",
        "",
        f"Generated: {inventory.get('generated_at')}",
        "",
        "| Area | Classification | Files | Folders |",
        "|------|----------------|------:|--------:|",
    ]
    for name, row in (inventory.get("sections") or {}).items():
        lines.append(
            f"| `{name}` | {row.get('classification')} | {row.get('file_count', 0)} | {row.get('folder_count', 0)} |"
        )
    lines.extend(["", "## Stale / duplicate manifests", ""])
    for item in inventory.get("duplicate_manifests") or []:
        lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
    lines.extend(["", "## Orphaned output roots", ""])
    for item in inventory.get("orphaned_outputs") or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines) + "\n"


def _render_cleanup_md(report: dict[str, Any]) -> str:
    audit = dict(report.get("reality_audit") or {})
    checks = dict(audit.get("checks") or {})
    lines = [
        "# Project Cleanup Report",
        "",
        f"Completed: {report.get('completed_at')}",
        f"Run ID: `{report.get('run_id')}`",
        f"Approved: **{report.get('approved')}**",
        "",
        "## Registry",
        "",
        f"- Path: `{report.get('registry_path')}`",
        f"- Latest video: `{((report.get('registry') or {}).get('latest_video') or '')}`",
        "",
        "## Archived",
        "",
        f"- Stale manifests: {len((report.get('stale_manifest_report') or {}).get('moved') or [])}",
        f"- Legacy outputs: {len((report.get('legacy_outputs') or {}).get('moved') or [])}",
        "",
        "## Reality audit",
        "",
        f"- Status: **{audit.get('status', 'NOT_RUN')}**",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    return "\n".join(lines) + "\n"


def main() -> int:
    summary = lock_final_delivery()
    print(json.dumps({"approved": summary.get("approved"), "registry": summary.get("registry"), "audit_status": (summary.get('reality_audit') or {}).get('status')}, indent=2, ensure_ascii=False))
    return 0 if summary.get("approved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
