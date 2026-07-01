"""Cinematic shot graph — connected visual graph across all clips."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.director.camera_language_engine import CameraLanguagePlan
from content_brain.director.shot_planner import PlannedShot, ShotPlan
from content_brain.director.visual_memory_store import resolve_project_root

SHOT_GRAPH_VERSION = "shot_graph_engine_v1"
SHOT_GRAPH_DIR = Path("project_brain") / "runtime_state" / "shot_graph"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_run_id(run_id: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", str(run_id or "run").strip())
    return cleaned[:80] or "run"


@dataclass
class ShotGraphNode:
    clip_index: int
    shot_type: str
    transition_type: str
    emotional_progression: str
    pacing: str
    scene_progression: str = ""
    camera_movement: str = ""
    lens: str = ""
    composition: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "shot_type": self.shot_type,
            "transition_type": self.transition_type,
            "emotional_progression": self.emotional_progression,
            "pacing": self.pacing,
            "scene_progression": self.scene_progression,
            "camera_movement": self.camera_movement,
            "lens": self.lens,
            "composition": self.composition,
        }


@dataclass
class ShotGraph:
    version: str = SHOT_GRAPH_VERSION
    run_id: str = ""
    topic: str = ""
    clip_count: int = 0
    nodes: list[ShotGraphNode] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    pacing_curve: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "topic": self.topic,
            "clip_count": self.clip_count,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": list(self.edges),
            "pacing_curve": list(self.pacing_curve),
            "created_at": _now(),
        }


def _pacing_for_index(index: int, clip_count: int) -> str:
    if clip_count <= 1:
        return "resolve"
    ratio = index / clip_count
    if ratio <= 0.34:
        return "open"
    if ratio <= 0.67:
        return "build"
    return "payoff"


def build_shot_graph(
    *,
    run_id: str,
    topic: str,
    shot_plan: ShotPlan,
    camera_plans: list[CameraLanguagePlan],
) -> ShotGraph:
    nodes: list[ShotGraphNode] = []
    pacing_curve: list[str] = []
    for planned, camera in zip(shot_plan.shots, camera_plans):
        pacing = _pacing_for_index(planned.clip_index, shot_plan.clip_count)
        pacing_curve.append(pacing)
        nodes.append(
            ShotGraphNode(
                clip_index=planned.clip_index,
                shot_type=planned.shot_type,
                transition_type=planned.transition_out,
                emotional_progression=planned.emotional_beat,
                pacing=pacing,
                scene_progression=planned.scene_progression,
                camera_movement=camera.camera_movement,
                lens=camera.lens,
                composition=camera.composition,
            )
        )

    edges: list[dict[str, Any]] = []
    for left, right in zip(nodes, nodes[1:]):
        edges.append(
            {
                "from_clip": left.clip_index,
                "to_clip": right.clip_index,
                "transition": right.transition_type,
                "pacing_shift": f"{left.pacing}->{right.pacing}",
            }
        )

    return ShotGraph(
        run_id=run_id,
        topic=topic,
        clip_count=shot_plan.clip_count,
        nodes=nodes,
        edges=edges,
        pacing_curve=pacing_curve,
    )


class ShotGraphStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.graph_dir = self.project_root / SHOT_GRAPH_DIR

    def run_dir(self, run_id: str) -> Path:
        return self.graph_dir / _safe_run_id(run_id)

    def save(self, graph: ShotGraph) -> Path:
        target = self.run_dir(graph.run_id)
        target.mkdir(parents=True, exist_ok=True)
        path = target / "shot_graph.json"
        path.write_text(json.dumps(graph.to_dict(), indent=2), encoding="utf-8")
        return path

    def load(self, run_id: str) -> dict[str, Any]:
        path = self.run_dir(run_id) / "shot_graph.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


__all__ = [
    "SHOT_GRAPH_DIR",
    "SHOT_GRAPH_VERSION",
    "ShotGraph",
    "ShotGraphNode",
    "ShotGraphStore",
    "build_shot_graph",
]
