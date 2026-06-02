import { useCallback, useEffect, useState } from "react";
import {
  fetchBrowserStatus,
  postBrowserLaunch,
  type BrowserStatusResponse,
} from "../api/browserOperationsClient";

type StatusKey =
  | "browser_running"
  | "cdp_connected"
  | "profile_loaded"
  | "runway_login_detected";

const STATUS_LABELS: Record<StatusKey, string> = {
  browser_running: "Browser Running",
  cdp_connected: "CDP Connected",
  profile_loaded: "Profile Loaded",
  runway_login_detected: "Runway Login Detected",
};

function checkPassed(status: BrowserStatusResponse | null, key: StatusKey): boolean {
  if (!status) return false;
  if (key === "browser_running") return status.browser_running;
  if (key === "cdp_connected") return status.cdp_connected;
  if (key === "profile_loaded") return status.profile_loaded;
  return status.runway_login_detected;
}

export function RunwayBrowserPanel({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<BrowserStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [launchMessage, setLaunchMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchBrowserStatus();
      setStatus(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load browser status");
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function handleLaunch() {
    setLaunching(true);
    setError(null);
    setLaunchMessage(null);
    try {
      const result = await postBrowserLaunch();
      setLaunchMessage(result.message);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to launch browser");
    } finally {
      setLaunching(false);
    }
  }

  return (
    <section className={`card runway-browser-card ${compact ? "runway-browser-card-compact" : ""}`}>
      <div className="card-header">
        <div>
          <h2>Runway Browser</h2>
          <p className="muted runway-browser-subtitle">
            Controlled Chrome profile for Runway browser mode. Sign in manually once; keep the browser open.
          </p>
        </div>
        <div className="runway-browser-actions">
          <button type="button" onClick={() => void refresh()} disabled={loading || launching}>
            {loading ? "Checking…" : "Refresh status"}
          </button>
          <button
            type="button"
            className="runway-browser-launch-btn"
            onClick={() => void handleLaunch()}
            disabled={launching}
          >
            {launching ? "Launching…" : "Open Runway Browser"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {launchMessage && <div className="runway-browser-launch-msg">{launchMessage}</div>}

      <div className="runway-browser-status-grid">
        {(Object.keys(STATUS_LABELS) as StatusKey[]).map((key) => {
          const passed = checkPassed(status, key);
          const check = status?.checks?.find((item) => item.id === key);
          return (
            <article key={key} className={`runway-browser-status-tile ${passed ? "ok" : "pending"}`}>
              <span className="runway-browser-status-label">{STATUS_LABELS[key]}</span>
              <span className={`runway-browser-status-value ${passed ? "ok" : ""}`}>
                {passed ? "Yes" : "No"}
              </span>
              {check?.message && <p className="runway-browser-status-detail">{check.message}</p>}
            </article>
          );
        })}
      </div>

      {status && (
        <div className="runway-browser-meta">
          <div className="runway-browser-meta-row">
            <span className="muted">Profile</span>
            <span className="mono">{status.profile_path_relative}</span>
          </div>
          <div className="runway-browser-meta-row">
            <span className="muted">CDP</span>
            <span className="mono">{status.cdp_url}</span>
          </div>
          {status.chrome_executable && (
            <div className="runway-browser-meta-row">
              <span className="muted">Chrome</span>
              <span className="mono">{status.chrome_executable}</span>
            </div>
          )}
          {status.chrome_error && (
            <div className="runway-browser-meta-row">
              <span className="muted">Chrome</span>
              <span className="runway-browser-error">{status.chrome_error}</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
