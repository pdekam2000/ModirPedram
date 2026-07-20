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
  uploadBrandingAsset,
  brandingAssetFileUrl,
  type BrandingAssetKind,
  type ChannelProfile,
  type ChannelProfileSuggestion,
  type ElevenLabsConnectionStatus,
} from "../api/productClient";
import {
  fetchAutomationCenter,
  fetchAutomationStatus,
  fetchCredentials,
  fetchYouTubeAuthStatus,
  getYouTubeOAuthConnectUrl,
  updateAutomationCenter,
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
  youtube_channel_topic: "",
  tiktok_channel_topic: "",
  instagram_channel_topic: "",
  target_audience: "",
  language: "English",
  tone_style: "cinematic",
  visual_style: "cinematic realistic",
  default_platform: "youtube_shorts",
  default_duration_seconds: 30,
  default_provider: "runway",
  default_voice: "",
  default_narration_provider: "elevenlabs",
  audio_source: "runway_native",
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
  cta_style: "text_only",
  cta_graphic_position: "bottom_center",
  cta_graphic_duration_seconds: 5,
  intro_enabled: false,
  intro_text: "",
  intro_duration: 2,
  intro_type: "none",
  intro_fade_effect: "fade_in",
  outro_enabled: false,
  outro_text: "",
  outro_duration: 3,
  outro_type: "none",
  outro_fade_effect: "fade_out",
  outro_subscribe_enabled: true,
  outro_subscribe_style: "classic_red",
  outro_subscribe_custom_color: "#E62117",
  youtube_upload_enabled: false,
  youtube_privacy: "public",
  youtube_default_description: "",
  youtube_default_hashtags: [],
  youtube_upload_confirmed: false,
  youtube_credentials_configured: false,
  youtube_oauth_client_path: "",
  youtube_made_for_kids: false,
  youtube_require_confirmation: false,
  youtube_playlist_id: "",
  instagram_upload_enabled: false,
  instagram_app_id: "",
  instagram_app_secret: "",
  instagram_access_token: "",
  instagram_account_id: "",
  instagram_token_expires_at: "",
  instagram_public_base_url: "",
  instagram_privacy: "public",
  tiktok_upload_enabled: false,
  tiktok_client_key: "",
  tiktok_client_secret: "",
  tiktok_access_token: "",
  tiktok_privacy: "PUBLIC_TO_EVERYONE",
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

function formatInstagramTokenExpiry(iso: string | undefined) {
  if (!iso) return "Not set — exchanges automatically when you save a new token";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getInstagramTokenExpiryStatus(iso: string | undefined): {
  label: string;
  warning: string | null;
  urgent: boolean;
} {
  if (!iso) {
    return {
      label: "Not set — save/refresh token to set expiry",
      warning: "Token expiry is unknown. Refresh the Instagram token soon.",
      urgent: true,
    };
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return { label: iso, warning: null, urgent: false };
  }
  const label = formatInstagramTokenExpiry(iso);
  const msLeft = date.getTime() - Date.now();
  const daysLeft = Math.ceil(msLeft / (1000 * 60 * 60 * 24));
  if (msLeft <= 0) {
    return {
      label,
      warning: "Instagram token has EXPIRED. Generate a new token and save it.",
      urgent: true,
    };
  }
  if (daysLeft <= 7) {
    return {
      label,
      warning: `Instagram token expires in ${daysLeft} day${daysLeft === 1 ? "" : "s"}. Refresh now to avoid upload failures.`,
      urgent: true,
    };
  }
  return { label, warning: null, urgent: false };
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
  const [instagramExchangeMessage, setInstagramExchangeMessage] = useState<string | null>(null);
  const [elevenLabs, setElevenLabs] = useState<ElevenLabsConnectionStatus | null>(null);
  const [elevenLabsError, setElevenLabsError] = useState<string | null>(null);
  const [logoExists, setLogoExists] = useState(false);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [introSectionOpen, setIntroSectionOpen] = useState(false);
  const [outroSectionOpen, setOutroSectionOpen] = useState(false);
  const [ctaGraphicPreview, setCtaGraphicPreview] = useState<string | null>(null);
  const [brandingAssets, setBrandingAssets] = useState<Partial<Record<BrandingAssetKind, boolean>>>({});
  const [assetUploading, setAssetUploading] = useState<BrandingAssetKind | null>(null);
  const [testingElevenLabs, setTestingElevenLabs] = useState(false);
  const [credentials, setCredentials] = useState<CredentialStatus[]>([]);
  const [credentialMessages, setCredentialMessages] = useState<Record<string, string>>({});
  const [automation, setAutomation] = useState<AutomationCenterState | null>(null);
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus | null>(null);
  const [automationBusy, setAutomationBusy] = useState(false);
  const [youtubeAuth, setYoutubeAuth] = useState<Record<string, unknown> | null>(null);
  const [youtubeConnecting, setYoutubeConnecting] = useState(false);
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
        setBrandingAssets({
          cta_graphic: Boolean(loaded.cta_graphic_path),
          intro_image: Boolean(loaded.intro_image_path),
          intro_video: Boolean(loaded.intro_video_path),
          outro_image: Boolean(loaded.outro_image_path),
          outro_video: Boolean(loaded.outro_video_path),
        });
        if (loaded.youtube_channel_topic || loaded.channel_topic) {
          setWizardTopic(loaded.youtube_channel_topic || loaded.channel_topic);
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
    void fetchYouTubeAuthStatus().then(setYoutubeAuth).catch(() => setYoutubeAuth(null));
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

  async function refreshYouTubeAuth(): Promise<Record<string, unknown> | null> {
    try {
      const status = await fetchYouTubeAuthStatus();
      setYoutubeAuth(status);
      if (status.authenticated) {
        setProfile((current) => ({
          ...current,
          youtube_credentials_configured: true,
          youtube_channel_name: String(status.channel_name || current.youtube_channel_name || ""),
        }));
      }
      return status;
    } catch {
      setYoutubeAuth(null);
      return null;
    }
  }

  function handleConnectYouTube() {
    setYoutubeConnecting(true);
    window.open(getYouTubeOAuthConnectUrl(), "_blank", "noopener,noreferrer");
    let attempts = 0;
    const poll = window.setInterval(() => {
      attempts += 1;
      void refreshYouTubeAuth().then((status) => {
        if (status?.authenticated || attempts >= 90) {
          window.clearInterval(poll);
          setYoutubeConnecting(false);
        }
      });
    }, 2000);
  }

  const youtubeConnected = Boolean(youtubeAuth?.authenticated && youtubeAuth?.refreshable);

  function update<K extends keyof ChannelProfile>(key: K, value: ChannelProfile[K]) {
    setProfile((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  function handleBrandingAssetUpload(kind: BrandingAssetKind, file: File | undefined) {
    if (!file) return;
    setAssetUploading(kind);
    void uploadBrandingAsset(kind, file)
      .then((result) => {
        setBrandingAssets((current) => ({ ...current, [kind]: true }));
        const pathKey = {
          cta_graphic: "cta_graphic_path",
          intro_image: "intro_image_path",
          intro_video: "intro_video_path",
          outro_image: "outro_image_path",
          outro_video: "outro_video_path",
        }[kind] as keyof ChannelProfile;
        update(pathKey, result.asset_path);
        if (kind === "cta_graphic") {
          setCtaGraphicPreview((current) => {
            if (current) URL.revokeObjectURL(current);
            return URL.createObjectURL(file);
          });
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : `${kind} upload failed`))
      .finally(() => setAssetUploading(null));
  }

  const ctaStyle = profile.cta_style || "text_only";
  const ctaGraphicPosition = profile.cta_graphic_position || "bottom_center";
  const ctaGraphicPositionClass = ctaGraphicPosition.replace(/_/g, "-");
  const ctaPreviewGraphicSrc =
    ctaGraphicPreview ||
    (brandingAssets.cta_graphic || profile.cta_graphic_path ? brandingAssetFileUrl("cta_graphic") : null);

  function toggleUploadPlatform(id: string) {
    setProfile((current) => {
      const isEnabled = current.upload_platforms.includes(id);
      const nextPlatforms = isEnabled
        ? current.upload_platforms.filter((p) => p !== id)
        : [...current.upload_platforms, id];
      const next: ChannelProfile = { ...current, upload_platforms: nextPlatforms };
      if (id === "instagram_reels") {
        next.instagram_upload_enabled = !isEnabled;
      }
      if (id === "tiktok") {
        next.tiktok_upload_enabled = !isEnabled;
      }
      return next;
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
      const youtubeTopic = wizardTopic.trim();
      const result = await saveChannelProfile({
        ...profile,
        youtube_channel_topic: youtubeTopic,
        channel_topic: youtubeTopic,
      });
      setProfile(result);
      setPreview(null);
      setSaved(true);
      setInstagramExchangeMessage(result.instagram_token_exchange_message || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function handleAutoUploadToggle(enabled: boolean) {
    setAutomationBusy(true);
    setError(null);
    try {
      const updated = await updateAutomationCenter({
        feature_flags: {
          ...(automation?.feature_flags ?? {}),
          auto_upload: enabled,
        },
      });
      setAutomation(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update auto upload setting");
    } finally {
      setAutomationBusy(false);
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
          <SettingsRow label="YouTube topic" helper={`Examples: ${WIZARD_TOPIC_EXAMPLES.slice(0, 3).join(" · ")}`}>
            <textarea
              id="youtube_channel_topic"
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
          <SettingsRow label="Instagram topic">
            <textarea
              id="instagram_channel_topic"
              className="filter-input full-width"
              rows={2}
              placeholder="e.g. Satisfying skincare routines, face mask transformations, morning and night beauty rituals, glowing skin tips"
              value={profile.instagram_channel_topic || ""}
              onChange={(e) => update("instagram_channel_topic", e.target.value)}
            />
          </SettingsRow>
          <SettingsRow label="TikTok topic">
            <textarea
              id="tiktok_channel_topic"
              className="filter-input full-width"
              rows={2}
              placeholder="e.g. Quick fitness tips, gym motivation, trending challenges"
              value={profile.tiktok_channel_topic || ""}
              onChange={(e) => update("tiktok_channel_topic", e.target.value)}
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
                  ["youtube_channel_topic", "YouTube topic"],
                  ["channel_topic", "Global topic fallback"],
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
                <img className="settings-logo-preview" src={brandingAssetFileUrl("logo")} alt="Saved channel logo" />
              ) : null}
              <SettingsRow label="Upload logo" helper={logoExists ? "Logo saved locally (PNG with transparency recommended)" : "PNG with transparency recommended, max 5MB"}>
                <input
                  className="filter-input full-width"
                  type="file"
                  accept="image/png,image/jpeg"
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
                      .then((result) => {
                        setLogoExists(true);
                        update("logo_path", result.logo_path);
                      })
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
            <SettingsRow label="CTA style">
              <select className="filter-input full-width" value={ctaStyle} onChange={(e) => update("cta_style", e.target.value)}>
                <option value="text_only">Text only</option>
                <option value="text_icon">Text + Icon</option>
                <option value="graphic_overlay">Graphic overlay</option>
              </select>
            </SettingsRow>
            {ctaStyle === "graphic_overlay" ? (
              <>
                <SettingsRow label="CTA graphic" helper="PNG or JPG, max 2MB">
                  <input
                    className="filter-input full-width"
                    type="file"
                    accept="image/png,image/jpeg"
                    disabled={assetUploading === "cta_graphic"}
                    onChange={(e) => handleBrandingAssetUpload("cta_graphic", e.target.files?.[0])}
                  />
                </SettingsRow>
                <SettingsRow label="Graphic position">
                  <select
                    className="filter-input full-width"
                    value={ctaGraphicPosition}
                    onChange={(e) => update("cta_graphic_position", e.target.value)}
                  >
                    <option value="bottom_left">Bottom left</option>
                    <option value="bottom_center">Bottom center</option>
                    <option value="bottom_right">Bottom right</option>
                  </select>
                </SettingsRow>
                <SettingsRow label="Show before end (seconds)" helper="Default 5s">
                  <input
                    className="filter-input full-width"
                    type="number"
                    min={1}
                    max={30}
                    value={profile.cta_graphic_duration_seconds ?? 5}
                    onChange={(e) => update("cta_graphic_duration_seconds", Number(e.target.value) || 5)}
                  />
                </SettingsRow>
              </>
            ) : null}
            <SettingsRow label="CTA preview">
              <div className={`settings-cta-preview ${ctaGraphicPositionClass}`}>
                {ctaStyle === "graphic_overlay" && ctaPreviewGraphicSrc ? (
                  <img className="settings-cta-preview-graphic" src={ctaPreviewGraphicSrc} alt="CTA graphic preview" />
                ) : (
                  <span className="settings-cta-preview-text">
                    {profile.cta_text || "Follow for more"}
                    {ctaStyle === "text_icon" ? " ▶" : ""}
                  </span>
                )}
              </div>
            </SettingsRow>
          </ToggleRow>

          <div className={`settings-sub-accordion ${introSectionOpen ? "is-open" : ""}`}>
            <button type="button" className="settings-sub-accordion-header" onClick={() => setIntroSectionOpen((v) => !v)}>
              <span>Intro</span>
              <span>{introSectionOpen ? "−" : "+"}</span>
            </button>
            {introSectionOpen ? (
              <div className="settings-sub-accordion-body">
                <ToggleRow label="Enable intro" checked={Boolean(profile.intro_enabled)} onChange={(v) => update("intro_enabled", v)} />
                <SettingsRow label="Intro type">
                  <select className="filter-input full-width" value={profile.intro_type || "none"} onChange={(e) => update("intro_type", e.target.value)}>
                    <option value="none">None</option>
                    <option value="image_fade_in">Image fade-in</option>
                    <option value="video_clip">Video clip</option>
                  </select>
                </SettingsRow>
                {profile.intro_type === "image_fade_in" ? (
                  <>
                    <SettingsRow label="Intro image" helper="PNG or JPG">
                      <input
                        className="filter-input full-width"
                        type="file"
                        accept="image/png,image/jpeg"
                        disabled={assetUploading === "intro_image"}
                        onChange={(e) => handleBrandingAssetUpload("intro_image", e.target.files?.[0])}
                      />
                    </SettingsRow>
                    <SettingsRow label="Duration (seconds)">
                      <input
                        className="filter-input full-width"
                        type="number"
                        min={1}
                        max={5}
                        value={profile.intro_duration ?? 2}
                        onChange={(e) => update("intro_duration", Number(e.target.value) || 2)}
                      />
                    </SettingsRow>
                  </>
                ) : null}
                {profile.intro_type === "video_clip" ? (
                  <SettingsRow label="Intro video" helper="MP4, max 5 seconds">
                    <input
                      className="filter-input full-width"
                      type="file"
                      accept="video/mp4"
                      disabled={assetUploading === "intro_video"}
                      onChange={(e) => handleBrandingAssetUpload("intro_video", e.target.files?.[0])}
                    />
                  </SettingsRow>
                ) : null}
                {profile.intro_type !== "none" ? (
                  <SettingsRow label="Fade effect">
                    <select
                      className="filter-input full-width"
                      value={profile.intro_fade_effect || "fade_in"}
                      onChange={(e) => update("intro_fade_effect", e.target.value)}
                    >
                      <option value="none">None</option>
                      <option value="fade_in">Fade in</option>
                      <option value="slide_from_right">Slide from right</option>
                      <option value="slide_from_left">Slide from left</option>
                    </select>
                  </SettingsRow>
                ) : null}
                <SettingsRow label="Intro text (fallback card)" helper="Used when no image/video is uploaded">
                  <input className="filter-input full-width" value={profile.intro_text || ""} onChange={(e) => update("intro_text", e.target.value)} />
                </SettingsRow>
              </div>
            ) : null}
          </div>

          <div className={`settings-sub-accordion ${outroSectionOpen ? "is-open" : ""}`}>
            <button type="button" className="settings-sub-accordion-header" onClick={() => setOutroSectionOpen((v) => !v)}>
              <span>Outro</span>
              <span>{outroSectionOpen ? "−" : "+"}</span>
            </button>
            {outroSectionOpen ? (
              <div className="settings-sub-accordion-body">
                <ToggleRow label="Enable outro" checked={Boolean(profile.outro_enabled)} onChange={(v) => update("outro_enabled", v)} />
                <SettingsRow label="Outro type">
                  <select className="filter-input full-width" value={profile.outro_type || "none"} onChange={(e) => update("outro_type", e.target.value)}>
                    <option value="none">None</option>
                    <option value="image_fade_out">Image fade-out</option>
                    <option value="video_clip">Video clip</option>
                  </select>
                </SettingsRow>
                {profile.outro_type === "image_fade_out" ? (
                  <>
                    <SettingsRow label="Outro image" helper="PNG or JPG">
                      <input
                        className="filter-input full-width"
                        type="file"
                        accept="image/png,image/jpeg"
                        disabled={assetUploading === "outro_image"}
                        onChange={(e) => handleBrandingAssetUpload("outro_image", e.target.files?.[0])}
                      />
                    </SettingsRow>
                    <SettingsRow label="Duration (seconds)">
                      <input
                        className="filter-input full-width"
                        type="number"
                        min={1}
                        max={5}
                        value={profile.outro_duration ?? 3}
                        onChange={(e) => update("outro_duration", Number(e.target.value) || 3)}
                      />
                    </SettingsRow>
                  </>
                ) : null}
                {profile.outro_type === "video_clip" ? (
                  <SettingsRow label="Outro video" helper="MP4, max 5 seconds">
                    <input
                      className="filter-input full-width"
                      type="file"
                      accept="video/mp4"
                      disabled={assetUploading === "outro_video"}
                      onChange={(e) => handleBrandingAssetUpload("outro_video", e.target.files?.[0])}
                    />
                  </SettingsRow>
                ) : null}
                {profile.outro_type !== "none" ? (
                  <>
                    <SettingsRow label="Fade effect">
                      <select
                        className="filter-input full-width"
                        value={profile.outro_fade_effect || "fade_out"}
                        onChange={(e) => update("outro_fade_effect", e.target.value)}
                      >
                        <option value="none">None</option>
                        <option value="fade_out">Fade out</option>
                        <option value="slide_from_right">Slide from right</option>
                        <option value="slide_from_left">Slide from left</option>
                      </select>
                    </SettingsRow>
                    <ToggleRow
                      label="Subscribe button overlay"
                      checked={profile.outro_subscribe_enabled !== false}
                      onChange={(v) => update("outro_subscribe_enabled", v)}
                    />
                    {profile.outro_subscribe_enabled !== false ? (
                      <>
                        <SettingsRow label="Subscribe button style">
                          <select
                            className="filter-input full-width"
                            value={profile.outro_subscribe_style || "classic_red"}
                            onChange={(e) => update("outro_subscribe_style", e.target.value)}
                          >
                            <option value="classic_red">Classic red</option>
                            <option value="white">White</option>
                            <option value="custom">Custom color</option>
                          </select>
                        </SettingsRow>
                        {profile.outro_subscribe_style === "custom" ? (
                          <SettingsRow label="Custom button color">
                            <input
                              className="filter-input full-width"
                              type="color"
                              value={profile.outro_subscribe_custom_color || "#E62117"}
                              onChange={(e) => update("outro_subscribe_custom_color", e.target.value)}
                            />
                          </SettingsRow>
                        ) : null}
                      </>
                    ) : null}
                  </>
                ) : null}
                <SettingsRow label="Outro text (fallback card)" helper="Used when no image/video is uploaded">
                  <input className="filter-input full-width" value={profile.outro_text || ""} onChange={(e) => update("outro_text", e.target.value)} />
                </SettingsRow>
              </div>
            ) : null}
          </div>
        </SettingsAccordion>

        <SettingsAccordion
          id="voice-music"
          title="Voice & Music"
          subtitle="Narration and background audio"
          open={isOpen("voice-music")}
          onToggle={() => toggleSection("voice-music")}
        >
          <div className="settings-row-grid">
            <SettingsRow label="Audio source" helper="Runway clips include native audio by default">
              <select
                className="filter-input full-width"
                id="audio_source"
                value={profile.audio_source || "runway_native"}
                onChange={(e) => update("audio_source", e.target.value)}
              >
                <option value="runway_native">Runway native audio (default)</option>
                <option value="elevenlabs_narration">ElevenLabs narration</option>
              </select>
            </SettingsRow>
            <SettingsRow label="Narration provider" helper={profile.audio_source === "elevenlabs_narration" ? "Used when Audio source is ElevenLabs narration" : "Only used when Audio source is ElevenLabs narration"}>
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
          <div className="settings-subsection upload-platform-credentials">
            <div className="action-row" style={{ alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="primary-btn"
                disabled={youtubeConnecting}
                onClick={handleConnectYouTube}
              >
                {youtubeConnecting ? "Connecting…" : "🔐 Connect YouTube Account"}
              </button>
              {youtubeConnected ? (
                <span className="success-text" style={{ fontWeight: 600 }}>
                  ● YouTube Connected
                  {youtubeAuth?.channel_name ? ` — ${String(youtubeAuth.channel_name)}` : ""}
                </span>
              ) : (
                <span className="muted">Not connected — OAuth token required for uploads</span>
              )}
            </div>
            {youtubeAuth?.token_path ? (
              <p className="muted settings-helper mono">Token: {String(youtubeAuth.token_path)}</p>
            ) : null}
          </div>
          <SettingsRow label="OAuth client path" helper="Path to Google OAuth client JSON (auto-detected from secrets/)">
            <input
              className="filter-input full-width mono"
              value={profile.youtube_oauth_client_path || ""}
              onChange={(e) => update("youtube_oauth_client_path", e.target.value)}
            />
          </SettingsRow>
          <SettingsRow label="Privacy">
            <select className="filter-input full-width" value={profile.youtube_privacy || "public"} onChange={(e) => update("youtube_privacy", e.target.value)}>
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </SettingsRow>
          <SettingsRow label="Playlist ID" helper="Optional — auto-add uploads to this YouTube playlist">
            <input
              className="filter-input full-width mono"
              value={profile.youtube_playlist_id || ""}
              onChange={(e) => update("youtube_playlist_id", e.target.value)}
              placeholder="PLxxxxxxxx"
            />
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
          {profile.upload_platforms.includes("tiktok") ? (
            <div className="settings-subsection upload-platform-credentials">
              <SettingsRow label="TikTok Access Token">
                <input
                  id="tiktok_access_token"
                  className="filter-input full-width mono"
                  type="password"
                  autoComplete="off"
                  value={profile.tiktok_access_token || ""}
                  onChange={(e) => update("tiktok_access_token", e.target.value)}
                />
              </SettingsRow>
              <SettingsRow label="TikTok Client Key">
                <input
                  id="tiktok_client_key"
                  className="filter-input full-width mono"
                  type="text"
                  autoComplete="off"
                  value={profile.tiktok_client_key || ""}
                  onChange={(e) => update("tiktok_client_key", e.target.value)}
                />
              </SettingsRow>
              <SettingsRow label="TikTok Client Secret">
                <input
                  id="tiktok_client_secret"
                  className="filter-input full-width mono"
                  type="password"
                  autoComplete="off"
                  value={profile.tiktok_client_secret || ""}
                  onChange={(e) => update("tiktok_client_secret", e.target.value)}
                />
              </SettingsRow>
              <p className="muted settings-helper">Get these from developers.tiktok.com</p>
            </div>
          ) : null}
          <label className="field-row compact">
            <input
              type="checkbox"
              checked={profile.upload_platforms.includes("instagram_reels")}
              onChange={() => toggleUploadPlatform("instagram_reels")}
            />
            Instagram package enabled
          </label>
          {profile.upload_platforms.includes("instagram_reels") ? (
            <div className="settings-subsection upload-platform-credentials">
              <SettingsRow label="Facebook App ID" helper="Required to exchange short-lived tokens for 60-day tokens">
                <input
                  id="instagram_app_id"
                  className="filter-input full-width mono"
                  type="text"
                  autoComplete="off"
                  value={profile.instagram_app_id || ""}
                  onChange={(e) => update("instagram_app_id", e.target.value)}
                />
              </SettingsRow>
              <SettingsRow label="Facebook App Secret">
                <input
                  id="instagram_app_secret"
                  className="filter-input full-width mono"
                  type="password"
                  autoComplete="off"
                  value={profile.instagram_app_secret || ""}
                  onChange={(e) => update("instagram_app_secret", e.target.value)}
                />
              </SettingsRow>
              <SettingsRow
                label="Instagram Access Token"
                helper={`Token expires: ${getInstagramTokenExpiryStatus(profile.instagram_token_expires_at).label}`}
              >
                <input
                  id="instagram_access_token"
                  className="filter-input full-width mono"
                  type="password"
                  autoComplete="off"
                  value={profile.instagram_access_token || ""}
                  onChange={(e) => update("instagram_access_token", e.target.value)}
                />
              </SettingsRow>
              {(() => {
                const expiry = getInstagramTokenExpiryStatus(profile.instagram_token_expires_at);
                if (!expiry.warning) return null;
                return (
                  <p
                    className="muted settings-helper"
                    style={{
                      color: expiry.urgent ? "#b45309" : undefined,
                      fontWeight: expiry.urgent ? 600 : undefined,
                    }}
                  >
                    ⚠ {expiry.warning}
                  </p>
                );
              })()}
              {instagramExchangeMessage ? (
                <p className="muted settings-helper">{instagramExchangeMessage}</p>
              ) : null}
              <SettingsRow label="Instagram Account ID">
                <input
                  id="instagram_account_id"
                  className="filter-input full-width mono"
                  type="text"
                  autoComplete="off"
                  value={profile.instagram_account_id || ""}
                  onChange={(e) => update("instagram_account_id", e.target.value)}
                />
              </SettingsRow>
              <SettingsRow
                label="Instagram Public URL"
                helper="ngrok URL for Instagram video upload (e.g. https://abc.ngrok.io). Instagram cannot fetch videos from localhost."
              >
                <input
                  id="instagram_public_base_url"
                  className="filter-input full-width mono"
                  type="url"
                  autoComplete="off"
                  placeholder="https://abc.ngrok.io"
                  value={profile.instagram_public_base_url || ""}
                  onChange={(e) => update("instagram_public_base_url", e.target.value)}
                />
              </SettingsRow>
              <p className="muted settings-helper">
                Videos are served at <code>{'{ngrok}'}/media/video/{'{run_id}'}</code> from this API.
              </p>
              <p className="muted settings-helper">
                Paste a short-lived token from Graph API Explorer — it is exchanged automatically on save for a 60-day token.
              </p>
            </div>
          ) : null}
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
            <SettingsRow label="Auto upload enabled" helper="Upload to all configured platforms after each video is generated">
              <label className="field-row compact">
                <input
                  type="checkbox"
                  checked={Boolean(automation?.feature_flags?.auto_upload)}
                  disabled={automationBusy}
                  onChange={(e) => void handleAutoUploadToggle(e.target.checked)}
                />
                {automation?.feature_flags?.auto_upload ? "Enabled" : "Disabled"}
              </label>
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
