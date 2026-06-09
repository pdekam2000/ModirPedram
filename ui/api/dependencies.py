from functools import lru_cache
from pathlib import Path

from content_brain.execution.session_store import ExecutionSessionStore

from ui.api.services.operations_control_service import OperationsControlService
from ui.api.services.queue_service import QueueService
from ui.api.services.runtime_service import RuntimeService
from ui.api.services.session_service import SessionService


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@lru_cache
def get_session_store() -> ExecutionSessionStore:
    return ExecutionSessionStore(get_project_root())


def get_session_service() -> SessionService:
    return SessionService(get_session_store())


def get_queue_service() -> QueueService:
    return QueueService(get_session_store())


def get_runtime_service() -> RuntimeService:
    return RuntimeService(get_session_store())


def get_operations_control_service() -> OperationsControlService:
    return OperationsControlService(get_session_store())


def get_voice_approval_service():
    from ui.api.voice_approval_service import VoiceApprovalService

    return VoiceApprovalService(get_session_store())


def get_voice_run_service():
    from ui.api.voice_run_service import VoiceRunService

    return VoiceRunService(get_session_store())


def get_subtitle_run_service():
    from ui.api.subtitle_run_service import SubtitleRunService

    return SubtitleRunService(get_session_store())


def get_assembly_run_service():
    from ui.api.assembly_run_service import AssemblyRunService

    return AssemblyRunService(get_session_store())


def get_assembly_approval_service():
    from ui.api.assembly_approval_service import AssemblyApprovalService

    return AssemblyApprovalService(get_session_store())


def get_uat_runtime_service():
    from ui.api.uat_runtime_service import UatRuntimeService

    return UatRuntimeService(get_session_store())


def get_runway_live_smoke_service():
    from ui.api.runway_live_smoke_service import RunwayLiveSmokeRuntimeService

    if not hasattr(get_runway_live_smoke_service, "_instance"):
        get_runway_live_smoke_service._instance = RunwayLiveSmokeRuntimeService()
    return get_runway_live_smoke_service._instance


def get_browser_operations_service():
    from ui.api.browser_operations_service import BrowserOperationsService

    return BrowserOperationsService(get_project_root())
