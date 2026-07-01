import { useEffect, useState } from "react";

import { fetchLatestResults, type AssetRecord } from "../api/productClient";

type RunHistoryEntry = {
  run_id?: string;
  topic?: string;
  run_dir?: string;
  created_at?: string;
};

export function ResultsPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchLatestResults>> | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadResults(runId = selectedRunId) {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchLatestResults(runId);
      setData(payload);
      if (!runId && payload.selected_run_id) {
        setSelectedRunId(payload.selected_run_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load results");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadResults("");
  }, []);

  const sectionAvailability = data?.section_availability || {};
  const pipelineHidden = sectionAvailability.pipeline === "hidden_stale";
  const continuityHidden = sectionAvailability.visual_continuity === "hidden_stale";
  const brandingHidden = sectionAvailability.branding === "hidden_stale";

  const runwayLabel = data?.runway_completed ? "Runway completed" : "Runway not completed";
  const assemblyLabel =
    data?.assembly_status === "ASSEMBLED"
      ? "Assembly complete"
      : data?.assembly_status === "PLAN_ONLY"
        ? "Assembly plan only (FFmpeg unavailable)"
        : data?.assembly_status
          ? `Assembly ${data.assembly_status.toLowerCase()}`
          : data?.has_downloads_only
            ? "Assembly missing"
            : "Assembly not started";
  const publishLabel =
    data?.publish_status === "PUBLISHED_PACKAGE_CREATED"
      ? "Publish package ready"
      : data?.publish_status === "SKIPPED_ASSEMBLY_PLAN_ONLY"
        ? "Publish skipped (assembly plan only)"
        : data?.publish_status
          ? `Publish ${data.publish_status.toLowerCase()}`
          : data?.has_downloads_only
            ? "Publish missing"
            : "Publish not started";
  const postProcessingLabel =
    data?.post_processing_status === "completed"
      ? "Post-processing complete"
      : data?.post_processing_missing
        ? "Post-processing missing/skipped"
        : data?.post_processing_status
          ? `Post-processing ${data.post_processing_status}`
          : "Post-processing not started";

  const continuityReport = data?.visual_continuity_report || data?.visual_continuity;
  const continuityClips = continuityReport?.clips || [];
  const continuityReady = !continuityHidden && continuityClips.length > 0;
  const overallPass = continuityReport?.overall_pass;
  const visualMemory = data?.visual_memory_report || data?.visual_memory;
  const memoryReady = Boolean(visualMemory?.subject || visualMemory?.visual_memory_status);
  const aiDirector = data?.ai_director_v2_report || data?.ai_director_v2;
  const directorReady = Boolean(aiDirector?.shot_plan?.length || aiDirector?.shot_plan_summary?.length);
  const qualityJudge = data?.video_quality_judge;
  const qualityJudgeP1 = data?.video_quality_judge_p1;
  const qualityJudgeReady = Boolean(
    qualityJudge?.version && typeof qualityJudge?.overall_score === "number",
  );
  const qualityJudgeP1Ready = Boolean(
    qualityJudgeP1?.version && typeof qualityJudgeP1?.overall_score === "number",
  );
  const branding = data?.branding_status;
  const musicLabel = data?.music_status || "Not reported";
  const ambienceLabel = data?.ambience_status || "Not reported";
  const sfxLabel = data?.sfx_status || "Not reported";
  const subtitleLabel = data?.subtitle_status || data?.subtitle_style_status || "Not reported";
  const subtitleStyleLabel = data?.subtitle_style_status || "Not reported";
  const characterVoiceLabel = data?.character_voice_status || "Not reported";
  const approvedVideoPath = data?.latest_approved_video_path || "";
  const candidateVideoPath = data?.latest_candidate_video_path || data?.candidate_video_path || "";
  const videoDisplayLabel = data?.video_display_label || (approvedVideoPath ? "Latest Approved Video" : candidateVideoPath ? "Unapproved Candidate Video" : "");
  const canonicalRunId = data?.canonical_run_id || data?.selected_run_id || "";
  const deliveryTruth = data?.delivery_truth;
  const displayVideoPath = approvedVideoPath || candidateVideoPath || String(deliveryTruth?.final_video_path || "");
  const deliveryChecks = data?.delivery_truth_checks || {};
  const deliveryTruthStatus = data?.delivery_truth_status || String(deliveryTruth?.status || "FAIL");
  const latestAttempt = data?.latest_run_attempt;
  const attemptStatus = data?.latest_attempt_status || String(latestAttempt?.status || "");
  const attemptMessage = data?.latest_attempt_message || String(latestAttempt?.message || "");
  const attemptRunId = data?.latest_attempt_run_id || canonicalRunId;
  const attemptTopic = data?.latest_attempt_topic || data?.topic || "";
  const approvedRunId = data?.approved_run_id || "";
  const truthLabel = (status?: string) =>
    status === "PASS" ? "success-text" : status === "FAIL" ? "error-text" : "muted";
  const storyDirector = data?.story_audio_director;
  const storyVisual = data?.story_visual_quality;
  const cinematicAudio = data?.cinematic_audio;
  const brandingStepClass = (status?: string) =>
    status === "PASS" ? "success-text" : status === "FAIL" ? "error-text" : "muted";

  const runHistory = (data?.run_history || []) as RunHistoryEntry[];
  const latestAssets = (data?.latest_assets || []) as AssetRecord[];
  const assetLibraryPath = data?.asset_library_path || "";

  function formatAssetDate(value?: string) {
    if (!value) return "Unknown date";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
  }

  function formatDuration(seconds?: number | null) {
    if (typeof seconds !== "number" || Number.isNaN(seconds)) return "—";
    const total = Math.max(0, Math.round(seconds));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  }

  async function copyAssetPath(path: string) {
    if (!path) return;
    try {
      await navigator.clipboard.writeText(path);
    } catch {
      // Clipboard unavailable in some contexts.
    }
  }

  return (
    <div className="product-page">
      <header className="header">
        <div>
          <p className="eyebrow">Results</p>
          <h1>Latest Output Package</h1>
          <p className="subtitle">Run-scoped final video, publish package, and metadata from one canonical run folder.</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {loading && !data && <p className="muted">Loading results…</p>}

      {data && (
        <div className="product-form-grid">
          <section className="card full-width">
            <h2>Canonical Run</h2>
            <ul>
              <li>
                Run ID: <span className="mono">{canonicalRunId || "None"}</span>
              </li>
              <li>Topic: {data.topic || attemptTopic || "None"}</li>
              <li>
                Delivery Truth:{" "}
                <strong className={truthLabel(deliveryTruthStatus)}>{deliveryTruthStatus}</strong>
              </li>
              <li>
                Final MP4:{" "}
                <span className="mono">{displayVideoPath || "Not available"}</span>
              </li>
              <li>
                Approved:{" "}
                <strong className={data?.video_approved ? "success-text" : "error-text"}>
                  {data?.video_approved
                    ? `Yes (${approvedRunId || attemptRunId})`
                    : "No — final MP4 audit, visual diversity, or publish package gate did not pass"}
                </strong>
              </li>
            </ul>
          </section>

          <section className="card full-width">
            <h2>Delivery Truth Audit (Final MP4 Only)</h2>
            <p className="muted">Manifests and metadata are ignored. Only the delivered MP4 is analyzed.</p>
            <ul>
              {Object.entries(deliveryChecks).map(([key, row]) => (
                <li key={key}>
                  {row?.label || key}:{" "}
                  <strong className={truthLabel(row?.status)}>{row?.status || "FAIL"}</strong>
                </li>
              ))}
              {!Object.keys(deliveryChecks).length && <li className="muted">No final MP4 available to audit.</li>}
            </ul>
          </section>

          <section className="card full-width">
            <h2>Run Attempt (Same Canonical Run)</h2>
            {!attemptRunId && !attemptStatus ? (
              <p className="muted">No run attempt recorded yet.</p>
            ) : (
              <ul>
                <li>
                  Run ID: <span className="mono">{attemptRunId || "Unknown"}</span>
                </li>
                <li>Topic: {attemptTopic || "Unknown"}</li>
                <li>
                  Status:{" "}
                  <strong className={attemptStatus === "completed" ? "success-text" : attemptStatus === "failed" ? "error-text" : ""}>
                    {attemptStatus || "unknown"}
                  </strong>
                </li>
                <li>
                  Requested clips:{" "}
                  {data?.expected_clip_count ?? data?.clip_count ?? "—"}
                  {data?.selected_duration_seconds ? (
                    <span className="muted"> ({data.selected_duration_seconds}s duration)</span>
                  ) : null}
                </li>
                <li>Clips downloaded: {data?.downloaded_clip_count ?? data?.latest_attempt_clips_completed ?? Number(latestAttempt?.clips_completed ?? 0)}</li>
                <li>
                  Duplicate clips:{" "}
                  <strong className={data?.duplicate_clips_status === "failed" ? "error-text" : "success-text"}>
                    {data?.duplicate_clips_status === "failed" ? "failed" : data?.duplicate_chain_failed ? "failed" : "pass"}
                  </strong>
                </li>
                {data?.clip_3_not_applicable ? (
                  <li>Clip 3: <span className="muted">not applicable (30s / 2-clip run)</span></li>
                ) : null}
                {Array.isArray(data?.clip_statuses) && data.clip_statuses.length > 0 ? (
                  <li>
                    Clip files:{" "}
                    <ul>
                      {data.clip_statuses.map((clip: { clip_index?: number; status?: string }) => (
                        <li key={clip.clip_index}>
                          clip_{clip.clip_index}:{" "}
                          <strong className={clip.status === "duplicate_failed" ? "error-text" : ""}>
                            {clip.status === "duplicate_failed" ? "duplicate_failed" : clip.status || "exists"}
                          </strong>
                        </li>
                      ))}
                    </ul>
                  </li>
                ) : null}
                {attemptMessage && <li>Message: {attemptMessage}</li>}
              </ul>
            )}
          </section>

          <section className="card full-width">
            <h2>Selected Run</h2>
            <ul>
              <li>
                Run ID: <span className="mono">{data.selected_run_id || "None"}</span>
              </li>
              <li>
                Run Folder: <span className="mono">{data.run_folder || "None"}</span>
              </li>
              <li>Topic: {data.topic || "None"}</li>
              <li>Canonical latest: {data.is_canonical_latest ? "Yes" : "No"}</li>
            </ul>
            <label className="field-row full-width">
              Run History
              <select
                className="filter-input full-width"
                value={selectedRunId}
                onChange={(e) => {
                  const nextRunId = e.target.value;
                  setSelectedRunId(nextRunId);
                  void loadResults(nextRunId);
                }}
              >
                {runHistory.map((run) => (
                  <option key={String(run.run_dir || run.run_id)} value={String(run.run_id || "")}>
                    {(run.topic || run.run_id || "Run") + (run.created_at ? ` — ${run.created_at}` : "")}
                  </option>
                ))}
              </select>
            </label>
            {data.stale_sections && data.stale_sections.length > 0 && (
              <p className="muted">Stale sections hidden: {data.stale_sections.join(", ")}</p>
            )}
          </section>

          {(data.pwmap_agent || data.multiclip_execution_plan || data.execution_mode) && (
            <section className="card full-width">
              <h2>Product Multi-Clip Output</h2>
              <ul>
                <li>
                  Status:{" "}
                  <strong className={data.status === "partial_failed" ? "warning-text" : data.status === "completed" ? "success-text" : "error-text"}>
                    {data.status || data.generation_status || "—"}
                  </strong>
                </li>
                {(data.status === "partial_failed" || data.generation_status === "partial_failed") && (
                  <>
                    <li>
                      Clips completed:{" "}
                      <strong>
                        {data.clips_completed ?? data.clip_count ?? 0} / {data.expected_clip_count ?? data.multiclip_execution_plan?.clip_count ?? "?"}
                      </strong>
                    </li>
                    <li>
                      Recovery available:{" "}
                      <strong className={data.recovery_available ? "success-text" : "muted"}>
                        {data.recovery_available ? "yes" : "no"}
                      </strong>
                    </li>
                    {data.failure_stage && (
                      <li>
                        Failure stage: <strong>{data.failure_stage}</strong>
                      </li>
                    )}
                    {data.failed_clip_index != null && (
                      <li>
                        Failed clip index: <strong>{data.failed_clip_index}</strong>
                      </li>
                    )}
                    {data.error && (
                      <li className="error-text">{String(data.error)}</li>
                    )}
                  </>
                )}
                <li>
                  Final MP4:{" "}
                  <strong className={data.video_path ? "success-text" : "error-text"}>
                    {data.video_path ? "ready" : "missing"}
                  </strong>
                </li>
                {data.video_path && (
                  <li>
                    Path: <span className="mono">{data.video_path}</span>
                  </li>
                )}
                <li>
                  Duration:{" "}
                  <strong>
                    {data.final_video_duration_seconds != null
                      ? `${data.final_video_duration_seconds}s`
                      : data.planned_duration_seconds != null
                        ? `${data.planned_duration_seconds}s planned`
                        : "—"}
                  </strong>
                </li>
                <li>
                  Clip Count: <strong>{data.clip_count ?? data.pwmap_agent?.clip_count ?? data.downloaded_clip_count ?? "—"}</strong>
                </li>
                <li>
                  Provider: <strong>{data.pwmap_agent?.provider_runtime || data.provider_runtime || "pwmap_agent"}</strong>
                </li>
                <li>
                  Generation Time:{" "}
                  <strong>
                    {data.generation_time_seconds != null
                      ? `${data.generation_time_seconds}s`
                      : data.pwmap_agent?.generation_time_seconds != null
                        ? `${data.pwmap_agent.generation_time_seconds}s`
                        : "—"}
                  </strong>
                </li>
                <li>
                  Execution Mode:{" "}
                  <strong>{data.execution_mode || data.pwmap_agent?.execution_mode || data.multiclip_execution_plan?.execution_mode || "—"}</strong>
                </li>
                {data.generation_runtime_status?.generation_state && (
                  <li>
                    Generation State: <strong>{data.generation_runtime_status.generation_state}</strong>
                  </li>
                )}
                <li>
                  Assembly:{" "}
                  <strong className={data.assembly_complete ? "success-text" : data.assembly_status === "assembly_failed" ? "error-text" : "muted"}>
                    {data.assembly_complete
                      ? "complete"
                      : data.assembly_status === "assembly_failed"
                        ? "failed"
                        : data.assembly_status || "not started"}
                  </strong>
                </li>
                <li>
                  Publish package:{" "}
                  <strong className={data.publish_package_ready ? "success-text" : "muted"}>
                    {data.publish_package_ready ? "ready" : "not ready"}
                  </strong>
                </li>
                {data.source_clip_count != null && (
                  <li>
                    Source clips assembled: <strong>{data.source_clip_count}</strong>
                  </li>
                )}
                {data.final_publish_video_path && (
                  <li>
                    Final publish video: <span className="mono">{data.final_publish_video_path}</span>
                  </li>
                )}
                {data.publish_package_path && (
                  <li>
                    Publish folder: <span className="mono">{data.publish_package_path}</span>
                  </li>
                )}
                {data.assembly_status === "assembly_failed" && (
                  <>
                    {data.missing_clip_index != null && (
                      <li>
                        Missing clip index: <strong>{data.missing_clip_index}</strong>
                      </li>
                    )}
                    <li>
                      Recovery possible:{" "}
                      <strong className={data.assembly_recovery_possible ? "success-text" : "muted"}>
                        {data.assembly_recovery_possible ? "yes" : "no"}
                      </strong>
                    </li>
                  </>
                )}
                {(data.publish_ready || data.final_branded_publish_video_path || data.branding_publish_status) && (
                  <>
                    <li>
                      Publish ready:{" "}
                      <strong className={data.publish_ready ? "success-text" : "muted"}>
                        {data.publish_ready ? "yes" : "no"}
                      </strong>
                    </li>
                    {data.final_branded_publish_video_path && (
                      <li>
                        Branded publish video: <span className="mono">{data.final_branded_publish_video_path}</span>
                      </li>
                    )}
                    <li>
                      Subtitle status: <strong>{data.subtitle_status || "—"}</strong>
                      {data.subtitle_count != null ? ` (${data.subtitle_count} cues)` : ""}
                    </li>
                    <li>
                      Branding status: <strong>{data.branding_publish_status || branding?.status || "—"}</strong>
                    </li>
                    <li>
                      Logo: <strong>{data.logo_status || (data.logo_enabled ? "enabled" : "disabled")}</strong>
                    </li>
                    <li>
                      CTA: <strong>{data.cta_status || (data.cta_enabled ? "enabled" : "disabled")}</strong>
                    </li>
                    <li>
                      Intro / Outro:{" "}
                      <strong>
                        {data.intro_status || "—"} / {data.outro_status || "—"}
                      </strong>
                    </li>
                    <li>
                      Audio normalization:{" "}
                      <strong>
                        {data.audio_status || "—"}
                        {data.normalization_applied && data.lufs_value != null ? ` (${data.lufs_value} LUFS)` : ""}
                      </strong>
                    </li>
                  </>
                )}
              </ul>
            </section>
          )}

          {data.kling_native_audio && (
            <section className="card full-width kling-results-panel">
              <h2>Kling Native Audio</h2>
              <ul>
                <li>Provider Used: <strong>{data.kling_native_audio.provider_used || "—"}</strong></li>
                <li>Audio Strategy Used: <strong>{data.kling_native_audio.audio_strategy_used || "—"}</strong></li>
                <li>Native Audio Status: <strong>{data.kling_native_audio.native_audio_status || "—"}</strong></li>
                <li>Generation Status: <strong>{data.kling_native_audio.generation_status || data.generation_status || "—"}</strong></li>
                <li>
                  Output Ready:{" "}
                  <strong className={(data.kling_native_audio.output_ready ?? data.output_ready) ? "success-text" : "error-text"}>
                    {(data.kling_native_audio.output_ready ?? data.output_ready) ? "yes" : "no"}
                  </strong>
                </li>
                <li>
                  Recovery Available:{" "}
                  <strong className={(data.kling_native_audio.recovery_available ?? data.recovery_available) ? "success-text" : "muted"}>
                    {(data.kling_native_audio.recovery_available ?? data.recovery_available) ? "yes" : "no"}
                  </strong>
                </li>
                {(data.kling_native_audio.generation_status === "download_failed" ||
                  data.kling_native_audio.native_audio_status === "download_failed") && (
                  <li className="error-text">
                    Download failed after generation completed. Run recovery without spending new credits.
                  </li>
                )}
                {!(data.kling_native_audio.output_ready ?? data.output_ready) && (
                  <li className="muted">Output not ready until MP4 exists in the parent run folder.</li>
                )}
                <li>Clip Count: <strong>{data.kling_native_audio.clip_count ?? "—"}</strong></li>
                <li>Shot Mode: <strong>{data.kling_native_audio.shot_mode || "—"}</strong></li>
                <li>Continuity Method: <strong>{data.kling_native_audio.continuity_method || "use_frame"}</strong></li>
                <li>Use Frame Status: <strong>{data.kling_native_audio.use_frame_status || data.kling_native_audio.story_progression_status || "—"}</strong></li>
                <li>
                  Fallback Used:{" "}
                  <strong className={data.kling_native_audio.fallback_used ? "error-text" : "success-text"}>
                    {data.kling_native_audio.fallback_used ? "yes" : "no"}
                  </strong>
                </li>
                <li>Story Progression: <strong>{data.kling_native_audio.story_progression_status || "—"}</strong></li>
                {data.kling_native_audio.story_progression?.chapters?.length ? (
                  <li>
                    <div>Story Chapters:</div>
                    <ul>
                      {data.kling_native_audio.story_progression.chapters.map((chapter) => (
                        <li key={chapter.clip_index}>
                          Clip {chapter.clip_index}: <strong>{chapter.chapter_label || chapter.chapter_role}</strong>
                        </li>
                      ))}
                    </ul>
                    <div>
                      Status:{" "}
                      <strong
                        className={
                          data.kling_native_audio.story_progression.validation_status === "PASS"
                            ? "success-text"
                            : "error-text"
                        }
                      >
                        {data.kling_native_audio.story_progression.validation_status || "—"}
                      </strong>
                    </div>
                  </li>
                ) : null}
                <li>Continuity Status: <strong>{data.kling_native_audio.continuity_status || "—"}</strong></li>
                <li>
                  Frames Extracted:{" "}
                  <strong>{data.kling_native_audio.frames_extracted_count ?? "—"}</strong>
                </li>
                <li>
                  Frames Uploaded:{" "}
                  <strong>{data.kling_native_audio.frames_uploaded_count ?? "—"}</strong>
                </li>
                <li>
                  Chain Complete:{" "}
                  <strong className={data.kling_native_audio.chain_complete ? "success-text" : "muted"}>
                    {data.kling_native_audio.chain_complete ? "yes" : "no"}
                  </strong>
                </li>
                <li>
                  Output Folder: <span className="mono">{data.kling_native_audio.output_folder || "—"}</span>
                </li>
                <li>
                  Download Path: <span className="mono">{data.kling_native_audio.download_path || data.video_path || "—"}</span>
                </li>
                {(data.legacy_run_folders?.length || data.kling_native_audio.legacy_run_folders?.length) ? (
                  <li>
                    Legacy Partial Folders:{" "}
                    <span className="mono">
                      {(data.legacy_run_folders || data.kling_native_audio.legacy_run_folders || []).join(", ")}
                    </span>
                  </li>
                ) : null}
                <li>
                  Generation Time:{" "}
                  <strong>
                    {typeof data.kling_native_audio.generation_time_seconds === "number"
                      ? `${data.kling_native_audio.generation_time_seconds}s`
                      : "—"}
                  </strong>
                </li>
              </ul>
              {data.kling_native_audio.approval_information && (
                <div>
                  <h3>Approval Information</h3>
                  <pre className="prompt-preview">{JSON.stringify(data.kling_native_audio.approval_information, null, 2)}</pre>
                </div>
              )}
            </section>
          )}

          <section className="card">
            <h2>Video Quality Judge</h2>
            {!qualityJudgeReady ? (
              <p className="muted">Quality Judge not run yet</p>
            ) : (
              <>
                <div className="cb-test-score-grid">
                  <div>
                    Overall: <strong>{Math.round(qualityJudge?.overall_score || 0)}</strong>
                  </div>
                  <div>
                    Story: <strong>{Math.round(qualityJudge?.story_score || 0)}</strong>
                  </div>
                  <div>
                    Audio: <strong>{Math.round(qualityJudge?.audio_score || 0)}</strong>
                  </div>
                  <div>
                    Visual: <strong>{Math.round(qualityJudge?.visual_score || 0)}</strong>
                  </div>
                  <div>
                    Continuity: <strong>{Math.round(qualityJudge?.continuity_score || 0)}</strong>
                  </div>
                  <div>
                    Viral: <strong>{Math.round(qualityJudge?.viral_score || 0)}</strong>
                  </div>
                </div>
                <p>
                  Learning proposed:{" "}
                  <strong className={data?.video_quality_learning_proposed ? "success-text" : "muted"}>
                    {data?.video_quality_learning_proposed ? "yes" : "no"}
                  </strong>
                </p>
                {qualityJudge?.strengths && qualityJudge.strengths.length > 0 && (
                  <div>
                    <h3>Strengths</h3>
                    <ul>
                      {qualityJudge.strengths.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {qualityJudge?.weaknesses && qualityJudge.weaknesses.length > 0 && (
                  <div>
                    <h3>Weaknesses</h3>
                    <ul>
                      {qualityJudge.weaknesses.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {qualityJudge?.improvement_actions && qualityJudge.improvement_actions.length > 0 && (
                  <div>
                    <h3>Improvement Actions</h3>
                    <ul>
                      {qualityJudge.improvement_actions.map((action, index) => (
                        <li key={`${action.action_id || "action"}-${index}`}>
                          <strong>{String(action.action_id || "action")}</strong>
                          {action.reason ? <span className="muted"> — {String(action.reason)}</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </section>

          <section className="card">
            <h2>Video Judge P1</h2>
            {!qualityJudgeP1Ready ? (
              <p className="muted">Semantic judge not run yet</p>
            ) : (
              <>
                <p className="muted">Semantic story review — evaluates narrative quality, not only metadata probes.</p>
                <div className="cb-test-score-grid">
                  <div>
                    Overall Rating: <strong>{Math.round(qualityJudgeP1?.overall_score || 0)}</strong>
                  </div>
                  <div>
                    Story Score: <strong>{Math.round(qualityJudgeP1?.story_score || 0)}</strong>
                  </div>
                  <div>
                    Dialogue Score: <strong>{Math.round(qualityJudgeP1?.dialogue_score || 0)}</strong>
                  </div>
                  <div>
                    Continuity Score: <strong>{Math.round(qualityJudgeP1?.continuity_score || 0)}</strong>
                  </div>
                  <div>
                    Viral Score: <strong>{Math.round(qualityJudgeP1?.viral_score || 0)}</strong>
                  </div>
                  <div>
                    Character: <strong>{Math.round(qualityJudgeP1?.character_score || 0)}</strong>
                  </div>
                  <div>
                    Visual: <strong>{Math.round(qualityJudgeP1?.visual_score || 0)}</strong>
                  </div>
                  <div>
                    Audio Immersion: <strong>{Math.round(qualityJudgeP1?.audio_score || 0)}</strong>
                  </div>
                </div>
                <p>
                  Learning proposed (P1):{" "}
                  <strong className={data?.video_quality_learning_p1_proposed ? "success-text" : "muted"}>
                    {data?.video_quality_learning_p1_proposed ? "yes" : "no"}
                  </strong>
                </p>
                {qualityJudgeP1?.strengths && qualityJudgeP1.strengths.length > 0 && (
                  <div>
                    <h3>Strengths</h3>
                    <ul>
                      {qualityJudgeP1.strengths.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {qualityJudgeP1?.weaknesses && qualityJudgeP1.weaknesses.length > 0 && (
                  <div>
                    <h3>Weaknesses</h3>
                    <ul>
                      {qualityJudgeP1.weaknesses.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {qualityJudgeP1?.improvement_actions && qualityJudgeP1.improvement_actions.length > 0 && (
                  <div>
                    <h3>Improvement Actions</h3>
                    <ul>
                      {qualityJudgeP1.improvement_actions.map((action, index) => (
                        <li key={`${action.action_id || "action"}-${index}`}>
                          <strong>{String(action.action_id || "action")}</strong>
                          {action.reason ? <span className="muted"> — {String(action.reason)}</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </section>

          {!pipelineHidden && (
            <section className="card">
              <h2>Pipeline Status</h2>
              <ul>
                <li>
                  {runwayLabel}
                  {data.downloaded_clip_count ? ` (${data.downloaded_clip_count} clip(s) downloaded)` : ""}
                </li>
                <li>{postProcessingLabel}</li>
                <li>{assemblyLabel}</li>
                <li>{publishLabel}</li>
              </ul>
              {data.last_completed_stage && (
                <p>
                  Last completed stage: <strong>{data.last_completed_stage}</strong>
                  {data.stop_stage ? (
                    <>
                      {" "}
                      — stopped at <strong className="error-text">{data.stop_stage}</strong>
                    </>
                  ) : null}
                </p>
              )}
              {data.post_processing_warnings && data.post_processing_warnings.length > 0 && (
                <p className="muted">Warnings: {data.post_processing_warnings.join("; ")}</p>
              )}
            </section>
          )}

          <section className="card">
            <h2>Publish Chain Trace</h2>
            {data.api_process_stale ? (
              <p className="error-text">
                API process may be stale — restart <code>python -m ui.api.main</code> to load the latest orchestrator.
              </p>
            ) : null}
            <ul>
              <li>
                API build: <strong>{data.api_build_id || "—"}</strong>
                {data.api_runtime_diagnostics?.startup_time ? (
                  <span className="muted"> (started {data.api_runtime_diagnostics.startup_time})</span>
                ) : null}
              </li>
              <li>
                Orchestrator: <strong>{data.orchestrator_version || "—"}</strong>
              </li>
              <li>
                Assembly bridge:{" "}
                <strong className={data.assembly_bridge_enabled ? "success-text" : "error-text"}>
                  {data.assembly_bridge_enabled ? "enabled" : "disabled"}
                </strong>
              </li>
              <li>
                Branding publish:{" "}
                <strong className={data.branding_publish_enabled ? "success-text" : "error-text"}>
                  {data.branding_publish_enabled ? "enabled" : "disabled"}
                </strong>
              </li>
              <li>
                YouTube metadata:{" "}
                <strong className={data.youtube_metadata_enabled ? "success-text" : "error-text"}>
                  {data.youtube_metadata_enabled ? "enabled" : "disabled"}
                </strong>
              </li>
            </ul>
            {data.pipeline_trace?.stages ? (
              <ul>
                {Object.entries(data.pipeline_trace.stages as Record<string, { status?: string; error?: string }>).map(
                  ([stage, info]) => (
                    <li key={stage}>
                      {stage}:{" "}
                      <strong
                        className={
                          info.status === "completed"
                            ? "success-text"
                            : info.status === "skipped"
                              ? "muted"
                              : "error-text"
                        }
                      >
                        {info.status || "unknown"}
                      </strong>
                      {info.error ? <span className="muted"> — {info.error}</span> : null}
                    </li>
                  ),
                )}
              </ul>
            ) : (
              <p className="muted">No pipeline trace recorded for this run yet.</p>
            )}
          </section>

          {!continuityHidden && (
            <section className="card">
              <h2>Visual Continuity</h2>
              {!continuityReady ? (
                <p className="muted">{continuityReport?.message || "No visual continuity report for this run."}</p>
              ) : (
                <>
                  <p>
                    Overall:{" "}
                    <strong className={overallPass ? "success-text" : "error-text"}>
                      {overallPass ? "PASS" : "FAIL"}
                    </strong>
                    {typeof continuityReport?.overall_score === "number" && (
                      <span className="muted"> — score {Math.round(continuityReport.overall_score)}</span>
                    )}
                  </p>
                  <ul>
                    {continuityClips.map((clip) => (
                      <li key={clip.clip_index}>
                        Clip {clip.clip_index}:{" "}
                        <strong className={clip.pass ? "success-text" : "error-text"}>
                          {clip.pass ? "PASS" : "FAIL"}
                        </strong>{" "}
                        {Math.round(clip.score)}
                        {!clip.pass && clip.detected_subject && clip.expected_subject && (
                          <span className="muted">
                            {" "}
                            — Detected: {clip.detected_subject}; Expected: {clip.expected_subject}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}

          {continuityHidden && (
            <section className="card">
              <h2>Visual Continuity</h2>
              <p className="muted">Hidden — stale data from another run was detected and excluded.</p>
            </section>
          )}

          <section className="card">
            <h2>Visual Memory</h2>
            {!memoryReady ? (
              <p className="muted">No visual memory profile for this run yet. Generate prompts to create subject memory.</p>
            ) : (
              <ul>
                <li>
                  Subject: <strong>{visualMemory?.subject || "Unknown"}</strong>
                  {visualMemory?.subject_type ? <span className="muted"> ({visualMemory.subject_type})</span> : null}
                </li>
                <li>
                  Visual Memory:{" "}
                  <strong
                    className={
                      visualMemory?.visual_memory_status === "PASS" ? "success-text" : "error-text"
                    }
                  >
                    {visualMemory?.visual_memory_status || "UNKNOWN"}
                  </strong>
                </li>
                <li>
                  Consistency:{" "}
                  <strong className={visualMemory?.consistency_pass ? "success-text" : "error-text"}>
                    {typeof visualMemory?.consistency_score === "number"
                      ? `${visualMemory.consistency_score}/100`
                      : "N/A"}
                  </strong>
                </li>
                <li>
                  Continuity Status:{" "}
                  <strong
                    className={visualMemory?.continuity_status === "PASS" ? "success-text" : "error-text"}
                  >
                    {visualMemory?.continuity_status || "UNKNOWN"}
                  </strong>
                </li>
                {visualMemory?.vision_verifier_ready && (
                  <li className="muted">Director-4 Vision Verifier architecture ready (frame analysis pending)</li>
                )}
              </ul>
            )}
          </section>

          <section className="card">
            <h2>AI Director V2</h2>
            {!directorReady ? (
              <p className="muted">No shot plan for this run yet. Generate prompts to create a director plan.</p>
            ) : (
              <>
                <p className="muted">{aiDirector?.director_version || "AI Director V2"}</p>
                <ul>
                  <li>
                    Rhythm Score:{" "}
                    <strong className={aiDirector?.rhythm_pass ? "success-text" : "error-text"}>
                      {typeof aiDirector?.rhythm_score === "number"
                        ? `${aiDirector.rhythm_score}/100`
                        : "N/A"}
                    </strong>
                  </li>
                  <li>
                    Shot Graph:{" "}
                    <strong className={aiDirector?.shot_graph_status === "PASS" ? "success-text" : "error-text"}>
                      {aiDirector?.shot_graph_status || "UNKNOWN"}
                    </strong>
                  </li>
                </ul>
                <h3>Shot Plan</h3>
                <ul>
                  {(aiDirector?.shot_plan_summary || []).map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                  {!aiDirector?.shot_plan_summary?.length &&
                    (aiDirector?.shot_plan || []).map((shot) => (
                      <li key={shot.clip_index}>
                        Clip {shot.clip_index}: {shot.shot_type}
                        {shot.scene_progression ? ` — ${shot.scene_progression}` : ""}
                      </li>
                    ))}
                </ul>
                {(aiDirector?.camera_language || []).length > 0 && (
                  <>
                    <h3>Camera Language</h3>
                    <ul>
                      {aiDirector?.camera_language?.map((cam) => (
                        <li key={cam.clip_index}>
                          Clip {cam.clip_index}: {cam.lens || "lens"} — {cam.camera_movement || "movement"}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </section>

          {!brandingHidden && (
            <section className="card">
              <h2>Branding Status</h2>
              {!branding ? (
                <p className="muted">No branding report for this run.</p>
              ) : (
                <>
                  <p className="muted">Runtime status: {branding.status || "not run"}</p>
                  <ul>
                    <li>
                      Subtitles: <strong className={brandingStepClass(branding.subtitles)}>{branding.subtitles || "SKIP"}</strong>
                    </li>
                    <li>
                      Logo: <strong className={brandingStepClass(branding.logo)}>{branding.logo || "SKIP"}</strong>
                    </li>
                    <li>
                      CTA: <strong className={brandingStepClass(branding.cta)}>{branding.cta || "SKIP"}</strong>
                    </li>
                    <li>
                      Intro: <strong className={brandingStepClass(branding.intro)}>{branding.intro || "SKIP"}</strong>
                    </li>
                    <li>
                      Outro: <strong className={brandingStepClass(branding.outro)}>{branding.outro || "SKIP"}</strong>
                    </li>
                  </ul>
                  <p>
                    {videoDisplayLabel || "Latest Video"}:{" "}
                    <span className="mono">{displayVideoPath || "Not registered yet"}</span>
                  </p>
                </>
              )}
            </section>
          )}

          <section className="card">
            <h2>Story &amp; Audio Director</h2>
            {storyDirector ? (
              <ul>
                <li>
                  Status: <strong>{storyDirector.status || "NOT_RUN"}</strong>
                </li>
                <li>
                  Story Score: <strong>{storyDirector.story_score ?? 0}</strong>
                </li>
                <li>
                  Dialogue Score: <strong>{storyDirector.dialogue_score ?? 0}</strong>
                </li>
                <li>
                  Emotion Score: <strong>{storyDirector.emotion_score ?? 0}</strong>
                </li>
                <li>
                  Character Count: <strong>{storyDirector.character_count ?? 0}</strong>
                </li>
                <li>
                  Voice Count: <strong>{storyDirector.voice_count ?? 0}</strong>
                </li>
                <li>
                  Environment: <strong>{storyDirector.environment_plan?.environment || "—"}</strong>
                </li>
                <li>
                  Music Mood: <strong>{storyDirector.music_plan?.mood || "—"}</strong>
                </li>
                {storyDirector.story_package_path ? (
                  <li>
                    Story package: <span className="mono">{storyDirector.story_package_path}</span>
                  </li>
                ) : null}
              </ul>
            ) : (
              <p className="muted">Story package not generated for this run yet.</p>
            )}
          </section>

          <section className="card">
            <h2>Story Visual Quality</h2>
            {storyVisual && (storyVisual.scene_diversity_score || storyVisual.repetition_score) ? (
              <>
                <ul>
                  <li>
                    Scene Diversity:{" "}
                    <strong className={(storyVisual.scene_diversity_score ?? 0) >= 70 ? "success-text" : "error-text"}>
                      {storyVisual.scene_diversity_score ?? 0}/100
                    </strong>
                  </li>
                  <li>
                    Emotion Coverage:{" "}
                    <strong className={(storyVisual.emotion_coverage_score ?? 0) >= 70 ? "success-text" : "error-text"}>
                      {storyVisual.emotion_coverage_score ?? 0}/100
                    </strong>
                  </li>
                  <li>
                    Story Progression:{" "}
                    <strong className={(storyVisual.story_progression_score ?? 0) >= 70 ? "success-text" : "error-text"}>
                      {storyVisual.story_progression_score ?? 0}/100
                    </strong>
                  </li>
                  <li>
                    Repetition Score:{" "}
                    <strong className={(storyVisual.repetition_score ?? 0) >= 70 ? "success-text" : "error-text"}>
                      {storyVisual.repetition_score ?? 0}/100
                    </strong>
                    {storyVisual.pass_visual_diversity === false ? (
                      <span className="muted"> — repeated visuals detected</span>
                    ) : null}
                  </li>
                </ul>
                {(storyVisual.clip_objectives || []).length > 0 && (
                  <>
                    <h3>Clip Visual Objectives</h3>
                    <ul>
                      {storyVisual.clip_objectives?.map((clip) => (
                        <li key={clip.clip_index}>
                          Clip {clip.clip_index}: {clip.location} — {clip.visual_objective}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            ) : (
              <p className="muted">Story visual quality plan not generated for this run yet.</p>
            )}
          </section>

          <section className="card">
            <h2>Cinematic Audio</h2>
            {cinematicAudio ? (
              <ul>
                <li>
                  Status: <strong>{cinematicAudio.status || "NOT_RUN"}</strong>
                </li>
                <li>
                  Character Count: <strong>{cinematicAudio.character_count ?? 0}</strong>
                </li>
                <li>
                  Voice Count: <strong>{cinematicAudio.voice_count ?? 0}</strong>
                </li>
                <li>
                  Dialogue Lines: <strong>{cinematicAudio.dialogue_line_count ?? 0}</strong>
                </li>
                <li>
                  Emotion States: <strong>{(cinematicAudio.emotion_states || []).join(" → ") || "—"}</strong>
                </li>
                <li>
                  Environment Layers: <strong>{cinematicAudio.environment_layers ?? 0}</strong>
                </li>
                <li>
                  Music Layers: <strong>{cinematicAudio.music_layers ?? 0}</strong>
                </li>
                <li>
                  Audio Quality Score: <strong>{cinematicAudio.audio_quality_score ?? 0}</strong>
                </li>
                {cinematicAudio.cinematic_video_path ? (
                  <li>
                    Cinematic video: <span className="mono">{cinematicAudio.cinematic_video_path}</span>
                  </li>
                ) : null}
              </ul>
            ) : (
              <p className="muted">Cinematic multi-voice audio not generated for this run yet.</p>
            )}
          </section>

          <section className="card">
            <h2>Audio &amp; Music</h2>
            <ul>
              <li>
                Music: <strong>{musicLabel}</strong>
              </li>
              <li>
                Ambience: <strong>{ambienceLabel}</strong>
              </li>
              <li>
                SFX: <strong>{sfxLabel}</strong>
              </li>
              <li>
                Character voices: <strong>{characterVoiceLabel}</strong>
              </li>
              <li>
                Subtitles: <strong>{subtitleLabel}</strong>
              </li>
              {subtitleStyleLabel !== subtitleLabel ? (
                <li>
                  Subtitle style: <strong>{subtitleStyleLabel}</strong>
                </li>
              ) : null}
            </ul>
          </section>

          <section className="card">
            <h2>{videoDisplayLabel || "Latest Video"}</h2>
            <p>{displayVideoPath || (data.found ? "No candidate video on disk for this run" : "No generated video found for this run")}</p>
            {displayVideoPath ? <p className="mono">{displayVideoPath}</p> : null}
            {candidateVideoPath && !approvedVideoPath ? (
              <p className="muted">Not approved — delivery audit, visual diversity, or publish package gate did not pass.</p>
            ) : null}
          </section>

          <section className="card">
            <h2>Publish Package</h2>
            <p>{data.publish_package_path || "No publish package for this run"}</p>
          </section>

          <section className="card full-width">
            <h2>YouTube OAuth</h2>
            <ul>
              <li>
                OAuth status:{" "}
                <strong
                  className={
                    data.youtube_oauth_status === "authorized"
                      ? "success-text"
                      : data.youtube_oauth_status === "credentials_ready"
                        ? "muted"
                        : "error-text"
                  }
                >
                  {data.youtube_oauth_status === "authorized"
                    ? "Authorized"
                    : data.youtube_oauth_status === "credentials_ready"
                      ? "Credentials ready — login required"
                      : data.youtube_oauth_status === "not_configured"
                        ? "Not configured"
                        : data.youtube_oauth_status || "Unknown"}
                </strong>
              </li>
              <li>
                Connected channel:{" "}
                <strong>
                  {data.youtube_connected_channel ||
                    data.youtube_channel_name ||
                    data.youtube_channel_id ||
                    "Not connected"}
                </strong>
              </li>
              {data.youtube_channel_id && (
                <li>
                  Channel ID: <strong>{data.youtube_channel_id}</strong>
                </li>
              )}
              <li>
                Credentials configured:{" "}
                <strong>{data.youtube_credentials_configured ? "Yes" : "No"}</strong>
              </li>
              <li>
                Token refresh verified:{" "}
                <strong>{data.youtube_token_refresh_verified ? "Yes" : "No"}</strong>
              </li>
              <li>
                Upload ready:{" "}
                <strong className={data.youtube_upload_ready ? "success-text" : "muted"}>
                  {data.youtube_upload_ready ? "Yes" : "No"}
                </strong>
              </li>
            </ul>
          </section>

          <section className="card full-width">
            <h2>Visual Diversity</h2>
            <ul>
              <li>
                Diversity score:{" "}
                <strong className={(data.visual_diversity_score ?? 0) >= 70 ? "success-text" : "error-text"}>
                  {data.visual_diversity_score ?? "—"}
                </strong>
              </li>
              <li>
                Repetition risk:{" "}
                <strong
                  className={
                    data.repetition_risk === "high"
                      ? "error-text"
                      : data.repetition_risk === "medium"
                        ? "muted"
                        : "success-text"
                  }
                >
                  {data.repetition_risk || "—"}
                </strong>
              </li>
              <li>
                Status: <strong>{data.visual_diversity_status || "—"}</strong>
              </li>
              <li>
                Repeated clip warning:{" "}
                <strong className={data.repeated_clip_warning ? "error-text" : "success-text"}>
                  {data.repeated_clip_warning ? "Yes" : "No"}
                </strong>
              </li>
              <li>
                YouTube upload allowed:{" "}
                <strong className={data.youtube_upload_allowed === false ? "error-text" : "success-text"}>
                  {data.youtube_upload_allowed === false ? "Blocked" : "Yes"}
                </strong>
              </li>
              {(data.similar_clip_pairs || []).length > 0 && (
                <li>
                  Similar clip pairs:{" "}
                  <span className="mono">
                    {(data.similar_clip_pairs || [])
                      .map((pair) => `${pair.clip_a}-${pair.clip_b} (${Math.round((pair.similarity || 0) * 100)}%)`)
                      .join(", ")}
                  </span>
                </li>
              )}
            </ul>
          </section>

          {(data.youtube_metadata || data.youtube_title) && (
            <section className="card full-width">
              <h2>YouTube Metadata</h2>
              <ul>
                <li>
                  Title: <strong>{data.youtube_title || data.youtube_metadata?.title || "—"}</strong>
                </li>
                <li>
                  Category: <strong>{data.youtube_category || data.youtube_metadata?.category || "—"}</strong>
                </li>
                <li>
                  Tags: <strong>{data.youtube_tags_count ?? data.youtube_metadata?.tags?.length ?? 0}</strong>
                </li>
                <li>
                  Hashtags:{" "}
                  <strong>
                    {(data.youtube_hashtags || data.youtube_metadata?.hashtags || []).join(" ") || "—"}
                  </strong>
                </li>
                {(data.youtube_thumbnail_prompt || data.youtube_metadata?.thumbnail_prompt) && (
                  <li>
                    Thumbnail prompt:{" "}
                    <span className="mono">
                      {String(data.youtube_thumbnail_prompt || data.youtube_metadata?.thumbnail_prompt).slice(0, 220)}
                      {String(data.youtube_thumbnail_prompt || data.youtube_metadata?.thumbnail_prompt).length > 220
                        ? "…"
                        : ""}
                    </span>
                  </li>
                )}
              </ul>
            </section>
          )}

          {(data.youtube_upload_status ||
            data.youtube_video_id ||
            data.youtube_url ||
            data.auto_upload_enabled ||
            data.youtube_upload_blocked_reason) && (
            <section className="card full-width">
              <h2>YouTube Upload</h2>
              <ul>
                <li>
                  Auto upload enabled:{" "}
                  <strong className={data.auto_upload_enabled ? "success-text" : "muted"}>
                    {data.auto_upload_enabled ? "Yes" : "No"}
                  </strong>
                </li>
                <li>
                  Upload started:{" "}
                  <strong className={data.auto_upload_started ? "success-text" : "muted"}>
                    {data.auto_upload_started ? "Yes" : "No"}
                  </strong>
                </li>
                <li>
                  Upload status:{" "}
                  <strong className={data.youtube_upload_status === "uploaded" ? "success-text" : data.youtube_upload_status === "upload_failed" || data.youtube_upload_status === "blocked" ? "error-text" : "muted"}>
                    {data.youtube_upload_status || "—"}
                  </strong>
                </li>
                {data.youtube_upload_blocked_reason && (
                  <li>
                    Blocked reason: <strong className="error-text">{data.youtube_upload_blocked_reason}</strong>
                  </li>
                )}
                {data.youtube_video_id && (
                  <li>
                    Video ID: <strong>{data.youtube_video_id}</strong>
                  </li>
                )}
                {data.youtube_url && (
                  <li>
                    YouTube URL:{" "}
                    <a href={data.youtube_url} target="_blank" rel="noreferrer">
                      {data.youtube_url}
                    </a>
                  </li>
                )}
                {data.youtube_visibility && (
                  <li>
                    Visibility: <strong>{data.youtube_visibility}</strong>
                  </li>
                )}
                {data.youtube_publish_time && (
                  <li>
                    Scheduled publish time: <strong>{data.youtube_publish_time}</strong>
                  </li>
                )}
                {data.youtube_upload_time && (
                  <li>
                    Upload time: <strong>{data.youtube_upload_time}</strong>
                  </li>
                )}
              </ul>
            </section>
          )}

          <section className="card">
            <h2>Platform Targets</h2>
            <ul>{data.platform_targets.map((platform) => <li key={platform}>{platform}</li>)}</ul>
          </section>

          <section className="card full-width">
            <h2>Asset Library</h2>
            <p className="muted">Permanent vault for publish-ready finals. Run folders stay intact; vault copies never overwrite.</p>
            <div className="asset-library-actions">
              <button
                type="button"
                className="secondary-btn"
                disabled={!assetLibraryPath}
                onClick={() => void copyAssetPath(assetLibraryPath)}
                title={assetLibraryPath || "Asset library not initialized yet"}
              >
                Open Asset Library
              </button>
              {assetLibraryPath ? (
                <span className="mono asset-library-path">{assetLibraryPath}</span>
              ) : (
                <span className="muted">Vault path will appear after the first registered asset.</span>
              )}
            </div>
            {latestAssets.length === 0 ? (
              <p className="muted">No vaulted assets yet. Assets register when publish status is PUBLISHED_PACKAGE_CREATED.</p>
            ) : (
              <ul className="asset-library-list">
                {latestAssets.map((asset) => (
                  <li key={asset.asset_id || asset.final_video_path} className="asset-library-item">
                    <div className="asset-library-thumb">
                      {asset.thumbnail_path ? (
                        <img src={asset.thumbnail_path} alt="" />
                      ) : (
                        <span className="asset-library-thumb-placeholder">MP4</span>
                      )}
                    </div>
                    <div className="asset-library-meta">
                      <strong>{asset.topic || asset.run_id || "Untitled"}</strong>
                      <span className="muted">
                        {formatDuration(asset.duration_seconds)} · {formatAssetDate(asset.creation_time)}
                        {asset.category ? ` · ${asset.category}` : ""}
                      </span>
                      <span className="mono">{asset.final_video_path || "—"}</span>
                    </div>
                    <button
                      type="button"
                      className="secondary-btn compact"
                      disabled={!asset.final_video_path}
                      onClick={() => void copyAssetPath(String(asset.final_video_path || ""))}
                    >
                      Open Folder
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card full-width">
            <h2>Metadata</h2>
            <pre className="json-block">{JSON.stringify(data.metadata, null, 2)}</pre>
          </section>
        </div>
      )}
    </div>
  );
}
