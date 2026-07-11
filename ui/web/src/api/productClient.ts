import { resolveApiBaseUrl } from "../config/apiConfig";

const API_BASE = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type ChannelProfile = {
  channel_name: string;
  main_niche: string;
  sub_niche: string;
  channel_topic: string;
  youtube_channel_topic?: string;
  tiktok_channel_topic?: string;
  instagram_channel_topic?: string;
  target_audience: string;
  language: string;
  tone_style: string;
  visual_style?: string;
  youtube_video_style?: string;
  instagram_video_style?: string;
  instagram_filter_mood?: string;
  tiktok_video_style?: string;
  tiktok_pace?: string;
  default_platform: string;
  default_duration_seconds: number;
  default_provider: string;
  default_voice?: string;
  default_narration_provider?: string;
  audio_source?: string;
  music_provider?: string;
  preferred_topics?: string[];
  forbidden_topics?: string[];
  content_formats?: string[];
  upload_platforms: string[];
  use_ai_director_default?: boolean;
  use_prompt_critic_default?: boolean;
  branding_enabled?: boolean;
  logo_enabled?: boolean;
  logo_position?: string;
  logo_scale?: number;
  subtitle_enabled?: boolean;
  subtitle_style?: string;
  subtitle_position?: string;
  cta_enabled?: boolean;
  cta_text?: string;
  cta_position?: string;
  cta_frequency?: string;
  cta_style?: string;
  cta_graphic_path?: string;
  cta_graphic_position?: string;
  cta_graphic_duration_seconds?: number;
  logo_path?: string;
  intro_enabled?: boolean;
  intro_text?: string;
  intro_duration?: number;
  intro_type?: string;
  intro_image_path?: string;
  intro_video_path?: string;
  intro_fade_effect?: string;
  outro_enabled?: boolean;
  outro_text?: string;
  outro_duration?: number;
  outro_type?: string;
  outro_image_path?: string;
  outro_video_path?: string;
  outro_fade_effect?: string;
  outro_subscribe_enabled?: boolean;
  outro_subscribe_style?: string;
  outro_subscribe_custom_color?: string;
  youtube_upload_enabled?: boolean;
  youtube_privacy?: string;
  youtube_default_description?: string;
  youtube_default_hashtags?: string[];
  youtube_upload_confirmed?: boolean;
  youtube_credentials_configured?: boolean;
  youtube_oauth_client_path?: string;
  youtube_made_for_kids?: boolean;
  youtube_require_confirmation?: boolean;
  youtube_playlist_id?: string;
  instagram_upload_enabled?: boolean;
  instagram_app_id?: string;
  instagram_app_secret?: string;
  instagram_access_token?: string;
  instagram_account_id?: string;
  instagram_token_expires_at?: string;
  instagram_token_exchange_message?: string;
  instagram_public_base_url?: string;
  instagram_privacy?: string;
  tiktok_upload_enabled?: boolean;
  tiktok_client_key?: string;
  tiktok_client_secret?: string;
  tiktok_access_token?: string;
  tiktok_privacy?: string;
  local_mode?: boolean;
  asset_vault_enabled?: boolean;
  asset_copy_mode?: "copy" | "move";
  updated_at?: string;
};

export type ChannelProfileSuggestion = ChannelProfile & {
  reasoning: string;
  source: string;
};

export type ChannelProfileSuggestRequest = {
  channel_topic: string;
  language_preference?: string;
  platform_preference?: string;
};

export type DurationPlan = {
  duration_seconds: number;
  clip_count: number;
  provider: string;
  clip_limit_seconds: number;
  warnings: string[];
  shot_mode?: string;
  kling_native_audio?: boolean;
  execution_mode?: string;
  requested_duration_seconds?: number;
  clip_duration_seconds?: number;
  use_frame_enabled?: boolean;
};

export type MultiClipExecutionPlan = {
  duration_seconds: number;
  clip_count: number;
  prompts: string[];
  provider: string;
  aspect_ratio: string;
  native_audio: boolean;
  execution_mode: string;
  use_frame_enabled: boolean;
  requested_duration_seconds?: number;
  warnings?: string[];
};

export type GenerationRuntimeStatus = {
  planned_clip_count: number;
  current_clip: number;
  completed_clips: number;
  generation_state: string;
  clip_statuses: Array<{
    clip: number;
    status: string;
    label: string;
    used_frame_from_previous?: boolean;
  }>;
};

export type KlingClipPromptPreview = {
  clip_index: number;
  shot_1_duration_seconds: number;
  shot_1_prompt: string;
  shot_2_duration_seconds: number;
  shot_2_prompt: string;
  continuity_anchor?: string;
  next_clip_reference_hint?: string;
};

export type CreateVideoPreflightResult = {
  ok: boolean;
  authoritative_topic: string;
  provider: string;
  platform?: string;
  aspect_ratio?: string;
  audio_strategy?: string;
  audio_strategy_request?: string;
  duration_plan: DurationPlan;
  pipeline_steps: string[];
  warnings: string[];
  preflight_mode?: string;
  kling_duration_plan?: Record<string, unknown>;
  kling_native_audio_plan?: Record<string, unknown>;
  kling_clip_count?: number;
  kling_shot_mode?: string;
  kling_clip_prompts?: KlingClipPromptPreview[];
  use_elevenlabs?: boolean;
  use_external_music?: boolean;
  native_audio_required?: boolean;
  subtitle_required?: boolean;
  multiclip_execution_plan?: MultiClipExecutionPlan;
  clip_execution_mode?: string;
  execution_mode?: string;
};

export function fetchChannelProfile() {
  return request<ChannelProfile>("/product/channel-profile");
}

export type LastTopicPayload = {
  topic: string;
  topic_mode?: string;
  updated_at?: string;
};

export function fetchLastTopic() {
  return request<LastTopicPayload>("/product/last-topic");
}

export function saveLastTopic(topic: string, topicMode = "custom") {
  return request<LastTopicPayload>("/product/last-topic", {
    method: "PUT",
    body: JSON.stringify({ topic, topic_mode: topicMode }),
  });
}

export function saveChannelProfile(body: Partial<ChannelProfile>) {
  return request<ChannelProfile>("/product/channel-profile", { method: "POST", body: JSON.stringify(body) });
}

export function fetchChannelLogoStatus() {
  return request<{ logo_exists: boolean; logo_path: string }>("/product/channel-assets/logo");
}

export async function uploadChannelLogo(file: File) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/product/channel-assets/logo`, { method: "POST", body: form });
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = String((payload as { detail?: string }).detail || "");
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `Logo upload failed: ${response.status}`);
  }
  return response.json() as Promise<{ ok: boolean; logo_path: string; logo_exists: boolean }>;
}

export type BrandingAssetKind = "cta_graphic" | "intro_image" | "intro_video" | "outro_image" | "outro_video";

export function brandingAssetFileUrl(kind: BrandingAssetKind | "logo") {
  const path = kind === "logo" ? "/product/channel-assets/logo/file" : `/product/channel-assets/${kind}/file`;
  return `${API_BASE}${path}?t=${Date.now()}`;
}

export async function uploadBrandingAsset(kind: BrandingAssetKind, file: File) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/product/channel-assets/${kind}`, { method: "POST", body: form });
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = String((payload as { detail?: string }).detail || "");
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `${kind} upload failed: ${response.status}`);
  }
  return response.json() as Promise<{ ok: boolean; kind: string; asset_path: string; exists: boolean }>;
}

export function suggestChannelProfile(body: ChannelProfileSuggestRequest) {
  return request<ChannelProfileSuggestion>("/product/channel-profile/suggest", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type ElevenLabsConnectionStatus = {
  ok: boolean;
  key_detected: boolean;
  api_key_env: string;
  provider_enabled: boolean;
  voices_probe_status: "not_tested" | "passed" | "failed" | string;
  last_error: string;
  last_tested_at: string;
  voice_count: number | null;
  message: string;
};

export function fetchElevenLabsConnectionStatus() {
  return request<ElevenLabsConnectionStatus>("/product/elevenlabs/connection-status");
}

export function testElevenLabsConnection() {
  return request<ElevenLabsConnectionStatus>("/product/elevenlabs/test-connection", { method: "POST" });
}

export function createVideoPreflight(body: Record<string, unknown>) {
  return request<CreateVideoPreflightResult>("/product/create-video/preflight", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type CreateVideoGenerateResult = {
  ok: boolean;
  wired: boolean;
  status: string;
  message?: string;
  run_id?: string;
  session_id?: string;
  project_id?: string;
  provider?: string;
  audio_strategy?: string;
  execution_mode?: string;
  clip_execution_mode?: string;
  authoritative_topic?: string;
  clip_count?: number;
  kling_clip_count?: number;
  kling_shot_mode?: string;
  duration_plan?: DurationPlan;
  multiclip_execution_plan?: MultiClipExecutionPlan;
  generation_runtime_status?: GenerationRuntimeStatus;
  generation_time_seconds?: number;
  final_video_duration_seconds?: number;
  merge_info?: Record<string, unknown>;
  pipeline_execution_mode?: string;
  pipeline_steps?: string[];
  snapshot?: Record<string, unknown> | null;
  approval_required?: boolean;
  approval_summary?: Record<string, unknown>;
  output_folder?: string;
  download_path?: string;
  video_path?: string;
  native_audio_status?: string;
  continuity_chain?: Record<string, unknown>;
};

export function createVideoGenerate(body: Record<string, unknown>) {
  return request<CreateVideoGenerateResult>("/product/create-video/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchRunwayLiveSmokeStatus() {
  return request<{
    ok: boolean;
    active?: boolean;
    snapshot?: Record<string, unknown> | null;
    report?: Record<string, unknown> | null;
  }>("/runway-live-smoke/status");
}

export function previewSchedule(body: Record<string, unknown>) {
  return request<{ plan: Record<string, unknown>; job_count: number; jobs_preview: Record<string, unknown>[] }>(
    "/product/schedules/preview",
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function saveSchedule(body: Record<string, unknown>) {
  return request<Record<string, unknown>>("/product/schedules", { method: "POST", body: JSON.stringify(body) });
}

export function generateScheduleJobs(scheduleId: string, onlyDate?: string) {
  const query = onlyDate ? `?only_date=${encodeURIComponent(onlyDate)}` : "";
  return request<{ schedule_id: string; job_count: number; jobs: Record<string, unknown>[] }>(
    `/product/schedules/${scheduleId}/generate-jobs${query}`,
    { method: "POST" },
  );
}

export function fetchLatestResults(runId = "", runDir = "") {
  const params = new URLSearchParams();
  if (runId) params.set("run_id", runId);
  if (runDir) params.set("run_dir", runDir);
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<{
    found: boolean;
    video_path: string;
    publish_package_path: string;
    platform_targets: string[];
    metadata: Record<string, unknown>;
    runway_completed: boolean;
    has_downloads_only: boolean;
    assembly_status: string;
    publish_status: string;
    downloaded_clip_count: number;
    post_processing_status?: string;
    post_processing_missing?: boolean;
    stale_manifest_ignored?: boolean;
    stale_sections?: string[];
    section_availability?: Record<string, string>;
    selected_run_id?: string;
    run_folder?: string;
    run_dir?: string;
    canonical_run_id?: string;
    is_canonical_latest?: boolean;
    topic?: string;
    latest_run_id?: string;
    stored_manifest_run_id?: string;
    post_processing_warnings: string[];
    run_history?: Array<Record<string, unknown>>;
    branding_status?: {
      status?: string;
      branding_enabled?: boolean;
      final_branded_video_path?: string;
      subtitled_video_path?: string;
      subtitles?: string;
      logo?: string;
      cta?: string;
      intro?: string;
      outro?: string;
    };
    final_branded_video_path?: string;
    visual_continuity?: {
      overall_pass?: boolean | null;
      overall_score?: number;
      status?: string;
      message?: string;
      run_id?: string;
      clips?: Array<{
        clip_index: number;
        pass: boolean;
        score: number;
        expected_subject?: string;
        detected_subject?: string;
        notes?: string;
      }>;
    };
    visual_continuity_report?: {
      overall_pass?: boolean | null;
      overall_score?: number;
      status?: string;
      message?: string;
      run_id?: string;
      clips?: Array<{
        clip_index: number;
        pass: boolean;
        score: number;
        expected_subject?: string;
        detected_subject?: string;
        notes?: string;
      }>;
    };
    visual_memory?: {
      subject?: string;
      subject_type?: string;
      visual_memory_status?: string;
      consistency_score?: number | null;
      consistency_pass?: boolean;
      continuity_status?: string;
      memory_path?: string;
      vision_verifier_ready?: boolean;
    };
    visual_memory_report?: {
      subject?: string;
      subject_type?: string;
      visual_memory_status?: string;
      consistency_score?: number | null;
      consistency_pass?: boolean;
      continuity_status?: string;
      memory_path?: string;
      vision_verifier_ready?: boolean;
    };
    ai_director_v2?: {
      director_version?: string;
      shot_plan?: Array<{ clip_index: number; shot_type: string; scene_progression?: string }>;
      shot_plan_summary?: string[];
      rhythm_score?: number | null;
      rhythm_pass?: boolean;
      shot_graph_status?: string;
      shot_graph_path?: string;
      camera_language?: Array<{
        clip_index: number;
        shot_type: string;
        camera_movement?: string;
        lens?: string;
        framing?: string;
        composition?: string;
        visual_objective?: string;
      }>;
    };
    ai_director_v2_report?: {
      director_version?: string;
      shot_plan?: Array<{ clip_index: number; shot_type: string; scene_progression?: string }>;
      shot_plan_summary?: string[];
      rhythm_score?: number | null;
      rhythm_pass?: boolean;
      shot_graph_status?: string;
      shot_graph_path?: string;
      camera_language?: Array<{
        clip_index: number;
        shot_type: string;
        camera_movement?: string;
        lens?: string;
        framing?: string;
        composition?: string;
        visual_objective?: string;
      }>;
    };
    asset_library_path?: string;
    latest_assets?: AssetRecord[];
    music_status?: string;
    subtitle_status?: string;
    ambience_status?: string;
    sfx_status?: string;
    subtitle_style_status?: string;
    character_voice_status?: string;
    final_branded_video_v2_path?: string;
    final_branded_video_v3_path?: string;
    latest_approved_video_path?: string;
    latest_run_attempt?: Record<string, unknown>;
    latest_attempt_status?: string;
    latest_attempt_message?: string;
    latest_attempt_run_id?: string;
    latest_attempt_topic?: string;
    latest_attempt_clips_completed?: number;
    approved_run_id?: string;
    delivery_truth?: Record<string, unknown>;
    delivery_truth_status?: string;
    delivery_truth_checks?: Record<string, { label?: string; status?: string }>;
    delivery_registry?: Record<string, unknown>;
    story_audio_director?: {
      status?: string;
      story_score?: number;
      dialogue_score?: number;
      emotion_score?: number;
      character_count?: number;
      voice_count?: number;
      environment_plan?: { environment?: string };
      music_plan?: { mood?: string };
      story_package_path?: string;
      checks?: Record<string, boolean>;
      failures?: string[];
    };
    story_visual_quality?: {
      scene_diversity_score?: number;
      emotion_coverage_score?: number;
      story_progression_score?: number;
      repetition_score?: number;
      reaction_coverage_score?: number;
      pass_visual_diversity?: boolean;
      unique_locations?: string[];
      clip_objectives?: Array<{
        clip_index?: number;
        location?: string;
        visual_objective?: string;
        setting_type?: string;
        story_beat?: string;
      }>;
    };
    kling_native_audio?: {
      provider_used?: string;
      audio_strategy_used?: string;
      native_audio_status?: string;
      generation_status?: string;
      output_ready?: boolean;
      recovery_available?: boolean;
      legacy_run_folders?: string[];
      clip_count?: number;
      shot_mode?: string;
      continuity_status?: string;
      continuity_method?: string;
      use_frame_status?: string;
      fallback_used?: boolean;
      story_progression_status?: string;
      story_progression?: {
        validation_status?: string;
        chapters?: Array<{
          clip_index?: number;
          chapter_role?: string;
          chapter_label?: string;
          story_objective?: string;
          emotion?: string;
          conflict_level?: number;
        }>;
      };
      use_frame_chain?: Record<string, unknown>;
      frames_extracted_count?: number;
      frames_uploaded_count?: number;
      chain_complete?: boolean;
      output_folder?: string;
      download_path?: string;
      generation_time_seconds?: number;
      approval_information?: Record<string, unknown>;
      continuity_chain?: Record<string, unknown>;
      kling_clip_prompts?: KlingClipPromptPreview[];
    };
    output_ready?: boolean;
    recovery_available?: boolean;
    generation_status?: string;
    legacy_run_folders?: string[];
    video_quality_judge?: {
      version?: string;
      run_id?: string;
      video_path?: string;
      overall_score?: number;
      story_score?: number;
      audio_score?: number;
      visual_score?: number;
      continuity_score?: number;
      viral_score?: number;
      strengths?: string[];
      weaknesses?: string[];
      improvement_actions?: Array<Record<string, unknown>>;
      used_sources?: string[];
      created_at?: string;
    };
    video_quality_learning_proposed?: boolean;
    video_quality_proposed_updates_path?: string;
    video_quality_judge_p1?: {
      version?: string;
      run_id?: string;
      video_path?: string;
      overall_score?: number;
      story_score?: number;
      character_score?: number;
      dialogue_score?: number;
      visual_score?: number;
      audio_score?: number;
      continuity_score?: number;
      viral_score?: number;
      strengths?: string[];
      weaknesses?: string[];
      improvement_actions?: Array<Record<string, unknown>>;
      judge_mode?: string;
      used_sources?: string[];
      created_at?: string;
    };
    video_quality_learning_p1_proposed?: boolean;
    video_quality_proposed_updates_p1_path?: string;
    cinematic_audio?: {
      status?: string;
      character_count?: number;
      voice_count?: number;
      dialogue_line_count?: number;
      emotion_states?: string[];
      environment_layers?: number;
      music_layers?: number;
      audio_quality_score?: number;
      cinematic_audio_path?: string;
      cinematic_video_path?: string;
      audio_reality_audit?: { status?: string; quality_score?: number };
      voice_presence_audit?: { status?: string; detected_speakers?: string[] };
    };
    youtube_oauth_status?: string;
    youtube_authorized?: boolean;
    youtube_credentials_configured?: boolean;
    youtube_channel_id?: string;
    youtube_channel_name?: string;
    youtube_connected_channel?: string;
    youtube_upload_ready?: boolean;
    youtube_token_refresh_verified?: boolean;
    youtube_upload_status?: string;
    youtube_video_id?: string;
    youtube_url?: string;
    youtube_visibility?: string;
    youtube_publish_time?: string;
    youtube_upload_time?: string;
    youtube_metadata?: Record<string, unknown>;
    youtube_title?: string;
    youtube_category?: string;
    youtube_tags_count?: number;
    youtube_hashtags?: string[];
    youtube_thumbnail_prompt?: string;
    visual_diversity_score?: number;
    visual_diversity_status?: string;
    repetition_risk?: string;
    repeated_clip_warning?: boolean;
    similar_clip_pairs?: Array<{ clip_a?: number; clip_b?: number; similarity?: number; reason?: string }>;
    frame_similarity_pairs?: Array<{ clip_a?: number; clip_b?: number; similarity?: number; reason?: string }>;
    youtube_upload_allowed?: boolean;
  }>(`/product/results/latest${query}`);
}

export type AssetRecord = {
  asset_id?: string;
  run_id?: string;
  topic?: string;
  category?: string;
  creation_time?: string;
  source_run_folder?: string;
  final_video_path?: string;
  duration_seconds?: number | null;
  clip_count?: number;
  branding_enabled?: boolean;
  narration_enabled?: boolean;
  music_enabled?: boolean;
  thumbnail_path?: string;
};

export function fetchAssetLibrary(limit = 20) {
  return request<{
    library_path: string;
    vault_videos_path: string;
    asset_count: number;
    assets: AssetRecord[];
    vault_enabled: boolean;
    copy_mode: string;
  }>(`/product/assets/library?limit=${limit}`);
}

export function fetchUpgradePatches() {
  return request<{
    patches: string[];
    future_patches?: string[];
    uploaded_patches?: Array<{ upgrade_id: string; label: string; status?: string }>;
    note: string;
  }>("/product/upgrade-center/patches");
}

export async function uploadUpgradePatch(file: File) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/upgrades/upload`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Upload failed: ${response.status}`);
  }
  return response.json() as Promise<{
    ok: boolean;
    upgrade_id: string;
    filename: string;
    auto_applied: boolean;
    message?: string;
  }>;
}
