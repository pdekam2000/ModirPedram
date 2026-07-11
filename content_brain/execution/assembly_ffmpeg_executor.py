"""
Phase 11J-19 — Assembly FFmpeg Executor.

Dry-run previews the assembly workflow without invoking FFmpeg.
Real execution runs a gated V1 pipeline when ``real_execution_allowed=True``:

* concatenate 1–2 video clips
* merge/attach narration MP3
* burn-in ASS/SRT subtitles when configured
* export ``FINAL_PUBLISH_READY.mp4`` + ``assembly_manifest.json``

Never imports ``pipelines/full_video_pipeline.py``.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_ffmpeg_availability import (
    check_ffmpeg_availability,
    resolve_ffmpeg_binary,
)
from content_brain.execution.assembly_models import (
    AssemblyManifestSkeleton,
    AssemblyPlan,
    EXPECTED_OUTPUT,
    MANIFEST_VERSION,
    ROLE_CLIP,
    ROLE_NARRATION,
    ROLE_SUBTITLE_ASS,
    ROLE_SUBTITLE_SRT,
    ROLE_SUBTITLE_VTT,
    SUBTITLE_MODE_BURN_IN,
    SUBTITLE_MODE_NONE,
    SUBTITLE_MODE_SIDECAR,
    VALIDATION_READY,
)
from content_brain.execution.assembly_smoke_profile import SMOKE_MAX_OUTPUT_BYTES
from content_brain.execution.failure_taxonomy import build_failure_object

EXECUTOR_VERSION = "11j19_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
MANIFEST_FILENAME = "assembly_manifest.json"

STATUS_DRY_RUN = "dry_run"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

CODE_PLAN_INVALID = "ASSEMBLY_PLAN_INVALID"
CODE_VIDEO_MISSING = "ASSEMBLY_VIDEO_MISSING"
CODE_AUDIO_MISSING = "ASSEMBLY_AUDIO_MISSING"
CODE_SUBTITLE_INVALID = "ASSEMBLY_SUBTITLE_INVALID"
CODE_CANCELLED = "ASSEMBLY_CANCELLED"
CODE_REAL_EXECUTION_DISABLED = "ASSEMBLY_REAL_EXECUTION_DISABLED"
CODE_FFMPEG_FAILED = "ASSEMBLY_FFMPEG_FAILED"
CODE_OUTPUT_INVALID = "ASSEMBLY_OUTPUT_INVALID"
CODE_OUTPUT_MISSING = "ASSEMBLY_OUTPUT_MISSING"
CODE_TIMEOUT = "ASSEMBLY_TIMEOUT"

_SUBTITLE_ROLES = frozenset({ROLE_SUBTITLE_ASS, ROLE_SUBTITLE_SRT, ROLE_SUBTITLE_VTT})


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


@dataclass
class AssemblyExecutionResult:
    """Structured result of an assembly execution attempt."""

    session_id: str
    status: str
    expected_output: str | None = None
    output_file: str | None = None
    output_created: bool = False
    output_size: int | None = None
    duration_seconds: float | None = None
    execution_time_seconds: float | None = None
    validation_status: str | None = None
    input_counts: dict[str, int] = field(default_factory=dict)
    planned_steps: list[dict[str, Any]] = field(default_factory=list)
    real_assembly_executed: bool = False
    manifest_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    executor_version: str = EXECUTOR_VERSION
    generated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor_version": self.executor_version,
            "session_id": self.session_id,
            "status": self.status,
            "expected_output": self.expected_output,
            "output_file": self.output_file,
            "output_created": bool(self.output_created),
            "output_size": self.output_size,
            "duration_seconds": self.duration_seconds,
            "execution_time_seconds": self.execution_time_seconds,
            "validation_status": self.validation_status,
            "input_counts": dict(self.input_counts),
            "planned_steps": list(self.planned_steps),
            "real_assembly_executed": bool(self.real_assembly_executed),
            "manifest_path": self.manifest_path,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "generated_at": self.generated_at,
        }


class AssemblyFFmpegExecutor:
    """Assembly executor — dry-run preview or gated real FFmpeg pipeline."""

    def __init__(self, ffmpeg_path: str | None = None, *, dry_run: bool = True) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._default_dry_run = dry_run

    def execute(
        self,
        plan: AssemblyPlan,
        *,
        cancel_check: Callable[[], bool] | None = None,
        overwrite: bool = False,
        timeout_seconds: int = 120,
        dry_run: bool = True,
        real_execution_allowed: bool = False,
        max_output_bytes: int | None = SMOKE_MAX_OUTPUT_BYTES,
    ) -> AssemblyExecutionResult:
        session_id = getattr(plan, "session_id", None) if plan is not None else None
        result = AssemblyExecutionResult(
            session_id=str(session_id or "unknown"),
            status=STATUS_FAILED,
            validation_status=getattr(plan, "validation_status", None) if plan is not None else None,
        )

        if not isinstance(plan, AssemblyPlan):
            result.errors.append(
                build_failure_object(CODE_PLAN_INVALID, "No AssemblyPlan provided.")
            )
            return result
        if plan.validation_status != VALIDATION_READY:
            result.errors.append(
                build_failure_object(
                    CODE_PLAN_INVALID,
                    f"AssemblyPlan not READY (validation_status={plan.validation_status}).",
                )
            )
            return result

        result.expected_output = plan.expected_output

        if cancel_check is not None and cancel_check():
            result.status = STATUS_CANCELLED
            result.errors.append(
                build_failure_object(CODE_CANCELLED, "Cancelled before assembly execution.")
            )
            return result

        clips = [a for a in plan.video_inputs if a.role == ROLE_CLIP]
        narration = [a for a in plan.audio_inputs if a.role == ROLE_NARRATION]
        subtitles = [a for a in plan.subtitle_inputs if a.role in _SUBTITLE_ROLES and not a.is_manifest]

        existing_clips = [a for a in clips if a.file_path and Path(a.file_path).is_file()]
        existing_narration = [a for a in narration if a.file_path and Path(a.file_path).is_file()]

        if not existing_clips:
            result.errors.append(
                build_failure_object(CODE_VIDEO_MISSING, "No usable video clips on disk.")
            )
            return result
        if not existing_narration:
            result.errors.append(
                build_failure_object(CODE_AUDIO_MISSING, "No usable narration audio on disk.")
            )
            return result

        if plan.subtitle_mode == SUBTITLE_MODE_BURN_IN:
            burn_sources = [a for a in subtitles if a.role in (ROLE_SUBTITLE_ASS, ROLE_SUBTITLE_SRT)]
            if not burn_sources:
                vtt_only = any(a.role == ROLE_SUBTITLE_VTT for a in subtitles)
                if vtt_only:
                    result.errors.append(
                        build_failure_object(
                            CODE_SUBTITLE_INVALID,
                            "VTT subtitle burn-in is unsupported in V1 (need ASS or SRT).",
                        )
                    )
                    return result
                result.warnings.append("burn_in requested but no subtitle source present")

        result.input_counts = {
            "video": len(existing_clips),
            "voice": len(existing_narration),
            "subtitle": len(subtitles),
        }
        result.warnings.extend(list(plan.warnings))

        if plan.music_inputs or plan.music_mode not in (None, "none"):
            result.warnings.append("music layer is reserved and ignored in V1")
        if plan.output_variant not in (None, "primary"):
            result.warnings.append(f"output_variant '{plan.output_variant}' is reserved and ignored in V1")

        result.planned_steps = self._plan_steps(plan, existing_clips, existing_narration, subtitles)

        effective_dry_run = dry_run is not False

        if effective_dry_run:
            result.status = STATUS_DRY_RUN
            result.real_assembly_executed = False
            result.output_created = False
            result.output_file = None
            return result

        if not real_execution_allowed:
            result.errors.append(
                build_failure_object(
                    CODE_REAL_EXECUTION_DISABLED,
                    "Real FFmpeg assembly is not permitted (gates not satisfied).",
                )
            )
            result.status = STATUS_FAILED
            result.real_assembly_executed = False
            result.output_created = False
            return result

        return self._execute_real(
            plan,
            result,
            existing_clips=existing_clips,
            existing_narration=existing_narration,
            subtitles=subtitles,
            cancel_check=cancel_check,
            overwrite=overwrite,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )

    def _execute_real(
        self,
        plan: AssemblyPlan,
        result: AssemblyExecutionResult,
        *,
        existing_clips: list[Any],
        existing_narration: list[Any],
        subtitles: list[Any],
        cancel_check: Callable[[], bool] | None,
        overwrite: bool,
        timeout_seconds: int,
        max_output_bytes: int | None,
    ) -> AssemblyExecutionResult:
        started = time.monotonic()
        ffmpeg_bin = self._ffmpeg_path or resolve_ffmpeg_binary()
        if not ffmpeg_bin:
            avail = check_ffmpeg_availability()
            result.errors.append(
                build_failure_object(
                    CODE_FFMPEG_FAILED,
                    avail.error or "FFmpeg binary not available.",
                )
            )
            result.status = STATUS_FAILED
            return result

        output_dir = Path(plan.output_dir or "")
        output_dir.mkdir(parents=True, exist_ok=True)
        work_dir = output_dir / "_work"
        work_dir.mkdir(parents=True, exist_ok=True)

        final_path = output_dir / (plan.expected_output or EXPECTED_OUTPUT)
        if final_path.is_file() and not overwrite:
            result.errors.append(
                build_failure_object(CODE_OUTPUT_INVALID, f"Output already exists: {final_path.name}.")
            )
            result.status = STATUS_FAILED
            return result

        temp_final = work_dir / "export_temp.mp4"
        if temp_final.is_file():
            temp_final.unlink(missing_ok=True)

        preferred_sub = next(
            (s for s in subtitles if s.role == ROLE_SUBTITLE_ASS),
            next((s for s in subtitles if s.role == ROLE_SUBTITLE_SRT), None),
        )

        try:
            if cancel_check and cancel_check():
                result.status = STATUS_CANCELLED
                result.errors.append(
                    build_failure_object(CODE_CANCELLED, "Cancelled before FFmpeg execution.")
                )
                return result

            concat_path = work_dir / "concat_video.mp4"
            self._concat_clips(
                ffmpeg_bin,
                existing_clips,
                concat_path,
                timeout_seconds=timeout_seconds,
                cancel_check=cancel_check,
            )

            if cancel_check and cancel_check():
                result.status = STATUS_CANCELLED
                result.errors.append(
                    build_failure_object(CODE_CANCELLED, "Cancelled during assembly.")
                )
                return result

            with_audio = work_dir / "with_audio.mp4"
            self._merge_audio(
                ffmpeg_bin,
                concat_path,
                Path(existing_narration[0].file_path),
                with_audio,
                timeout_seconds=timeout_seconds,
                cancel_check=cancel_check,
            )

            if cancel_check and cancel_check():
                result.status = STATUS_CANCELLED
                result.errors.append(
                    build_failure_object(CODE_CANCELLED, "Cancelled during assembly.")
                )
                return result

            if plan.subtitle_mode == SUBTITLE_MODE_BURN_IN and preferred_sub is not None:
                self._burn_subtitles(
                    ffmpeg_bin,
                    with_audio,
                    Path(preferred_sub.file_path),
                    temp_final,
                    work_dir=work_dir,
                    timeout_seconds=timeout_seconds,
                    cancel_check=cancel_check,
                )
            else:
                temp_final.write_bytes(with_audio.read_bytes())
                if plan.subtitle_mode == SUBTITLE_MODE_SIDECAR:
                    result.warnings.append("sidecar subtitle mode not implemented in V1; video only")

            if not temp_final.is_file() or temp_final.stat().st_size <= 0:
                result.errors.append(
                    build_failure_object(CODE_OUTPUT_MISSING, "Assembly output file missing or empty.")
                )
                result.status = STATUS_FAILED
                return result

            size = temp_final.stat().st_size
            if max_output_bytes is not None and size > int(max_output_bytes):
                result.errors.append(
                    build_failure_object(
                        CODE_OUTPUT_INVALID,
                        f"Output size {size} exceeds cap {max_output_bytes}.",
                    )
                )
                result.status = STATUS_FAILED
                return result

            if final_path.is_file():
                if overwrite:
                    final_path.unlink()
                else:
                    result.errors.append(
                        build_failure_object(CODE_OUTPUT_INVALID, "Final output path collision.")
                    )
                    result.status = STATUS_FAILED
                    return result

            temp_final.replace(final_path)

            manifest_path = output_dir / MANIFEST_FILENAME
            manifest = self._build_manifest(
                plan,
                final_path=final_path,
                existing_clips=existing_clips,
                existing_narration=existing_narration,
                subtitles=subtitles,
                output_size=size,
                started_at=result.generated_at,
                completed_at=_now(),
            )
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

            result.status = STATUS_COMPLETED
            result.real_assembly_executed = True
            result.output_created = True
            result.output_file = str(final_path.resolve())
            result.output_size = size
            result.manifest_path = str(manifest_path.resolve())
            result.execution_time_seconds = round(time.monotonic() - started, 3)
            return result

        except _AssemblyTimeout as exc:
            result.errors.append(build_failure_object(CODE_TIMEOUT, str(exc)))
            result.status = STATUS_FAILED
            result.execution_time_seconds = round(time.monotonic() - started, 3)
            return result
        except _AssemblyCancelled as exc:
            result.status = STATUS_CANCELLED
            result.errors.append(build_failure_object(CODE_CANCELLED, str(exc)))
            result.execution_time_seconds = round(time.monotonic() - started, 3)
            return result
        except _AssemblyFFmpegError as exc:
            result.errors.append(build_failure_object(CODE_FFMPEG_FAILED, str(exc)))
            result.status = STATUS_FAILED
            result.execution_time_seconds = round(time.monotonic() - started, 3)
            return result

    def _run_ffmpeg(
        self,
        ffmpeg_bin: str,
        args: list[str],
        *,
        timeout_seconds: int,
        cancel_check: Callable[[], bool] | None,
        description: str,
    ) -> None:
        if cancel_check and cancel_check():
            raise _AssemblyCancelled("Cancelled before FFmpeg command.")
        cmd = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", *args]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise _AssemblyTimeout(f"{description} timed out after {timeout_seconds}s.") from exc

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            raise _AssemblyFFmpegError(f"{description} failed: {detail}")

    def _concat_clips(
        self,
        ffmpeg_bin: str,
        clips: list[Any],
        output_path: Path,
        *,
        timeout_seconds: int,
        cancel_check: Callable[[], bool] | None,
    ) -> None:
        if len(clips) == 1:
            self._run_ffmpeg(
                ffmpeg_bin,
                ["-i", clips[0].file_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(output_path)],
                timeout_seconds=timeout_seconds,
                cancel_check=cancel_check,
                description="single clip normalize",
            )
            return

        concat_list = output_path.parent / "concat_list.txt"
        lines = [f"file '{Path(c.file_path).as_posix()}'" for c in clips]
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._run_ffmpeg(
            ffmpeg_bin,
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(output_path),
            ],
            timeout_seconds=timeout_seconds,
            cancel_check=cancel_check,
            description="video concat",
        )

    def _merge_audio(
        self,
        ffmpeg_bin: str,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        *,
        timeout_seconds: int,
        cancel_check: Callable[[], bool] | None,
    ) -> None:
        self._run_ffmpeg(
            ffmpeg_bin,
            [
                "-i",
                str(video_path),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ],
            timeout_seconds=timeout_seconds,
            cancel_check=cancel_check,
            description="audio merge",
        )

    def _burn_subtitles(
        self,
        ffmpeg_bin: str,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
        *,
        work_dir: Path,
        timeout_seconds: int,
        cancel_check: Callable[[], bool] | None,
    ) -> None:
        local_sub = work_dir / subtitle_path.name
        if subtitle_path.resolve() != local_sub.resolve():
            local_sub.write_bytes(subtitle_path.read_bytes())

        sub_filter = f"subtitles={local_sub.name}"
        if cancel_check and cancel_check():
            raise _AssemblyCancelled("Cancelled before subtitle burn-in.")

        cmd = [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path.resolve()),
            "-vf",
            sub_filter,
            "-c:a",
            "copy",
            str(output_path.resolve()),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_seconds)),
                check=False,
                cwd=str(work_dir),
            )
        except subprocess.TimeoutExpired as exc:
            raise _AssemblyTimeout("subtitle burn-in timed out.") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            raise _AssemblyFFmpegError(f"subtitle burn-in failed: {detail}")

    def _build_manifest(
        self,
        plan: AssemblyPlan,
        *,
        final_path: Path,
        existing_clips: list[Any],
        existing_narration: list[Any],
        subtitles: list[Any],
        output_size: int,
        started_at: str,
        completed_at: str,
    ) -> dict[str, Any]:
        skeleton = AssemblyManifestSkeleton(
            session_id=plan.session_id,
            assembly_mode=plan.assembly_mode,
            subtitle_mode=plan.subtitle_mode,
            input_artifacts={
                "video": [c.file_path for c in existing_clips],
                "voice": [n.file_path for n in existing_narration],
                "subtitle": [s.file_path for s in subtitles if not s.is_manifest],
            },
            output_artifacts=[
                {
                    "variant": plan.output_variant or "primary",
                    "file_name": final_path.name,
                    "file_path": str(final_path.resolve()),
                    "size_bytes": output_size,
                }
            ],
            validation_status=VALIDATION_READY,
            warnings=list(plan.warnings),
            real_assembly_executed=True,
        )
        payload = skeleton.to_dict()
        payload["manifest_version"] = MANIFEST_VERSION
        payload["executor_version"] = EXECUTOR_VERSION
        payload["started_at"] = started_at
        payload["completed_at"] = completed_at
        payload["duration_seconds"] = None
        return payload

    def _plan_steps(
        self,
        plan: AssemblyPlan,
        clips: list[Any],
        narration: list[Any],
        subtitles: list[Any],
    ) -> list[dict[str, Any]]:
        output_path = str(Path(plan.output_dir or "") / (plan.expected_output or ""))
        steps: list[dict[str, Any]] = [
            {
                "step": 1,
                "name": "validate_inputs",
                "action": "verify video/voice/subtitle inputs and output directory",
                "detail": {
                    "video_clips": len(clips),
                    "narration_segments": len(narration),
                    "subtitle_tracks": len(subtitles),
                },
            },
            {
                "step": 2,
                "name": "video_concat",
                "action": "concatenate ordered clips (preserve plan order)",
                "detail": {"clips": [c.file_name for c in clips]},
            },
            {
                "step": 3,
                "name": "audio_merge",
                "action": "merge ordered narration segments",
                "detail": {"narration": [n.file_name for n in narration]},
            },
        ]

        if plan.subtitle_mode == SUBTITLE_MODE_NONE:
            steps.append(
                {
                    "step": 4,
                    "name": "subtitle_handling",
                    "action": "skip (subtitle_mode=none)",
                    "detail": {},
                }
            )
        else:
            preferred = next(
                (s for s in subtitles if s.role == ROLE_SUBTITLE_ASS),
                next((s for s in subtitles if s.role == ROLE_SUBTITLE_SRT), None),
            )
            steps.append(
                {
                    "step": 4,
                    "name": "subtitle_handling",
                    "action": (
                        "burn_in (ASS preferred, SRT fallback)"
                        if plan.subtitle_mode == SUBTITLE_MODE_BURN_IN
                        else "sidecar mux (reserved)"
                    ),
                    "detail": {
                        "subtitle_mode": plan.subtitle_mode,
                        "source": preferred.file_name if preferred is not None else None,
                    },
                }
            )

        steps.append(
            {
                "step": 5,
                "name": "export",
                "action": "export final video (atomic temp -> replace)",
                "detail": {"expected_output": plan.expected_output, "output_path": output_path},
            }
        )
        steps.append(
            {
                "step": 6,
                "name": "output_validation",
                "action": "verify file exists, non-zero size, duration > 0",
                "detail": {},
            }
        )
        return steps


class _AssemblyFFmpegError(Exception):
    pass


class _AssemblyTimeout(Exception):
    pass


class _AssemblyCancelled(Exception):
    pass


__all__ = [
    "EXECUTOR_VERSION",
    "MANIFEST_FILENAME",
    "STATUS_DRY_RUN",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_CANCELLED",
    "AssemblyExecutionResult",
    "AssemblyFFmpegExecutor",
]
