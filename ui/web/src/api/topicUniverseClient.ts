import { resolveApiBaseUrl } from "../config/apiConfig";

const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export type TopicUniverseTitleEntry = {
  title_id: string;
  title: string;
  subtopic: string;
  category: string;
  intent: string;
  difficulty: string;
  estimated_viral_potential: number;
  educational_value: number;
  trend_score: number;
  source_provider: string;
  keywords: string[];
  suggested_duration: number;
  suggested_clip_count: number;
  content_strategy: string;
  duplicate_status: string;
};

export type TopicUniverseResult = {
  run_id: string;
  status: string;
  started_at: string;
  completed_at: string;
  total_duration_ms: number;
  input: Record<string, unknown>;
  title_bank: {
    topic: string;
    scope: Record<string, unknown>;
    mode: string;
    trend_mode: string;
    title_target: number;
    title_count: number;
    titles: TopicUniverseTitleEntry[];
    deduplication: Record<string, unknown>;
    notes: string[];
  };
  export_paths: Record<string, string>;
  e2e_handoff: Record<string, unknown>;
  errors: string[];
};

export type TopicUniverseGenerateResponse = {
  ok: boolean;
  message: string;
  result: TopicUniverseResult;
};

export type TopicUniverseHandoffResponse = {
  ok: boolean;
  message: string;
  selected_title: string;
  source_run_id?: string | null;
  result: Record<string, unknown>;
};

export type TopicUniversePreflightResponse = {
  ok: boolean;
  trend_mode: string;
  live_trend_providers_ready: string[];
  openai_story_ready: boolean;
  recommended_mode: string;
  title_bank_ready: boolean;
  checks: Record<string, { ready: boolean; label?: string; notes?: string }>;
};

export async function fetchTopicUniversePreflight(): Promise<TopicUniversePreflightResponse> {
  const response = await fetch(`${API_BASE_URL}/topic-universe-studio/preflight`);
  if (!response.ok) {
    throw new Error("Failed to fetch Topic Universe preflight status");
  }
  return response.json();
}

export async function postTopicUniverseGenerate(payload: {
  topic: string;
  language_code?: string | null;
  platform: string;
  audience_level: string;
  niche_style: string;
  title_target: number;
  use_live_trends: boolean;
  suggested_duration: number;
}): Promise<TopicUniverseGenerateResponse> {
  const response = await fetch(`${API_BASE_URL}/topic-universe-studio/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await response.json()) as TopicUniverseGenerateResponse | { detail?: unknown };
  if (!response.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? JSON.stringify(data.detail)
        : response.statusText;
    throw new Error(detail || "Topic Universe generation failed");
  }
  return data as TopicUniverseGenerateResponse;
}

export async function postTopicUniverseHandoffE2E(payload: {
  selected_title: string;
  source_run_id?: string | null;
  duration_seconds: number;
  platform: string;
  niche: string;
  mood: string;
}): Promise<TopicUniverseHandoffResponse> {
  const response = await fetch(`${API_BASE_URL}/topic-universe-studio/handoff-e2e`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await response.json()) as TopicUniverseHandoffResponse | { detail?: unknown };
  if (!response.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? JSON.stringify(data.detail)
        : response.statusText;
    throw new Error(detail || "E2E handoff failed");
  }
  return data as TopicUniverseHandoffResponse;
}

export async function postTopicUniverseOpenExport(path?: string | null): Promise<{
  ok: boolean;
  path: string;
  message: string;
}> {
  const response = await fetch(`${API_BASE_URL}/topic-universe-studio/open-export`, {
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
