"""Video Quality Judge P1 — semantic story review of delivered MP4 + run context."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.media_probe import probe_duration_seconds
from content_brain.quality.video_learning_loop import LIVE_WEIGHTS_PATH, live_weights_snapshot
from content_brain.quality.video_quality_judge import (
    VideoQualityJudgeResult,
    build_judge_context_from_run_dir,
    judge_video_quality,
    probe_has_audio_stream,
    resolve_quality_output_dir,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

JUDGE_P1_VERSION = "video_quality_judge_p1"
LEARNING_P1_VERSION = "video_learning_loop_p1"
DEFAULT_MODEL = "gpt-4.1-mini"
SCORE_WEAK_THRESHOLD = 65

P1_IMPROVEMENT_CATALOG: tuple[tuple[str, str, str, dict[str, float]], ...] = (
    ("increase_dialogue_emphasis", "dialogue_score", "dialogue weak or missing emotional delivery", {"dialogue_weight": 0.12}),
    ("increase_conflict_strength", "story_score", "story arc lacks rising conflict", {"conflict_weight": 0.10}),
    ("increase_environment_detail", "visual_score", "environment storytelling underdeveloped", {"environment_detail_weight": 0.10}),
    ("increase_emotional_arc", "story_score", "emotional progression flat across clips", {"emotional_arc_weight": 0.12}),
    ("strengthen_character_consistency", "character_score", "character identity or performance inconsistent", {"character_consistency_weight": 0.10}),
    ("improve_narrative_flow", "story_score", "chapters do not advance clearly", {"narrative_flow_weight": 0.10}),
    ("boost_audio_immersion", "audio_score", "native audio immersion weak", {"audio_immersion_weight": 0.10}),
    ("improve_visual_storytelling", "visual_score", "frames lack cinematic storytelling", {"visual_storytelling_weight": 0.10}),
    ("strengthen_hook", "viral_score", "opening hook not compelling", {"hook_weight": 0.10}),
    ("improve_continuity_handoff", "continuity_score", "clip-to-clip continuity weak", {"continuity_strictness": 0.10}),
)

SEMANTIC_SYSTEM_PROMPT = """You are a cinematic short-form video critic reviewing a FINISHED deliverable.
Evaluate story quality from frames AND production metadata — not just technical probes.
Return ONLY valid JSON:
{
  "overall_score": 0-100,
  "story_score": 0-100,
  "character_score": 0-100,
  "dialogue_score": 0-100,
  "visual_score": 0-100,
  "audio_score": 0-100,
  "continuity_score": 0-100,
  "viral_score": 0-100,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "improvement_actions": ["increase_dialogue_emphasis", "increase_emotional_arc"]
}
Scores must reflect viewer experience: emotional impact, dialogue, character consistency, narrative flow, visual storytelling, audio immersion, continuity, viral hook.
improvement_actions must use only these ids: increase_dialogue_emphasis, increase_conflict_strength, increase_environment_detail, increase_emotional_arc, strengthen_character_consistency, improve_narrative_flow, boost_audio_immersion, improve_visual_storytelling, strengthen_hook, improve_continuity_handoff."""


@dataclass
class VideoQualityJudgeP1Result:
    version: str = JUDGE_P1_VERSION
    run_id: str = ""
    video_path: str = ""
    overall_score: int = 0
    story_score: int = 0
    character_score: int = 0
    dialogue_score: int = 0
    visual_score: int = 0
    audio_score: int = 0
    continuity_score: int = 0
    viral_score: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvement_actions: list[dict[str, Any]] = field(default_factory=list)
    used_sources: list[str] = field(default_factory=list)
    judge_mode: str = "semantic_heuristic"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "video_path": self.video_path,
            "overall_score": self.overall_score,
            "story_score": self.story_score,
            "character_score": self.character_score,
            "dialogue_score": self.dialogue_score,
            "visual_score": self.visual_score,
            "audio_score": self.audio_score,
            "continuity_score": self.continuity_score,
            "viral_score": self.viral_score,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "improvement_actions": list(self.improvement_actions),
            "used_sources": list(self.used_sources),
            "judge_mode": self.judge_mode,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


def _clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def extract_semantic_review_frames(
    video_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    max_frames: int = 3,
) -> list[Path]:
    """Sample opening, midpoint, and closing frames for semantic vision review."""
    video = Path(video_path).resolve()
    if not video.is_file():
        return []

    duration = probe_duration_seconds(video) or 15.0
    if duration <= 1.0:
        stamps = [0.0]
    elif max_frames <= 1:
        stamps = [0.5]
    else:
        stamps = [0.5, duration * 0.5, max(0.5, duration - 0.5)][:max_frames]

    out_root = Path(output_dir or video.parent / "quality" / "semantic_frames")
    out_root.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    for index, stamp in enumerate(stamps, start=1):
        out_path = out_root / f"semantic_frame_{index:02d}.jpg"
        try:
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{stamp:.3f}",
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
            frames.append(out_path)
    return frames


def _collect_semantic_context(context: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(str(context.get("run_dir") or ""))
    preflight = dict(context.get("preflight") or _read_json(run_dir / "preflight.json"))
    frame_plan = dict(preflight.get("kling_frame_to_video_plan") or {})
    story_progression = dict(
        frame_plan.get("story_progression")
        or preflight.get("story_progression")
        or {}
    )
    clip_prompts = list(preflight.get("kling_clip_prompts") or [])
    if not clip_prompts and frame_plan.get("clips"):
        clip_prompts = list(frame_plan.get("clips") or [])

    story_package = dict(context.get("story_package") or {})
    blueprint = dict(story_package.get("story_blueprint") or {})
    use_frame_chain = _read_json(run_dir / "use_frame_chain.json")
    if not use_frame_chain:
        use_frame_chain = _read_json(run_dir / "continuity" / "use_frame_chain.json")

    return {
        "topic": str(context.get("topic") or ""),
        "clip_count": int(context.get("clip_count") or frame_plan.get("clip_count") or 1),
        "story_progression": story_progression,
        "chapters": list(story_progression.get("chapters") or []),
        "clip_prompts": clip_prompts,
        "story_blueprint": blueprint,
        "use_frame_chain": use_frame_chain,
        "continuity_method": str(use_frame_chain.get("continuity_method") or preflight.get("continuity_method") or ""),
        "audio_strategy": str(context.get("audio_strategy") or ""),
    }


def _chapter_roles(chapters: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("chapter_role") or "").strip().lower() for item in chapters if item.get("chapter_role")]


def _prompt_texts(clip_prompts: list[Any]) -> list[str]:
    texts: list[str] = []
    for item in clip_prompts:
        if isinstance(item, dict):
            texts.append(str(item.get("prompt") or ""))
        else:
            texts.append(str(item))
    return [text for text in texts if text.strip()]


def _build_p1_improvement_actions(
    scores: dict[str, int],
    weaknesses: list[str],
    explicit_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    weakness_blob = " ".join(weaknesses).lower()
    chosen: list[str] = []
    if explicit_ids:
        chosen.extend([item for item in explicit_ids if item])

    for action_id, target_score, reason, delta in P1_IMPROVEMENT_CATALOG:
        if action_id in chosen:
            continue
        score_key = target_score
        if scores.get(score_key, 100) < SCORE_WEAK_THRESHOLD:
            chosen.append(action_id)
            actions.append(
                {
                    "action_id": action_id,
                    "reason": reason,
                    "target_score": score_key,
                    "current_score": scores.get(score_key, 0),
                    "suggested_delta": dict(delta),
                }
            )
        elif any(token in weakness_blob for token in reason.lower().split()[:3]):
            chosen.append(action_id)
            actions.append(
                {
                    "action_id": action_id,
                    "reason": reason,
                    "target_score": score_key,
                    "current_score": scores.get(score_key, 0),
                    "suggested_delta": dict(delta),
                }
            )

    for action_id in chosen:
        if any(item["action_id"] == action_id for item in actions):
            continue
        catalog = next((row for row in P1_IMPROVEMENT_CATALOG if row[0] == action_id), None)
        if catalog:
            actions.append(
                {
                    "action_id": catalog[0],
                    "reason": catalog[2],
                    "target_score": catalog[1],
                    "current_score": scores.get(catalog[1], 0),
                    "suggested_delta": dict(catalog[3]),
                }
            )
    return actions[:6]


def _score_semantic_heuristic(
    *,
    semantic: dict[str, Any],
    video_path: Path,
    p0: VideoQualityJudgeResult | None,
    used_sources: list[str],
) -> VideoQualityJudgeP1Result:
    chapters = list(semantic.get("chapters") or [])
    roles = _chapter_roles(chapters)
    prompts = _prompt_texts(list(semantic.get("clip_prompts") or []))
    blueprint = dict(semantic.get("story_blueprint") or {})
    topic = str(semantic.get("topic") or "")
    clip_count = int(semantic.get("clip_count") or 1)

    story = 55.0
    character = 58.0
    dialogue = 50.0
    visual = 55.0
    audio = 52.0
    continuity = 58.0
    viral = 54.0
    strengths: list[str] = []
    weaknesses: list[str] = []

    if chapters:
        used_sources.append("story_progression_chapters")
        unique_roles = len(set(roles))
        if unique_roles == len(roles):
            story += 18
            strengths.append("Distinct story chapters planned across clips")
        else:
            weaknesses.append("Story chapters repeat — narrative may stagnate")
            story -= 12
        if "hook" in roles:
            viral += 12
            strengths.append("Hook chapter present in story arc")
        if roles and roles[-1] in {"resolution", "payoff"}:
            story += 10
            strengths.append("Story resolves with a dedicated final chapter")
        conflict_levels = [int(c.get("conflict_level") or 0) for c in chapters]
        if conflict_levels and max(conflict_levels) >= 3:
            story += 8
            strengths.append("Conflict escalation built into chapter plan")

    if prompts:
        used_sources.append("clip_prompts")
        joined = "\n".join(prompts).lower()
        if "character continuity" in joined:
            character += 15
            strengths.append("Prompts enforce character continuity")
        if "environment continuity" in joined:
            visual += 10
            strengths.append("Environment continuity language present")
        if "do not repeat" in joined:
            story += 10
            strengths.append("Anti-repetition guidance in clip prompts")
        if any('spoken line:' in p.lower() or "dialogue:" in p.lower() for p in prompts):
            dialogue += 18
            strengths.append("Dialogue directives present in production prompts")
        else:
            weaknesses.append("Limited dialogue emphasis in clip prompts")
            dialogue -= 10
        if "chapter role" in joined:
            visual += 12
            strengths.append("Visual storytelling tied to chapter roles")
        if len(prompts) >= 2 and prompts[0] != prompts[1]:
            story += 8
        else:
            weaknesses.append("Clip prompts may be too similar")

    if blueprint:
        used_sources.append("story_blueprint")
        if any(str(blueprint.get(k) or "").strip() for k in ("hook", "conflict", "resolution")):
            story += 10
            viral += 6

    chain = dict(semantic.get("use_frame_chain") or {})
    if chain:
        used_sources.append("use_frame_chain")
        if chain.get("continuity_method") == "use_frame":
            continuity += 15
            strengths.append("Use Frame continuity chain recorded")
        if chain.get("fallback_used"):
            continuity -= 8
            weaknesses.append("Continuity fallback used instead of native Use Frame")
        if chain.get("chain_complete"):
            continuity += 8

    if video_path.is_file() and probe_has_audio_stream(video_path):
        audio += 15
        used_sources.append("ffprobe_audio_stream")
        if str(semantic.get("audio_strategy") or "") == "kling_native_audio":
            audio += 10
            strengths.append("Native in-video audio route")
    else:
        weaknesses.append("Delivered MP4 lacks audible immersion signals")
        audio -= 15

    if p0 is not None:
        used_sources.append("p0_baseline")
        visual = max(visual, float(p0.visual_score) * 0.35 + visual * 0.65)
        audio = max(audio, float(p0.audio_score) * 0.35 + audio * 0.65)
        continuity = max(continuity, float(p0.continuity_score) * 0.4 + continuity * 0.6)

    if clip_count >= 2 and not chapters:
        weaknesses.append("Multi-clip run missing story progression metadata")
        story -= 10
        continuity -= 8

    if topic:
        strengths.append(f"Topic anchor present: {topic[:80]}")

    scores = {
        "story_score": _clamp_score(story),
        "character_score": _clamp_score(character),
        "dialogue_score": _clamp_score(dialogue),
        "visual_score": _clamp_score(visual),
        "audio_score": _clamp_score(audio),
        "continuity_score": _clamp_score(continuity),
        "viral_score": _clamp_score(viral),
    }
    overall = _clamp_score(
        scores["story_score"] * 0.20
        + scores["character_score"] * 0.15
        + scores["dialogue_score"] * 0.10
        + scores["visual_score"] * 0.15
        + scores["audio_score"] * 0.10
        + scores["continuity_score"] * 0.15
        + scores["viral_score"] * 0.15
    )
    actions = _build_p1_improvement_actions(scores, weaknesses)
    return VideoQualityJudgeP1Result(
        overall_score=overall,
        story_score=scores["story_score"],
        character_score=scores["character_score"],
        dialogue_score=scores["dialogue_score"],
        visual_score=scores["visual_score"],
        audio_score=scores["audio_score"],
        continuity_score=scores["continuity_score"],
        viral_score=scores["viral_score"],
        strengths=list(dict.fromkeys(strengths))[:8],
        weaknesses=list(dict.fromkeys(weaknesses))[:8],
        improvement_actions=actions,
        used_sources=sorted(set(used_sources)),
        judge_mode="semantic_heuristic",
        metadata={"clip_count": clip_count, "chapter_roles": roles},
    )


def _semantic_review_openai(
    *,
    video_path: Path,
    frames: list[Path],
    semantic: dict[str, Any],
    p0: VideoQualityJudgeResult | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        notes.append("openai_unavailable")
        return None, notes

    user_payload = {
        "topic": semantic.get("topic"),
        "clip_count": semantic.get("clip_count"),
        "story_progression": semantic.get("story_progression"),
        "story_blueprint": semantic.get("story_blueprint"),
        "continuity_method": semantic.get("continuity_method"),
        "p0_scores": p0.to_dict() if p0 else {},
        "review_questions": [
            "Does the story advance emotionally across the deliverable?",
            "Are characters visually and narratively consistent?",
            "Is dialogue or in-scene voice compelling?",
            "Does visual storytelling support the narrative arc?",
            "Does audio feel immersive?",
            "Is clip continuity believable?",
            "Would this hook and hold viewer attention?",
        ],
    }
    content: list[dict[str, Any]] = [
        {"type": "text", "text": json.dumps(user_payload, ensure_ascii=False)},
    ]
    for frame in frames[:3]:
        mime = "image/jpeg" if frame.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{_encode_image(frame)}"},
            }
        )

    client = OpenAI(api_key=api_key, timeout=90.0)
    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SEMANTIC_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.25,
            max_tokens=1200,
        )
        raw = (response.choices[0].message.content or "").strip()
        payload = json.loads(raw)
        if isinstance(payload, dict):
            notes.append(f"openai_semantic_applied:{DEFAULT_MODEL}")
            return payload, notes
    except Exception as exc:  # pragma: no cover
        notes.append(f"openai_semantic_failed:{exc}")
    return None, notes


def judge_video_quality_p1(
    *,
    video_path: str | Path,
    run_id: str = "",
    context: dict[str, Any] | None = None,
    p0_result: VideoQualityJudgeResult | dict[str, Any] | None = None,
    prefer_openai: bool = True,
) -> VideoQualityJudgeP1Result:
    """Semantic review of delivered MP4 using frames + story metadata."""
    path = Path(video_path).resolve()
    ctx = dict(context or {})
    used_sources: list[str] = []
    semantic = _collect_semantic_context(ctx)
    if semantic.get("topic"):
        used_sources.append("topic")
    if ctx.get("preflight"):
        used_sources.append("preflight_inline")

    p0: VideoQualityJudgeResult | None = None
    if isinstance(p0_result, VideoQualityJudgeResult):
        p0 = p0_result
    elif isinstance(p0_result, dict) and p0_result:
        p0 = VideoQualityJudgeResult(
            run_id=str(p0_result.get("run_id") or ""),
            video_path=str(p0_result.get("video_path") or path),
            overall_score=int(p0_result.get("overall_score") or 0),
            story_score=int(p0_result.get("story_score") or 0),
            audio_score=int(p0_result.get("audio_score") or 0),
            visual_score=int(p0_result.get("visual_score") or 0),
            continuity_score=int(p0_result.get("continuity_score") or 0),
            viral_score=int(p0_result.get("viral_score") or 0),
        )

    heuristic = _score_semantic_heuristic(
        semantic=semantic,
        video_path=path,
        p0=p0,
        used_sources=list(used_sources),
    )

    openai_payload: dict[str, Any] | None = None
    if prefer_openai and path.is_file():
        frames = extract_semantic_review_frames(path, output_dir=path.parent / "quality" / "semantic_frames")
        if frames:
            used_sources.append("semantic_frames")
            openai_payload, openai_notes = _semantic_review_openai(
                video_path=path,
                frames=frames,
                semantic=semantic,
                p0=p0,
            )
            heuristic.used_sources.extend(openai_notes)

    if openai_payload:
        scores = {
            "story_score": _clamp_score(float(openai_payload.get("story_score") or heuristic.story_score)),
            "character_score": _clamp_score(float(openai_payload.get("character_score") or heuristic.character_score)),
            "dialogue_score": _clamp_score(float(openai_payload.get("dialogue_score") or heuristic.dialogue_score)),
            "visual_score": _clamp_score(float(openai_payload.get("visual_score") or heuristic.visual_score)),
            "audio_score": _clamp_score(float(openai_payload.get("audio_score") or heuristic.audio_score)),
            "continuity_score": _clamp_score(float(openai_payload.get("continuity_score") or heuristic.continuity_score)),
            "viral_score": _clamp_score(float(openai_payload.get("viral_score") or heuristic.viral_score)),
        }
        overall = _clamp_score(float(openai_payload.get("overall_score") or 0))
        if overall <= 0:
            overall = _clamp_score(
                scores["story_score"] * 0.20
                + scores["character_score"] * 0.15
                + scores["dialogue_score"] * 0.10
                + scores["visual_score"] * 0.15
                + scores["audio_score"] * 0.10
                + scores["continuity_score"] * 0.15
                + scores["viral_score"] * 0.15
            )
        strengths = list(openai_payload.get("strengths") or heuristic.strengths)
        weaknesses = list(openai_payload.get("weaknesses") or heuristic.weaknesses)
        explicit_actions = [str(x) for x in list(openai_payload.get("improvement_actions") or [])]
        result = VideoQualityJudgeP1Result(
            run_id=str(run_id or ctx.get("run_id") or ""),
            video_path=str(path),
            overall_score=overall,
            story_score=scores["story_score"],
            character_score=scores["character_score"],
            dialogue_score=scores["dialogue_score"],
            visual_score=scores["visual_score"],
            audio_score=scores["audio_score"],
            continuity_score=scores["continuity_score"],
            viral_score=scores["viral_score"],
            strengths=list(dict.fromkeys(str(s) for s in strengths))[:8],
            weaknesses=list(dict.fromkeys(str(w) for w in weaknesses))[:8],
            improvement_actions=_build_p1_improvement_actions(scores, weaknesses, explicit_actions),
            used_sources=sorted(set(heuristic.used_sources + ["openai_semantic"])),
            judge_mode="semantic_openai",
            metadata={"semantic_context": semantic, "openai_applied": True},
        )
    else:
        result = heuristic
        result.run_id = str(run_id or ctx.get("run_id") or "")
        result.video_path = str(path)
        result.metadata = {"semantic_context": semantic, "openai_applied": False}

    return result


def persist_video_quality_judge_p1(
    result: VideoQualityJudgeP1Result | dict[str, Any],
    *,
    project_root: str | Path,
    run_dir: str | Path | None = None,
) -> Path:
    root = Path(project_root).resolve()
    payload = result.to_dict() if isinstance(result, VideoQualityJudgeP1Result) else dict(result)
    video_path = Path(str(payload.get("video_path") or ""))
    run_id = str(payload.get("run_id") or video_path.stem)
    quality_dir = resolve_quality_output_dir(
        video_path=video_path,
        run_id=run_id,
        run_dir=run_dir,
        project_root=root,
    )
    quality_dir.mkdir(parents=True, exist_ok=True)
    out_path = quality_dir / "video_quality_judge_p1.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    latest_dir = root / "project_brain" / "quality_judge"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "latest_video_quality_judge_p1.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def propose_p1_learning_updates(
    judge_result: dict[str, Any],
    *,
    project_root: str | Path,
    channel_id: str = "default",
    overall_threshold: int = 70,
) -> dict[str, Any]:
    """Map P1 semantic judge output to proposed learning updates only — no weight mutation."""
    run_id = str(judge_result.get("run_id") or "unknown_run")
    overall_score = int(judge_result.get("overall_score") or 0)
    improvement_actions = list(judge_result.get("improvement_actions") or [])
    mode = "skip"
    if overall_score < overall_threshold:
        mode = "corrective"
    elif overall_score >= 85:
        mode = "reinforcement"

    payload = {
        "version": LEARNING_P1_VERSION,
        "run_id": run_id,
        "channel_id": channel_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "judge_version": judge_result.get("version"),
        "overall_score": overall_score,
        "mode": mode,
        "overall_threshold": overall_threshold,
        "proposed_actions": improvement_actions,
        "weaknesses": list(judge_result.get("weaknesses") or []),
        "strengths": list(judge_result.get("strengths") or []),
        "applied": False,
        "weights_mutated": False,
        "note": "P1 proposed updates only — live Content Brain weights were not mutated.",
    }
    return payload


def persist_p1_proposed_updates(proposed: dict[str, Any], *, project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    run_id = str(proposed.get("run_id") or "unknown_run")
    out_dir = root / "project_brain" / "quality_learning" / "proposed_updates_p1"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(proposed, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def run_video_learning_loop_p1(
    judge_result: dict[str, Any],
    *,
    project_root: str | Path,
    channel_id: str = "default",
    overall_threshold: int = 70,
) -> dict[str, Any]:
    proposed = propose_p1_learning_updates(
        judge_result,
        project_root=project_root,
        channel_id=channel_id,
        overall_threshold=overall_threshold,
    )
    out_path = persist_p1_proposed_updates(proposed, project_root=project_root)
    proposed["proposed_updates_path"] = str(out_path)
    return proposed


def judge_and_persist_p1(
    *,
    video_path: str | Path,
    run_id: str = "",
    context: dict[str, Any] | None = None,
    project_root: str | Path,
    run_dir: str | Path | None = None,
    p0_result: dict[str, Any] | None = None,
    prefer_openai: bool = True,
) -> dict[str, Any]:
    result = judge_video_quality_p1(
        video_path=video_path,
        run_id=run_id,
        context=context,
        p0_result=p0_result,
        prefer_openai=prefer_openai,
    )
    persist_video_quality_judge_p1(result, project_root=project_root, run_dir=run_dir)
    return result.to_dict()


def run_post_processing_quality_pipeline_p1(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    run_id: str,
    video_path: str | Path,
    topic: str = "",
    clip_count: int | None = None,
    audio_strategy: str = "",
    context_overrides: dict[str, Any] | None = None,
    p0_judge_result: dict[str, Any] | None = None,
    prefer_openai: bool = True,
) -> dict[str, Any]:
    """Run P1 semantic judge + proposed-only learning after deliverable exists."""
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve()
    video = Path(video_path).resolve()
    if not video.is_file():
        return {
            "skipped": True,
            "reason": "missing_video",
            "run_id": run_id,
            "video_path": str(video),
        }

    context = build_judge_context_from_run_dir(
        project_root=root,
        run_dir=run_path,
        run_id=run_id,
        topic=topic,
        clip_count=clip_count,
        audio_strategy=audio_strategy,
        overrides=context_overrides,
    )
    context["preflight"] = _read_json(run_path / "preflight.json")

    p0_payload = dict(p0_judge_result or {})
    if not p0_payload:
        p0_payload = judge_video_quality(video_path=video, run_id=run_id, context=context).to_dict()

    judge_p1 = judge_and_persist_p1(
        video_path=video,
        run_id=run_id,
        context=context,
        project_root=root,
        run_dir=run_path,
        p0_result=p0_payload,
        prefer_openai=prefer_openai,
    )
    learning = run_video_learning_loop_p1(judge_p1, project_root=root)
    out_path = run_path / "quality" / "video_quality_judge_p1.json"
    return {
        "skipped": False,
        "run_id": run_id,
        "video_path": str(video),
        "judge_p1": judge_p1,
        "learning_p1": learning,
        "video_quality_judge_p1_path": str(out_path),
        "proposed_updates_p1_path": str(learning.get("proposed_updates_path") or ""),
        "learning_applied": False,
        "weights_mutated": False,
    }


__all__ = [
    "JUDGE_P1_VERSION",
    "LEARNING_P1_VERSION",
    "LIVE_WEIGHTS_PATH",
    "VideoQualityJudgeP1Result",
    "extract_semantic_review_frames",
    "judge_and_persist_p1",
    "judge_video_quality_p1",
    "persist_p1_proposed_updates",
    "persist_video_quality_judge_p1",
    "propose_p1_learning_updates",
    "run_post_processing_quality_pipeline_p1",
    "run_video_learning_loop_p1",
]
