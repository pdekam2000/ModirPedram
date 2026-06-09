"""Topic Universe / SEO Title Bank API service."""

from __future__ import annotations

import platform
import subprocess
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

from content_brain.execution.content_brain_e2e_micro_test_studio import (
    ContentBrainE2EMicroTestStudio,
    ContentBrainE2ETestInput,
)
from content_brain.execution.content_brain_studio_preflight import run_content_brain_studio_preflight
from content_brain.execution.topic_universe_studio import (
    DEFAULT_EXPORT_DIR,
    TopicUniverseStudio,
)


class TopicUniverseStudioService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_result: dict[str, Any] | None = None
        self._running = False
        self._last_error = ""

    def preflight(self) -> dict[str, Any]:
        payload = run_content_brain_studio_preflight()
        payload["title_bank_ready"] = True
        return payload

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return {
                    "ok": False,
                    "message": "A Topic Universe run is already in progress.",
                    "result": self._last_result or {},
                }
            self._running = True
            self._last_error = ""

        try:
            studio = TopicUniverseStudio(project_root=ROOT)
            result = studio.run(payload)
            body = {
                "ok": result.status == "completed",
                "message": "Topic Universe title bank generated.",
                "result": result.to_dict(),
            }
            with self._lock:
                self._last_result = body
            return body
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            return {
                "ok": False,
                "message": str(exc),
                "result": self._last_result or {},
            }
        finally:
            with self._lock:
                self._running = False

    def handoff_to_e2e(self, payload: dict[str, Any]) -> dict[str, Any]:
        selected_title = str(payload.get("selected_title") or payload.get("topic") or "").strip()
        if not selected_title:
            return {"ok": False, "message": "selected_title is required.", "result": {}}

        e2e_studio = ContentBrainE2EMicroTestStudio(project_root=ROOT)
        spec = ContentBrainE2ETestInput(
            topic=selected_title,
            duration_seconds=int(payload.get("duration_seconds") or 30),
            platform=str(payload.get("platform") or "youtube_shorts"),
            niche=str(payload.get("niche") or "general"),
            mood=str(payload.get("mood") or "instructional"),
            clip_length_preference=(
                int(payload["clip_length_preference"])
                if payload.get("clip_length_preference") not in (None, "")
                else None
            ),
        )
        result = e2e_studio.run(spec)
        return {
            "ok": result.status == "completed",
            "message": "Selected title passed into Content Brain E2E Micro Test.",
            "selected_title": selected_title,
            "source_run_id": payload.get("source_run_id"),
            "result": result.to_dict(),
        }

    def open_export_folder(self, path: str | None = None) -> dict[str, Any]:
        target = Path(path or DEFAULT_EXPORT_DIR).resolve()
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
        opened = _open_path_in_file_manager(target)
        return {
            "ok": opened,
            "path": str(target),
            "message": "Export folder opened." if opened else "Could not open export folder on this system.",
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "running": self._running,
                "last_error": self._last_error,
                "last_result": self._last_result,
                "preflight": self.preflight(),
                "export_dir": str(DEFAULT_EXPORT_DIR.resolve()),
            }


def _open_path_in_file_manager(path: Path) -> bool:
    system = platform.system().lower()
    try:
        if system == "windows":
            subprocess.Popen(["explorer", str(path)])
            return True
        if system == "darwin":
            subprocess.Popen(["open", str(path)])
            return True
        subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:
        return False


_service: TopicUniverseStudioService | None = None


def get_topic_universe_studio_service() -> TopicUniverseStudioService:
    global _service
    if _service is None:
        _service = TopicUniverseStudioService()
    return _service
