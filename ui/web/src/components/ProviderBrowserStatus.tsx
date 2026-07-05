import type { BrowserStatusResponse } from "../api/browserOperationsClient";
import type { RunwaySessionStatus } from "../api/platformClient";

type ProviderBrowserStatusProps = {
  runwaySession: RunwaySessionStatus | null;
  browserStatus: BrowserStatusResponse | null;
  klingUsesRunway: boolean;
};

function statusTone(connected: boolean, expired = false): "ok" | "warn" | "bad" {
  if (connected) {
    return "ok";
  }
  if (expired) {
    return "warn";
  }
  return "bad";
}

function ProviderRow({
  label,
  connected,
  expired,
  detail,
}: {
  label: string;
  connected: boolean;
  expired?: boolean;
  detail: string;
}) {
  const tone = statusTone(connected, expired);
  const valueText = connected ? "● Connected" : expired ? "● Session Expired" : "● Disconnected";
  return (
    <div className={`provider-browser-row ${tone}`}>
      <span className="provider-browser-label">{label}</span>
      <span className="provider-browser-value">{valueText}</span>
      <span className="provider-browser-detail muted">{detail}</span>
    </div>
  );
}

export function ProviderBrowserStatus({
  runwaySession,
  browserStatus,
  klingUsesRunway,
}: ProviderBrowserStatusProps) {
  const runwayConnected = Boolean(runwaySession?.connected);
  const runwayMsg = (runwaySession?.message || "").toLowerCase();
  const runwayExpired =
    !runwayConnected && (runwayMsg.includes("expired") || runwayMsg.includes("login"));

  const klingConnected = runwayConnected;
  const klingExpired = runwayExpired;

  const hailuoBrowserUp = Boolean(
    (browserStatus?.browser_connected || browserStatus?.browser_running) &&
      browserStatus?.cdp_connected,
  );

  return (
    <section className="card provider-browser-status" aria-label="Provider browser connections">
      <h2>Browser Connections</h2>
      <p className="muted">
        Kling 3.0 Pro runs inside the Runway web app — it shares the same Runway browser session.
        Hailuo uses the shared Chrome profile at hailuoai.video (no separate session file).
      </p>
      <ProviderRow
        label="Runway"
        connected={runwayConnected}
        expired={runwayExpired}
        detail="Session: project_brain/sessions/runway_session.json"
      />
      <ProviderRow
        label="Kling"
        connected={klingConnected}
        expired={klingExpired}
        detail={
          klingUsesRunway
            ? "Uses Runway browser · model Kling 3.0 Pro on app.runwayml.com"
            : "Uses Runway browser when Kling 3.0 Pro Native Audio is selected"
        }
      />
      <ProviderRow
        label="Hailuo"
        connected={hailuoBrowserUp}
        detail="Chrome CDP + profile · log in at hailuoai.video when using Hailuo"
      />
    </section>
  );
}

export function pwmapBrowserRequired(
  klingUiActive: boolean,
  provider: string,
  resolvedProvider: string,
): boolean {
  if (klingUiActive) {
    return true;
  }
  const active = resolvedProvider || provider;
  return active === "runway" || active === "runway_gen5";
}

export function isRunwaySessionExpired(session: RunwaySessionStatus | null): boolean {
  if (!session || session.connected) {
    return false;
  }
  const msg = (session.message || "").toLowerCase();
  return msg.includes("expired") || msg.includes("login");
}
