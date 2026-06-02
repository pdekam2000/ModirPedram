import { useCallback, useEffect, useMemo, useState } from "react";
import {
  buildUatRunPayload,
  postUatReview,
  postUatRun,
  uatFinalVideoUrl,
  UatAssemblyMode,
  UatPlatform,
  UatRunResponse,
  UatVideoProvider,
  UatVoiceProvider,
} from "../api/uatRuntimeClient";
import { useUatStatusPoll } from "../hooks/useUatStatusPoll";
import { fetchBrowserStatus, type BrowserStatusResponse } from "../api/browserOperationsClient";
import { RunwayBrowserPanel } from "../components/RunwayBrowserPanel";
import {
  evaluateUatGenerateEligibility,
  showAssemblyApprovalGate,
  showRealVideoApprovalGate,
  showVoiceApprovalGate,
  uatDefaultDurationSeconds,
  uatDurationBounds,
  UatFormState,
} from "../utils/uatRuntimeEligibility";
import {
  assemblyModeChip,
  estimateUatCostUsd,
  formatPlatformLabel,
  providerChipLabel,
  REVIEW_SCORE_FIELDS,
  stageStatus,
  UAT_BRAND_SUBTITLE,
  UAT_BRAND_TITLE,
  UAT_GENERATE_LABEL,
  UAT_SAFETY_WARNING,
  UAT_STAGE_ORDER,
  UatWorkspaceStatus,
  videoProviderChip,
  voiceProviderChip,
  workspaceStatusFromRun,
} from "../utils/uatRuntimeLabels";
import "../styles/uat-runtime.css";

const DEFAULT_FORM: UatFormState = {
  topic: "",
  platform: "youtube_shorts",
  durationSeconds: 10,
  videoProvider: "runway_browser",
  voiceProvider: "elevenlabs",
  assemblyMode: "dry_run_only",
  confirmRealVoice: false,
  confirmRealVideo: false,
  confirmRealAssembly: false,
  oneRunAcknowledged: false,
};

type ReviewScores = Record<(typeof REVIEW_SCORE_FIELDS)[number]["key"], number>;

const DEFAULT_SCORES: ReviewScores = {
  story_quality_score: 7,
  visual_quality_score: 7,
  voice_quality_score: 7,
  subtitle_quality_score: 7,
  continuity_score: 7,
  overall_quality_score: 7,
};

export function UatRuntimePage() {
  const [form, setForm] = useState<UatFormState>(DEFAULT_FORM);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [reviewScores, setReviewScores] = useState<ReviewScores>(DEFAULT_SCORES);
  const [comments, setComments] = useState("");
  const [publishable, setPublishable] = useState<boolean | null>(null);
  const [reviewSaved, setReviewSaved] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [savingReview, setSavingReview] = useState(false);
  const [browserStatus, setBrowserStatus] = useState<BrowserStatusResponse | null>(null);

  const refreshBrowserStatus = useCallback(async () => {
    try {
      setBrowserStatus(await fetchBrowserStatus());
    } catch {
      setBrowserStatus(null);
    }
  }, []);

  useEffect(() => {
    if (form.videoProvider !== "runway_browser") {
      return;
    }
    void refreshBrowserStatus();
    const timer = window.setInterval(() => void refreshBrowserStatus(), 5000);
    return () => window.clearInterval(timer);
  }, [form.videoProvider, refreshBrowserStatus]);

  const { status, polling, error: pollError } = useUatStatusPoll(sessionId, Boolean(sessionId));
  const running = starting || polling || status?.status === "running";

  const workspaceStatus: UatWorkspaceStatus = workspaceStatusFromRun(status, running);
  const eligibility = useMemo(
    () => evaluateUatGenerateEligibility(form, running, browserStatus),
    [form, running, browserStatus],
  );

  async function handleGenerate() {
    if (!eligibility.canGenerate) return;
    setStarting(true);
    setStartError(null);
    setReviewSaved(false);
    setReviewError(null);
    try {
      const payload = buildUatRunPayload({
        topic: form.topic,
        platform: form.platform,
        durationSeconds: form.durationSeconds,
        videoProvider: form.videoProvider,
        voiceProvider: form.voiceProvider,
        assemblyMode: form.assemblyMode,
        confirmRealVoice: form.confirmRealVoice,
        confirmRealVideo: form.confirmRealVideo,
        confirmRealAssembly: form.confirmRealAssembly,
      });
      const response = await postUatRun(payload);
      setSessionId(response.session_id);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Failed to start UAT");
    } finally {
      setStarting(false);
    }
  }

  async function handleSaveReview() {
    if (!sessionId || publishable === null) return;
    setSavingReview(true);
    setReviewError(null);
    try {
      await postUatReview(sessionId, {
        ...reviewScores,
        comments,
        publishable,
        submitted_by: "operator_uat",
      });
      setReviewSaved(true);
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : "Failed to save review");
    } finally {
      setSavingReview(false);
    }
  }

  function copySessionId() {
    if (sessionId) void navigator.clipboard.writeText(sessionId);
  }

  const costEstimate = estimateUatCostUsd(form);
  const showVideo = status?.status === "completed" && Boolean(sessionId);

  return (
    <div className="uat-workspace">
      <header className="uat-brand-header">
        <div>
          <h1 className="uat-brand-title">{UAT_BRAND_TITLE}</h1>
          <p className="uat-brand-subtitle">{UAT_BRAND_SUBTITLE}</p>
        </div>
        <span className={`uat-status-pill ${workspaceStatus.toLowerCase()}`}>{workspaceStatus}</span>
      </header>

      {(startError || pollError) && (
        <div className="error-banner">{startError || pollError}</div>
      )}

      <div className="uat-grid">
        <aside className="uat-left">
          <MissionSetupCard form={form} onChange={setForm} disabled={running} />
          <ProviderStackCard form={form} onChange={setForm} disabled={running} />
          {form.videoProvider === "runway_browser" && <RunwayBrowserPanel compact />}
          <SafetyGateCard form={form} onChange={setForm} disabled={running} />
          <button
            type="button"
            className="uat-generate-btn"
            disabled={!eligibility.canGenerate || starting}
            onClick={() => void handleGenerate()}
          >
            {starting ? "Starting…" : UAT_GENERATE_LABEL}
          </button>
          {!eligibility.canGenerate && eligibility.reasons.length > 0 && (
            <ul className="uat-block-hints">
              {eligibility.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
          {eligibility.preflightWarnings.length > 0 && (
            <ul className="uat-preflight-warnings">
              {eligibility.preflightWarnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </aside>

        <section className="uat-glass-card">
          <h2 className="uat-card-title">Runtime Monitor</h2>
          <RuntimeMonitor status={status} running={running} />
        </section>

        <aside className="uat-glass-card">
          <h2 className="uat-card-title">Session Intelligence</h2>
          <SessionIntelligence
            sessionId={sessionId}
            status={status}
            form={form}
            costEstimate={costEstimate}
            onCopySessionId={copySessionId}
          />
        </aside>
      </div>

      <div className="uat-bottom">
        <section className="uat-glass-card">
          <h2 className="uat-card-title">Video Preview</h2>
          {showVideo && sessionId ? (
            <>
              <p className="muted">FINAL_PUBLISH_READY.mp4</p>
              <div className="uat-video-wrap">
                <video controls src={uatFinalVideoUrl(sessionId)} />
              </div>
              <div className="uat-action-row">
                {status?.artifact_folder && (
                  <button type="button" className="uat-action-btn" disabled title="Desktop only">
                    Open Folder
                  </button>
                )}
                {status?.report_path && (
                  <button type="button" className="uat-action-btn" disabled title="Open via file explorer">
                    Open Report
                  </button>
                )}
                <button type="button" className="uat-action-btn" onClick={copySessionId}>
                  Copy Session ID
                </button>
              </div>
            </>
          ) : (
            <p className="muted">Complete a UAT run to preview the final video here.</p>
          )}
        </section>

        <section className="uat-glass-card">
          <h2 className="uat-card-title">Pedram Review System</h2>
          <HumanReviewPanel
            disabled={!showVideo || reviewSaved}
            scores={reviewScores}
            comments={comments}
            publishable={publishable}
            onScoresChange={setReviewScores}
            onCommentsChange={setComments}
            onPublishableChange={setPublishable}
            onSave={() => void handleSaveReview()}
            saving={savingReview}
            saved={reviewSaved}
            error={reviewError}
          />
        </section>
      </div>
    </div>
  );
}

function MissionSetupCard({
  form,
  onChange,
  disabled,
}: {
  form: UatFormState;
  onChange: (next: UatFormState) => void;
  disabled: boolean;
}) {
  const durationBounds = uatDurationBounds(form);

  return (
    <div className="uat-glass-card" style={{ marginBottom: "0.75rem" }}>
      <h2 className="uat-card-title">UAT Mission Setup</h2>
      <div className="uat-field">
        <label htmlFor="uat-topic">Topic</label>
        <textarea
          id="uat-topic"
          placeholder="Cat in the streets of Los Angeles"
          value={form.topic}
          disabled={disabled}
          maxLength={500}
          onChange={(e) => onChange({ ...form, topic: e.target.value })}
        />
      </div>
      <div className="uat-field">
        <label>Platform</label>
        <div className="uat-segmented">
          {(["youtube_shorts", "tiktok", "instagram_reels"] as UatPlatform[]).map((platform) => (
            <button
              key={platform}
              type="button"
              className={`uat-segment ${form.platform === platform ? "active" : ""}`}
              disabled={disabled}
              onClick={() => onChange({ ...form, platform })}
            >
              {formatPlatformLabel(platform)}
            </button>
          ))}
        </div>
      </div>
      <div className="uat-field">
        <label htmlFor="uat-duration">Duration (seconds)</label>
        <input
          id="uat-duration"
          type="number"
          min={durationBounds.min}
          max={durationBounds.max}
          value={form.durationSeconds}
          disabled={disabled}
          onChange={(e) => onChange({ ...form, durationSeconds: Number(e.target.value) })}
        />
        <p className="uat-duration-helper muted">{durationBounds.helper}</p>
      </div>
    </div>
  );
}

function ProviderStackCard({
  form,
  onChange,
  disabled,
}: {
  form: UatFormState;
  onChange: (next: UatFormState) => void;
  disabled: boolean;
}) {
  const videoOptions: { id: UatVideoProvider; label: string }[] = [
    { id: "runway_browser", label: "Runway Browser" },
    { id: "hailuo_browser", label: "Hailuo Browser" },
    { id: "mock", label: "Mock" },
  ];
  const voiceOptions: { id: UatVoiceProvider; label: string }[] = [
    { id: "elevenlabs", label: "ElevenLabs" },
    { id: "mock", label: "Mock" },
  ];
  const assemblyOptions: { id: UatAssemblyMode; label: string }[] = [
    { id: "real_assembly", label: "Real Assembly" },
    { id: "dry_run_only", label: "Dry Run" },
  ];

  return (
    <div className="uat-glass-card" style={{ marginBottom: "0.75rem" }}>
      <h2 className="uat-card-title">Provider Stack</h2>
      <div className="uat-provider-stack">
        <div>
          <div className="uat-provider-group-label">VIDEO</div>
          <div className="uat-provider-cards">
            {videoOptions.map((opt) => {
              const chip = videoProviderChip(opt.id);
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`uat-provider-card ${form.videoProvider === opt.id ? "selected" : ""}`}
                  disabled={disabled}
                  onClick={() =>
                    onChange({
                      ...form,
                      videoProvider: opt.id,
                      durationSeconds: uatDefaultDurationSeconds(opt.id),
                    })
                  }
                >
                  <span className="uat-provider-name">{opt.label}</span>
                  <span className={`uat-chip ${chip}`}>{providerChipLabel(chip)}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div>
          <div className="uat-provider-group-label">VOICE</div>
          <div className="uat-provider-cards">
            {voiceOptions.map((opt) => {
              const chip = voiceProviderChip(opt.id);
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`uat-provider-card ${form.voiceProvider === opt.id ? "selected" : ""}`}
                  disabled={disabled}
                  onClick={() => onChange({ ...form, voiceProvider: opt.id })}
                >
                  <span className="uat-provider-name">{opt.label}</span>
                  <span className={`uat-chip ${chip}`}>{providerChipLabel(chip)}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div>
          <div className="uat-provider-group-label">ASSEMBLY</div>
          <div className="uat-provider-cards">
            {assemblyOptions.map((opt) => {
              const chip = assemblyModeChip(opt.id);
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`uat-provider-card ${form.assemblyMode === opt.id ? "selected" : ""}`}
                  disabled={disabled}
                  onClick={() => onChange({ ...form, assemblyMode: opt.id })}
                >
                  <span className="uat-provider-name">{opt.label}</span>
                  <span className={`uat-chip ${chip}`}>{providerChipLabel(chip)}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function SafetyGateCard({
  form,
  onChange,
  disabled,
}: {
  form: UatFormState;
  onChange: (next: UatFormState) => void;
  disabled: boolean;
}) {
  return (
    <div className="uat-glass-card uat-safety-card">
      <h2 className="uat-card-title">Safety Gate</h2>
      <p className="uat-safety-warning">{UAT_SAFETY_WARNING}</p>
      {showRealVideoApprovalGate(form) && (
        <label className="uat-toggle-row">
          <input
            type="checkbox"
            checked={form.confirmRealVideo}
            disabled={disabled}
            onChange={(e) => onChange({ ...form, confirmRealVideo: e.target.checked })}
          />
          <span className="uat-toggle-label">
            Video Approval — I approve real Runway browser video for this one UAT run.
          </span>
        </label>
      )}
      {showVoiceApprovalGate(form) && (
        <label className="uat-toggle-row">
          <input
            type="checkbox"
            checked={form.confirmRealVoice}
            disabled={disabled}
            onChange={(e) => onChange({ ...form, confirmRealVoice: e.target.checked })}
          />
          <span className="uat-toggle-label">Voice Approval — I approve real voice for this one UAT run.</span>
        </label>
      )}
      {showAssemblyApprovalGate(form) && (
        <label className="uat-toggle-row">
          <input
            type="checkbox"
            checked={form.confirmRealAssembly}
            disabled={disabled}
            onChange={(e) => onChange({ ...form, confirmRealAssembly: e.target.checked })}
          />
          <span className="uat-toggle-label">Assembly Approval — I approve real assembly for this one UAT run.</span>
        </label>
      )}
      <label className="uat-toggle-row">
        <input
          type="checkbox"
          checked={form.oneRunAcknowledged}
          disabled={disabled}
          onChange={(e) => onChange({ ...form, oneRunAcknowledged: e.target.checked })}
        />
        <span className="uat-toggle-label">One Run Only — I understand this is one supervised run, not batch mode.</span>
      </label>
    </div>
  );
}

function formatVideoRuntimeState(state: string | null | undefined): string {
  const normalized = String(state || "").trim().toUpperCase();
  if (!normalized) return "—";
  if (normalized === "RUNNING") return "ACTIVE";
  return normalized;
}

function RunwayBrowserObsPanel({ status }: { status: UatRunResponse | null }) {
  const videoRuntime = status?.video_runtime;
  const obs = status?.runway_browser_obs;
  const step = videoRuntime?.runway_step || obs?.step;
  if (!step && !videoRuntime?.state) {
    return null;
  }

  const controlledUrl =
    videoRuntime?.controlled_tab_url || obs?.controlled_page?.page_url || "—";
  const controlledTitle =
    videoRuntime?.controlled_tab_title || obs?.controlled_page?.page_title || "—";
  const openPages = videoRuntime?.open_pages?.length
    ? videoRuntime.open_pages
    : obs?.open_pages || [];

  return (
    <div className="uat-runway-obs-panel">
      <div className="uat-runway-obs-row">
        <span className="uat-runway-obs-key">Video Runtime</span>
        <span className="uat-runway-obs-value">{formatVideoRuntimeState(videoRuntime?.state)}</span>
      </div>
      {step ? (
        <div className="uat-runway-obs-row">
          <span className="uat-runway-obs-key">Runway step</span>
          <span className="uat-runway-obs-value mono">{step}</span>
        </div>
      ) : null}
      <div className="uat-runway-obs-row">
        <span className="uat-runway-obs-key">Controlled tab</span>
        <span className="uat-runway-obs-value mono">{controlledUrl}</span>
      </div>
      <div className="uat-runway-obs-row">
        <span className="uat-runway-obs-key">Page title</span>
        <span className="uat-runway-obs-value">{controlledTitle}</span>
      </div>
      {openPages.length > 1 ? (
        <details className="uat-runway-obs-pages">
          <summary>Open tabs ({openPages.length})</summary>
          <ul>
            {openPages.map((page) => (
              <li key={`${page.index}-${page.page_url || "tab"}`}>
                <span className="mono">
                  {page.controlled ? "▶ " : ""}
                  {page.page_title || "(no title)"}
                </span>
                <span className="uat-runway-obs-page-url mono">{page.page_url || "—"}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function RuntimeMonitor({ status, running }: { status: UatRunResponse | null; running: boolean }) {
  const currentStage = status?.current_stage;
  const showRunwayObs =
    status?.video_runtime?.runway_step ||
    status?.video_runtime?.state ||
    status?.runway_browser_obs?.step;

  return (
    <>
      <div className="uat-stepper">
        {UAT_STAGE_ORDER.map((stage, index) => {
          const state = stageStatus(stage.key, status, currentStage);
          const isVideoStage = stage.key === "video";
          return (
            <article key={stage.key} className={`uat-step ${state}`}>
              <div className="uat-step-dot">{index + 1}</div>
              <div className="uat-step-body">
                <h4>{stage.label}</h4>
                <p className="uat-step-meta">
                  {state === "active" && running ? "In progress…" : state === "completed" ? "Complete" : state === "failed" ? "Failed" : "Waiting"}
                </p>
                {isVideoStage && showRunwayObs ? <RunwayBrowserObsPanel status={status} /> : null}
              </div>
              <span className={`uat-step-badge ${state}`}>{state}</span>
            </article>
          );
        })}
      </div>
      {status?.progress_log && status.progress_log.length > 0 && (
        <div className="uat-progress-log">
          {status.progress_log.slice(-12).map((entry, idx) => (
            <div key={`${entry.timestamp}-${idx}`} className={`uat-log-line ${entry.level === "error" ? "error" : ""}`}>
              <span className="mono">{entry.timestamp}</span>
              <span>{entry.message}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function SessionIntelligence({
  sessionId,
  status,
  form,
  costEstimate,
  onCopySessionId,
}: {
  sessionId: string | null;
  status: UatRunResponse | null;
  form: UatFormState;
  costEstimate: string;
  onCopySessionId: () => void;
}) {
  const rows = [
    { key: "Session ID", value: sessionId ?? "—" },
    {
      key: "Provider stack",
      value: `${form.videoProvider} / ${form.voiceProvider} / ${form.assemblyMode}`,
    },
    { key: "Estimated cost", value: costEstimate },
    { key: "Duration target", value: `${form.durationSeconds}s` },
    { key: "Artifact folder", value: status?.artifact_folder ?? "—" },
    { key: "Report path", value: status?.report_path ?? "—" },
    { key: "Status", value: status?.status ?? "idle" },
  ];

  return (
    <>
      {rows.map((row) => (
        <div key={row.key} className="uat-intel-row">
          <span className="uat-intel-key">{row.key}</span>
          <span className="uat-intel-value mono">{row.value}</span>
        </div>
      ))}
      {status?.warnings && status.warnings.length > 0 && (
        <div className="uat-intel-row">
          <span className="uat-intel-key">Warnings</span>
          <span className="uat-intel-value">{status.warnings.join("; ")}</span>
        </div>
      )}
      {status?.errors && status.errors.length > 0 && (
        <div className="uat-intel-row">
          <span className="uat-intel-key">Errors</span>
          <span className="uat-intel-value" style={{ color: "#fca5a5" }}>
            {status.errors.join("; ")}
          </span>
        </div>
      )}
      {sessionId && (
        <div className="uat-action-row">
          <button type="button" className="uat-action-btn" onClick={onCopySessionId}>
            Copy Session ID
          </button>
        </div>
      )}
    </>
  );
}

function HumanReviewPanel({
  disabled,
  scores,
  comments,
  publishable,
  onScoresChange,
  onCommentsChange,
  onPublishableChange,
  onSave,
  saving,
  saved,
  error,
}: {
  disabled: boolean;
  scores: ReviewScores;
  comments: string;
  publishable: boolean | null;
  onScoresChange: (next: ReviewScores) => void;
  onCommentsChange: (value: string) => void;
  onPublishableChange: (value: boolean) => void;
  onSave: () => void;
  saving: boolean;
  saved: boolean;
  error: string | null;
}) {
  if (disabled && !saved) {
    return <p className="muted">Complete a UAT run to submit your review scores.</p>;
  }

  return (
    <>
      <div className="uat-score-grid">
        {REVIEW_SCORE_FIELDS.map((field) => (
          <div key={field.key} className="uat-score-field">
            <label>
              <span>{field.label}</span>
              <span>{scores[field.key]}/10</span>
            </label>
            <input
              type="range"
              min={0}
              max={10}
              step={1}
              value={scores[field.key]}
              disabled={disabled || saved}
              onChange={(e) =>
                onScoresChange({ ...scores, [field.key]: Number(e.target.value) })
              }
            />
          </div>
        ))}
      </div>
      <div className="uat-field" style={{ marginTop: "0.75rem" }}>
        <label htmlFor="uat-comments">Comments</label>
        <textarea
          id="uat-comments"
          value={comments}
          disabled={disabled || saved}
          placeholder="What felt good, what felt wrong, what should improve…"
          onChange={(e) => onCommentsChange(e.target.value)}
        />
      </div>
      <div className="uat-field">
        <label>Publishable</label>
        <div className="uat-yesno">
          <button
            type="button"
            className={publishable === true ? "active-yes" : ""}
            disabled={disabled || saved}
            onClick={() => onPublishableChange(true)}
          >
            Yes
          </button>
          <button
            type="button"
            className={publishable === false ? "active-no" : ""}
            disabled={disabled || saved}
            onClick={() => onPublishableChange(false)}
          >
            No
          </button>
        </div>
      </div>
      {error && <p className="uat-block-hints">{error}</p>}
      {saved ? (
        <p className="muted">Review saved to project_brain/user_acceptance_reviews/</p>
      ) : (
        <button
          type="button"
          className="uat-save-review"
          disabled={disabled || saving || publishable === null}
          onClick={onSave}
        >
          {saving ? "Saving…" : "Save Review"}
        </button>
      )}
    </>
  );
}
