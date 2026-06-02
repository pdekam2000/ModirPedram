/** Single source of truth for ModirAgentOS Control Center API base URL. */
export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8765";

export function resolveApiBaseUrl(envValue: string | undefined): string {
  const trimmed = envValue?.trim().replace(/\/$/, "");
  return trimmed || DEFAULT_API_BASE_URL;
}
