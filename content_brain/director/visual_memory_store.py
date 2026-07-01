"""Visual memory store — persist subject identity across clips and runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VISUAL_MEMORY_STORE_VERSION = "visual_memory_store_v1"
MEMORY_DIR = Path("project_brain") / "visual_memory"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _safe_run_id(run_id: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", str(run_id or "run").strip())
    return cleaned[:80] or "run"


def resolve_project_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return Path.cwd().resolve()


@dataclass
class VisualSubjectMemory:
    run_id: str = ""
    subject_name: str = ""
    subject_type: str = "concept"
    face_shape: str = ""
    eye_shape: str = ""
    eye_color: str = ""
    skin_color: str = ""
    fur_color: str = ""
    scale_color: str = ""
    markings: str = ""
    body_shape: str = ""
    clothing: str = ""
    accessories: str = ""
    location: str = ""
    weather: str = ""
    lighting: str = ""
    color_palette: str = ""
    camera_style: str = ""
    lens: str = ""
    framing: str = ""
    version: str = VISUAL_MEMORY_STORE_VERSION
    vision_verifier_ready: bool = True
    frame_analysis_hooks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "subject_name": self.subject_name,
            "subject_type": self.subject_type,
            "appearance": {
                "face_shape": self.face_shape,
                "eye_shape": self.eye_shape,
                "eye_color": self.eye_color,
                "skin_color": self.skin_color,
                "fur_color": self.fur_color,
                "scale_color": self.scale_color,
                "markings": self.markings,
                "body_shape": self.body_shape,
                "clothing": self.clothing,
                "accessories": self.accessories,
            },
            "environment": {
                "location": self.location,
                "weather": self.weather,
                "lighting": self.lighting,
                "color_palette": self.color_palette,
            },
            "camera": {
                "camera_style": self.camera_style,
                "lens": self.lens,
                "framing": self.framing,
            },
            "vision_verifier_ready": self.vision_verifier_ready,
            "frame_analysis_hooks": dict(self.frame_analysis_hooks),
            "created_at": _now(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> VisualSubjectMemory:
        data = dict(payload or {})
        appearance = dict(data.get("appearance") or {})
        environment = dict(data.get("environment") or {})
        camera = dict(data.get("camera") or {})
        return cls(
            run_id=str(data.get("run_id") or ""),
            subject_name=str(data.get("subject_name") or ""),
            subject_type=str(data.get("subject_type") or "concept"),
            face_shape=str(appearance.get("face_shape") or data.get("face_shape") or ""),
            eye_shape=str(appearance.get("eye_shape") or data.get("eye_shape") or ""),
            eye_color=str(appearance.get("eye_color") or data.get("eye_color") or ""),
            skin_color=str(appearance.get("skin_color") or data.get("skin_color") or ""),
            fur_color=str(appearance.get("fur_color") or data.get("fur_color") or ""),
            scale_color=str(appearance.get("scale_color") or data.get("scale_color") or ""),
            markings=str(appearance.get("markings") or data.get("markings") or ""),
            body_shape=str(appearance.get("body_shape") or data.get("body_shape") or ""),
            clothing=str(appearance.get("clothing") or data.get("clothing") or ""),
            accessories=str(appearance.get("accessories") or data.get("accessories") or ""),
            location=str(environment.get("location") or data.get("location") or ""),
            weather=str(environment.get("weather") or data.get("weather") or ""),
            lighting=str(environment.get("lighting") or data.get("lighting") or ""),
            color_palette=str(environment.get("color_palette") or data.get("color_palette") or ""),
            camera_style=str(camera.get("camera_style") or data.get("camera_style") or ""),
            lens=str(camera.get("lens") or data.get("lens") or ""),
            framing=str(camera.get("framing") or data.get("framing") or ""),
            version=str(data.get("version") or VISUAL_MEMORY_STORE_VERSION),
            vision_verifier_ready=bool(data.get("vision_verifier_ready", True)),
            frame_analysis_hooks=dict(data.get("frame_analysis_hooks") or {}),
        )

    def appearance_summary(self) -> str:
        parts = [
            self.fur_color,
            self.scale_color,
            self.skin_color,
            self.markings,
            self.body_shape,
            self.eye_color and f"{self.eye_color} eyes",
            self.clothing,
            self.accessories,
        ]
        cleaned = [_normalize(item) for item in parts if _normalize(item)]
        return ", ".join(cleaned) if cleaned else self.subject_name

    def identity_lock_lines(self) -> list[str]:
        lines = [
            f"Subject: {self.subject_name} ({self.subject_type})",
            f"Appearance lock: {self.appearance_summary()}",
        ]
        if self.markings:
            lines.append(f"Markings locked: {self.markings}")
        if self.location:
            lines.append(f"Environment lock: {self.location}; weather {self.weather or 'unchanged'}; lighting {self.lighting or 'unchanged'}")
        if self.color_palette:
            lines.append(f"Palette lock: {self.color_palette}")
        if self.camera_style or self.lens:
            lines.append(f"Camera lock: {self.camera_style or 'cinematic'} {self.lens or '50mm'} {self.framing or 'vertical hero framing'}")
        return lines


class VisualMemoryStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.memory_dir = self.project_root / MEMORY_DIR

    def memory_path(self, run_id: str) -> Path:
        return self.memory_dir / f"run_{_safe_run_id(run_id)}.json"

    def save(self, memory: VisualSubjectMemory) -> Path:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path = self.memory_path(memory.run_id)
        payload = memory.to_dict()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load(self, run_id: str) -> VisualSubjectMemory | None:
        path = self.memory_path(run_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        memory = VisualSubjectMemory.from_dict(payload)
        if not memory.subject_name:
            return None
        return memory

    def exists(self, run_id: str) -> bool:
        return self.memory_path(run_id).is_file()


__all__ = [
    "MEMORY_DIR",
    "VISUAL_MEMORY_STORE_VERSION",
    "VisualMemoryStore",
    "VisualSubjectMemory",
    "resolve_project_root",
]
