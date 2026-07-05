"""pwmap Runway Agent — external execution adapter for ModirAgentOS Product Studio."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ADAPTER_VERSION = "pwmap_runway_agent_adapter_v1"
LEGACY_INTERNAL_RUNTIME = "legacy_internal"
PWMAP_AGENT_RUNTIME = "pwmap_agent"
MODIR_ROOT = Path(__file__).resolve().parents[2]
VENDORED_PWMAP_ROOT = MODIR_ROOT / "external" / "pwmap"
DESKTOP_PWMAP_ROOT = Path(r"C:\Users\kaman\Desktop\pwmap")
OUTPUT_ROOT_NAME = "pwmap_agent_runs"
MIN_REAL_MP4_BYTES = 1_000_000
KLING_CINEMATIC_MIN_CHARS = 2400
KLING_CINEMATIC_MAX_CHARS = 2500

YOUTUBE_TOPIC_KEYWORDS = ("animal", "dog", "cat", "funny", "fail")
INSTAGRAM_TOPIC_KEYWORDS = ("skincare", "beauty", "routine", "glow")

STORY_BRIEF_MARKERS = ("Character:", "Clip 1:", "Visual hook:", "Conflict:", "Setting:")


def _is_story_brief_prompt(text: str) -> bool:
    """Detect planning-document prose that must not be sent to Kling."""
    if not text:
        return False
    hits = sum(1 for marker in STORY_BRIEF_MARKERS if marker in text)
    return hits >= 2


def _contains_topic_keyword(text: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(keyword)}\b", str(text or ""), flags=re.IGNORECASE) is not None


def validate_platform_prompt_isolation(platform: str, text: str) -> tuple[bool, str]:
    """Reject prompts that contain keywords from another platform's topic lane."""
    platform_key = str(platform or "").strip().lower()
    if platform_key in {"youtube_shorts", "youtube"}:
        if any(_contains_topic_keyword(text, keyword) for keyword in INSTAGRAM_TOPIC_KEYWORDS):
            return False, "instagram_keywords_in_youtube_prompt"
    if platform_key in {"instagram_reels", "instagram"}:
        if any(_contains_topic_keyword(text, keyword) for keyword in YOUTUBE_TOPIC_KEYWORDS):
            return False, "youtube_keywords_in_instagram_prompt"
    return True, ""


def _clip_prompts_from_frame_plan(preflight: dict[str, Any]) -> list[str]:
    frame_plan = preflight.get("kling_frame_to_video_plan") or preflight.get("kling_frame_plan") or {}
    clips = frame_plan.get("clips") if isinstance(frame_plan, dict) else None
    prompts: list[str] = []
    if isinstance(clips, list):
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            text = str(clip.get("prompt") or "").strip()
            if text:
                prompts.append(text)
    return prompts


def ensure_kling_cinematic_preflight(
    *,
    project_root: str | Path,
    payload: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    """Ensure preflight contains full cinematic Kling clip prompts (2400+ chars each)."""
    import logging

    logger = logging.getLogger(__name__)
    prompts = _clip_prompts_from_frame_plan(preflight)
    needs_rebuild = not prompts
    if not needs_rebuild:
        for index, prompt in enumerate(prompts, start=1):
            if len(prompt) < KLING_CINEMATIC_MIN_CHARS or _is_story_brief_prompt(prompt):
                logger.error(
                    "Prompt too short: %s chars (clip %s) — running full preflight",
                    len(prompt),
                    index,
                )
                needs_rebuild = True
                break

    if not needs_rebuild:
        return preflight

    logger.error(
        "kling_frame_to_video_plan missing or incomplete (%s clip prompts) — running full preflight",
        len(prompts),
    )
    from ui.api.product_studio_service import ProductStudioService

    full_payload = {
        **payload,
        "execute_preflight": True,
        "browser_automation": True,
        "provider_runtime": PWMAP_AGENT_RUNTIME,
        "automation_mode": bool(payload.get("automation_mode", True)),
    }
    full_payload.setdefault("provider", "kling")
    service = ProductStudioService(project_root)
    refreshed = service.create_video_preflight(full_payload)
    refreshed_prompts = _clip_prompts_from_frame_plan(refreshed)
    for index, prompt in enumerate(refreshed_prompts, start=1):
        if len(prompt) < KLING_CINEMATIC_MIN_CHARS:
            logger.error(
                "Prompt too short after preflight: %s chars (clip %s)",
                len(prompt),
                index,
            )
            raise PwmapAdapterError(
                f"Kling cinematic prompt clip {index} is {len(prompt)} chars; "
                f"minimum is {KLING_CINEMATIC_MIN_CHARS}."
            )
    if not refreshed_prompts:
        raise PwmapAdapterError(
            "Full preflight did not produce kling_frame_to_video_plan clip prompts."
        )
    return refreshed


def resolve_default_pwmap_root() -> Path:
    """Resolve pwmap runtime root: env override, project vendored copy, then Desktop fallback."""
    env = os.environ.get("MODIR_PWMAP_ROOT", "").strip()
    if env:
        return Path(env)
    project = os.environ.get("MODIR_PROJECT_ROOT", "").strip()
    if project:
        vendored = Path(project).resolve() / "external" / "pwmap"
        if vendored.is_dir() and (vendored / "runway_agent.py").is_file():
            return vendored
    if VENDORED_PWMAP_ROOT.is_dir() and (VENDORED_PWMAP_ROOT / "runway_agent.py").is_file():
        return VENDORED_PWMAP_ROOT
    if DESKTOP_PWMAP_ROOT.is_dir() and (DESKTOP_PWMAP_ROOT / "runway_agent.py").is_file():
        return DESKTOP_PWMAP_ROOT
    return VENDORED_PWMAP_ROOT


DEFAULT_PWMAP_ROOT = resolve_default_pwmap_root()

RUNWAY_SESSION_MISSING_MESSAGE = (
    "❌ Runway browser not connected. Click 'Connect Runway Browser' first."
)
RUNWAY_SESSION_EXPIRED_MESSAGE = (
    "⚠️ Runway session expired. Click 'Connect Runway Browser' to reconnect."
)


class PwmapAdapterError(Exception):
    pass


@dataclass
class PwmapAgentRunResult:
    ok: bool
    run_id: str
    status: str = "failed"
    provider_runtime: str = PWMAP_AGENT_RUNTIME
    execution_engine: str = "pwmap/runway_agent.py"
    video_path: str = ""
    download_path: str = ""
    clip_count: int = 0
    clips: list[dict[str, Any]] = field(default_factory=list)
    output_folder: str = ""
    run_dir: str = ""
    job_path: str = ""
    last_result_path: str = ""
    normalized_result_path: str = ""
    pwmap_root: str = ""
    subprocess_command: list[str] = field(default_factory=list)
    subprocess_exit_code: int = -1
    errors: list[str] = field(default_factory=list)
    message: str = ""
    preflight_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": ADAPTER_VERSION,
            "ok": self.ok,
            "run_id": self.run_id,
            "status": self.status,
            "provider_runtime": self.provider_runtime,
            "execution_engine": self.execution_engine,
            "video_path": self.video_path,
            "download_path": self.download_path,
            "clip_count": self.clip_count,
            "clips": list(self.clips),
            "output_folder": self.output_folder,
            "run_dir": self.run_dir,
            "job_path": self.job_path,
            "last_result_path": self.last_result_path,
            "normalized_result_path": self.normalized_result_path,
            "pwmap_root": self.pwmap_root,
            "subprocess_command": list(self.subprocess_command),
            "subprocess_exit_code": self.subprocess_exit_code,
            "errors": list(self.errors),
            "message": self.message,
            "preflight_snapshot": dict(self.preflight_snapshot),
            "legacy_internal_runtime_available": True,
            "legacy_note": "Internal Kling/Runway live engines retained for diagnostics only.",
        }


def _message_for_subprocess_exit(exit_code: int, stderr: str = "") -> str:
    detail = str(stderr or "").strip()
    if int(exit_code) == 2:
        lowered = detail.lower()
        if "unrecognized arguments" in lowered or "usage:" in lowered:
            return (
                "pwmap agent CLI error (exit code 2): outdated pwmap copy or invalid arguments. "
                "Use the vendored agent at external/pwmap/runway_agent.py."
            )
        if any(token in lowered for token in ("session", "login", "expired", "connect runway")):
            if "expired" in lowered or "login" in lowered:
                return RUNWAY_SESSION_EXPIRED_MESSAGE
            return RUNWAY_SESSION_MISSING_MESSAGE
        return RUNWAY_SESSION_MISSING_MESSAGE
    if int(exit_code) == 1:
        return "pwmap agent failed with exit code 1 (runtime error — generation or browser launch failed)."
    if int(exit_code) == 0:
        return "pwmap agent completed successfully."
    return f"pwmap agent failed with exit code {exit_code}"


def _apply_runway_session_gate(
    result: PwmapAgentRunResult,
    *,
    project_root: str | Path,
) -> bool:
    """Return True when generation may proceed."""
    from content_brain.automation.runway_session_manager import require_runway_session_for_generation

    check = require_runway_session_for_generation(project_root, validate=True)
    if check.get("ok"):
        return True
    result.status = "runway_session_required"
    result.subprocess_exit_code = int(check.get("exit_code") or 2)
    result.message = str(check.get("message") or RUNWAY_SESSION_MISSING_MESSAGE)
    result.errors.append(str(check.get("reason") or "runway_session_required"))
    return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_pwmap_agent_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"pwmap_{stamp}_{uuid.uuid4().hex[:8]}"


def resolve_pwmap_root(pwmap_root: str | Path | None = None) -> Path:
    root = Path(pwmap_root or DEFAULT_PWMAP_ROOT).resolve()
    if not root.is_dir():
        raise PwmapAdapterError(
            f"pwmap root not found: {root}. Set MODIR_PWMAP_ROOT, use vendored "
            f"{VENDORED_PWMAP_ROOT}, or install pwmap at {DESKTOP_PWMAP_ROOT}."
        )
    agent_script = root / "runway_agent.py"
    if not agent_script.is_file():
        raise PwmapAdapterError(f"pwmap runway_agent.py not found: {agent_script}")
    return root


def pwmap_run_dir(project_root: str | Path, run_id: str) -> Path:
    path = Path(project_root).resolve() / "outputs" / OUTPUT_ROOT_NAME / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_pwmap_job(
    *,
    prompt: str = "",
    prompts: list[str] | None = None,
    model: str = "Kling 3.0 Pro",
    duration: int = 15,
    aspect: str = "9:16",
    native_audio: bool = True,
    use_frame_second: int | None = None,
) -> dict[str, Any]:
    job: dict[str, Any] = {
        "model": model,
        "duration": int(duration),
        "aspect": aspect,
        "native_audio": bool(native_audio),
    }
    if prompts:
        cleaned = [str(p).strip() for p in prompts if str(p).strip()]
        if not cleaned:
            raise PwmapAdapterError("prompts list is empty.")
        job["prompts"] = cleaned
    else:
        text = str(prompt or "").strip()
        if not text:
            raise PwmapAdapterError("prompt is required when prompts list is not provided.")
        job["prompt"] = text
    if use_frame_second is not None:
        job["use_frame_second"] = int(use_frame_second)
    return job


def extract_prompts_from_preflight(preflight: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    import logging

    logger = logging.getLogger(__name__)
    platform = str(preflight.get("platform") or "")
    prompts = _clip_prompts_from_frame_plan(preflight)
    source = "kling_frame_to_video_plan"
    if not prompts:
        for item in preflight.get("kling_clip_prompts") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("prompt") or "").strip()
            if text:
                prompts.append(text)
        source = "kling_clip_prompts"
    if not prompts:
        native = preflight.get("kling_native_audio_plan") or {}
        if isinstance(native, dict):
            for clip in native.get("clips") or []:
                if not isinstance(clip, dict):
                    continue
                for shot_key in ("shot_1", "shot_2"):
                    shot = clip.get(shot_key) or {}
                    if isinstance(shot, dict):
                        text = str(shot.get("prompt") or "").strip()
                        if text:
                            prompts.append(text)
        source = "kling_native_audio_plan"
    if not prompts:
        raise PwmapAdapterError(
            "No cinematic prompts in kling_frame_to_video_plan — full preflight required."
        )
    for index, prompt in enumerate(prompts, start=1):
        if len(prompt) < KLING_CINEMATIC_MIN_CHARS or _is_story_brief_prompt(prompt):
            logger.error(
                "Prompt too short: %s chars (clip %s from %s) — not cinematic prose",
                len(prompt),
                index,
                source,
            )
            raise PwmapAdapterError(
                f"Clip {index} prompt is {len(prompt)} chars; "
                f"cinematic minimum is {KLING_CINEMATIC_MIN_CHARS}."
            )
        ok, reason = validate_platform_prompt_isolation(platform, prompt)
        if not ok:
            logger.error("Platform topic contamination in clip %s: %s", index, reason)
            raise PwmapAdapterError(f"Platform topic contamination: {reason}")
    visual_style = str(
        preflight.get("visual_style")
        or preflight.get("style")
        or "cinematic realistic"
    ).strip()
    from content_brain.execution.runway_prompt_composer import apply_visual_style_to_clip_prompts

    prompts = apply_visual_style_to_clip_prompts(prompts, visual_style)
    duration_plan = dict(preflight.get("duration_plan") or {})
    kling_duration = dict(preflight.get("kling_duration_plan") or {})
    duration = int(
        duration_plan.get("clip_duration_seconds")
        or kling_duration.get("clip_duration_seconds")
        or 15
    )
    aspect = str(preflight.get("aspect_ratio") or "9:16")
    use_frame_second = duration if len(prompts) > 1 else None
    meta = {
        "duration": duration,
        "aspect": aspect,
        "clip_count": len(prompts),
        "use_frame_second": use_frame_second,
        "prompt_source": source,
        "prompt_lengths": [len(item) for item in prompts],
    }
    return prompts, meta


def build_pwmap_job_from_preflight(
    preflight: dict[str, Any],
    *,
    native_audio: bool = True,
    project_root: str | Path | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    working_preflight = dict(preflight)
    if project_root is not None and payload is not None:
        working_preflight = ensure_kling_cinematic_preflight(
            project_root=project_root,
            payload=payload,
            preflight=working_preflight,
        )
    prompts, meta = extract_prompts_from_preflight(working_preflight)
    if len(prompts) == 1:
        return build_pwmap_job(
            prompt=prompts[0],
            duration=meta["duration"],
            aspect=meta["aspect"],
            native_audio=native_audio,
        )
    return build_pwmap_job(
        prompts=prompts,
        duration=meta["duration"],
        aspect=meta["aspect"],
        native_audio=native_audio,
        use_frame_second=meta.get("use_frame_second"),
    )


def build_subprocess_command(
    *,
    pwmap_root: Path,
    job_path: Path,
    project_root: str | Path | None = None,
    use_powershell: bool = False,
    close_browser: bool = True,
    clip_timeout_seconds: int = 900,
) -> list[str]:
    if use_powershell:
        ps1 = pwmap_root / "n8n_run.ps1"
        if not ps1.is_file():
            raise PwmapAdapterError(f"n8n_run.ps1 not found: {ps1}")
        return [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
        ]
    command = [
        os.environ.get("PYTHON", "python"),
        str(pwmap_root / "runway_agent.py"),
        "--job",
        str(job_path),
        "--timeout",
        str(max(60, int(clip_timeout_seconds))),
        "--project-root",
        str(Path(project_root or Path.cwd()).resolve()),
    ]
    if close_browser:
        command.append("--close-browser")
    return command


def validate_mp4_path(path: str | Path, *, min_bytes: int = MIN_REAL_MP4_BYTES) -> dict[str, Any]:
    target = Path(path)
    result = {
        "path": str(target),
        "exists": target.is_file(),
        "size_bytes": 0,
        "valid": False,
    }
    if not target.is_file():
        return result
    size = target.stat().st_size
    result["size_bytes"] = size
    result["valid"] = size >= min_bytes
    return result


def parse_last_result(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise PwmapAdapterError(f"last_result.json not found: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PwmapAdapterError("last_result.json must be a JSON object.")
    return payload


def copy_mp4_outputs(
    *,
    last_result: dict[str, Any],
    run_dir: Path,
) -> tuple[list[dict[str, Any]], str]:
    copied: list[dict[str, Any]] = []
    final_video = ""
    clips = last_result.get("clips") or []
    if not isinstance(clips, list):
        clips = []
    for index, clip in enumerate(clips, start=1):
        if not isinstance(clip, dict):
            continue
        src_text = str(clip.get("download") or "").strip()
        if not src_text:
            continue
        src = Path(src_text)
        verify = validate_mp4_path(src)
        if not verify["valid"]:
            raise PwmapAdapterError(f"Invalid MP4 for clip {index}: {src}")
        dest = run_dir / f"clip_{index}.mp4"
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        canonical = run_dir / "video.mp4" if index == len(clips) else None
        item = {
            "clip": int(clip.get("clip") or index),
            "source_path": str(src.resolve()).replace("\\", "/"),
            "modir_path": str(dest.resolve()).replace("\\", "/"),
            "size_bytes": verify["size_bytes"],
            "used_frame_from_previous": bool(clip.get("used_frame_from_previous")),
        }
        copied.append(item)
        final_video = str(dest.resolve()).replace("\\", "/")
    if len(copied) == 1:
        single = run_dir / "video.mp4"
        src = Path(copied[0]["modir_path"])
        if src.resolve() != single.resolve():
            shutil.copy2(src, single)
        final_video = str(single.resolve()).replace("\\", "/")
    elif len(copied) > 1:
        last = run_dir / f"clip_{len(copied)}.mp4"
        merged = run_dir / "video.mp4"
        if last.is_file() and last.resolve() != merged.resolve():
            shutil.copy2(last, merged)
        final_video = str(merged.resolve()).replace("\\", "/")
    return copied, final_video


def _finalize_partial_or_failure(
    *,
    project_root: str | Path,
    root: Path,
    run_dir: Path,
    run_id: str,
    result: PwmapAgentRunResult,
    job: dict[str, Any],
    preflight: dict[str, Any] | None,
    subprocess_stdout: str,
    close_browser: bool,
    clip_timeout_seconds: int,
) -> None:
    from content_brain.execution.pwmap_finalization import finalize_partial_pwmap_run

    normalized = result.to_dict()
    normalized["job"] = job
    normalized["clip_timeout_seconds"] = clip_timeout_seconds
    finalized = finalize_partial_pwmap_run(
        project_root=project_root,
        run_dir=run_dir,
        run_id=run_id,
        pwmap_root=root,
        adapter_payload=normalized,
        preflight=preflight,
        subprocess_stdout=subprocess_stdout,
        close_browser_requested=close_browser,
        clip_timeout_seconds=clip_timeout_seconds,
    )
    result.clips = list(finalized.get("clips") or [])
    result.clip_count = int(finalized.get("clip_count") or len(result.clips))
    result.video_path = str(finalized.get("video_path") or "")
    result.download_path = str(finalized.get("download_path") or result.video_path)
    result.status = str(finalized.get("status") or "failed")
    result.ok = bool(finalized.get("ok"))
    result.message = (
        "pwmap agent partial — clips preserved; recovery available."
        if result.status == "partial_failed"
        else result.message
    )
    result.normalized_result_path = str((run_dir / "normalized_result.json").resolve()).replace("\\", "/")
    if result.status == "failed" and not result.clips:
        _write_failure_artifacts(run_dir, result)


def run_pwmap_agent(
    *,
    project_root: str | Path,
    job: dict[str, Any],
    run_id: str | None = None,
    pwmap_root: str | Path | None = None,
    use_powershell: bool = False,
    timeout_seconds: int = 3600,
    dry_run: bool = False,
    preflight: dict[str, Any] | None = None,
) -> PwmapAgentRunResult:
    root = resolve_pwmap_root(pwmap_root)
    run_id = run_id or create_pwmap_agent_run_id()
    run_dir = pwmap_run_dir(project_root, run_id)
    job_path = run_dir / "job.json"
    job_path.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")

    pwmap_job_path = root / "agent_inbox" / "job.json"
    pwmap_job_path.parent.mkdir(parents=True, exist_ok=True)
    pwmap_job_path.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")

    from content_brain.execution.pwmap_timeout_policy import (
        clip_count_from_job,
        resolve_clip_timeout_seconds,
    )

    planned_clip_count = clip_count_from_job(job)
    clip_timeout_seconds = resolve_clip_timeout_seconds(planned_clip_count)
    close_browser = not bool(dry_run)
    command = build_subprocess_command(
        pwmap_root=root,
        job_path=pwmap_job_path,
        project_root=project_root,
        use_powershell=use_powershell,
        close_browser=close_browser,
        clip_timeout_seconds=clip_timeout_seconds,
    )
    result = PwmapAgentRunResult(
        ok=False,
        run_id=run_id,
        output_folder=str(run_dir.resolve()).replace("\\", "/"),
        run_dir=str(run_dir.resolve()).replace("\\", "/"),
        job_path=str(job_path.resolve()).replace("\\", "/"),
        pwmap_root=str(root.resolve()).replace("\\", "/"),
        subprocess_command=command,
        preflight_snapshot=dict(preflight or {}),
    )
    result.subprocess_command = command

    if not _apply_runway_session_gate(result, project_root=project_root):
        _write_failure_artifacts(run_dir, result)
        return result

    if dry_run:
        result.status = "dry_run"
        result.message = "Dry run — job.json written, subprocess not executed."
        result.ok = True
        from content_brain.execution.credit_safety_guard import (
            attach_credit_safety_to_report,
            evaluate_credit_safety,
        )

        credit_decision = evaluate_credit_safety(
            payload={"dry_run": True, **dict(preflight or {})},
            preflight=preflight,
            model=str(job.get("model") or ""),
            dry_run=True,
            clip_count=planned_clip_count,
        )
        normalized = attach_credit_safety_to_report(result.to_dict(), credit_decision)
        normalized["job"] = job
        (run_dir / "normalized_result.json").write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        result.normalized_result_path = str((run_dir / "normalized_result.json").resolve()).replace("\\", "/")
        return result

    from content_brain.execution.credit_safety_guard import (
        assert_credit_safe_for_live_run,
        attach_credit_safety_to_report,
    )

    credit_payload = dict(preflight or {})
    credit_payload.update(
        {
            "dry_run": False,
            "model": job.get("model"),
            "clip_count": planned_clip_count,
            "operator_paid_approval": credit_payload.get("operator_paid_approval"),
            "free_credit_mode": credit_payload.get("free_credit_mode"),
            "credit_mode": credit_payload.get("credit_mode"),
            "confirm_credit_spend": credit_payload.get("confirm_credit_spend"),
            "approved_by": credit_payload.get("approved_by"),
        }
    )
    credit_decision = assert_credit_safe_for_live_run(
        payload=credit_payload,
        preflight=preflight,
        provider="runway",
        model=str(job.get("model") or ""),
        clip_count=planned_clip_count,
    )
    if credit_decision.blocked:
        result.status = "paid_credit_blocked"
        result.message = credit_decision.block_reason
        result.errors.append("paid_credit_blocked")
        blocked = attach_credit_safety_to_report(result.to_dict(), credit_decision)
        blocked["job"] = job
        (run_dir / "normalized_result.json").write_text(json.dumps(blocked, indent=2), encoding="utf-8")
        (run_dir / "credit_safety_report.json").write_text(
            json.dumps(credit_decision.to_report(), indent=2), encoding="utf-8"
        )
        result.normalized_result_path = str((run_dir / "normalized_result.json").resolve()).replace("\\", "/")
        return result

    try:
        env = os.environ.copy()
        env["MODIR_PROJECT_ROOT"] = str(Path(project_root).resolve())
        env.setdefault("PYTHONIOENCODING", "utf-8")
        completed = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=max(60, int(timeout_seconds)),
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        result.errors.append(f"subprocess_timeout:{exc}")
        result.message = "pwmap agent subprocess timed out."
        stdout_text = str(exc.stdout or "")
        if stdout_text:
            (run_dir / "subprocess_stdout.log").write_text(stdout_text, encoding="utf-8")
        elif (run_dir / "subprocess_stdout.log").is_file():
            stdout_text = (run_dir / "subprocess_stdout.log").read_text(encoding="utf-8")
        _finalize_partial_or_failure(
            project_root=project_root,
            root=root,
            run_dir=run_dir,
            run_id=run_id,
            result=result,
            job=job,
            preflight=preflight,
            subprocess_stdout=stdout_text,
            close_browser=close_browser,
            clip_timeout_seconds=clip_timeout_seconds,
        )
        return result
    except OSError as exc:
        result.errors.append(str(exc))
        result.message = f"Failed to launch pwmap agent: {exc}"
        _write_failure_artifacts(run_dir, result)
        return result

    result.subprocess_exit_code = int(completed.returncode)
    if completed.stdout:
        (run_dir / "subprocess_stdout.log").write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        (run_dir / "subprocess_stderr.log").write_text(completed.stderr, encoding="utf-8")

    if completed.returncode != 0:
        stderr_text = completed.stderr or ""
        result.errors.append(f"pwmap_exit_code:{completed.returncode}")
        result.message = _message_for_subprocess_exit(completed.returncode, stderr_text)
        subprocess_stdout = completed.stdout or ""
        if (run_dir / "subprocess_stdout.log").is_file():
            subprocess_stdout = (run_dir / "subprocess_stdout.log").read_text(encoding="utf-8")
        _finalize_partial_or_failure(
            project_root=project_root,
            root=root,
            run_dir=run_dir,
            run_id=run_id,
            result=result,
            job=job,
            preflight=preflight,
            subprocess_stdout=subprocess_stdout,
            close_browser=close_browser,
            clip_timeout_seconds=clip_timeout_seconds,
        )
        return result

    last_result_path = root / "runway_downloads" / "last_result.json"
    result.last_result_path = str(last_result_path.resolve()).replace("\\", "/")
    try:
        last_result = parse_last_result(last_result_path)
    except PwmapAdapterError as exc:
        result.errors.append(str(exc))
        result.message = str(exc)
        _write_failure_artifacts(run_dir, result)
        return result

    shutil.copy2(last_result_path, run_dir / "last_result.json")
    copied, final_video = copy_mp4_outputs(last_result=last_result, run_dir=run_dir)
    result.clips = copied
    result.clip_count = len(copied)
    result.video_path = final_video
    result.download_path = final_video
    result.subprocess_exit_code = int(completed.returncode)

    from content_brain.execution.pwmap_finalization import finalize_pwmap_run

    subprocess_stdout = completed.stdout or ""
    if (run_dir / "subprocess_stdout.log").is_file():
        subprocess_stdout = (run_dir / "subprocess_stdout.log").read_text(encoding="utf-8")

    normalized = result.to_dict()
    normalized["job"] = job
    normalized["last_result"] = last_result
    finalized = finalize_pwmap_run(
        project_root=project_root,
        run_dir=run_dir,
        run_id=run_id,
        last_result=last_result,
        copied_clips=copied,
        adapter_payload=normalized,
        preflight=preflight,
        subprocess_stdout=subprocess_stdout,
        close_browser_requested=close_browser,
    )
    result.clips = list(finalized.get("clips") or copied)
    result.clip_count = int(finalized.get("clip_count") or len(copied))
    result.video_path = str(finalized.get("video_path") or final_video)
    result.download_path = str(finalized.get("download_path") or result.video_path)
    result.status = str(finalized.get("status") or ("completed" if result.video_path else "download_failed"))
    result.ok = bool(finalized.get("ok"))
    result.message = (
        "pwmap agent completed."
        if result.ok and result.status == "completed"
        else ("pwmap agent partial — clips preserved; recovery available." if result.status == "partial" else "pwmap agent finished without valid MP4.")
    )
    result.normalized_result_path = str((run_dir / "normalized_result.json").resolve()).replace("\\", "/")
    return result


def _write_failure_artifacts(run_dir: Path, result: PwmapAgentRunResult) -> None:
    payload = result.to_dict()
    payload["finished_at"] = _now_iso()
    (run_dir / "normalized_result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result.normalized_result_path = str((run_dir / "normalized_result.json").resolve()).replace("\\", "/")
    result.status = "failed"


def load_pwmap_agent_run_results(project_root: str | Path, *, run_id: str = "") -> dict[str, Any] | None:
    from content_brain.execution.pwmap_finalization import (
        build_pwmap_results_payload,
        load_latest_product_studio_pwmap_results,
    )

    root = Path(project_root).resolve()
    run_id_text = str(run_id or "").strip()
    if not run_id_text:
        latest_product = load_latest_product_studio_pwmap_results(root)
        if latest_product:
            return latest_product

    if run_id_text:
        run_dir = pwmap_run_dir(root, run_id_text)
        if not (run_dir / "normalized_result.json").is_file():
            return None
    else:
        base = root / "outputs" / OUTPUT_ROOT_NAME
        if not base.is_dir():
            return None
        candidates = sorted(
            [p for p in base.iterdir() if p.is_dir()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        run_dir = candidates[0]
        run_id_text = run_dir.name

    normalized_path = run_dir / "normalized_result.json"
    if not normalized_path.is_file():
        return None
    payload = json.loads(normalized_path.read_text(encoding="utf-8"))
    return build_pwmap_results_payload(run_dir, payload)


def _merge_credit_payload_fields(
    preflight: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Carry operator credit flags from generate payload into pwmap preflight snapshot."""
    merged = dict(preflight)
    for key in (
        "free_credit_mode",
        "use_free_credits",
        "operator_paid_approval",
        "confirm_credit_spend",
        "approved_by",
        "credit_mode",
        "free_credit_first",
        "live_retest",
        "phase",
        "browser_automation",
        "skip_credit_guard",
        "provider_runtime",
    ):
        if payload.get(key) not in (None, ""):
            merged[key] = payload[key]
    return merged


def run_pwmap_product_studio_generate(
    *,
    project_root: str | Path,
    payload: dict[str, Any],
    preflight: dict[str, Any],
    pwmap_root: str | Path | None = None,
) -> dict[str, Any]:
    """Product Studio entrypoint — replaces legacy internal Kling execution for product generation."""
    run_id = str(payload.get("run_id") or create_pwmap_agent_run_id())
    native_audio = bool(payload.get("native_audio", True))
    try:
        job = build_pwmap_job_from_preflight(
            preflight,
            native_audio=native_audio,
            project_root=project_root,
            payload=payload,
        )
    except PwmapAdapterError as exc:
        return {
            "ok": False,
            "wired": True,
            "status": "failed",
            "provider_runtime": PWMAP_AGENT_RUNTIME,
            "message": str(exc),
            "run_id": run_id,
            "legacy_internal_runtime": LEGACY_INTERNAL_RUNTIME,
        }

    from content_brain.execution.pwmap_timeout_policy import (
        clip_count_from_job,
        resolve_subprocess_timeout_seconds,
    )

    planned_clips = int(
        preflight.get("kling_clip_count")
        or (preflight.get("multiclip_execution_plan") or {}).get("clip_count")
        or clip_count_from_job(job)
    )
    from content_brain.execution.credit_safety_guard import (
        assert_credit_safe_for_live_run,
        attach_credit_safety_to_report,
        blocked_live_response,
    )

    duration_seconds = int(
        (preflight.get("duration_plan") or {}).get("requested_duration_seconds")
        or (preflight.get("duration_plan") or {}).get("duration_seconds")
        or payload.get("duration_seconds")
        or 30
    )
    live_retest = bool(payload.get("live_retest") or payload.get("phase") == "PWMAP-30S-TWO-CLIP-LIVE-RETEST")
    credit_decision = None
    if not bool(payload.get("dry_run")):
        credit_decision = assert_credit_safe_for_live_run(
            payload=payload,
            preflight=preflight,
            provider="runway",
            model=str(job.get("model") or ""),
            clip_count=planned_clips,
            duration_seconds=duration_seconds,
            live_retest=live_retest or duration_seconds == 30,
        )
        if credit_decision.blocked:
            return blocked_live_response(
                decision=credit_decision,
                run_id=run_id,
                provider_runtime=PWMAP_AGENT_RUNTIME,
                legacy_internal_runtime=LEGACY_INTERNAL_RUNTIME,
            )

    adapter_result = run_pwmap_agent(
        project_root=project_root,
        job=job,
        run_id=run_id,
        pwmap_root=pwmap_root,
        preflight=_merge_credit_payload_fields(preflight, payload),
        timeout_seconds=int(
            payload.get("pwmap_timeout_seconds")
            or resolve_subprocess_timeout_seconds(planned_clips)
        ),
        dry_run=bool(payload.get("dry_run")),
    )
    response = adapter_result.to_dict()
    if credit_decision is not None:
        response = attach_credit_safety_to_report(response, credit_decision)
    elif bool(payload.get("dry_run")):
        from content_brain.execution.credit_safety_guard import evaluate_credit_safety

        dry_decision = evaluate_credit_safety(payload=payload, preflight=preflight, dry_run=True)
        response = attach_credit_safety_to_report(response, dry_decision)
    response.update(
        {
            "wired": True,
            "session_id": run_id,
            "project_id": run_id,
            "authoritative_topic": str(preflight.get("authoritative_topic") or ""),
            "clip_count": adapter_result.clip_count or int(preflight.get("kling_clip_count") or 1),
            "kling_clip_count": adapter_result.clip_count or int(preflight.get("kling_clip_count") or 1),
            "duration_plan": preflight.get("duration_plan") or {},
            "pipeline_steps": preflight.get("pipeline_steps") or [],
            "output_folder": adapter_result.output_folder,
            "native_audio_required": True,
            "use_elevenlabs": False,
            "preflight_mode": "executed_via_pwmap_agent",
            "legacy_internal_runtime": LEGACY_INTERNAL_RUNTIME,
            "legacy_note": "Internal Kling live engines retained for diagnostics; not used for this run.",
        }
    )
    return response


def resolve_product_provider_runtime(payload: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    profile = profile or {}
    explicit = str(payload.get("provider_runtime") or profile.get("provider_runtime") or "").strip().lower()
    if explicit:
        return explicit
    env_default = str(os.environ.get("MODIR_PROVIDER_RUNTIME") or "").strip().lower()
    if env_default:
        return env_default
    return PWMAP_AGENT_RUNTIME


__all__ = [
    "ADAPTER_VERSION",
    "LEGACY_INTERNAL_RUNTIME",
    "PWMAP_AGENT_RUNTIME",
    "PwmapAdapterError",
    "PwmapAgentRunResult",
    "build_pwmap_job",
    "build_pwmap_job_from_preflight",
    "build_subprocess_command",
    "copy_mp4_outputs",
    "create_pwmap_agent_run_id",
    "extract_prompts_from_preflight",
    "load_pwmap_agent_run_results",
    "parse_last_result",
    "pwmap_run_dir",
    "resolve_product_provider_runtime",
    "resolve_pwmap_root",
    "run_pwmap_agent",
    "run_pwmap_product_studio_generate",
    "validate_mp4_path",
]
