"""Delivery reality auditor — fail closed on final MP4 perceptible delivery."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.audio.audio_delivery_verifier import (
    AUDIBLE_MEAN_DB,
    build_audio_delivery_report,
    measure_environment_contribution,
    measure_music_contribution,
)
from content_brain.branding.subtitle_format_engine import compare_subtitle_burn_visibility, measure_subtitle_text_bbox

DELIVERY_REALITY_AUDITOR_VERSION = "delivery_reality_auditor_v3"
MIN_SUBTITLE_BRIGHT_RATIO = 0.012
SHORTS_READABLE_SUBTITLE_MIN_HEIGHT = 18
AUDIBLE_SPEECH_DB = -45.0


@dataclass
class DeliveryRealityAuditResult:
    status: str
    quality_score: int
    checks: dict[str, bool]
    failures: list[str]
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DELIVERY_REALITY_AUDITOR_VERSION,
            "status": self.status,
            "quality_score": self.quality_score,
            "checks": dict(self.checks),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
        }


def _segment_mean_db(path: Path, start: float, end: float) -> float | None:
    if not path.is_file() or end <= start:
        return None
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{max(0.05, end - start):.3f}",
                "-i",
                str(path),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)", proc.stderr or "")
    return float(match.group(1)) if match else None


def _subtitle_visible_on_video(video_path: Path, sample_seconds: float = 0.5) -> tuple[bool, float]:
    png = video_path.with_suffix(f".subtitle_probe_{sample_seconds:.1f}.png")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-ss",
                str(sample_seconds),
                "-i",
                str(video_path),
                "-vf",
                "crop=iw:ih*24/100:0:ih-ih*24/100",
                "-frames:v",
                "1",
                str(png),
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if not png.is_file():
            return False, 0.0
        from PIL import Image
        import numpy as np

        arr = np.array(Image.open(png))
        bright = (arr[:, :, 0] > 210) & (arr[:, :, 1] > 210) & (arr[:, :, 2] > 210)
        ratio = float(bright.mean())
        return ratio >= MIN_SUBTITLE_BRIGHT_RATIO, ratio
    except Exception:
        return False, 0.0
    finally:
        png.unlink(missing_ok=True)


def _probe_duration_seconds(path: Path) -> float:
    if not path.is_file():
        return 0.0
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return float((proc.stdout or "0").strip())
    except (ValueError, OSError):
        return 0.0


def _extract_audio_track(video_path: Path, output_path: Path) -> Path | None:
    if not video_path.is_file():
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "44100",
                str(output_path),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not output_path.is_file() or output_path.stat().st_size <= 0:
        return None
    return output_path


def _detect_speech_windows(audio_path: Path, *, duration: float, window_seconds: float = 0.5) -> list[tuple[float, float]]:
    if not audio_path.is_file() or duration <= 0:
        return []
    windows: list[tuple[float, float]] = []
    start = 0.0
    while start < duration:
        end = min(duration, start + window_seconds)
        mean_db = _segment_mean_db(audio_path, start, end)
        if mean_db is not None and mean_db > AUDIBLE_SPEECH_DB:
            windows.append((start, end))
        start = end
    return windows


def audit_final_mp4_delivery(final_video_path: str | Path) -> DeliveryRealityAuditResult:
    """Audit delivered MP4 only — ignore manifests, metadata, and PASS flags."""
    video_path = Path(final_video_path).resolve()
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        return DeliveryRealityAuditResult(
            status="FAIL",
            quality_score=0,
            checks={
                "subtitles": False,
                "music": False,
                "ambience": False,
                "dialogue": False,
                "voice_separation": False,
                "story_quality": False,
            },
            failures=["final_mp4_missing"],
            metrics={"final_video_path": str(video_path)},
        )

    duration = _probe_duration_seconds(video_path)
    temp_audio = video_path.with_suffix(".delivery_truth_audio.wav")
    audio_path = _extract_audio_track(video_path, temp_audio)

    bbox_samples = [1.0, 3.0, 5.0, 8.0]
    bbox_rows = [measure_subtitle_text_bbox(video_path, sample) for sample in bbox_samples if sample <= max(duration, 8.0)]
    subtitle_visible = any(bool(row.get("visible")) for row in bbox_rows)
    subtitle_readable = any(
        bool(row.get("visible")) and int(row.get("bbox_height") or 0) >= SHORTS_READABLE_SUBTITLE_MIN_HEIGHT
        for row in bbox_rows
    )

    music: dict[str, Any] = {}
    environment: dict[str, Any] = {}
    speech_windows: list[tuple[float, float]] = []
    if audio_path is not None:
        music = measure_music_contribution(audio_path, duration=duration)
        environment = measure_environment_contribution(audio_path, duration=duration)
        speech_windows = _detect_speech_windows(audio_path, duration=duration)

    speech_seconds = sum(end - start for start, end in speech_windows)
    speech_coverage = speech_seconds / max(duration, 0.001)
    dialogue_audible = speech_seconds >= 2.0 and len(speech_windows) >= 3
    voice_separation = len(speech_windows) >= 4 and speech_coverage >= 0.12
    story_quality = dialogue_audible and speech_coverage >= 0.15

    tail_mean = _segment_mean_db(audio_path, max(1.0, duration * 0.75), max(1.5, duration * 0.95)) if audio_path else None
    no_silent_gaps = tail_mean is None or tail_mean > AUDIBLE_MEAN_DB or speech_coverage >= 0.2

    checks = {
        "subtitles": subtitle_readable if subtitle_visible else False,
        "music": bool(music.get("audible")),
        "ambience": bool(environment.get("audible")),
        "dialogue": dialogue_audible,
        "voice_separation": voice_separation,
        "story_quality": story_quality,
        "no_silent_gaps": no_silent_gaps,
    }
    failures = [name for name, ok in checks.items() if not ok]
    passed = sum(1 for ok in checks.values() if ok)
    quality_score = int(round(100 * passed / max(1, len(checks))))

    temp_audio.unlink(missing_ok=True)

    return DeliveryRealityAuditResult(
        status="PASS" if not failures else "FAIL",
        quality_score=quality_score,
        checks=checks,
        failures=failures,
        metrics={
            "final_video_path": str(video_path),
            "duration_seconds": duration,
            "subtitle_checks": {"samples": bbox_rows, "shorts_min_height": SHORTS_READABLE_SUBTITLE_MIN_HEIGHT},
            "music_contribution": music,
            "environment_contribution": environment,
            "speech_windows": [{"start": s, "end": e} for s, e in speech_windows[:20]],
            "speech_coverage": round(speech_coverage, 4),
            "audit_mode": "final_mp4_only",
        },
    )


def audit_delivery_reality(context: dict[str, Any], *, check_subtitles: bool = True) -> DeliveryRealityAuditResult:
    final_video = str(context.get("final_video_path") or context.get("cinematic_video_path") or "")
    if final_video and Path(final_video).is_file():
        return audit_final_mp4_delivery(final_video)
    video_path = Path(str(context.get("final_video_path") or context.get("cinematic_video_path") or ""))
    mix_path = Path(str(context.get("cinematic_audio_path") or ""))
    dialogue_timeline = dict(context.get("dialogue_timeline") or {})
    duration = float(context.get("duration_seconds") or dialogue_timeline.get("duration_seconds") or 12.0)

    if mix_path.is_file() and not dialogue_timeline:
        delivery_report = build_audio_delivery_report(mix_path=mix_path, dialogue_timeline={"duration_seconds": duration, "lines": []})
    else:
        delivery_report = build_audio_delivery_report(
            mix_path=mix_path,
            dialogue_timeline=dialogue_timeline,
            ffmpeg_filter_proof=str(context.get("ffmpeg_filter_proof") or ""),
            mix_version=str(context.get("mix_version") or ""),
        )

    lines = delivery_report.get("lines") or []
    speakers_required = {"whiskers", "sage", "narrator"}
    speakers_audible = {str(name).lower() for name in (delivery_report.get("speakers_audible") or [])}

    music = measure_music_contribution(mix_path, duration=duration) if mix_path.is_file() else {}
    environment = measure_environment_contribution(mix_path, duration=duration) if mix_path.is_file() else {}

    subtitle_checks: dict[str, Any] = {}
    subtitle_visible = False
    if check_subtitles and video_path.is_file():
        reference_video = Path(str(context.get("cinematic_video_path") or context.get("subtitle_reference_video") or ""))
        bbox_samples = [1.0, 3.0, 5.0, 8.0]
        bbox_rows = [measure_subtitle_text_bbox(video_path, sample) for sample in bbox_samples]
        subtitle_visible = any(row.get("visible") for row in bbox_rows)
        subtitle_checks = {
            "method": "measure_subtitle_text_bbox",
            "samples": bbox_rows,
        }
        if reference_video.is_file() and reference_video.resolve() != video_path.resolve():
            visibility = compare_subtitle_burn_visibility(
                before_video=reference_video,
                after_video=video_path,
                sample_seconds=bbox_samples,
            )
            subtitle_checks["burn_compare"] = visibility
            subtitle_visible = subtitle_visible or bool(visibility.get("visible_enough"))

    video_duration = duration
    if video_path.is_file():
        try:
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            video_duration = float((proc.stdout or str(duration)).strip())
        except (ValueError, OSError):
            video_duration = duration

    mix_duration = float(delivery_report.get("duration_seconds") or 0)
    overlap_pairs: list[dict[str, Any]] = []
    no_unintended_overlap = True
    timeline_lines = [line for line in lines if isinstance(line, dict)]
    for index in range(len(timeline_lines) - 1):
        current = timeline_lines[index]
        nxt = timeline_lines[index + 1]
        handoff = float(nxt.get("start_time") or nxt.get("start_seconds") or 0)
        spill_end = float(current.get("end_time") or current.get("end_seconds") or 0)
        if handoff >= spill_end - 0.02:
            continue
        overlap_start = handoff
        overlap_end = min(spill_end, handoff + 0.35)
        tail_db = _segment_mean_db(mix_path, overlap_start, overlap_end) if mix_path.is_file() else None
        pair_audible = tail_db is not None and tail_db > AUDIBLE_MEAN_DB
        overlap_pairs.append(
            {
                "from": current.get("speaker"),
                "to": nxt.get("speaker"),
                "start": round(overlap_start, 3),
                "end": round(overlap_end, 3),
                "mean_volume_db": tail_db,
                "audible_overlap": pair_audible,
            }
        )
        if pair_audible:
            no_unintended_overlap = False

    checks = {
        "dialogue_delivered": len([line for line in lines if line.get("audible")]) >= 3,
        "whiskers_audible": "whiskers" in speakers_audible,
        "sage_audible": "sage" in speakers_audible,
        "narrator_audible": "narrator" in speakers_audible,
        "voices_delivered": speakers_required.issubset(speakers_audible),
        "music_delivered": bool(music.get("audible")),
        "ambience_delivered": bool(environment.get("audible")),
        "subtitles_delivered": subtitle_visible if check_subtitles else True,
        "duration_match": abs(mix_duration - duration) <= 0.2 and abs(video_duration - duration) <= 0.2,
        "tail_not_silent": bool(delivery_report.get("tail_not_silent")),
        "no_unintended_overlap": no_unintended_overlap,
    }
    failures = [name for name, ok in checks.items() if not ok]
    passed = sum(1 for ok in checks.values() if ok)
    quality_score = int(round(100 * passed / max(1, len(checks))))

    return DeliveryRealityAuditResult(
        status="PASS" if not failures else "FAIL",
        quality_score=quality_score,
        checks=checks,
        failures=failures,
        metrics={
            "delivery_report": delivery_report,
            "music_contribution": music,
            "environment_contribution": environment,
            "subtitle_checks": subtitle_checks,
            "overlap_pairs": overlap_pairs,
            "video_duration_seconds": video_duration,
            "mix_duration_seconds": mix_duration,
        },
    )


__all__ = [
    "DELIVERY_REALITY_AUDITOR_VERSION",
    "DeliveryRealityAuditResult",
    "SHORTS_READABLE_SUBTITLE_MIN_HEIGHT",
    "audit_delivery_reality",
    "audit_final_mp4_delivery",
]
