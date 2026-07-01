"""Visual consistency scoring — prompt-time identity coherence metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from content_brain.director.visual_memory_injector import MEMORY_LOCK_MARKER, clip_has_memory_lock
from content_brain.director.visual_memory_store import VisualSubjectMemory
from content_brain.execution.seamless_continuity_engine import CONTINUE_MARKER, EXACT_FRAME_MARKER

SCORE_ENGINE_VERSION = "consistency_score_engine_v1"
PASS_THRESHOLD = 70.0


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword and keyword.lower() in lowered)


@dataclass
class VisualConsistencyScore:
    visual_consistency_score: float = 0.0
    subject_consistency: float = 0.0
    environment_consistency: float = 0.0
    color_consistency: float = 0.0
    camera_consistency: float = 0.0
    continuity_consistency: float = 0.0
    pass_: bool = False
    version: str = SCORE_ENGINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "visual_consistency_score": round(self.visual_consistency_score, 2),
            "subject_consistency": round(self.subject_consistency, 2),
            "environment_consistency": round(self.environment_consistency, 2),
            "color_consistency": round(self.color_consistency, 2),
            "camera_consistency": round(self.camera_consistency, 2),
            "continuity_consistency": round(self.continuity_consistency, 2),
            "pass": self.pass_,
            "pass_threshold": PASS_THRESHOLD,
        }


def score_visual_consistency(
    *,
    memory: VisualSubjectMemory,
    clip_prompts: list[str],
    continuity_states: list[Any] | None = None,
) -> VisualConsistencyScore:
    if not clip_prompts:
        return VisualConsistencyScore()

    subject_keywords = tuple(
        filter(
            None,
            [
                memory.subject_name,
                memory.fur_color,
                memory.markings,
                memory.scale_color,
                memory.body_shape,
            ],
        )
    )
    env_keywords = (memory.location, memory.weather, memory.lighting)
    color_keywords = (memory.color_palette, memory.fur_color, memory.scale_color)
    camera_keywords = (memory.camera_style, memory.lens, memory.framing)

    subject_hits = sum(_keyword_hits(prompt, subject_keywords) for prompt in clip_prompts)
    env_hits = sum(_keyword_hits(prompt, env_keywords) for prompt in clip_prompts)
    color_hits = sum(_keyword_hits(prompt, color_keywords) for prompt in clip_prompts)
    camera_hits = sum(_keyword_hits(prompt, camera_keywords) for prompt in clip_prompts)

    memory_locks = sum(1 for prompt in clip_prompts if clip_has_memory_lock(prompt))
    continue_markers = sum(1 for prompt in clip_prompts if CONTINUE_MARKER in prompt)
    exact_frame = sum(1 for prompt in clip_prompts if EXACT_FRAME_MARKER in prompt)

    clip_count = len(clip_prompts)
    subject_consistency = min(100.0, 55.0 + subject_hits * 8.0 + memory_locks * 5.0)
    environment_consistency = min(100.0, 50.0 + env_hits * 10.0)
    color_consistency = min(100.0, 50.0 + color_hits * 12.0)
    camera_consistency = min(100.0, 50.0 + camera_hits * 10.0)
    continuity_consistency = min(
        100.0,
        40.0 + continue_markers * 12.0 + exact_frame * 10.0 + (len(continuity_states or []) >= clip_count) * 15.0,
    )

    if clip_count > 1 and not any(MEMORY_LOCK_MARKER in prompt for prompt in clip_prompts[1:]):
        subject_consistency = max(0.0, subject_consistency - 20.0)

    visual_consistency_score = round(
        subject_consistency * 0.30
        + environment_consistency * 0.20
        + color_consistency * 0.15
        + camera_consistency * 0.15
        + continuity_consistency * 0.20,
        2,
    )
    return VisualConsistencyScore(
        visual_consistency_score=visual_consistency_score,
        subject_consistency=subject_consistency,
        environment_consistency=environment_consistency,
        color_consistency=color_consistency,
        camera_consistency=camera_consistency,
        continuity_consistency=continuity_consistency,
        pass_=visual_consistency_score >= PASS_THRESHOLD,
    )


def build_results_panel_payload(
    *,
    memory: VisualSubjectMemory,
    score: VisualConsistencyScore,
    continuity_status: str = "PASS",
) -> dict[str, Any]:
    return {
        "version": SCORE_ENGINE_VERSION,
        "run_id": memory.run_id,
        "subject": memory.subject_name,
        "subject_type": memory.subject_type,
        "visual_memory_status": "PASS" if memory.subject_name else "FAIL",
        "consistency_score": round(score.visual_consistency_score),
        "consistency_pass": score.pass_,
        "continuity_status": continuity_status,
        "metrics": score.to_dict(),
        "memory_path_hint": f"project_brain/visual_memory/run_{memory.run_id}.json",
        "vision_verifier_ready": memory.vision_verifier_ready,
    }


__all__ = [
    "PASS_THRESHOLD",
    "SCORE_ENGINE_VERSION",
    "VisualConsistencyScore",
    "build_results_panel_payload",
    "score_visual_consistency",
]
