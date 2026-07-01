import { useEffect, useMemo, useState } from "react";

import {

  createVideoGenerate,

  createVideoPreflight,

  fetchChannelProfile,

  fetchLastTopic,

  fetchRunwayLiveSmokeStatus,

  saveLastTopic,

  type CreateVideoGenerateResult,

  type CreateVideoPreflightResult,

  type DurationPlan,

} from "../api/productClient";

import {

  AUDIO_STRATEGY_OPTIONS,

  ASPECT_RATIO_OPTIONS,

  DURATION_PRESETS,

  defaultAspectRatioForPlatform,

  KLING_CLIP_HINTS,

  KLING_DURATION_PRESETS,

  PIPELINE_STEPS,

  PLATFORM_OPTIONS,

  PROVIDER_OPTIONS,

  STYLE_OPTIONS,

} from "../product/constants";

import { RunwayBrowserPanel } from "../components/RunwayBrowserPanel";



type DurationChoice = (typeof DURATION_PRESETS)[number] | (typeof KLING_DURATION_PRESETS)[number] | "custom";

type RunStatus = "idle" | "starting" | "running" | "completed" | "failed" | "unsupported" | "awaiting_approval";



const KLING_PROVIDER = "kling_3_0_pro_native_audio";



function isKlingProvider(value: string) {

  return value === KLING_PROVIDER || value === "kling" || value === "kling_3_pro_native";

}



export function CreateVideoPage() {

  const [topicMode, setTopicMode] = useState<"channel" | "custom">("custom");

  const [customTopic, setCustomTopic] = useState("");

  const [durationChoice, setDurationChoice] = useState<DurationChoice>(30);

  const [customDuration, setCustomDuration] = useState("45");

  const [platform, setPlatform] = useState("youtube_shorts");

  const [aspectRatio, setAspectRatio] = useState(defaultAspectRatioForPlatform("youtube_shorts"));

  const [aspectRatioManual, setAspectRatioManual] = useState(false);

  const [style, setStyle] = useState("cinematic");

  const [provider, setProvider] = useState(KLING_PROVIDER);

  const [audioStrategy, setAudioStrategy] = useState("kling_native_audio");

  const [useDirector, setUseDirector] = useState(true);

  const [useCritic, setUseCritic] = useState(true);

  const [useChannelProfile, setUseChannelProfile] = useState(true);

  const [channelTopic, setChannelTopic] = useState("");

  const [channelNiche, setChannelNiche] = useState("");

  const [specificStoryOverride, setSpecificStoryOverride] = useState("");

  const [plan, setPlan] = useState<DurationPlan | null>(null);

  const [preflight, setPreflight] = useState<CreateVideoPreflightResult | null>(null);

  const [clipCount, setClipCount] = useState<number | null>(null);

  const [authoritativeTopic, setAuthoritativeTopic] = useState("");

  const [steps, setSteps] = useState<string[]>([...PIPELINE_STEPS]);

  const [warnings, setWarnings] = useState<string[]>([]);

  const [busy, setBusy] = useState(false);

  const [generating, setGenerating] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [runStatus, setRunStatus] = useState<RunStatus>("idle");

  const [runId, setRunId] = useState("");

  const [latestStep, setLatestStep] = useState("");

  const [generateResult, setGenerateResult] = useState<CreateVideoGenerateResult | null>(null);



  useEffect(() => {

    void fetchLastTopic()

      .then((saved) => {

        const topic = String(saved.topic || "").trim();

        if (topic) {

          setCustomTopic(topic);

          setTopicMode((saved.topic_mode as "channel" | "custom") || "custom");

        }

      })

      .catch(() => {

        /* offline fallback */

      });

    void fetchChannelProfile()

      .then((profile) => {

        setChannelTopic(profile.channel_topic);

        setChannelNiche(profile.main_niche);

        setPlatform(profile.default_platform || "youtube_shorts");

        setAspectRatio(defaultAspectRatioForPlatform(profile.default_platform || "youtube_shorts"));

        setStyle(profile.visual_style || profile.tone_style || "cinematic");

        setUseDirector(profile.use_ai_director_default !== false);

        setUseCritic(profile.use_prompt_critic_default !== false);

        const preset = profile.default_duration_seconds as DurationChoice;

        if (KLING_DURATION_PRESETS.includes(preset as (typeof KLING_DURATION_PRESETS)[number])) {

          setDurationChoice(preset);

        }

      })

      .catch(() => {

        /* offline fallback */

      });

  }, []);



  useEffect(() => {

    if (!aspectRatioManual) {

      setAspectRatio(defaultAspectRatioForPlatform(platform));

    }

  }, [platform, aspectRatioManual]);



  function persistTopic(topic: string) {

    const cleaned = topic.trim();

    if (!cleaned) {

      return;

    }

    void saveLastTopic(cleaned, topicMode).catch(() => {

      /* offline fallback */

    });

  }



  const klingUiActive = useMemo(() => {

    if (isKlingProvider(provider) || audioStrategy === "kling_native_audio") {

      return true;

    }

    if (preflight?.provider && isKlingProvider(preflight.provider)) {

      return true;

    }

    return preflight?.audio_strategy === "kling_native_audio";

  }, [provider, audioStrategy, preflight]);



  const durationSeconds = useMemo(() => {

    if (durationChoice === "custom") {

      return Math.max(klingUiActive ? 15 : 6, parseInt(customDuration, 10) || (klingUiActive ? 15 : 6));

    }

    return durationChoice;

  }, [durationChoice, customDuration, klingUiActive]);



  const resolvedProvider = useMemo(() => {

    if (provider !== "auto") {

      return provider === "runway_gen5" ? "runway" : provider;

    }

    return preflight?.provider || provider;

  }, [provider, preflight]);



  function buildPayload(extra: Record<string, unknown> = {}) {

    const payload: Record<string, unknown> = {

      topic_source: topicMode,

      topic_mode: topicMode,

      custom_topic: topicMode === "custom" ? customTopic : channelTopic,

      specific_story_override: specificStoryOverride,

      duration_seconds: durationSeconds,

      duration_preset: String(durationChoice),

      platform,

      aspect_ratio: aspectRatio,

      aspect_ratio_manual: aspectRatioManual,

      platform_targets: [platform],

      style,

      provider: provider === "auto" ? "auto" : resolvedProvider,

      audio_strategy: audioStrategy,

      use_ai_director: useDirector,

      use_prompt_critic: useCritic,

      use_channel_profile: useChannelProfile,

      execution_mode: "FULL_AUTO",

      free_credit_first: true,

      free_credit_mode: true,

      ...extra,

    };

    if (clipCount !== null) {

      payload.clip_count = clipCount;

    }

    if (runId) {

      payload.run_id = runId;

    }

    return payload;

  }



  async function handlePreflight() {

    setBusy(true);

    setError(null);

    try {

      const result = await createVideoPreflight(buildPayload());

      setPreflight(result);

      setPlan(result.duration_plan);

      setClipCount(result.kling_clip_count ?? result.duration_plan.clip_count);

      setAuthoritativeTopic(result.authoritative_topic);

      setSteps(result.pipeline_steps);

      setWarnings(result.warnings);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Preflight failed");

    } finally {

      setBusy(false);

    }

  }



  async function handleGenerate() {

    setGenerating(true);

    setError(null);

    setGenerateResult(null);



    const klingRoute =

      klingUiActive ||

      isKlingProvider(preflight?.provider || "") ||

      preflight?.audio_strategy === "kling_native_audio";



    if (!customTopic.trim() && topicMode === "custom" && !channelTopic.trim()) {

      setGenerating(false);

      setError("Enter a channel topic / niche before generating.");

      return;

    }



    persistTopic(customTopic);



    setRunStatus("starting");

    setLatestStep(klingRoute ? "Starting Kling Frame-to-Video workflow…" : "Starting Phase I FULL_AUTO…");



    try {

      const result = await createVideoGenerate(

        buildPayload({

          approve_generate: klingRoute,

          approved_by: klingRoute ? "product_studio" : "",

          confirm_credit_spend: klingRoute,

        }),

      );



      setGenerateResult(result);

      setPreflight((current) => ({ ...(current || {}), ...result } as CreateVideoPreflightResult));

      setPlan(result.duration_plan || null);

      setClipCount(result.kling_clip_count ?? result.duration_plan?.clip_count ?? clipCount);

      setAuthoritativeTopic(result.authoritative_topic || authoritativeTopic);

      setSteps(result.pipeline_steps || steps);

      setWarnings(Array.isArray(result.warnings) ? result.warnings : warnings);

      const blockedStatuses = new Set([
        "paid_credit_blocked",
        "duplicate_failed",
        "dry_run",
        "failed",
        "download_failed",
        "visual_repetition_failed",
      ]);

      if (blockedStatuses.has(String(result.status || ""))) {
        setRunStatus("failed");
        setError(
          result.message
            || `Generate blocked (${result.status}). No clips were generated or registered.`,
        );
        return;
      }

      if (!result.ok && result.status !== "partial") {
        setRunStatus("failed");
        setError(result.message || `Generate failed (${result.status || "unknown"})`);
        return;
      }

      if (!result.wired || result.status === "unsupported_provider") {

        setRunStatus("unsupported");

        setError(result.message || "Provider execution not wired yet.");

        return;

      }



      if (klingRoute && result.status === "failed" && result.generate_clicked) {

        setRunStatus("failed");

        setError(result.message || "Generate failed");

        return;

      }



      if (!result.ok && !klingRoute) {

        setRunStatus("failed");

        setError(result.message || "Generate failed");

        return;

      }



      setRunId(result.run_id || result.session_id || result.project_id || "");



      if (klingRoute) {

        setRunStatus(result.status === "completed" ? "completed" : "running");

        const runtime = result.generation_runtime_status;

        if (runtime?.clip_statuses?.length) {

          const active = runtime.clip_statuses.find((item) => item.status === "generating")

            || runtime.clip_statuses[runtime.clip_statuses.length - 1];

          setLatestStep(

            runtime.generation_state === "merge_complete"

              ? "Merge Complete"

              : `${active?.label || `Clip ${runtime.current_clip}/${runtime.planned_clip_count}`} Generating...`,

          );

        } else {

          const planned = result.multiclip_execution_plan?.clip_count ?? result.kling_clip_count ?? 1;

          setLatestStep(

            result.status === "completed"

              ? planned > 1

                ? "Merge Complete"

                : "Kling Native Audio generation completed"

              : `Clip 1/${planned} Generating...`,

          );

        }

        if (result.status === "completed") {

          setRunStatus("completed");

        }

        return;

      }



      setRunStatus("running");

      setLatestStep("Runway browser session started");

    } catch (err) {

      setRunStatus("failed");

      setError(err instanceof Error ? err.message : "Generate failed");

    } finally {

      setGenerating(false);

    }

  }



  useEffect(() => {

    if (runStatus !== "running" || isKlingProvider(generateResult?.provider || preflight?.provider || "")) {

      return;

    }

    const timer = window.setInterval(() => {

      void fetchRunwayLiveSmokeStatus()

        .then((status) => {

          const snapshot = status.snapshot || {};

          const step = String(snapshot.current_step_id || snapshot.last_auto_action || snapshot.next_auto_action || "");

          if (step) {

            setLatestStep(step);

          }

          if (status.active) {

            setRunStatus("running");

            return;

          }

          const report = status.report || {};

          const ok = Boolean(report.ok ?? snapshot.run_ok);

          setRunStatus(ok ? "completed" : "failed");

          if (!ok) {

            setError(String(report.stopped_reason || snapshot.stopped_reason || "Run failed"));

          }

        })

        .catch(() => {

          /* keep polling */

        });

    }, 2500);

    return () => window.clearInterval(timer);

  }, [runStatus, generateResult?.provider, preflight?.provider]);



  const durationPresets = klingUiActive ? KLING_DURATION_PRESETS : DURATION_PRESETS;

  const showRunwayPanel = !klingUiActive && (resolvedProvider === "runway" || provider === "runway" || provider === "runway_gen5");



  return (

    <div className="product-page">

      <header className="header">

        <div>

          <p className="eyebrow">Create Video</p>

          <h1>Professional Create Flow</h1>

          <p className="subtitle">

            Preflight planning, then Generate routes to Runway, Hailuo, or Kling 3.0 Pro Native Audio based on your selections.

          </p>

        </div>

      </header>



      {error && <div className="error-banner">{error}</div>}



      {showRunwayPanel && <RunwayBrowserPanel compact showRunwayDetails={false} />}



      {runStatus === "completed" && (

        <div className="success-banner">

          Video run completed. Open Results from the sidebar to view the output package.

        </div>

      )}



      <div className="product-form-grid">

        <section className="card">

          <h2>Channel Topic / Niche</h2>

          <p className="muted">The channel theme guides story ideation. Each run gets a fresh story inside this niche unless you override it below.</p>

          <label className="field-row">

            <input type="radio" checked={topicMode === "channel"} onChange={() => setTopicMode("channel")} />

            Use saved channel topic

            <span className="muted"> ({channelTopic || channelNiche || "configure in Settings"})</span>

          </label>

          <label className="field-row">

            <input type="radio" checked={topicMode === "custom"} onChange={() => setTopicMode("custom")} />

            Use custom channel topic / niche

          </label>

          <input

            className="filter-input full-width"

            placeholder="Channel topic / niche (e.g. dark fantasy analog horror stories)"

            value={customTopic}

            onChange={(e) => setCustomTopic(e.target.value)}

            onBlur={() => persistTopic(customTopic)}

            disabled={topicMode !== "custom"}

          />

          <label className="field-row" style={{ marginTop: "1rem" }}>

            Specific Story Override <span className="muted">(optional)</span>

          </label>

          <textarea

            className="filter-input full-width"

            placeholder="Leave empty to auto-generate a fresh story for this run"

            value={specificStoryOverride}

            onChange={(e) => setSpecificStoryOverride(e.target.value)}

            rows={3}

          />

        </section>



        <section className="card">

          <h2>Duration</h2>

          <div className="chip-row">

            {durationPresets.map((preset) => (

              <button

                key={preset}

                type="button"

                className={`chip-btn ${durationChoice === preset ? "active" : ""}`}

                onClick={() => setDurationChoice(preset)}

              >

                {preset}s

              </button>

            ))}

            <button

              type="button"

              className={`chip-btn ${durationChoice === "custom" ? "active" : ""}`}

              onClick={() => setDurationChoice("custom")}

            >

              Custom

            </button>

          </div>

          {durationChoice === "custom" && (

            <input

              className="filter-input full-width"

              type="number"

              min={klingUiActive ? 15 : 6}

              value={customDuration}

              onChange={(e) => setCustomDuration(e.target.value)}

            />

          )}

          {klingUiActive && (

            <p className="muted">

              {KLING_CLIP_HINTS[durationSeconds] || `${durationSeconds}s Kling pack`} — 12s Main Action + 3s Continuity Bridge per clip

            </p>

          )}

          {plan && (

            <p className="muted">

              Planned clips: <strong>{preflight?.kling_clip_count ?? plan.clip_count}</strong>

              {klingUiActive ? ` · ${preflight?.kling_shot_mode || "two_shot_continuity"}` : ` (${plan.provider} limit ${plan.clip_limit_seconds}s/clip)`}

            </p>

          )}

          {!klingUiActive && (

            <label className="field-row full-width">

              Clip count override

              <input

                className="filter-input full-width"

                type="number"

                min={1}

                max={6}

                value={clipCount ?? plan?.clip_count ?? ""}

                onChange={(e) => setClipCount(Math.max(1, Math.min(6, parseInt(e.target.value, 10) || 1)))}

              />

            </label>

          )}

        </section>



        <section className="card">

          <h2>Platform & Style</h2>

          <select className="filter-input full-width" value={platform} onChange={(e) => setPlatform(e.target.value)}>

            {PLATFORM_OPTIONS.map((item) => (

              <option key={item.id} value={item.id}>

                {item.label}

              </option>

            ))}

          </select>

          <label className="field-label">Aspect ratio</label>

          <select
            className="filter-input full-width"
            value={aspectRatio}
            onChange={(e) => {
              setAspectRatio(e.target.value);
              setAspectRatioManual(true);
            }}
          >

            {ASPECT_RATIO_OPTIONS.map((item) => (

              <option key={item.id} value={item.id}>

                {item.label}

              </option>

            ))}

          </select>

          <select className="filter-input full-width" value={style} onChange={(e) => setStyle(e.target.value)}>

            {STYLE_OPTIONS.map((item) => (

              <option key={item} value={item}>

                {item}

              </option>

            ))}

          </select>

        </section>



        <section className="card">

          <h2>Audio Strategy</h2>

          <select className="filter-input full-width" value={audioStrategy} onChange={(e) => setAudioStrategy(e.target.value)}>

            {AUDIO_STRATEGY_OPTIONS.map((item) => (

              <option key={item.id} value={item.id}>

                {item.label}

              </option>

            ))}

          </select>

          <h2>Video Provider</h2>

          <select className="filter-input full-width" value={provider} onChange={(e) => setProvider(e.target.value)}>

            {PROVIDER_OPTIONS.map((item) => (

              <option key={item.id} value={item.id}>

                {item.label}

              </option>

            ))}

          </select>

        </section>



        <section className="card">

          <h2>AI Options</h2>

          <label className="field-row"><input type="checkbox" checked={useDirector} onChange={(e) => setUseDirector(e.target.checked)} /> Use AI Director</label>

          <label className="field-row"><input type="checkbox" checked={useCritic} onChange={(e) => setUseCritic(e.target.checked)} /> Use Prompt Critic</label>

          <label className="field-row"><input type="checkbox" checked={useChannelProfile} onChange={(e) => setUseChannelProfile(e.target.checked)} /> Use Channel Profile</label>

          <div className="chip-row">

            <button type="button" className="chip-btn" disabled={busy} onClick={() => void handlePreflight()}>

              {busy ? "Planning…" : "Preflight Plan"}

            </button>

            <button type="button" className="primary-btn" disabled={generating} onClick={() => void handleGenerate()}>

              {generating ? "Starting…" : "Generate Video"}

            </button>

          </div>

        </section>

      </div>



      {(preflight || authoritativeTopic || warnings.length > 0) && (

        <section className="card detail-card kling-preflight-panel">

          <h2>Preflight</h2>

          {authoritativeTopic && <p>Authoritative topic: <strong>{authoritativeTopic}</strong></p>}

          {preflight && (

            <div className="kling-preflight-summary">

              <p>Provider: <strong>{preflight.provider}</strong></p>

              <p>Platform: <strong>{preflight.platform || platform}</strong></p>

              <p>Aspect Ratio: <strong>{preflight.aspect_ratio || aspectRatio}</strong></p>

              <p>Audio Strategy: <strong>{preflight.audio_strategy || audioStrategy}</strong></p>

              <p>Planned Duration: <strong>{preflight.duration_plan.duration_seconds}s</strong></p>

              <p>Clip Count: <strong>{preflight.kling_clip_count ?? preflight.duration_plan.clip_count}</strong></p>

              <p>Execution Mode: <strong>{preflight.multiclip_execution_plan?.execution_mode || preflight.clip_execution_mode || preflight.duration_plan.execution_mode || "—"}</strong></p>

              <p>Shot Mode: <strong>{preflight.kling_shot_mode || preflight.duration_plan.shot_mode || "—"}</strong></p>

              {preflight.native_audio_required && <p className="muted">Native audio required · ElevenLabs disabled · External music disabled</p>}

            </div>

          )}

          {preflight?.kling_clip_prompts?.map((clip) => (

            <div key={clip.clip_index} className="kling-clip-preview">

              <h3>Clip {clip.clip_index}</h3>

              <p className="muted">Shot 1 ({clip.shot_1_duration_seconds}s)</p>

              <pre className="prompt-preview">{clip.shot_1_prompt}</pre>

              <p className="muted">Shot 2 ({clip.shot_2_duration_seconds}s)</p>

              <pre className="prompt-preview">{clip.shot_2_prompt}</pre>

              {clip.continuity_anchor && (

                <p><strong>Continuity Anchor:</strong> {clip.continuity_anchor}</p>

              )}

              {clip.next_clip_reference_hint && (

                <p><strong>Next Clip Reference:</strong> {clip.next_clip_reference_hint}</p>

              )}

            </div>

          ))}

          {warnings.map((warning) => (

            <p key={warning} className="warning-text">{warning}</p>

          ))}

        </section>

      )}



      {runStatus !== "idle" && (

        <section className="card detail-card">

          <h2>Execution Status</h2>

          <p>Status: <strong>{runStatus}</strong></p>

          {runId && <p className="muted">Run ID: {runId}</p>}

          {generateResult?.output_folder && <p className="muted">Output: {generateResult.output_folder}</p>}

          {generateResult?.download_path && <p className="muted">Download: {generateResult.download_path}</p>}

          {latestStep && <p className="muted">Latest step: {latestStep}</p>}

          {generateResult?.execution_mode && <p className="muted">Execution Mode: <strong>{generateResult.execution_mode}</strong></p>}

          {(generateResult?.multiclip_execution_plan?.clip_count || generateResult?.kling_clip_count) && (

            <p className="muted">

              Planned clips: <strong>{generateResult.multiclip_execution_plan?.clip_count ?? generateResult.kling_clip_count}</strong>

            </p>

          )}

          {generateResult?.generation_runtime_status?.clip_statuses?.map((clip) => (

            <p key={clip.clip} className="muted">

              {clip.label} — <strong>{clip.status === "completed" ? (generateResult.generation_runtime_status?.generation_state === "merge_complete" && clip.clip === generateResult.generation_runtime_status.planned_clip_count ? "Merge Complete" : "Completed") : clip.status === "generating" ? "Generating..." : clip.status}</strong>

            </p>

          ))}

          {generateResult?.generation_time_seconds != null && (

            <p className="muted">Generation time: <strong>{generateResult.generation_time_seconds}s</strong></p>

          )}

          {generateResult?.provider && <p className="muted">Provider: {generateResult.provider}</p>}

          {runStatus === "completed" && (

            <p className="muted">Open Results from the sidebar to view the publish package.</p>

          )}

        </section>

      )}



      <section className="card detail-card">

        <h2>Progress Steps</h2>

        <ol className="progress-steps">

          {steps.map((step) => (

            <li key={step}>{step}</li>

          ))}

        </ol>

      </section>

    </div>

  );

}


