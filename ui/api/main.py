"""
ModirAgentOS API — Phase 10C Execution Center V2.

Session read endpoints + Phase 10H queue + Phase 10I/10J provider runtime dispatch.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from ui.api.dependencies import (
    get_automation_service,
    get_browser_operations_service,
    get_operations_control_service,
    get_product_studio_service,
    get_platform_service,
    get_project_root,
    get_queue_service,
    get_runtime_service,
    get_runway_live_smoke_service,
    get_runway_runtime_bridge_service,
    get_session_service,
    get_session_store,
    get_assembly_approval_service,
    get_assembly_run_service,
    get_upload_service,
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
from ui.api.schemas.runway_runtime_bridge import (
    RunwayRuntimeGenerateRequest,
    RunwayRuntimeGenerateResponse,
    RunwayRuntimeStatusResponse,
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
from ui.api.schemas.product_studio import (
    ChannelProfileDTO,
    ChannelLogoStatusDTO,
    ChannelProfileSuggestRequest,
    ChannelProfileSuggestionDTO,
    CreateVideoGenerateRequest,
    CreateVideoGenerateResponse,
    CreateVideoPreflightRequest,
    CreateVideoPreflightResponse,
    ElevenLabsConnectionStatusDTO,
    AssetLibraryResponse,
    LatestResultsResponse,
    ScheduleJobsResponse,
    SchedulePreviewResponse,
    UpgradeUploadResponse,
    VideoSchedulePlanDTO,
)
from ui.api.schemas.platform import (
    AuthConfigResponse,
    AuthMeResponse,
    AuthSessionResponse,
    AutomationCenterDTO,
    AutomationCenterUpdateRequest,
    AutomationJobCreateRequest,
    AutomationQueueJobRequest,
    AutomationStatusResponse,
    AutomationResetDailyCounterResponse,
    BrowserActionResponse,
    BrowserHealthResponse,
    CommentDraftActionRequest,
    CommentDraftRequest,
    CreateLocalUserRequest,
    CredentialSaveRequest,
    CredentialsListResponse,
    CredentialTestResponse,
    LoginRequest,
    RunHistoryResponse,
    RunwaySessionResponse,
    PlatformSchedulerUpdateRequest,
    UploadPrepareRequest,
    UploadCenterStatusResponse,
    UploadMetadataRequest,
    UploadPackagePrepareRequest,
    UploadYouTubeAuthExchangeRequest,
    UploadYouTubeFirstAuthRequest,
    UploadYouTubePublishPackageRequest,
    UploadYouTubeSubmitRequest,
    UploadInstagramSubmitRequest,
    UploadTikTokSubmitRequest,
)
from content_brain.upgrades.patch_upload_service import PatchUploadError, upload_patch_package

API_HOST = os.getenv("MODIR_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("MODIR_API_PORT", "8765"))

_cors_origins = os.getenv(
    "MODIR_API_CORS_ORIGINS",
    "http://127.0.0.1:5173,http://127.0.0.1:5174,http://localhost:5173,http://localhost:5174",
)
CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]

API_VERSION = "0.6.0"

logger = logging.getLogger(__name__)


def _bootstrap_platform_runtime() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        get_platform_service().credentials.apply_all_to_env()
    except Exception as exc:
        logger.warning("credential bootstrap failed: %s", exc)
    try:
        from content_brain.platform.api_runtime_diagnostics import init_api_runtime_diagnostics

        init_api_runtime_diagnostics(get_project_root(), api_version=API_VERSION)
    except Exception as exc:
        logger.warning("runtime diagnostics init failed: %s", exc)
    try:
        from content_brain.automation.background_scheduler import start_background_scheduler

        result = start_background_scheduler(get_project_root())
        logger.info("automation scheduler startup: %s", result)
    except Exception as exc:
        logger.exception("automation scheduler failed to start: %s", exc)


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    _bootstrap_platform_runtime()
    yield
    try:
        from content_brain.automation.background_scheduler import stop_background_scheduler

        stop_background_scheduler()
    except Exception as exc:
        logger.warning("automation scheduler shutdown failed: %s", exc)


app = FastAPI(
    title="ModirAgentOS API",
    version=API_VERSION,
    description="Execution Center V2 — sessions + queue + provider runtime + operator control.",
    lifespan=_app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


@app.get("/platform/runtime-diagnostics")
def platform_runtime_diagnostics():
    from content_brain.platform.api_runtime_diagnostics import (
        build_runtime_diagnostics,
        compute_api_build_id,
        get_live_runtime_diagnostics,
        is_api_process_stale,
    )

    root = get_project_root()
    live = get_live_runtime_diagnostics(root)
    current_build_id = compute_api_build_id(root)
    return {
        "live": live,
        "current_build_id": current_build_id,
        "api_process_stale": is_api_process_stale(root, live_build_id=str(live.get("api_build_id") or "")),
        "expected": build_runtime_diagnostics(root, api_version=API_VERSION),
    }


class CancelQueueRequest(BaseModel):
    reason: str = "cancelled"


@app.get("/health")
def health():
    from content_brain.platform.api_runtime_diagnostics import (
        compute_api_build_id,
        get_live_runtime_diagnostics,
        is_api_process_stale,
    )

    root = get_project_root()
    live = get_live_runtime_diagnostics(root)
    return {
        "status": "ok",
        "service": "modiragent-api",
        "version": API_VERSION,
        "api_build_id": live.get("api_build_id") or compute_api_build_id(root),
        "orchestrator_version": live.get("orchestrator_version") or "",
        "startup_time": live.get("startup_time") or "",
        "assembly_bridge_enabled": live.get("assembly_bridge_enabled"),
        "branding_publish_enabled": live.get("branding_publish_enabled"),
        "youtube_metadata_enabled": live.get("youtube_metadata_enabled"),
        "youtube_upload_enabled": live.get("youtube_upload_enabled"),
        "api_process_stale": is_api_process_stale(
            root,
            live_build_id=str(live.get("api_build_id") or ""),
        ),
    }


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


@app.post("/runway/runtime/generate", response_model=RunwayRuntimeGenerateResponse, status_code=202)
def runway_runtime_generate(
    body: RunwayRuntimeGenerateRequest,
    service=Depends(get_runway_runtime_bridge_service),
):
    """Start Phase I Runway generation for AI Content Factory via runtime bridge."""
    result = service.start_generate(body.model_dump())
    if not result.get("ok"):
        code = str(result.get("error_code") or "")
        if code in {
            "unsupported_provider",
            "unsupported_model",
            "invalid_model_for_provider",
            "prompt_too_long",
            "unsupported_aspect_ratio",
            "validation_error",
            "missing_story_idea",
            "missing_starter_image_prompt",
            "invalid_clip_prompts",
            "clip_prompt_count_mismatch",
            "missing_project_id",
            "invalid_prompt_package",
            "invalid_clip_duration_seconds",
        }:
            raise HTTPException(status_code=400, detail=result)
        if code == "run_id_active":
            raise HTTPException(status_code=409, detail=result)
        if code == "browser_unavailable":
            raise HTTPException(status_code=503, detail=result)
        raise HTTPException(status_code=400, detail=result)
    return RunwayRuntimeGenerateResponse(**result)


@app.get("/runway/runtime/status/{run_id}", response_model=RunwayRuntimeStatusResponse)
def runway_runtime_status(
    run_id: str,
    service=Depends(get_runway_runtime_bridge_service),
):
    result = service.get_status(run_id)
    if not result.get("ok") and result.get("error_code") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    return RunwayRuntimeStatusResponse(**result)


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


# --- Product Studio (UI-PRO-2) — planning UI only, no runtime automation changes ---


def _normalize_create_video_payload(body: CreateVideoGenerateRequest | CreateVideoPreflightRequest) -> dict:
    payload = body.model_dump()
    topic_source = payload.pop("topic_source", None)
    if topic_source and not payload.get("topic_mode"):
        payload["topic_mode"] = topic_source
    if not payload.get("provider"):
        payload["provider"] = ""
    return payload


@app.get("/product/channel-profile", response_model=ChannelProfileDTO)
def product_get_channel_profile(service=Depends(get_product_studio_service)):
    return ChannelProfileDTO(**service.get_channel_profile())


@app.put("/product/channel-profile", response_model=ChannelProfileDTO)
def product_save_channel_profile_put(body: ChannelProfileDTO, service=Depends(get_product_studio_service)):
    return ChannelProfileDTO(**service.save_channel_profile(body.model_dump()))


@app.post("/product/channel-profile", response_model=ChannelProfileDTO)
def product_save_channel_profile_post(body: ChannelProfileDTO, service=Depends(get_product_studio_service)):
    return ChannelProfileDTO(**service.save_channel_profile(body.model_dump()))


@app.post("/product/channel-profile/suggest", response_model=ChannelProfileSuggestionDTO)
def product_suggest_channel_profile(body: ChannelProfileSuggestRequest, service=Depends(get_product_studio_service)):
    return ChannelProfileSuggestionDTO(**service.suggest_channel_profile(body.model_dump()))


@app.get("/product/last-topic")
def product_get_last_topic(service=Depends(get_product_studio_service)):
    return service.get_last_topic()


@app.put("/product/last-topic")
def product_save_last_topic(body: dict[str, Any], service=Depends(get_product_studio_service)):
    return service.save_last_topic(
        topic=str(body.get("topic") or ""),
        topic_mode=str(body.get("topic_mode") or "custom"),
    )


@app.get("/product/channel-assets/logo", response_model=ChannelLogoStatusDTO)
def product_get_channel_logo(service=Depends(get_product_studio_service)):
    return ChannelLogoStatusDTO(**service.get_channel_logo_status())


@app.get("/product/channel-assets/logo/file")
def product_get_channel_logo_file(service=Depends(get_product_studio_service)):
    try:
        asset_path = service.get_branding_asset_path("logo")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if asset_path is None or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Logo not found")
    media_type = "image/jpeg" if asset_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return FileResponse(asset_path, media_type=media_type, filename=asset_path.name)


@app.post("/product/channel-assets/logo")
async def product_upload_channel_logo(file: UploadFile = File(...), service=Depends(get_product_studio_service)):
    payload = await file.read()
    try:
        return service.save_channel_logo(
            payload,
            content_type=str(file.content_type or ""),
            filename=str(file.filename or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/product/channel-assets/{asset_kind}")
async def product_upload_branding_asset(
    asset_kind: str,
    file: UploadFile = File(...),
    service=Depends(get_product_studio_service),
):
    payload = await file.read()
    try:
        return service.save_branding_asset(
            asset_kind,
            payload,
            content_type=str(file.content_type or ""),
            filename=str(file.filename or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/product/channel-assets/{asset_kind}/file")
def product_get_branding_asset_file(asset_kind: str, service=Depends(get_product_studio_service)):
    try:
        asset_path = service.get_branding_asset_path(asset_kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if asset_path is None or not asset_path.is_file():
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_kind}")
    media_type = "video/mp4" if asset_path.suffix.lower() == ".mp4" else "image/png"
    if asset_path.suffix.lower() in {".jpg", ".jpeg"}:
        media_type = "image/jpeg"
    return FileResponse(asset_path, media_type=media_type, filename=asset_path.name)


@app.get("/product/elevenlabs/connection-status", response_model=ElevenLabsConnectionStatusDTO)
def product_elevenlabs_connection_status(service=Depends(get_product_studio_service)):
    return ElevenLabsConnectionStatusDTO(**service.get_elevenlabs_connection_status())


@app.post("/product/elevenlabs/test-connection", response_model=ElevenLabsConnectionStatusDTO)
def product_elevenlabs_test_connection(service=Depends(get_product_studio_service)):
    return ElevenLabsConnectionStatusDTO(**service.test_elevenlabs_connection())


@app.post("/product/create-video/preflight", response_model=CreateVideoPreflightResponse)
def product_create_video_preflight(body: CreateVideoPreflightRequest, service=Depends(get_product_studio_service)):
    return CreateVideoPreflightResponse(**service.create_video_preflight(body.model_dump()))


@app.post("/product/create-video/generate", response_model=CreateVideoGenerateResponse, status_code=202)
def product_create_video_generate(
    body: CreateVideoGenerateRequest,
    service=Depends(get_product_studio_service),
    runway_service=Depends(get_runway_live_smoke_service),
):
    """Start Phase I FULL_AUTO via existing Runway live smoke runner."""
    payload = _normalize_create_video_payload(body)
    result = service.create_video_generate(payload, runway_service=runway_service)
    if not result.get("ok") and result.get("wired") and result.get("status") == "failed":
        raise HTTPException(status_code=409, detail=result)
    return CreateVideoGenerateResponse(**result)


@app.get("/product/schedules")
def product_list_schedules(service=Depends(get_product_studio_service)):
    return {"schedules": service.list_schedules()}


@app.post("/product/schedules")
def product_save_schedule(body: VideoSchedulePlanDTO, service=Depends(get_product_studio_service)):
    try:
        return service.save_schedule(body.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/product/schedules/preview", response_model=SchedulePreviewResponse)
def product_preview_schedule(body: VideoSchedulePlanDTO, service=Depends(get_product_studio_service)):
    try:
        return SchedulePreviewResponse(**service.preview_schedule(body.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/product/schedules/{schedule_id}/generate-jobs", response_model=ScheduleJobsResponse)
def product_generate_schedule_jobs(
    schedule_id: str,
    only_date: Optional[str] = None,
    service=Depends(get_product_studio_service),
):
    try:
        return ScheduleJobsResponse(**service.generate_schedule_jobs(schedule_id, only_date=only_date))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/product/schedules/{schedule_id}/disable")
def product_disable_schedule(schedule_id: str, service=Depends(get_product_studio_service)):
    return service.disable_schedule(schedule_id)


@app.get("/product/results/latest", response_model=LatestResultsResponse)
def product_latest_results(
    run_id: str = "",
    run_dir: str = "",
    service=Depends(get_product_studio_service),
):
    return LatestResultsResponse(**service.get_results(run_id=run_id, run_dir=run_dir))


@app.get("/product/assets/library", response_model=AssetLibraryResponse)
def product_asset_library(limit: int = 20, service=Depends(get_product_studio_service)):
    return AssetLibraryResponse(**service.get_asset_library(limit=limit))


@app.get("/product/upgrade-center/patches")
def product_upgrade_patches(service=Depends(get_product_studio_service)):
    registry = service.list_upgrade_patches()
    return {
        "patches": registry.get("patches") or [],
        "future_patches": registry.get("future_patches") or [],
        "uploaded_patches": registry.get("uploaded_patches") or [],
        "note": "Upload patch packages here. Preview, backup, and apply remain required before installation.",
    }


@app.post("/upgrades/upload", response_model=UpgradeUploadResponse)
async def upgrades_upload_patch(file: UploadFile = File(...)):
    """Store uploaded patch package — never auto-applies."""
    filename = str(file.filename or "patch.zip")
    content = await file.read()
    try:
        result = upload_patch_package(
            project_root=get_project_root(),
            filename=filename,
            content=content,
        )
    except PatchUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UpgradeUploadResponse(**result, message="Patch uploaded. Preview and apply separately.")


@app.get("/platform/credentials", response_model=CredentialsListResponse)
def platform_list_credentials(service=Depends(get_platform_service)):
    return CredentialsListResponse(**service.list_credentials())


@app.post("/platform/credentials/save")
def platform_save_credential(body: CredentialSaveRequest, service=Depends(get_platform_service)):
    service.save_credential(body.provider_id, body.secret)
    return {"ok": True, "provider_id": body.provider_id, "message": "Credential saved."}


@app.post("/platform/credentials/test", response_model=CredentialTestResponse)
def platform_test_credential(body: CredentialSaveRequest, service=Depends(get_platform_service)):
    return CredentialTestResponse(**service.test_credential(body.provider_id))


@app.get("/platform/auth/config", response_model=AuthConfigResponse)
def platform_auth_config(service=Depends(get_platform_service)):
    return AuthConfigResponse(**service.get_auth_config())


@app.post("/platform/auth/local-auto-login", response_model=AuthSessionResponse)
def platform_local_auto_login(service=Depends(get_platform_service)):
    result = service.auto_login_local()
    if not result.get("ok"):
        raise HTTPException(status_code=403, detail=str(result.get("message") or "Local auto-login unavailable"))
    return AuthSessionResponse(
        ok=True,
        token=str(result.get("token") or ""),
        username=str(result.get("username") or ""),
        message=str(result.get("message") or ""),
    )


@app.get("/platform/auth/user")
def platform_get_local_user(service=Depends(get_platform_service)):
    return service.get_local_user()


@app.post("/platform/auth/create-user", response_model=AuthSessionResponse)
def platform_create_local_user(body: CreateLocalUserRequest, service=Depends(get_platform_service)):
    try:
        service.create_local_user(body.username, body.password)
        return AuthSessionResponse(**service.login(body.username, body.password))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/platform/auth/login", response_model=AuthSessionResponse)
def platform_login(body: LoginRequest, service=Depends(get_platform_service)):
    result = service.login(body.username, body.password)
    if not result.get("ok"):
        raise HTTPException(status_code=401, detail=str(result.get("message") or "Login failed"))
    return AuthSessionResponse(**result)


@app.post("/platform/auth/logout")
def platform_logout(authorization: str | None = Header(default=None), service=Depends(get_platform_service)):
    token = (authorization or "").replace("Bearer ", "").strip()
    return service.logout(token)


@app.get("/platform/auth/me", response_model=AuthMeResponse)
def platform_auth_me(authorization: str | None = Header(default=None), service=Depends(get_platform_service)):
    token = (authorization or "").replace("Bearer ", "").strip()
    return AuthMeResponse(**service.me(token))


@app.get("/platform/browser/health", response_model=BrowserHealthResponse)
def platform_browser_health(service=Depends(get_platform_service)):
    return BrowserHealthResponse(**service.browser_health())


@app.post("/platform/browser/open", response_model=BrowserActionResponse)
def platform_browser_open(service=Depends(get_platform_service)):
    from automation.browser_launcher import launch_controlled_chrome

    launch = launch_controlled_chrome(get_project_root())
    health = service.browser_health()
    return BrowserActionResponse(
        ok=bool(launch.get("success")),
        message=str(launch.get("message") or ""),
        health=BrowserHealthResponse(**health),
    )


@app.post("/platform/browser/reconnect", response_model=BrowserActionResponse)
def platform_browser_reconnect(service=Depends(get_platform_service)):
    payload = service.browser_reconnect()
    return BrowserActionResponse(
        ok=bool(payload.get("ok")),
        message=str(payload.get("message") or ""),
        health=BrowserHealthResponse(**(payload.get("health") or {})),
    )


@app.post("/platform/browser/refresh-runway", response_model=BrowserActionResponse)
def platform_browser_refresh_runway(force: bool = False, service=Depends(get_platform_service)):
    payload = service.browser_refresh_runway(force=force)
    return BrowserActionResponse(
        ok=bool(payload.get("ok")),
        message=str(payload.get("message") or ""),
        blocked=bool(payload.get("blocked")),
        requires_confirmation=bool(payload.get("requires_confirmation")),
        health=BrowserHealthResponse(**(payload.get("health") or {})),
    )


@app.get("/platform/browser/runway-session", response_model=RunwaySessionResponse)
def platform_runway_session_status(validate: bool = False, service=Depends(get_platform_service)):
    return RunwaySessionResponse(**service.runway_session_status(validate=validate))


@app.post("/platform/browser/connect-runway", response_model=RunwaySessionResponse)
def platform_connect_runway_browser(service=Depends(get_platform_service)):
    payload = service.connect_runway_browser()
    status = payload.get("status") or {}
    return RunwaySessionResponse(
        connected=bool(payload.get("connected")),
        disconnected=not bool(payload.get("connected")),
        message=str(payload.get("message") or status.get("message") or ""),
        validated=bool(status.get("validated")),
        updated_at=str(status.get("updated_at") or ""),
        session_path=str(status.get("session_path") or ""),
        awaiting_login=bool(payload.get("awaiting_login")),
    )


@app.post("/platform/browser/save-runway-session", response_model=RunwaySessionResponse)
def platform_save_runway_browser_session(service=Depends(get_platform_service)):
    payload = service.save_runway_browser_session()
    status = payload.get("status") or {}
    return RunwaySessionResponse(
        connected=bool(payload.get("connected")),
        disconnected=not bool(payload.get("connected")),
        message=str(payload.get("message") or ""),
        validated=bool(status.get("validated")),
        updated_at=str(status.get("updated_at") or ""),
        session_path=str(status.get("session_path") or ""),
        awaiting_login=False,
    )


@app.get("/platform/runs/history", response_model=RunHistoryResponse)
def platform_run_history(limit: int = 20, service=Depends(get_platform_service)):
    return RunHistoryResponse(**service.run_history(limit=limit))


@app.get("/platform/automation-center", response_model=AutomationCenterDTO)
def platform_get_automation_center(service=Depends(get_platform_service)):
    return AutomationCenterDTO(**service.get_automation_center())


@app.post("/platform/automation-center", response_model=AutomationCenterDTO)
def platform_update_automation_center(body: AutomationCenterUpdateRequest, service=Depends(get_platform_service)):
    return AutomationCenterDTO(**service.update_automation_center(body.model_dump(exclude_none=True)))


@app.post("/platform/automation-center/queue", response_model=AutomationCenterDTO)
def platform_queue_automation_job(body: AutomationQueueJobRequest, service=Depends(get_platform_service)):
    return AutomationCenterDTO(**service.queue_automation_job(body.model_dump()))


@app.post("/platform/automation-center/start-next", response_model=AutomationCenterDTO)
def platform_start_next_automation_job(
    automation=Depends(get_automation_service),
    product_service=Depends(get_product_studio_service),
    runway_service=Depends(get_runway_live_smoke_service),
):
    automation.start_next(product_service=product_service, runway_service=runway_service)
    return AutomationCenterDTO(**automation.center.load())


@app.get("/automation/status", response_model=AutomationStatusResponse)
def automation_status(service=Depends(get_automation_service)):
    return AutomationStatusResponse(**service.get_status())


@app.get("/automation/jobs")
def automation_jobs(service=Depends(get_automation_service)):
    return service.list_jobs()


@app.post("/automation/jobs")
def automation_create_job(body: AutomationJobCreateRequest, service=Depends(get_automation_service)):
    return service.create_job(body.model_dump())


@app.post("/automation/start-next")
def automation_start_next(
    service=Depends(get_automation_service),
    product_service=Depends(get_product_studio_service),
    runway_service=Depends(get_runway_live_smoke_service),
):
    return service.start_next(product_service=product_service, runway_service=runway_service)


@app.post("/automation/start")
def automation_start(
    service=Depends(get_automation_service),
    product_service=Depends(get_product_studio_service),
    runway_service=Depends(get_runway_live_smoke_service),
):
    return service.start_automation(product_service=product_service, runway_service=runway_service)


@app.post("/automation/pause")
def automation_pause(service=Depends(get_automation_service)):
    return service.pause()


@app.post("/automation/resume")
def automation_resume(service=Depends(get_automation_service)):
    return service.resume()


@app.post("/automation/cancel/{job_id}")
def automation_cancel_job(job_id: str, service=Depends(get_automation_service)):
    return service.cancel_job(job_id)


@app.post("/automation/reset-daily-counter", response_model=AutomationResetDailyCounterResponse)
def automation_reset_daily_counter(platform: str | None = None, service=Depends(get_automation_service)):
    return AutomationResetDailyCounterResponse(**service.reset_daily_counter(platform=platform))


@app.get("/automation/platform-schedules")
def automation_platform_schedules(service=Depends(get_automation_service)):
    return service.get_platform_scheduler()


@app.post("/automation/platform-schedules")
def automation_update_platform_schedules(body: PlatformSchedulerUpdateRequest, service=Depends(get_automation_service)):
    return service.update_platform_scheduler(body.model_dump(exclude_none=True))


@app.post("/upload/prepare")
def upload_prepare(body: UploadPrepareRequest, service=Depends(get_automation_service)):
    return service.prepare_upload(body.model_dump())


@app.post("/upload/youtube/submit")
def upload_youtube_submit(body: UploadYouTubeSubmitRequest, service=Depends(get_automation_service)):
    return service.submit_youtube(body.model_dump())


@app.post("/upload/instagram/submit")
def upload_instagram_submit(body: UploadInstagramSubmitRequest, service=Depends(get_automation_service)):
    return service.submit_instagram(body.model_dump())


@app.get("/upload/instagram/auth-status")
def upload_instagram_auth_status(service=Depends(get_upload_service)):
    return service.instagram_auth_status()


@app.get("/media/video/{run_id}")
def serve_pwmap_run_video(run_id: str, project_root=Depends(get_project_root)):
    from content_brain.upload.media_video_resolver import is_valid_run_id, resolve_pwmap_run_video

    if not is_valid_run_id(run_id):
        raise HTTPException(status_code=400, detail={"code": "INVALID_RUN_ID", "message": "Invalid run id"})
    video_path = resolve_pwmap_run_video(project_root, run_id)
    if video_path is None or not video_path.is_file():
        raise HTTPException(
            status_code=404,
            detail={"code": "VIDEO_NOT_FOUND", "message": "Video file not found for run"},
        )
    return FileResponse(path=str(video_path), media_type="video/mp4", filename=video_path.name)


@app.get("/upload/instagram/public/{token}.mp4")
def upload_instagram_public_video(token: str, service=Depends(get_upload_service)):
    from content_brain.upload.instagram_video_stager import resolve_staged_video_path

    video_path = resolve_staged_video_path(service.project_root, token)
    if video_path is None:
        raise HTTPException(status_code=404, detail={"code": "INSTAGRAM_STAGED_VIDEO_NOT_FOUND", "message": "Staged video not found"})
    return FileResponse(video_path, media_type="video/mp4", filename=f"{token}.mp4")


@app.post("/upload/tiktok/submit")
def upload_tiktok_submit(body: UploadTikTokSubmitRequest, service=Depends(get_automation_service)):
    return service.submit_tiktok(body.model_dump())


@app.get("/upload/status", response_model=UploadCenterStatusResponse)
def upload_center_status(run_id: str = "", service=Depends(get_upload_service)):
    return UploadCenterStatusResponse(**service.get_status(run_id=run_id))


@app.post("/upload/metadata/generate")
def upload_generate_metadata(body: UploadMetadataRequest, service=Depends(get_upload_service)):
    return service.generate_metadata(body.model_dump())


@app.post("/upload/packages/prepare")
def upload_prepare_packages(body: UploadPackagePrepareRequest, service=Depends(get_upload_service)):
    return service.prepare_packages(body.model_dump())


@app.get("/upload/youtube/auth")
def upload_youtube_auth_connect(service=Depends(get_upload_service)):
    """One-time YouTube OAuth: opens Google login in browser and saves token on success."""
    from content_brain.upload.youtube_auth import _token_path, _token_secrets_path

    result = service.youtube_oauth_connect(open_browser=True)
    ok = bool(result.get("ok") or result.get("authorized"))
    channel = str(result.get("channel_name") or "")
    token_path = str(result.get("token_path") or _token_path(service.project_root))
    secrets_path = str(result.get("token_secrets_path") or _token_secrets_path(service.project_root))
    if ok:
        body = (
            "<html><body style='font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem'>"
            "<h2>YouTube connected</h2>"
            f"<p>Channel: <strong>{channel or 'Connected'}</strong></p>"
            f"<p>Token saved to:<br><code>{token_path}</code><br><code>{secrets_path}</code></p>"
            "<p>You can close this window and return to Settings.</p>"
            "</body></html>"
        )
        return HTMLResponse(content=body, status_code=200)
    error = str(result.get("error") or result.get("reason") or "oauth_failed")
    details = str(result.get("details") or "")
    body = (
        "<html><body style='font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem'>"
        "<h2>YouTube connection failed</h2>"
        f"<p><strong>{error}</strong></p>"
        f"<p>{details}</p>"
        "<p>Ensure <code>secrets/client_secret*.json</code> exists, then try again from Settings.</p>"
        "</body></html>"
    )
    return HTMLResponse(content=body, status_code=400)


@app.get("/upload/youtube/auth/status")
def upload_youtube_auth_status(service=Depends(get_upload_service)):
    return service.youtube_auth_status()


@app.post("/upload/youtube/auth/start")
def upload_youtube_auth_start(service=Depends(get_upload_service)):
    return service.youtube_auth_start()


@app.post("/upload/youtube/auth/exchange")
def upload_youtube_auth_exchange(body: UploadYouTubeAuthExchangeRequest, service=Depends(get_upload_service)):
    return service.youtube_auth_exchange(body.model_dump())


@app.post("/upload/youtube/auth/first")
def upload_youtube_auth_first(body: UploadYouTubeFirstAuthRequest, service=Depends(get_upload_service)):
    return service.youtube_first_authorization(body.model_dump())


@app.get("/upload/youtube/auth/result")
def upload_youtube_auth_result(service=Depends(get_upload_service)):
    return service.youtube_auth_result()


@app.get("/upload/youtube/auth/readiness")
def upload_youtube_auth_readiness(service=Depends(get_upload_service)):
    return service.youtube_oauth_readiness()


@app.post("/upload/youtube/publish-package")
def upload_youtube_publish_package(body: UploadYouTubePublishPackageRequest, service=Depends(get_upload_service)):
    return service.submit_publish_package_upload(body.model_dump())


@app.get("/upload/youtube/result")
def upload_youtube_result(run_id: str = "", publish_dir: str = "", service=Depends(get_upload_service)):
    return service.get_publish_upload_result(run_id=run_id, publish_dir=publish_dir)


@app.get("/upload/caption/{platform}")
def upload_platform_caption(platform: str, run_id: str = "", service=Depends(get_upload_service)):
    return service.get_platform_caption(run_id=run_id, platform=platform)


@app.post("/comments/draft-reply")
def comments_draft_reply(body: CommentDraftRequest, service=Depends(get_automation_service)):
    return service.draft_comment_reply(body.model_dump())


@app.post("/comments/draft-reply/approve")
def comments_draft_reply_approve(body: CommentDraftActionRequest, service=Depends(get_automation_service)):
    return service.approve_comment_draft(body.model_dump())


@app.post("/comments/draft-reply/reject")
def comments_draft_reply_reject(body: CommentDraftActionRequest, service=Depends(get_automation_service)):
    return service.reject_comment_draft(body.model_dump())


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _listening_pids_on_port(port: int) -> set[int]:
    """Return PIDs listening on the given local TCP port."""
    pids: set[int] = set()
    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
        )
        port_token = f":{port}"
        for line in result.stdout.splitlines():
            if port_token not in line:
                continue
            upper = line.upper()
            if "LISTENING" not in upper and "ABH" not in upper:
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                pid = int(parts[-1])
            except ValueError:
                continue
            if pid > 0:
                pids.add(pid)
        return pids

    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    for token in result.stdout.split():
        try:
            pids.add(int(token))
        except ValueError:
            continue
    return pids


def release_port(port: int) -> None:
    """Terminate stale processes still bound to port before API startup."""
    current_pid = os.getpid()
    stale_pids = _listening_pids_on_port(port) - {current_pid}
    if not stale_pids:
        return

    for pid in sorted(stale_pids):
        logger.warning("Releasing port %s — terminating stale process pid=%s", port, pid)
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                check=False,
            )
        else:
            subprocess.run(["kill", "-9", str(pid)], capture_output=True, check=False)

    time.sleep(2)
    if is_port_in_use(port):
        logger.error("Port %s still in use after cleanup attempt", port)


def main():
    import uvicorn

    if is_port_in_use(API_PORT):
        logger.warning("Port %s is in use — cleaning up stale API process", API_PORT)
        release_port(API_PORT)

    uvicorn.run(
        "ui.api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
