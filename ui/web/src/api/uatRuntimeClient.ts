import { API_BASE_URL } from "./client";

export type UatPlatform = "youtube_shorts" | "tiktok" | "instagram_reels";
export type UatVideoProvider = "runway_browser" | "hailuo_browser" | "mock";
export type UatVoiceProvider = "elevenlabs" | "mock";
export type UatAssemblyMode = "real_assembly" | "dry_run_only";
export type UatRunStatus = "running" | "completed" | "failed" | "cancelled" | "unknown";

export type UatProgressEntry = {
  timestamp: string;
  stage: string;
  level: string;
  message: string;
};

export type RunwayOpenPageObs = {
  index: number;
  page_url?: string;
  page_title?: string;
  is_runway_url?: boolean;
  controlled?: boolean;
};

export type RunwayBrowserObsPayload = {
  step?: string | null;
  step_updated_at?: string | null;
  controlled_page?: {
    page_index?: number;
    page_url?: string;
    page_title?: string;
    is_runway_url?: boolean;
  } | null;
  open_pages?: RunwayOpenPageObs[];
  failure_message?: string | null;
  clip_index?: number | null;
};

export type UatVideoRuntimeObs = {
  state?: string | null;
  provider?: string | null;
  runway_step?: string | null;
  controlled_tab_url?: string | null;
  controlled_tab_title?: string | null;
  is_runway_url?: boolean | null;
  open_pages?: RunwayOpenPageObs[];
};

export type UatRunResponse = {
  session_id: string;
  status: UatRunStatus;
  current_stage?: string | null;
  failed_stage?: string | null;
  stages?: Record<string, Record<string, unknown> | null>;
  progress_log?: UatProgressEntry[];
  artifact_folder?: string | null;
  final_video_path?: string | null;
  report_path?: string | null;
  review_template_path?: string | null;
  warnings?: string[];
  errors?: string[];
  flags_active?: Record<string, boolean>;
  api_version?: string;
  runway_browser_obs?: RunwayBrowserObsPayload;
  video_runtime?: UatVideoRuntimeObs;
};

export type UatRunRequest = {
  topic: string;
  platform: UatPlatform;
  duration_seconds: number;
  video_provider: UatVideoProvider;
  voice_provider: UatVoiceProvider;
  confirm_real_voice: boolean;
  confirm_real_video: boolean;
  confirm_real_assembly: boolean;
  open_folder?: boolean;
  niche?: string;
};

export type UatReviewRequest = {
  story_quality_score: number;
  visual_quality_score: number;
  voice_quality_score: number;
  subtitle_quality_score: number;
  continuity_score: number;
  overall_quality_score: number;
  comments: string;
  publishable: boolean;
  submitted_by?: string;
};

export type UatReviewResponse = {
  success: boolean;
  session_id: string;
  review_path: string;
  submitted_at: string;
  api_version?: string;
};

function formatValidationDetail(detail: unknown): string | null {
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item !== "object" || item === null) {
          return String(item);
        }
        const record = item as Record<string, unknown>;
        const loc = Array.isArray(record.loc) ? record.loc.filter(Boolean).join(".") : "body";
        const msg = record.msg ?? record.message ?? "invalid value";
        return `${loc}: ${String(msg)}`;
      })
      .filter(Boolean);
    return parts.length > 0 ? parts.join("; ") : null;
  }
  if (typeof detail === "object" && detail !== null) {
    const record = detail as Record<string, unknown>;
    if (record.message || record.code) {
      return String(record.message || record.code);
    }
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return null;
}

export function parseApiError(data: unknown, fallback: string): string {
  if (typeof data !== "object" || data === null) {
    return fallback;
  }
  const record = data as Record<string, unknown>;
  const validation = formatValidationDetail(record.detail);
  if (validation) {
    return validation;
  }
  if (typeof record.detail === "object" && record.detail !== null) {
    const detailRecord = record.detail as Record<string, unknown>;
    return String(detailRecord.message || detailRecord.code || fallback);
  }
  return String(record.message || record.detail || fallback);
}

export async function postUatRun(body: UatRunRequest): Promise<UatRunResponse> {
  const payload: UatRunRequest = {
    ...body,
    duration_seconds: Number(body.duration_seconds),
  };
  const response = await fetch(`${API_BASE_URL}/uat/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await response.json()) as UatRunResponse & { detail?: unknown };
  if (!response.ok) {
    const prefix = response.status === 422 ? "Validation failed" : "Request failed";
    throw new Error(`${prefix}: ${parseApiError(data, "Failed to start UAT run")}`);
  }
  return data;
}

export async function fetchUatStatus(sessionId: string): Promise<UatRunResponse> {
  const response = await fetch(`${API_BASE_URL}/uat/status/${encodeURIComponent(sessionId)}`);
  const data = (await response.json()) as UatRunResponse & { detail?: unknown };
  if (!response.ok) {
    throw new Error(parseApiError(data, "Failed to fetch UAT status"));
  }
  return data;
}

export async function postUatReview(
  sessionId: string,
  body: UatReviewRequest,
): Promise<UatReviewResponse> {
  const response = await fetch(`${API_BASE_URL}/uat/review/${encodeURIComponent(sessionId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json()) as UatReviewResponse & { detail?: unknown };
  if (!response.ok) {
    throw new Error(parseApiError(data, "Failed to save review"));
  }
  return data;
}

export function uatFinalVideoUrl(sessionId: string): string {
  return `${API_BASE_URL}/uat/artifacts/${encodeURIComponent(sessionId)}/final-video`;
}

export function buildUatRunPayload(config: {
  topic: string;
  platform: UatPlatform;
  durationSeconds: number;
  videoProvider: UatVideoProvider;
  voiceProvider: UatVoiceProvider;
  assemblyMode: UatAssemblyMode;
  confirmRealVoice: boolean;
  confirmRealVideo: boolean;
  confirmRealAssembly: boolean;
}): UatRunRequest {
  return {
    topic: config.topic.trim(),
    platform: config.platform,
    duration_seconds: Number(config.durationSeconds),
    video_provider: config.videoProvider,
    voice_provider: config.voiceProvider,
    confirm_real_voice: Boolean(config.confirmRealVoice),
    confirm_real_video:
      config.videoProvider === "runway_browser" && Boolean(config.confirmRealVideo),
    confirm_real_assembly: config.assemblyMode === "real_assembly" && Boolean(config.confirmRealAssembly),
    open_folder: false,
    niche: "general",
  };
}
