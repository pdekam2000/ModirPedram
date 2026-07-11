"""Delivery quality gate — block publish when deliverable fails quality checks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.audio.audio_mastering_engine import probe_mean_volume_db as probe_speech_mean_db
from content_brain.platform.media_probe import (
    DURATION_LOSS_RATIO_FAIL,
    duration_loss_ratio,
    duration_preserved,
    probe_duration_seconds,
    probe_has_audio_stream,
    probe_mean_volume_db,
)

DELIVERY_QUALITY_GATE_VERSION = "delivery_quality_gate_v1"
DELIVERY_PASS = "PASS"
DELIVERY_WARNING = "WARNING"
DELIVERY_FAIL = "FAIL"
STEP_PASS = "PASS"
STEP_FAIL = "FAIL"


@dataclass
class DeliveryQualityResult:
    delivery_status: str
    upload_ready: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    assembled_duration_seconds: float | None = None
    deliverable_duration_seconds: float | None = None
    canonical_video_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DELIVERY_QUALITY_GATE_VERSION,
            "delivery_status": self.delivery_status,
            "upload_ready": self.upload_ready,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "checks": list(self.checks),
            "assembled_duration_seconds": self.assembled_duration_seconds,
            "deliverable_duration_seconds": self.deliverable_duration_seconds,
            "canonical_video_path": self.canonical_video_path,
            "metadata": dict(self.metadata),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


def _check(checks: list[dict[str, Any]], check_id: str, name: str, passed: bool, detail: str = "") -> None:
    checks.append({"id": check_id, "name": name, "passed": passed, "detail": detail})


def evaluate_delivery_quality(
    *,
    project_root: str | Path,
    assembly_manifest: dict[str, Any],
    audio_post_result: dict[str, Any] | None = None,
    branding_post_result: dict[str, Any] | None = None,
    publish_manifest: dict[str, Any] | None = None,
    channel_profile: dict[str, Any] | None = None,
) -> DeliveryQualityResult:
    root = Path(project_root).resolve()
    audio_post_result = dict(audio_post_result or {})
    branding_post_result = dict(branding_post_result or {})
    publish_manifest = dict(publish_manifest or {})
    profile = dict(channel_profile or {})

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []

    assembly_status = str(assembly_manifest.get("status") or "")
    assembled_path = Path(str(assembly_manifest.get("output_path") or ""))
    assembled_duration = probe_duration_seconds(assembled_path) if assembled_path.is_file() else None
    if assembled_duration is None:
        assembled_duration = float(assembly_manifest.get("duration_seconds") or 0) or None

    branded_path = Path(
        str(
            branding_post_result.get("final_branded_video_path")
            or publish_manifest.get("branded_video_path")
            or ""
        )
    )
    if not branded_path.is_file():
        branded_path = Path(str(publish_manifest.get("branded_video_path") or ""))

    deliverable_duration = probe_duration_seconds(branded_path) if branded_path.is_file() else None

    if assembly_status != "ASSEMBLED":
        failures.append("assembly_not_assembled")
        _check(checks, "F4", "assembly_ready", False, assembly_status)
    else:
        _check(checks, "F4", "assembly_ready", True)

    if not branded_path.is_file() or branded_path.stat().st_size <= 0:
        failures.append("missing_final_video")
        _check(checks, "F5", "canonical_video_exists", False, str(branded_path))
    else:
        _check(checks, "F5", "canonical_video_exists", True, str(branded_path))

    loss_ratio = duration_loss_ratio(
        assembled_seconds=assembled_duration,
        deliverable_seconds=deliverable_duration,
    )
    if assembled_duration and deliverable_duration is not None:
        preserved = duration_preserved(assembled_seconds=assembled_duration, deliverable_seconds=deliverable_duration)
        _check(
            checks,
            "F1",
            "duration_preservation",
            preserved,
            f"{deliverable_duration:.2f}s vs {assembled_duration:.2f}s",
        )
        if not preserved or (loss_ratio is not None and loss_ratio > DURATION_LOSS_RATIO_FAIL):
            failures.append("duration_loss_exceeds_tolerance")
    elif assembled_duration:
        failures.append("duration_unknown_on_deliverable")
        _check(checks, "F1", "duration_preservation", False, "deliverable duration unknown")

    subtitle_enabled = bool(profile.get("subtitle_enabled", branding_post_result.get("settings", {}).get("subtitle_enabled", True)))
    subtitle_step = dict((branding_post_result.get("steps") or {}).get("subtitles") or {})
    subtitle_status = str(subtitle_step.get("status") or "")
    burn_visible = subtitle_step.get("burn_visible_enough")
    if subtitle_enabled:
        subtitle_ok = subtitle_status == STEP_PASS or burn_visible is True
        _check(checks, "F2", "subtitle_burn", subtitle_ok, subtitle_status)
        if not subtitle_ok:
            failures.append("subtitle_failure")

    if branded_path.is_file() and not probe_has_audio_stream(branded_path):
        failures.append("missing_audio_stream")
        _check(checks, "F3", "audio_stream_present", False)
    elif branded_path.is_file():
        _check(checks, "F3", "audio_stream_present", True)

    music_provider = str(profile.get("music_provider") or audio_post_result.get("music_provider") or "none").lower()
    music_code = str(audio_post_result.get("music_status_code") or "")
    if music_code and music_code not in {"completed"}:
        warnings.append("music_missing_or_failed")
        _check(checks, "W1", "music_layer", music_code == "completed", music_code or "not_merged")

    speech_mean = probe_speech_mean_db(branded_path, start_seconds=0, duration_seconds=18.5) if branded_path.is_file() else None
    mean_db = probe_mean_volume_db(branded_path) if branded_path.is_file() else None
    if speech_mean is not None and speech_mean < -20.0:
        warnings.append("narration_quiet_in_speech_window")
        _check(checks, "W2", "narration_speech_level", False, f"{speech_mean:.1f} dB")
    elif speech_mean is not None:
        _check(checks, "W2", "narration_speech_level", -18.0 >= speech_mean >= -12.0 or speech_mean >= -20.0, f"{speech_mean:.1f} dB")

    if mean_db is not None and mean_db < -38.0 and (speech_mean is None or speech_mean < -20.0):
        warnings.append("ambience_weak_or_quiet_mix")
        _check(checks, "W3", "ambience_audibility", False, f"full={mean_db:.1f} dB speech={speech_mean}")

    character_status = str(audio_post_result.get("character_voice_status") or "")
    if "skipped" in character_status.lower() or "mode off" in character_status.lower():
        warnings.append("character_voices_disabled")
        _check(checks, "W4", "character_voices", False, character_status)

    if failures:
        delivery_status = DELIVERY_FAIL
        upload_ready = False
    elif warnings:
        delivery_status = DELIVERY_WARNING
        upload_ready = False
    else:
        delivery_status = DELIVERY_PASS
        upload_ready = True

    return DeliveryQualityResult(
        delivery_status=delivery_status,
        upload_ready=upload_ready,
        failures=failures,
        warnings=warnings,
        checks=checks,
        assembled_duration_seconds=assembled_duration,
        deliverable_duration_seconds=deliverable_duration,
        canonical_video_path=str(branded_path.resolve()) if branded_path.is_file() else "",
        metadata={
            "duration_loss_ratio": loss_ratio,
            "assembly_status": assembly_status,
            "branding_status": str(branding_post_result.get("status") or ""),
            "publish_status": str(publish_manifest.get("status") or ""),
        },
    )


def write_delivery_quality_gate(
    project_root: str | Path,
    result: DeliveryQualityResult,
    *,
    run_dir: str | Path | None = None,
) -> Path:
    root = Path(project_root).resolve()
    payload = result.to_dict()
    latest = root / "project_brain" / "runtime_state" / "delivery_quality_gate.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if run_dir:
        run_path = Path(run_dir).resolve() / "metadata" / "delivery_quality_gate.json"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return run_path
    return latest


__all__ = [
    "DELIVERY_FAIL",
    "DELIVERY_PASS",
    "DELIVERY_QUALITY_GATE_VERSION",
    "DELIVERY_WARNING",
    "DeliveryQualityResult",
    "evaluate_delivery_quality",
    "write_delivery_quality_gate",
]
