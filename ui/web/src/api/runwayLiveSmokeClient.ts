import { resolveApiBaseUrl } from "../config/apiConfig";

const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export type RunwayLiveSmokeSnapshot = {
  runtime_version?: string;
  run_status?: string;
  gate_type?: string;
  waiting?: boolean;
  current_step_id?: string;
  current_control_key?: string;
  current_label?: string;
  current_action?: string;
  ui_connected?: boolean;
  fallback_to_terminal?: boolean;
  project_id?: string;
  operator?: string;
  approval_history?: Array<Record<string, unknown>>;
  runtime_logs?: string[];
  run_ok?: boolean | null;
  stopped_reason?: string;
  cancelled?: boolean;
  gate_ready?: boolean;
  gate_enabled?: boolean;
  gate_reason?: string;
  expected_step_id?: string;
  early_approval_rejections_count?: number;
  approval_gate_safety_enabled?: boolean;
  execution_mode?: string;
  last_auto_action?: string;
  next_auto_action?: string;
  auto_validation_state?: string;
  auto_execution_timeline?: Array<Record<string, unknown>>;
};

export type RunwayLiveSmokeHandoffPreview = {
  prompt_source?: string;
  content_brain_run_id?: string;
  prompt_cleanup_used?: boolean;
  prompt_noise_score?: number;
  prompt_efficiency_score?: number;
  loaded_from?: string;
  topic_label?: string;
  content_brain_topic?: string;
  seo_title?: string;
  story_summary?: string;
  starter_prompt_preview?: string;
  handoff_version?: string;
  warnings?: string[];
};

export type RunwayLiveSmokeRuntimeResponse = {
  ok: boolean;
  api_version?: string;
  approval_runtime_version?: string;
  message?: string;
  project_id?: string;
  simulate?: boolean;
  active?: boolean;
  snapshot?: RunwayLiveSmokeSnapshot | null;
  report?: Record<string, unknown> | null;
  handoff_preview?: RunwayLiveSmokeHandoffPreview | null;
};

async function parseResponse(response: Response): Promise<RunwayLiveSmokeRuntimeResponse> {
  const data = (await response.json()) as RunwayLiveSmokeRuntimeResponse | { detail?: unknown };
  if (!response.ok) {
    const detail = (data as { detail?: { message?: string } }).detail;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail && "message" in detail
          ? String((detail as { message?: string }).message)
          : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data as RunwayLiveSmokeRuntimeResponse;
}

export async function postRunwayLiveSmokeStart(payload: {
  story_idea: string;
  project_id?: string;
  operator?: string;
  simulate?: boolean;
  clip_count?: number;
  execution_mode?: string;
}): Promise<RunwayLiveSmokeRuntimeResponse> {
  const response = await fetch(`${API_BASE_URL}/runway-live-smoke/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function fetchRunwayLiveSmokeStatus(): Promise<RunwayLiveSmokeRuntimeResponse> {
  const response = await fetch(`${API_BASE_URL}/runway-live-smoke/status`);
  return parseResponse(response);
}

export async function fetchRunwayLiveSmokeHandoffPreview(payload: {
  story_idea?: string;
  clip_count?: number;
}): Promise<RunwayLiveSmokeRuntimeResponse> {
  const params = new URLSearchParams();
  if (payload.story_idea) {
    params.set("story_idea", payload.story_idea);
  }
  if (payload.clip_count) {
    params.set("clip_count", String(payload.clip_count));
  }
  const query = params.toString();
  const response = await fetch(
    `${API_BASE_URL}/runway-live-smoke/handoff-preview${query ? `?${query}` : ""}`,
  );
  return parseResponse(response);
}

export async function postRunwayLiveSmokeConnectUi(): Promise<RunwayLiveSmokeRuntimeResponse> {
  const response = await fetch(`${API_BASE_URL}/runway-live-smoke/connect-ui`, { method: "POST" });
  return parseResponse(response);
}

export async function postRunwayLiveSmokeApprove(operator = "operator"): Promise<RunwayLiveSmokeRuntimeResponse> {
  const response = await fetch(`${API_BASE_URL}/runway-live-smoke/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator }),
  });
  return parseResponse(response);
}

export async function postRunwayLiveSmokeImageReady(operator = "operator"): Promise<RunwayLiveSmokeRuntimeResponse> {
  const response = await fetch(`${API_BASE_URL}/runway-live-smoke/image-ready`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator }),
  });
  return parseResponse(response);
}

export async function postRunwayLiveSmokeCancel(operator = "operator", reason = "ui_cancel"): Promise<RunwayLiveSmokeRuntimeResponse> {
  const response = await fetch(`${API_BASE_URL}/runway-live-smoke/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator, reason }),
  });
  return parseResponse(response);
}

export { API_BASE_URL };
