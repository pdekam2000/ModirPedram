import { useCallback, useEffect, useState } from "react";
import {
  exchangeYouTubeAuth,
  fetchUploadCenterStatus,
  generateUploadMetadata,
  prepareUploadPackages,
  startYouTubeAuth,
  submitYouTubeUpload,
  updatePlatformSchedules,
  type PlatformScheduleEntry,
  type PlatformSchedulerState,
  type UploadCenterStatus,
} from "../api/platformClient";

const PLATFORMS = [
  { id: "youtube_shorts", label: "YouTube", logo: "▶", accent: "#ff4444" },
  { id: "instagram_reels", label: "Instagram", logo: "◎", accent: "#e1306c" },
  { id: "tiktok", label: "TikTok", logo: "♪", accent: "#25f4ee" },
] as const;

const VIDEOS_PER_DAY_OPTIONS = [1, 2, 3, 4, 5];
const INTERVAL_OPTIONS = [1, 2, 4, 6, 8];
const DURATION_OPTIONS = [15, 30, 45, 60];

function platformLabel(platform: string) {
  return PLATFORMS.find((item) => item.id === platform)?.label || platform;
}

function formatTime(iso: string | undefined) {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleString();
}

export function UploadCenterPage() {
  const [status, setStatus] = useState<UploadCenterStatus | null>(null);
  const [scheduler, setScheduler] = useState<PlatformSchedulerState | null>(null);
  const [runId, setRunId] = useState("");
  const [topic, setTopic] = useState("");
  const [authCode, setAuthCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);

  const refresh = useCallback(async (nextRunId = runId) => {
    const payload = await fetchUploadCenterStatus(nextRunId);
    setStatus(payload);
    if (payload.platform_scheduler) {
      setScheduler(payload.platform_scheduler);
    }
    if (!runId && payload.run_id) setRunId(payload.run_id);
    if (!topic && payload.topic) setTopic(payload.topic);
  }, [runId, topic]);

  useEffect(() => {
    void refresh("").catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load upload status"));
  }, [refresh]);

  async function runAction(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await action();
      if (result && typeof result === "object" && "message" in result) {
        setMessage(String((result as Record<string, unknown>).message || ""));
      }
      await refresh(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload action failed");
    } finally {
      setBusy(false);
    }
  }

  async function savePlatform(platformId: string, updates: Partial<PlatformScheduleEntry>) {
    setBusy(true);
    setError(null);
    try {
      const result = await updatePlatformSchedules({ platforms: { [platformId]: updates } });
      setScheduler(result);
      setMessage(`${platformLabel(platformId)} schedule saved.`);
      await refresh(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save platform schedule");
    } finally {
      setBusy(false);
    }
  }

  const packages = status?.upload_manifest?.packages || [];
  const metadataByPlatform = status?.metadata_by_platform || {};
  const youtubeAuth = status?.youtube_auth || {};
  const platformState = scheduler?.platforms || {};

  async function copyCaption(platform: string) {
    const meta = metadataByPlatform[platform] as Record<string, unknown> | undefined;
    const caption =
      platform === "youtube_shorts"
        ? String(meta?.description || meta?.title || "")
        : String(meta?.caption || "");
    if (!caption) {
      setError("No caption available for this platform.");
      return;
    }
    await navigator.clipboard.writeText(caption);
    setMessage(`${platformLabel(platform)} caption copied.`);
  }

  return (
    <div className="product-page upload-center-page">
      <header className="header">
        <div>
          <p className="eyebrow">Platform</p>
          <h1>Upload Center</h1>
          <p className="subtitle">
            Configure independent daily automation per platform. Each platform creates videos about its own topic and uploads on its own schedule.
          </p>
        </div>
        <div className="upload-center-global-status">
          <span className={`automation-pill ${scheduler?.automation_enabled ? "on" : "off"}`}>
            Automation {scheduler?.automation_enabled && !scheduler?.automation_paused ? "ON" : "OFF"}
          </span>
          <span className="muted">Daily cap: {scheduler?.daily_job_cap ?? 0} videos</span>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <div className="upload-platform-grid">
        {PLATFORMS.map((platform) => {
          const entry = platformState[platform.id] || {};
          const history = entry.upload_history || [];
          const timesPreview = (entry.upload_times_preview || []).join(", ") || "—";
          return (
            <section key={platform.id} className="card upload-platform-card" style={{ borderColor: `${platform.accent}33` }}>
              <div className="upload-platform-card-header">
                <div className="upload-platform-brand">
                  <span className="upload-platform-logo" style={{ color: platform.accent }}>
                    {platform.logo}
                  </span>
                  <h2>{platform.label}</h2>
                </div>
                <label className="upload-toggle">
                  <input
                    type="checkbox"
                    checked={Boolean(entry.enabled)}
                    disabled={busy}
                    onChange={(e) => void savePlatform(platform.id, { enabled: e.target.checked })}
                  />
                  <span>{entry.enabled ? "ON" : "OFF"}</span>
                </label>
              </div>

              <label className="field-row full-width">
                Topic for this platform
                <input
                  className="filter-input full-width"
                  value={entry.topic || ""}
                  disabled={busy}
                  placeholder={`e.g. ${platform.id === "youtube_shorts" ? "science facts" : platform.id === "instagram_reels" ? "beauty & makeup" : "men's fashion"}`}
                  onChange={(e) =>
                    setScheduler((current) => ({
                      ...(current || {}),
                      platforms: {
                        ...(current?.platforms || {}),
                        [platform.id]: { ...entry, topic: e.target.value },
                      },
                    }))
                  }
                  onBlur={() => {
                    const nextTopic = platformState[platform.id]?.topic ?? entry.topic;
                    if (nextTopic !== undefined) void savePlatform(platform.id, { topic: nextTopic });
                  }}
                />
              </label>

              <div className="upload-option-row">
                <span className="upload-option-label">Videos per day</span>
                <div className="chip-row">
                  {VIDEOS_PER_DAY_OPTIONS.map((count) => (
                    <button
                      key={count}
                      type="button"
                      className={`chip-btn ${Number(entry.videos_per_day || 3) === count ? "active" : ""}`}
                      disabled={busy}
                      onClick={() => void savePlatform(platform.id, { videos_per_day: count })}
                    >
                      {count}
                    </button>
                  ))}
                </div>
              </div>

              <div className="upload-option-row">
                <span className="upload-option-label">Video duration</span>
                <div className="chip-row">
                  {DURATION_OPTIONS.map((seconds) => (
                    <button
                      key={seconds}
                      type="button"
                      className={`chip-btn ${Number(entry.duration_seconds || 30) === seconds ? "active" : ""}`}
                      disabled={busy}
                      onClick={() => {
                        setScheduler((current) => ({
                          ...(current || {}),
                          platforms: {
                            ...(current?.platforms || {}),
                            [platform.id]: { ...entry, duration_seconds: seconds },
                          },
                        }));
                        void savePlatform(platform.id, { duration_seconds: seconds });
                      }}
                    >
                      {seconds}s
                    </button>
                  ))}
                </div>
              </div>

              <div className="upload-option-row">
                <span className="upload-option-label">Interval between uploads</span>
                <div className="chip-row">
                  {INTERVAL_OPTIONS.map((hours) => (
                    <button
                      key={hours}
                      type="button"
                      className={`chip-btn ${Number(entry.interval_hours || 4) === hours ? "active" : ""}`}
                      disabled={busy}
                      onClick={() => void savePlatform(platform.id, { interval_hours: hours })}
                    >
                      {hours}h
                    </button>
                  ))}
                </div>
              </div>

              <ul className="upload-platform-meta">
                <li>Today's upload times: <strong>{timesPreview}</strong></li>
                <li>
                  Upload status:{" "}
                  {entry.last_upload_success ? (
                    <span className="upload-status-ok">✓ Last upload succeeded</span>
                  ) : (
                    <span className="muted">No confirmed success yet</span>
                  )}
                </li>
              </ul>

              <div className="upload-history-block">
                <h3>Upload history</h3>
                {history.length === 0 ? (
                  <p className="muted">No uploads recorded yet for {platform.label}.</p>
                ) : (
                  <ul className="upload-history-list">
                    {history.map((item, index) => (
                      <li key={`${item.run_id || item.uploaded_at || index}`} className="upload-history-item">
                        <span className={item.success ? "upload-status-ok" : "upload-status-fail"}>
                          {item.success ? "✓" : "✗"}
                        </span>
                        <div>
                          <strong>{item.title || "Untitled"}</strong>
                          <div className="muted">{formatTime(item.uploaded_at)}</div>
                          {!item.success && item.error ? <div className="upload-status-fail">{item.error}</div> : null}
                          {(item.post_url || item.youtube_url) ? (
                            <a
                              className="link-button"
                              href={item.post_url || item.youtube_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {platform.id === "youtube_shorts"
                                ? "View on YouTube"
                                : platform.id === "instagram_reels"
                                  ? "View on Instagram"
                                  : "View on TikTok"}
                            </a>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <section className="card full-width manual-upload-section">
        <button type="button" className="link-button manual-upload-toggle" onClick={() => setManualOpen((v) => !v)}>
          {manualOpen ? "Hide" : "Show"} manual upload tools (existing workflow — unchanged)
        </button>

        {manualOpen ? (
          <div className="product-form-grid">
            <section className="card">
              <h2>Latest Publish Package</h2>
              <ul>
                <li>Run ID: {status?.run_id || "None"}</li>
                <li>Topic: {status?.topic || "None"}</li>
                <li>Upload root: {status?.upload_root || "Not prepared"}</li>
                <li>Auto-upload: {status?.auto_upload_enabled ? "Enabled" : "Off"}</li>
              </ul>
              <label className="field-row full-width">
                Run ID override
                <input className="filter-input full-width" value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="cb_e2e_..." />
              </label>
              <label className="field-row full-width">
                Topic
                <input className="filter-input full-width" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Video topic" />
              </label>
            </section>

            <section className="card">
              <h2>YouTube Auth Status</h2>
              <ul>
                <li>Enabled: {youtubeAuth.enabled ? "Yes" : "No"}</li>
                <li>Credentials configured: {youtubeAuth.credentials_configured ? "Yes" : "No"}</li>
                <li>Authenticated: {youtubeAuth.authenticated ? "Yes" : "No"}</li>
                <li>Connect required: {youtubeAuth.connect_required ? "Yes" : "No"}</li>
                <li>Default privacy: private</li>
              </ul>
              <div className="action-row">
                <button
                  type="button"
                  className="primary-button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(async () => {
                      const result = await startYouTubeAuth();
                      if (result.authorization_url) {
                        setMessage(`Open this URL to connect YouTube: ${String(result.authorization_url)}`);
                      }
                      return result;
                    })
                  }
                >
                  Get Connect URL
                </button>
              </div>
              <label className="field-row full-width">
                OAuth code
                <input className="filter-input full-width" value={authCode} onChange={(e) => setAuthCode(e.target.value)} placeholder="Paste Google OAuth code" />
              </label>
              <button
                type="button"
                className="secondary-button"
                disabled={busy || !authCode}
                onClick={() => void runAction(async () => exchangeYouTubeAuth(authCode))}
              >
                Complete YouTube Connect
              </button>
            </section>

            <section className="card full-width">
              <h2>Platform Targets & Metadata</h2>
              <div className="action-row">
                <button
                  type="button"
                  className="primary-button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(async () =>
                      generateUploadMetadata({
                        run_id: runId,
                        topic,
                        platform_targets: status?.platform_targets || [],
                      }),
                    )
                  }
                >
                  Generate Metadata
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(async () =>
                      prepareUploadPackages({
                        run_id: runId,
                        topic,
                        platform_targets: status?.platform_targets || [],
                      }),
                    )
                  }
                >
                  Prepare Upload Packages
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(async () =>
                      submitYouTubeUpload({
                        run_id: runId,
                        confirmed: true,
                        upload_package: status?.latest_legacy_package || {},
                      }),
                    )
                  }
                >
                  Upload to YouTube Private
                </button>
                <button type="button" className="secondary-button" disabled={busy} onClick={() => void copyCaption("tiktok")}>
                  Copy TikTok Caption
                </button>
                <button type="button" className="secondary-button" disabled={busy} onClick={() => void copyCaption("instagram_reels")}>
                  Copy Instagram Caption
                </button>
              </div>

              {(status?.platform_targets || []).map((platform) => {
                const meta = metadataByPlatform[platform] as Record<string, unknown> | undefined;
                const pkg = packages.find((item) => item.platform === platform);
                return (
                  <div key={platform} className="upload-platform-block">
                    <h3>{platformLabel(platform)}</h3>
                    <ul>
                      <li>Package status: {String(pkg?.status || "not_prepared")}</li>
                      <li>Manual upload only: {pkg?.manual_upload_only ? "Yes" : "No"}</li>
                      <li>Auto-upload: {pkg?.auto_upload ? "Yes" : "No"}</li>
                      <li>Metadata source: {String(meta?.source || "n/a")}</li>
                    </ul>
                  </div>
                );
              })}
            </section>
          </div>
        ) : null}
      </section>
    </div>
  );
}
