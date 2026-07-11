"""Continuity Director V1 — last-frame extract + PNG upload chain (no Use Frame)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from content_brain.execution.kling_frame_to_video_models import (
    FIRST_FRAME_PRIOR_CLIP,
    FIRST_FRAME_PROMPT_ONLY,
)
from content_brain.execution.kling_last_frame_extractor import (
    continuity_dir,
    continuity_frame_path,
    extract_and_save_continuity_frame,
    validate_frame,
)
from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4
from content_brain.execution.kling_starter_frame_generator import (
    STARTER_FRAME_PROMPT_JSON,
    build_kling_starter_image_prompt,
    kling_frame_clip_dir,
    kling_frame_run_dir,
    prompt_matches_topic,
    starter_frame_dir,
)

AGENT_VERSION = "continuity_director_v1"
CONTINUITY_METHOD_LAST_FRAME = "last_frame_extract_upload"
CHAIN_FILENAME = "continuity_director_chain.json"

STATUS_PLANNED = "planned"
STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"
STATUS_COMPLETE = "complete"

STOP_MP4_MISSING = "mp4_missing_or_invalid"
STOP_GENERATION_FAILED = "generation_failed"
STOP_FRAME_EXTRACT_FAILED = "last_frame_extract_failed"
STOP_CONTINUITY_FRAME_MISSING = "continuity_frame_missing_for_next_clip"

GenerateClipFn = Callable[..., "ClipExecutionResult"]


@dataclass
class ContinuityDirectorClipPlan:
    clip_index: int
    prompt: str
    duration_seconds: int = 15
    character_continuity: str = ""
    environment_continuity: str = ""
    camera_direction: str = ""
    mood: str = ""
    first_frame_source: str = FIRST_FRAME_PROMPT_ONLY
    first_frame_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "prompt": self.prompt,
            "duration_seconds": self.duration_seconds,
            "character_continuity": self.character_continuity,
            "environment_continuity": self.environment_continuity,
            "camera_direction": self.camera_direction,
            "mood": self.mood,
            "first_frame_source": self.first_frame_source,
            "first_frame_path": self.first_frame_path,
        }


@dataclass
class ContinuityDirectorPlan:
    run_id: str
    topic: str
    clip_count: int
    clips: list[ContinuityDirectorClipPlan]
    continuity_method: str = CONTINUITY_METHOD_LAST_FRAME
    version: str = AGENT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "topic": self.topic,
            "clip_count": self.clip_count,
            "continuity_method": self.continuity_method,
            "clips": [clip.to_dict() for clip in self.clips],
        }


@dataclass
class ClipExecutionResult:
    clip_index: int
    ok: bool
    generate_clicked: bool = False
    mp4_path: str = ""
    last_frame_path: str = ""
    first_frame_input_path: str = ""
    errors: list[str] = field(default_factory=list)
    live_payload: dict[str, Any] = field(default_factory=dict)
    mp4_recovery_audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "ok": self.ok,
            "generate_clicked": self.generate_clicked,
            "mp4_path": self.mp4_path,
            "last_frame_path": self.last_frame_path,
            "first_frame_input_path": self.first_frame_input_path,
            "errors": list(self.errors),
            "live_payload": dict(self.live_payload),
            "mp4_recovery_audit": dict(self.mp4_recovery_audit),
        }


@dataclass
class ContinuityDirectorChainResult:
    ok: bool
    status: str
    run_id: str
    clip_count: int
    clips_completed: int
    generate_clicks: int
    continuity_method: str
    stop_reason: str = ""
    stopped_at_clip: int | None = None
    clip_results: list[ClipExecutionResult] = field(default_factory=list)
    final_video_path: str = ""
    chain_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": AGENT_VERSION,
            "ok": self.ok,
            "status": self.status,
            "run_id": self.run_id,
            "clip_count": self.clip_count,
            "clips_completed": self.clips_completed,
            "generate_clicks": self.generate_clicks,
            "continuity_method": self.continuity_method,
            "stop_reason": self.stop_reason,
            "stopped_at_clip": self.stopped_at_clip,
            "clip_results": [item.to_dict() for item in self.clip_results],
            "final_video_path": self.final_video_path,
            "chain_path": self.chain_path,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip_dir(run_dir: Path, clip_index: int) -> Path:
    path = run_dir / "clips" / f"c{clip_index}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def plan_clip_chain(
    *,
    run_id: str,
    topic: str,
    clip_count: int = 2,
    planned_duration_seconds: int = 30,
    characters: list[str] | None = None,
    environment: str = "",
    mood: str = "",
    style: str = "cinematic",
) -> ContinuityDirectorPlan:
    """Build a multi-clip plan with last-frame continuity metadata preserved per clip."""
    from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content

    frame_plan = plan_kling_frame_to_video_content(
        topic=topic,
        planned_duration_seconds=planned_duration_seconds,
        clip_count=clip_count,
        characters=characters,
        environment=environment,
        mood=mood,
        style=style,
    )
    clips: list[ContinuityDirectorClipPlan] = []
    for clip in frame_plan.clips:
        first_source = FIRST_FRAME_PROMPT_ONLY if clip.clip_index <= 1 else FIRST_FRAME_PRIOR_CLIP
        clips.append(
            ContinuityDirectorClipPlan(
                clip_index=clip.clip_index,
                prompt=clip.prompt,
                duration_seconds=int(clip.duration_seconds or 15),
                character_continuity=str(clip.character_continuity or ""),
                environment_continuity=str(clip.environment_continuity or ""),
                camera_direction=str(clip.camera_direction or ""),
                mood=mood or str(clip.chapter_progression.get("emotion") or ""),
                first_frame_source=first_source,
            )
        )
    return ContinuityDirectorPlan(
        run_id=run_id,
        topic=topic,
        clip_count=len(clips),
        clips=clips,
    )


def validate_real_mp4(path: str | Path) -> dict[str, Any]:
    """Require a real MP4 — fake/placeholder files are rejected (extractor rules)."""
    return verify_extracted_kling_mp4(path)


def ensure_kling_frame_metadata_for_plan(
    plan: ContinuityDirectorPlan,
    project_root: str | Path,
) -> dict[str, Any]:
    """
    Write topic-aligned starter_image_prompt for Kling frame run metadata.
    Keeps Topic Guard satisfied for clip 2+ PNG upload without disabling guard globally.
    """
    root = Path(project_root).resolve()
    run_dir = kling_frame_run_dir(root, plan.run_id)
    starter_dir = starter_frame_dir(run_dir)
    prompt_path = starter_dir / STARTER_FRAME_PROMPT_JSON
    clip0 = plan.clips[0] if plan.clips else None
    mood = str(clip0.mood or "") if clip0 else ""
    environment = str(clip0.environment_continuity or "") if clip0 else ""
    starter_prompt, clip_preview = build_kling_starter_image_prompt(
        topic=plan.topic,
        story_summary=plan.topic,
        mood=mood,
        environment=environment,
    )
    if not prompt_matches_topic(prompt=starter_prompt, topic=plan.topic):
        starter_prompt = plan.topic[:1200]
    guard_passed = prompt_matches_topic(prompt=starter_prompt, topic=plan.topic)
    payload = {
        "version": AGENT_VERSION,
        "run_id": plan.run_id,
        "topic": plan.topic,
        "starter_image_prompt": starter_prompt,
        "clip_prompt_preview": clip_preview or (clip0.prompt[:400] if clip0 else ""),
        "topic_guard_passed": guard_passed,
        "continuity_method": CONTINUITY_METHOD_LAST_FRAME,
    }
    prompt_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _live_clip_candidate_paths(project_root: Path, run_id: str, clip_index: int) -> list[Path]:
    live_clip_dir = kling_frame_clip_dir(kling_frame_run_dir(project_root, run_id), clip_index)
    names = (f"clip_{clip_index}.mp4", "video.mp4")
    return [live_clip_dir / name for name in names]


def _read_extract_report(live_clip_dir: Path) -> dict[str, Any]:
    report_path = live_clip_dir / "mp4_extract_report.json"
    if not report_path.is_file():
        return {}
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_real_clip_mp4(
    *,
    project_root: str | Path,
    run_id: str,
    clip_index: int,
    agent_clip_dir: Path,
    exec_result: ClipExecutionResult,
    recover_mp4: Callable[..., str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Resolve a real MP4 after generation: existing paths, extract report, then live recovery.
    """
    root = Path(project_root).resolve()
    live_clip_dir = kling_frame_clip_dir(kling_frame_run_dir(root, run_id), clip_index)
    audit: dict[str, Any] = {
        "attempted_methods": [],
        "candidates_checked": [],
        "quarantined_paths": [],
        "verify_results": [],
        "extract_report_path": str((live_clip_dir / "mp4_extract_report.json").resolve()).replace("\\", "/"),
        "final_path": "",
        "failure_reason": "",
    }

    def _check_path(path: Path, *, label: str) -> str:
        if not path.is_file():
            audit["candidates_checked"].append({"path": str(path), "label": label, "exists": False})
            return ""
        verify = verify_extracted_kling_mp4(path)
        audit["candidates_checked"].append(
            {
                "path": str(path.resolve()).replace("\\", "/"),
                "label": label,
                "exists": True,
                "is_real_mp4": bool(verify.get("is_real_mp4")),
                "size_bytes": verify.get("size_bytes"),
                "duration_seconds": verify.get("duration_seconds"),
            }
        )
        audit["verify_results"].append({"path": str(path), "verify": verify})
        if verify.get("is_real_mp4"):
            audit["final_path"] = str(path.resolve()).replace("\\", "/")
            return audit["final_path"]
        return ""

    candidates: list[tuple[str, Path]] = []
    inline = str(exec_result.mp4_path or "").strip()
    if inline:
        candidates.append(("exec_result.mp4_path", Path(inline)))
    live_payload = dict(exec_result.live_payload or {})
    for key in ("clip_output_path", "output_path", "download_path"):
        value = str(live_payload.get(key) or "").strip()
        if value:
            candidates.append((f"live_payload.{key}", Path(value)))
    for path in _live_clip_candidate_paths(root, run_id, clip_index):
        candidates.append((path.name, path))
    canonical = agent_clip_dir / "video.mp4"
    candidates.append(("agent_clip_dir.video.mp4", canonical))

    seen: set[str] = set()
    for label, path in candidates:
        key = str(path.resolve()) if path.is_file() else str(path)
        if key in seen:
            continue
        seen.add(key)
        found = _check_path(path, label=label)
        if found:
            audit["attempted_methods"].append(f"existing:{label}")
            return found, audit

    extract_report = _read_extract_report(live_clip_dir)
    if extract_report.get("ok") and extract_report.get("output_path"):
        audit["attempted_methods"].append("extract_report_reuse")
        found = _check_path(Path(str(extract_report["output_path"])), label="extract_report.output_path")
        if found:
            return found, audit
        audit["attempted_methods"].extend(list(extract_report.get("attempted_methods") or []))
        audit["quarantined_paths"].extend(list(extract_report.get("quarantined_paths") or []))

    if recover_mp4 is not None:
        audit["attempted_methods"].append("recover_kling_frame_output")
        try:
            recovered = str(
                recover_mp4(
                    run_id=run_id,
                    clip_index=clip_index,
                    clip_dir=agent_clip_dir,
                    live_payload=live_payload,
                )
                or ""
            ).strip()
        except Exception as exc:
            audit["failure_reason"] = f"recover_failed:{exc}"
            exec_result.errors.append(audit["failure_reason"])
            recovered = ""
        if recovered:
            found = _check_path(Path(recovered), label="recover_hook")
            if found:
                return found, audit

        extract_report = _read_extract_report(live_clip_dir)
        audit["attempted_methods"].extend(list(extract_report.get("attempted_methods") or []))
        audit["quarantined_paths"].extend(list(extract_report.get("quarantined_paths") or []))
        if extract_report.get("output_path"):
            found = _check_path(Path(str(extract_report["output_path"])), label="post_recovery_extract_report")
            if found:
                return found, audit

        for path in _live_clip_candidate_paths(root, run_id, clip_index):
            found = _check_path(path, label=f"post_recovery:{path.name}")
            if found:
                audit["attempted_methods"].append(f"post_recovery:{path.name}")
                return found, audit

    if not audit["failure_reason"]:
        methods = ", ".join(audit.get("attempted_methods") or []) or "none"
        audit["failure_reason"] = f"no_real_mp4_after_recovery methods={methods}"
    return "", audit


def quarantine_invalid_mp4(path: str | Path, clip_dir: Path) -> str:
    """Move invalid MP4 aside so it is never used as continuity source."""
    src = Path(path)
    if not src.is_file():
        return ""
    quarantine = clip_dir / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    dest = quarantine / f"invalid_{src.name}"
    try:
        if src.resolve() != dest.resolve():
            shutil.move(str(src), str(dest))
    except OSError:
        try:
            shutil.copy2(src, dest)
            src.unlink(missing_ok=True)
        except OSError:
            return ""
    return str(dest.resolve()).replace("\\", "/")


class ContinuityDirectorAgent:
    """Orchestrate clip chains using last-frame PNG extraction — never Use Frame."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def write_chain_report(self, run_dir: Path, payload: dict[str, Any]) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = dict(payload)
        payload["updated_at"] = _now_iso()
        path = run_dir / CHAIN_FILENAME
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        continuity_copy = continuity_dir(run_dir) / CHAIN_FILENAME
        continuity_copy.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def prepare_next_clip_first_frame(
        self,
        *,
        run_dir: Path,
        from_clip_index: int,
        video_path: str | Path,
    ) -> str:
        """Extract last frame PNG from a verified clip MP4."""
        extracted = extract_and_save_continuity_frame(
            video_path=video_path,
            run_dir=run_dir,
            clip_index=from_clip_index,
        )
        validation = validate_frame(extracted.frame_path)
        if not validation.get("ok"):
            raise RuntimeError(
                f"continuity PNG invalid after clip {from_clip_index}: {extracted.frame_path}"
            )
        return str(Path(extracted.frame_path).resolve())

    def run_chain(
        self,
        *,
        plan: ContinuityDirectorPlan,
        run_dir: str | Path,
        generate_clip: GenerateClipFn,
        recover_mp4: Callable[..., str] | None = None,
        dry_run: bool = False,
    ) -> ContinuityDirectorChainResult:
        """
        Execute clip chain:
        Generate → real MP4 → extract PNG → pass PNG to next clip first frame.
        """
        run_dir_path = Path(run_dir).resolve()
        run_dir_path.mkdir(parents=True, exist_ok=True)
        prior_frame_path = ""
        clip_results: list[ClipExecutionResult] = []
        generate_clicks = 0
        final_video = ""
        status = STATUS_RUNNING
        stop_reason = ""
        stopped_at: int | None = None

        chain_state: dict[str, Any] = {
            "version": AGENT_VERSION,
            "run_id": plan.run_id,
            "topic": plan.topic,
            "continuity_method": CONTINUITY_METHOD_LAST_FRAME,
            "dry_run": dry_run,
            "clips": [],
            "started_at": _now_iso(),
        }
        metadata_info = ensure_kling_frame_metadata_for_plan(plan, self.project_root)
        chain_state["topic_guard_passed"] = bool(metadata_info.get("topic_guard_passed"))
        chain_state["starter_image_prompt"] = metadata_info.get("starter_image_prompt", "")
        self.write_chain_report(run_dir_path, chain_state)

        for clip in plan.clips:
            clip_index = clip.clip_index
            clip_dir = _clip_dir(run_dir_path, clip_index)
            first_frame_input = prior_frame_path if clip_index > 1 else ""

            if clip_index > 1:
                if not first_frame_input or not Path(first_frame_input).is_file():
                    stop_reason = STOP_CONTINUITY_FRAME_MISSING
                    stopped_at = clip_index
                    status = STATUS_STOPPED
                    break
                clip.first_frame_source = FIRST_FRAME_PRIOR_CLIP
                clip.first_frame_path = first_frame_input

            exec_result = generate_clip(
                clip=clip,
                run_id=plan.run_id,
                run_dir=run_dir_path,
                clip_dir=clip_dir,
                first_frame_path=first_frame_input or None,
                dry_run=dry_run,
            )
            exec_result.first_frame_input_path = first_frame_input
            if exec_result.generate_clicked:
                generate_clicks += 1
            if generate_clicks > plan.clip_count:
                stop_reason = "max_generate_clicks_exceeded"
                stopped_at = clip_index
                status = STATUS_STOPPED
                clip_results.append(exec_result)
                break

            mp4_path, recovery_audit = resolve_real_clip_mp4(
                project_root=self.project_root,
                run_id=plan.run_id,
                clip_index=clip_index,
                agent_clip_dir=clip_dir,
                exec_result=exec_result,
                recover_mp4=recover_mp4,
            )
            exec_result.mp4_recovery_audit = recovery_audit

            canonical = clip_dir / "video.mp4"
            if mp4_path and Path(mp4_path).is_file() and Path(mp4_path).resolve() != canonical.resolve():
                shutil.copy2(mp4_path, canonical)
            if canonical.is_file() and verify_extracted_kling_mp4(canonical).get("is_real_mp4"):
                mp4_path = str(canonical.resolve())
            live_canonical = kling_frame_clip_dir(
                kling_frame_run_dir(self.project_root, plan.run_id),
                clip_index,
            ) / f"clip_{clip_index}.mp4"
            if mp4_path and Path(mp4_path).is_file() and live_canonical.parent.exists():
                if not live_canonical.is_file() or live_canonical.resolve() != Path(mp4_path).resolve():
                    shutil.copy2(mp4_path, live_canonical)

            verify = validate_real_mp4(mp4_path) if mp4_path else {"is_real_mp4": False}
            exec_result.mp4_path = mp4_path
            if not verify.get("is_real_mp4"):
                if mp4_path:
                    quarantined = quarantine_invalid_mp4(mp4_path, clip_dir)
                    if quarantined:
                        exec_result.errors.append(f"quarantined_invalid_mp4:{quarantined}")
                        recovery_audit.setdefault("quarantined_paths", []).append(quarantined)
                exec_result.ok = False
                reason = recovery_audit.get("failure_reason") or STOP_MP4_MISSING
                exec_result.errors.append(STOP_MP4_MISSING)
                exec_result.errors.append(reason)
                exec_result.mp4_recovery_audit = recovery_audit
                clip_results.append(exec_result)
                stop_reason = STOP_MP4_MISSING
                stopped_at = clip_index
                status = STATUS_STOPPED
                break

            exec_result.ok = True

            final_video = mp4_path
            last_frame_path = ""
            if clip_index < plan.clip_count:
                try:
                    last_frame_path = self.prepare_next_clip_first_frame(
                        run_dir=run_dir_path,
                        from_clip_index=clip_index,
                        video_path=mp4_path,
                    )
                except Exception as exc:
                    exec_result.ok = False
                    exec_result.errors.append(f"{STOP_FRAME_EXTRACT_FAILED}:{exc}")
                    clip_results.append(exec_result)
                    stop_reason = STOP_FRAME_EXTRACT_FAILED
                    stopped_at = clip_index
                    status = STATUS_STOPPED
                    break
                prior_frame_path = last_frame_path

            exec_result.last_frame_path = last_frame_path
            clip_results.append(exec_result)
            chain_state["clips"].append(
                {
                    "clip": clip_index,
                    "mp4_path": mp4_path,
                    "last_frame_path": last_frame_path,
                    "first_frame_input_path": first_frame_input,
                    "next_clip": clip_index + 1 if clip_index < plan.clip_count else None,
                    "character_continuity": clip.character_continuity,
                    "environment_continuity": clip.environment_continuity,
                    "camera_direction": clip.camera_direction,
                    "mood": clip.mood,
                }
            )
            self.write_chain_report(run_dir_path, chain_state)

        clips_completed = len([r for r in clip_results if r.ok and validate_real_mp4(r.mp4_path).get("is_real_mp4")])
        if status == STATUS_RUNNING and clips_completed >= plan.clip_count:
            status = STATUS_COMPLETE
        chain_state["status"] = status
        chain_state["stop_reason"] = stop_reason
        chain_state["clips_completed"] = clips_completed
        chain_state["generate_clicks"] = generate_clicks
        chain_state["finished_at"] = _now_iso()
        chain_path = self.write_chain_report(run_dir_path, chain_state)

        return ContinuityDirectorChainResult(
            ok=status == STATUS_COMPLETE,
            status=status,
            run_id=plan.run_id,
            clip_count=plan.clip_count,
            clips_completed=clips_completed,
            generate_clicks=generate_clicks,
            continuity_method=CONTINUITY_METHOD_LAST_FRAME,
            stop_reason=stop_reason,
            stopped_at_clip=stopped_at,
            clip_results=clip_results,
            final_video_path=final_video,
            chain_path=str(chain_path.resolve()).replace("\\", "/"),
        )


def build_frame_live_generate_hook(
    *,
    approved_by: str,
    confirm_credit_spend: bool,
    cdp_url: str = "http://127.0.0.1:9222",
    aspect_ratio: str = "9:16",
    topic: str = "",
) -> GenerateClipFn:
    """Live hook: Kling Frame-to-Video with PNG file upload (never Use Frame)."""

    def _generate(
        *,
        clip: ContinuityDirectorClipPlan,
        run_id: str,
        run_dir: Path,
        clip_dir: Path,
        first_frame_path: str | None,
        dry_run: bool = False,
    ) -> ClipExecutionResult:
        if dry_run:
            return ClipExecutionResult(
                clip_index=clip.clip_index,
                ok=False,
                errors=["dry_run_live_hook_blocked"],
            )
        from content_brain.execution.kling_frame_to_video_live_engine import run_kling_frame_to_video_live

        live = run_kling_frame_to_video_live(
            starter_frame_path=first_frame_path,
            frame_prompt=clip.prompt,
            topic=topic or clip.prompt[:600],
            run_id=run_id,
            clip_index=clip.clip_index,
            aspect_ratio=aspect_ratio,
            approve_generate=True,
            approved_by=approved_by,
            confirm_credit_spend=confirm_credit_spend,
            cdp_url=cdp_url,
            continuity_frame_in_ui=False,
        )
        payload = live.to_dict()
        mp4 = str(payload.get("clip_output_path") or payload.get("output_path") or "").strip()
        generation_ok = bool(live.ok) or bool(live.generation_completed)
        return ClipExecutionResult(
            clip_index=clip.clip_index,
            ok=generation_ok,
            generate_clicked=bool(live.generate_clicked),
            mp4_path=mp4,
            errors=list(live.errors),
            live_payload=payload,
        )

    return _generate


def build_frame_live_recover_hook(
    *,
    cdp_url: str = "http://127.0.0.1:9222",
    project_root: str | Path = ".",
) -> Callable[..., str]:
    """Recover MP4 after generation via Kling real MP4 extractor (no Generate)."""
    root = Path(project_root).resolve()

    def _recover(
        *,
        run_id: str,
        clip_index: int,
        clip_dir: Path,
        live_payload: dict[str, Any],
    ) -> str:
        from content_brain.execution.kling_frame_to_video_live_engine import recover_kling_frame_output

        live_clip_dir = kling_frame_clip_dir(kling_frame_run_dir(root, run_id), clip_index)
        dest = live_clip_dir / f"clip_{clip_index}.mp4"
        for candidate in (dest, live_clip_dir / "video.mp4"):
            verify = verify_extracted_kling_mp4(candidate)
            if verify.get("is_real_mp4"):
                return str(candidate.resolve())

        result = recover_kling_frame_output(
            run_id=run_id,
            cdp_url=cdp_url,
            clip_index=clip_index,
        )
        for candidate in (
            dest,
            live_clip_dir / "video.mp4",
            Path(str(result.clip_output_path or "")),
            Path(str(result.output_path or "")),
        ):
            if not candidate.is_file():
                continue
            verify = verify_extracted_kling_mp4(candidate)
            if verify.get("is_real_mp4"):
                agent_dest = clip_dir / "video.mp4"
                if candidate.resolve() != agent_dest.resolve():
                    shutil.copy2(candidate, agent_dest)
                return str(candidate.resolve())
            quarantine_invalid_mp4(candidate, clip_dir)
        return ""

    return _recover


__all__ = [
    "AGENT_VERSION",
    "CONTINUITY_METHOD_LAST_FRAME",
    "CHAIN_FILENAME",
    "ClipExecutionResult",
    "ContinuityDirectorAgent",
    "ContinuityDirectorChainResult",
    "ContinuityDirectorClipPlan",
    "ContinuityDirectorPlan",
    "ensure_kling_frame_metadata_for_plan",
    "resolve_real_clip_mp4",
    "build_frame_live_generate_hook",
    "build_frame_live_recover_hook",
    "plan_clip_chain",
    "quarantine_invalid_mp4",
    "validate_real_mp4",
]
