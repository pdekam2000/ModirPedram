"""AI Director V2 pipeline — shot plan, camera language, graph, rhythm, prompt injection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.director.camera_language_engine import (
    DIRECTOR_CAMERA_PLAN_MARKER,
    generate_camera_language_for_plan,
)
from content_brain.director.shot_graph_engine import ShotGraphStore, build_shot_graph
from content_brain.director.shot_planner import plan_shot_sequence
from content_brain.director.subject_memory_extractor import derive_run_id
from content_brain.director.visual_memory_store import resolve_project_root
from content_brain.director.visual_rhythm_engine import score_visual_rhythm

PIPELINE_VERSION = "ai_director_v2_v1"


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


@dataclass
class AiDirectorV2Result:
    version: str = PIPELINE_VERSION
    run_id: str = ""
    clip_prompts: list[str] = field(default_factory=list)
    shot_plan: dict[str, Any] = field(default_factory=dict)
    camera_language: list[dict[str, Any]] = field(default_factory=list)
    shot_graph_path: str = ""
    shot_graph_status: str = "PENDING"
    rhythm_score: float = 0.0
    rhythm_pass: bool = False
    results_panel: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "clip_prompts": list(self.clip_prompts),
            "shot_plan": dict(self.shot_plan),
            "camera_language": list(self.camera_language),
            "shot_graph_path": self.shot_graph_path,
            "shot_graph_status": self.shot_graph_status,
            "rhythm_score": self.rhythm_score,
            "rhythm_pass": self.rhythm_pass,
            "results_panel": dict(self.results_panel),
        }


def inject_camera_plan_into_prompt(prompt: str, camera_block: str) -> str:
    return _normalize(f"{camera_block} {_normalize(prompt)}")


def apply_ai_director_v2(
    *,
    clip_prompts: list[str],
    topic: str,
    clip_count: int,
    story_brief: Any | None = None,
    run_id: str = "",
    project_id: str = "",
    project_root: str | Path | None = None,
    persist: bool = True,
) -> AiDirectorV2Result:
    root = resolve_project_root(project_root)
    resolved_run_id = derive_run_id(run_id=run_id, topic=topic, project_id=project_id)

    shot_plan = plan_shot_sequence(
        clip_count=clip_count,
        topic=topic,
        story_brief=story_brief,
    )
    camera_plans = generate_camera_language_for_plan(
        shot_plan=shot_plan,
        topic_category=shot_plan.topic_category,
    )
    graph = build_shot_graph(
        run_id=resolved_run_id,
        topic=topic,
        shot_plan=shot_plan,
        camera_plans=camera_plans,
    )
    rhythm = score_visual_rhythm(
        shot_plan=shot_plan,
        camera_plans=camera_plans,
        pacing_curve=graph.pacing_curve,
    )

    updated_prompts: list[str] = []
    for index, prompt in enumerate(clip_prompts):
        camera = camera_plans[index] if index < len(camera_plans) else camera_plans[-1]
        updated_prompts.append(inject_camera_plan_into_prompt(prompt, camera.prompt_block()))

    graph_path = ""
    graph_status = "PLAN_ONLY"
    if persist:
        graph_path = str(ShotGraphStore(root).save(graph))
        graph_status = "PASS" if graph_path else "FAIL"
        report_path = root / "project_brain" / "runtime_state" / f"ai_director_v2_report_{resolved_run_id}.json"
        results_panel = build_results_panel(
            run_id=resolved_run_id,
            shot_plan=shot_plan,
            camera_plans=camera_plans,
            graph_status=graph_status,
            graph_path=graph_path,
            rhythm=rhythm,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(results_panel, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        results_panel = build_results_panel(
            run_id=resolved_run_id,
            shot_plan=shot_plan,
            camera_plans=camera_plans,
            graph_status=graph_status,
            graph_path=graph_path,
            rhythm=rhythm,
        )

    return AiDirectorV2Result(
        run_id=resolved_run_id,
        clip_prompts=updated_prompts,
        shot_plan=shot_plan.to_dict(),
        camera_language=[plan.to_dict() for plan in camera_plans],
        shot_graph_path=graph_path,
        shot_graph_status=graph_status,
        rhythm_score=rhythm.rhythm_score,
        rhythm_pass=rhythm.pass_,
        results_panel=results_panel,
    )


def build_results_panel(
    *,
    run_id: str,
    shot_plan: Any,
    camera_plans: list[Any],
    graph_status: str,
    graph_path: str,
    rhythm: Any,
) -> dict[str, Any]:
    shots = [shot.to_dict() for shot in getattr(shot_plan, "shots", [])]
    return {
        "version": PIPELINE_VERSION,
        "run_id": run_id,
        "director_version": "AI Director V2",
        "shot_plan": shots,
        "shot_plan_summary": [
            f"Clip {shot['clip_index']}: {shot['shot_type']} — {shot['scene_progression']}"
            for shot in shots
        ],
        "camera_language": [plan.to_dict() for plan in camera_plans],
        "rhythm_score": round(float(getattr(rhythm, "rhythm_score", 0.0))),
        "rhythm_pass": bool(getattr(rhythm, "pass_", False)),
        "shot_graph_status": graph_status,
        "shot_graph_path": graph_path,
        "director_camera_plan_marker": DIRECTOR_CAMERA_PLAN_MARKER,
    }


__all__ = [
    "PIPELINE_VERSION",
    "AiDirectorV2Result",
    "apply_ai_director_v2",
    "build_results_panel",
    "inject_camera_plan_into_prompt",
]
