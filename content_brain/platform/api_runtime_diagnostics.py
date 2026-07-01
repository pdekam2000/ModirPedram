"""API runtime diagnostics — publish chain capability flags and version stamp."""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_RUNTIME_DIAGNOSTICS_VERSION = "api_runtime_diagnostics_v1"
RUNTIME_STATE_PATH = Path("project_brain") / "runtime_state" / "api_runtime_diagnostics.json"

_BUILD_KEY_FILES: tuple[str, ...] = (
    "ui/api/main.py",
    "content_brain/execution/product_multiclip_orchestrator.py",
    "content_brain/execution/product_publish_pipeline_trace.py",
    "content_brain/execution/product_assembly_bridge.py",
    "content_brain/execution/product_subtitle_branding_publish.py",
    "content_brain/publish/youtube_metadata_generator.py",
    "content_brain/upload/youtube_upload_runtime.py",
)

_logger = logging.getLogger("modiragent.api.diagnostics")
_live_diagnostics: dict[str, Any] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_api_build_id(project_root: str | Path) -> str:
    root = Path(project_root).resolve()
    digest = hashlib.sha256()
    for relative in _BUILD_KEY_FILES:
        path = root / relative
        if path.is_file():
            stat = path.stat()
            digest.update(relative.encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            digest.update(str(stat.st_size).encode("utf-8"))
    return digest.hexdigest()[:16]


def _module_available(module_path: str, symbol: str) -> bool:
    try:
        module = importlib.import_module(module_path)
        return callable(getattr(module, symbol, None))
    except Exception:
        return False


def get_publish_chain_capabilities(project_root: str | Path) -> dict[str, bool]:
    root = Path(project_root).resolve()
    profile: dict[str, Any] = {}
    try:
        from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

        profile = ProductChannelProfileStore(root).load()
    except Exception:
        profile = {}

    try:
        from content_brain.automation.youtube_auto_upload_config import load_youtube_auto_upload_config

        youtube_auto = load_youtube_auto_upload_config(root)
    except Exception:
        youtube_auto = {}

    return {
        "assembly_bridge_enabled": _module_available(
            "content_brain.execution.product_assembly_bridge",
            "run_product_assembly_bridge",
        ),
        "branding_publish_enabled": _module_available(
            "content_brain.execution.product_subtitle_branding_publish",
            "run_product_subtitle_branding_publish",
        ),
        "youtube_metadata_enabled": _module_available(
            "content_brain.publish.youtube_metadata_generator",
            "ensure_product_studio_publish_metadata",
        ),
        "youtube_upload_enabled": bool(profile.get("youtube_upload_enabled"))
        and _module_available(
            "content_brain.upload.youtube_upload_runtime",
            "run_youtube_upload_from_publish_package",
        ),
        "auto_upload_enabled": bool(youtube_auto.get("auto_upload_enabled")),
    }


def build_runtime_diagnostics(project_root: str | Path, *, api_version: str = "") -> dict[str, Any]:
    from content_brain.execution.product_publish_pipeline_trace import ORCHESTRATOR_VERSION

    root = Path(project_root).resolve()
    capabilities = get_publish_chain_capabilities(root)
    payload = {
        "version": API_RUNTIME_DIAGNOSTICS_VERSION,
        "api_version": api_version,
        "api_build_id": compute_api_build_id(root),
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "startup_time": _now_iso(),
        **capabilities,
    }
    return payload


def persist_runtime_diagnostics(project_root: str | Path, payload: dict[str, Any]) -> Path:
    root = Path(project_root).resolve()
    path = root / RUNTIME_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_persisted_runtime_diagnostics(project_root: str | Path) -> dict[str, Any] | None:
    path = Path(project_root).resolve() / RUNTIME_STATE_PATH
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def init_api_runtime_diagnostics(project_root: str | Path, *, api_version: str = "") -> dict[str, Any]:
    global _live_diagnostics
    payload = build_runtime_diagnostics(project_root, api_version=api_version)
    persist_runtime_diagnostics(project_root, payload)
    _live_diagnostics = payload
    _logger.info(
        "API runtime diagnostics startup api_build_id=%s orchestrator_version=%s "
        "assembly_bridge_enabled=%s branding_publish_enabled=%s youtube_metadata_enabled=%s youtube_upload_enabled=%s auto_upload_enabled=%s",
        payload.get("api_build_id"),
        payload.get("orchestrator_version"),
        payload.get("assembly_bridge_enabled"),
        payload.get("branding_publish_enabled"),
        payload.get("youtube_metadata_enabled"),
        payload.get("youtube_upload_enabled"),
        payload.get("auto_upload_enabled"),
    )
    return payload


def get_live_runtime_diagnostics(project_root: str | Path | None = None) -> dict[str, Any]:
    if _live_diagnostics is not None:
        return dict(_live_diagnostics)
    if project_root is not None:
        persisted = load_persisted_runtime_diagnostics(project_root)
        if persisted:
            return dict(persisted)
    return {}


def is_api_process_stale(project_root: str | Path, *, live_build_id: str = "") -> bool:
    persisted = load_persisted_runtime_diagnostics(project_root) or {}
    current_build_id = compute_api_build_id(project_root)
    reference = live_build_id or str(persisted.get("api_build_id") or "")
    if not reference:
        return False
    return reference != current_build_id


__all__ = [
    "build_runtime_diagnostics",
    "compute_api_build_id",
    "get_live_runtime_diagnostics",
    "get_publish_chain_capabilities",
    "init_api_runtime_diagnostics",
    "is_api_process_stale",
    "load_persisted_runtime_diagnostics",
    "persist_runtime_diagnostics",
]
