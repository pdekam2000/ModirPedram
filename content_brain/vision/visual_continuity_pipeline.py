"""Run visual continuity verification across downloaded Runway clips."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.director.visual_subject_lock import VisualSubjectLock, extract_visual_subject_lock
from content_brain.vision.frame_extractor import extract_analysis_frames
from content_brain.vision.visual_continuity_verifier import ClipContinuityResult, verify_clip_frames

PIPELINE_VERSION = "visual_continuity_pipeline_v1"
REPORT_FILENAME = "visual_continuity_report.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def visual_continuity_report_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / "project_brain" / "runtime_state" / REPORT_FILENAME


def _resolve_visual_subject_lock(
    *,
    topic: str,
    visual_subject_lock: VisualSubjectLock | dict[str, Any] | None,
) -> VisualSubjectLock | None:
    if visual_subject_lock is not None:
        if isinstance(visual_subject_lock, VisualSubjectLock):
            return visual_subject_lock
        parsed = VisualSubjectLock.from_dict(dict(visual_subject_lock))
        if parsed and parsed.primary_visual_subject:
            return parsed
    return extract_visual_subject_lock(topic=topic)


def run_visual_continuity_verification(
    *,
    project_root: str | Path,
    topic: str,
    clip_video_paths: list[str],
    visual_subject_lock: VisualSubjectLock | dict[str, Any] | None = None,
    run_id: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    lock = _resolve_visual_subject_lock(topic=topic, visual_subject_lock=visual_subject_lock)
    analysis_root = root / "outputs" / "vision" / (run_id or "latest")
    clip_results: list[ClipContinuityResult] = []
    prior_detected: list[str] = []
    warnings: list[str] = []

    for index, video_path in enumerate(clip_video_paths, start=1):
        path = Path(video_path)
        if not path.is_file():
            warnings.append(f"clip_{index}_video_missing")
            clip_results.append(
                ClipContinuityResult(
                    clip_index=index,
                    video_path=str(path),
                    pass_=False,
                    score=0.0,
                    expected_subject=lock.primary_visual_subject if lock else topic,
                    detected_subject="",
                    similarity_score=0.0,
                    issues=["video_missing"],
                    warnings=[f"missing video: {path}"],
                    notes="Clip video missing.",
                )
            )
            continue
        try:
            frames = extract_analysis_frames(path, output_dir=analysis_root, clip_index=index)
            result = verify_clip_frames(
                clip_index=index,
                topic=topic,
                video_path=str(path),
                frames=frames,
                visual_subject_lock=lock,
                dry_run=dry_run,
                prior_detected_subjects=prior_detected,
            )
        except Exception as exc:
            warnings.append(f"clip_{index}_verification_error")
            result = ClipContinuityResult(
                clip_index=index,
                video_path=str(path),
                pass_=False,
                score=0.0,
                expected_subject=lock.primary_visual_subject if lock else topic,
                detected_subject="",
                similarity_score=0.0,
                issues=["verification_error"],
                warnings=[str(exc)],
                notes=str(exc),
            )
        if result.detected_subject:
            prior_detected.append(result.detected_subject)
        clip_results.append(result)
        if not result.pass_:
            warnings.append(f"clip_{index}_visual_continuity_fail")

    scores = [item.score for item in clip_results]
    overall_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    overall_pass = bool(clip_results) and all(item.pass_ for item in clip_results)
    payload = {
        "version": PIPELINE_VERSION,
        "status": "completed",
        "run_id": run_id,
        "topic": topic,
        "overall_pass": overall_pass,
        "overall_score": overall_score,
        "visual_subject_lock": lock.to_dict() if lock else {},
        "clips": [item.to_dict() for item in clip_results],
        "warnings": warnings,
        "created_at": _now(),
    }
    report_path = visual_continuity_report_path(root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["report_path"] = str(report_path)
    return payload


__all__ = [
    "PIPELINE_VERSION",
    "REPORT_FILENAME",
    "run_visual_continuity_verification",
    "visual_continuity_report_path",
]
