import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchRunwayLiveSmokeHandoffPreview,
  fetchRunwayLiveSmokeStatus,
  postRunwayLiveSmokeApprove,
  postRunwayLiveSmokeCancel,
  postRunwayLiveSmokeConnectUi,
  postRunwayLiveSmokeImageReady,
  postRunwayLiveSmokeStart,
  RunwayLiveSmokeHandoffPreview,
  RunwayLiveSmokeSnapshot,
} from "../api/runwayLiveSmokeClient";

const DEFAULT_STORY =
  "A lone astronaut on a rain-soaked platform above a neon cyberpunk city at night. She turns toward the skyline as rain intensifies.";

const DEFAULT_STORY_3CLIP =
  "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere. Clip 1: rain intensifies as she turns toward the skyline. Clip 2: she walks along the platform edge with city lights pulsing below. Clip 3: she reaches a dormant launch cradle and places her gloved hand on its surface.";

const CONTENT_BRAIN_SOURCE = "CONTENT_BRAIN_V83";

export type RunwayLiveSmokePanelMode = "phase_h" | "phase_i";

type RunwayLiveSmokeApprovalPanelProps = {
  mode?: RunwayLiveSmokePanelMode;
};

function panelMeta(mode: RunwayLiveSmokePanelMode) {
  if (mode === "phase_i") {
    return {
      title: "Runway 3-Clip Continuity — Phase I",
      subtitle: "1 starter image + 3 clips · Use Frame after clips 1–2 · 7 approval gates",
      clipCount: 3,
      projectId: "phase_i_live",
      defaultStory: DEFAULT_STORY_3CLIP,
    };
  }
  return {
    title: "Runway Live Smoke — Phase H",
    subtitle: "1 starter image + 1 clip · 3 approval gates",
    clipCount: 1,
    projectId: "live_smoke_h",
    defaultStory: DEFAULT_STORY,
  };
}

function gateTitle(snapshot: RunwayLiveSmokeSnapshot | null | undefined): string {
  if (!snapshot?.waiting) {
    return "No approval gate active";
  }
  if (snapshot.gate_type === "manual_hold") {
    return "Waiting: image ready";
  }
  if (snapshot.current_control_key) {
    return `Waiting: ${snapshot.current_control_key}`;
  }
  return "Waiting for operator action";
}

function previewFromReport(report: Record<string, unknown> | null): RunwayLiveSmokeHandoffPreview | null {
  if (!report?.prompt_source) {
    return null;
  }
  return {
    prompt_source: String(report.prompt_source || ""),
    content_brain_run_id: String(report.content_brain_run_id || ""),
    prompt_cleanup_used: Boolean(report.prompt_cleanup_used),
    prompt_noise_score:
      typeof report.prompt_noise_score === "number" ? report.prompt_noise_score : undefined,
    prompt_efficiency_score:
      typeof report.prompt_efficiency_score === "number" ? report.prompt_efficiency_score : undefined,
    loaded_from: String(report.handoff_loaded_from || ""),
    topic_label: String(report.topic_label || ""),
    content_brain_topic: String(report.content_brain_topic || ""),
    seo_title: String(report.seo_title || ""),
    story_summary: String(report.story_summary || ""),
    starter_prompt_preview: String(report.starter_prompt_preview || ""),
    handoff_version: String(report.handoff_version || ""),
  };
}

export function RunwayLiveSmokeApprovalPanel({ mode = "phase_h" }: RunwayLiveSmokeApprovalPanelProps) {
  const meta = panelMeta(mode);
  const [story, setStory] = useState(meta.defaultStory);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<RunwayLiveSmokeSnapshot | null>(null);
  const [active, setActive] = useState(false);
  const [reportOk, setReportOk] = useState<boolean | null>(null);
  const [handoffPreview, setHandoffPreview] = useState<RunwayLiveSmokeHandoffPreview | null>(null);
  const [lastReport, setLastReport] = useState<Record<string, unknown> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await fetchRunwayLiveSmokeStatus();
      setSnapshot(result.snapshot ?? null);
      const runActive = Boolean(result.active);
      setActive(runActive);
      if (!runActive && result.report && typeof result.report.ok === "boolean") {
        setReportOk(result.report.ok);
        setLastReport(result.report);
      }
    } catch {
      setSnapshot(null);
      setActive(false);
    }
  }, []);

  const refreshHandoffPreview = useCallback(async () => {
    try {
      const result = await fetchRunwayLiveSmokeHandoffPreview({
        clip_count: meta.clipCount,
      });
      setHandoffPreview(result.handoff_preview ?? null);
    } catch {
      setHandoffPreview(null);
    }
  }, [meta.clipCount]);

  useEffect(() => {
    void postRunwayLiveSmokeConnectUi().catch(() => undefined);
    void refresh();
    void refreshHandoffPreview();
    const timer = window.setInterval(() => void refresh(), 1500);
    return () => window.clearInterval(timer);
  }, [refresh, refreshHandoffPreview]);

  useEffect(() => {
    const timer = window.setInterval(() => void refreshHandoffPreview(), 5000);
    return () => window.clearInterval(timer);
  }, [refreshHandoffPreview]);

  const effectiveHandoff = useMemo(() => {
    return previewFromReport(lastReport) ?? handoffPreview;
  }, [handoffPreview, lastReport]);

  const contentBrainActive = effectiveHandoff?.prompt_source === CONTENT_BRAIN_SOURCE;

  const handoffDisplay = useMemo(() => {
    if (!effectiveHandoff) {
      return null;
    }
    return {
      promptSource: effectiveHandoff.prompt_source || "—",
      runId: effectiveHandoff.content_brain_run_id || "—",
      topicLabel: effectiveHandoff.topic_label || "—",
      contentBrainTopic: effectiveHandoff.content_brain_topic || "—",
      seoTitle: effectiveHandoff.seo_title || "—",
      storySummary: effectiveHandoff.story_summary || "—",
      starterPromptPreview: effectiveHandoff.starter_prompt_preview || "—",
      cleanupUsed:
        effectiveHandoff.prompt_cleanup_used === undefined
          ? "—"
          : effectiveHandoff.prompt_cleanup_used
            ? "yes"
            : "no",
      noiseScore:
        typeof effectiveHandoff.prompt_noise_score === "number"
          ? effectiveHandoff.prompt_noise_score.toFixed(4)
          : "—",
      efficiencyScore:
        typeof effectiveHandoff.prompt_efficiency_score === "number"
          ? effectiveHandoff.prompt_efficiency_score.toFixed(4)
          : "—",
    };
  }, [effectiveHandoff]);

  const waitingApproval = Boolean(snapshot?.waiting && snapshot?.gate_type === "approval");
  const waitingImageReady = Boolean(snapshot?.waiting && snapshot?.gate_type === "manual_hold");
  const gateEnabled = snapshot?.gate_enabled !== false;
  const canApprove = waitingApproval && gateEnabled;

  const statusLabel = useMemo(() => {
    if (active) return "running";
    if (!snapshot) return "idle";
    return snapshot.run_status || "idle";
  }, [active, snapshot]);

  const storyForRun = useMemo(() => {
    if (contentBrainActive) {
      return (
        effectiveHandoff?.content_brain_topic ||
        effectiveHandoff?.topic_label ||
        story
      );
    }
    return story;
  }, [contentBrainActive, effectiveHandoff, story]);

  async function startRun(simulate: boolean) {
    setStarting(true);
    setStartError(null);
    setActionError(null);
    setReportOk(null);
    try {
      await postRunwayLiveSmokeStart({
        story_idea: storyForRun,
        project_id: meta.projectId,
        operator: "operator",
        simulate,
        clip_count: meta.clipCount,
        execution_mode: "FULL_AUTO",
      });
      await refresh();
      await refreshHandoffPreview();
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Failed to start live smoke run");
    } finally {
      setStarting(false);
    }
  }

  async function runAction(action: "approve" | "image_ready" | "cancel") {
    setActionError(null);
    try {
      if (action === "approve") {
        await postRunwayLiveSmokeApprove();
      } else if (action === "image_ready") {
        await postRunwayLiveSmokeImageReady();
      } else {
        await postRunwayLiveSmokeCancel();
      }
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    }
  }

  return (
    <section className="card runway-live-smoke-panel">
      <div className="card-header">
        <div>
          <h2>{meta.title}</h2>
          <p className="muted">{meta.subtitle}</p>
        </div>
        <span className={`pill ${active ? "pill-live" : ""}`}>{active ? "RUN ACTIVE" : "IDLE"}</span>
      </div>

      {contentBrainActive && handoffDisplay ? (
        <article className="runway-live-smoke-content-brain-card">
          <div className="runway-live-smoke-content-brain-banner">
            <strong>Using Content Brain V8.3 prompts</strong>
            <span className="pill pill-live">CONTENT_BRAIN_V83</span>
          </div>
          <dl className="runway-live-smoke-meta">
            <div>
              <dt>Topic label</dt>
              <dd>{handoffDisplay.topicLabel}</dd>
            </div>
            <div>
              <dt>SEO title</dt>
              <dd>{handoffDisplay.seoTitle}</dd>
            </div>
            <div>
              <dt>Run ID</dt>
              <dd className="mono">{handoffDisplay.runId}</dd>
            </div>
            <div className="runway-live-smoke-meta-wide">
              <dt>Content Brain topic</dt>
              <dd>{handoffDisplay.contentBrainTopic}</dd>
            </div>
            <div className="runway-live-smoke-meta-wide">
              <dt>Story summary</dt>
              <dd>{handoffDisplay.storySummary}</dd>
            </div>
            <div className="runway-live-smoke-meta-wide">
              <dt>Starter prompt preview</dt>
              <dd className="mono small">{handoffDisplay.starterPromptPreview}</dd>
            </div>
          </dl>
        </article>
      ) : null}

      <div className="runway-live-smoke-grid">
        {contentBrainActive ? (
          <div className="runway-live-smoke-story runway-live-smoke-story--ignored">
            <span className="field-label">Manual story / video idea</span>
            <p className="muted small">
              Ignored while Content Brain V8.3 prompts are active. Switch to fallback mode only if export/handoff is unavailable.
            </p>
            <textarea value={story} rows={3} disabled readOnly aria-disabled="true" />
          </div>
        ) : (
          <label className="runway-live-smoke-story">
            <span className="field-label">Story / video idea</span>
            <p className="muted small">Used for fallback continuity prompt building when Content Brain handoff is unavailable.</p>
            <textarea value={story} rows={4} onChange={(event) => setStory(event.target.value)} />
          </label>
        )}

        <div className="runway-live-smoke-start-actions">
          <button type="button" disabled={starting || active} onClick={() => void startRun(false)}>
            {starting ? "Starting…" : meta.clipCount > 1 ? "Start 3-Clip Live (CDP)" : "Start Live Smoke (CDP)"}
          </button>
          <button type="button" className="secondary" disabled={starting || active} onClick={() => void startRun(true)}>
            Start Simulate Rehearsal
          </button>
        </div>
      </div>

      {startError && <div className="error-banner">{startError}</div>}
      {actionError && <div className="error-banner">{actionError}</div>}

      {handoffDisplay ? (
        <article className="runway-live-smoke-status-card runway-live-smoke-handoff-card">
          <h3>Prompt Handoff</h3>
          <dl className="runway-live-smoke-meta">
            <div>
              <dt>Prompt Source</dt>
              <dd className="mono">{handoffDisplay.promptSource}</dd>
            </div>
            <div>
              <dt>Run ID</dt>
              <dd className="mono">{handoffDisplay.runId}</dd>
            </div>
            <div>
              <dt>Prompt cleanup used</dt>
              <dd>{handoffDisplay.cleanupUsed}</dd>
            </div>
            <div>
              <dt>Noise score</dt>
              <dd>{handoffDisplay.noiseScore}</dd>
            </div>
            <div>
              <dt>Efficiency score</dt>
              <dd>{handoffDisplay.efficiencyScore}</dd>
            </div>
          </dl>
        </article>
      ) : null}

      <div className="runway-live-smoke-status-grid">
        <article className="runway-live-smoke-status-card">
          <h3>Execution Timeline</h3>
          <p className="runway-live-smoke-gate-title">
            {snapshot?.execution_mode || "FULL_AUTO"} · {snapshot?.current_step_id || "idle"}
          </p>
          <dl className="runway-live-smoke-meta">
            <div>
              <dt>Current step</dt>
              <dd className="mono">{snapshot?.current_step_id || "—"}</dd>
            </div>
            <div>
              <dt>Last action</dt>
              <dd className="mono">{snapshot?.last_auto_action || "—"}</dd>
            </div>
            <div>
              <dt>Next action</dt>
              <dd className="mono">{snapshot?.next_auto_action || "—"}</dd>
            </div>
            <div>
              <dt>Validation</dt>
              <dd>{snapshot?.auto_validation_state || "—"}</dd>
            </div>
            <div>
              <dt>Run status</dt>
              <dd>{statusLabel}</dd>
            </div>
          </dl>
        </article>

        <article className="runway-live-smoke-status-card">
          <h3>Legacy Gate (MANUAL mode)</h3>
          <p className="runway-live-smoke-gate-title">{gateTitle(snapshot)}</p>
          <dl className="runway-live-smoke-meta">
            <div>
              <dt>Status</dt>
              <dd>{statusLabel}</dd>
            </div>
            <div>
              <dt>Step</dt>
              <dd className="mono">{snapshot?.current_step_id || "—"}</dd>
            </div>
            <div>
              <dt>Control</dt>
              <dd className="mono">{snapshot?.current_control_key || "—"}</dd>
            </div>
            <div>
              <dt>Label</dt>
              <dd>{snapshot?.current_label || snapshot?.current_action || "—"}</dd>
            </div>
            <div>
              <dt>Gate ready</dt>
              <dd>{snapshot?.gate_ready === undefined ? "—" : snapshot.gate_ready ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Gate enabled</dt>
              <dd>{snapshot?.gate_enabled === undefined ? "—" : snapshot.gate_enabled ? "yes" : "no"}</dd>
            </div>
            {snapshot?.gate_reason ? (
              <div>
                <dt>Gate reason</dt>
                <dd>{snapshot.gate_reason}</dd>
              </div>
            ) : null}
          </dl>
        </article>

        <article className="runway-live-smoke-actions-card">
          <h3>Operator Actions</h3>
          <div className="runway-live-smoke-buttons">
            <button type="button" disabled={!canApprove} onClick={() => void runAction("approve")}>
              Approve
            </button>
            <button type="button" disabled={!waitingImageReady} onClick={() => void runAction("image_ready")}>
              Image Ready
            </button>
            <button type="button" className="danger" disabled={!active && !snapshot?.waiting} onClick={() => void runAction("cancel")}>
              Cancel Run
            </button>
          </div>
          {waitingApproval && !gateEnabled && (
            <p className="muted small" role="status">
              Approve disabled until clip generation is fully complete ({snapshot?.gate_reason || "waiting"}).
            </p>
          )}
          <p className="muted small">
            Default execution mode is FULL_AUTO — the pipeline validates and continues automatically.
            Use MANUAL mode only for debugging legacy approval gates.
          </p>
          {reportOk !== null && !active && (
            <p className={reportOk ? "success-text" : "error-text"}>
              Last run result: {reportOk ? "PASS" : "FAIL"}
            </p>
          )}
          {active && (
            <p className="muted small" role="status">
              Pipeline running in FULL_AUTO — status updates while clips generate.
            </p>
          )}
        </article>
      </div>

      <div className="runway-live-smoke-history-grid">
        <article>
          <h3>Auto Execution Log</h3>
          <div className="runway-live-smoke-log-box mono">
            {(snapshot?.auto_execution_timeline ?? []).length === 0 ? (
              <p className="muted">No automatic actions yet.</p>
            ) : (
              <ul>
                {(snapshot?.auto_execution_timeline ?? []).map((entry, index) => (
                  <li key={`${String(entry.timestamp || "")}-${index}`}>
                    {String(entry.timestamp || "")} · {String(entry.action || "")} · {String(entry.step_id || "")}
                    {entry.reason ? ` · ${String(entry.reason)}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </article>
        <article>
          <h3>Approval History</h3>
          <div className="runway-live-smoke-log-box">
            {(snapshot?.approval_history ?? []).length === 0 ? (
              <p className="muted">No approval events yet.</p>
            ) : (
              <ul>
                {(snapshot?.approval_history ?? []).map((entry, index) => (
                  <li key={`${entry.timestamp}-${index}`}>
                    <span className="mono">{String(entry.timestamp || "")}</span> · {String(entry.event || "")}
                    {entry.control_key ? ` · ${String(entry.control_key)}` : ""}
                    {entry.granted === false ? " · denied" : entry.granted ? " · granted" : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </article>
        <article>
          <h3>Runtime Logs</h3>
          <div className="runway-live-smoke-log-box mono">
            {(snapshot?.runtime_logs ?? []).length === 0 ? (
              <p className="muted">No runtime logs yet.</p>
            ) : (
              (snapshot?.runtime_logs ?? []).map((line, index) => <div key={`${line}-${index}`}>{line}</div>)
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
