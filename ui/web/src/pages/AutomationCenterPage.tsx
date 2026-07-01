import { useEffect, useState } from "react";
import {
  approveCommentDraft,
  automationCancelJob,
  automationPause,
  automationResume,
  automationStartNext,
  createAutomationJob,
  draftCommentReply,
  fetchAutomationStatus,
  rejectCommentDraft,
  updateAutomationCenter,
  type AutomationStatus,
} from "../api/platformClient";

function jobLabel(job: Record<string, unknown> | null | undefined) {
  if (!job) return "None";
  return String(job.title || job.topic || job.job_id || "Job");
}

export function AutomationCenterPage() {
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [commentText, setCommentText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const next = await fetchAutomationStatus();
    setStatus(next);
  }

  useEffect(() => {
    void refresh().catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load automation status"));
  }, []);

  async function runAction(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Automation action failed");
    } finally {
      setBusy(false);
    }
  }

  const upcoming = status?.jobs?.upcoming || [];
  const running = status?.jobs?.running || [];
  const completed = status?.jobs?.completed || [];
  const failed = status?.jobs?.failed || [];
  const drafts = status?.comment_drafts || [];
  const uploadPackages = status?.upload_packages || [];

  return (
    <div className="product-page">
      <header className="header">
        <div>
          <p className="eyebrow">Platform</p>
          <h1>Automation Center</h1>
          <p className="subtitle">Queue jobs, run the full pipeline one at a time, prepare uploads, and draft comment replies.</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="product-form-grid">
        <section className="card">
          <h2>Automation Status</h2>
          <ul>
            <li>Enabled: {status?.enabled ? "Yes" : "No"}</li>
            <li>Paused: {status?.paused ? "Yes" : "No"}</li>
            <li>Completed today: {status?.completed_today ?? 0} / {status?.max_jobs_per_day ?? 5}</li>
            <li>Running: {jobLabel(running[0] as Record<string, unknown>)}</li>
            <li>Next: {jobLabel(status?.next_job || (upcoming[0] as Record<string, unknown>))}</li>
          </ul>
          <div className="action-row">
            <button type="button" className="primary-btn" disabled={busy} onClick={() => void runAction(automationStartNext)}>
              Start next job
            </button>
            <button type="button" className="secondary-btn" disabled={busy} onClick={() => void runAction(automationPause)}>
              Pause automation
            </button>
            <button type="button" className="secondary-btn" disabled={busy} onClick={() => void runAction(automationResume)}>
              Resume automation
            </button>
          </div>
          <label className="field-row compact">
            <input
              type="checkbox"
              checked={Boolean(status?.enabled)}
              disabled={busy}
              onChange={(e) => void runAction(() => updateAutomationCenter({ enabled: e.target.checked }))}
            />
            Enable automation
          </label>
        </section>

        <section className="card">
          <h2>Queue Job</h2>
          <label className="field-row full-width">
            Title
            <input className="filter-input full-width" value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="field-row full-width">
            Topic
            <input className="filter-input full-width" value={topic} onChange={(e) => setTopic(e.target.value)} />
          </label>
          <button
            type="button"
            className="primary-btn"
            disabled={busy || !topic.trim()}
            onClick={() =>
              void runAction(() => createAutomationJob({ title, topic, duration: 30, clip_count: 3, platform_targets: ["youtube_shorts"] }))
            }
          >
            Add job
          </button>
        </section>

        <section className="card full-width">
          <h2>Queue</h2>
          {upcoming.length === 0 ? (
            <p className="muted">No upcoming jobs.</p>
          ) : (
            <ul>
              {upcoming.map((job) => (
                <li key={String(job.job_id)}>
                  <strong>{jobLabel(job as Record<string, unknown>)}</strong>
                  <span className="muted"> — {String(job.status || "planned")}</span>
                  <button
                    type="button"
                    className="secondary-btn"
                    disabled={busy}
                    onClick={() => void runAction(() => automationCancelJob(String(job.job_id)))}
                  >
                    Cancel
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <h2>Running Job</h2>
          {running.length === 0 ? <p className="muted">No job running.</p> : <p>{jobLabel(running[0] as Record<string, unknown>)}</p>}
        </section>

        <section className="card">
          <h2>Completed Jobs</h2>
          <ul>
            {completed.slice(0, 8).map((job) => (
              <li key={String(job.job_id)}>
                {jobLabel(job as Record<string, unknown>)}
                {job.output_path ? <div className="muted mono">{String(job.output_path)}</div> : null}
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2>Failed Jobs</h2>
          <ul>
            {failed.slice(0, 8).map((job) => (
              <li key={String(job.job_id)}>
                {jobLabel(job as Record<string, unknown>)}
                <div className="muted">{String(job.error || "Failed")}</div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card full-width">
          <h2>Upload Packages</h2>
          {uploadPackages.length === 0 ? (
            <p className="muted">No upload packages prepared yet.</p>
          ) : (
            <ul>
              {uploadPackages.map((pkg) => (
                <li key={String(pkg.package_dir)}>
                  <strong>{String(pkg.topic || "Upload package")}</strong>
                  <div className="muted mono">{String(pkg.package_dir || "")}</div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card full-width">
          <h2>Comment Agent Drafts</h2>
          <label className="field-row full-width">
            Incoming comment (placeholder)
            <textarea
              className="filter-input full-width"
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              rows={3}
            />
          </label>
          <button
            type="button"
            className="primary-btn"
            disabled={busy || !commentText.trim()}
            onClick={() => void runAction(() => draftCommentReply({ comment_text: commentText }))}
          >
            Generate draft reply
          </button>
          {drafts.length === 0 ? (
            <p className="muted">No drafts yet.</p>
          ) : (
            <ul>
              {drafts.slice(0, 8).map((draft, index) => (
                <li key={`${index}-${String(draft.comment_text || "")}`}>
                  <div>{String(draft.comment_text || "")}</div>
                  <div>
                    <strong>Suggested:</strong> {String(draft.suggested_reply || "")}
                  </div>
                  <div className="muted">
                    Risk: {String(draft.risk_level || "unknown")} — approve required: {String(draft.approve_required ?? true)}
                  </div>
                  <div className="action-row">
                    <button type="button" className="secondary-btn" disabled={busy} onClick={() => void runAction(() => approveCommentDraft(index))}>
                      Approve
                    </button>
                    <button type="button" className="secondary-btn" disabled={busy} onClick={() => void runAction(() => rejectCommentDraft(index))}>
                      Reject
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
