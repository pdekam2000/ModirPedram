import { resolveApiBaseUrl } from "../config/apiConfig";

const API_BASE = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
const TOKEN_KEY = "modir_platform_token";

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setAuthToken(token: string) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type CredentialStatus = {
  provider_id: string;
  label: string;
  configured: boolean;
  masked_value: string;
  testable: boolean;
  updated_at: string;
};

export function fetchCredentials() {
  return request<{ providers: CredentialStatus[] }>("/platform/credentials");
}

export function saveCredential(providerId: string, secret: string) {
  return request<{ ok: boolean; message: string }>("/platform/credentials/save", {
    method: "POST",
    body: JSON.stringify({ provider_id: providerId, secret }),
  });
}

export function testCredential(providerId: string) {
  return request<{ ok: boolean; message: string }>("/platform/credentials/test", {
    method: "POST",
    body: JSON.stringify({ provider_id: providerId, secret: "" }),
  });
}

export function fetchLocalUser() {
  return request<{ exists: boolean; username: string }>("/platform/auth/user");
}

export function fetchAuthConfig() {
  return request<{ local_mode: boolean; user_exists: boolean; username: string }>("/platform/auth/config");
}

export function localAutoLogin() {
  return request<{ ok: boolean; token: string; username: string; message: string }>(
    "/platform/auth/local-auto-login",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function createLocalUser(username: string, password: string) {
  return request<{ ok: boolean; token: string; username: string; message: string }>(
    "/platform/auth/create-user",
    { method: "POST", body: JSON.stringify({ username, password }) },
  );
}

export function loginUser(username: string, password: string) {
  return request<{ ok: boolean; token: string; username: string; message: string }>(
    "/platform/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }) },
  );
}

export function logoutUser() {
  return request<{ ok: boolean; message: string }>("/platform/auth/logout", { method: "POST" });
}

export function fetchAuthMe() {
  return request<{ authenticated: boolean; username: string }>("/platform/auth/me");
}

export type BrowserHealth = {
  connected: boolean;
  disconnected: boolean;
  cdp_reachable: boolean;
  runway_tab_found: boolean;
  page_responsive: boolean;
  generation_active: boolean;
  generation_reason: string;
  last_heartbeat: string;
  cdp_url: string;
  message: string;
  refresh_allowed: boolean;
  reconnect_allowed: boolean;
};

export function fetchBrowserHealth() {
  return request<BrowserHealth>("/platform/browser/health");
}

export function openPlatformBrowser() {
  return request<{ ok: boolean; message: string; health?: BrowserHealth }>("/platform/browser/open", {
    method: "POST",
  });
}

export function reconnectPlatformBrowser() {
  return request<{ ok: boolean; message: string; health?: BrowserHealth }>("/platform/browser/reconnect", {
    method: "POST",
  });
}

export function refreshRunwayPage(force = false) {
  return request<{ ok: boolean; message: string; blocked?: boolean; requires_confirmation?: boolean }>(
    `/platform/browser/refresh-runway?force=${force ? "true" : "false"}`,
    { method: "POST" },
  );
}

export type RunwaySessionStatus = {
  connected: boolean;
  disconnected: boolean;
  message: string;
  validated: boolean;
  updated_at: string;
  session_path: string;
  awaiting_login?: boolean;
};

export function fetchRunwaySessionStatus(validate = false) {
  return request<RunwaySessionStatus>(`/platform/browser/runway-session?validate=${validate ? "true" : "false"}`);
}

export function connectRunwayBrowser() {
  return request<RunwaySessionStatus>("/platform/browser/connect-runway", { method: "POST" });
}

export function saveRunwayBrowserSession() {
  return request<RunwaySessionStatus>("/platform/browser/save-runway-session", { method: "POST" });
}

export type RunHistoryItem = {
  run_id: string;
  topic: string;
  run_dir: string;
  final_video_path: string;
  publish_dir: string;
  assembly_status: string;
  publish_status: string;
  created_at: string;
};

export function fetchRunHistory(limit = 20) {
  return request<{ latest: RunHistoryItem | null; runs: RunHistoryItem[] }>(
    `/platform/runs/history?limit=${limit}`,
  );
}

export type AutomationCenterState = {
  enabled: boolean;
  paused: boolean;
  daily_schedule_overview: Record<string, unknown>[];
  queued_jobs: Record<string, unknown>[];
  run_history: Record<string, unknown>[];
  failed_jobs: Record<string, unknown>[];
  feature_flags: Record<string, boolean>;
  updated_at: string;
};

export function fetchAutomationCenter() {
  return request<AutomationCenterState>("/platform/automation-center");
}

export function updateAutomationCenter(body: Partial<AutomationCenterState>) {
  return request<AutomationCenterState>("/platform/automation-center", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function queueAutomationJob(body: { title?: string; topic?: string; provider?: string }) {
  return request<AutomationCenterState>("/platform/automation-center/queue", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function startNextAutomationJob() {
  return request<AutomationCenterState>("/platform/automation-center/start-next", { method: "POST" });
}

export type AutomationStatus = {
  version: string;
  enabled: boolean;
  paused: boolean;
  feature_flags: Record<string, boolean>;
  running_job: Record<string, unknown> | null;
  next_job: Record<string, unknown> | null;
  next_due_job?: Record<string, unknown> | null;
  has_due_jobs?: boolean;
  queued_count: number;
  completed_count: number;
  failed_count: number;
  completed_today: number;
  max_jobs_per_day: number;
  jobs: {
    upcoming?: Record<string, unknown>[];
    running?: Record<string, unknown>[];
    completed?: Record<string, unknown>[];
    failed?: Record<string, unknown>[];
    cancelled?: Record<string, unknown>[];
  };
  comment_drafts?: Record<string, unknown>[];
  upload_packages?: Record<string, unknown>[];
  updated_at: string;
};

export function fetchAutomationStatus() {
  return request<AutomationStatus>("/automation/status");
}

export function createAutomationJob(body: {
  title?: string;
  topic?: string;
  duration?: number;
  clip_count?: number;
  platform_targets?: string[];
  scheduled_time?: string;
}) {
  return request<{ ok: boolean; job: Record<string, unknown> }>("/automation/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function automationStartNext() {
  return request<Record<string, unknown>>("/automation/start-next", { method: "POST" });
}

export function automationStart() {
  return request<Record<string, unknown>>("/automation/start", { method: "POST" });
}

export function automationPause() {
  return request<Record<string, unknown>>("/automation/pause", { method: "POST" });
}

export function automationResume() {
  return request<Record<string, unknown>>("/automation/resume", { method: "POST" });
}

export function automationCancelJob(jobId: string) {
  return request<Record<string, unknown>>(`/automation/cancel/${encodeURIComponent(jobId)}`, { method: "POST" });
}

export function automationResetDailyCounter(platform?: "youtube" | "instagram" | "tiktok") {
  const query = platform ? `?platform=${encodeURIComponent(platform)}` : "";
  return request<{ ok: boolean; message: string; jobs_reset: number; platform: string; completed_today: number }>(
    `/automation/reset-daily-counter${query}`,
    { method: "POST" },
  );
}

export function prepareUploadPackage(body: Record<string, unknown>) {
  return request<{ ok: boolean; upload_package: Record<string, unknown> }>("/upload/prepare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitYouTubeUpload(body: {
  package_dir?: string;
  run_id?: string;
  confirmed?: boolean;
  upload_package?: Record<string, unknown>;
  automation_mode?: boolean;
}) {
  return request<Record<string, unknown>>("/upload/youtube/submit", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitInstagramUpload(body: {
  package_dir?: string;
  run_id?: string;
  video_path?: string;
  upload_package?: Record<string, unknown>;
  title?: string;
  caption?: string;
  hashtags?: string[];
  automation_mode?: boolean;
}) {
  return request<Record<string, unknown>>("/upload/instagram/submit", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitTikTokUpload(body: {
  package_dir?: string;
  run_id?: string;
  video_path?: string;
  upload_package?: Record<string, unknown>;
  title?: string;
  caption?: string;
  automation_mode?: boolean;
}) {
  return request<Record<string, unknown>>("/upload/tiktok/submit", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function draftCommentReply(body: {
  comment_text: string;
  video_topic?: string;
  topic?: string;
  channel_tone?: string;
  language?: string;
}) {
  return request<{ ok: boolean; draft: Record<string, unknown> }>("/comments/draft-reply", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function approveCommentDraft(index: number) {
  return request<Record<string, unknown>>("/comments/draft-reply/approve", {
    method: "POST",
    body: JSON.stringify({ index }),
  });
}

export function rejectCommentDraft(index: number) {
  return request<Record<string, unknown>>("/comments/draft-reply/reject", {
    method: "POST",
    body: JSON.stringify({ index }),
  });
}

export type UploadCenterStatus = {
  version?: string;
  run_id?: string;
  topic?: string;
  platform_targets?: string[];
  upload_manifest?: {
    packages?: Array<Record<string, unknown>>;
    upload_root?: string;
    run_dir?: string;
  };
  metadata_by_platform?: Record<string, Record<string, unknown>>;
  youtube_auth?: Record<string, unknown>;
  upload_root?: string;
  publish_package_path?: string;
  auto_upload_enabled?: boolean;
  latest_legacy_package?: Record<string, unknown>;
  platform_scheduler?: PlatformSchedulerState;
};

export type PlatformUploadHistoryItem = {
  title?: string;
  uploaded_at?: string;
  success?: boolean;
  run_id?: string;
  youtube_url?: string;
  post_url?: string;
  error?: string;
};

export type PlatformScheduleEntry = {
  enabled?: boolean;
  topic?: string;
  videos_per_day?: number;
  interval_hours?: number;
  start_hour?: number;
  duration_seconds?: number;
  upload_times_preview?: string[];
  last_upload_success?: boolean;
  upload_history?: PlatformUploadHistoryItem[];
};

export type PlatformSchedulerState = {
  version?: string;
  automation_enabled?: boolean;
  automation_paused?: boolean;
  daily_job_cap?: number;
  youtube_duration_seconds?: number;
  instagram_duration_seconds?: number;
  tiktok_duration_seconds?: number;
  platforms?: Record<string, PlatformScheduleEntry>;
  updated_at?: string;
};

export function fetchPlatformSchedules() {
  return request<PlatformSchedulerState>("/automation/platform-schedules");
}

export function updatePlatformSchedules(body: {
  automation_enabled?: boolean;
  automation_paused?: boolean;
  platforms?: Record<string, Partial<PlatformScheduleEntry>>;
}) {
  return request<PlatformSchedulerState & { ok?: boolean; sync?: Record<string, unknown> }>(
    "/automation/platform-schedules",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function fetchUploadCenterStatus(runId = "") {
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<UploadCenterStatus>(`/upload/status${query}`);
}

export function generateUploadMetadata(body: Record<string, unknown>) {
  return request<{ ok: boolean; metadata: Record<string, unknown> }>("/upload/metadata/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function prepareUploadPackages(body: Record<string, unknown>) {
  return request<{ ok: boolean; upload_manifest: Record<string, unknown>; upload_center_ready?: boolean }>(
    "/upload/packages/prepare",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function fetchYouTubeAuthStatus() {
  return request<Record<string, unknown>>("/upload/youtube/auth/status");
}

export function getYouTubeOAuthConnectUrl() {
  return `${API_BASE}/upload/youtube/auth`;
}

export function startYouTubeAuth() {
  return request<Record<string, unknown>>("/upload/youtube/auth/start", { method: "POST" });
}

export function exchangeYouTubeAuth(code: string) {
  return request<Record<string, unknown>>("/upload/youtube/auth/exchange", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}
