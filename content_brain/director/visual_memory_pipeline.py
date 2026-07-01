"""Visual memory pipeline — extract, store, inject, recall, and score."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.director.consistency_score_engine import (
    build_results_panel_payload,
    score_visual_consistency,
)
from content_brain.director.scene_recall_engine import SceneRecallStore, generate_scene_recall_packages
from content_brain.director.subject_memory_extractor import derive_run_id, extract_subject_memory
from content_brain.director.visual_memory_injector import apply_visual_memory_injection
from content_brain.director.visual_memory_store import VisualMemoryStore, resolve_project_root
from content_brain.execution.seamless_continuity_engine import SeamlessContinuityPlan, apply_seamless_continuity

PIPELINE_VERSION = "visual_memory_pipeline_v1"


@dataclass
class VisualMemoryPipelineResult:
    version: str = PIPELINE_VERSION
    run_id: str = ""
    memory_path: str = ""
    recall_manifest_path: str = ""
    clip_prompts: list[str] = field(default_factory=list)
    continuity_plan: SeamlessContinuityPlan | None = None
    results_panel: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "memory_path": self.memory_path,
            "recall_manifest_path": self.recall_manifest_path,
            "clip_prompts": list(self.clip_prompts),
            "continuity_plan": self.continuity_plan.to_dict() if self.continuity_plan else {},
            "results_panel": dict(self.results_panel),
        }


def apply_visual_memory_pipeline(
    *,
    clip_prompts: list[str],
    topic: str,
    story_brief: Any | None = None,
    director_layer: Any | None = None,
    visual_subject_lock: Any | None = None,
    anchors: Any | None = None,
    clip_beats: list[str] | None = None,
    run_id: str = "",
    project_id: str = "",
    project_root: str | Path | None = None,
    persist: bool = True,
) -> VisualMemoryPipelineResult:
    root = resolve_project_root(project_root)
    resolved_run_id = derive_run_id(run_id=run_id, topic=topic, project_id=project_id)

    memory = extract_subject_memory(
        run_id=resolved_run_id,
        topic=topic,
        story_brief=story_brief,
        director_layer=director_layer,
        visual_subject_lock=visual_subject_lock,
    )

    continuity_plan = apply_seamless_continuity(
        clip_prompts=clip_prompts,
        story_brief=story_brief,
        anchors=anchors,
        clip_beats=clip_beats,
        visual_memory=memory,
    )

    injection = apply_visual_memory_injection(
        clip_prompts=continuity_plan.clip_prompts,
        memory=memory,
        run_id=resolved_run_id,
    )

    recalls = generate_scene_recall_packages(
        run_id=resolved_run_id,
        clip_count=len(injection.clip_prompts),
        environment=memory.location,
        lighting=memory.lighting,
        emotional_arc=str(getattr(story_brief, "emotional_arc", "") or ""),
    )

    memory_path = ""
    recall_path = ""
    if persist:
        store = VisualMemoryStore(root)
        memory_path = str(store.save(memory))
        recall_path = str(SceneRecallStore(root).save_packages(recalls))
        report_path = root / "project_brain" / "runtime_state" / f"visual_memory_report_{resolved_run_id}.json"

    score = score_visual_consistency(
        memory=memory,
        clip_prompts=injection.clip_prompts,
        continuity_states=continuity_plan.states,
    )
    if len(injection.clip_prompts) <= 1:
        continuity_status = "PASS"
    else:
        from content_brain.director.visual_memory_injector import MEMORY_LOCK_MARKER
        from content_brain.execution.seamless_continuity_engine import CONTINUE_MARKER, EXACT_FRAME_MARKER

        continuity_status = (
            "PASS"
            if all(
                CONTINUE_MARKER in prompt and EXACT_FRAME_MARKER in prompt and MEMORY_LOCK_MARKER in prompt
                for prompt in injection.clip_prompts[1:]
            )
            else "FAIL"
        )

    results_panel = build_results_panel_payload(
        memory=memory,
        score=score,
        continuity_status=continuity_status,
    )
    results_panel["recall_manifest_path"] = recall_path
    results_panel["memory_path"] = memory_path

    if persist:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(results_panel, indent=2), encoding="utf-8")

    return VisualMemoryPipelineResult(
        run_id=resolved_run_id,
        memory_path=memory_path,
        recall_manifest_path=recall_path,
        clip_prompts=injection.clip_prompts,
        continuity_plan=continuity_plan,
        results_panel=results_panel,
    )


__all__ = [
    "PIPELINE_VERSION",
    "VisualMemoryPipelineResult",
    "apply_visual_memory_pipeline",
]
