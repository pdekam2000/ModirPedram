"""Final delivery registry — single canonical final video path only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FINAL_DELIVERY_REGISTRY_VERSION = "final_delivery_registry_v2"
REGISTRY_REL_PATH = Path("project_brain") / "runtime_state" / "final_delivery_registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def registry_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / REGISTRY_REL_PATH


def _normalize_registry(payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload or {})
    body.setdefault("version", FINAL_DELIVERY_REGISTRY_VERSION)
    canonical = str(body.get("canonical_final_video_path") or body.get("latest_video") or "")
    body["canonical_final_video_path"] = canonical
    return body


def load_final_delivery_registry(project_root: str | Path) -> dict[str, Any]:
    path = registry_path(project_root)
    if not path.is_file():
        return {
            "version": FINAL_DELIVERY_REGISTRY_VERSION,
            "latest_run_id": "",
            "canonical_final_video_path": "",
            "latest_publish_package": "",
            "latest_asset": "",
            "approved": False,
            "approved_at": "",
            "updated_at": "",
            "delivery_reality_passed": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return _normalize_registry(payload)


def save_final_delivery_registry(project_root: str | Path, payload: dict[str, Any]) -> Path:
    path = registry_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = _normalize_registry(payload)
    body["version"] = FINAL_DELIVERY_REGISTRY_VERSION
    body["updated_at"] = _now()
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


def resolve_approved_delivery(
    project_root: str | Path,
    *,
    run_id: str = "",
) -> dict[str, Any]:
    """Return approved delivery paths only when registry, canonical run, and MP4 audit align."""
    from content_brain.platform.canonical_run import load_canonical_run, resolve_canonical_run_id

    registry = load_final_delivery_registry(project_root)
    if not registry.get("approved"):
        return {}
    canonical_run_id = resolve_canonical_run_id(project_root)
    registry_run_id = str(registry.get("latest_run_id") or "")
    if canonical_run_id and registry_run_id and canonical_run_id != registry_run_id:
        return {}
    if run_id and registry_run_id not in {"", run_id}:
        return {}
    if not bool(registry.get("delivery_reality_passed")):
        return {}

    canonical_video = str(registry.get("canonical_final_video_path") or "")
    if not canonical_video or not Path(canonical_video).is_file():
        return {}

    publish = str(registry.get("latest_publish_package") or "")
    asset = str(registry.get("latest_asset") or "")
    canonical = load_canonical_run(project_root)
    return {
        "latest_run_id": registry_run_id or canonical_run_id,
        "canonical_final_video_path": canonical_video,
        "latest_publish_package": publish if publish and Path(publish).is_dir() else "",
        "latest_asset": asset if asset and Path(asset).is_file() else "",
        "approved": True,
        "approved_at": str(registry.get("approved_at") or ""),
        "topic": str(registry.get("topic") or canonical.get("topic") or ""),
        "registry_path": str(registry_path(project_root).resolve()),
        "delivery_reality_passed": True,
    }


def update_final_delivery_registry(
    project_root: str | Path,
    *,
    run_id: str,
    canonical_final_video_path: str | Path = "",
    latest_publish_package: str | Path,
    latest_asset: str | Path = "",
    approved: bool = True,
    topic: str = "",
    clips_completed: int = 0,
    assembly_status: str = "",
    reality_audit_passed: bool = True,
    force: bool = False,
    latest_video: str | Path = "",
    **_: Any,
) -> dict[str, Any]:
    video_path = canonical_final_video_path or latest_video
    updated, payload, _reason = try_update_final_delivery_registry(
        project_root,
        run_id=run_id,
        canonical_final_video_path=video_path,
        latest_publish_package=latest_publish_package,
        latest_asset=latest_asset,
        approved=approved,
        topic=topic,
        clips_completed=clips_completed,
        assembly_status=assembly_status,
        reality_audit_passed=reality_audit_passed,
        force=force,
    )
    if not updated and not force:
        return load_final_delivery_registry(project_root)
    return payload


def try_update_final_delivery_registry(
    project_root: str | Path,
    *,
    run_id: str,
    canonical_final_video_path: str | Path = "",
    latest_publish_package: str | Path,
    latest_asset: str | Path = "",
    approved: bool = True,
    topic: str = "",
    clips_completed: int = 0,
    assembly_status: str = "",
    reality_audit_passed: bool = True,
    force: bool = False,
    latest_video: str | Path = "",
    **_: Any,
) -> tuple[bool, dict[str, Any], str]:
    """Guarded registry update. Returns (updated, registry_payload, reason)."""
    video_path = Path(canonical_final_video_path or latest_video).resolve()
    publish_path = Path(latest_publish_package).resolve()
    existing = load_final_delivery_registry(project_root)

    if not force:
        if not approved:
            return False, existing, "not_approved"
        from content_brain.platform.canonical_run import resolve_canonical_run_id

        canonical_run_id = resolve_canonical_run_id(project_root)
        if canonical_run_id and str(run_id or "") and canonical_run_id != str(run_id):
            return False, existing, "canonical_run_mismatch"
        if clips_completed <= 0:
            return False, existing, "zero_clips_completed"
        if str(assembly_status or "").upper() not in {"ASSEMBLED", "COMPLETED"}:
            return False, existing, "assembly_not_succeeded"
        if not reality_audit_passed:
            return False, existing, "reality_audit_failed"
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            return False, existing, "final_video_missing"
        if topic and run_id:
            from content_brain.platform.run_isolation import load_run_context

            context = load_run_context(project_root, run_id)
            context_topic = str(context.get("topic") or "")
            if context_topic and context_topic.strip().lower() != str(topic).strip().lower():
                return False, existing, "topic_mismatch_run_context"

    payload = {
        "version": FINAL_DELIVERY_REGISTRY_VERSION,
        "latest_run_id": str(run_id or ""),
        "canonical_final_video_path": str(video_path) if video_path.is_file() else "",
        "latest_publish_package": str(publish_path) if publish_path.is_dir() else "",
        "latest_asset": str(Path(latest_asset).resolve()) if latest_asset and Path(latest_asset).is_file() else "",
        "approved": bool(approved and video_path.is_file()),
        "approved_at": _now() if approved and video_path.is_file() else "",
        "topic": str(topic or ""),
        "delivery_reality_passed": bool(reality_audit_passed and approved and video_path.is_file()),
    }
    if not payload["approved"]:
        return False, existing, "final_video_missing"
    save_final_delivery_registry(project_root, payload)
    return True, payload, "updated"


__all__ = [
    "FINAL_DELIVERY_REGISTRY_VERSION",
    "load_final_delivery_registry",
    "registry_path",
    "resolve_approved_delivery",
    "save_final_delivery_registry",
    "try_update_final_delivery_registry",
    "update_final_delivery_registry",
]
