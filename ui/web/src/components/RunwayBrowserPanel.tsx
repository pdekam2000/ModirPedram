import { useCallback, useEffect, useState } from "react";
import {
  fetchBrowserStatus,
  postBrowserLaunch,
  type BrowserStatusResponse,
} from "../api/browserOperationsClient";
import {
  connectRunwayBrowser,
  fetchBrowserHealth,
  fetchRunwaySessionStatus,
  openPlatformBrowser,
  reconnectPlatformBrowser,
  refreshRunwayPage,
  saveRunwayBrowserSession,
  type BrowserHealth,
  type RunwaySessionStatus,
} from "../api/platformClient";

type StatusKey =
  | "browser_running"
  | "cdp_connected"
  | "profile_loaded"
  | "runway_login_detected";

const RUNWAY_STATUS_LABELS: Record<StatusKey, string> = {
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

function cdpPort(status: BrowserStatusResponse | null): number {
  return status?.cdp_port ?? 9222;
}

function browserConnected(status: BrowserStatusResponse | null): boolean {
  if (!status) return false;
  return status.browser_connected ?? status.browser_running;
}

function cdpReachable(status: BrowserStatusResponse | null): boolean {
  if (!status) return false;
  return status.cdp_connected || status.cdp_reachable === true || status.browser_running;
}

type RunwayBrowserPanelProps = {
  compact?: boolean;
  /** User Mode: simplified status card. Developer Mode: include Runway login checks. */
  showRunwayDetails?: boolean;
};

export function RunwayBrowserPanel({ compact = false, showRunwayDetails = true }: RunwayBrowserPanelProps) {
  const [status, setStatus] = useState<BrowserStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [launchMessage, setLaunchMessage] = useState<string | null>(null);
  const [health, setHealth] = useState<BrowserHealth | null>(null);
  const [refreshConfirm, setRefreshConfirm] = useState(false);
  const [runwaySession, setRunwaySession] = useState<RunwaySessionStatus | null>(null);
  const [connectingRunway, setConnectingRunway] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchBrowserStatus();
      setStatus(payload);
      const [healthPayload, sessionPayload] = await Promise.all([
        fetchBrowserHealth(),
        fetchRunwaySessionStatus(false),
      ]);
      setHealth(healthPayload);
      setRunwaySession(sessionPayload);
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

  async function handleConnectRunway() {
    setConnectingRunway(true);
    setError(null);
    setLaunchMessage(null);
    try {
      let session = await connectRunwayBrowser();
      setRunwaySession(session);
      setLaunchMessage(session.message);
      await refresh();

      if (!session.connected && session.awaiting_login) {
        for (let attempt = 0; attempt < 40; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 3000));
          const healthPayload = await fetchBrowserHealth();
          if (!healthPayload.runway_tab_found) continue;
          session = await saveRunwayBrowserSession();
          setRunwaySession(session);
          if (session.connected) {
            setLaunchMessage(session.message || "Runway session saved ✓");
            await refresh();
            break;
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect Runway browser");
    } finally {
      setConnectingRunway(false);
    }
  }

  async function handleLaunch() {
    setLaunching(true);
    setError(null);
    setLaunchMessage(null);
    try {
      const result = await openPlatformBrowser().catch(() => postBrowserLaunch());
      setLaunchMessage(result.message);
      let latest = await fetchBrowserStatus();
      setStatus(latest);
      if (result.cdp_reachable) {
        for (let attempt = 0; attempt < 4; attempt += 1) {
          if (browserConnected(latest)) break;
          await new Promise((resolve) => window.setTimeout(resolve, 750));
          latest = await fetchBrowserStatus();
          setStatus(latest);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to launch browser");
    } finally {
      setLaunching(false);
    }
  }

  const connected = browserConnected(status);
  const reachable = cdpReachable(status);
  const port = cdpPort(status);

  return (
    <section className={`card runway-browser-card ${compact ? "runway-browser-card-compact" : ""}`}>
      <div className="card-header">
        <div>
          <h2>Browser Status</h2>
          <p className="muted runway-browser-subtitle">
            {showRunwayDetails
              ? "Controlled Chrome with CDP on port 9222 for Runway browser mode. Sign in manually once; keep the browser open."
              : "Launch Chrome with remote debugging before generating Runway videos."}
          </p>
        </div>
        <div className="runway-browser-actions">
          <button type="button" onClick={() => void refresh()} disabled={loading || launching}>
            {loading ? "Checking…" : "Refresh"}
          </button>
          <button
            type="button"
            className={`runway-browser-launch-btn ${runwaySession?.connected ? "runway-session-connected" : ""}`}
            onClick={() => void handleConnectRunway()}
            disabled={connectingRunway || launching}
          >
            {connectingRunway
              ? "Connecting…"
              : runwaySession?.connected
                ? "● Connected"
                : "🔐 Connect Runway Browser"}
          </button>
          <button
            type="button"
            className="runway-browser-launch-btn"
            onClick={() => void handleLaunch()}
            disabled={launching}
          >
            {launching ? "Launching…" : "Open Browser"}
          </button>
          <button type="button" onClick={() => void reconnectPlatformBrowser().then(() => refresh())} disabled={launching}>
            Reconnect
          </button>
          <button
            type="button"
            onClick={() => {
              if (health?.generation_active && !refreshConfirm) {
                setRefreshConfirm(true);
                return;
              }
              void refreshRunwayPage(refreshConfirm)
                .then((result) => {
                  setLaunchMessage(result.message);
                  setRefreshConfirm(false);
                  return refresh();
                })
                .catch((err: unknown) => setError(err instanceof Error ? err.message : "Refresh failed"));
            }}
            disabled={launching || health?.generation_active === true && !refreshConfirm}
          >
            {refreshConfirm ? "Confirm Refresh" : "Refresh Runway Page"}
          </button>
        </div>
      </div>

      {!connected && !loading && (
        <div className="runway-browser-disconnected">Browser not connected</div>
      )}

      <div className={`runway-session-status ${runwaySession?.connected ? "ok" : "pending"}`}>
        Runway: {runwaySession?.connected ? "● Connected" : "● Disconnected"}
        {runwaySession?.message && <span className="muted"> — {runwaySession.message}</span>}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {launchMessage && <div className="runway-browser-launch-msg">{launchMessage}</div>}
      {health?.last_heartbeat && (
        <p className="muted">Last heartbeat: {health.last_heartbeat}</p>
      )}
      {health?.generation_active && (
        <p className="muted">Generation active — refresh blocked unless confirmed.</p>
      )}

      <div className="runway-browser-status-grid">
        <article className={`runway-browser-status-tile ${connected ? "ok" : "pending"}`}>
          <span className="runway-browser-status-label">Browser Status</span>
          <span className={`runway-browser-status-value ${connected ? "ok" : ""}`}>
            {connected ? "Connected" : "Not Connected"}
          </span>
        </article>
        <article className={`runway-browser-status-tile ${reachable ? "ok" : "pending"}`}>
          <span className="runway-browser-status-label">CDP</span>
          <span className={`runway-browser-status-value ${reachable ? "ok" : ""}`}>
            {reachable ? "Reachable" : "Unreachable"}
          </span>
        </article>
        <article className={`runway-browser-status-tile ${health?.runway_tab_found ? "ok" : "pending"}`}>
          <span className="runway-browser-status-label">Runway Tab</span>
          <span className={`runway-browser-status-value ${health?.runway_tab_found ? "ok" : ""}`}>
            {health?.runway_tab_found ? "Found" : "Not Found"}
          </span>
        </article>
        <article className="runway-browser-status-tile ok">
          <span className="runway-browser-status-label">Current Port</span>
          <span className="runway-browser-status-value ok">{port}</span>
        </article>
      </div>

      <div className="runway-browser-meta">
        <div className="runway-browser-meta-row">
          <span className="muted">Browser</span>
          <select className="runway-browser-kind-select" value={status?.browser_kind ?? "chrome"} disabled>
            <option value="chrome">Chrome</option>
            <option value="edge">Edge (coming soon)</option>
          </select>
        </div>
        {status?.cdp_url && (
          <div className="runway-browser-meta-row">
            <span className="muted">CDP URL</span>
            <span className="mono">{status.cdp_url}</span>
          </div>
        )}
      </div>

      {showRunwayDetails && (
        <>
          <div className="runway-browser-status-grid runway-browser-detail-grid">
            {(Object.keys(RUNWAY_STATUS_LABELS) as StatusKey[]).map((key) => {
              const passed = checkPassed(status, key);
              const check = status?.checks?.find((item) => item.id === key);
              return (
                <article key={key} className={`runway-browser-status-tile ${passed ? "ok" : "pending"}`}>
                  <span className="runway-browser-status-label">{RUNWAY_STATUS_LABELS[key]}</span>
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
        </>
      )}
    </section>
  );
}
