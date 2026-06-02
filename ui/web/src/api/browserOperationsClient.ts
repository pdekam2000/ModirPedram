import { API_BASE_URL } from "./client";

export type BrowserCheck = {
  id: string;
  passed: boolean;
  message: string;
};

export type BrowserStatusResponse = {
  browser_running: boolean;
  cdp_connected: boolean;
  profile_loaded: boolean;
  runway_login_detected: boolean;
  ready_for_runway_browser: boolean;
  profile_path: string;
  profile_path_relative: string;
  cdp_url: string;
  chrome_executable?: string | null;
  chrome_error?: string | null;
  message: string;
  checks: BrowserCheck[];
  last_launch?: Record<string, unknown> | null;
  api_version?: string;
};

export type BrowserLaunchResponse = {
  success: boolean;
  already_running: boolean;
  message: string;
  profile_path: string;
  cdp_url: string;
  chrome_executable?: string | null;
  cdp_port: number;
  pid?: number | null;
  api_version?: string;
};

export async function fetchBrowserStatus(): Promise<BrowserStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/operations/browser/status`);
  const data = (await response.json()) as BrowserStatusResponse & { detail?: unknown };
  if (!response.ok) {
    throw new Error(
      typeof data === "object" && data !== null && "message" in data
        ? String((data as { message?: string }).message)
        : "Failed to fetch browser status",
    );
  }
  return data;
}

export async function postBrowserLaunch(): Promise<BrowserLaunchResponse> {
  const response = await fetch(`${API_BASE_URL}/operations/browser/launch`, {
    method: "POST",
  });
  const data = (await response.json()) as BrowserLaunchResponse & { detail?: unknown };
  if (!response.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail?: string }).detail)
        : "Failed to launch browser";
    throw new Error(detail);
  }
  return data;
}
