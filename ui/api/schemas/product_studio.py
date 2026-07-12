"""Product studio API schemas — Create Video + Scheduling."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChannelProfileDTO(BaseModel):
    channel_name: str = ""
    main_niche: str = ""
    sub_niche: str = ""
    channel_topic: str = ""
    youtube_channel_topic: str = ""
    tiktok_channel_topic: str = ""
    instagram_channel_topic: str = ""
    target_audience: str = ""
    language: str = "English"
    tone_style: str = "cinematic"
    visual_style: str = "cinematic realistic"
    youtube_video_style: str = "cinematic realistic"
    instagram_video_style: str = "aesthetic"
    instagram_filter_mood: str = "neutral"
    tiktok_video_style: str = "energetic"
    tiktok_pace: str = "medium"
    default_platform: str = "youtube_shorts"
    default_duration_seconds: int = 30
    default_provider: str = "runway"
    default_voice: str = ""
    default_narration_provider: str = "elevenlabs"
    audio_source: str = "runway_native"
    music_provider: str = "none"
    preferred_topics: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    content_formats: list[str] = Field(default_factory=list)
    upload_platforms: list[str] = Field(default_factory=lambda: ["tiktok", "instagram_reels", "youtube_shorts"])
    use_ai_director_default: bool = True
    use_prompt_critic_default: bool = True
    branding_enabled: bool = True
    logo_enabled: bool = True
    logo_position: str = "top_right"
    logo_scale: float = 0.12
    subtitle_enabled: bool = True
    subtitle_style: str = "tiktok"
    subtitle_position: str = "bottom_center"
    cta_enabled: bool = True
    cta_text: str = "Subscribe"
    cta_position: str = "top_right"
    cta_start_seconds: float = 5
    cta_end_seconds: float = 24
    cta_frequency: str = "end"
    cta_style: str = "text_only"
    cta_graphic_path: str = ""
    cta_graphic_position: str = "bottom_center"
    cta_graphic_duration_seconds: float = 5
    logo_path: str = ""
    intro_enabled: bool = False
    intro_text: str = ""
    intro_duration: float = 2.0
    intro_type: str = "none"
    intro_image_path: str = ""
    intro_video_path: str = ""
    intro_fade_effect: str = "fade_in"
    outro_enabled: bool = False
    outro_text: str = ""
    outro_duration: float = 3.0
    outro_type: str = "none"
    outro_image_path: str = ""
    outro_video_path: str = ""
    outro_fade_effect: str = "fade_out"
    outro_subscribe_enabled: bool = True
    outro_subscribe_style: str = "classic_red"
    outro_subscribe_custom_color: str = "#E62117"
    youtube_upload_enabled: bool = False
    youtube_privacy: str = "public"
    youtube_default_description: str = ""
    youtube_default_hashtags: list[str] = Field(default_factory=list)
    youtube_upload_confirmed: bool = False
    youtube_credentials_configured: bool = False
    youtube_oauth_client_path: str = ""
    youtube_made_for_kids: bool = False
    youtube_require_confirmation: bool = False
    youtube_playlist_id: str = ""
    instagram_upload_enabled: bool = False
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_access_token: str = ""
    instagram_account_id: str = ""
    instagram_token_expires_at: str = ""
    instagram_token_exchange_message: str = ""
    instagram_public_base_url: str = ""
    instagram_privacy: str = "public"
    tiktok_upload_enabled: bool = False
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_access_token: str = ""
    tiktok_privacy: str = "PUBLIC_TO_EVERYONE"
    local_mode: bool = True
    asset_vault_enabled: bool = True
    asset_copy_mode: str = "copy"
    updated_at: str = ""


class ChannelLogoStatusDTO(BaseModel):
    logo_exists: bool = False
    logo_path: str = ""


class BrandingStatusDTO(BaseModel):
    status: str = ""
    branding_enabled: bool = False
    final_branded_video_path: str = ""
    subtitled_video_path: str = ""
    subtitles: str = "SKIP"
    logo: str = "SKIP"
    cta: str = "SKIP"
    intro: str = "SKIP"
    outro: str = "SKIP"


class ChannelProfileSuggestRequest(BaseModel):
    channel_topic: str = ""
    language_preference: str = ""
    platform_preference: str = ""


class ChannelProfileSuggestionDTO(BaseModel):
    channel_name: str = ""
    main_niche: str = ""
    sub_niche: str = ""
    channel_topic: str = ""
    target_audience: str = ""
    language: str = "English"
    tone_style: str = "cinematic"
    visual_style: str = "cinematic realistic"
    default_platform: str = "youtube_shorts"
    default_duration_seconds: int = 30
    default_provider: str = "runway"
    default_narration_provider: str = "elevenlabs"
    default_voice: str = ""
    music_provider: str = "none"
    preferred_topics: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    content_formats: list[str] = Field(default_factory=list)
    upload_platforms: list[str] = Field(default_factory=lambda: ["tiktok", "instagram_reels", "youtube_shorts"])
    use_ai_director_default: bool = True
    use_prompt_critic_default: bool = True
    reasoning: str = ""
    source: str = "rule_based"


class DurationPlanDTO(BaseModel):
    duration_seconds: int
    clip_count: int
    provider: str
    clip_limit_seconds: int
    warnings: list[str] = Field(default_factory=list)
    requested_duration_seconds: int | None = None
    planned_duration_seconds: int | None = None
    kling_native_audio: bool | None = None
    audio_strategy: str | None = None
    shot_mode: str | None = None
    shot_1_duration_seconds: int | None = None
    shot_2_duration_seconds: int | None = None
    native_audio_required: bool | None = None
    use_elevenlabs: bool | None = None
    use_external_music: bool | None = None
    subtitle_required: bool | None = None
    shot_prompt_max_chars: int | None = None


class CreateVideoPreflightRequest(BaseModel):
    topic_mode: Literal["channel", "custom"] = "channel"
    custom_topic: str = ""
    specific_story_override: str = ""
    story_diversity_mode: str = "safe_variety"
    duration_seconds: int = 30
    duration_preset: str = "30"
    platform: str = "youtube_shorts"
    style: str = "cinematic"
    provider: str = "runway"
    audio_strategy: str = "auto"
    use_ai_director: bool = True
    use_prompt_critic: bool = True
    use_channel_profile: bool = True


class CreateVideoPreflightResponse(BaseModel):
    ok: bool = True
    authoritative_topic: str = ""
    provider: str = "runway"
    audio_strategy: str = ""
    audio_strategy_request: str = "auto"
    audio_strategy_route: dict[str, Any] | None = None
    duration_plan: DurationPlanDTO
    topic_mode: str
    platform: str
    style: str
    pipeline_steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    preflight_mode: str = "preview_only"
    kling_duration_plan: dict[str, Any] | None = None
    kling_native_audio_plan: dict[str, Any] | None = None
    kling_clip_count: int | None = None
    kling_shot_mode: str | None = None
    kling_clip_prompts: list[dict[str, Any]] = Field(default_factory=list)
    use_elevenlabs: bool | None = None
    use_external_music: bool | None = None
    native_audio_required: bool | None = None
    subtitle_required: bool | None = None
    channel_topic: str = ""
    specific_story_override: str = ""
    story_override_active: bool = False
    story_diversity_mode: str = "safe_variety"
    channel_story_idea: dict[str, Any] = Field(default_factory=dict)
    runway_story_brief: dict[str, Any] = Field(default_factory=dict)
    story_summary: str = ""
    story_repetition_warning: str = ""
    story_ideation_version: str = ""


class CreateVideoGenerateRequest(BaseModel):
    topic_source: Literal["channel", "custom"] = "channel"
    topic_mode: Literal["channel", "custom"] | None = None
    custom_topic: str = ""
    duration_seconds: int = 30
    duration_preset: str = "30"
    clip_count: int | None = None
    platform: str = "youtube_shorts"
    style: str = "cinematic"
    provider: str = ""
    audio_strategy: str = "auto"
    platform_targets: list[str] = Field(default_factory=list)
    use_ai_director: bool = True
    use_prompt_critic: bool = True
    use_channel_profile: bool = True
    execution_mode: str = "FULL_AUTO"
    approve_generate: bool = False
    approved_by: str = ""
    dry_run: bool = False
    free_credit_first: bool = True
    free_credit_mode: bool = False
    operator_paid_approval: bool = False
    credit_mode: str = ""
    specific_story_override: str = ""
    story_diversity_mode: str = "safe_variety"
    run_id: str = ""


class CreateVideoGenerateResponse(BaseModel):
    ok: bool = False
    wired: bool = True
    status: str = "failed"
    message: str = ""
    run_id: str = ""
    credit_safety: dict[str, Any] = Field(default_factory=dict)
    credit_mode: str = ""
    paid_credit_risk: bool = False
    free_credit_checked: bool = False
    estimated_credit_cost: float | None = None
    session_id: str = ""
    project_id: str = ""
    provider: str = ""
    audio_strategy: str = ""
    execution_mode: str = "FULL_AUTO"
    authoritative_topic: str = ""
    clip_count: int = 0
    requested_clip_count: int = 0
    actual_clip_count: int = 0
    prompt_builder_topic: str = ""
    content_brain_run_id: str = ""
    topic_authority_trace: dict[str, Any] = Field(default_factory=dict)
    topic_authority_trace_path: str = ""
    duration_plan: dict[str, Any] = Field(default_factory=dict)
    pipeline_steps: list[str] = Field(default_factory=list)
    snapshot: dict[str, Any] | None = None
    handoff_preview: dict[str, Any] | None = None
    approval_required: bool | None = None
    approval_summary: dict[str, Any] | None = None
    kling_clip_count: int | None = None
    kling_shot_mode: str | None = None
    output_folder: str | None = None
    download_path: str | None = None
    video_path: str | None = None
    native_audio_status: str | None = None
    continuity_chain: dict[str, Any] | None = None
    kling_output_package: dict[str, Any] | None = None


class UpgradeUploadResponse(BaseModel):
    ok: bool = True
    upgrade_id: str = ""
    filename: str = ""
    stored_path: str = ""
    extracted: bool = False
    auto_applied: bool = False
    message: str = ""


class VideoSchedulePlanDTO(BaseModel):
    schedule_id: str = ""
    title: str = ""
    mode: str = "daily"
    videos_per_day: int = 1
    duration_seconds: int = 30
    clip_count: int = 1
    topic_source: str = "channel"
    custom_topic: str = ""
    topic_list: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=lambda: ["tiktok"])
    provider: str = "runway"
    start_date: str = ""
    end_date: str = ""
    run_time: str = "09:00"
    enabled: bool = True


class SchedulePreviewResponse(BaseModel):
    plan: dict[str, Any]
    job_count: int
    jobs_preview: list[dict[str, Any]]
    truncated: bool = False


class ScheduleJobsResponse(BaseModel):
    schedule_id: str
    job_count: int
    jobs: list[dict[str, Any]]


class ElevenLabsConnectionStatusDTO(BaseModel):
    ok: bool = True
    key_detected: bool = False
    api_key_env: str = "ELEVENLABS_API_KEY"
    provider_enabled: bool = True
    voices_probe_status: str = "not_tested"
    last_error: str = ""
    last_tested_at: str = ""
    voice_count: int | None = None
    message: str = ""


class LatestResultsResponse(BaseModel):
    found: bool = False
    video_path: str = ""
    publish_package_path: str = ""
    platform_targets: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    runway_completed: bool = False
    has_downloads_only: bool = False
    assembly_status: str = ""
    publish_status: str = ""
    downloaded_clip_count: int = 0
    post_processing_status: str = ""
    post_processing_missing: bool = False
    stale_manifest_ignored: bool = False
    stale_sections: list[str] = Field(default_factory=list)
    section_availability: dict[str, str] = Field(default_factory=dict)
    selected_run_id: str = ""
    run_folder: str = ""
    run_dir: str = ""
    canonical_run_id: str = ""
    is_canonical_latest: bool = False
    topic: str = ""
    latest_run_id: str = ""
    stored_manifest_run_id: str = ""
    post_processing_warnings: list[str] = Field(default_factory=list)
    music_status: str = ""
    ambience_status: str = ""
    sfx_status: str = ""
    subtitle_style_status: str = ""
    character_voice_status: str = ""
    final_branded_video_v2_path: str = ""
    final_branded_video_v3_path: str = ""
    latest_approved_video_path: str = ""
    latest_run_attempt: dict[str, Any] = Field(default_factory=dict)
    latest_attempt_status: str = ""
    latest_attempt_message: str = ""
    latest_attempt_run_id: str = ""
    latest_attempt_topic: str = ""
    latest_attempt_clips_completed: int = 0
    approved_run_id: str = ""
    delivery_truth: dict[str, Any] = Field(default_factory=dict)
    delivery_truth_status: str = ""
    delivery_truth_checks: dict[str, Any] = Field(default_factory=dict)
    delivery_registry: dict[str, Any] = Field(default_factory=dict)
    story_audio_director: dict[str, Any] = Field(default_factory=dict)
    story_visual_quality: dict[str, Any] = Field(default_factory=dict)
    cinematic_audio: dict[str, Any] = Field(default_factory=dict)
    branding_status: BrandingStatusDTO = Field(default_factory=BrandingStatusDTO)
    final_branded_video_path: str = ""
    visual_continuity: dict[str, Any] = Field(default_factory=dict)
    visual_continuity_report: dict[str, Any] = Field(default_factory=dict)
    visual_memory: dict[str, Any] = Field(default_factory=dict)
    visual_memory_report: dict[str, Any] = Field(default_factory=dict)
    ai_director_v2: dict[str, Any] = Field(default_factory=dict)
    ai_director_v2_report: dict[str, Any] = Field(default_factory=dict)
    video_quality_judge: dict[str, Any] = Field(default_factory=dict)
    video_quality_learning_proposed: bool = False
    video_quality_proposed_updates_path: str = ""
    output_ready: bool = False
    recovery_available: bool = False
    generation_status: str = ""
    legacy_run_folders: list[str] = Field(default_factory=list)
    run_history: list[dict[str, Any]] = Field(default_factory=list)
    asset_library_path: str = ""
    latest_assets: list[dict[str, Any]] = Field(default_factory=list)
    youtube_oauth_status: str = ""
    youtube_authorized: bool = False
    youtube_credentials_configured: bool = False
    youtube_channel_id: str = ""
    youtube_channel_name: str = ""
    youtube_connected_channel: str = ""
    youtube_upload_ready: bool = False
    youtube_token_refresh_verified: bool = False
    youtube_upload_status: str = ""
    youtube_video_id: str = ""
    youtube_url: str = ""
    youtube_visibility: str = ""
    youtube_publish_time: str = ""
    youtube_upload_time: str = ""
    youtube_metadata: dict[str, Any] = Field(default_factory=dict)
    youtube_title: str = ""
    youtube_category: str = ""
    youtube_tags_count: int = 0
    youtube_hashtags: list[str] = Field(default_factory=list)
    visual_diversity_score: int = 0
    visual_diversity_status: str = ""
    repetition_risk: str = ""
    repeated_clip_warning: bool = False
    similar_clip_pairs: list[dict[str, Any]] = Field(default_factory=list)
    frame_similarity_pairs: list[dict[str, Any]] = Field(default_factory=list)
    youtube_upload_allowed: bool = True
    auto_upload_enabled: bool = False
    auto_upload_started: bool = False
    youtube_upload_blocked_reason: str = ""
    youtube_auto_upload_config: dict[str, Any] = Field(default_factory=dict)
    pipeline_trace: dict[str, Any] = Field(default_factory=dict)
    stop_stage: str = ""
    last_completed_stage: str = ""
    orchestrator_version: str = ""
    api_runtime_diagnostics: dict[str, Any] = Field(default_factory=dict)
    api_build_id: str = ""
    api_process_stale: bool = False
    assembly_bridge_enabled: bool = False
    branding_publish_enabled: bool = False
    branding_publish_status: str = ""
    youtube_metadata_enabled: bool = False
    video_approved: bool = False
    video_display_label: str = ""
    candidate_video_path: str = ""
    latest_candidate_video_path: str = ""
    run_truth: dict[str, Any] = Field(default_factory=dict)
    selected_duration_seconds: int = 0
    duplicate_chain_failed: bool = False
    duplicate_clips_status: str = ""
    clip_statuses: list[dict[str, Any]] = Field(default_factory=list)
    clip_3_not_applicable: bool = False
    clip_3_status: str = ""


class AssetLibraryResponse(BaseModel):
    library_path: str = ""
    vault_videos_path: str = ""
    asset_count: int = 0
    assets: list[dict[str, Any]] = Field(default_factory=list)
    vault_enabled: bool = True
    copy_mode: str = "copy"
