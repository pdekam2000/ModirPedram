import { resolveApiBaseUrl } from "../config/apiConfig";

const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export type ContentBrainTestStep = {
  step: number;
  step_key: string;
  title: string;
  duration_ms: number;
  api_sources: string[];
  provider_costs?: Record<string, unknown>;
  payload: Record<string, unknown>;
  error?: string;
};

export type ContentBrainTestResult = {
  run_id: string;
  started_at: string;
  completed_at: string;
  status: string;
  input: Record<string, unknown>;
  steps: ContentBrainTestStep[];
  quality_audit: Record<string, unknown>;
  overall_content_score: number;
  export_paths: Record<string, string>;
  errors: string[];
  total_duration_ms: number;
};

export type ContentBrainTestStudioResponse = {
  ok: boolean;
  message: string;
  result: ContentBrainTestResult;
};

export type ContentBrainPreflightCheck = {
  ready: boolean;
  mode?: string;
  label?: string;
  active?: boolean;
  notes?: string;
};

export type ContentBrainPreflightResponse = {
  ok: boolean;
  trend_mode: string;
  live_trend_providers_ready: string[];
  openai_story_ready: boolean;
  recommended_mode: string;
  checks: Record<string, ContentBrainPreflightCheck>;
};

export type ContentBrainStudioStatusResponse = {
  ok: boolean;
  running: boolean;
  last_error: string;
  last_result: ContentBrainTestStudioResponse | null;
  preflight?: ContentBrainPreflightResponse;
  export_dir?: string;
};

export function findStep(
  result: ContentBrainTestResult | null | undefined,
  stepKey: string,
): ContentBrainTestStep | undefined {
  return result?.steps?.find((step) => step.step_key === stepKey);
}

export async function fetchContentBrainTestStudioPreflight(): Promise<ContentBrainPreflightResponse> {
  const response = await fetch(`${API_BASE_URL}/content-brain-test-studio/preflight`);
  if (!response.ok) {
    throw new Error("Failed to fetch Content Brain preflight status");
  }
  return response.json();
}

export async function postContentBrainTestStudioRun(payload: {
  topic: string;
  duration_seconds: number;
  platform: string;
  niche: string;
  mood: string;
  clip_length_preference?: number | null;
}): Promise<ContentBrainTestStudioResponse> {
  const response = await fetch(`${API_BASE_URL}/content-brain-test-studio/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await response.json()) as ContentBrainTestStudioResponse | { detail?: unknown };
  if (!response.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? JSON.stringify(data.detail)
        : response.statusText;
    throw new Error(detail || "Content Brain test run failed");
  }
  return data as ContentBrainTestStudioResponse;
}

export async function fetchContentBrainTestStudioStatus(): Promise<ContentBrainStudioStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/content-brain-test-studio/status`);
  if (!response.ok) {
    throw new Error("Failed to fetch Content Brain test studio status");
  }
  return response.json();
}

export async function postContentBrainOpenExportFolder(path?: string | null): Promise<{
  ok: boolean;
  path: string;
  message: string;
}> {
  const response = await fetch(`${API_BASE_URL}/content-brain-test-studio/open-export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: path || null }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(typeof data === "object" && data?.detail ? JSON.stringify(data.detail) : "Open export failed");
  }
  return data;
}
