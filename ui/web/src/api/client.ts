import { DEFAULT_API_BASE_URL, resolveApiBaseUrl } from "../config/apiConfig";

const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export type PanelDTO = {
  status: "available" | "partial" | "missing" | "unavailable" | string;
  completeness: number;
  warnings: string[];
  metadata: Record<string, unknown>;
  data: Record<string, unknown>;
  panel?: string;
};

export type SessionSummary = {
  session_id: string;
  session_uuid?: string | null;
  session_schema_version?: string | null;
  brief_id: string;
  status: string;
  provider: string;
  story_quality_score: number | null;
  approval_state: string;
  budget_state: string;
  priority_band: string;
  execution_confidence: number | null;
  created_at: string;
  archived?: boolean;
  archived_at?: string | null;
  archived_by?: string | null;
  archive_reason?: string | null;
};

export type SessionOverview = {
  total_sessions: number;
  active_sessions_count?: number;
  archived_sessions_count?: number;
  simulated_count: number;
  approved_count: number;
  blocked_count: number;
  failed_count: number;
  cancelled_count: number;
  queued_count?: number;
  runtime_active_count?: number;
  runtime_completed_count?: number;
  runtime_stale_count?: number;
  avg_story_quality_score: number | null;
  avg_execution_confidence: number | null;
  generated_at: string;
};

export type DataCompleteness = {
  story_quality: number;
  approval: number;
  budget: number;
  priority: number;
  provider_selection: number;
  simulation: number;
  readiness: number;
  queue: number;
  provider_runtime: number;
};

export type ExecutionReadiness = {
  decision: string;
  readiness_score: number;
  readiness_failures: string[];
  readiness_warnings: string[];
  metadata?: Record<string, unknown>;
};

export type SessionDetail = SessionSummary & {
  source_session_uuid?: string | null;
  execution_readiness?: ExecutionReadiness | null;
  queue_item?: Record<string, unknown> | null;
  execution_runtime?: Record<string, unknown> | null;
  timeline: Array<Record<string, string>>;
  story_quality_panel: PanelDTO;
  approval_panel: PanelDTO;
  budget_panel: PanelDTO;
  priority_panel: PanelDTO;
  provider_selection_panel: PanelDTO;
  simulation_panel: PanelDTO;
  readiness_panel: PanelDTO;
  queue_panel: PanelDTO;
  provider_runtime_panel: PanelDTO;
  data_completeness: DataCompleteness;
  session: Record<string, unknown>;
  simulation_report: Record<string, unknown> | null;
  approval_decision: Record<string, unknown> | null;
};

export type SessionListResponse = {
  sessions: SessionSummary[];
  count: number;
};

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchSessionSummary(): Promise<SessionOverview> {
  return request<SessionOverview>("/sessions/summary");
}

export function fetchSessions(archived?: "false" | "true" | "all"): Promise<SessionListResponse> {
  const query =
    archived === undefined ? "" : `?archived=${encodeURIComponent(archived)}`;
  return request<SessionListResponse>(`/sessions${query}`);
}

export function fetchSession(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${encodeURIComponent(sessionId)}`);
}

export { API_BASE_URL, DEFAULT_API_BASE_URL };

export type RuntimeDispatchRequest = {
  skip_provider_execution?: boolean;
};

export type RuntimeActionResponse = {
  success: boolean;
  accepted?: boolean;
  async_mode?: boolean;
  dispatch_mode?: "sync" | "async" | string;
  session_id?: string;
  dispatch_id?: string | null;
  state?: string | null;
  execution_runtime?: Record<string, unknown> | null;
  reject_code?: string | null;
  reject_reasons?: string[];
  api_version?: string;
};

export type RuntimeJobStatus = {
  active: boolean;
  phase?: string | null;
  dispatch_id?: string | null;
  heartbeat_at?: string | null;
  elapsed_seconds?: number | null;
  stale?: boolean;
  stale_reason?: string | null;
  stale_after_seconds?: number;
};

export type RuntimeHeartbeatStatus = {
  heartbeat_at?: string | null;
  elapsed_seconds?: number | null;
  stale?: boolean;
  stale_reason?: string | null;
  stale_after_seconds?: number;
  clip_target?: number | null;
  clip_observed?: number | null;
};

export type RuntimeProgressStatus = {
  clip_target?: number | null;
  clip_artifact_count?: number;
  clip_validated_count?: number;
};

export type CategoryRuntimeSlotStatus = {
  category_key: string;
  category_name: string;
  status?: string;
  provider?: string | null;
  artifacts?: unknown[];
  error?: unknown;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  cost_estimate?: unknown;
  executable?: boolean;
  future_router?: string | null;
};

export type RuntimeStatusResponse = {
  session_id: string;
  state?: string | null;
  category_runtime_slots?: CategoryRuntimeSlotStatus[];
  runtime_state?: string | null;
  provider_category?: string | null;
  provider_resolved?: string | null;
  provider_family?: string | null;
  provider_execution_mode?: string | null;
  learning_key?: string | null;
  operations_phase?: string | null;
  dispatch_id?: string | null;
  dispatched_at?: string | null;
  running_at?: string | null;
  completed_at?: string | null;
  clip_artifact_count?: number;
  failure?: Record<string, unknown> | null;
  preflight?: Record<string, unknown> | null;
  cost_telemetry?: Record<string, unknown> | null;
  job?: RuntimeJobStatus | null;
  heartbeat?: RuntimeHeartbeatStatus | null;
  progress?: RuntimeProgressStatus | null;
  execution_runtime?: Record<string, unknown> | null;
  api_version?: string;
};

export async function dispatchRuntime(
  sessionId: string,
  body: RuntimeDispatchRequest = {},
): Promise<RuntimeActionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/runtime/dispatch`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  const payload = (await response.json()) as RuntimeActionResponse;
  if (!response.ok) {
    throw new Error(JSON.stringify(payload));
  }
  return payload;
}

export function fetchRuntimeStatus(sessionId: string): Promise<RuntimeStatusResponse> {
  return request<RuntimeStatusResponse>(
    `/sessions/${encodeURIComponent(sessionId)}/runtime/status`,
  );
}

export type SessionActionType = "retry" | "cancel" | "archive" | "requeue";

export type ActionEligibilityItem = {
  allowed: boolean;
  reason: string;
};

export type SessionActionEligibility = {
  session_id: string;
  current_state: string;
  actions: Record<SessionActionType, ActionEligibilityItem>;
  api_version?: string;
};

export type SessionActionRequest = {
  reason?: string;
  actor?: string;
};

export type SessionActionResponse = {
  ok: boolean;
  session_id: string;
  action: string;
  previous_state?: string | null;
  next_state?: string | null;
  audit_event_id?: string | null;
  message?: string;
  code?: string | null;
  current_state?: string | null;
  reason?: string | null;
  reject_reasons?: string[];
  api_version?: string;
};

async function postJson<T>(path: string, body: unknown): Promise<{ response: Response; data: T }> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json()) as T;
  return { response, data };
}

export function fetchSessionActionEligibility(sessionId: string): Promise<SessionActionEligibility> {
  return request<SessionActionEligibility>(
    `/sessions/${encodeURIComponent(sessionId)}/actions/eligibility`,
  );
}

export async function postSessionAction(
  sessionId: string,
  action: SessionActionType,
  payload: SessionActionRequest = {},
): Promise<SessionActionResponse> {
  const { response, data } = await postJson<SessionActionResponse>(
    `/sessions/${encodeURIComponent(sessionId)}/actions/${action}`,
    {
      reason: payload.reason ?? "",
      actor: payload.actor ?? "operator",
    },
  );
  if (!response.ok || !data.ok) {
    throw new Error(JSON.stringify(data));
  }
  return data;
}
