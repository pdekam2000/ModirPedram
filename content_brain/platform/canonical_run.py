"""Single canonical run pointer — removes split-brain between registry, results, and assets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.run_output_versioning import list_run_history

CANONICAL_RUN_VERSION = "canonical_run_v1"
CANONICAL_RUN_PATH = Path("project_brain") / "runtime_state" / "canonical_run.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_run_file(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / CANONICAL_RUN_PATH


def load_canonical_run(project_root: str | Path) -> dict[str, Any]:
    path = canonical_run_file(project_root)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and str(payload.get("run_id") or "").strip():
            payload.setdefault("version", CANONICAL_RUN_VERSION)
            return payload

    history = list_run_history(project_root, limit=1)
    head = history[0] if history else {}
    return {
        "version": CANONICAL_RUN_VERSION,
        "run_id": str(head.get("run_id") or ""),
        "topic": str(head.get("topic") or ""),
        "run_dir": str(head.get("run_dir") or ""),
        "source": "runs_index_head",
        "updated_at": _now(),
    }


def save_canonical_run(project_root: str | Path, payload: dict[str, Any]) -> Path:
    path = canonical_run_file(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["version"] = CANONICAL_RUN_VERSION
    body["updated_at"] = _now()
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def sync_canonical_run_from_index(project_root: str | Path, *, run_id: str = "") -> dict[str, Any]:
    """Align canonical pointer to runs index head or explicit run_id."""
    root = Path(project_root).resolve()
    history = list_run_history(root, limit=100)
    selected: dict[str, Any] = {}
    run_id_text = str(run_id or "").strip()
    if run_id_text:
        selected = next((item for item in history if str(item.get("run_id") or "") == run_id_text), {})
    if not selected and history:
        selected = history[0]
    payload = {
        "version": CANONICAL_RUN_VERSION,
        "run_id": str(selected.get("run_id") or ""),
        "topic": str(selected.get("topic") or ""),
        "run_dir": str(selected.get("run_dir") or ""),
        "publish_dir": str(selected.get("publish_dir") or ""),
        "source": "explicit_run_id" if run_id_text else "runs_index_head",
        "updated_at": _now(),
    }
    save_canonical_run(root, payload)
    return payload


def resolve_canonical_run_id(project_root: str | Path) -> str:
    return str(load_canonical_run(project_root).get("run_id") or "").strip()


def resolve_final_mp4_for_run(run_dir: str | Path, *, project_root: str | Path | None = None) -> Path | None:
    """Return the single canonical branded deliverable for a run folder."""
    from content_brain.platform.canonical_delivery import resolve_canonical_final_video

    root = Path(project_root).resolve() if project_root else Path(run_dir).resolve().parent.parent.parent.parent
    resolved = resolve_canonical_final_video(root, run_dir=run_dir)
    if resolved is not None:
        return resolved
    candidate = Path(run_dir).resolve() / "publish" / "FINAL_BRANDED_VIDEO_CANONICAL.mp4"
    if candidate.is_file() and candidate.stat().st_size > 0:
        return candidate.resolve()
    return None


__all__ = [
    "CANONICAL_RUN_PATH",
    "CANONICAL_RUN_VERSION",
    "canonical_run_file",
    "load_canonical_run",
    "resolve_canonical_run_id",
    "resolve_final_mp4_for_run",
    "save_canonical_run",
    "sync_canonical_run_from_index",
]
