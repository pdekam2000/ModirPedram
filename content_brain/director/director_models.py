"""Director Layer — shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DIRECTOR_VERSION = "director_layer_v1"
PROMPT_CRITIC_VERSION = "director_prompt_critic_v2"

CRITIC_DECISION_PASS = "PASS"
CRITIC_DECISION_IMPROVE = "IMPROVE"
CRITIC_DECISION_REWRITE_REQUIRED = "REWRITE_REQUIRED"

CRITIC_ISSUE_TOPIC_DRIFT = "topic_drift"
CRITIC_ISSUE_WEAK_VISUALS = "weak_visuals"
CRITIC_ISSUE_WEAK_HOOK = "weak_hook"
CRITIC_ISSUE_WEAK_ENDING = "weak_ending"
CRITIC_ISSUE_CONTINUITY_RISK = "continuity_risk"
CRITIC_ISSUE_REPETITION_RISK = "repetition_risk"
CRITIC_ISSUE_VISUAL_SUBJECT_DRIFT = "visual_subject_drift"


@dataclass
class StoryboardClipPlan:
    clip_index: int
    summary: str = ""
    goal: str = ""
    key_visual: str = ""
    emotion: str = ""
    continuity_anchor: str = ""
    ending_transition: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "summary": self.summary,
            "goal": self.goal,
            "key_visual": self.key_visual,
            "emotion": self.emotion,
            "continuity_anchor": self.continuity_anchor,
            "ending_transition": self.ending_transition,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, clip_index: int = 0) -> StoryboardClipPlan:
        return cls(
            clip_index=int(payload.get("clip_index") or clip_index or 0),
            summary=str(payload.get("summary") or payload.get(f"clip_{clip_index}_summary") or ""),
            goal=str(payload.get("goal") or ""),
            key_visual=str(payload.get("key_visual") or ""),
            emotion=str(payload.get("emotion") or ""),
            continuity_anchor=str(payload.get("continuity_anchor") or ""),
            ending_transition=str(payload.get("ending_transition") or ""),
        )


@dataclass
class StoryboardPlan:
    title: str = ""
    logline: str = ""
    main_character: str = ""
    setting: str = ""
    visual_style: str = ""
    emotional_arc: str = ""
    clips: list[StoryboardClipPlan] = field(default_factory=list)
    source: str = "deterministic"
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "logline": self.logline,
            "main_character": self.main_character,
            "setting": self.setting,
            "visual_style": self.visual_style,
            "emotional_arc": self.emotional_arc,
            "clips": [clip.to_dict() for clip in self.clips],
            "source": self.source,
            "model": self.model,
        }


@dataclass
class SceneSpec:
    scene_id: str
    purpose: str = ""
    camera_direction: str = ""
    environment: str = ""
    subject_action: str = ""
    mood: str = ""
    continuity_elements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "purpose": self.purpose,
            "camera_direction": self.camera_direction,
            "environment": self.environment,
            "subject_action": self.subject_action,
            "mood": self.mood,
            "continuity_elements": list(self.continuity_elements),
        }


@dataclass
class ClipSceneBreakdown:
    clip_index: int
    scenes: list[SceneSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"clip_index": self.clip_index, "scenes": [scene.to_dict() for scene in self.scenes]}


@dataclass
class SceneBreakdown:
    clips: list[ClipSceneBreakdown] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"clips": [clip.to_dict() for clip in self.clips]}

    def primary_scene(self, clip_index: int) -> SceneSpec | None:
        for clip in self.clips:
            if clip.clip_index == clip_index and clip.scenes:
                return clip.scenes[0]
        return None


@dataclass
class ContinuityPlan:
    recurring_subjects: list[str] = field(default_factory=list)
    recurring_objects: list[str] = field(default_factory=list)
    recurring_locations: list[str] = field(default_factory=list)
    continuity_rules: list[str] = field(default_factory=list)
    forbidden_changes: list[str] = field(default_factory=list)
    source: str = "deterministic"
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "recurring_subjects": list(self.recurring_subjects),
            "recurring_objects": list(self.recurring_objects),
            "recurring_locations": list(self.recurring_locations),
            "continuity_rules": list(self.continuity_rules),
            "forbidden_changes": list(self.forbidden_changes),
            "source": self.source,
            "model": self.model,
        }


@dataclass
class DirectorLayerOutput:
    storyboard: StoryboardPlan
    scene_breakdown: SceneBreakdown
    continuity_plan: ContinuityPlan
    visual_subject_lock: Any | None = None
    topic_authority_score: float = 0.0
    topic_authority_pass: bool = False
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "version": DIRECTOR_VERSION,
            "storyboard": self.storyboard.to_dict(),
            "scene_breakdown": self.scene_breakdown.to_dict(),
            "continuity_plan": self.continuity_plan.to_dict(),
            "topic_authority_score": self.topic_authority_score,
            "topic_authority_pass": self.topic_authority_pass,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }
        if self.visual_subject_lock is not None and hasattr(self.visual_subject_lock, "to_dict"):
            payload["visual_subject_lock"] = self.visual_subject_lock.to_dict()
        return payload

    def to_director_shots(self, clip_count: int) -> list[dict[str, Any]]:
        shots: list[dict[str, Any]] = []
        for index in range(1, max(1, clip_count) + 1):
            storyboard_clip = next((c for c in self.storyboard.clips if c.clip_index == index), None)
            scene = self.scene_breakdown.primary_scene(index)
            prompt_parts: list[str] = []
            if storyboard_clip:
                prompt_parts.extend([storyboard_clip.summary, storyboard_clip.goal, storyboard_clip.key_visual])
            if scene:
                prompt_parts.extend([scene.subject_action, scene.purpose])
            continuity_notes = list(self.continuity_plan.continuity_rules[:2])
            if storyboard_clip and storyboard_clip.ending_transition:
                continuity_notes.append(storyboard_clip.ending_transition)
            shots.append(
                {
                    "clip_number": index,
                    "prompt": ". ".join(part for part in prompt_parts if part),
                    "action": scene.subject_action if scene else (storyboard_clip.goal if storyboard_clip else ""),
                    "camera_shot": scene.camera_direction if scene else "",
                    "camera_movement": scene.camera_direction if scene else "",
                    "lighting": self.storyboard.visual_style,
                    "continuity_notes": "; ".join(continuity_notes),
                    "emotion": storyboard_clip.emotion if storyboard_clip else (scene.mood if scene else ""),
                    "continuity_anchor": storyboard_clip.continuity_anchor if storyboard_clip else "",
                }
            )
        return shots


@dataclass(frozen=True)
class PromptQualityThresholds:
    overall_min: float = 80.0
    topic_authority_min: float = 90.0
    continuity_min: float = 80.0
    visual_subject_min: float = 80.0
    hook_min: float = 75.0
    ending_min: float = 75.0
    repetition_min: float = 70.0

    def to_dict(self) -> dict[str, float]:
        return {
            "overall_min": self.overall_min,
            "topic_authority_min": self.topic_authority_min,
            "continuity_min": self.continuity_min,
            "visual_subject_min": self.visual_subject_min,
            "hook_min": self.hook_min,
            "ending_min": self.ending_min,
            "repetition_min": self.repetition_min,
        }


@dataclass
class PromptCriticReport:
    overall_score: float = 0.0
    topic_authority_score: float = 0.0
    visual_impact_score: float = 0.0
    continuity_score: float = 0.0
    visual_subject_consistency_score: float = 0.0
    hook_score: float = 0.0
    ending_score: float = 0.0
    repetition_score: float = 0.0
    issues: list[str] = field(default_factory=list)
    decision: str = CRITIC_DECISION_IMPROVE
    weaknesses: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    source: str = "deterministic"
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "topic_authority_score": round(self.topic_authority_score, 2),
            "visual_impact_score": round(self.visual_impact_score, 2),
            "continuity_score": round(self.continuity_score, 2),
            "visual_subject_consistency_score": round(self.visual_subject_consistency_score, 2),
            "hook_score": round(self.hook_score, 2),
            "ending_score": round(self.ending_score, 2),
            "repetition_score": round(self.repetition_score, 2),
            "issues": list(self.issues),
            "decision": self.decision,
            "weaknesses": list(self.weaknesses),
            "improvements": list(self.improvements),
            "source": self.source,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PromptCriticReport:
        return cls(
            overall_score=float(payload.get("overall_score") or 0.0),
            topic_authority_score=float(payload.get("topic_authority_score") or 0.0),
            visual_impact_score=float(payload.get("visual_impact_score") or 0.0),
            continuity_score=float(payload.get("continuity_score") or 0.0),
            visual_subject_consistency_score=float(payload.get("visual_subject_consistency_score") or 0.0),
            hook_score=float(payload.get("hook_score") or 0.0),
            ending_score=float(payload.get("ending_score") or 0.0),
            repetition_score=float(payload.get("repetition_score") or 0.0),
            issues=[str(item) for item in payload.get("issues") or []],
            decision=str(payload.get("decision") or CRITIC_DECISION_IMPROVE),
            weaknesses=[str(item) for item in payload.get("weaknesses") or []],
            improvements=[str(item) for item in payload.get("improvements") or []],
            source=str(payload.get("source") or "openai"),
            model=str(payload.get("model") or payload.get("_model") or ""),
        )


@dataclass
class PromptReviewMetadata:
    score: float
    decision: str
    issues: list[str]
    rewrite_count: int
    topic: str = ""
    version: str = PROMPT_CRITIC_VERSION
    thresholds: dict[str, float] = field(default_factory=dict)
    reports: list[dict[str, Any]] = field(default_factory=list)
    final_report: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "topic": self.topic,
            "score": round(self.score, 2),
            "decision": self.decision,
            "issues": list(self.issues),
            "rewrite_count": self.rewrite_count,
            "thresholds": dict(self.thresholds),
            "reports": list(self.reports),
            "final_report": dict(self.final_report),
            "notes": list(self.notes),
        }


@dataclass
class PromptReviewResult:
    starter_image_prompt: str
    clip_prompts: list[str]
    metadata: PromptReviewMetadata
    initial_report: PromptCriticReport
    final_report: PromptCriticReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "starter_image_prompt": self.starter_image_prompt,
            "clip_prompts": list(self.clip_prompts),
            "metadata": self.metadata.to_dict(),
            "initial_report": self.initial_report.to_dict(),
            "final_report": self.final_report.to_dict(),
        }
