"""Scene recall engine — last-frame recall packages for cross-clip continuity."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.director.visual_memory_store import resolve_project_root

SCENE_RECALL_VERSION = "scene_recall_engine_v1"
RECALL_DIR = Path("project_brain") / "runtime_state" / "scene_recall"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _safe_run_id(run_id: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", str(run_id or "run").strip())
    return cleaned[:80] or "run"


@dataclass
class SceneRecallPackage:
    clip_index: int
    run_id: str = ""
    subject_position: str = ""
    motion_direction: str = ""
    camera_angle: str = ""
    environment_state: str = ""
    lighting_state: str = ""
    emotional_state: str = ""
    version: str = SCENE_RECALL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "clip_index": self.clip_index,
            "run_id": self.run_id,
            "subject_position": self.subject_position,
            "motion_direction": self.motion_direction,
            "camera_angle": self.camera_angle,
            "environment_state": self.environment_state,
            "lighting_state": self.lighting_state,
            "emotional_state": self.emotional_state,
            "created_at": _now(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> SceneRecallPackage:
        data = dict(payload or {})
        return cls(
            clip_index=int(data.get("clip_index") or 0),
            run_id=str(data.get("run_id") or ""),
            subject_position=str(data.get("subject_position") or ""),
            motion_direction=str(data.get("motion_direction") or ""),
            camera_angle=str(data.get("camera_angle") or ""),
            environment_state=str(data.get("environment_state") or ""),
            lighting_state=str(data.get("lighting_state") or ""),
            emotional_state=str(data.get("emotional_state") or ""),
            version=str(data.get("version") or SCENE_RECALL_VERSION),
        )

    def recall_block(self) -> str:
        return _normalize(
            "LAST FRAME RECALL: "
            f"subject position {self.subject_position}; "
            f"motion direction {self.motion_direction}; "
            f"camera angle {self.camera_angle}; "
            f"environment {self.environment_state}; "
            f"lighting {self.lighting_state}; "
            f"emotion {self.emotional_state}."
        )


def _subject_position(clip_index: int, clip_count: int) -> str:
    if clip_index == 1:
        return "center-left hero plane, facing camera three-quarter"
    if clip_index >= clip_count:
        return "center frame hero hold, eyeline locked to lens"
    return "advancing along same screen direction, mid-frame dominance"


def _motion_direction(clip_index: int, clip_count: int) -> str:
    if clip_index == 1:
        return "slow forward discovery push"
    if clip_index >= clip_count:
        return "decelerating settle into final pose"
    return "continuous forward tracking without axis flip"


def _camera_angle(clip_index: int) -> str:
    angles = (
        "low hero angle, slight upward tilt",
        "eye-level tracking with subtle parallax",
        "controlled push-in maintaining horizon",
    )
    return angles[(clip_index - 1) % len(angles)]


def generate_scene_recall_packages(
    *,
    run_id: str,
    clip_count: int,
    environment: str = "",
    lighting: str = "",
    emotional_arc: str = "",
) -> list[SceneRecallPackage]:
    packages: list[SceneRecallPackage] = []
    for index in range(1, clip_count + 1):
        packages.append(
            SceneRecallPackage(
                clip_index=index,
                run_id=run_id,
                subject_position=_subject_position(index, clip_count),
                motion_direction=_motion_direction(index, clip_count),
                camera_angle=_camera_angle(index),
                environment_state=_normalize(environment or "same spatial layout and props anchored"),
                lighting_state=_normalize(lighting or "same key direction and rim separation"),
                emotional_state=_normalize(emotional_arc or f"beat {index} emotional continuity"),
            )
        )
    return packages


class SceneRecallStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.recall_dir = self.project_root / RECALL_DIR

    def run_dir(self, run_id: str) -> Path:
        return self.recall_dir / _safe_run_id(run_id)

    def save_packages(self, packages: list[SceneRecallPackage]) -> Path:
        if not packages:
            raise ValueError("packages required")
        run_id = packages[0].run_id
        target = self.run_dir(run_id)
        target.mkdir(parents=True, exist_ok=True)
        for package in packages:
            path = target / f"clip_{package.clip_index:02d}_recall.json"
            path.write_text(json.dumps(package.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        manifest = {
            "version": SCENE_RECALL_VERSION,
            "run_id": run_id,
            "clip_count": len(packages),
            "packages": [item.to_dict() for item in packages],
            "created_at": _now(),
        }
        manifest_path = target / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest_path

    def load_packages(self, run_id: str) -> list[SceneRecallPackage]:
        manifest_path = self.run_dir(run_id) / "manifest.json"
        if not manifest_path.is_file():
            return []
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        packages = payload.get("packages") if isinstance(payload, dict) else None
        if not isinstance(packages, list):
            return []
        return [SceneRecallPackage.from_dict(item) for item in packages if isinstance(item, dict)]


__all__ = [
    "RECALL_DIR",
    "SCENE_RECALL_VERSION",
    "SceneRecallPackage",
    "SceneRecallStore",
    "generate_scene_recall_packages",
]
