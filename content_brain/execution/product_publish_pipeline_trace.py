"""Mandatory Create Video publish pipeline trace — stage tracking and post-processing chain."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PIPELINE_TRACE_VERSION = "product_publish_pipeline_trace_v1"
ORCHESTRATOR_VERSION = "product_multiclip_orchestrator_v3"
PIPELINE_TRACE_FILENAME = "pipeline_trace.json"

STAGE_STORY_PLANNING = "story_planning"
STAGE_CLIP_GENERATION = "clip_generation"
STAGE_USE_FRAME_CHAIN = "use_frame_chain"
STAGE_DOWNLOAD_VERIFICATION = "download_verification"
STAGE_ASSEMBLY_BRIDGE = "assembly_bridge"
STAGE_SUBTITLE_BRANDING_PUBLISH = "subtitle_branding_publish"
STAGE_YOUTUBE_METADATA = "youtube_metadata_generation"
STAGE_YOUTUBE_UPLOAD = "youtube_upload_runtime"

PIPELINE_STAGES: tuple[str, ...] = (
    STAGE_STORY_PLANNING,
    STAGE_CLIP_GENERATION,
    STAGE_USE_FRAME_CHAIN,
    STAGE_DOWNLOAD_VERIFICATION,
    STAGE_ASSEMBLY_BRIDGE,
    STAGE_SUBTITLE_BRANDING_PUBLISH,
    STAGE_YOUTUBE_METADATA,
    STAGE_YOUTUBE_UPLOAD,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineTrace:
    def __init__(self, *, run_id: str = "", orchestrator_version: str = ORCHESTRATOR_VERSION) -> None:
        self.run_id = run_id
        self.orchestrator_version = orchestrator_version
        self.stages: dict[str, dict[str, Any]] = {}
        self.stop_stage = ""
        self.last_completed_stage = ""
        self.pipeline_complete = False
        self.updated_at = _now_iso()

    def mark(
        self,
        stage: str,
        *,
        status: str = "completed",
        error: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        if stage not in PIPELINE_STAGES:
            return
        payload = {
            "status": status,
            "finished_at": _now_iso(),
        }
        if error:
            payload["error"] = error
        if extra:
            payload.update(extra)
        self.stages[stage] = payload
        self.updated_at = _now_iso()
        if status == "completed":
            self.last_completed_stage = stage
            self.stop_stage = ""
        elif status in {"failed", "blocked"}:
            self.stop_stage = stage
        self.pipeline_complete = (
            self.last_completed_stage == STAGE_YOUTUBE_UPLOAD
            and status in {"completed", "skipped"}
            and not self.stop_stage
        ) or (
            self.last_completed_stage == STAGE_SUBTITLE_BRANDING_PUBLISH
            and not self.stop_stage
            and STAGE_YOUTUBE_UPLOAD in self.stages
            and self.stages[STAGE_YOUTUBE_UPLOAD].get("status") in {"completed", "skipped"}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PIPELINE_TRACE_VERSION,
            "run_id": self.run_id,
            "orchestrator_version": self.orchestrator_version,
            "stages": self.stages,
            "last_completed_stage": self.last_completed_stage,
            "stop_stage": self.stop_stage,
            "pipeline_complete": self.pipeline_complete,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PipelineTrace:
        trace = cls(
            run_id=str(payload.get("run_id") or ""),
            orchestrator_version=str(payload.get("orchestrator_version") or ORCHESTRATOR_VERSION),
        )
        trace.stages = dict(payload.get("stages") or {})
        trace.last_completed_stage = str(payload.get("last_completed_stage") or "")
        trace.stop_stage = str(payload.get("stop_stage") or "")
        trace.pipeline_complete = bool(payload.get("pipeline_complete"))
        trace.updated_at = str(payload.get("updated_at") or _now_iso())
        return trace


def save_pipeline_trace(run_dir: str | Path, trace: PipelineTrace) -> Path:
    target = Path(run_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / PIPELINE_TRACE_FILENAME
    path.write_text(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_pipeline_trace(run_dir: str | Path) -> dict[str, Any] | None:
    path = Path(run_dir).resolve() / PIPELINE_TRACE_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def bootstrap_trace_from_pwmap_result(
    *,
    run_id: str,
    pwmap_result: dict[str, Any],
    multiclip_plan: dict[str, Any] | None = None,
) -> PipelineTrace:
    trace = PipelineTrace(run_id=run_id)
    trace.mark(STAGE_STORY_PLANNING, status="completed")

    finalization = dict(pwmap_result.get("finalization_stages") or pwmap_result.get("finalization") or {})
    if isinstance(finalization.get("stages"), dict):
        finalization = finalization["stages"]

    clips_stage = dict(finalization.get("clips_generated") or {})
    if clips_stage.get("status") == "completed" or pwmap_result.get("ok"):
        trace.mark(STAGE_CLIP_GENERATION, status="completed", extra={"clip_count": pwmap_result.get("clip_count")})

    plan = multiclip_plan or dict(pwmap_result.get("multiclip_execution_plan") or {})
    execution_mode = str(plan.get("execution_mode") or pwmap_result.get("execution_mode") or "")
    if execution_mode == "use_frame_chain" and int(plan.get("clip_count") or pwmap_result.get("clip_count") or 0) > 1:
        trace.mark(STAGE_USE_FRAME_CHAIN, status="completed")
    elif execution_mode != "use_frame_chain":
        trace.mark(STAGE_USE_FRAME_CHAIN, status="skipped", extra={"reason": "single_clip_or_mode_disabled"})

    downloads_stage = dict(finalization.get("downloads_verified") or {})
    if downloads_stage.get("status") == "completed":
        trace.mark(
            STAGE_DOWNLOAD_VERIFICATION,
            status="completed",
            extra={"valid_clip_count": downloads_stage.get("valid_clip_count")},
        )
    elif pwmap_result.get("ok"):
        trace.mark(STAGE_DOWNLOAD_VERIFICATION, status="completed")

    return trace


def run_publish_post_processing_chain(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    run_id: str,
    topic: str,
    expected_clip_count: int,
    preflight: dict[str, Any] | None = None,
    trace: PipelineTrace | None = None,
    visual_diversity: dict[str, Any] | None = None,
    attempt_auto_youtube_upload: bool = True,
) -> dict[str, Any]:
    """Run assembly → branding (metadata generated inside assembly when enabled)."""
    run_path = Path(run_dir).resolve()
    preflight = dict(preflight or {})
    trace = trace or PipelineTrace(run_id=run_id)
    result: dict[str, Any] = {"ok": True, "pipeline_trace": trace.to_dict()}

    from content_brain.execution.product_assembly_bridge import run_product_assembly_bridge

    try:
        assembly_result = run_product_assembly_bridge(
            project_root=project_root,
            run_dir=run_path,
            run_id=run_id,
            topic=topic,
            expected_clip_count=expected_clip_count,
            preflight=preflight,
            invoke_youtube_metadata=True,
        )
    except Exception as exc:
        trace.mark(STAGE_ASSEMBLY_BRIDGE, status="failed", error=str(exc))
        save_pipeline_trace(run_path, trace)
        return {
            "ok": False,
            "status": "assembly_failed",
            "error": str(exc),
            "assembly": {"ok": False, "error": str(exc)},
            "pipeline_trace": trace.to_dict(),
        }

    result["assembly"] = assembly_result
    result["assembly_status"] = assembly_result.get("assembly_status")
    result["assembly_complete"] = bool(assembly_result.get("assembly_complete"))
    result["publish_package_ready"] = bool(assembly_result.get("publish_package_ready"))
    result["publish_package_path"] = assembly_result.get("publish_package_path")
    result["final_publish_video_path"] = assembly_result.get("final_publish_video_path")
    result["source_clip_count"] = assembly_result.get("source_clip_count")

    if not assembly_result.get("ok"):
        trace.mark(
            STAGE_ASSEMBLY_BRIDGE,
            status="failed",
            error=str(assembly_result.get("error") or "assembly_failed"),
        )
        save_pipeline_trace(run_path, trace)
        result["ok"] = False
        result["status"] = "assembly_failed"
        result["error"] = assembly_result.get("error")
        result["pipeline_trace"] = trace.to_dict()
        return result

    trace.mark(STAGE_ASSEMBLY_BRIDGE, status="completed")

    metadata_path = str(assembly_result.get("youtube_metadata_path") or "")
    publish_dir = Path(str(assembly_result.get("publish_package_path") or run_path / "publish"))
    if metadata_path or (publish_dir / "youtube_metadata.json").is_file():
        trace.mark(STAGE_YOUTUBE_METADATA, status="completed", extra={"path": metadata_path or str(publish_dir / "youtube_metadata.json")})
    else:
        trace.mark(STAGE_YOUTUBE_METADATA, status="failed", error="youtube_metadata_missing")

    result["youtube_metadata"] = assembly_result.get("youtube_metadata")
    result["youtube_metadata_path"] = assembly_result.get("youtube_metadata_path")

    from content_brain.execution.product_subtitle_branding_publish import run_product_subtitle_branding_publish

    try:
        branding_publish_result = run_product_subtitle_branding_publish(
            project_root=project_root,
            run_dir=run_path,
            run_id=run_id,
            topic=topic,
            preflight=preflight,
        )
    except Exception as exc:
        trace.mark(STAGE_SUBTITLE_BRANDING_PUBLISH, status="failed", error=str(exc))
        save_pipeline_trace(run_path, trace)
        result["ok"] = False
        result["status"] = "branding_failed"
        result["error"] = str(exc)
        result["branding_publish"] = {"ok": False, "error": str(exc)}
        result["pipeline_trace"] = trace.to_dict()
        return result

    result["branding_publish"] = branding_publish_result
    result["branding_status"] = branding_publish_result.get("branding_status")
    result["subtitle_status"] = branding_publish_result.get("subtitle_status")
    result["final_branded_publish_video_path"] = branding_publish_result.get("final_branded_publish_video_path")

    if branding_publish_result.get("branding_status") == "branding_failed":
        trace.mark(
            STAGE_SUBTITLE_BRANDING_PUBLISH,
            status="failed",
            error=str(branding_publish_result.get("error") or "branding_failed"),
        )
        result["ok"] = False
        result["status"] = "branding_failed"
        result["error"] = branding_publish_result.get("error")
    elif branding_publish_result.get("publish_ready"):
        trace.mark(STAGE_SUBTITLE_BRANDING_PUBLISH, status="completed")
        result["publish_package_ready"] = True
        result["video_path"] = branding_publish_result.get("final_branded_publish_video_path")
    else:
        trace.mark(STAGE_SUBTITLE_BRANDING_PUBLISH, status="completed", extra={"publish_ready": False})

    publish_dir_text = str(
        branding_publish_result.get("publish_package_path")
        or assembly_result.get("publish_package_path")
        or run_path / "publish"
    )
    result["youtube_upload"] = {}
    if attempt_auto_youtube_upload and branding_publish_result.get("publish_ready"):
        from content_brain.automation.auto_youtube_upload_after_publish import maybe_auto_youtube_upload_after_publish

        upload_result = maybe_auto_youtube_upload_after_publish(
            project_root=project_root,
            run_dir=run_path,
            run_id=run_id,
            publish_dir=publish_dir_text,
            branding_publish_result=branding_publish_result,
            assembly_result=assembly_result,
            visual_diversity=visual_diversity,
            expected_clip_count=expected_clip_count,
        )
        result["youtube_upload"] = upload_result
        result["youtube_upload_status"] = str(upload_result.get("upload_status") or "")
        result["youtube_video_id"] = str(upload_result.get("youtube_video_id") or "")
        result["youtube_url"] = str(upload_result.get("youtube_url") or "")
        result["youtube_visibility"] = str(upload_result.get("visibility") or "")
        result["youtube_upload_time"] = str(upload_result.get("upload_time") or "")
        result["auto_upload_enabled"] = bool(upload_result.get("auto_upload_enabled"))
        result["auto_upload_started"] = bool(upload_result.get("auto_upload_started"))
        result["youtube_upload_blocked_reason"] = str(upload_result.get("blocked_reason") or upload_result.get("error") or "")

        if upload_result.get("uploaded"):
            trace.mark(
                STAGE_YOUTUBE_UPLOAD,
                status="completed",
                extra={
                    "youtube_video_id": upload_result.get("youtube_video_id"),
                    "visibility": upload_result.get("visibility"),
                    "auto_upload": True,
                },
            )
        elif upload_result.get("blocked_reason") or upload_result.get("upload_status") == "blocked":
            trace.mark(
                STAGE_YOUTUBE_UPLOAD,
                status="blocked",
                error=str(upload_result.get("blocked_reason") or upload_result.get("error") or "upload_blocked"),
            )
        elif not upload_result.get("auto_upload_enabled"):
            trace.mark(
                STAGE_YOUTUBE_UPLOAD,
                status="skipped",
                extra={"reason": "auto_upload_disabled"},
            )
        else:
            trace.mark(
                STAGE_YOUTUBE_UPLOAD,
                status="failed",
                error=str(upload_result.get("error") or upload_result.get("upload_status") or "upload_failed"),
            )
    elif attempt_auto_youtube_upload:
        trace.mark(
            STAGE_YOUTUBE_UPLOAD,
            status="blocked",
            error="publish_not_ready",
        )
    else:
        trace.mark(
            STAGE_YOUTUBE_UPLOAD,
            status="skipped",
            extra={"reason": "auto_upload_not_requested"},
        )

    save_pipeline_trace(run_path, trace)
    result["pipeline_trace"] = trace.to_dict()
    result["stop_stage"] = trace.stop_stage
    result["last_completed_stage"] = trace.last_completed_stage
    return result


def repair_publish_chain_for_run(
    *,
    project_root: str | Path,
    run_id: str = "",
    run_dir: str | Path = "",
) -> dict[str, Any]:
    """Repair post-processing for a run that stopped after download verification."""
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve() if run_dir else root / "outputs" / "pwmap_agent_runs" / run_id
    if not run_path.is_dir():
        return {"ok": False, "error": "run_dir_missing", "run_dir": str(run_path)}

    resolved_run_id = run_id or run_path.name
    topic = ""
    preflight: dict[str, Any] = {}
    expected_clip_count = 2

    agent_path = run_path / "agent_result.json"
    if agent_path.is_file():
        try:
            agent = json.loads(agent_path.read_text(encoding="utf-8"))
            topic = str(agent.get("topic") or "")
            expected_clip_count = int(agent.get("clip_count") or expected_clip_count)
        except (OSError, json.JSONDecodeError):
            pass

    normalized_path = run_path / "normalized_result.json"
    if normalized_path.is_file():
        try:
            normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
            preflight = dict(normalized.get("preflight_snapshot") or normalized.get("preflight") or {})
            plan = dict(normalized.get("multiclip_execution_plan") or {})
            if plan.get("clip_count"):
                expected_clip_count = int(plan["clip_count"])
            if not topic:
                topic = str(preflight.get("authoritative_topic") or normalized.get("topic") or "")
        except (OSError, json.JSONDecodeError):
            pass

    runtime_path = run_path / "product_multiclip_runtime.json"
    pwmap_stub: dict[str, Any] = {"ok": True, "clip_count": expected_clip_count}
    if agent_path.is_file():
        try:
            pwmap_stub = json.loads(agent_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    if runtime_path.is_file():
        try:
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            plan = dict(runtime.get("multiclip_execution_plan") or {})
            pwmap_stub["multiclip_execution_plan"] = plan
            pwmap_stub["execution_mode"] = plan.get("execution_mode")
        except (OSError, json.JSONDecodeError):
            pass

    trace = bootstrap_trace_from_pwmap_result(run_id=resolved_run_id, pwmap_result=pwmap_stub)
    chain_result = run_publish_post_processing_chain(
        project_root=root,
        run_dir=run_path,
        run_id=resolved_run_id,
        topic=topic,
        expected_clip_count=expected_clip_count,
        preflight=preflight,
        trace=trace,
        attempt_auto_youtube_upload=True,
    )
    chain_result["run_id"] = resolved_run_id
    chain_result["run_dir"] = str(run_path.resolve()).replace("\\", "/")
    return chain_result


__all__ = [
    "ORCHESTRATOR_VERSION",
    "PIPELINE_STAGES",
    "PIPELINE_TRACE_FILENAME",
    "PipelineTrace",
    "bootstrap_trace_from_pwmap_result",
    "load_pipeline_trace",
    "repair_publish_chain_for_run",
    "run_publish_post_processing_chain",
    "save_pipeline_trace",
    "STAGE_ASSEMBLY_BRIDGE",
    "STAGE_CLIP_GENERATION",
    "STAGE_DOWNLOAD_VERIFICATION",
    "STAGE_STORY_PLANNING",
    "STAGE_SUBTITLE_BRANDING_PUBLISH",
    "STAGE_USE_FRAME_CHAIN",
    "STAGE_YOUTUBE_METADATA",
    "STAGE_YOUTUBE_UPLOAD",
]
