"""
ModirAgentOS API — Phase 10C Execution Center V2.

Session read endpoints + Phase 10H queue + Phase 10I/10J provider runtime dispatch.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ui.api.dependencies import (
    get_browser_operations_service,
    get_operations_control_service,
    get_queue_service,
    get_runtime_service,
    get_runway_live_smoke_service,
    get_session_service,
    get_session_store,
    get_assembly_approval_service,
    get_assembly_run_service,
    get_subtitle_run_service,
    get_uat_runtime_service,
    get_voice_approval_service,
    get_voice_run_service,
)
from ui.api.schemas.browser_operations import BrowserLaunchResponse, BrowserStatusResponse
from ui.api.schemas.operations import (
    OperationsActionRequest,
    OperationsActionResponse,
    OperationsEligibilityResponse,
)
from ui.api.schemas.panels import SessionOverviewResponse
from ui.api.schemas.queue import QueueActionResponse, QueuePeekResponse, QueueStatusResponse
from ui.api.schemas.runtime import RuntimeActionResponse, RuntimeDispatchRequest, RuntimeStatusResponse
from ui.api.schemas.sessions import (
    SessionDetailResponse,
    SessionListResponse,
    SessionSummaryDTO,
)
from ui.api.schemas.voice_approval import (
    VoiceApprovalActionResponse,
    VoiceApproveRequest,
    VoiceExpireRequest,
    VoiceRejectRequest,
    VoiceResetApprovalRequest,
)
from ui.api.schemas.assembly_approval import (
    AssemblyApprovalActionResponse,
    AssemblyApproveRequest,
    AssemblyExpireRequest,
    AssemblyRejectRequest,
    AssemblyResetApprovalRequest,
)
from ui.api.schemas.assembly_run import AssemblyRunRequest, AssemblyRunResponse
from ui.api.schemas.subtitle_run import SubtitleRunRequest, SubtitleRunResponse
from ui.api.schemas.uat_runtime import UatReviewRequest, UatReviewResponse, UatRunRequest, UatRunResponse
from ui.api.schemas.runway_live_smoke import (
    RunwayLiveSmokeActionRequest,
    RunwayLiveSmokeRuntimeResponse,
    RunwayLiveSmokeStartRequest,
)
from ui.api.schemas.content_brain_test_studio import (
    ContentBrainTestStudioOpenExportRequest,
    ContentBrainTestStudioOpenExportResponse,
    ContentBrainTestStudioPreflightResponse,
    ContentBrainTestStudioRunRequest,
    ContentBrainTestStudioRunResponse,
)
from ui.api.schemas.voice_run import VoiceRunRequest, VoiceRunResponse
from ui.api.services.operations_control_service import OperationsControlService
from ui.api.services.queue_service import QueueService
from ui.api.services.runtime_service import RuntimeService
from ui.api.services.session_service import SessionService, parse_archived_query
from ui.api.voice_approval_service import VoiceApprovalService
from ui.api.assembly_approval_service import AssemblyApprovalService
from ui.api.assembly_run_service import AssemblyRunService
from ui.api.subtitle_run_service import SubtitleRunService
from ui.api.voice_run_service import VoiceRunService
from ui.api.uat_runtime_service import UatRuntimeService, map_uat_error
from ui.api.runway_live_smoke_service import RunwayLiveSmokeRuntimeService
from ui.api.content_brain_test_studio_service import get_content_brain_test_studio_service
from ui.api.schemas.topic_universe_studio import (
    TopicUniverseGenerateRequest,
    TopicUniverseGenerateResponse,
    TopicUniverseHandoffRequest,
    TopicUniverseHandoffResponse,
    TopicUniverseOpenExportRequest,
    TopicUniverseOpenExportResponse,
    TopicUniversePreflightResponse,
)
from ui.api.topic_universe_studio_service import get_topic_universe_studio_service

API_HOST = os.getenv("MODIR_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("MODIR_API_PORT", "8765"))

_cors_origins = os.getenv(
    "MODIR_API_CORS_ORIGINS",
    "http://127.0.0.1:5173,http://127.0.0.1:5174,http://localhost:5173,http://localhost:5174",
)
CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]

API_VERSION = "0.6.0"

app = FastAPI(
    title="ModirAgentOS API",
    version=API_VERSION,
    description="Execution Center V2 — sessions + queue + provider runtime + operator control.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class CancelQueueRequest(BaseModel):
    reason: str = "cancelled"


@app.get("/health")
def health():
    return {"status": "ok", "service": "modiragent-api", "version": API_VERSION}


@app.post("/operations/browser/launch", response_model=BrowserLaunchResponse)
def operations_browser_launch(
    service=Depends(get_browser_operations_service),
):
    """Launch controlled Chrome for Runway browser mode (operator manual login)."""
    try:
        return service.launch()
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/operations/browser/status", response_model=BrowserStatusResponse)
def operations_browser_status(
    service=Depends(get_browser_operations_service),
):
    """CDP / profile / Runway login readiness for browser providers."""
    return service.status()


@app.get("/sessions/summary", response_model=SessionOverviewResponse)
def sessions_summary(service: SessionService = Depends(get_session_service)):
    return SessionOverviewResponse(**service.get_overview())


@app.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    archived: Optional[str] = None,
    service: SessionService = Depends(get_session_service),
):
    try:
        archive_filter = parse_archived_query(archived)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    sessions = service.list_sessions(archived=archive_filter)
    return SessionListResponse(
        sessions=[SessionSummaryDTO(**item) for item in sessions],
        count=len(sessions),
    )


@app.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    try:
        detail = service.get_session(session_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return SessionDetailResponse(**detail)


@app.post("/sessions/{session_id}/queue/enqueue", response_model=QueueActionResponse)
def enqueue_session(
    session_id: str,
    queue_service: QueueService = Depends(get_queue_service),
):
    try:
        result = queue_service.enqueue(session_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if not result["success"]:
        raise HTTPException(status_code=409, detail=result)
    return QueueActionResponse(**result)


@app.post("/sessions/{session_id}/queue/cancel", response_model=QueueActionResponse)
def cancel_queue_item(
    session_id: str,
    body: CancelQueueRequest,
    queue_service: QueueService = Depends(get_queue_service),
):
    try:
        result = queue_service.cancel(session_id, reason=body.reason)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return QueueActionResponse(success=True, **result)


@app.get("/queue/peek", response_model=QueuePeekResponse)
def peek_queue(queue_service: QueueService = Depends(get_queue_service)):
    return QueuePeekResponse(**queue_service.peek())


@app.post("/queue/dequeue", response_model=QueueActionResponse)
def dequeue_next(queue_service: QueueService = Depends(get_queue_service)):
    result = queue_service.dequeue_next()
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result)
    return QueueActionResponse(**result)


@app.get("/queue/status", response_model=QueueStatusResponse)
def queue_status(queue_service: QueueService = Depends(get_queue_service)):
    return QueueStatusResponse(**queue_service.status())


class RuntimeDispatchBody(RuntimeDispatchRequest):
    pass


@app.post(
    "/sessions/{session_id}/runtime/dispatch",
    response_model=RuntimeActionResponse,
    responses={
        200: {"description": "Synchronous dispatch completed (dry-run / skip_provider_execution)"},
        202: {"description": "Async dispatch accepted — worker started in background"},
        409: {"description": "Dispatch rejected"},
    },
)
def dispatch_runtime(
    session_id: str,
    body: RuntimeDispatchBody = RuntimeDispatchBody(),
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    try:
        result = runtime_service.dispatch(
            session_id,
            skip_provider_execution=body.skip_provider_execution,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    payload = RuntimeActionResponse(**result).model_dump()

    if result.get("reject_code") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=result)

    if result.get("async_mode"):
        if not result.get("accepted"):
            raise HTTPException(status_code=409, detail=result)
        return JSONResponse(status_code=202, content=payload)

    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result)
    return RuntimeActionResponse(**result)


@app.get("/sessions/{session_id}/runtime/status", response_model=RuntimeStatusResponse)
def runtime_status(
    session_id: str,
    runtime_service: RuntimeService = Depends(get_runtime_service),
):
    try:
        return RuntimeStatusResponse(**runtime_service.status(session_id))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/sessions/{session_id}/actions/eligibility", response_model=OperationsEligibilityResponse)
def session_action_eligibility(
    session_id: str,
    service: OperationsControlService = Depends(get_operations_control_service),
):
    try:
        return OperationsEligibilityResponse(**service.eligibility(session_id))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _operations_action_response(result: dict) -> OperationsActionResponse | JSONResponse:
    payload = OperationsActionResponse(**result).model_dump()
    if not result.get("ok"):
        status = 400 if result.get("code") == "REASON_REQUIRED" else 409
        return JSONResponse(status_code=status, content=payload)
    return OperationsActionResponse(**result)


@app.post("/sessions/{session_id}/actions/retry", response_model=OperationsActionResponse)
def session_action_retry(
    session_id: str,
    body: OperationsActionRequest,
    service: OperationsControlService = Depends(get_operations_control_service),
):
    try:
        result = service.retry(session_id, reason=body.reason, actor=body.actor)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _operations_action_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/actions/cancel", response_model=OperationsActionResponse)
def session_action_cancel(
    session_id: str,
    body: OperationsActionRequest,
    service: OperationsControlService = Depends(get_operations_control_service),
):
    try:
        result = service.cancel(session_id, reason=body.reason, actor=body.actor)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _operations_action_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/actions/archive", response_model=OperationsActionResponse)
def session_action_archive(
    session_id: str,
    body: OperationsActionRequest,
    service: OperationsControlService = Depends(get_operations_control_service),
):
    try:
        result = service.archive(session_id, reason=body.reason, actor=body.actor)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _operations_action_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/actions/requeue", response_model=OperationsActionResponse)
def session_action_requeue(
    session_id: str,
    body: OperationsActionRequest,
    service: OperationsControlService = Depends(get_operations_control_service),
):
    try:
        result = service.requeue(session_id, reason=body.reason, actor=body.actor)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _operations_action_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


def _voice_approval_response(result: dict) -> VoiceApprovalActionResponse | JSONResponse:
    payload = VoiceApprovalActionResponse(**result).model_dump()
    if not result.get("success"):
        status = 409
        return JSONResponse(status_code=status, content=payload)
    return VoiceApprovalActionResponse(**result)


@app.post("/sessions/{session_id}/voice/approve", response_model=VoiceApprovalActionResponse)
def voice_approve(
    session_id: str,
    body: VoiceApproveRequest,
    service: VoiceApprovalService = Depends(get_voice_approval_service),
):
    try:
        result = service.approve(
            session_id,
            request_live_tts=body.request_live_tts,
            reason=body.reason,
            approved_by=body.approved_by,
            ttl_minutes=body.ttl_minutes,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _voice_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/voice/reject", response_model=VoiceApprovalActionResponse)
def voice_reject(
    session_id: str,
    body: VoiceRejectRequest,
    service: VoiceApprovalService = Depends(get_voice_approval_service),
):
    try:
        result = service.reject(session_id, reason=body.reason, rejected_by=body.rejected_by)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _voice_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/voice/expire", response_model=VoiceApprovalActionResponse)
def voice_expire(
    session_id: str,
    body: VoiceExpireRequest,
    service: VoiceApprovalService = Depends(get_voice_approval_service),
):
    try:
        result = service.expire(session_id, reason=body.reason, expired_by=body.expired_by)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _voice_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/voice/reset-approval", response_model=VoiceApprovalActionResponse)
def voice_reset_approval(
    session_id: str,
    body: VoiceResetApprovalRequest,
    service: VoiceApprovalService = Depends(get_voice_approval_service),
):
    try:
        result = service.reset_approval(
            session_id,
            reason=body.reason,
            reset_by=body.reset_by,
            clear_live_tts_request=body.clear_live_tts_request,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _voice_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


def _voice_run_response(result: dict) -> VoiceRunResponse | JSONResponse:
    payload = VoiceRunResponse(**result).model_dump()
    if not result.get("success"):
        return JSONResponse(status_code=409, content=payload)
    return VoiceRunResponse(**result)


def _subtitle_run_response(result: dict) -> SubtitleRunResponse | JSONResponse:
    payload = SubtitleRunResponse(**result).model_dump()
    if not result.get("success"):
        return JSONResponse(status_code=409, content=payload)
    return SubtitleRunResponse(**result)


@app.post("/sessions/{session_id}/subtitle/run", response_model=SubtitleRunResponse)
def subtitle_run(
    session_id: str,
    body: SubtitleRunRequest | None = None,
    service: SubtitleRunService = Depends(get_subtitle_run_service),
):
    """Run local subtitle generation — cues + SRT/VTT/ASS sidecar files; no FFmpeg."""
    request = body or SubtitleRunRequest()
    try:
        result = service.run(
            session_id,
            formats=request.formats,
            timing_strategy=request.timing_strategy,
            overwrite=request.overwrite,
            language=request.language,
            triggered_by=request.triggered_by,
            force_retry=request.force_retry,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _subtitle_run_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


def _assembly_run_response(result: dict) -> AssemblyRunResponse | JSONResponse:
    payload = AssemblyRunResponse(**result).model_dump()
    if not result.get("success"):
        return JSONResponse(status_code=409, content=payload)
    return AssemblyRunResponse(**result)


def _assembly_approval_response(result: dict) -> AssemblyApprovalActionResponse | JSONResponse:
    payload = AssemblyApprovalActionResponse(**result).model_dump()
    if not result.get("success"):
        return JSONResponse(status_code=409, content=payload)
    return AssemblyApprovalActionResponse(**result)


@app.post("/sessions/{session_id}/assembly/approve", response_model=AssemblyApprovalActionResponse)
def assembly_approve(
    session_id: str,
    body: AssemblyApproveRequest,
    service: AssemblyApprovalService = Depends(get_assembly_approval_service),
):
    try:
        result = service.approve(
            session_id,
            request_real_assembly=body.request_real_assembly,
            reason=body.reason,
            approved_by=body.approved_by,
            ttl_minutes=body.ttl_minutes,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _assembly_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/assembly/reject", response_model=AssemblyApprovalActionResponse)
def assembly_reject(
    session_id: str,
    body: AssemblyRejectRequest,
    service: AssemblyApprovalService = Depends(get_assembly_approval_service),
):
    try:
        result = service.reject(session_id, reason=body.reason, rejected_by=body.rejected_by)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _assembly_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/assembly/expire", response_model=AssemblyApprovalActionResponse)
def assembly_expire(
    session_id: str,
    body: AssemblyExpireRequest,
    service: AssemblyApprovalService = Depends(get_assembly_approval_service),
):
    try:
        result = service.expire(session_id, reason=body.reason, expired_by=body.expired_by)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _assembly_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/assembly/reset-approval", response_model=AssemblyApprovalActionResponse)
def assembly_reset_approval(
    session_id: str,
    body: AssemblyResetApprovalRequest,
    service: AssemblyApprovalService = Depends(get_assembly_approval_service),
):
    try:
        result = service.reset_approval(session_id, reason=body.reason, reset_by=body.reset_by)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _assembly_approval_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/assembly/run", response_model=AssemblyRunResponse)
def assembly_run(
    session_id: str,
    body: AssemblyRunRequest | None = None,
    service: AssemblyRunService = Depends(get_assembly_run_service),
):
    """Run assembly dry-run or gated real execution for a session."""
    request = body or AssemblyRunRequest()
    try:
        result = service.run(
            session_id,
            dry_run=request.dry_run,
            confirm_real_assembly=request.confirm_real_assembly,
            overwrite=request.overwrite,
            timeout_seconds=request.timeout_seconds,
            triggered_by=request.triggered_by,
            reason=request.reason,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _assembly_run_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/sessions/{session_id}/voice/run", response_model=VoiceRunResponse)
def voice_run(
    session_id: str,
    body: VoiceRunRequest | None = None,
    service: VoiceRunService = Depends(get_voice_run_service),
):
    """Run mock live voice TTS — 11H-2a forces mock mode; no real ElevenLabs."""
    request = body or VoiceRunRequest()
    try:
        result = service.run(
            session_id,
            triggered_by=request.triggered_by,
            reason=request.reason,
            force_retry=request.force_retry,
            provider_mode=request.provider_mode,
            confirm_live_tts=request.confirm_live_tts,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = _voice_run_response(result)
    if isinstance(response, JSONResponse):
        return response
    return response


@app.post("/uat/run", response_model=UatRunResponse, status_code=202)
def uat_run(
    body: UatRunRequest,
    service: UatRuntimeService = Depends(get_uat_runtime_service),
):
    """Start one supervised UAT run asynchronously (Phase 12D)."""
    try:
        result = service.start_run(body)
    except Exception as error:
        status_code, code, message = map_uat_error(error)
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message}) from error
    return UatRunResponse(**result)


@app.get("/uat/status/{session_id}", response_model=UatRunResponse)
def uat_status(
    session_id: str,
    service: UatRuntimeService = Depends(get_uat_runtime_service),
):
    """Poll UAT run progress (Phase 12D)."""
    try:
        result = service.get_status(session_id)
    except Exception as error:
        status_code, code, message = map_uat_error(error)
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message}) from error
    return UatRunResponse(**result)


@app.post("/uat/review/{session_id}", response_model=UatReviewResponse, status_code=201)
def uat_review(
    session_id: str,
    body: UatReviewRequest,
    service: UatRuntimeService = Depends(get_uat_runtime_service),
):
    """Persist human UAT review scores (Phase 12D)."""
    try:
        result = service.submit_review(session_id, body)
    except Exception as error:
        status_code, code, message = map_uat_error(error)
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message}) from error
    return UatReviewResponse(**result)


@app.get("/uat/artifacts/{session_id}/final-video")
def uat_final_video(
    session_id: str,
    store=Depends(get_session_store),
):
    """Stream FINAL_PUBLISH_READY.mp4 for UAT preview (Phase 12E)."""
    from content_brain.execution.assembly_models import EXPECTED_OUTPUT
    from content_brain.execution.provider_categories import CATEGORY_ASSEMBLY_GENERATION
    from content_brain.execution.uat_runtime_profile import UAT_SESSION_PREFIX

    if not str(session_id).startswith(UAT_SESSION_PREFIX):
        raise HTTPException(status_code=404, detail={"code": "UAT_SESSION_NOT_FOUND", "message": "Not a UAT session"})

    video_path = store.artifact_dir(session_id, CATEGORY_ASSEMBLY_GENERATION) / EXPECTED_OUTPUT
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "UAT_VIDEO_NOT_FOUND", "message": "Final video not ready"})

    return FileResponse(video_path, media_type="video/mp4", filename=EXPECTED_OUTPUT)


@app.post("/runway-live-smoke/start", response_model=RunwayLiveSmokeRuntimeResponse, status_code=202)
def runway_live_smoke_start(
    body: RunwayLiveSmokeStartRequest,
    service: RunwayLiveSmokeRuntimeService = Depends(get_runway_live_smoke_service),
):
    """Start Phase H live smoke run with Runtime Studio UI approval surface."""
    result = service.start_run(
        story_idea=body.story_idea,
        project_id=body.project_id,
        operator=body.operator,
        simulate=body.simulate,
        clip_count=body.clip_count,
        execution_mode=body.execution_mode,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    return RunwayLiveSmokeRuntimeResponse(**result)


@app.get("/runway-live-smoke/status", response_model=RunwayLiveSmokeRuntimeResponse)
def runway_live_smoke_status(
    service: RunwayLiveSmokeRuntimeService = Depends(get_runway_live_smoke_service),
):
    result = service.snapshot()
    return RunwayLiveSmokeRuntimeResponse(**result)


@app.get("/runway-live-smoke/handoff-preview", response_model=RunwayLiveSmokeRuntimeResponse)
def runway_live_smoke_handoff_preview(
    story_idea: str = "",
    clip_count: int = 3,
    service: RunwayLiveSmokeRuntimeService = Depends(get_runway_live_smoke_service),
):
    result = service.handoff_preview(story_idea=story_idea, clip_count=clip_count)
    return RunwayLiveSmokeRuntimeResponse(**result)


@app.post("/runway-live-smoke/connect-ui", response_model=RunwayLiveSmokeRuntimeResponse)
def runway_live_smoke_connect_ui(
    service: RunwayLiveSmokeRuntimeService = Depends(get_runway_live_smoke_service),
):
    result = service.connect_ui()
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)
    return RunwayLiveSmokeRuntimeResponse(**result)


@app.post("/runway-live-smoke/approve", response_model=RunwayLiveSmokeRuntimeResponse)
def runway_live_smoke_approve(
    body: RunwayLiveSmokeActionRequest,
    service: RunwayLiveSmokeRuntimeService = Depends(get_runway_live_smoke_service),
):
    result = service.approve(operator=body.operator)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    return RunwayLiveSmokeRuntimeResponse(**result)


@app.post("/runway-live-smoke/image-ready", response_model=RunwayLiveSmokeRuntimeResponse)
def runway_live_smoke_image_ready(
    body: RunwayLiveSmokeActionRequest,
    service: RunwayLiveSmokeRuntimeService = Depends(get_runway_live_smoke_service),
):
    result = service.image_ready(operator=body.operator)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    return RunwayLiveSmokeRuntimeResponse(**result)


@app.post("/runway-live-smoke/cancel", response_model=RunwayLiveSmokeRuntimeResponse)
def runway_live_smoke_cancel(
    body: RunwayLiveSmokeActionRequest,
    service: RunwayLiveSmokeRuntimeService = Depends(get_runway_live_smoke_service),
):
    result = service.cancel(operator=body.operator, reason=body.reason or "ui_cancel")
    return RunwayLiveSmokeRuntimeResponse(**result)


@app.get(
    "/content-brain-test-studio/preflight",
    response_model=ContentBrainTestStudioPreflightResponse,
)
def content_brain_test_studio_preflight(
    service=Depends(get_content_brain_test_studio_service),
):
    return ContentBrainTestStudioPreflightResponse(**service.preflight())


@app.post(
    "/content-brain-test-studio/open-export",
    response_model=ContentBrainTestStudioOpenExportResponse,
)
def content_brain_test_studio_open_export(
    body: ContentBrainTestStudioOpenExportRequest,
    service=Depends(get_content_brain_test_studio_service),
):
    result = service.open_export_folder(body.path)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return ContentBrainTestStudioOpenExportResponse(**result)


@app.post(
    "/content-brain-test-studio/run",
    response_model=ContentBrainTestStudioRunResponse,
)
def content_brain_test_studio_run(
    body: ContentBrainTestStudioRunRequest,
    service=Depends(get_content_brain_test_studio_service),
):
    """Run Content Brain intelligence pipeline (no Runway / no media generation)."""
    result = service.run_test(body.model_dump())
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return ContentBrainTestStudioRunResponse(**result)


@app.get("/content-brain-test-studio/status")
def content_brain_test_studio_status(
    service=Depends(get_content_brain_test_studio_service),
):
    return service.status()


@app.get(
    "/topic-universe-studio/preflight",
    response_model=TopicUniversePreflightResponse,
)
def topic_universe_studio_preflight(
    service=Depends(get_topic_universe_studio_service),
):
    return TopicUniversePreflightResponse(**service.preflight())


@app.post(
    "/topic-universe-studio/generate",
    response_model=TopicUniverseGenerateResponse,
)
def topic_universe_studio_generate(
    body: TopicUniverseGenerateRequest,
    service=Depends(get_topic_universe_studio_service),
):
    """Generate SEO title bank from broad category topics (no media generation)."""
    result = service.generate(body.model_dump())
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return TopicUniverseGenerateResponse(**result)


@app.post(
    "/topic-universe-studio/handoff-e2e",
    response_model=TopicUniverseHandoffResponse,
)
def topic_universe_studio_handoff_e2e(
    body: TopicUniverseHandoffRequest,
    service=Depends(get_topic_universe_studio_service),
):
    """Pass a selected title into Content Brain E2E Micro Test."""
    result = service.handoff_to_e2e(body.model_dump())
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return TopicUniverseHandoffResponse(**result)


@app.post(
    "/topic-universe-studio/open-export",
    response_model=TopicUniverseOpenExportResponse,
)
def topic_universe_studio_open_export(
    body: TopicUniverseOpenExportRequest,
    service=Depends(get_topic_universe_studio_service),
):
    result = service.open_export_folder(body.path)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return TopicUniverseOpenExportResponse(**result)


@app.get("/topic-universe-studio/status")
def topic_universe_studio_status(
    service=Depends(get_topic_universe_studio_service),
):
    return service.status()


def main():
    import uvicorn

    uvicorn.run(
        "ui.api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
