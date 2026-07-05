import { useEffect, useMemo, useState } from "react";

import {

  createVideoGenerate,

  createVideoPreflight,

  fetchChannelProfile,

  fetchLastTopic,

  fetchRunwayLiveSmokeStatus,

  saveChannelProfile,

  saveLastTopic,

  type CreateVideoGenerateResult,

  type CreateVideoPreflightResult,

  type DurationPlan,

} from "../api/productClient";

import {

  AUDIO_STRATEGY_OPTIONS,

  KLING_CLIP_HINTS,

  PIPELINE_STEPS,

  PROVIDER_OPTIONS,

} from "../product/constants";

import {

  DEFAULT_PLATFORM_SETTINGS,

  INSTAGRAM_DURATION_OPTIONS,

  INSTAGRAM_FILTER_MOOD_OPTIONS,

  INSTAGRAM_STYLE_OPTIONS,

  PLATFORM_TABS,

  TIKTOK_DURATION_OPTIONS,

  TIKTOK_PACE_OPTIONS,

  TIKTOK_STYLE_OPTIONS,

  YOUTUBE_DURATION_OPTIONS,

  YOUTUBE_STYLE_OPTIONS,

  type PlatformSettings,

  type PlatformTabId,

} from "../product/platformStyleOptions";

import { RunwayBrowserPanel } from "../components/RunwayBrowserPanel";

import {
  ProviderBrowserStatus,
  isRunwaySessionExpired,
  pwmapBrowserRequired,
} from "../components/ProviderBrowserStatus";

import {
  fetchBrowserStatus,
  type BrowserStatusResponse,
} from "../api/browserOperationsClient";

import {
  fetchRunwaySessionStatus,
  type RunwaySessionStatus,
} from "../api/platformClient";



type RunStatus = "idle" | "starting" | "running" | "completed" | "failed" | "unsupported" | "awaiting_approval";



const KLING_PROVIDER = "kling_3_0_pro_native_audio";

type TopicMode = "saved" | "custom";

function readStoredTopicMode(): TopicMode {
  const saved = localStorage.getItem("topicMode") ?? "saved";
  return saved === "custom" ? "custom" : "saved";
}

function persistTopicMode(value: TopicMode) {
  localStorage.setItem("topicMode", value);
}

function topicModeForApi(mode: TopicMode): "channel" | "custom" {
  return mode === "saved" ? "channel" : "custom";
}



function isKlingProvider(value: string) {

  return value === KLING_PROVIDER || value === "kling" || value === "kling_3_pro_native";

}



function runwaySessionIndicator(session: RunwaySessionStatus | null): {
  tone: "ok" | "warn" | "bad";
  text: string;
} {
  if (session?.connected) {
    return { tone: "ok", text: "● Runway Connected" };
  }
  const msg = (session?.message || "").toLowerCase();
  if (msg.includes("expired") || msg.includes("login")) {
    return { tone: "warn", text: "● Runway Session Expired — reconnect first" };
  }
  return { tone: "bad", text: "● Runway Disconnected — connect first" };
}



export function CreateVideoPage() {

  const [topicMode, setTopicMode] = useState<TopicMode>(readStoredTopicMode);

  function updateTopicMode(value: TopicMode) {
    setTopicMode(value);
    persistTopicMode(value);
  }

  const [customTopic, setCustomTopic] = useState("");

  const [activePlatformTab, setActivePlatformTab] = useState<PlatformTabId>("youtube_shorts");

  const [platformSettings, setPlatformSettings] = useState<PlatformSettings>(DEFAULT_PLATFORM_SETTINGS);

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

  const [runwaySession, setRunwaySession] = useState<RunwaySessionStatus | null>(null);

  const [browserStatus, setBrowserStatus] = useState<BrowserStatusResponse | null>(null);



  useEffect(() => {

    void fetchLastTopic()

      .then((saved) => {

        const topic = String(saved.topic || "").trim();

        if (topic) {

          setCustomTopic(topic);

        }

      })

      .catch(() => {

        /* offline fallback */

      });

    void fetchChannelProfile()

      .then((profile) => {

        setChannelTopic(profile.channel_topic);

        setChannelNiche(profile.main_niche);

        setPlatformSettings({
          youtube_shorts: {
            style: profile.youtube_video_style || profile.visual_style || profile.tone_style || "cinematic realistic",
            duration: profile.default_duration_seconds || 30,
          },
          instagram_reels: {
            style: profile.instagram_video_style || "aesthetic",
            duration: profile.default_duration_seconds === 40 ? 30 : profile.default_duration_seconds || 30,
            filterMood: profile.instagram_filter_mood || "neutral",
          },
          tiktok: {
            style: profile.tiktok_video_style || "energetic",
            duration: profile.default_duration_seconds === 40 ? 30 : profile.default_duration_seconds || 30,
            pace: profile.tiktok_pace || "medium",
          },
        });

        setUseDirector(profile.use_ai_director_default !== false);

        setUseCritic(profile.use_prompt_critic_default !== false);

      })

      .catch(() => {

        /* offline fallback */

      });

  }, []);



  function persistTopic(topic: string) {

    const cleaned = topic.trim();

    if (!cleaned) {

      return;

    }

    void saveLastTopic(cleaned, topicModeForApi(topicMode)).catch(() => {

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



  const durationSeconds = useMemo(() => platformSettings[activePlatformTab].duration, [platformSettings, activePlatformTab]);



  const activePlatformStyle = useMemo(() => {
    if (activePlatformTab === "instagram_reels") {
      const settings = platformSettings.instagram_reels;
      return `${settings.style} — ${settings.filterMood} filter mood`;
    }
    if (activePlatformTab === "tiktok") {
      const settings = platformSettings.tiktok;
      return `${settings.style} — ${settings.pace} pace editing`;
    }
    return platformSettings.youtube_shorts.style;
  }, [platformSettings, activePlatformTab]);



  function savePlatformStylePreferences() {
    void saveChannelProfile({
      youtube_video_style: platformSettings.youtube_shorts.style,
      instagram_video_style: platformSettings.instagram_reels.style,
      instagram_filter_mood: platformSettings.instagram_reels.filterMood,
      tiktok_video_style: platformSettings.tiktok.style,
      tiktok_pace: platformSettings.tiktok.pace,
      default_platform: activePlatformTab,
      default_duration_seconds: durationSeconds,
    }).catch(() => {
      /* offline fallback */
    });
  }



  const resolvedProvider = useMemo(() => {

    if (provider !== "auto") {

      return provider === "runway_gen5" ? "runway" : provider;

    }

    return preflight?.provider || provider;

  }, [provider, preflight]);



  function patchPlatformSettings<T extends PlatformTabId>(
    tab: T,
    patch: Partial<PlatformSettings[T]>,
  ) {
    setPlatformSettings((current) => ({
      ...current,
      [tab]: { ...current[tab], ...patch },
    }));
  }



  function buildPayload(extra: Record<string, unknown> = {}) {

    const apiTopicMode = topicModeForApi(topicMode);

    const payload: Record<string, unknown> = {

      topic_source: apiTopicMode,

      topic_mode: apiTopicMode,

      custom_topic: topicMode === "custom" ? customTopic : channelTopic,

      specific_story_override: specificStoryOverride,

      duration_seconds: durationSeconds,

      duration_preset: String(durationSeconds),

      platform: activePlatformTab,

      aspect_ratio: "9:16",

      aspect_ratio_manual: false,

      platform_targets: [activePlatformTab],

      style: activePlatformStyle,

      visual_style: activePlatformStyle,

      youtube_video_style: platformSettings.youtube_shorts.style,

      instagram_video_style: platformSettings.instagram_reels.style,

      instagram_filter_mood: platformSettings.instagram_reels.filterMood,

      tiktok_video_style: platformSettings.tiktok.style,

      tiktok_pace: platformSettings.tiktok.pace,

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

      savePlatformStylePreferences();

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



    if (runwayGenerateBlocked) {

      setGenerating(false);

      setError(

        isRunwaySessionExpired(runwaySession)

          ? "⚠️ Runway session expired. Click 'Connect Runway Browser' to reconnect. (Kling 3.0 Pro uses this same session.)"

          : "❌ Runway browser not connected. Click 'Connect Runway Browser' first. (Required for Runway and Kling 3.0 Pro.)",

      );

      return;

    }



    persistTopic(customTopic);

    savePlatformStylePreferences();



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



  const showRunwayPanel = pwmapBrowserRequired(klingUiActive, provider, resolvedProvider);

  const runwaySessionState = useMemo(() => runwaySessionIndicator(runwaySession), [runwaySession]);

  const runwayGenerateBlocked = showRunwayPanel && !runwaySession?.connected;



  useEffect(() => {
    let cancelled = false;
    const refreshBrowserConnections = () => {
      void fetchRunwaySessionStatus(false)
        .then((payload) => {
          if (!cancelled) {
            setRunwaySession(payload);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setRunwaySession(null);
          }
        });
      void fetchBrowserStatus()
        .then((payload) => {
          if (!cancelled) {
            setBrowserStatus(payload);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setBrowserStatus(null);
          }
        });
    };
    refreshBrowserConnections();
    const timer = window.setInterval(refreshBrowserConnections, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);



  const activeTabLabel = PLATFORM_TABS.find((tab) => tab.id === activePlatformTab)?.label || activePlatformTab;



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



      <div className="info-banner" role="note">

        ⚡ Manual Creation — For custom one-off videos. Daily automation runs independently from Automation Center.

      </div>



      {showRunwayPanel && (

        <div className={`runway-connection-status ${runwaySessionState.tone}`} role="status">

          {runwaySessionState.text}

          {klingUiActive && <span className="muted"> — Kling 3.0 Pro uses this Runway session</span>}

        </div>

      )}



      <ProviderBrowserStatus
        runwaySession={runwaySession}
        browserStatus={browserStatus}
        klingUsesRunway={klingUiActive}
      />



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

            <input
              type="radio"
              checked={topicMode === "saved"}
              onChange={() => updateTopicMode("saved")}
            />

            Use saved channel topic

            <span className="muted"> ({channelTopic || channelNiche || "configure in Settings"})</span>

          </label>

          <label className="field-row">

            <input type="radio" checked={topicMode === "custom"} onChange={() => updateTopicMode("custom")} />

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

          <h2>Duration & Clips</h2>

          <p className="muted">

            Duration for <strong>{activeTabLabel}</strong>: <strong>{durationSeconds}s</strong> (configure in Platform & Style)

          </p>

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

          <div className="platform-tab-row">

            {PLATFORM_TABS.map((tab) => (

              <button

                key={tab.id}

                type="button"

                className={`chip-btn platform-tab ${activePlatformTab === tab.id ? "active" : ""}`}

                onClick={() => setActivePlatformTab(tab.id)}

              >

                {tab.label}

              </button>

            ))}

          </div>

          <div className="platform-style-panel">

            <p className="platform-locked-field">Aspect ratio: <strong>9:16</strong> (locked)</p>

            {activePlatformTab === "youtube_shorts" && (

              <>

                <label className="field-label">Style</label>

                <select

                  className="filter-input full-width"

                  value={platformSettings.youtube_shorts.style}

                  onChange={(e) => patchPlatformSettings("youtube_shorts", { style: e.target.value })}

                >

                  {YOUTUBE_STYLE_OPTIONS.map((item) => (

                    <option key={item.id} value={item.id}>

                      {item.label}

                    </option>

                  ))}

                </select>

                <label className="field-label">Duration</label>

                <div className="chip-row">

                  {YOUTUBE_DURATION_OPTIONS.map((preset) => (

                    <button

                      key={preset}

                      type="button"

                      className={`chip-btn ${platformSettings.youtube_shorts.duration === preset ? "active" : ""}`}

                      onClick={() => patchPlatformSettings("youtube_shorts", { duration: preset })}

                    >

                      {preset}s

                    </button>

                  ))}

                </div>

              </>

            )}

            {activePlatformTab === "instagram_reels" && (

              <>

                <label className="field-label">Style</label>

                <select

                  className="filter-input full-width"

                  value={platformSettings.instagram_reels.style}

                  onChange={(e) => patchPlatformSettings("instagram_reels", { style: e.target.value })}

                >

                  {INSTAGRAM_STYLE_OPTIONS.map((item) => (

                    <option key={item.id} value={item.id}>

                      {item.label}

                    </option>

                  ))}

                </select>

                <label className="field-label">Duration</label>

                <div className="chip-row">

                  {INSTAGRAM_DURATION_OPTIONS.map((preset) => (

                    <button

                      key={preset}

                      type="button"

                      className={`chip-btn ${platformSettings.instagram_reels.duration === preset ? "active" : ""}`}

                      onClick={() => patchPlatformSettings("instagram_reels", { duration: preset })}

                    >

                      {preset}s

                    </button>

                  ))}

                </div>

                <label className="field-label">Filter mood</label>

                <select

                  className="filter-input full-width"

                  value={platformSettings.instagram_reels.filterMood}

                  onChange={(e) => patchPlatformSettings("instagram_reels", { filterMood: e.target.value })}

                >

                  {INSTAGRAM_FILTER_MOOD_OPTIONS.map((item) => (

                    <option key={item.id} value={item.id}>

                      {item.label}

                    </option>

                  ))}

                </select>

              </>

            )}

            {activePlatformTab === "tiktok" && (

              <>

                <label className="field-label">Style</label>

                <select

                  className="filter-input full-width"

                  value={platformSettings.tiktok.style}

                  onChange={(e) => patchPlatformSettings("tiktok", { style: e.target.value })}

                >

                  {TIKTOK_STYLE_OPTIONS.map((item) => (

                    <option key={item.id} value={item.id}>

                      {item.label}

                    </option>

                  ))}

                </select>

                <label className="field-label">Duration</label>

                <div className="chip-row">

                  {TIKTOK_DURATION_OPTIONS.map((preset) => (

                    <button

                      key={preset}

                      type="button"

                      className={`chip-btn ${platformSettings.tiktok.duration === preset ? "active" : ""}`}

                      onClick={() => patchPlatformSettings("tiktok", { duration: preset })}

                    >

                      {preset}s

                    </button>

                  ))}

                </div>

                <label className="field-label">Pace</label>

                <select

                  className="filter-input full-width"

                  value={platformSettings.tiktok.pace}

                  onChange={(e) => patchPlatformSettings("tiktok", { pace: e.target.value })}

                >

                  {TIKTOK_PACE_OPTIONS.map((item) => (

                    <option key={item.id} value={item.id}>

                      {item.label}

                    </option>

                  ))}

                </select>

              </>

            )}

          </div>

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

            <button
              type="button"
              className="primary-btn"
              disabled={generating || runwayGenerateBlocked}
              title={
                runwayGenerateBlocked
                  ? "Connect Runway Browser first (required for Runway and Kling 3.0 Pro)"
                  : undefined
              }
              onClick={() => void handleGenerate()}
            >

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

              <p>Platform: <strong>{preflight.platform || activePlatformTab}</strong></p>

              <p>Aspect Ratio: <strong>{preflight.aspect_ratio || "9:16"}</strong></p>

              <p>Visual Style: <strong>{activePlatformStyle}</strong></p>

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


