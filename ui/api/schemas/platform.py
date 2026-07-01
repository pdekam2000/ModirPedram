"""Platform foundation API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CredentialStatusDTO(BaseModel):
    provider_id: str
    label: str = ""
    configured: bool = False
    masked_value: str = ""
    testable: bool = False
    updated_at: str = ""


class CredentialSaveRequest(BaseModel):
    provider_id: str
    secret: str = ""


class CredentialTestResponse(BaseModel):
    ok: bool = False
    provider_id: str = ""
    message: str = ""


class CredentialsListResponse(BaseModel):
    providers: list[CredentialStatusDTO] = Field(default_factory=list)


class LocalUserPublicDTO(BaseModel):
    exists: bool = False
    username: str = ""
    created_at: str = ""
    updated_at: str = ""


class CreateLocalUserRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthSessionResponse(BaseModel):
    ok: bool = False
    token: str = ""
    username: str = ""
    message: str = ""


class AuthMeResponse(BaseModel):
    authenticated: bool = False
    username: str = ""


class AuthConfigResponse(BaseModel):
    local_mode: bool = True
    user_exists: bool = False
    username: str = ""


class BrowserHealthResponse(BaseModel):
    connected: bool = False
    disconnected: bool = True
    cdp_reachable: bool = False
    runway_tab_found: bool = False
    page_responsive: bool = False
    generation_active: bool = False
    generation_reason: str = ""
    last_heartbeat: str = ""
    cdp_url: str = ""
    message: str = ""
    refresh_allowed: bool = False
    reconnect_allowed: bool = True
    checks: list[dict[str, Any]] = Field(default_factory=list)


class BrowserActionResponse(BaseModel):
    ok: bool = False
    message: str = ""
    blocked: bool = False
    requires_confirmation: bool = False
    health: BrowserHealthResponse | None = None


class RunHistoryItemDTO(BaseModel):
    run_id: str = ""
    topic: str = ""
    run_dir: str = ""
    final_video_path: str = ""
    publish_dir: str = ""
    assembly_status: str = ""
    publish_status: str = ""
    created_at: str = ""


class RunHistoryResponse(BaseModel):
    latest: RunHistoryItemDTO | None = None
    runs: list[RunHistoryItemDTO] = Field(default_factory=list)


class AutomationCenterDTO(BaseModel):
    enabled: bool = False
    paused: bool = True
    daily_schedule_overview: list[dict[str, Any]] = Field(default_factory=list)
    queued_jobs: list[dict[str, Any]] = Field(default_factory=list)
    run_history: list[dict[str, Any]] = Field(default_factory=list)
    failed_jobs: list[dict[str, Any]] = Field(default_factory=list)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    updated_at: str = ""


class AutomationCenterUpdateRequest(BaseModel):
    enabled: bool | None = None
    paused: bool | None = None
    feature_flags: dict[str, bool] | None = None


class AutomationQueueJobRequest(BaseModel):
    title: str = ""
    topic: str = ""
    provider: str = "runway"


class AutomationJobCreateRequest(BaseModel):
    title: str = ""
    topic: str = ""
    duration: int = 30
    clip_count: int = 3
    platform_targets: list[str] = Field(default_factory=lambda: ["youtube_shorts"])
    scheduled_time: str = ""


class AutomationStatusResponse(BaseModel):
    version: str = ""
    enabled: bool = False
    paused: bool = True
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    running_job: dict[str, Any] | None = None
    next_job: dict[str, Any] | None = None
    queued_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    completed_today: int = 0
    max_jobs_per_day: int = 5
    jobs: dict[str, Any] = Field(default_factory=dict)
    comment_drafts: list[dict[str, Any]] = Field(default_factory=list)
    upload_packages: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: str = ""


class UploadPrepareRequest(BaseModel):
    topic: str = ""
    title: str = ""
    run_id: str = ""
    video_path: str = ""
    publish_package_path: str = ""
    platform_targets: list[str] = Field(default_factory=lambda: ["youtube_shorts"])


class UploadYouTubeSubmitRequest(BaseModel):
    package_dir: str = ""
    run_id: str = ""
    upload_package: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


class CommentDraftRequest(BaseModel):
    comment_text: str = ""
    video_topic: str = ""
    topic: str = ""
    channel_tone: str = ""
    language: str = ""
    use_openai: bool = True


class CommentDraftActionRequest(BaseModel):
    index: int = 0


class UploadCenterStatusResponse(BaseModel):
    version: str = ""
    run_id: str = ""
    topic: str = ""
    platform_targets: list[str] = Field(default_factory=list)
    upload_manifest: dict[str, Any] = Field(default_factory=dict)
    metadata_by_platform: dict[str, Any] = Field(default_factory=dict)
    youtube_auth: dict[str, Any] = Field(default_factory=dict)
    upload_root: str = ""
    publish_package_path: str = ""
    auto_upload_enabled: bool = False


class UploadMetadataRequest(BaseModel):
    topic: str = ""
    run_id: str = ""
    video_path: str = ""
    publish_package_path: str = ""
    platform_targets: list[str] = Field(default_factory=list)
    use_openai: bool = True


class UploadPackagePrepareRequest(BaseModel):
    topic: str = ""
    run_id: str = ""
    video_path: str = ""
    publish_package_path: str = ""
    platform_targets: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    use_openai: bool = True


class UploadYouTubeAuthExchangeRequest(BaseModel):
    code: str = ""


class UploadYouTubeFirstAuthRequest(BaseModel):
    open_browser: bool = True
    port: int = 8080
    enable_upload: bool = True


class UploadYouTubePublishPackageRequest(BaseModel):
    run_id: str = ""
    run_dir: str = ""
    publish_package_path: str = ""
    publish_dir: str = ""
    visibility: str = ""
    privacy: str = ""
    publish_now: bool = True
    publish_at: str = ""
    publish_at_datetime: str = ""
    confirmed: bool = False
    upload_thumbnail: bool = True
