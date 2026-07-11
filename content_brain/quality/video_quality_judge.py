"""Video Quality Judge P0 — rules-only scoring from probes and existing reports."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.media_probe import (
    DURATION_LOSS_RATIO_FAIL,
    duration_loss_ratio,
    probe_duration_seconds,
    probe_has_audio_stream,
    probe_mean_volume_db,
)

JUDGE_VERSION = "video_quality_judge_p0"
MIN_AUDIBLE_DB = -45.0
GOOD_LEVEL_DB = -35.0
SHORT_FORM_MIN_SECONDS = 6.0
SHORT_FORM_MAX_SECONDS = 60.0
SCORE_WEAK_THRESHOLD = 60

IMPROVEMENT_ACTIONS: tuple[tuple[str, str, str, dict[str, float]], ...] = (
    ("boost_dialogue_emphasis", "audio_score", "dialogue too weak or narration inaudible", {"dialogue_weight": 0.15}),
    ("increase_environment_weight", "audio_score", "environment audio excellent", {"ambience_weight": 0.10}),
    ("improve_visual_continuity", "continuity_score", "continuity metadata weak or missing", {"continuity_strictness": 0.10}),
    ("strengthen_hook", "viral_score", "hook or opening signals weak", {"hook_weight": 0.10}),
    ("improve_pacing", "story_score", "duration/story pacing mismatch", {"pacing_tightness": 0.10}),
    ("increase_cinematic_language", "visual_score", "visual stream or resolution weak", {"cinematic_prompt_weight": 0.10}),
)


@dataclass
class VideoQualityJudgeResult:
    version: str = JUDGE_VERSION
    run_id: str = ""
    video_path: str = ""
    overall_score: int = 0
    story_score: int = 0
    audio_score: int = 0
    visual_score: int = 0
    continuity_score: int = 0
    viral_score: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvement_actions: list[dict[str, Any]] = field(default_factory=list)
    used_sources: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "video_path": self.video_path,
            "overall_score": self.overall_score,
            "story_score": self.story_score,
            "audio_score": self.audio_score,
            "visual_score": self.visual_score,
            "continuity_score": self.continuity_score,
            "viral_score": self.viral_score,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "improvement_actions": list(self.improvement_actions),
            "used_sources": list(self.used_sources),
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


def probe_has_video_stream(path: str | Path) -> bool:
    target = Path(path)
    if not target.is_file():
        return False
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "video" in (proc.stdout or "")


def probe_video_resolution(path: str | Path) -> tuple[int, int] | None:
    target = Path(path)
    if not target.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0:s=x",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or "").strip()
    if "x" not in text:
        return None
    try:
        width_text, height_text = text.split("x", 1)
        width = int(width_text)
        height = int(height_text)
        if width > 0 and height > 0:
            return width, height
    except ValueError:
        return None
    return None


def _collect_context_paths(context: dict[str, Any]) -> dict[str, Path]:
    root_hint = Path(str(context.get("project_root") or "")).resolve() if context.get("project_root") else None
    run_dir = Path(str(context.get("run_dir") or "")).resolve() if context.get("run_dir") else None
    paths: dict[str, Path] = {}
    mapping = {
        "delivery_gate_report": context.get("delivery_gate_report_path") or "metadata/delivery_quality_gate.json",
        "visual_continuity_report": context.get("visual_continuity_report_path") or "metadata/visual_continuity_report.json",
        "audio_report": context.get("audio_report_path") or "metadata/audio_post_result.json",
        "publish_metadata": context.get("publish_metadata_path") or "publish/metadata.json",
        "runtime_metadata": context.get("runtime_metadata_path") or "metadata/run_summary.json",
        "story_package": context.get("story_package_path") or "",
    }
    for key, value in mapping.items():
        if not value:
            continue
        path = Path(str(value))
        if not path.is_absolute() and run_dir is not None:
            path = run_dir / path
        elif not path.is_absolute() and root_hint is not None:
            path = root_hint / path
        paths[key] = path
    return paths


def _load_reports(context: dict[str, Any]) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    inline_keys = (
        "delivery_gate_report",
        "visual_continuity_report",
        "audio_report",
        "story_package",
        "publish_metadata",
        "runtime_metadata",
        "assembly_manifest",
    )
    for key in inline_keys:
        if isinstance(context.get(key), dict):
            reports[key] = dict(context[key])

    for key, path in _collect_context_paths(context).items():
        if key in reports:
            continue
        loaded = _read_json(path)
        if loaded:
            reports[key] = loaded
    return reports


def _score_visual(
    *,
    video_path: Path,
    duration_seconds: float | None,
    reports: dict[str, Any],
    used_sources: list[str],
) -> tuple[int, list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    score = 35.0

    if video_path.is_file() and video_path.stat().st_size > 0:
        score += 15
        used_sources.append("ffprobe_file_size")
    else:
        weaknesses.append("missing or empty video file")
        return 0, strengths, weaknesses

    if probe_has_video_stream(video_path):
        score += 20
        used_sources.append("ffprobe_video_stream")
        strengths.append("Video stream present")
    else:
        weaknesses.append("no video stream detected")

    if duration_seconds is not None and duration_seconds > 0:
        score += 15
        used_sources.append("ffprobe_duration")
    else:
        weaknesses.append("zero or unreadable duration")
        score = min(score, 20)

    resolution = probe_video_resolution(video_path)
    if resolution:
        width, height = resolution
        used_sources.append("ffprobe_resolution")
        if width >= 720 and height >= 720:
            score += 15
            strengths.append(f"Resolution present ({width}x{height})")
        else:
            score += 8
            weaknesses.append(f"low resolution ({width}x{height})")
    else:
        weaknesses.append("resolution metadata unavailable")

    assembly = dict(reports.get("assembly_manifest") or {})
    assembled_duration = float(assembly.get("duration_seconds") or 0) or None
    loss_ratio = duration_loss_ratio(assembled_seconds=assembled_duration, deliverable_seconds=duration_seconds)
    if loss_ratio is not None:
        used_sources.append("assembly_duration_compare")
        if loss_ratio > DURATION_LOSS_RATIO_FAIL:
            score -= 25
            weaknesses.append("truncated duration vs assembly manifest")
        elif loss_ratio <= 0.01:
            strengths.append("Duration preserved vs assembly")

    return _clamp_score(score), strengths, weaknesses


def _score_audio(
    *,
    video_path: Path,
    reports: dict[str, Any],
    context: dict[str, Any],
    used_sources: list[str],
) -> tuple[int, list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    score = 30.0
    profile = dict(context.get("channel_profile") or {})
    audio_strategy = str(context.get("audio_strategy") or profile.get("audio_strategy") or "").lower()
    music_provider = str(profile.get("music_provider") or "none").lower()
    music_required = music_provider not in {"", "none"} and audio_strategy not in {"kling_native_audio", "music_only"}

    has_audio = probe_has_audio_stream(video_path)
    if has_audio:
        score += 25
        used_sources.append("ffprobe_audio_stream")
    else:
        weaknesses.append("missing audio stream")
        return _clamp_score(min(score, 25)), strengths, weaknesses

    mean_db = probe_mean_volume_db(video_path)
    if mean_db is not None:
        used_sources.append("ffmpeg_mean_volume")
        if mean_db >= GOOD_LEVEL_DB:
            score += 25
            strengths.append(f"Audio level healthy ({mean_db:.1f} dB)")
        elif mean_db >= MIN_AUDIBLE_DB:
            score += 15
            strengths.append(f"Audio audible ({mean_db:.1f} dB)")
        else:
            score += 5
            weaknesses.append(f"audio too quiet ({mean_db:.1f} dB)")
    else:
        weaknesses.append("mean volume probe unavailable")

    audio_report = dict(reports.get("audio_report") or {})
    if audio_report:
        used_sources.append("audio_report")
        music_status = str(audio_report.get("music_status_code") or audio_report.get("music_status") or "").lower()
        if music_required and "skip" in music_status:
            score -= 15
            weaknesses.append("music missing but music provider enabled")
        elif music_status in {"completed", "pass"}:
            strengths.append("Music track reported complete")

    if audio_strategy == "kling_native_audio":
        used_sources.append("audio_strategy_kling_native")
        if has_audio and mean_db is not None and mean_db >= MIN_AUDIBLE_DB:
            score += 10
            strengths.append("Native in-video audio present for Kling route")

    return _clamp_score(score), strengths, weaknesses


def _score_continuity(
    *,
    reports: dict[str, Any],
    context: dict[str, Any],
    used_sources: list[str],
) -> tuple[int, list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    clip_count = int(context.get("clip_count") or dict(reports.get("assembly_manifest") or {}).get("clip_count") or 1)
    continuity = dict(reports.get("visual_continuity_report") or {})

    if continuity:
        used_sources.append("visual_continuity_report")
        overall = continuity.get("overall_score")
        if isinstance(overall, (int, float)):
            score = float(overall)
            if continuity.get("overall_pass") is True:
                strengths.append("Visual continuity report passed")
            elif continuity.get("overall_pass") is False:
                weaknesses.append("Visual continuity report failed")
                score = min(score, 55)
            return _clamp_score(score), strengths, weaknesses
        if continuity.get("overall_pass") is True:
            return 75, ["Visual continuity report passed"], weaknesses
        if continuity.get("overall_pass") is False:
            return 45, strengths, ["Visual continuity report failed"]

    if clip_count >= 2:
        weaknesses.append("missing continuity metadata for multi-clip run")
        return 35, strengths, weaknesses

    return 60, ["Single-clip run — continuity metadata optional"], weaknesses


def _score_story(
    *,
    duration_seconds: float | None,
    reports: dict[str, Any],
    context: dict[str, Any],
    used_sources: list[str],
) -> tuple[int, list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    score = 45.0

    story_package = dict(reports.get("story_package") or {})
    if story_package:
        used_sources.append("story_package")
        metadata = dict(story_package.get("metadata") or {})
        story_visual = dict(metadata.get("story_visual_quality") or {})
        audit = dict(metadata.get("story_audio_audit") or story_package.get("story_audio_audit") or {})
        if audit.get("story_score") is not None:
            used_sources.append("story_audio_audit")
            score = float(audit["story_score"])
        elif story_visual:
            used_sources.append("story_visual_quality")
            parts = [
                story_visual.get("story_progression_score"),
                story_visual.get("emotion_coverage_score"),
                story_visual.get("scene_diversity_score"),
            ]
            numeric = [float(item) for item in parts if isinstance(item, (int, float))]
            if numeric:
                score = sum(numeric) / len(numeric)
        blueprint = dict(story_package.get("story_blueprint") or {})
        if any(str(blueprint.get(key) or "").strip() for key in ("hook", "setup", "conflict", "resolution")):
            strengths.append("Story package arc fields present")
    else:
        weaknesses.append("missing story package")
        score = min(score, 40)

    planned_duration = float(
        context.get("planned_duration_seconds")
        or dict(reports.get("assembly_manifest") or {}).get("duration_seconds")
        or 0
    )
    if planned_duration > 0 and duration_seconds is not None:
        used_sources.append("duration_story_compare")
        delta_ratio = abs(duration_seconds - planned_duration) / planned_duration
        if delta_ratio > 0.25:
            score -= 15
            weaknesses.append("duration/story mismatch vs planned duration")
        else:
            strengths.append("Delivered duration aligns with planned story length")

    runtime = dict(reports.get("runtime_metadata") or {})
    if str(runtime.get("topic") or context.get("topic") or "").strip():
        used_sources.append("runtime_topic")
        score += 5

    return _clamp_score(score), strengths, weaknesses


def _score_viral(
    *,
    duration_seconds: float | None,
    reports: dict[str, Any],
    context: dict[str, Any],
    used_sources: list[str],
) -> tuple[int, list[str], list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    existing = context.get("viral_score")
    if isinstance(existing, (int, float)):
        used_sources.append("existing_viral_score")
        return _clamp_score(float(existing)), strengths, weaknesses

    brief = dict(context.get("brief_snapshot") or {})
    story_quality = dict(brief.get("story_quality") or context.get("story_quality") or {})
    viral_card = dict(story_quality.get("viral_scorecard") or {})
    composite = viral_card.get("composite_score")
    if isinstance(composite, (int, float)):
        used_sources.append("viral_scorecard")
        return _clamp_score(float(composite)), strengths, weaknesses

    score = 40.0
    topic = str(context.get("topic") or dict(reports.get("runtime_metadata") or {}).get("topic") or "").strip()
    if topic:
        score += 20
        used_sources.append("topic_present")
        strengths.append("Topic/title present for distribution")
    else:
        weaknesses.append("topic missing")

    if duration_seconds is not None and SHORT_FORM_MIN_SECONDS <= duration_seconds <= SHORT_FORM_MAX_SECONDS:
        score += 20
        used_sources.append("short_form_duration")
        strengths.append("Short-form duration supported")
    else:
        weaknesses.append("duration outside short-form heuristic range")

    story_package = dict(reports.get("story_package") or {})
    blueprint = dict(story_package.get("story_blueprint") or {})
    if str(blueprint.get("hook") or "").strip():
        score += 20
        used_sources.append("story_hook")
        strengths.append("Story hook present")
    else:
        weaknesses.append("hook missing from story package")

    publish = dict(reports.get("publish_metadata") or {})
    if publish:
        used_sources.append("publish_metadata")
        score += 5

    return _clamp_score(score), strengths, weaknesses


def _build_improvement_actions(scores: dict[str, int], weaknesses: list[str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    weakness_text = " ".join(weaknesses).lower()
    for action_id, score_key, reason, delta in IMPROVEMENT_ACTIONS:
        current = scores.get(score_key, 100)
        if action_id == "increase_environment_weight":
            if current >= 70 and "environment" in weakness_text:
                actions.append(
                    {
                        "action_id": action_id,
                        "reason": reason,
                        "target_score": score_key,
                        "current_score": current,
                        "suggested_delta": dict(delta),
                    }
                )
            continue
        if current >= SCORE_WEAK_THRESHOLD:
            continue
        if action_id == "improve_pacing" and "duration/story mismatch" not in weakness_text:
            continue
        if action_id == "strengthen_hook" and "hook missing" not in weakness_text:
            continue
        actions.append(
            {
                "action_id": action_id,
                "reason": reason,
                "target_score": score_key,
                "current_score": current,
                "suggested_delta": dict(delta),
            }
        )
    return actions


def judge_video_quality(
    *,
    video_path: str | Path,
    run_id: str = "",
    context: dict[str, Any] | None = None,
) -> VideoQualityJudgeResult:
    """Score a canonical deliverable using probes and existing run reports only."""
    payload = dict(context or {})
    path = Path(video_path).resolve()
    reports = _load_reports(payload)
    used_sources: list[str] = []
    duration_seconds = probe_duration_seconds(path)

    visual_score, visual_strengths, visual_weaknesses = _score_visual(
        video_path=path,
        duration_seconds=duration_seconds,
        reports=reports,
        used_sources=used_sources,
    )
    audio_score, audio_strengths, audio_weaknesses = _score_audio(
        video_path=path,
        reports=reports,
        context=payload,
        used_sources=used_sources,
    )
    continuity_score, continuity_strengths, continuity_weaknesses = _score_continuity(
        reports=reports,
        context=payload,
        used_sources=used_sources,
    )
    story_score, story_strengths, story_weaknesses = _score_story(
        duration_seconds=duration_seconds,
        reports=reports,
        context=payload,
        used_sources=used_sources,
    )
    viral_score, viral_strengths, viral_weaknesses = _score_viral(
        duration_seconds=duration_seconds,
        reports=reports,
        context=payload,
        used_sources=used_sources,
    )

    scores = {
        "story_score": story_score,
        "audio_score": audio_score,
        "visual_score": visual_score,
        "continuity_score": continuity_score,
        "viral_score": viral_score,
    }
    overall = _clamp_score(
        story_score * 0.25
        + audio_score * 0.20
        + visual_score * 0.20
        + continuity_score * 0.20
        + viral_score * 0.15
    )

    strengths = visual_strengths + audio_strengths + continuity_strengths + story_strengths + viral_strengths
    weaknesses = visual_weaknesses + audio_weaknesses + continuity_weaknesses + story_weaknesses + viral_weaknesses
    deduped_strengths = list(dict.fromkeys(strengths))
    deduped_weaknesses = list(dict.fromkeys(weaknesses))
    actions = _build_improvement_actions(scores, deduped_weaknesses)

    return VideoQualityJudgeResult(
        run_id=str(run_id or payload.get("run_id") or ""),
        video_path=str(path),
        overall_score=overall,
        story_score=story_score,
        audio_score=audio_score,
        visual_score=visual_score,
        continuity_score=continuity_score,
        viral_score=viral_score,
        strengths=deduped_strengths[:8],
        weaknesses=deduped_weaknesses[:8],
        improvement_actions=actions,
        used_sources=sorted(set(used_sources)),
        metadata={
            "duration_seconds": duration_seconds,
            "judge_mode": "rules_only_p0",
        },
    )


def resolve_quality_output_dir(
    *,
    video_path: str | Path,
    run_id: str = "",
    run_dir: str | Path | None = None,
    project_root: str | Path | None = None,
) -> Path:
    if run_dir:
        return Path(run_dir).resolve() / "quality"

    path = Path(video_path).resolve()
    parts = path.parts
    if "kling_multishot_live" in parts:
        idx = parts.index("kling_multishot_live")
        if idx + 1 < len(parts):
            return Path(*parts[: idx + 2]) / "quality"
    if "runs" in parts:
        idx = parts.index("runs")
        if idx + 1 < len(parts):
            return Path(*parts[: idx + 2]) / "quality"

    root = Path(project_root).resolve() if project_root else Path.cwd()
    safe_run = run_id or path.stem
    return root / "outputs" / "quality_judge" / safe_run


def persist_video_quality_judge(
    result: VideoQualityJudgeResult | dict[str, Any],
    *,
    project_root: str | Path,
    run_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    root = Path(project_root).resolve()
    payload = result.to_dict() if isinstance(result, VideoQualityJudgeResult) else dict(result)
    video_path = Path(str(payload.get("video_path") or ""))
    run_id = str(payload.get("run_id") or video_path.stem)

    run_quality_dir = resolve_quality_output_dir(
        video_path=video_path,
        run_id=run_id,
        run_dir=run_dir,
        project_root=root,
    )
    run_quality_dir.mkdir(parents=True, exist_ok=True)
    run_output = run_quality_dir / "video_quality_judge.json"
    run_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    latest_dir = root / "project_brain" / "quality_judge"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_output = latest_dir / "latest_video_quality_judge.json"
    latest_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_output, latest_output


def judge_and_persist(
    *,
    video_path: str | Path,
    run_id: str = "",
    context: dict[str, Any] | None = None,
    project_root: str | Path,
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    result = judge_video_quality(video_path=video_path, run_id=run_id, context=context)
    persist_video_quality_judge(result, project_root=project_root, run_dir=run_dir)
    return result.to_dict()


def build_judge_context_from_run_dir(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    run_id: str = "",
    topic: str = "",
    clip_count: int | None = None,
    audio_strategy: str = "",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect inline/file reports from a versioned run folder for judge scoring."""
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve()
    run_summary = _read_json(run_path / "metadata" / "run_summary.json")
    kling_metadata = _read_json(run_path / "metadata.json")
    preflight = _read_json(run_path / "preflight.json")
    assembly_manifest = _read_json(run_path / "metadata" / "assembly_manifest.json")
    if not assembly_manifest:
        assembly_manifest = _read_json(root / "project_brain" / "runtime_state" / "assembly_manifest.json")

    story_package: dict[str, Any] = {}
    for candidate in (
        run_path / "metadata" / "story_package.json",
        run_path / "story_package.json",
        root / "project_brain" / "runtime_state" / "story_package.json",
    ):
        loaded = _read_json(candidate)
        if loaded:
            story_package = loaded
            break

    resolved_clip_count = clip_count
    if resolved_clip_count is None:
        resolved_clip_count = int(
            assembly_manifest.get("clip_count")
            or kling_metadata.get("clip_count")
            or preflight.get("kling_clip_count")
            or 1
        )

    try:
        from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

        channel_profile = ProductChannelProfileStore(root).load()
    except Exception:
        channel_profile = {}

    context: dict[str, Any] = {
        "project_root": str(root),
        "run_dir": str(run_path),
        "run_id": str(run_id or run_summary.get("run_id") or kling_metadata.get("run_id") or run_path.name),
        "topic": str(
            topic
            or run_summary.get("topic")
            or kling_metadata.get("topic")
            or preflight.get("authoritative_topic")
            or ""
        ),
        "clip_count": resolved_clip_count,
        "audio_strategy": str(
            audio_strategy
            or kling_metadata.get("audio_strategy")
            or preflight.get("audio_strategy")
            or channel_profile.get("audio_strategy")
            or ""
        ),
        "channel_profile": dict(channel_profile),
        "runtime_metadata": run_summary or kling_metadata,
        "assembly_manifest": assembly_manifest,
        "publish_metadata": _read_json(run_path / "publish" / "metadata.json"),
        "visual_continuity_report": _read_json(run_path / "metadata" / "visual_continuity_report.json"),
        "audio_report": _read_json(run_path / "metadata" / "audio_post_result.json"),
        "delivery_gate_report": _read_json(run_path / "metadata" / "delivery_quality_gate.json"),
        "story_package": story_package,
    }
    if overrides:
        context.update(overrides)
    return context


def run_post_processing_quality_pipeline(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    run_id: str,
    video_path: str | Path,
    topic: str = "",
    clip_count: int | None = None,
    audio_strategy: str = "",
    context_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run judge + proposed-only learning loop after a final deliverable exists."""
    from content_brain.quality.video_learning_loop import run_video_learning_loop

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
    judge_result = judge_and_persist(
        video_path=video,
        run_id=run_id,
        context=context,
        project_root=root,
        run_dir=run_path,
    )
    learning_result = run_video_learning_loop(judge_result, project_root=root)
    run_output = run_path / "quality" / "video_quality_judge.json"

    p1_pipeline: dict[str, Any] = {"skipped": True, "reason": "not_run"}
    try:
        from content_brain.quality.video_quality_judge_p1 import run_post_processing_quality_pipeline_p1

        p1_pipeline = run_post_processing_quality_pipeline_p1(
            project_root=root,
            run_dir=run_path,
            run_id=run_id,
            video_path=video,
            topic=topic,
            clip_count=clip_count,
            audio_strategy=audio_strategy,
            context_overrides=context_overrides,
            p0_judge_result=judge_result,
            prefer_openai=bool(context.get("prefer_openai_semantic", True)),
        )
    except Exception as exc:
        p1_pipeline = {"skipped": True, "reason": f"p1_error:{str(exc)[:120]}"}

    return {
        "skipped": False,
        "run_id": run_id,
        "video_path": str(video),
        "judge": judge_result,
        "learning": learning_result,
        "video_quality_judge_path": str(run_output),
        "proposed_updates_path": str(learning_result.get("proposed_updates_path") or ""),
        "learning_applied": False,
        "judge_p1": dict(p1_pipeline.get("judge_p1") or {}),
        "learning_p1": dict(p1_pipeline.get("learning_p1") or {}),
        "video_quality_judge_p1_path": str(p1_pipeline.get("video_quality_judge_p1_path") or ""),
        "proposed_updates_p1_path": str(p1_pipeline.get("proposed_updates_p1_path") or ""),
        "p1_skipped": bool(p1_pipeline.get("skipped")),
        "p1_skip_reason": str(p1_pipeline.get("reason") or ""),
    }


__all__ = [
    "JUDGE_VERSION",
    "VideoQualityJudgeResult",
    "build_judge_context_from_run_dir",
    "judge_and_persist",
    "judge_video_quality",
    "persist_video_quality_judge",
    "probe_has_video_stream",
    "probe_video_resolution",
    "resolve_quality_output_dir",
    "run_post_processing_quality_pipeline",
]
