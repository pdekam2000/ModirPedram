import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  fetchChannelProfile,
  fetchChannelLogoStatus,
  fetchElevenLabsConnectionStatus,
  fetchLatestResults,
  saveChannelProfile,
  suggestChannelProfile,
  testElevenLabsConnection,
  uploadChannelLogo,
  type ChannelProfile,
  type ChannelProfileSuggestion,
  type ElevenLabsConnectionStatus,
} from "../api/productClient";
import {
  fetchAutomationCenter,
  fetchAutomationStatus,
  fetchCredentials,
  type AutomationCenterState,
  type AutomationStatus,
  type CredentialStatus,
} from "../api/platformClient";
import { useAppMode } from "../context/AppModeContext";
import { CredentialTable } from "../components/settings/CredentialTable";
import { SettingsAccordion } from "../components/settings/SettingsAccordion";
import {
  LANGUAGE_PRESETS,
  MUSIC_PRESETS,
  NARRATION_PRESETS,
  PROVIDER_PRESETS,
  TONE_PRESETS,
  VISUAL_STYLE_PRESETS,
  WIZARD_TOPIC_EXAMPLES,
} from "../product/channelPresets";
import { DURATION_PRESET_OPTIONS, DURATION_PRESETS, PLATFORM_OPTIONS } from "../product/constants";

const emptyProfile: ChannelProfile = {
  channel_name: "",
  main_niche: "",
  sub_niche: "",
  channel_topic: "",
  target_audience: "",
  language: "English",
  tone_style: "cinematic",
  visual_style: "cinematic realistic",
  default_platform: "youtube_shorts",
  default_duration_seconds: 30,
  default_provider: "runway",
  default_voice: "",
  default_narration_provider: "elevenlabs",
  music_provider: "none",
  preferred_topics: [],
  forbidden_topics: [],
  content_formats: [],
  upload_platforms: ["tiktok", "instagram_reels", "youtube_shorts"],
  use_ai_director_default: true,
  use_prompt_critic_default: true,
  branding_enabled: true,
  logo_enabled: true,
  logo_position: "top_right",
  logo_scale: 0.12,
  subtitle_enabled: true,
  subtitle_style: "tiktok",
  subtitle_position: "bottom_center",
  cta_enabled: true,
  cta_text: "Follow for more",
  cta_position: "bottom_center",
  cta_frequency: "end",
  intro_enabled: false,
  intro_text: "",
  intro_duration: 2,
  outro_enabled: false,
  outro_text: "",
  outro_duration: 2,
  youtube_upload_enabled: false,
  youtube_privacy: "private",
  youtube_default_description: "",
  youtube_default_hashtags: [],
  youtube_upload_confirmed: false,
  youtube_credentials_configured: false,
  youtube_oauth_client_path: "",
  youtube_made_for_kids: false,
  youtube_require_confirmation: true,
  local_mode: true,
  asset_vault_enabled: true,
  asset_copy_mode: "copy",
};

const SECTION_IDS = [
  "channel",
  "credentials",
  "providers",
  "branding",
  "voice-music",
  "upload",
  "automation",
  "asset-library",
  "local-access",
  "advanced",
] as const;

type SectionId = (typeof SECTION_IDS)[number];

function listToText(items: string[] | undefined) {
  return (items || []).join(", ");
}

function textToList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function presetOrCustom(value: string, presets: readonly string[]) {
  const normalized = value.trim().toLowerCase();
  const match = presets.find((item) => item.toLowerCase() === normalized);
  if (match) return { mode: match, custom: "" };
  if (normalized === "custom") return { mode: "custom", custom: value };
  if (!value) return { mode: presets[0], custom: "" };
  return { mode: "custom", custom: value };
}

type PresetFieldProps = {
  label: string;
  value: string;
  presets: readonly string[];
  onChange: (next: string) => void;
};

function PresetField({ label, value, presets, onChange }: PresetFieldProps) {
  const { mode, custom } = presetOrCustom(value, presets);
  const selectValue = presets.includes(mode as (typeof presets)[number]) ? mode : "custom";

  return (
    <label className="settings-row field-row">
      <span>{label}</span>
      <select
        className="filter-input"
        value={selectValue}
        onChange={(e) => {
          const next = e.target.value;
          onChange(next === "custom" ? custom || "" : next);
        }}
      >
        {presets.map((item) => (
          <option key={item} value={item}>
            {item === "custom" ? "Custom…" : item.charAt(0).toUpperCase() + item.slice(1)}
          </option>
        ))}
      </select>
      {selectValue === "custom" && (
        <input
          className="filter-input"
          value={custom || value}
          placeholder={`Custom ${label.toLowerCase()}`}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  );
}

function SettingsRow({
  label,
  helper,
  children,
}: {
  label: string;
  helper?: string;
  children: ReactNode;
}) {
  return (
    <label className="settings-row field-row">
      <span>{label}</span>
      {children}
      {helper ? <span className="muted settings-helper">{helper}</span> : null}
    </label>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
  children,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  children?: ReactNode;
}) {
  return (
    <div className="settings-toggle-block">
      <label className="field-row compact settings-toggle-row">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        {label}
      </label>
      {checked && children ? <div className="settings-toggle-panel">{children}</div> : null}
    </div>
  );
}

export function SettingsPage() {
  const { developerMode } = useAppMode();
  const [profile, setProfile] = useState<ChannelProfile>(emptyProfile);
  const [wizardTopic, setWizardTopic] = useState("");
  const [preview, setPreview] = useState<ChannelProfileSuggestion | null>(null);
  const [showProfileFields, setShowProfileFields] = useState(false);
  const [showYoutubeAdvanced, setShowYoutubeAdvanced] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elevenLabs, setElevenLabs] = useState<ElevenLabsConnectionStatus | null>(null);
  const [elevenLabsError, setElevenLabsError] = useState<string | null>(null);
  const [logoExists, setLogoExists] = useState(false);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [testingElevenLabs, setTestingElevenLabs] = useState(false);
  const [credentials, setCredentials] = useState<CredentialStatus[]>([]);
  const [credentialMessages, setCredentialMessages] = useState<Record<string, string>>({});
  const [automation, setAutomation] = useState<AutomationCenterState | null>(null);
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus | null>(null);
  const [visualMemoryPreview, setVisualMemoryPreview] = useState<Record<string, unknown> | null>(null);
  const [openSections, setOpenSections] = useState<SectionId[]>(["channel"]);

  const durationPreset = DURATION_PRESETS.includes(
    profile.default_duration_seconds as (typeof DURATION_PRESETS)[number],
  )
    ? String(profile.default_duration_seconds)
    : "custom";

  const configuredCredentialCount = useMemo(
    () => credentials.filter((item) => item.configured).length,
    [credentials],
  );

  function toggleSection(id: SectionId) {
    setOpenSections((current) => {
      if (current.includes(id)) {
        return current.filter((item) => item !== id);
      }
      const next = [...current, id];
      return next.length <= 2 ? next : next.slice(-2);
    });
  }

  function isOpen(id: SectionId) {
    return openSections.includes(id);
  }

  useEffect(() => {
    void fetchChannelProfile()
      .then((loaded) => {
        setProfile({ ...emptyProfile, ...loaded });
        if (loaded.channel_topic) {
          setWizardTopic(loaded.channel_topic);
        }
      })
      .catch(() => setProfile(emptyProfile));
    void fetchElevenLabsConnectionStatus().then(setElevenLabs).catch((err: unknown) => {
      setElevenLabsError(err instanceof Error ? err.message : "Failed to load ElevenLabs status");
    });
    void fetchChannelLogoStatus()
      .then((payload) => setLogoExists(Boolean(payload.logo_exists)))
      .catch(() => setLogoExists(false));
    void refreshCredentials().catch(() => setCredentials([]));
    void fetchAutomationCenter().then(setAutomation).catch(() => setAutomation(null));
    void fetchAutomationStatus().then(setAutomationStatus).catch(() => setAutomationStatus(null));
    void fetchLatestResults()
      .then((payload) => {
        const memory = payload.visual_memory_report || payload.visual_memory;
        if (memory?.subject || memory?.visual_memory_status) {
          setVisualMemoryPreview(memory as Record<string, unknown>);
        }
      })
      .catch(() => setVisualMemoryPreview(null));
  }, []);

  async function refreshCredentials() {
    const payload = await fetchCredentials();
    setCredentials(payload.providers || []);
  }

  function update<K extends keyof ChannelProfile>(key: K, value: ChannelProfile[K]) {
    setProfile((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  function toggleUploadPlatform(id: string) {
    setProfile((current) => {
      const next = current.upload_platforms.includes(id)
        ? current.upload_platforms.filter((p) => p !== id)
        : [...current.upload_platforms, id];
      return { ...current, upload_platforms: next };
    });
    setSaved(false);
  }

  async function handleGenerateProfile() {
    setError(null);
    setGenerating(true);
    setPreview(null);
    try {
      const suggestion = await suggestChannelProfile({ channel_topic: wizardTopic.trim() });
      setPreview(suggestion);
      const { reasoning, source, ...editable } = suggestion;
      setProfile((current) => ({
        ...current,
        ...editable,
        channel_topic: editable.channel_topic || wizardTopic.trim(),
      }));
      setShowProfileFields(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Profile generation failed");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    setError(null);
    try {
      const result = await saveChannelProfile(profile);
      setProfile(result);
      setPreview(null);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function handleTestElevenLabs() {
    setElevenLabsError(null);
    setTestingElevenLabs(true);
    try {
      setElevenLabs(await testElevenLabsConnection());
    } catch (err) {
      setElevenLabsError(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setTestingElevenLabs(false);
    }
  }

  return (
    <div className="product-page settings-page">
      <header className="header settings-header">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Studio Configuration</h1>
          <p className="subtitle">Compact panels for channel, credentials, branding, and runtime defaults.</p>
        </div>
        <button type="button" className="primary-btn" onClick={() => void handleSave()}>
          Save Profile
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {saved && <div className="success-banner">Channel profile saved.</div>}

      <div className="settings-accordion-stack">
        <SettingsAccordion
          id="channel"
          title="Channel Setup"
          subtitle="Topic wizard and generated profile fields"
          open={isOpen("channel")}
          onToggle={() => toggleSection("channel")}
        >
          <SettingsRow label="Channel topic" helper={`Examples: ${WIZARD_TOPIC_EXAMPLES.slice(0, 3).join(" · ")}`}>
            <textarea
              className="filter-input full-width"
              rows={2}
              value={wizardTopic}
              onChange={(e) => {
                setWizardTopic(e.target.value);
                setPreview(null);
                setSaved(false);
              }}
            />
          </SettingsRow>
          <div className="action-row">
            <button
              type="button"
              className="primary-btn"
              disabled={!wizardTopic.trim() || generating}
              onClick={() => void handleGenerateProfile()}
            >
              {generating ? "Generating…" : "Generate Profile"}
            </button>
            <button type="button" className="link-button" onClick={() => setShowProfileFields((value) => !value)}>
              {showProfileFields ? "Hide generated profile fields" : "Show generated profile fields"}
            </button>
          </div>
          {preview ? (
            <p className="muted settings-helper">
              Generated ({preview.source === "openai" ? "OpenAI" : "rule-based"}). Review before saving.
            </p>
          ) : null}
          {showProfileFields ? (
            <div className="settings-row-grid">
              {(
                [
                  ["channel_name", "Channel name"],
                  ["main_niche", "Main niche"],
                  ["sub_niche", "Sub niche"],
                  ["channel_topic", "Channel topic"],
                  ["target_audience", "Target audience"],
                ] as const
              ).map(([key, label]) => (
                <SettingsRow key={key} label={label}>
                  <input
                    className="filter-input full-width"
                    value={String(profile[key])}
                    onChange={(e) => update(key, e.target.value)}
                  />
                </SettingsRow>
              ))}
              <PresetField label="Language" value={profile.language} presets={LANGUAGE_PRESETS} onChange={(v) => update("language", v)} />
              <PresetField label="Tone / style" value={profile.tone_style} presets={TONE_PRESETS} onChange={(v) => update("tone_style", v)} />
              <PresetField
                label="Visual style"
                value={profile.visual_style || "cinematic realistic"}
                presets={VISUAL_STYLE_PRESETS}
                onChange={(v) => update("visual_style", v)}
              />
              <SettingsRow label="Preferred topics" helper="Comma-separated">
                <input
                  className="filter-input full-width"
                  value={listToText(profile.preferred_topics)}
                  onChange={(e) => update("preferred_topics", textToList(e.target.value))}
                />
              </SettingsRow>
              <SettingsRow label="Forbidden topics" helper="Comma-separated">
                <input
                  className="filter-input full-width"
                  value={listToText(profile.forbidden_topics)}
                  onChange={(e) => update("forbidden_topics", textToList(e.target.value))}
                />
              </SettingsRow>
            </div>
          ) : null}
        </SettingsAccordion>

        <SettingsAccordion
          id="credentials"
          title="API Credentials"
          subtitle="Local encrypted keys"
          badge={`${configuredCredentialCount}/${credentials.length}`}
          open={isOpen("credentials")}
          onToggle={() => toggleSection("credentials")}
        >
          <CredentialTable
            credentials={credentials}
            onRefresh={refreshCredentials}
            onError={setError}
            onMessage={(providerId, message) =>
              setCredentialMessages((current) => ({ ...current, [providerId]: message }))
            }
          />
          {Object.entries(credentialMessages).map(([providerId, message]) => (
            <p key={providerId} className="muted settings-helper">
              {providerId}: {message}
            </p>
          ))}
        </SettingsAccordion>

        <SettingsAccordion
          id="providers"
          title="Providers"
          subtitle="Default video and AI pipeline"
          open={isOpen("providers")}
          onToggle={() => toggleSection("providers")}
        >
          <div className="settings-row-grid">
            <SettingsRow label="Default platform">
              <select className="filter-input full-width" value={profile.default_platform} onChange={(e) => update("default_platform", e.target.value)}>
                {PLATFORM_OPTIONS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </SettingsRow>
            <SettingsRow label="Default duration">
              <select
                className="filter-input full-width"
                value={durationPreset}
                onChange={(e) => {
                  const next = e.target.value;
                  if (next !== "custom") {
                    update("default_duration_seconds", Number(next));
                  }
                }}
              >
                {DURATION_PRESET_OPTIONS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </SettingsRow>
            <SettingsRow label="Default provider">
              <select className="filter-input full-width" value={profile.default_provider} onChange={(e) => update("default_provider", e.target.value)}>
                {PROVIDER_PRESETS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </SettingsRow>
            <label className="field-row compact">
              <input
                type="checkbox"
                checked={profile.use_ai_director_default !== false}
                onChange={(e) => update("use_ai_director_default", e.target.checked)}
              />
              AI Director default ON
            </label>
            <label className="field-row compact">
              <input
                type="checkbox"
                checked={profile.use_prompt_critic_default !== false}
                onChange={(e) => update("use_prompt_critic_default", e.target.checked)}
              />
              Prompt Critic default ON
            </label>
          </div>
        </SettingsAccordion>

        <SettingsAccordion
          id="branding"
          title="Branding"
          subtitle="Subtitles, logo, CTA, intro/outro"
          open={isOpen("branding")}
          onToggle={() => toggleSection("branding")}
        >
          <ToggleRow label="Branding enabled" checked={profile.branding_enabled !== false} onChange={(v) => update("branding_enabled", v)} />
          <ToggleRow label="Subtitles enabled" checked={profile.subtitle_enabled !== false} onChange={(v) => update("subtitle_enabled", v)}>
            <SettingsRow label="Subtitle style">
              <select className="filter-input full-width" value={profile.subtitle_style || "tiktok"} onChange={(e) => update("subtitle_style", e.target.value)}>
                <option value="tiktok">TikTok</option>
                <option value="instagram_reels">Instagram Reels</option>
                <option value="youtube_shorts">YouTube Shorts</option>
              </select>
            </SettingsRow>
          </ToggleRow>
          <ToggleRow label="Logo enabled" checked={profile.logo_enabled !== false} onChange={(v) => update("logo_enabled", v)}>
            <div className="settings-logo-row">
              {logoPreviewUrl ? (
                <img className="settings-logo-preview" src={logoPreviewUrl} alt="Channel logo preview" />
              ) : logoExists ? (
                <div className="settings-logo-preview settings-logo-placeholder" title="Logo saved on disk">
                  PNG
                </div>
              ) : null}
              <SettingsRow label="Upload logo" helper={logoExists ? "Logo saved locally" : "PNG only"}>
                <input
                  className="filter-input full-width"
                  type="file"
                  accept="image/png"
                  disabled={logoUploading}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setLogoPreviewUrl((current) => {
                      if (current) URL.revokeObjectURL(current);
                      return URL.createObjectURL(file);
                    });
                    setLogoUploading(true);
                    void uploadChannelLogo(file)
                      .then(() => setLogoExists(true))
                      .catch((err) => setError(err instanceof Error ? err.message : "Logo upload failed"))
                      .finally(() => setLogoUploading(false));
                  }}
                />
              </SettingsRow>
            </div>
            <SettingsRow label="Logo position">
              <select className="filter-input full-width" value={profile.logo_position || "top_right"} onChange={(e) => update("logo_position", e.target.value)}>
                <option value="top_left">Top left</option>
                <option value="top_right">Top right</option>
                <option value="bottom_left">Bottom left</option>
                <option value="bottom_right">Bottom right</option>
              </select>
            </SettingsRow>
          </ToggleRow>
          <ToggleRow label="CTA enabled" checked={profile.cta_enabled !== false} onChange={(v) => update("cta_enabled", v)}>
            <SettingsRow label="CTA text">
              <input className="filter-input full-width" value={profile.cta_text || ""} onChange={(e) => update("cta_text", e.target.value)} />
            </SettingsRow>
          </ToggleRow>
          <ToggleRow label="Intro enabled" checked={Boolean(profile.intro_enabled)} onChange={(v) => update("intro_enabled", v)}>
            <SettingsRow label="Intro text">
              <input className="filter-input full-width" value={profile.intro_text || ""} onChange={(e) => update("intro_text", e.target.value)} />
            </SettingsRow>
          </ToggleRow>
          <ToggleRow label="Outro enabled" checked={Boolean(profile.outro_enabled)} onChange={(v) => update("outro_enabled", v)}>
            <SettingsRow label="Outro text">
              <input className="filter-input full-width" value={profile.outro_text || ""} onChange={(e) => update("outro_text", e.target.value)} />
            </SettingsRow>
          </ToggleRow>
        </SettingsAccordion>

        <SettingsAccordion
          id="voice-music"
          title="Voice & Music"
          subtitle="Narration and background audio"
          open={isOpen("voice-music")}
          onToggle={() => toggleSection("voice-music")}
        >
          <div className="settings-row-grid">
            <SettingsRow label="Narration provider">
              <select
                className="filter-input full-width"
                value={profile.default_narration_provider === "none" ? "disabled" : profile.default_narration_provider || "elevenlabs"}
                onChange={(e) => update("default_narration_provider", e.target.value)}
              >
                {NARRATION_PRESETS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </SettingsRow>
            <SettingsRow label="Default voice ID" helper="Optional ElevenLabs override">
              <input className="filter-input full-width mono" value={profile.default_voice || ""} onChange={(e) => update("default_voice", e.target.value)} />
            </SettingsRow>
            <SettingsRow label="Music provider">
              <select className="filter-input full-width" value={profile.music_provider || "none"} onChange={(e) => update("music_provider", e.target.value)}>
                {MUSIC_PRESETS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </SettingsRow>
            <SettingsRow label="Local music path" helper="Relative path when music provider is local">
              <input
                className="filter-input full-width mono"
                value={(profile as ChannelProfile & { music_track_path?: string }).music_track_path || "project_brain/music/default_background.mp3"}
                readOnly
              />
            </SettingsRow>
            <div className="action-row">
              <button type="button" className="secondary-btn" disabled={testingElevenLabs} onClick={() => void handleTestElevenLabs()}>
                {testingElevenLabs ? "Testing…" : "Test ElevenLabs"}
              </button>
            </div>
            {elevenLabsError ? <div className="error-banner">{elevenLabsError}</div> : null}
            {elevenLabs?.message ? <p className="muted settings-helper">{elevenLabs.message}</p> : null}
          </div>
        </SettingsAccordion>

        <SettingsAccordion
          id="upload"
          title="Upload & Platforms"
          subtitle="YouTube and short-form targets"
          open={isOpen("upload")}
          onToggle={() => toggleSection("upload")}
        >
          <label className="field-row compact">
            <input type="checkbox" checked={Boolean(profile.youtube_upload_enabled)} onChange={(e) => update("youtube_upload_enabled", e.target.checked)} />
            YouTube upload enabled
          </label>
          <SettingsRow label="OAuth client path" helper="Path to Google OAuth client JSON">
            <input
              className="filter-input full-width mono"
              value={profile.youtube_oauth_client_path || ""}
              onChange={(e) => update("youtube_oauth_client_path", e.target.value)}
            />
          </SettingsRow>
          <SettingsRow label="Privacy">
            <select className="filter-input full-width" value={profile.youtube_privacy || "private"} onChange={(e) => update("youtube_privacy", e.target.value)}>
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </SettingsRow>
          <label className="field-row compact">
            <input type="checkbox" checked={Boolean(profile.youtube_made_for_kids)} onChange={(e) => update("youtube_made_for_kids", e.target.checked)} />
            Made for kids
          </label>
          <label className="field-row compact">
            <input
              type="checkbox"
              checked={profile.upload_platforms.includes("tiktok")}
              onChange={() => toggleUploadPlatform("tiktok")}
            />
            TikTok package enabled
          </label>
          <label className="field-row compact">
            <input
              type="checkbox"
              checked={profile.upload_platforms.includes("instagram_reels")}
              onChange={() => toggleUploadPlatform("instagram_reels")}
            />
            Instagram package enabled
          </label>
          <button type="button" className="link-button" onClick={() => setShowYoutubeAdvanced((value) => !value)}>
            {showYoutubeAdvanced ? "Hide advanced OAuth details" : "Show advanced OAuth details"}
          </button>
          {showYoutubeAdvanced ? (
            <div className="settings-row-grid">
              <SettingsRow label="Default description">
                <textarea
                  className="filter-input full-width"
                  rows={2}
                  value={profile.youtube_default_description || ""}
                  onChange={(e) => update("youtube_default_description", e.target.value)}
                />
              </SettingsRow>
              <label className="field-row compact danger-text">
                <input
                  type="checkbox"
                  checked={profile.youtube_require_confirmation !== false}
                  onChange={(e) => update("youtube_require_confirmation", e.target.checked)}
                />
                Require confirmation before upload (recommended)
              </label>
            </div>
          ) : null}
        </SettingsAccordion>

        <SettingsAccordion
          id="automation"
          title="Automation"
          subtitle="Background jobs and upload automation"
          open={isOpen("automation")}
          onToggle={() => toggleSection("automation")}
        >
          <div className="settings-row-grid">
            <SettingsRow label="Automation enabled">
              <strong>{automation?.enabled ? "Yes" : "No"}</strong>
            </SettingsRow>
            <SettingsRow label="Daily job limit" helper={`Completed today: ${automationStatus?.completed_today ?? 0}`}>
              <strong>{automationStatus?.max_jobs_per_day ?? 5}</strong>
            </SettingsRow>
            <SettingsRow label="Auto upload enabled">
              <strong className={automation?.feature_flags?.auto_upload ? "danger-text" : undefined}>
                {automation?.feature_flags?.auto_upload ? "Enabled" : "Disabled"}
              </strong>
            </SettingsRow>
            <SettingsRow label="Comment drafts enabled">
              <strong>{automation?.feature_flags?.comment_drafts ? "Enabled" : "Disabled"}</strong>
            </SettingsRow>
          </div>
          <p className="muted settings-helper">Manage schedules and dangerous actions in Automation Center.</p>
        </SettingsAccordion>

        <SettingsAccordion
          id="asset-library"
          title="Asset Library"
          subtitle="Permanent vault for publish-ready finals"
          open={isOpen("asset-library")}
          onToggle={() => toggleSection("asset-library")}
        >
          <label className="field-row compact">
            <input
              type="checkbox"
              checked={Boolean(profile.asset_vault_enabled ?? true)}
              onChange={(e) => update("asset_vault_enabled", e.target.checked)}
            />
            Enable Asset Vault
          </label>
          <SettingsRow label="Asset copy mode" helper="Run folders always stay intact; vault receives a copy">
            <select
              className="filter-input full-width"
              value={profile.asset_copy_mode || "copy"}
              onChange={(e) => update("asset_copy_mode", e.target.value as ChannelProfile["asset_copy_mode"])}
            >
              <option value="copy">copy</option>
              <option value="move">move</option>
            </select>
          </SettingsRow>
          <p className="muted settings-helper">Vault root: assets/videos/</p>
        </SettingsAccordion>

        <SettingsAccordion
          id="local-access"
          title="Local Access"
          subtitle="Single-user vs SaaS login"
          open={isOpen("local-access")}
          onToggle={() => toggleSection("local-access")}
        >
          <label className="field-row compact">
            <input type="checkbox" checked={Boolean(profile.local_mode ?? true)} onChange={(e) => update("local_mode", e.target.checked)} />
            Local Single User Mode (auto-login)
          </label>
          <p className="muted settings-helper">
            {profile.local_mode ?? true
              ? "Login page hidden on startup. Turn off for SaaS-style username/password login."
              : "SaaS mode: login page and logout return after refresh."}
          </p>
        </SettingsAccordion>

        {developerMode ? (
          <SettingsAccordion
            id="advanced"
            title="Advanced / Developer"
            subtitle="Diagnostics and raw profile"
            open={isOpen("advanced")}
            onToggle={() => toggleSection("advanced")}
          >
            {visualMemoryPreview ? (
              <div className="settings-row-grid">
                <SettingsRow label="Visual memory subject">
                  <strong>{String(visualMemoryPreview.subject || "Unknown")}</strong>
                </SettingsRow>
                <SettingsRow label="Consistency score">
                  <strong>{String(visualMemoryPreview.consistency_score ?? "N/A")}</strong>
                </SettingsRow>
              </div>
            ) : null}
            <SettingsRow label="ElevenLabs probe">
              <span className="muted">{elevenLabs?.voices_probe_status || "not tested"}</span>
            </SettingsRow>
            <details className="settings-advanced-block">
              <summary>Raw channel profile JSON</summary>
              <pre className="json-block">{JSON.stringify(profile, null, 2)}</pre>
            </details>
            <p className="muted settings-helper">Runtime paths: project_brain/product_settings/channel_profile.json</p>
          </SettingsAccordion>
        ) : null}
      </div>
    </div>
  );
}
