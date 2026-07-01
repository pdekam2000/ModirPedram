import { useEffect, useState } from "react";
import {
  exchangeYouTubeAuth,
  fetchUploadCenterStatus,
  generateUploadMetadata,
  prepareUploadPackages,
  startYouTubeAuth,
  submitYouTubeUpload,
  type UploadCenterStatus,
} from "../api/platformClient";

function platformLabel(platform: string) {
  if (platform === "youtube_shorts") return "YouTube Shorts";
  if (platform === "instagram_reels") return "Instagram Reels";
  if (platform === "tiktok") return "TikTok";
  return platform;
}

export function UploadCenterPage() {
  const [status, setStatus] = useState<UploadCenterStatus | null>(null);
  const [runId, setRunId] = useState("");
  const [topic, setTopic] = useState("");
  const [authCode, setAuthCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh(nextRunId = runId) {
    const payload = await fetchUploadCenterStatus(nextRunId);
    setStatus(payload);
    if (!runId && payload.run_id) setRunId(payload.run_id);
    if (!topic && payload.topic) setTopic(payload.topic);
  }

  useEffect(() => {
    void refresh("").catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load upload status"));
  }, []);

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

  const packages = status?.upload_manifest?.packages || [];
  const metadataByPlatform = status?.metadata_by_platform || {};
  const youtubeAuth = status?.youtube_auth || {};

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

  function openPackageFolder() {
    const root = status?.upload_root || packages[0]?.platform_dir;
    if (!root) {
      setError("No upload package folder available yet.");
      return;
    }
    setMessage(`Package folder: ${root}`);
  }

  return (
    <div className="product-page">
      <header className="header">
        <div>
          <p className="eyebrow">Platform</p>
          <h1>Upload Center</h1>
          <p className="subtitle">Generate platform metadata, prepare upload packages, and upload to YouTube as private when confirmed.</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

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
            <button type="button" className="link-button" disabled={busy} onClick={openPackageFolder}>
              Open Package Folder
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
                {platform === "youtube_shorts" && meta && (
                  <pre className="code-block">{JSON.stringify(
                    {
                      title: meta.title,
                      description: meta.description,
                      hashtags: meta.hashtags,
                      privacy: meta.privacy,
                      pinned_comment: meta.pinned_comment,
                    },
                    null,
                    2,
                  )}</pre>
                )}
                {platform !== "youtube_shorts" && meta && (
                  <pre className="code-block">{JSON.stringify(
                    {
                      caption: meta.caption,
                      hashtags: meta.hashtags,
                      pinned_comment: meta.pinned_comment,
                    },
                    null,
                    2,
                  )}</pre>
                )}
              </div>
            );
          })}
        </section>
      </div>
    </div>
  );
}
